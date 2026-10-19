"""Regressão local com SQL executado em DuckDB e dados sintéticos.

Não acessa produção. Não substitui homologação no PostgreSQL/Worker.
--serve disponibiliza o mesmo serviço e frontend para o teste do navegador.
"""
import argparse
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
import sys
import os
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.dev_deps'), str(ROOT / 'backend')]
sys.path.append(os.environ.get('BACKEND_REFERENCE', str(ROOT.parent / 'api-db' / 'api_zootecnico')))
sys.dont_write_bytecode = True
import duckdb
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
import modules
modules.__path__.insert(0, str(ROOT / 'backend' / 'modules'))
from modules.faturamento_nf.details import ITEM_COLUMNS
from modules.faturamento_nf.service import build_service


def fixture():
    conn = duckdb.connect(':memory:')
    conn.execute('CREATE SCHEMA comercial')
    conn.execute('CREATE MACRO BTRIM(x) AS TRIM(x)')
    numbers = {'id','peso','valor_total_faturado'}
    columns = ','.join(c + (' DECIMAL(18,2)' if c in numbers else ' DATE' if c == 'data' else ' VARCHAR') for c in ITEM_COLUMNS)
    conn.execute('CREATE TABLE comercial.vw_faturamento_cfop_filtrado (' + columns + ')')
    rows = []
    for note in range(1, 57):
        unit = '180' if note == 55 else '102' if note == 56 else '10' if note <= 52 else '111'
        for item in range(12):
            row = dict(id=len(rows)+1, unidade_documento=' '+unit+' ', serie=' 001 ', nota_numero=' '+str(note)+' ',
                       vendedor='001', vendedor_nome='Vendedor teste', data='2026-10-01' if note <= 28 else '2026-10-04',
                       produto=str(item // 2), produto_descricao='Produto '+str(item // 2),
                       razao_social='Cliente especial' if note == 1 else 'Cliente teste',
                       cfop='5101-01', peso=Decimal('1.25'), valor_total_faturado=Decimal('12.50'))
            rows.append([row.get(c) for c in ITEM_COLUMNS])
    conn.executemany('INSERT INTO comercial.vw_faturamento_cfop_filtrado VALUES ('+','.join('?' for _ in ITEM_COLUMNS)+')', rows)
    # View canônica de teste: a seleção dos itens deve seguir sua classificação por NF.
    conn.execute('''CREATE VIEW comercial.vw_nf_por_vendedor_pai AS
        SELECT to_json([trim(unidade_documento),trim(serie),trim(nota_numero)])::VARCHAR AS chave_nf,
            min(data) AS data, trim(unidade_documento) AS unidade_documento,
            trim(serie) AS serie, trim(nota_numero) AS nota_numero, min(vendedor) AS vendedor,
            CASE WHEN trim(unidade_documento)='180' THEN 'CD Ribeirão das Neves'
                 WHEN trim(unidade_documento)='102' THEN 'Januária'
                 WHEN trim(unidade_documento)='111' THEN 'Não classificado'
                 ELSE 'Varejo Centro-Oeste' END AS vendedor_pai,
            count(DISTINCT produto) AS qtde_produtos_distintos, sum(peso) AS peso_total_nf,
            sum(valor_total_faturado) AS valor_total_nf,count(*) AS qtde_itens,
            NULL::VARCHAR AS carregado_em,FALSE AS divergencia_nf
        FROM comercial.vw_faturamento_cfop_filtrado GROUP BY ALL''')
    lock = threading.Lock()
    queries = []

    class Result:
        def __init__(self, cursor):
            names = [c[0] for c in cursor.description]
            self.rows = [dict(zip(names, row)) for row in cursor.fetchall()]
        def fetchall(self): return self.rows
        def fetchone(self): return self.rows[0] if self.rows else None

    class Adapter:
        def execute(self, query, params=None):
            text = query.as_string() if hasattr(query, 'as_string') else query
            queries.append(text)
            # Equivalente DuckDB do agregado JSON PostgreSQL usado pela API.
            text = text.replace('json_agg(p ORDER BY p._ord)', 'to_json(list(p ORDER BY p._ord))')
            return Result(conn.execute(text.replace('%s','?'), params or []))

    @contextmanager
    def banco():
        with lock: yield Adapter()

    class Context: pass
    context = Context()
    context.banco = banco
    service = build_service(context)
    app = FastAPI()
    app.state.sql_queries = queries

    @app.get('/api/bi/faturamento-nf/{operation}')
    def endpoint(operation: str, request: Request):
        return service.execute(operation, request)

    app.mount('/', StaticFiles(directory=ROOT, html=True), name='frontend')
    return app, conn


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', type=int)
    args=parser.parse_args()
    app, conn = fixture()
    if args.serve:
        import uvicorn
        uvicorn.run(app, host='127.0.0.1', port=args.serve, log_level='warning')
        return
    client=TestClient(app)
    base='/api/bi/faturamento-nf/'
    filters={'data_inicio':'2026-10-01','data_fim':'2026-10-04'}

    def get(**params):
        response=client.get(base+'detalhes', params={**filters, **params})
        assert response.status_code==200, response.text
        return response.json()

    notes=get()
    assert notes['total_registros']==56 and len(notes['linhas'])==50
    assert len(get(pagina=2)['linhas'])==6
    assert notes['totais']['qtde_itens']==672
    assert Decimal(notes['totais']['peso_total'])==Decimal('840')
    assert Decimal(notes['totais']['valor_total'])==Decimal('8400')
    assert all(n['qtde_produtos_distintos']==6 for n in notes['linhas'])
    items=get(visao='itens', por_pagina=500)
    assert items['total_registros']==672 and len(items['linhas'])==500
    assert len(get(visao='itens',por_pagina=500,pagina=2)['linhas'])==172
    assert items['colunas']==list(ITEM_COLUMNS)
    summary=client.get(base+'resumo',params=filters).json()
    assert summary['total']['qtde_nfs']==56
    assert Decimal(summary['total']['valor_total'])==Decimal(notes['totais']['valor_total'])
    for group in summary['grupos']:
        detail=get(vendedor_pai=group['vendedor_pai'])
        assert detail['totais']['qtde_nfs']==group['qtde_nfs']
        assert Decimal(detail['totais']['valor_total'])==Decimal(group['valor_total'])
    assert get(vendedor_pai='CD Ribeirão das Neves')['total_registros']==1
    assert get(vendedor_pai='Januária')['total_registros']==1
    assert get(vendedor_pai='Não classificado')['total_registros']==2
    assert get(busca='especial',visao='itens')['total_registros']==12
    assert get(busca='Produto 0',visao='itens')['total_registros']==672  # notas completas
    key=get(busca='especial')['linhas'][0]['chave_nf']
    assert get(chave_nf=key,visao='itens')['total_registros']==12
    assert get(chave_nf=key,vendedor_pai='Januária',visao='itens')['total_registros']==0
    assert get(data_fim='2026-10-01')['total_registros']==28
    assert get(unidade=['180','102'])['total_registros']==2
    assert get(data_inicio='2020-01-01',data_fim='2020-01-02')['total_registros']==0
    assert get(vendedor_pai="x' OR 1=1 --")['total_registros']==0
    assert get(busca="%' OR 1=1 --")['total_registros']==0
    assert get(busca='%')['total_registros']==0
    before=len(app.state.sql_queries)
    broad=get(visao='itens',data_inicio='2026-01-01',data_fim='2026-10-19',por_pagina=25)
    assert len(app.state.sql_queries)==before+1
    assert 'notas_pagina AS MATERIALIZED' in app.state.sql_queries[-1]
    expected=[r[0] for r in conn.execute('''SELECT id FROM comercial.vw_faturamento_cfop_filtrado
        ORDER BY data DESC NULLS LAST,trim(unidade_documento),trim(serie),trim(nota_numero),id''').fetchall()]
    all_ids=[]
    for page in range(1,28):
        result=get(visao='itens',por_pagina=25,pagina=page)
        all_ids.extend(Decimal(row['id']) for row in result['linhas'])
    assert all_ids==expected  # inclui páginas começando/terminando dentro de uma NF
    for view, columns in [('itens',ITEM_COLUMNS),('notas',notes['colunas'])]:
        for column in columns:
            get(visao=view,ordenar_por=column,ordem='asc',por_pagina=1)
    assert [Decimal(r['id']) for r in get(visao='itens',ordenar_por='id',ordem='asc',por_pagina=25,pagina=2)['linhas']]==list(range(26,51))
    assert Decimal(get(visao='itens',ordenar_por='id',ordem='desc')['linhas'][0]['id'])==672
    assert Decimal(get(visao='itens',ordenar_por='id',ordem='asc')['linhas'][0]['id'])==1
    conn.execute('UPDATE comercial.vw_faturamento_cfop_filtrado SET peso=10.25,valor_total_faturado=123456789.12 WHERE id=1')
    conn.execute('UPDATE comercial.vw_faturamento_cfop_filtrado SET data=NULL WHERE id=2')
    highest=get(visao='itens',ordenar_por='peso',ordem='desc')['linhas'][0]
    assert Decimal(highest['id'])==1 and highest['valor_total_faturado']=='123456789.12'
    assert get(visao='itens')['total_registros']==672
    assert len(get(visao='itens',busca='especial')['linhas'])==12  # data NULL não perde item
    for invalid in ({'visao':'sql'},{'indicador':'sql'},{'pagina':'0'},{'pagina':'abc'},
                    {'por_pagina':501},{'chave_nf':'[1,2,3]'},{'chave_nf':'{}'},
                    {'busca':'a'*201},{'sql':'select'},{'data_inicio':'2026-11-01'},
                    {'ordenar_por':'id; DROP TABLE x'}, {'ordem':'desc; SELECT 1'},
                    {'visao':'notas','ordenar_por':'produto'}):
        assert client.get(base+'detalhes',params={**filters,**invalid}).status_code==422
    assert client.get(base+'detalhes',params=[('visao','notas'),('visao','itens')]).status_code==422
    conn.execute('ALTER VIEW comercial.vw_nf_por_vendedor_pai RENAME TO nf_sem_bloqueio')
    conn.execute('CREATE VIEW comercial.vw_nf_por_vendedor_pai AS SELECT * EXCLUDE(divergencia_nf), TRUE AS divergencia_nf FROM comercial.nf_sem_bloqueio')
    assert client.get(base+'detalhes',params=filters).status_code==409
    assert client.get(base+'resumo',params=filters).status_code==409
    print('OK: detalhes SQL, conciliação com resumo, paginação, 60 colunas, busca por NF completa, unidades especiais, datas inclusivas e validação de parâmetros (dados sintéticos; DuckDB).')


if __name__=='__main__': main()
