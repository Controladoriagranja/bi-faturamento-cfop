"""Nova alimentação opt-in. Mesmo motor e contrato de resumo/detalhes, sem CRUD."""
from collections import defaultdict
from copy import deepcopy
from calendar import monthrange
from datetime import date
from decimal import localcontext
from threading import RLock
from time import monotonic
import os

from fastapi import HTTPException
from fob.calculator import code,item_key,decimal,requires_freight_fill
from fob.master_data import MasterCatalog,calculate_master_item,calculate_payroll,day,item_identity
from fob.master_repository import read_current,read_monthly,read_invoices,read_sales,read_status,read_revision,SALES_VIEW
from fob.freight import invoice_key
from .aggregation import aggregate,public,order_items
from .config import CHANNELS,COSTS


def enabled():return os.environ.get('FOB_MASTER_ENABLED','0')=='1'


def _load_month(conn,base_start,base_end,reference):
    rules=read_current(conn,base_start,base_end)
    payroll_rules=[r for r in rules if r['tipo']=='folha']
    base_start=min([base_start,*[day(r['inicio']) for r in payroll_rules]])
    base_end=max([base_end,*[day(r['fim']) for r in payroll_rules]])
    if (base_end-base_start).days>62:raise ValueError('Divida a consulta em até dois meses para a base da folha.')
    all_items=read_sales(conn,base_start,base_end)
    # Regra adicional autorizada para janeiro/2026, somente no FOB. A tabela
    # original e o relatório Vendedor Pai continuam preservados.
    def zero_january(item):
        return (date(2026,1,1)<=day(item['data'])<date(2026,2,1)
            and item.get('peso') is not None and decimal(item['peso'])==0)
    excluded=[i for i in all_items if zero_january(i)]
    if excluded:all_items=[i for i in all_items if not zero_january(i)]
    for item in all_items:item.setdefault('_source',SALES_VIEW)
    monthly=read_monthly(conn)
    invoice_keys=set()
    for item in all_items:
        if code(item.get('unidade_documento'))=='102':continue
        try:invoice_keys.add(invoice_key(item))
        except ValueError:continue
    keys=[]
    for r in rules:
        if r['tipo']=='frete':
            dims=r['dimensoes'];key=tuple(dims[k] for k in ('empresa_contexto','unidade_documento','serie','nota_numero','ano_nf'))
            if key in invoice_keys:keys.append(key)
    invoices=read_invoices(conn,keys)
    with localcontext() as ctx:
        ctx.prec=38
        payroll=calculate_payroll(rules,all_items)
    catalog=MasterCatalog(rules,monthly,invoices,payroll)
    status=read_status(conn)
    calculated=[]
    for item in all_items:
        row=calculate_master_item(item,catalog)
        row['identificacao'].update(empresa_contexto=item.get('empresa_contexto'),ano_nf=day(item['data']).year)
        row['chave_item']=item_identity(item)
        row.update(familia=item.get('familia_grupo') or item.get('familia') or 'Sem família',
            canal=item.get('canal_grupo','Não classificado'),produto_descricao=item.get('produto_descricao'),
            provisorio=bool(item.get('_provisional')),divergente=False)
        ref=reference.index.get(item_key(item)) if reference.period[0]<=str(day(item['data']))<=reference.period[1] else None
        calculated.append((row,ref))
    return dict(rows=calculated,status=status,peso_zero_janeiro=len(excluded))


def _month(service,conn,start,end,reference,scope):
    lock=getattr(service,'_lock',None)
    if lock is None:
        lock=RLock();service._lock=lock
    with lock:
        revision=read_revision(conn) if scope is not None else None
        stable=revision and revision['somente_leitura']=='on' and revision['isolamento'] in ('repeatable read','serializable')
        key=(str(start),str(end),scope,tuple(sorted(revision.items()))) if stable else None
        now=monotonic();entry=getattr(service,'_fob_month_cache',None)
        if key is not None and entry and entry['key']==key and now-entry['time']<60:
            return entry['value'],'reutilizado'
        # Uma única competência/base por serviço; libera a anterior antes de
        # calcular outra. O resultado de erro nunca entra no cache.
        service._fob_month_cache=None;entry=None
        value=_load_month(conn,start,end,reference)
        if key is not None and len(value['rows'])<=30000:
            service._fob_month_cache=dict(key=key,time=monotonic(),value=value)
        return value,'recalculado' if key is not None else 'desabilitado'


