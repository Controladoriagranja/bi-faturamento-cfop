"""Substitutos de frete auditáveis. Não modifica a identificação nem o faturamento."""
from datetime import date
from .calculator import Rate, decimal

MONTHLY_TABLE = 'comercial.custo_mensal_januaria'
OCTOBER = date(2026, 10, 1)


def competence(value):
    if isinstance(value, date):
        return value.replace(day=1)
    text = str(value)
    if len(text) == 7:
        text += '-01'
    return date.fromisoformat(text).replace(day=1)


def invoice_key(item):
    """Chave diferente de item_key: nunca converte série/NF/empresa em números."""
    parts = tuple(item.get(k) for k in ('empresa_contexto','unidade_documento','serie','nota_numero'))
    # BTRIM da view fornecida: apenas bordas, nunca conversão numérica.
    parts = tuple(v.strip(' ') if i and isinstance(v,str) else v for i,v in enumerate(parts))
    if any(not isinstance(v,str) or not v or v != v.strip() or any(ord(c)<32 for c in v) for v in parts):
        raise ValueError('Identificação completa da NF indisponível; manual não associado.')
    day = item.get('data')
    day = day if isinstance(day,date) else date.fromisoformat(str(day))
    return (*parts, day.year)


def monthly_rate(day, records):
    requested = competence(day)
    source = requested if requested in records else OCTOBER
    record = records.get(source)
    inputs = dict(competencia_nf=requested.strftime('%Y-%m'),competencia_origem=source.strftime('%Y-%m'))
    if record is None:
        return Rate(None, MONTHLY_TABLE, 'competência própria; senão outubro/2026; senão pendente',
                    'pendente_custo_mensal', inputs)
    value = decimal(record.get('custo_kg'))
    if value is None or value < 0:
        raise ValueError('Custo mensal inválido na origem.')
    inputs.update(versao=record['versao'],atualizado_por=record.get('atualizado_por'),
                  atualizado_em=record.get('atualizado_em'),provisorio=source != requested)
    return Rate(value, MONTHLY_TABLE, 'custo mensal substitui todo o frete da unidade 102',
                'mensal_provisorio' if source != requested else 'mensal', inputs)


class FreightOverrides:
    def __init__(self, monthly=(), manuals=()):
        self.monthly = {}
        for row in monthly:
            key = competence(row['competencia'])
            if key in self.monthly:raise ValueError('Competência mensal duplicada.')
            self.monthly[key] = row
        self.manuals = {};self.duplicates = set()
        for row in manuals:
            key = tuple(row.get(k) for k in ('empresa','unidade','serie','nf','ano_nf'))
            if key in self.manuals:self.duplicates.add(key)
            self.manuals[key] = row

    def resolve(self, item):
        if str(item.get('unidade_documento')).strip(' ') == '102':
            return monthly_rate(item['data'], self.monthly), None
        try:key = invoice_key(item)
        except ValueError as error:return None,str(error)
        row = self.manuals.get(key)
        if row is None or row.get('frete_manual_id') is None:return None,None
        try:
            if key in self.duplicates:raise ValueError('Identificação duplicada na view de fretes.')
            if row.get('status_frete') != 'PREENCHIDO' or row.get('datas_distintas') != 1 or row.get('clientes_distintos') != 1:
                raise ValueError('Frete manual exige revisão da identificação.')
            total,weight = decimal(row.get('frete_manual_total')),decimal(row.get('peso_total_nf'))
            item_weight = decimal(item.get('peso'))
            if total is None or weight is None or total <= 0 or weight <= 0 or not row.get('quantidade_itens'):
                raise ValueError('Total/peso do frete manual inválido.')
            if item_weight is None or item_weight <= 0 or item_weight > weight:
                raise ValueError('Peso do item incompatível com o peso integral atual da NF.')
            if type(row.get('versao')) is not int or row['versao'] < 1:
                raise ValueError('Versão do frete manual inválida.')
            value=decimal(row.get('frete_manual_kg'))
            if value is None or value <= 0:raise ValueError('Frete/kg inválido na view de fretes.')
            return Rate(value,'comercial.vw_frete_manual_nf','frete_manual_total / peso_total_nf (NF integral)',
                'manual_nf',dict(empresa=key[0],unidade=key[1],serie=key[2],nf=key[3],ano_nf=key[4],
                    frete_total=total,peso_total_nf=weight,versao=row['versao'],
                    frete_manual_kg_view=row.get('frete_manual_kg'),atualizado_por=row.get('atualizado_por'),
                    atualizado_em=row.get('atualizado_em'))),None
        except (ValueError, ArithmeticError) as error:return None,str(error)
