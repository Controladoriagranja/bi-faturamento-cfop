"""Nova alimentação opt-in. Mesmo motor e contrato de resumo/detalhes, sem CRUD."""
from collections import defaultdict
from calendar import monthrange
from datetime import date
from decimal import localcontext
import os

from fastapi import HTTPException
from fob.calculator import code,item_key,decimal,requires_freight_fill
from fob.master_data import MasterCatalog,calculate_master_item,calculate_payroll,day,item_identity
from fob.master_repository import read_current,read_monthly,read_invoices,read_sales,read_status,SALES_VIEW
from fob.freight import invoice_key
from .aggregation import aggregate,public,order_items
from .config import CHANNELS,COSTS


def enabled():return os.environ.get('FOB_MASTER_ENABLED','0')=='1'


def execute_master(service,operation,start,end,choices,search,single,reference):
    """Resumo e detalhes têm o mesmo conjunto; filtros não mudam o rateio da folha."""
    try:
        with service.context.banco() as conn:
            # A consulta de um dia usa a mesma comissão mensal do fechamento.
            base_start=start.replace(day=1)
            base_end=end.replace(day=monthrange(end.year,end.month)[1])
            rules=read_current(conn,base_start,base_end)
            payroll_rules=[r for r in rules if r['tipo']=='folha']
            base_start=min([base_start,*[day(r['inicio']) for r in payroll_rules]])
            base_end=max([base_end,*[day(r['fim']) for r in payroll_rules]])
            if (base_end-base_start).days>62:raise ValueError('Divida a consulta em até dois meses para a base da folha.')
            all_items=read_sales(conn,base_start,base_end)
            for item in all_items:item.setdefault('_source',SALES_VIEW)
            monthly=read_monthly(conn)
            exact=start.isoformat()>=reference.period[0] and end.isoformat()<=reference.period[1]
            # O Excel histórico é apenas uma comparação. Não seleciona itens,
            # não altera canais e não cria registros provisórios no cálculo.
            note_status='sem_inclusao_de_itens_da_referencia'
            # Ler NF integral só onde existe frete cadastrado para a NF do conjunto.
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
            if not start<=day(item['data'])<=end:continue
            if choices['unidade'] and code(item.get('unidade_documento')) not in choices['unidade']:continue
            family=item.get('familia_grupo') or item.get('familia') or 'Sem família'
            channel=item.get('canal_grupo','Não classificado')
            if choices['familia'] and family not in choices['familia']:continue
            if choices['canal'] and channel not in choices['canal']:continue
            if search and search not in ' '.join(str(item.get(k) or '') for k in ('nota_numero','produto','cliente','produto_descricao')).casefold():continue
            row=calculate_master_item(item,catalog)
            row['identificacao'].update(empresa_contexto=item.get('empresa_contexto'),ano_nf=day(item['data']).year)
            row['chave_item']=item_identity(item)
            ref=reference.index.get(item_key(item)) if exact else None
            row.update(familia=family,canal=channel,produto_descricao=item.get('produto_descricao'),
                       valor_fob_excel=ref.cached['valor_fob'] if ref else 0,
                       peso_excel=ref.fields['peso'] if ref else None,
                       provisorio=bool(item.get('_provisional')),divergente=False)
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
            fonte=SALES_VIEW,comissao_base='mes_completo',
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
        return public(result)
    except ValueError as error:raise HTTPException(422,str(error)) from None
    except HTTPException:raise
    except Exception:raise HTTPException(503,'Não foi possível ler a alimentação FOB. Último lote válido não foi alterado.') from None
