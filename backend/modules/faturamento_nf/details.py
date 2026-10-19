"""Detalhes somente leitura; a view de NFs determina a classificação e os filtros."""
import json
import logging
import psycopg
from datetime import timedelta
from decimal import Decimal
from fastapi import HTTPException
from psycopg import sql
from .config import CONFIG
from .service import filtros_request, publico

ITEM_COLUMNS = tuple('id empresa_contexto unidade_contexto processo periodo_inicio periodo_fim carregado_em vendedor vendedor_nome data mes meio_venda devolucao unidade_documento serie nota_numero pedido oc_principal redespacho romaneio frete cliente rede razao_social tipo_de_cliente nome_fantasia rota_cliente rota_pedido cidade uf ramo_ativ produto produto_descricao um familia cfop cfop_descricao volumes peso lista ocorr pre_base preco_praticado valor_produto desconto_comercial valor_total_faturado desc_finan frete_kg nota_refaturada romaneio_refaturada nota_devolucao cliente_original cond_pag_cliente cond_pag_nota ano_semana numero_semana frete_sem_valor cond_pag_nota_original cond_pag_nota_status id_venda_correspondente'.split())
NOTE_COLUMNS = tuple('chave_nf data unidade_documento serie nota_numero vendedor vendedor_pai qtde_itens qtde_produtos_distintos peso_total_nf valor_total_nf carregado_em'.split())
EXTRAS = {'vendedor_pai', 'visao', 'pagina', 'por_pagina', 'busca', 'chave_nf', 'indicador', 'ordenar_por', 'ordem'}
DECIMAL_COLUMNS = set('volumes peso pre_base preco_praticado valor_produto desconto_comercial valor_total_faturado desc_finan frete_kg peso_total_nf valor_total_nf'.split())
logger = logging.getLogger(__name__)
SORTS = {'vendedor_pai': 'data DESC', 'qtde_nfs': 'data DESC',
         'qtde_produto_por_nf': 'qtde_produtos_distintos DESC',
         'peso_por_nf': 'peso_total_nf DESC', 'ticket_medio_por_nf': 'valor_total_nf DESC'}


def unico(request, name, default=''):
    values = request.query_params.getlist(name)
    if len(values) > 1:
        raise HTTPException(422, f'Parâmetro duplicado: {name}.')
    return values[0] if values else default


def inteiro(request, name, default, maximum):
    raw = unico(request, name, str(default))
    if not raw.isascii() or not raw.isdigit() or len(raw) > 9:
        raise HTTPException(422, f'Parâmetro inválido: {name}.')
    value = int(raw)
    if not 1 <= value <= maximum:
        raise HTTPException(422, f'Parâmetro fora do limite: {name}.')
    return value


