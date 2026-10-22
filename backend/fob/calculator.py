"""Cálculo por item em Decimal; cadastros são fornecidos, nunca consultados aqui."""
from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import Protocol

ZERO = Decimal(0)


def decimal(value):
    if value is None or value == '': return None
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    if not number.is_finite(): raise ValueError('Número não finito.')
    return number


def code(value):
    text = str('' if value is None else value).strip()
    try: return str(int(Decimal(text))) if Decimal(text) == int(Decimal(text)) else text
    except (InvalidOperation, ValueError, OverflowError): return text


def item_key(item):
    day = item.get('data')
    if hasattr(day, 'isoformat'): day = day.isoformat()
    return (str(day or ''), *(code(item.get(k)) for k in ('unidade_documento','serie','nota_numero','produto','cliente')), format(decimal(item.get('peso')).normalize(),'f'))


@dataclass(frozen=True)
class Rate:
    value: Decimal | None
    origin: str
    formula: str = ''
    status: str = 'calculado'
    inputs: dict | None = None


@dataclass(frozen=True)
class ManualFreight:
    value: Decimal
    origin: str

    def __post_init__(self):
        if not self.origin.strip(): raise ValueError('Frete manual exige identificação da origem.')
        if decimal(self.value) is None: raise ValueError('Frete manual exige valor explícito.')


class Catalog(Protocol):
    """Contrato reutilizável por um futuro cadastro PostgreSQL, sem CRUD."""
    def locate(self, item): ...
    def components(self, item, reference) -> dict[str, Rate]: ...
    def freight(self, item, reference) -> Rate: ...


def requires_freight_fill(row):
    """Mesmo critério do Fretes.xlsx: tipo 1 zero/nulo fora de Januária,
    excluindo um preenchimento já válido. Outras despesas não entram nessa lista.
    """
    source=row.get('dados_entrada') or {}
    identity=row.get('identificacao') or {}
    freight=(row.get('componentes') or {}).get('frete') or {}
    return code(identity.get('unidade_documento'))!='102' and code(source.get('frete'))=='1' and \
        decimal(source.get('frete_kg')) in (None,ZERO) and freight.get('value') is None


def combine(price, weight, components):
    if any(rate.value is None for rate in components.values()): return None, None
    price_fob = price - sum((rate.value for rate in components.values()), ZERO)
    return price_fob, weight * price_fob


def calculate_item(item, catalog: Catalog, manual_freight: ManualFreight | None = None, *, freight_override: Rate | None = None):
    """Sem arredondamento intermediário; pendência impede FOB numérico do item."""
    with localcontext() as context:
        context.prec = 38
        out = dict(id=item.get('id'), origem_registro=item.get('_source', 'nao_informada'),
                   identificacao={k:item.get(k) for k in ('data','unidade_documento','serie','nota_numero','produto','cliente','cfop')},
                   dados_entrada={k:item.get(k) for k in ('vendedor','rede','uf','familia','frete','frete_kg','oc_principal','redespacho','preco_praticado','peso','valor_total_faturado','desc_finan')},
                   incluido=False, status='fora_perimetro_excel', componentes={}, preco_fob_kg=None, valor_fob=None)
        try:
            reference = catalog.locate(item)
        except (InvalidOperation, ValueError, AttributeError, TypeError) as error:
            out.update(incluido=None,status='pendente',pendencias=['Identificação incompleta: '+str(error)])
            return out
        if reference is None:
            out['motivo'] = 'Item não consta no recorte comprovado do Excel; não constitui regra geral de exclusão.'
            return out
        out.update(incluido=True, categoria=reference.category, origem_excel=reference.origin)
        try:
            weight = decimal(item.get('peso'))
            out['peso'] = weight
            price = decimal(item.get('preco_praticado'))
            out['preco_praticado_kg'] = price
            if price is None or weight is None: raise ValueError('Preço praticado ou peso ausente.')
            if weight == 0: raise ValueError('Peso zero: custo/kg não pode ser calculado.')
            components = catalog.components(item, reference)
            raw_freight = decimal(item.get('frete_kg'))
            freight_type = code(item.get('frete'))
            unit = code(item.get('unidade_documento'))
            needs_manual = freight_type == '1' and raw_freight in (None, ZERO)
            if unit == '102':
                # Todos os tipos: custo mensal tem precedência absoluta sobre NF/Excel.
                freight = freight_override if freight_override and freight_override.status in ('mensal','mensal_provisorio','pendente_custo_mensal') else Rate(
                    None,'comercial.custo_mensal_januaria','competência da emissão; fallback outubro/2026','pendente_custo_mensal')
            elif freight_override is not None:
                freight = freight_override
            elif manual_freight is not None:
                freight = Rate(decimal(manual_freight.value), manual_freight.origin, 'valor manual explícito por item', 'manual_informado')
            elif needs_manual:
                freight = Rate(None, 'Preenchimento manual não informado', 'frete tipo 1 sem valor', 'pendente_manual')
            else:
                freight = catalog.freight(item, reference)
            components = {'frete':freight, **components}
            price_fob, value_fob = combine(price, weight, components)
            available_price=price-sum((rate.value for rate in components.values() if rate.value is not None),ZERO)
            out.update(status='calculado' if value_fob is not None else 'pendente', peso=weight,
                       preco_praticado_kg=price, frete_kg_origem=raw_freight,
                       componentes={key:asdict(rate) for key,rate in components.items()},
                       preco_fob_kg=price_fob, valor_fob=value_fob,
                       preco_fob_disponivel_kg=available_price,valor_fob_disponivel=weight*available_price,
                       formula_preco_fob='preco_praticado - soma(componentes/kg)', formula_valor_fob='peso * preco_fob_kg',
                       pendencias=[key for key,rate in components.items() if rate.value is None])
            out.update({key+'_kg':rate.value for key,rate in components.items()})
        except (InvalidOperation, ValueError, ZeroDivisionError, KeyError) as error:
            out.update(status='pendente', pendencias=[str(error)])
        return out
