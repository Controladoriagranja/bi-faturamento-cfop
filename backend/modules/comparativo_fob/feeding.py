"""Nova alimentação opt-in. Mesmo motor e contrato de resumo/detalhes, sem CRUD."""
from collections import defaultdict
from datetime import date
from decimal import localcontext
import os

from fastapi import HTTPException
from fob.calculator import code,item_key,decimal,requires_freight_fill
from fob.master_data import MasterCatalog,calculate_master_item,calculate_payroll,day,item_identity
from fob.master_repository import read_current,read_monthly,read_invoices,read_sales,read_status
from fob.freight import invoice_key
from fob.repository import read_invoice
from .aggregation import aggregate,public,order_items
from .config import CHANNELS,COSTS


def enabled():return os.environ.get('FOB_MASTER_ENABLED','0')=='1'


def execute_master(service,operation,start,end,choices,search,single,reference):
    """Resumo e detalhes têm o mesmo conjunto; filtros não mudam o rateio da folha."""
    try:
        with service.context.banco() as conn:
            rules=read_current(conn,start,end)
            # Bases de folha são lidas até o fim da vigência, mesmo em consulta de um dia.
            payroll_rules=[r for r in rules if r['tipo']=='folha']
            base_start=min([start,*[day(r['inicio']) for r in payroll_rules]])
            base_end=max([end,*[day(r['fim']) for r in payroll_rules]])
            if (base_end-base_start).days>62:raise ValueError('Divida a consulta em até dois meses para a base da folha.')
            all_items=read_sales(conn,base_start,base_end)
            for item in all_items:item.setdefault('_source','comercial.vw_faturamento_cfop_filtrado')
            monthly=read_monthly(conn)
            exact=start.isoformat()>=reference.period[0] and end.isoformat()<=reference.period[1]
            missing=[]
            note_status='presente_na_view'
            payroll_items=all_items;payroll_missing=[]
            reference_payroll=any(str(r['inicio'])==reference.period[0] and str(r['fim'])==reference.period[1] for r in payroll_rules)
            if exact or reference_payroll:
                indexed={}
                for item in all_items:
                    key=item_key(item)
                    if key not in reference.index:continue
                    if key in indexed:raise ValueError('Item duplicado no perímetro de referência.')
                    indexed[key]=item
                note=next(r for r in reference.items if r.sheet=='FaturamentoANeRA' and r.row==422)
                if item_key(note.fields) not in indexed:
                    try:
                        # Savepoint: consulta pontual não invalida leituras independentes.
                        with conn.transaction():raw=read_invoice(conn,unit='111',invoice='806684',customer='9880',raw=True)
                        note_status='nao_encontrada_na_tabela_bruta' if not raw else 'itens_divergentes_na_tabela_bruta'
                    except Exception:
                        raw=[];note_status='consulta_bruta_indisponivel'
                    candidates=[i for i in raw if item_key(i)==item_key(note.fields)]
                    if len(candidates)>1:raise ValueError('NF 806684 ambígua.')
                    if candidates:note_status='conciliada_na_tabela_bruta'
                    indexed[item_key(note.fields)]=candidates[0] if candidates else {**note.fields,'_provisional':True}
                reference_items=list(indexed.values())
                payroll_missing=[ref for ref in reference.items if item_key(ref.fields) not in indexed]
                payroll_items=[item for item in all_items if not reference.period[0]<=str(item['data'])<=reference.period[1]]+reference_items
                if exact:
                    all_items=reference_items;missing=payroll_missing
                for item in reference_items:
                    ref=reference.index[item_key(item)]
                    item.update(canal_grupo=ref.category,familia_grupo=ref.fields.get('familia') or 'Sem família')
            # Ler NF integral só onde existe frete cadastrado para a NF do conjunto.
            keys=[]
            for r in rules:
                if r['tipo']=='frete':
                    dims=r['dimensoes'];keys.append(tuple(dims[k] for k in ('empresa_contexto','unidade_documento','serie','nota_numero','ano_nf')))
            invoices=read_invoices(conn,keys)
            with localcontext() as ctx:
                ctx.prec=38
                payroll=calculate_payroll(rules,payroll_items)
                if payroll_missing:
                    for r in payroll_rules:
                        if str(r['inicio'])==reference.period[0] and str(r['fim'])==reference.period[1]:payroll[r['registro']]=None
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
        for ref in missing:
            if single('preencher_frete','0')=='1':continue
            identity=ref.fields
            if not start<=day(identity['data'])<=end:continue
            if choices['unidade'] and code(identity['unidade_documento']) not in choices['unidade']:continue
            family=identity.get('familia') or 'Sem família';channel=ref.category
            if choices['familia'] and family not in choices['familia']:continue
            if choices['canal'] and channel not in choices['canal']:continue
            if search and search not in ' '.join(str(identity.get(k) or '') for k in ('nota_numero','produto','cliente','produto_descricao')).casefold():continue
            calculated.append(dict(id=None,identificacao=identity,incluido=True,familia=family,canal=channel,
                peso=None,peso_excel=decimal(identity['peso']),valor_fob=None,preco_fob_kg=None,
                valor_fob_excel=ref.cached['valor_fob'],ausente_origem=True,status='ausente_origem',
                pendencias=['Registro não encontrado na origem; denominador da folha não confirmado.'],
                componentes={},provisorio=False,divergente=True))
        groups=defaultdict(list)
        for row in calculated:groups[row['familia'],row['canal']].append(row)
        result=dict(contexto=dict(modo='planilhas_mestre',data_inicio=start,data_fim=end,
            referencia_disponivel=exact,origem='PostgreSQL / três planilhas-mestre',
            ultima_importacao_valida=status['ultima_importacao_valida'],
            consulta_nf_806684=note_status,
            observacao='Despesas com vigência explícita. Folha usa base integral da vigência; ausências permanecem pendentes. '
              'Frete válido vem do banco; tipo 1 zero/nulo aguarda Fretes.xlsx. Januária usa custo mensal. '
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
