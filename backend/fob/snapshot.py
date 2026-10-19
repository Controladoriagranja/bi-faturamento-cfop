"""Catálogo transportável: mesmas regras, sem precisar distribuir o XLSX original."""
from dataclasses import asdict
import json
from pathlib import Path
from .calculator import decimal, item_key
from .reference import ExcelItem, WorkbookCatalog


def export_snapshot(catalog):
    return dict(versao=1,sha256=catalog.sha256,periodo=['2026-10-01','2026-10-04'],
        items=[asdict(item) for item in catalog.items],tables=catalog.tables,
        freight_totals=dict(catalog.freight_totals),commission_sheet=catalog.commission_sheet,
        sheets={'Despesas':{'rows':{'3':catalog.sheets['Despesas']['rows']['3']}},
                'ControleFrete':catalog.sheets['ControleFrete']})


class SnapshotCatalog(WorkbookCatalog):
    def __init__(self,path):
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if data.get('versao')!=1:raise ValueError('Versão de catálogo FOB não suportada.')
        self.sha256=data['sha256'];self.period=data['periodo']
        self.tables=data['tables'];self.sheets=data['sheets'];self.commission_sheet=data['commission_sheet']
        self.freight_totals={k:[decimal(v[0]),decimal(v[1]),v[2]] for k,v in data['freight_totals'].items()}
        self.items=[ExcelItem(**{**item,'cached':{k:decimal(v) for k,v in item['cached'].items()}}) for item in data['items']]
        self.index={item_key(item.fields):item for item in self.items}
        if len(self.index)!=len(self.items):raise ValueError('Itens duplicados no catálogo FOB.')
