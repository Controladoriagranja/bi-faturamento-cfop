"""Detalhes somente leitura; a view de NFs determina a classificação e os filtros."""
import json
from fastapi import HTTPException
from psycopg import sql
from .config import CONFIG
from .service import filtros_request, publico

ITEM_COLUMNS = tuple('id empresa_contexto unidade_contexto processo periodo_inicio periodo_fim carregado_em vendedor vendedor_nome data mes meio_venda devolucao unidade_documento serie nota_numero pedido oc_principal redespacho romaneio frete cliente rede razao_social tipo_de_cliente nome_fantasia rota_cliente rota_pedido cidade uf ramo_ativ produto produto_descricao um familia cfop cfop_descricao volumes peso lista ocorr pre_base preco_praticado valor_produto desconto_comercial valor_total_faturado desc_finan frete_kg nota_refaturada romaneio_refaturada nota_devolucao cliente_original cond_pag_cliente cond_pag_nota ano_semana numero_semana frete_sem_valor cond_pag_nota_original cond_pag_nota_status id_venda_correspondente'.split())
NOTE_COLUMNS = tuple('chave_nf data unidade_documento serie nota_numero vendedor vendedor_pai qtde_itens qtde_produtos_distintos peso_total_nf valor_total_nf carregado_em'.split())
EXTRAS = {'vendedor_pai', 'visao', 'pagina', 'por_pagina', 'busca', 'chave_nf', 'indicador'}
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
    page = inteiro(request, 'pagina', 1, 10000000)
    size = inteiro(request, 'por_pagina', 50, 500)
    if view not in ('notas', 'itens') or metric not in SORTS:
        raise HTTPException(422, 'Visão ou indicador inválido.')
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
    prefix = '''WITH base AS (SELECT * FROM {source} ''' + where + '''),
        selecionadas AS (SELECT n.* FROM base n ''' + ('WHERE ' + ' AND '.join(clauses) if clauses else '') + ') '
    source = sql.Identifier(CONFIG['bi']['schema'], CONFIG['bi']['table'])
    items = sql.Identifier('comercial', 'vw_faturamento_cfop_filtrado')

    def query(body):
        return sql.SQL(prefix + body).format(source=source, items=items)

    with context.banco() as conn:
        stats = conn.execute(query('''SELECT COUNT(*) AS qtde_nfs,
            COALESCE(SUM(qtde_itens),0) AS qtde_itens,
            COALESCE(SUM(peso_total_nf),0) AS peso_total,
            COALESCE(SUM(valor_total_nf),0) AS valor_total,
            COUNT(*) FILTER (WHERE divergencia_nf) AS nfs_divergentes FROM selecionadas'''), params).fetchone()
        if stats['nfs_divergentes']:
            raise HTTPException(409, 'Há NFs com chave, data ou vendedor divergente. Confira a auditoria antes de abrir os detalhes.')
        if view == 'notas':
            body = 'SELECT ' + ','.join(NOTE_COLUMNS) + ' FROM selecionadas ORDER BY ' + SORTS[metric] + ', unidade_documento,serie,nota_numero LIMIT %s OFFSET %s'
            total = int(stats['qtde_nfs'])
        else:
            body = 'SELECT i.* FROM selecionadas n JOIN {items} i ON ' + join + ' ORDER BY n.data DESC,n.unidade_documento,n.serie,n.nota_numero,i.id LIMIT %s OFFSET %s'
            total = int(stats['qtde_itens'])
        rows = conn.execute(query(body), [*params, size, (page - 1) * size]).fetchall()
    return dict(linhas=[publico(r) for r in rows], colunas=list(NOTE_COLUMNS if view == 'notas' else ITEM_COLUMNS),
                total_registros=total, pagina=page, por_pagina=size, visao=view,
                totais=publico(stats), vendedor_pai=group or None,
                periodo=dict(data_inicio=datas[0], data_fim=datas[1]), unidades=unidades)
