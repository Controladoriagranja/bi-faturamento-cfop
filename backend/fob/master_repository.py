"""Consultas limitadas. Não depende de vw_frete_manual_nf nem abre conexões."""
from collections import defaultdict
from datetime import date, timedelta
from .freight import invoice_key

FIELDS = ('empresa_contexto,unidade_documento,serie,nota_numero,data,produto,cliente,cfop,'
          'pedido,oc_principal,um,peso,frete,frete_kg,volumes,produto_descricao,redespacho,'
          'vendedor,rede,uf,familia,rota_cliente,preco_praticado,valor_total_faturado,valor_produto')


def read_candidates(conn,start,end,limit=30000):
    rows=conn.execute('SELECT '+FIELDS+''' FROM comercial.vw_faturamento_cfop_filtrado
      WHERE data >= %s AND data < %s AND btrim(unidade_documento)<>'102'
      AND btrim(frete)='1' AND coalesce(frete_kg,0)=0
      ORDER BY data,empresa_contexto,unidade_documento,serie,nota_numero,produto LIMIT %s''',
      [start,end+timedelta(days=1),limit+1]).fetchall()
    if len(rows)>limit:raise ValueError('Limite de pendências excedido; divida o período. Não houve truncamento.')
    return rows


def read_invoices(conn,keys,limit_per_batch=20000):
    """NF integral: nenhum filtro comercial, de família, de canal ou de CFOP."""
    invoices=defaultdict(list);keys=sorted(set(keys))
    for offset in range(0,len(keys),150):
        batch=keys[offset:offset+150]
        values=','.join(['(%s,%s,%s,%s,%s)']*len(batch))
        rows=conn.execute('SELECT '+FIELDS+''' FROM comercial.faturamento_cfop
          WHERE (empresa_contexto,btrim(unidade_documento),btrim(serie),btrim(nota_numero),
                 extract(year FROM data)::integer) IN ('''+values+') LIMIT %s',
          [*(v for key in batch for v in key),limit_per_batch+1]).fetchall()
        if len(rows)>limit_per_batch:raise ValueError('NF/lote excede limite de itens integrais; revisar identificação.')
        for row in rows:invoices[invoice_key(row)].append(row)
    return dict(invoices)


def read_current(conn,start,end):
    return conn.execute('''SELECT * FROM comercial.fob_cadastro
      WHERE ativo AND inicio<=%s AND fim>=%s ORDER BY registro''',[end,start]).fetchall()


def read_monthly(conn):
    return conn.execute('SELECT * FROM comercial.custo_mensal_januaria ORDER BY competencia').fetchall()


def read_sales(conn,start,end,limit=100000):
    rows=conn.execute('''WITH vendedores AS (
      SELECT coalesce(nullif(ltrim(btrim(vendedor),'0'),''),'0') vendedor,
      CASE WHEN count(DISTINCT canal_venda)=1 THEN max(canal_venda) ELSE 'Não classificado' END canal
      FROM comercial.vendedor_grupo GROUP BY 1
    ) SELECT f.*,coalesce(nullif(f.familia,''),'Sem família') familia_grupo,
      CASE WHEN upper(btrim(f.familia))='SUBPRODUTOS' THEN 'Subprodutos'
        ELSE coalesce(v.canal,'Não classificado') END canal_grupo
    FROM comercial.vw_faturamento_cfop_filtrado f LEFT JOIN vendedores v
      ON coalesce(nullif(ltrim(btrim(f.vendedor),'0'),''),'0')=v.vendedor
    WHERE f.data>=%s AND f.data<%s ORDER BY f.data,f.id LIMIT %s''',
    [start,end+timedelta(days=1),limit+1]).fetchall()
    if len(rows)>limit:raise ValueError('Período excede 100.000 itens; divida a consulta. Nada foi truncado.')
    return rows


def read_status(conn):
    imports=conn.execute('''SELECT lote,executado_em,status,arquivos,resumo,erros
       FROM comercial.fob_importacao ORDER BY executado_em DESC,lote DESC LIMIT 10''').fetchall()
    latest=conn.execute('''SELECT lote,executado_em,arquivos,resumo FROM comercial.fob_importacao
       WHERE status='VALIDADO' ORDER BY executado_em DESC,lote DESC LIMIT 1''').fetchone()
    return dict(ultima_importacao_valida=latest,execucoes=imports)
