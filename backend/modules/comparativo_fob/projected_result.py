"""Resultado projetado separado do FOB: CPV e rateio mensal, exclusivamente PostgreSQL."""
from collections import defaultdict
from decimal import Decimal
from fob.calculator import code

ZERO=Decimal(0)


def read_months(conn,start,end):
    if conn.execute("SELECT to_regclass('comercial.fob_fechamento_mensal') objeto").fetchone()['objeto'] is None:return {}
    rows=conn.execute('''SELECT competencia,conteudo,versao,lote FROM comercial.fob_fechamento_mensal
        WHERE competencia BETWEEN date_trunc('month',%s::date)::date AND date_trunc('month',%s::date)::date''',[start,end]).fetchall()
    return {str(r['competencia'])[:7]:r for r in rows}


def enrich(rows,months,gross):
    by_month=defaultdict(list)
    for row in rows:by_month[str(row['identificacao']['data'])[:7]].append(row)
    result=[];status=[]
    for month,items in by_month.items():
        stored=months.get(month);catalog=stored['conteudo'] if stored else None
        rates={};pool=None;reason='Fechamento mensal/CPV ainda não cadastrado.'
        if catalog:
            scope=set(catalog['regra']['produtos_rateio'])
            allocated=[r for r in items if code(r['identificacao']['produto']) in scope]
            pallet_rows=[r for r in items if code(r['identificacao']['unidade_documento']) in ('10','111','180')]
            if all(r.get('pallet_kg') is not None for r in pallet_rows) and all(r.get('valor_fob') is not None for r in allocated):
                d=catalog['despesas']
                pallet=sum(((r['peso'] or ZERO)*r['pallet_kg'] for r in pallet_rows),ZERO)
                pool=sum((Decimal(d[k]) for k in ('despesa_administrativa','despesa_financeira','comercial_sem_comissao','logistica_total')),ZERO)-pallet
                denominator=sum((r['valor_fob'] for r in allocated),ZERO)
                grouped=defaultdict(list)
                for r in allocated:grouped[code(r['identificacao']['produto'])].append(r)
                if denominator>0:
                    for product,group in grouped.items():
                        weight=sum((r['peso'] or ZERO for r in group),ZERO)
                        rates[product]=(sum((r['valor_fob'] for r in group),ZERO)/denominator*pool/weight
                            if weight>0 else ZERO if weight==0 else None)
                    reason=''
                else:reason='Base FOB do rateio não é positiva.'
            else:reason='FOB ou pallet pendente na base mensal do rateio.'
        missing=0
        for base in items:
            row=dict(base);product=code(row['identificacao']['produto']);weight=row.get('peso')
            cpv=None;expense=None;origin=None
            if catalog:
                entry=catalog['cpv'].get(product)
                if entry:cpv=Decimal(entry['cpv_kg']);origin=entry['origem']
                expense=rates.get(product)
                if product in catalog['regra']['residuos_sem_cpv_rateio']:
                    cpv=expense=ZERO;origin='Regra explícita: E/G vazios em AnaliseMixPMInclusiveCDs!120:123'
                if weight is not None and weight==0:cpv=expense=ZERO
            projected=(row['valor_fob']-weight*(cpv+expense)
                if row.get('valor_fob') is not None and weight is not None and cpv is not None and expense is not None else None)
            if projected is None:missing+=1
            row.update(_resultado=projected,_cpv_kg=cpv,_despesas_kg=expense,_valor_produto=gross.get(row.get('id')),
                auditoria_resultado=dict(competencia=month,cpv_origem=origin,cpv_kg=cpv,rateio_kg=expense,
                    pool_mensal=pool,versao=stored['versao'] if stored else None,lote=str(stored['lote']) if stored else None,
                    formula='valor_fob - peso * (cpv_kg + rateio_kg)',
                    pendencia=reason or ('CPV ou produto fora do universo de rateio.' if projected is None else None)))
            result.append(row)
        status.append(dict(competencia=month,cadastrada=bool(catalog),itens_resultado_pendente=missing,
            pool_mensal=pool,origem_competencia=month,versao=stored['versao'] if stored else None,
            lote=str(stored['lote']) if stored else None,
            arquivo_despesas=catalog['origem_despesas']['arquivo'] if catalog else None,
            arquivo_cpv=catalog['origem_cpv']['arquivo'] if catalog else None,
            impostos_status='PENDENTE_CONFERENCIA_RESPONSAVEIS'))
    return result,status
