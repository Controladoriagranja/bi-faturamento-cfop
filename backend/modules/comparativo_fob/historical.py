"""Histórico da view, sem extrapolar os cadastros/itens do Excel para outros meses.

Consulta agregada e paginação no PostgreSQL: nunca carrega o ano inteiro em Python.
O cadastro de canal é o atual, pois vendedor_grupo não possui vigência histórica.
"""
from collections import defaultdict
from decimal import Decimal, localcontext

from fastapi import HTTPException
from .aggregation import public
from .config import CHANNELS, COSTS
from fob.repository import read_freight_overrides
from dataclasses import asdict

ORIGIN = 'comercial.vw_faturamento_cfop_filtrado'
PENDING = 'Despesas e regras de inclusão do período ainda não validadas; FOB não calculado.'
BASE = """WITH vendedores AS (
 SELECT COALESCE(NULLIF(ltrim(trim(vendedor),'0'),''),'0') AS vendedor_normalizado,
 CASE WHEN count(DISTINCT canal_venda) = 1 THEN max(canal_venda) ELSE 'Não classificado' END AS canal_venda
 FROM comercial.vendedor_grupo GROUP BY 1
), origem_base AS (
 SELECT f.*, COALESCE(NULLIF(f.familia,''),'Sem família') AS familia_grupo,
 CASE WHEN upper(trim(f.familia)) = 'SUBPRODUTOS' THEN 'Subprodutos'
 ELSE COALESCE(NULLIF(trim(v.canal_venda),''),'Não classificado') END AS canal_grupo
 FROM comercial.vw_faturamento_cfop_filtrado f
 LEFT JOIN vendedores v
 ON COALESCE(NULLIF(ltrim(trim(f.vendedor),'0'),''),'0') =
    v.vendedor_normalizado
 WHERE f.data >= %s AND f.data <= %s
), manuais AS (
 SELECT m.empresa,m.unidade,m.serie,m.nf,m.ano_nf,
 CASE WHEN count(*)=1 AND bool_and(m.status_frete='PREENCHIDO'
   AND m.frete_manual_id IS NOT NULL AND m.versao>=1
   AND m.datas_distintas=1 AND m.clientes_distintos=1 AND m.quantidade_itens>0
   AND m.peso_total_nf>0 AND m.frete_manual_total>0 AND m.frete_manual_kg>0)
 THEN max(m.frete_manual_kg) ELSE NULL END AS custo_kg,
 max(m.peso_total_nf) AS peso_integral
 FROM comercial.vw_frete_manual_nf m
 WHERE (m.empresa,m.unidade,m.serie,m.nf,m.ano_nf) IN (
  SELECT empresa_contexto,btrim(unidade_documento),btrim(serie),btrim(nota_numero),extract(year from data)::int
  FROM origem_base WHERE btrim(unidade_documento)<>'102')
 GROUP BY m.empresa,m.unidade,m.serie,m.nf,m.ano_nf
), origem AS (
 SELECT f.*,CASE WHEN btrim(f.unidade_documento)='102' THEN coalesce(c.custo_kg,o.custo_kg)
   WHEN f.peso>0 AND f.peso<=m.peso_integral THEN m.custo_kg ELSE NULL END AS frete_substituto_kg
 FROM origem_base f
 LEFT JOIN manuais m ON m.empresa=f.empresa_contexto AND m.unidade=btrim(f.unidade_documento)
  AND m.serie=btrim(f.serie) AND m.nf=btrim(f.nota_numero) AND m.ano_nf=extract(year from f.data)::int
 LEFT JOIN comercial.custo_mensal_januaria c ON c.competencia=date_trunc('month',f.data)::date
 LEFT JOIN comercial.custo_mensal_januaria o ON o.competencia=DATE '2026-10-01'
), filtrado AS (SELECT * FROM origem WHERE {where})
"""


