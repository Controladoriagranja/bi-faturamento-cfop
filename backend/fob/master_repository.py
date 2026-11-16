"""Consultas limitadas. Não depende de vw_frete_manual_nf nem abre conexões."""
from collections import defaultdict
from datetime import date, timedelta
from .freight import invoice_key

FIELDS = ('empresa_contexto,unidade_documento,serie,nota_numero,data,produto,cliente,cfop,'
          'pedido,oc_principal,um,peso,frete,frete_kg,volumes,produto_descricao,redespacho,'
          'vendedor,rede,uf,familia,rota_cliente,preco_praticado,valor_total_faturado,valor_produto')

SALES_VIEW = 'comercial.vw_faturamento_vendedor_pai_itens'


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
    for offset in range(0,len(keys),2000):
        batch=keys[offset:offset+2000]
        columns=','.join('f.'+field for field in FIELDS.split(','))
        # Arrays mantêm o número de parâmetros fixo e evitam dezenas de viagens
        # para uma competência com milhares de fretes. A NF continua integral.
        rows=conn.execute('SELECT '+columns+''' FROM comercial.faturamento_cfop f
          JOIN unnest(%s::text[],%s::text[],%s::text[],%s::text[],%s::integer[])
            AS k(empresa,unidade,serie,nf,ano)
          ON f.empresa_contexto=k.empresa AND btrim(f.unidade_documento)=k.unidade
            AND btrim(f.serie)=k.serie AND btrim(f.nota_numero)=k.nf
            AND extract(year FROM f.data)::integer=k.ano LIMIT %s''',
          [*[list(values) for values in zip(*batch)],limit_per_batch+1]).fetchall()
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
        WHEN ltrim(btrim(f.unidade_documento),'0')='102' THEN 'Varejo'
        ELSE coalesce(v.canal,'Não classificado') END canal_grupo
    FROM '''+SALES_VIEW+''' f LEFT JOIN vendedores v
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
