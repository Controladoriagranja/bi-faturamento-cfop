"""Serviço no contrato existente; métricas agregadas somente no PostgreSQL."""
from datetime import date,timedelta
from decimal import Decimal
from fastapi import HTTPException
from .config import CONFIG,GROUP_ORDER,PENDING_GROUPS

def filtros_request(request, extras=()):
    permitidos={'data_inicio','data_fim','unidade',*extras}
    if set(request.query_params)-permitidos:raise HTTPException(422,'Filtro não configurado.')
    datas=[]
    for key in ('data_inicio','data_fim'):
        values=request.query_params.getlist(key)
        if len(values)>1:raise HTTPException(422,'Data duplicada.')
        value=values[0] if values else None
        try:
            parsed=date.fromisoformat(value) if value else None
            if parsed and parsed.isoformat()!=value:raise ValueError()
        except ValueError:raise HTTPException(422,'Data inválida. Use AAAA-MM-DD.')
        datas.append(parsed)
    if all(datas) and datas[0]>datas[1]:raise HTTPException(422,'Intervalo de datas invertido.')
    unidades=list(dict.fromkeys(v.strip() for v in request.query_params.getlist('unidade') if v.strip()))
    if len(unidades)>100 or any(len(v)>30 for v in unidades):raise HTTPException(422,'Limite do filtro excedido.')
    if datas[1]==date.max:raise HTTPException(422,'Data final fora do intervalo suportado.')
    clauses=[];params=[]
    if datas[0]:clauses.append('data >= %s');params.append(datas[0])
    if datas[1]:clauses.append('data < %s');params.append(datas[1]+timedelta(days=1))
    if unidades:clauses.append('unidade_documento = ANY(%s)');params.append(unidades)
    return (' WHERE '+' AND '.join(clauses) if clauses else ''),params,datas,unidades

SUMMARY_SQL = '''WITH selecionadas AS (SELECT * FROM {source} {where})
SELECT CASE WHEN GROUPING(vendedor_pai)=1 THEN NULL ELSE vendedor_pai END AS vendedor_pai,
       GROUPING(vendedor_pai)=1 AS total,
       COUNT(*) AS qtde_nfs,
       COALESCE(SUM(qtde_produtos_distintos),0)::NUMERIC/NULLIF(COUNT(*),0) AS qtde_produto_por_nf,
       COALESCE(SUM(peso_total_nf),0)/NULLIF(COUNT(*),0) AS peso_por_nf,
       COALESCE(SUM(valor_total_nf),0)/NULLIF(COUNT(*),0) AS ticket_medio_por_nf,
       COALESCE(SUM(peso_total_nf),0) AS peso_total,
       COALESCE(SUM(valor_total_nf),0) AS valor_total,
       COALESCE(SUM(qtde_produtos_distintos),0) AS soma_produtos_distintos,
       COUNT(*) FILTER(WHERE divergencia_nf) AS nfs_divergentes,
       MAX(carregado_em) AS atualizado_em
FROM selecionadas GROUP BY GROUPING SETS ((vendedor_pai),())'''

def publico(row):
    out={k:(str(v) if isinstance(v,Decimal) else v.isoformat() if hasattr(v,'isoformat') else v) for k,v in row.items()}
    for k in ('qtde_produto_por_nf','peso_por_nf','ticket_medio_por_nf'):
        if out.get(k) is None:out[k]='0'
    return out

def payload_resumo(rows,datas,unidades):
    total=next(r for r in rows if r['total'])
    if total['nfs_divergentes']:raise HTTPException(409,'Há NFs com chave, data ou vendedor divergente. Confira a auditoria antes de publicar indicadores.')
    grupos={r['vendedor_pai']:publico(r) for r in rows if not r['total']}
    ordered=[]
    zero={'qtde_nfs':0,'qtde_produto_por_nf':'0','peso_por_nf':'0','ticket_medio_por_nf':'0','peso_total':'0','valor_total':'0','soma_produtos_distintos':0}
    for label in GROUP_ORDER:
        item=grupos.pop(label,{'vendedor_pai':label,**zero})
        item['pendente']=label in PENDING_GROUPS
        ordered.append(item)
    ordered += [grupos[k] for k in sorted(grupos)]
    return dict(grupos=ordered,total=publico(total),
      periodo=dict(data_inicio=datas[0].isoformat() if datas[0] else None,data_fim=datas[1].isoformat() if datas[1] else None),
      unidades=unidades,fonte='comercial.vw_nf_por_vendedor_pai',versao_regras='faturamento-nf-2026-10-14')

class FaturamentoNFService:
    key=CONFIG['bi_key']
    definition=CONFIG
    def __init__(self,context):self.context=context
    def execute(self,operation,request):
        from psycopg import sql
        if operation == 'detalhes':
            from .details import detalhes
            return detalhes(self.context, request)
        if operation not in ('filtros','resumo'):raise HTTPException(404,'Operação não disponível.')
        where,params,datas,unidades=filtros_request(request)
        source=sql.Identifier(CONFIG['bi']['schema'],CONFIG['bi']['table'])
        with self.context.banco() as conn:
            if operation=='filtros':
                # Opções globais: não desaparecem ao selecionar um intervalo vazio.
                q=sql.SQL('SELECT DISTINCT unidade_documento FROM {} WHERE unidade_documento IS NOT NULL ORDER BY 1').format(source)
                options=conn.execute(q).fetchall()
                bounds=conn.execute(sql.SQL('SELECT MIN(data) AS inicio,MAX(data) AS fim FROM {}').format(source)).fetchone()
                return dict(unidade=[dict(value=r['unidade_documento'],label='Unidade '+r['unidade_documento']) for r in options],
                    periodo_disponivel=dict(data_inicio=bounds['inicio'].isoformat() if bounds['inicio'] else None,data_fim=bounds['fim'].isoformat() if bounds['fim'] else None))
            q=sql.SQL(SUMMARY_SQL.replace('{where}',where)).format(source=source)
            rows=conn.execute(q,params).fetchall()
        return payload_resumo(rows,datas,unidades)

def build_service(context):return FaturamentoNFService(context)