def detalhes(context, request):
    where, params, datas, unidades = filtros_request(request, EXTRAS)
    group = unico(request, 'vendedor_pai')
    search = unico(request, 'busca').strip()
    view = unico(request, 'visao', 'notas')
    metric = unico(request, 'indicador', 'qtde_nfs')
    sort_column = unico(request, 'ordenar_por')
    direction = unico(request, 'ordem', 'asc')
    page = inteiro(request, 'pagina', 1, 10000000)
    size = inteiro(request, 'por_pagina', 50, 500)
    if view not in ('notas', 'itens') or metric not in SORTS:
        raise HTTPException(422, 'Visão ou indicador inválido.')
    columns = NOTE_COLUMNS if view == 'notas' else ITEM_COLUMNS
    if (sort_column and sort_column not in columns) or direction not in ('asc', 'desc'):
        raise HTTPException(422, 'Coluna ou direção de ordenação inválida.')
    if len(group) > 200 or len(search) > 200:
        raise HTTPException(422, 'Busca ou grupo excede o limite de 200 caracteres.')
    clauses = []
    if group:
        clauses.append('n.vendedor_pai = %s')
        params.append(group)
    key = unico(request, 'chave_nf')
    if key:
        try:
            parts = json.loads(key)
            if not isinstance(parts, list) or len(parts) != 3 or any(not isinstance(v, str) or not v or len(v) > 100 for v in parts):
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(422, 'Chave de NF inválida.')
        clauses.append('(n.unidade_documento,n.serie,n.nota_numero) = (%s,%s,%s)')
        params.extend(parts)
    join = '''NULLIF(BTRIM(i.unidade_documento),'') = n.unidade_documento
              AND NULLIF(BTRIM(i.serie),'') = n.serie
              AND NULLIF(BTRIM(i.nota_numero),'') = n.nota_numero'''
    if search:
        clauses.append('''EXISTS (SELECT 1 FROM {items} i WHERE ''' + join + '''
            AND STRPOS(LOWER(CONCAT_WS(' ',i.nota_numero,i.serie,i.cliente,i.razao_social,
                i.nome_fantasia,i.vendedor,i.vendedor_nome,i.produto,i.produto_descricao,i.cfop)),LOWER(%s)) > 0)''')
        params.append(search)
    # A busca seleciona NFs completas: não remove itens e não altera as médias das notas.
    selected_where = where + ((' AND ' if where else ' WHERE ') + ' AND '.join(clauses) if clauses else '')
    prefix = 'WITH selecionadas AS MATERIALIZED (SELECT n.* FROM {source} n ' + selected_where + '), '
    source = sql.Identifier(CONFIG['bi']['schema'], CONFIG['bi']['table'])
    items = sql.Identifier('comercial', 'vw_faturamento_cfop_filtrado')

    stats_sql = '''estatisticas AS (
        SELECT COUNT(*) AS qtde_nfs,
            COALESCE(SUM(qtde_itens),0) AS qtde_itens,
            COALESCE(SUM(peso_total_nf),0) AS peso_total,
            COALESCE(SUM(valor_total_nf),0) AS valor_total,
            COUNT(*) FILTER (WHERE divergencia_nf) AS nfs_divergentes FROM selecionadas), '''
    offset = (page - 1) * size
    alias = 'n' if view == 'notas' else 'i'

    def field(column):
        return sql.Identifier(alias, column).as_string()

    # NUMERIC vira texto dentro do JSON para preservar os decimais na API.
    projection = ','.join(field(c) + ('::text' if c in DECIMAL_COLUMNS else '') + ' AS ' + sql.Identifier(c).as_string() for c in columns)
    tie = 'n.data DESC NULLS LAST,n.unidade_documento,n.serie,n.nota_numero'
    if view == 'itens': tie += ',i.id'
    if sort_column:
        order = field(sort_column) + ' ' + direction.upper() + ' NULLS LAST,' + tie
    elif view == 'notas':
        order = 'n.' + SORTS[metric] + ' NULLS LAST,n.unidade_documento,n.serie,n.nota_numero'
    else:
        order = tie
    extra_cte = ''
    valid = '(SELECT nfs_divergentes FROM estatisticas)=0'
    page_offset = str(offset)
    if view == 'notas':
        from_sql = 'selecionadas n'
        item_where = valid
    else:
        # Na ordem padrão, as contagens da view localizam as NFs da página
        # ANTES de acessar a view larga de itens. Uma NF pode atravessar páginas.
        if not sort_column:
            note_order = 'n.data DESC NULLS LAST,n.unidade_documento,n.serie,n.nota_numero'
            extra_cte = '''ordenadas AS (
                SELECT n.*,COALESCE(SUM(qtde_itens) OVER (ORDER BY ''' + note_order + '''
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) AS inicio_item
                FROM selecionadas n),
                notas_pagina AS MATERIALIZED (SELECT * FROM ordenadas
                    WHERE inicio_item < ''' + str(offset + size) + '''
                      AND inicio_item + qtde_itens > ''' + str(offset) + ''' AND ''' + valid + '), '
            from_sql = 'notas_pagina n JOIN {items} i ON ' + join
            page_offset = str(offset) + ' - COALESCE((SELECT MIN(inicio_item)::bigint FROM notas_pagina),' + str(offset) + ')'
        else:
            # Ordenação por qualquer coluna do item considera todo o filtro.
            from_sql = 'selecionadas n JOIN {items} i ON ' + join
        raw_clauses = [valid]
        # Ajuda o PostgreSQL a restringir a fonte. NULL é mantido porque pode
        # pertencer a uma NF cuja data consolidada é válida.
        if datas[0]:
            raw_clauses.append('(i.data >= %s OR i.data IS NULL)')
            params.append(datas[0])
        if datas[1]:
            raw_clauses.append('(i.data < %s OR i.data IS NULL)')
            params.append(datas[1] + timedelta(days=1))
        item_where = ' AND '.join(raw_clauses)
    body = prefix + stats_sql + extra_cte + '''pagina AS (
        SELECT ''' + projection + ', ROW_NUMBER() OVER (ORDER BY ' + order + ''') AS _ord
        FROM ''' + from_sql + ' WHERE ' + item_where + ' ORDER BY ' + order + '''
        LIMIT ''' + str(size) + ' OFFSET (' + page_offset + ''') )
        SELECT e.*, COALESCE((SELECT json_agg(p ORDER BY p._ord) FROM pagina p),'[]'::json) AS linhas
        FROM estatisticas e'''
    query = sql.SQL(body).format(source=source, items=items)
    try:
        with context.banco() as conn:
            stats = conn.execute(query, params).fetchone()
    except psycopg.Error as error:
        logger.exception('Erro no detalhamento CFOP: SQLSTATE=%s, visao=%s', error.sqlstate, view)
        if error.sqlstate == '57014':
            raise HTTPException(504, 'A consulta de detalhes excedeu o tempo limite do banco. Reduza o período ou refine os filtros.') from error
        raise
    if stats['nfs_divergentes']:
        raise HTTPException(409, 'Há NFs com chave, data ou vendedor divergente. Confira a auditoria antes de abrir os detalhes.')
    rows = stats.pop('linhas') or []
    if isinstance(rows, str): rows = json.loads(rows, parse_float=Decimal)
    for row in rows: row.pop('_ord', None)
    total = int(stats['qtde_nfs'] if view == 'notas' else stats['qtde_itens'])
    return dict(linhas=[publico(r) for r in rows], colunas=list(columns),
                total_registros=total, pagina=page, por_pagina=size, visao=view,
                ordenar_por=sort_column or None, ordem=direction if sort_column else None,
                totais=publico(stats), vendedor_pai=group or None,
                periodo=dict(data_inicio=datas[0], data_fim=datas[1]), unidades=unidades)
