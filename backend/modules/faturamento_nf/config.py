"""Configuração independente; nenhum indicador de Matrizes/Zootécnico."""
GROUP_ORDER = (
 'Varejo Centro-Oeste','Sem Vínculo','Varejo Grande BH','Varejo Jequitinhonha MG',
 'Varejo RJ','Varejo Sul Minas','Varejo Vale Aço','Raio 150 KM','Zona da Mata Mineira',
 'Triângulo Mineiro','CD Ribeirão das Neves','Januária',
 'Atacado - Vendedores externos - Outros','Atacado - Vendedores externos - AL/PE',
 'Atacado - Vendedores externos - BA/SE','Atacado - Vendedores externos - DF/GO',
 'Atacado - Vendedores externos - MG','Atacado - Vendedores externos - RJ',
 'Atacado - Vendedores externos - RN/PB','Atacado - Vendedores externos - Norte Brasil',
 'Atacado - Vendedores externos - Matéria Prima','Atacado - Vendedores internos')
PENDING_GROUPS = ()
UNIT_LABELS = {'10':'10 — Ave Nova','111':'111 — Real Alimentos',
               '180':'180 — Ribeirão das Neves','102':'102 — Januária'}
CONFIG = {'bi_key':'faturamento-nf',
 'bi':{'schema':'comercial','table':'vw_nf_por_vendedor_pai_faturamento',
       'filters':{'unidade':{'kind':'text','column':'unidade_documento'}}}}
