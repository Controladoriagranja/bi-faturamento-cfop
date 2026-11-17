"""Consultas limitadas. Não depende de vw_frete_manual_nf nem abre conexões."""
from collections import defaultdict
from datetime import date, timedelta
from .freight import invoice_key
from .exclusions import exclusion_reason

FIELDS = ('empresa_contexto,unidade_documento,serie,nota_numero,data,produto,cliente,cfop,'
          'pedido,oc_principal,um,peso,frete,frete_kg,volumes,produto_descricao,redespacho,'
          'vendedor,rede,uf,familia,rota_cliente,preco_praticado,valor_total_faturado,valor_produto')

SALES_VIEW = 'comercial.vw_faturamento_vendedor_pai_itens'


def read_revision(conn):
    """A revisão MVCC muda com escritas, inclusive sem mudar carregado_em.

    Cache somente em transação de leitura com snapshot estável. Não cria objetos
    nem depende de triggers, agendamentos ou timestamps mantidos pelo extrator.
    """
    return conn.execute('''SELECT pg_current_snapshot()::text revisao,
      current_database() banco,current_user::text usuario,session_user::text sessao,
      inet_server_addr()::text servidor,inet_server_port() porta,
      current_setting('role') papel,current_setting('transaction_isolation') isolamento,
      current_setting('transaction_read_only') somente_leitura''').fetchone()


def read_candidates(conn,start,end,limit=30000):
    rows=conn.execute('SELECT '+FIELDS+' FROM '+SALES_VIEW+'''
      WHERE data >= %s AND data < %s AND btrim(unidade_documento)<>'102'
      AND btrim(frete)='1' AND coalesce(frete_kg,0)=0
      ORDER BY data,empresa_contexto,unidade_documento,serie,nota_numero,produto LIMIT %s''',
      [start,end+timedelta(days=1),limit+1]).fetchall()
    if len(rows)>limit:raise ValueError('Limite de pendências excedido; divida o período. Não houve truncamento.')
    return [row for row in rows if not exclusion_reason(row)]


def read_invoices(conn,keys,limit_per_batch=20000):
    """NF integral: nenhum filtro comercial, de família, de canal ou de CFOP."""
    invoices=defaultdict(list);keys=sorted(set(keys))
    if not keys:return {}
    # Uma leitura da origem para todas as chaves. O limite original de 20.000
    # itens por grupo de 2.000 NFs continua sendo conferido após a leitura.
    buckets={key:i//2000 for i,key in enumerate(keys)}
    maximum=((len(keys)+1999)//2000)*limit_per_batch
    columns=','.join('f.'+field for field in FIELDS.split(','))
    rows=conn.execute('SELECT '+columns+''' FROM comercial.faturamento_cfop f
          JOIN unnest(%s::text[],%s::text[],%s::text[],%s::text[],%s::integer[])
            AS k(empresa,unidade,serie,nf,ano)
          ON f.empresa_contexto=k.empresa AND btrim(f.unidade_documento)=k.unidade
            AND btrim(f.serie)=k.serie AND btrim(f.nota_numero)=k.nf
            AND extract(year FROM f.data)::integer=k.ano LIMIT %s''',
          [*[list(values) for values in zip(*keys)],maximum+1]).fetchall()
    if len(rows)>maximum:raise ValueError('NF/lote excede limite de itens integrais; revisar identificação.')
    counts=defaultdict(int)
    for row in rows:
        key=invoice_key(row);bucket=buckets[key];counts[bucket]+=1
        if counts[bucket]>limit_per_batch:raise ValueError('NF/lote excede limite de itens integrais; revisar identificação.')
        invoices[key].append(row)
    return dict(invoices)


def read_current(conn,start,end):
    # Fretes são anuais por chave de NF. Ler todos os meses do ano em cada
    # consulta torna o histórico progressivamente mais lento. Mantém somente
    # os fretes das NFs do período; despesas/folha conservam a vigência original.
    return conn.execute('''WITH notas_periodo AS (
      SELECT DISTINCT empresa_contexto,btrim(unidade_documento) unidade,
        btrim(serie) serie,btrim(nota_numero) nf,extract(year FROM data)::integer::text ano
      FROM '''+SALES_VIEW+''' WHERE data>=%s AND data<%s
    ) SELECT r.* FROM comercial.fob_cadastro r
      WHERE r.ativo AND r.inicio<=%s AND r.fim>=%s AND
       (r.tipo<>'frete' OR
        (r.dimensoes->>'empresa_contexto',r.dimensoes->>'unidade_documento',
         r.dimensoes->>'serie',r.dimensoes->>'nota_numero',r.dimensoes->>'ano_nf')
          IN (SELECT empresa_contexto,unidade,serie,nf,ano FROM notas_periodo))
      ORDER BY r.registro''',[start,end+timedelta(days=1),end,start]).fetchall()


def read_monthly(conn):
    return conn.execute('SELECT * FROM comercial.custo_mensal_januaria ORDER BY competencia').fetchall()


def read_sales(conn,start,end,limit=100000):
    columns=','.join('f.'+name for name in ('id,'+FIELDS+',desc_finan').split(','))
    rows=conn.execute('''WITH vendedores AS (
      SELECT coalesce(nullif(ltrim(btrim(vendedor),'0'),''),'0') vendedor,
      CASE WHEN count(DISTINCT canal_venda)=1 THEN max(canal_venda) ELSE 'Não classificado' END canal
      FROM comercial.vendedor_grupo GROUP BY 1
    ) SELECT '''+columns+''',coalesce(nullif(f.familia,''),'Sem família') familia_grupo,
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
