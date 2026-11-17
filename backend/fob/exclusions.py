"""Exclusões pontuais do FOB, autorizadas e conferidas no fechamento mensal.

Não altera o faturamento original nem o relatório por Vendedor Pai.
O arquivo de dados contém somente hashes de identidades, sem valores financeiros.
"""
from datetime import date
from functools import lru_cache
import json
from pathlib import Path
from .calculator import decimal
from .master_data import day,item_identity
from .freight import invoice_key


@lru_cache(maxsize=1)
def historical_keys():
    data=json.loads(Path(__file__).with_name('historical_exclusions.json').read_text(encoding='utf-8'))
    if data.get('versao')!=1:raise ValueError('Versão desconhecida das exclusões históricas FOB.')
    return {month:frozenset(record['itens']) for month,record in data['meses'].items()}


def january_invoice(item):
    if not date(2026,1,1)<=day(item['data'])<date(2026,2,1):return False
    try:key=invoice_key(item)
    except ValueError:return False
    return key in {('1','10','001','624834',2026),('1','111','001','771948',2026)}


def exclusion_reason(item):
    current=day(item['data'])
    # Peso nulo continua como pendência; não é convertido em peso zero.
    if current.year==2026 and 1<=current.month<=9 and item.get('peso') is not None and decimal(item['peso'])==0:
        return 'peso_zero_historico'
    if january_invoice(item):return 'conciliacao_janeiro'
    month=current.strftime('%Y-%m')
    keys=historical_keys().get(month)
    if not keys:return None
    try:identity=item_identity(item)
    except ValueError:return None
    return 'ausente_fechamento_mensal' if identity in keys else None