def execute_master(service,operation,start,end,choices,search,single,reference,*,cache_scope=None):
    """Resumo e detalhes têm o mesmo conjunto; filtros não mudam o rateio da folha."""
    try:
        with service.context.banco() as conn:
            # A consulta de um dia usa a mesma comissão mensal do fechamento.
            base_start=start.replace(day=1)
            base_end=end.replace(day=monthrange(end.year,end.month)[1])
            bundle,cache_status=_month(service,conn,base_start,base_end,reference,cache_scope)
            exact=start.isoformat()>=reference.period[0] and end.isoformat()<=reference.period[1]
            # O Excel histórico é apenas uma comparação. Não seleciona itens,
            # não altera canais e não cria registros provisórios no cálculo.
            note_status='sem_inclusao_de_itens_da_referencia'
            status=bundle['status']
        response_key=(operation,str(start),str(end),tuple((k,tuple(choices[k])) for k in ('unidade','familia','canal')),
            search,single('pendentes','0'),single('preencher_frete','0'))
        if operation!='resumo':
            response_key+=tuple(single(k,default) for k,default in
                (('pagina','1'),('por_pagina','50'),('ordenar_por','nota_numero'),('ordem','asc')))
        responses=bundle.setdefault('responses',{})
        with service._lock:
            cached_response=responses.get(response_key)
            result=deepcopy(cached_response) if cached_response is not None else None
        if result is not None:
            result['contexto'].update(cache_calculo=cache_status,cache_resposta='reutilizada')
            return result
        calculated=[]
        for base,cached_ref in bundle['rows']:
            identity=base['identificacao']
            if not start<=day(identity['data'])<=end:continue
            if choices['unidade'] and code(identity.get('unidade_documento')) not in choices['unidade']:continue
            family,channel=base['familia'],base['canal']
            if choices['familia'] and family not in choices['familia']:continue
            if choices['canal'] and channel not in choices['canal']:continue
            if search and search not in ' '.join(str(identity.get(k) or '') for k in ('nota_numero','produto','cliente')).casefold()+' '+str(base.get('produto_descricao') or '').casefold():continue
            row=dict(base)
            ref=cached_ref if exact else None
            row.update(valor_fob_excel=ref.cached['valor_fob'] if ref else 0,peso_excel=ref.fields['peso'] if ref else None)
            # Agregador espera Decimal; referências não são parâmetros financeiros.
            if ref:
                row['peso_excel']=decimal(ref.fields['peso'])
                row['origem_excel']=ref.origin;row['formulas_excel']=ref.formulas
            if single('pendentes','0')=='1' and row.get('valor_fob') is not None:continue
            if single('preencher_frete','0')=='1' and not requires_freight_fill(row):continue
            calculated.append(row)
        groups=defaultdict(list)
        for row in calculated:groups[row['familia'],row['canal']].append(row)
        result=dict(contexto=dict(modo='planilhas_mestre',data_inicio=start,data_fim=end,
            referencia_disponivel=exact,origem='PostgreSQL / três planilhas-mestre',
            ultima_importacao_valida=status['ultima_importacao_valida'],
            consulta_nf_806684=note_status,
            fonte=SALES_VIEW,comissao_base='mes_completo',cache_calculo=cache_status,
            itens_peso_zero_excluidos_base_janeiro=bundle['peso_zero_janeiro'],
            observacao='Despesas com vigência explícita. Folha usa base integral da vigência; ausências permanecem pendentes. '
              'Frete final confirmado em Fretes.xlsx pode substituir o original; ausência permanece pendente. '
              'Januária: tipo 1 usa custo mensal; tipo maior que 1 usa zero, como no Excel. '
              'A referência Excel é comparativa e pode divergir; suas fórmulas históricas de frete não são exigidas. '
              'Canal histórico segue cadastro atual fora do recorte conferido.'),
            total=aggregate(calculated))
        if operation=='resumo':
            result.update(grupos=[dict(familia=f,canal=c,**aggregate(rows)) for (f,c),rows in sorted(groups.items())],
                familias=[dict(familia=f,**aggregate([r for r in calculated if r['familia']==f])) for f in sorted({r['familia'] for r in calculated})],
                canais=[dict(canal=c,**aggregate([r for r in calculated if r['canal']==c])) for c in
                    [*CHANNELS,*sorted({r['canal'] for r in calculated}-set(CHANNELS))]])
        else:
            page,size=int(single('pagina','1')),int(single('por_pagina','50'))
            sort=single('ordenar_por','nota_numero');direction=single('ordem','asc')
            allowed={'data','unidade_documento','nota_numero','cliente','produto','peso','preco_praticado_kg',
                     'valor_fob','preco_fob_kg','familia','canal',*(k+'_kg' for k in COSTS)}
            if sort not in allowed or direction not in ('asc','desc') or not 1<=page<=100000 or not 1<=size<=500:
                raise ValueError('Ordenação ou paginação inválida.')
            ordered=order_items(calculated,sort,direction)
            result.update(linhas=ordered[(page-1)*size:page*size],total_registros=len(calculated),pagina=page,por_pagina=size)
        if not exact:
            for group in [result['total'],*result.get('grupos',[]),*result.get('familias',[]),*result.get('canais',[])]:
                for key in ('peso_excel','valor_fob_excel','pm_fob_excel','diferenca_peso','diferenca_fob'):group[key]=None
        result=public(result)
        # Resultados pequenos já agrupados/paginados; no máximo oito por base.
        # A revisão MVCC foi conferida antes de consultar este armazenamento.
        with service._lock:
            if len(responses)>=8:responses.pop(next(iter(responses)))
            responses[response_key]=deepcopy(result)
        return result
    except ValueError as error:raise HTTPException(422,str(error)) from None
    except HTTPException:raise
    except Exception:raise HTTPException(503,'Não foi possível ler a alimentação FOB. Último lote válido não foi alterado.') from None
