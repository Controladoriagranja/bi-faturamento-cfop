"""Análise regional somente leitura; reutiliza o motor operacional sem alterá-lo."""
from collections import defaultdict
from datetime import date
from calendar import monthrange
from decimal import Decimal, localcontext
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from fob.calculator import code
from .aggregation import public

ZERO = Decimal(0)


@lru_cache(maxsize=1)
def catalogue():
    return json.loads(Path(__file__).with_name('analise_vendedor_catalogo.json').read_text(encoding='utf-8'))


def normalized(value):
    return code(value) or '0'


def seller_map(records):
    """Um vendedor normalizado gera no máximo uma regional; conflito não multiplica itens."""
    groups = defaultdict(set)
    for record in records:
        groups[normalized(record['vendedor'])].add((record.get('vendedor_pai') or 'Não classificado').strip())
    return {key: next(iter(values)) if len(values) == 1 else 'Não classificado'
            for key, values in groups.items()}


def region(item, sellers):
    unit = normalized(item['identificacao']['unidade_documento'])
    if unit == '180': return 'CD Ribeirão da Neves'
    if unit == '102': return 'Januária'
    return sellers.get(normalized(item['dados_entrada'].get('vendedor')), 'Não classificado')


def pending_reason(row):
    labels={'frete':'Frete','comissao':'Comissão','contrato':'Contrato','pallet':'Pallet','descarga':'Descarga'}
    reasons=[]
    for key,value in row.get('componentes',{}).items():
        if value.get('value') is None:
            status=value.get('status','pendente')
            reason='revisar identificação da nota/itens' if status=='revisar_identificacao' else status.replace('_',' ')
            reasons.append(labels.get(key,key)+': '+reason+' — '+str(value.get('origin') or 'Origem não informada'))
    if row.get('_resultado') is None and row.get('auditoria_resultado',{}).get('pendencia'):
        reasons.append(row['auditoria_resultado']['pendencia'])
    return reasons


def summarize(items):
    weight = sum((r['peso'] or ZERO for r in items), ZERO)
    pending = sum(r.get('valor_fob') is None for r in items)
    fob = None if pending else sum((r['valor_fob'] for r in items), ZERO)
    result = dict(itens=len(items), peso=weight, fob=fob, pendentes=pending,
                  pm_fob=fob/weight if weight > 0 and fob is not None else (ZERO if not weight and not pending else None),
                  resultado=None, percentual_resultado=None)
    projected=[r.get('_resultado') for r in items]
    if all(v is not None for v in projected):result['resultado']=sum(projected,ZERO)
    result['pendentes_resultado']=sum(v is None for v in projected)
    for field,label in [('_cpv_kg','cpv_kg'),('_despesas_kg','despesas_kg')]:
        result[label]=(sum(((r['peso'] or ZERO)*r[field] for r in items),ZERO)/weight
            if weight>0 and all(r.get(field) is not None for r in items) else None)
    if result['resultado'] is not None and all(r.get('_valor_produto') is not None for r in items):
        denominator=sum((r['_valor_produto'] for r in items),ZERO)
        result['percentual_resultado']=result['resultado']/denominator if denominator>0 else None
    for label, fields in [('frete', ('frete_kg',)), ('comissao', ('comissao_kg', 'adicional_comissao_kg')),
                           ('contrato', ('contrato_kg',))]:
        complete = all(all(r.get(field) is not None for field in fields) for r in items)
        value = sum(((r['peso'] or ZERO)*sum((r.get(field) or ZERO for field in fields), ZERO) for r in items), ZERO)
        result[label+'_kg'] = value/weight if weight > 0 and complete else (ZERO if not items else None)
    return result