def aggregate_groups(groups):
    """Soma apenas medidas observadas; despesa ausente e referência não viram zero."""
    with localcontext() as ctx:
        ctx.prec = 38
        count = sum(g['itens'] for g in groups)
        weight = sum((g['peso'] or Decimal(0) for g in groups), Decimal(0))
        missing_price = sum(g.get('precos_ausentes', 0) for g in groups)
        missing_weight = sum(g.get('pesos_ausentes', 0) for g in groups)
        gross = sum((g.get('valor_praticado_observado') or Decimal(0) for g in groups), Decimal(0))
        freight_pending=sum(g.get('frete_pendentes',g['itens']) for g in groups)
        freight_value=sum((g.get('frete_valor_parcial') or Decimal(0) for g in groups),Decimal(0))
        components={key:dict(valor=None,valor_parcial=None,media_kg=None,pendentes=count) for key in COSTS}
        components['frete']=dict(valor=None if freight_pending else freight_value,valor_parcial=freight_value,
            media_kg=freight_value/weight if weight and not freight_pending else None,pendentes=freight_pending)
        return dict(itens=count, peso=weight, pesos_ausentes=missing_weight,
            precos_ausentes=missing_price, valor_praticado_observado=gross,
            preco_praticado_kg=gross/weight if weight and not missing_price and not missing_weight else None,
            pendentes=count, peso_pendente=weight, ausentes=0, provisorios=0, divergencias=0,
            valor_fob=None if count else Decimal(0), valor_fob_parcial=None,
            pm_fob_kg=None, peso_excel=None, valor_fob_excel=None, pm_fob_excel=None,
            diferenca_peso=None, diferenca_fob=None,
            componentes=components)


def audit_item(row,overrides=None):
    weight, price = row.get('peso'), row.get('preco_praticado')
    freight=row.get('frete_kg')
    manual=str(row.get('frete') or '').strip()=='1' and (freight is None or freight==0)
    result=dict(id=row['id'], incluido=True, status='pendente_cadastro_periodo',
        identificacao={key:row.get(key) for key in ('data','unidade_documento','serie','nota_numero','produto','cliente','cfop')},
        familia=row['familia_grupo'], canal=row['canal_grupo'], peso=weight,
        produto_descricao=row.get('produto_descricao'), preco_praticado_kg=price,
        origem_registro=ORIGIN, origem_canal='comercial.vendedor_grupo.canal_venda (cadastro atual); família SUBPRODUTOS separada',
        dados_entrada={key:row.get(key) for key in ('frete','frete_kg','preco_praticado','valor_total_faturado','peso')},
        valor_fob=None, preco_fob_kg=None, valor_fob_excel=None, provisorio=False,
        pendencias=[PENDING], divergencias_entrada={},
        componentes={key:dict(value=None, status='pendente_cadastro_periodo',
            origin='Sem cadastro com vigência para o período consultado.',
            formula='Não aplicada; os parâmetros de outubro não foram extrapolados.') for key in COSTS},
        **{key+'_kg':None for key in COSTS})
    if overrides is not None:
        substitute,warning=overrides.resolve(row)
        if substitute is not None:
            result['componentes']['frete']=asdict(substitute)
            result['frete_kg']=substitute.value
        if warning:result['avisos_frete']=[warning]
    if manual and result['componentes']['frete']['value'] is None and str(row.get('unidade_documento')).strip()!='102':
        result['pendencias'].append('Frete tipo 1 sem valor: exige preenchimento manual.')
        result['componentes']['frete'].update(status='pendente_manual',
            origin=ORIGIN+'.frete_kg nulo/zero com tipo de frete 1',formula='Aguardar preenchimento manual com origem identificada.')
    return result


