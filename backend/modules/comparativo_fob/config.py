"""Configuração exclusiva deste módulo; nenhum cadastro global é alterado."""
from pathlib import Path

CONFIG={'prefix':'/api/comercial/comparativo-fob','max_itens':5000,'cache_segundos':45}
CATALOG_PATH=Path(__file__).resolve().parent/'data'/'referencia_excel.json'
COSTS=('frete','comissao','adicional_comissao','contrato','contrato_administracao','logistica_reversa','pallet','descarga')
CHANNELS=('Varejo','Atacado','Subprodutos')
UNITS={'10':'10 — Ave Nova','111':'111 — Real Alimentos','180':'180 — Ribeirão das Neves','102':'102 — Januária'}
