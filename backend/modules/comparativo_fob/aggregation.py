"""Agregações ponderadas, sem converter pendência em zero ou média completa."""
from decimal import Decimal, localcontext
from fob.calculator import code
from .config import COSTS

ZERO=Decimal(0)


def order_items(rows,sort,direction):
    """Normaliza datas do PostgreSQL/Excel e mantém pendências no final."""
    def value(row):
        current=row.get(sort,row.get('identificacao',{}).get(sort))
        if current is None:return None
        if sort=='data':return current.isoformat() if hasattr(current,'isoformat') else str(current)
        if sort in ('nota_numero','produto','unidade_documento','cliente'):
            normalized=code(current)
            try:
                number=Decimal(normalized)
                if number.is_finite():return (0,number)
            except ArithmeticError:pass
            return (1,normalized)
        return current
    available=[r for r in rows if value(r) is not None]
    empty=[r for r in rows if value(r) is None]
    return sorted(available,key=value,reverse=direction=='desc')+empty


def aggregate(rows):
    with localcontext() as context:
        context.prec=38
        weight=sum((r.get('peso') or ZERO for r in rows),ZERO)
        pending=[r for r in rows if r.get('valor_fob') is None]
        missing=[r for r in rows if r.get('ausente_origem')]
        partial=sum((r.get('valor_fob') or ZERO for r in rows),ZERO)
        reference=sum((r['valor_fob_excel'] for r in rows),ZERO)
        reference_weight=sum((r.get('peso_excel',r.get('peso')) or ZERO for r in rows),ZERO)
        gross=sum(((r.get('peso') or ZERO)*(r.get('preco_praticado_kg') or ZERO) for r in rows),ZERO)
        value=None if pending else partial
        costs={}
        for key in COSTS:
            unresolved=sum(r.get(key+'_kg') is None for r in rows)
            cost=sum(((r.get(key+'_kg') or ZERO)*(r.get('peso') or ZERO) for r in rows),ZERO)
            costs[key]=dict(valor=None if unresolved else cost,valor_parcial=cost,
                            media_kg=cost/weight if weight and not unresolved else None,pendentes=unresolved)
        return dict(itens=len(rows),peso=weight,peso_excel=reference_weight,diferenca_peso=weight-reference_weight,peso_pendente=sum((r.get('peso') or ZERO for r in pending),ZERO),
            pendentes=len(pending),ausentes=len(missing),provisorios=sum(r.get('provisorio',False) for r in rows),
            divergencias=sum(r.get('divergente',False) for r in rows),
            preco_praticado_kg=gross/weight if weight and not missing and all(r.get('peso') is not None and r.get('preco_praticado_kg') is not None for r in rows) else None,
            valor_fob=value,valor_fob_parcial=partial,pm_fob_kg=value/weight if weight and value is not None else None,
            valor_fob_excel=reference,pm_fob_excel=reference/reference_weight if reference_weight else None,
            diferenca_fob=value-reference if value is not None else None,componentes=costs)


def public(value):
    if isinstance(value,Decimal):return str(value)
    if hasattr(value,'isoformat'):return value.isoformat()
    if isinstance(value,dict):return {key:public(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):return [public(item) for item in value]
    return value