def build_analysis(rows, sellers, units=(), selected_regions=(), products=()):
    """Benchmark sempre nas quatro unidades; filtros de exibição não mudam a referência."""
    cat = catalogue()
    main = {normalized(p['codigo']) for p in cat['produtos']}
    cms = {normalized(p) for p in cat['cms']}
    product_filter = {normalized(p) for p in products}
    by_product = defaultdict(list)
    for item in rows:
        by_product[normalized(item['identificacao']['produto'])].append(item)
    benchmark = {p: summarize(items) for p, items in by_product.items()}
    visible = [r for r in rows if (not units or normalized(r['identificacao']['unidade_documento']) in units)
               and (not product_filter or normalized(r['identificacao']['produto']) in product_filter)]
    main_rows = [r for r in visible if normalized(r['identificacao']['produto']) in main]
    regions = list(cat['regionais'])
    extra = sorted({region(r, sellers) for r in main_rows} - set(regions))
    regions += extra
    denominator = summarize(main_rows)
    grouped = defaultdict(list)
    for item in main_rows:
        grouped[region(item, sellers), normalized(item['identificacao']['produto'])].append(item)
    details = []
    for (name, product), items in sorted(grouped.items()):
        summary = summarize(items)
        global_summary = benchmark[product]
        difference = None
        if summary['fob'] is not None and global_summary['pm_fob'] is not None:
            difference = summary['peso']*(summary['pm_fob']-global_summary['pm_fob']) if summary['peso'] > 0 else ZERO
        audits={str(r.get('auditoria_resultado',{}).get('competencia')):r.get('auditoria_resultado',{}) for r in items}
        details.append(dict(regional=name, produto=product, descricao=items[0].get('produto_descricao'),
                            **summary, pm_geral=global_summary['pm_fob'], diferenca=difference,
                            motivos_pendencia=sorted({reason for r in items for reason in pending_reason(r)}),
                            auditoria_resultado=list(audits.values()),origem_cpv='; '.join(
                                str(a.get('competencia',''))+' / '+str(a.get('cpv_origem') or 'Pendente') for a in audits.values())))
    def aggregate(items, product_rows):
        result = summarize(items)
        result['diferenca'] = (sum((p['diferenca'] for p in product_rows), ZERO)
                               if all(p['diferenca'] is not None for p in product_rows) else None)
        result['percentual_peso'] = result['peso']/denominator['peso'] if denominator['peso'] > 0 else None
        result['percentual_fob'] = (result['fob']/denominator['fob']
            if result['fob'] is not None and denominator['fob'] not in (None, ZERO) else None)
        base = result['fob']-result['diferenca'] if result['fob'] is not None and result['diferenca'] is not None else None
        result['percentual_diferenca'] = (ZERO if result['fob'] is not None and result['fob'] <= 0 else
            result['diferenca']/base if result['fob'] is not None and base else None)
        return result
    lines = []
    for name in regions:
        if selected_regions and name not in selected_regions: continue
        items = [r for r in main_rows if region(r, sellers) == name]
        result = aggregate(items, [p for p in details if p['regional'] == name])
        # K136: numerador do catálogo principal; denominador AJ de toda a regional.
        regional_base=[r for r in visible if region(r,sellers)==name]
        if result['resultado'] is not None and all(r.get('_valor_produto') is not None for r in regional_base):
            gross=sum((r['_valor_produto'] for r in regional_base),ZERO)
            result['percentual_resultado']=result['resultado']/gross if gross>0 else None
        # O Excel contém zeros fixos nestas células; não presumir ausência de contrato.
        if name in ('Januária', 'CD Ribeirão da Neves'):
            result['contrato_kg'] = None
        lines.append(dict(regional=name, fora_catalogo_regional=name in extra, **result))
    selected = [r for r in visible if not selected_regions or region(r, sellers) in selected_regions]
    totals = []
    for name, names in [('Atacado', set(cat['regionais'][:10])), ('Varejo', set(cat['regionais'][10:]))]:
        items = [r for r in selected if normalized(r['identificacao']['produto']) in main and region(r, sellers) in names]
        totals.append(dict(regional=name, **aggregate(items, [p for p in details if p['regional'] in names and (not selected_regions or p['regional'] in selected_regions)])))
    granel_rows = []
    for label, key in [('Pele à Granel', 'pele'), ('Dorso à Granel', 'dorso')]:
        items = [r for r in selected if normalized(r['identificacao']['produto']) == normalized(cat['granel'][key])
                 and normalized(r['identificacao']['unidade_documento']) in ('10', '111') and region(r, sellers) == 'Sem Vínculo']
        totals.append(dict(regional=label, **summarize(items)))
        granel_rows.extend(items)
    totals.append(dict(regional='CMS', **summarize([r for r in selected if normalized(r['identificacao']['produto']) in cms])))
    total_scope = [r for r in selected if normalized(r['identificacao']['produto']) in main
                   and region(r, sellers) in cat['regionais']] + granel_rows
    totals.append(dict(regional='Total Projetado sem Impostos', **summarize(total_scope)))
    for label in ('Impostos Projetados', 'Total Líquido Projetado'):
        totals.append(dict(regional=label, financeiro_pendente=True))
    included = main | cms | set(map(normalized, cat['granel'].values()))
    excluded = [r for r in selected if normalized(r['identificacao']['produto']) not in included]
    pending=[dict(regional=region(r,sellers),**r['identificacao'],peso=r.get('peso'),
        motivos=pending_reason(r)) for r in selected if r.get('valor_fob') is None]
    return dict(linhas=lines, consolidacoes=totals,
        pendencias_itens=pending[:500],total_pendencias_itens=len(pending),pendencias_truncadas=len(pending)>500,
        produtos=[p for p in details if not selected_regions or p['regional'] in selected_regions],
        filtros=dict(regionais=regions, produtos=cat['produtos']),
        validacao=dict(peso_base=sum((r['peso'] or ZERO for r in selected), ZERO),
            itens_fora_catalogo=len(excluded), peso_fora_catalogo=sum((r['peso'] or ZERO for r in excluded), ZERO),
            regionais_adicionais=extra, diferenca_global=sum((p['diferenca'] or ZERO for p in details), ZERO)
                if all(p['diferenca'] is not None for p in details) else None,
            resultado=None, comparacao_excel='Não executada; a validação abaixo verifica apenas o equilíbrio do benchmark.'))