def execute_history(context, operation, start, end, choices, search, single):
    clauses = ['TRUE']; params = [start,end]
    columns = dict(unidade="COALESCE(NULLIF(ltrim(trim(unidade_documento),'0'),''),'0')",
                   familia='familia_grupo',canal='canal_grupo')
    for key, selected in choices.items():
        if selected:
            clauses.append(columns[key]+' = ANY(%s)'); params.append(selected)
    if search:
        # Busca literal: %, _ e barra não são curingas fornecidos pelo usuário.
        escaped=search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        clauses.append("concat_ws(' ',nota_numero,produto,cliente,produto_descricao) ILIKE %s")
        params.append('%'+escaped+'%')
    base=BASE.format(where=' AND '.join(clauses))
    page=size=None
    sort=single('ordenar_por','nota_numero'); direction=single('ordem','asc')
    sort_columns={key:key for key in ('data','unidade_documento','nota_numero','cliente','produto','peso')}
    sort_columns.update(familia='familia_grupo',canal='canal_grupo',preco_praticado_kg='preco_praticado')
    # Todos os valores FOB e despesas estão pendentes; ordenar pela chave mantém estabilidade.
    sort_columns.update({key:'id' for key in ('valor_fob','preco_fob_kg',*(key+'_kg' for key in COSTS))})
    sort_columns['frete_kg']='frete_substituto_kg'
    if sort not in sort_columns or direction not in ('asc','desc'):raise HTTPException(422,'Ordenação inválida.')
    if operation=='detalhes':
        try:page,size=int(single('pagina','1')),int(single('por_pagina','50'))
        except ValueError:raise HTTPException(422,'Paginação inválida.')
        if not 1<=page<=100000 or not 1<=size<=500:raise HTTPException(422,'Paginação fora do limite.')
    elif operation!='resumo':raise HTTPException(404,'Operação não disponível.')
    with context.banco() as conn:
        groups=conn.execute(base+"""SELECT familia_grupo AS familia, canal_grupo AS canal,
            count(*) AS itens, sum(peso) AS peso,
            count(*) FILTER (WHERE peso IS NULL) AS pesos_ausentes,
            count(*) FILTER (WHERE preco_praticado IS NULL) AS precos_ausentes,
            count(*) FILTER (WHERE frete_substituto_kg IS NULL OR peso IS NULL) AS frete_pendentes,
            sum(peso * frete_substituto_kg) AS frete_valor_parcial,
            sum(peso * preco_praticado) AS valor_praticado_observado
            FROM filtrado GROUP BY familia_grupo,canal_grupo ORDER BY familia_grupo,canal_grupo""",params).fetchall()
        result=dict(contexto=dict(modo='historico',data_inicio=start,data_fim=end,
            referencia_disponivel=False,origem=ORIGIN,linhas_fora_perimetro=None,
            observacao=PENDING+' Inclusões/exclusões são as da view; exceções pontuais do Excel não são extrapoladas. '
                'Canal conforme cadastro atual de vendedores, sem vigência histórica.'),
            total=aggregate_groups(groups))
        if operation=='detalhes':
            rows=conn.execute(base+'SELECT * FROM filtrado ORDER BY '+sort_columns[sort]+' '+direction+' NULLS LAST, id ASC LIMIT %s OFFSET %s',
                [*params,size,(page-1)*size]).fetchall()
            overrides=read_freight_overrides(conn,rows)
            return public(dict(**result,linhas=[audit_item(row,overrides) for row in rows],
                total_registros=result['total']['itens'],pagina=page,por_pagina=size))
    by_family=defaultdict(list);by_channel=defaultdict(list)
    for group in groups:
        by_family[group['familia']].append(group);by_channel[group['canal']].append(group)
    return public(dict(**result,
        grupos=[dict(familia=g['familia'],canal=g['canal'],**aggregate_groups([g])) for g in groups],
        familias=[dict(familia=k,**aggregate_groups(v)) for k,v in sorted(by_family.items())],
        canais=[dict(canal=k,**aggregate_groups(by_channel.get(k,[]))) for k in
            [*CHANNELS,*sorted(set(by_channel)-set(CHANNELS))]]))