def execute(service, request):
    from fastapi import HTTPException
    from .feeding import _month, enabled
    if not enabled(): raise HTTPException(409, 'A análise exige FOB_MASTER_ENABLED=1 e os cadastros operacionais.')
    allowed = {'data_inicio', 'data_fim', 'unidade', 'regional', 'produto'}
    params = request.query_params
    if set(params)-allowed: raise HTTPException(422, 'Filtro não configurado para a análise regional.')
    try:
        for key in ('data_inicio', 'data_fim'):
            if len(params.getlist(key)) != 1: raise ValueError('Informe uma data inicial e uma data final.')
        start, end = (date.fromisoformat(params[k]) for k in ('data_inicio', 'data_fim'))
        if start > end or start < date(2026, 1, 1) or end > date.today() or (end-start).days > 62:
            raise ValueError('Consulte um intervalo de até 63 dias, desde 01/01/2026 até hoje.')
        filters = {k: params.getlist(k) for k in ('unidade', 'regional', 'produto')}
        if any(len(v)>100 or any(len(x)>150 for x in v) for v in filters.values()): raise ValueError('Limite de filtro excedido.')
        if any(normalized(u) not in ('10','111','180','102') for u in filters['unidade']): raise ValueError('Unidade inválida.')
        headers = request.headers
        scope = sha256(('seller-analysis\0'+headers.get('authorization','')+'\0'+headers.get('x-portal-authorization','')).encode()).hexdigest()
        # Apenas o catálogo de códigos é necessário. Não carregar valores financeiros
        # de referência Excel; escopo de cache próprio evita misturar seus metadados.
        reference = SimpleNamespace(period=('0001-01-01','0001-01-01'), index={})
        with service.context.banco() as conn:
            bundle, cache = _month(service, conn, start.replace(day=1),
                end.replace(day=monthrange(end.year,end.month)[1]), reference, scope)
            sellers = seller_map(conn.execute('SELECT vendedor,vendedor_pai FROM comercial.vendedor_grupo').fetchall())
            from .projected_result import read_months,enrich
            closures=read_months(conn,start,end)
            from fob.master_repository import SALES_VIEW
            source=conn.execute('SELECT id,valor_produto FROM '+SALES_VIEW+' WHERE data>=%s AND data<=%s',
                [start.replace(day=1),end.replace(day=monthrange(end.year,end.month)[1])]).fetchall()
            gross={r['id']:r['valor_produto'] for r in source}
            if len(gross)!=len(source):raise ValueError('Identificadores de item duplicados na origem.')
        with localcontext() as ctx:
            ctx.prec=38
            enriched,financial_status=enrich([r for r,_ in bundle['rows']],closures,gross)
        rows = [r for r in enriched if start <= date.fromisoformat(str(r['identificacao']['data'])) <= end
                and normalized(r['identificacao']['unidade_documento']) in ('10','111','180','102')]
        with localcontext() as ctx:
            ctx.prec = 38
            result = build_analysis(rows, sellers, tuple(map(normalized, filters['unidade'])), filters['regional'], filters['produto'])
        result['contexto'] = dict(data_inicio=start, data_fim=end, fonte='comercial.vw_faturamento_vendedor_pai_itens',
            modo='planilhas_mestre', cache_calculo=cache, benchmark='Mesmo produto nas quatro unidades e todas as regionais no período; filtros de exibição não alteram esse PM.',
            percentuais='Peso e FOB divididos pelo total do catálogo principal nas unidades/produtos selecionados, antes do filtro regional.',
            fechamento=financial_status,impostos_status='PENDENTE_CONFERENCIA_RESPONSAVEIS',
            observacao_resultado='Custos da própria competência; rateio pela base integral do mês. % Resultado regional usa valor_produto de toda a regional, conforme K136.',
            pendencias=['Impostos: alíquotas e abrangência aguardam responsáveis', 'Regra da coluna contrato para RN e Januária'],
            catalogo_origem=catalogue()['origem'],catalogo_sha256=catalogue()['sha256'])
        return public(result)
    except ValueError as error: raise HTTPException(422, str(error)) from None
    except HTTPException: raise
    except Exception: raise HTTPException(503, 'Não foi possível consultar a análise regional FOB.') from None
