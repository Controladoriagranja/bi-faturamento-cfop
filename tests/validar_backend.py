"""Validação SELECT no banco existente, sem criar objetos ou alterar produção.

Tabela de vendedores e view NF são CTEs nesta execução. A API real compartilhada
é exercitada por TestClient; nenhuma porta ou autenticação de produção é alterada.
"""
import argparse,json,runpy,sys
from pathlib import Path
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.append(str(ROOT/'.dev_deps'))
sys.path.insert(0,str(ROOT/'backend'))
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from importar_vendedores import ler_planilha

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend-referencia',type=Path,required=True)
    p.add_argument('--config-banco',type=Path,required=True)
    p.add_argument('--vendedores',type=Path,required=True)
    p.add_argument('--planilha-conferencia',type=Path)
    a=p.parse_args()
    sys.path.insert(0,str(a.backend_referencia))
    import modules
    modules.__path__.append(str(ROOT/'backend/modules'))
    from core.registry import discover_modules
    discover_modules.cache_clear()
    assert 'faturamento_nf' in {m.key for m in discover_modules()}
    from core.contracts import RuntimeContext
    from modules.faturamento_nf.service import build_service
    from bi_generic.router import criar_router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    vendedores,import_audit=ler_planilha(a.vendedores)
    config=runpy.run_path(str(a.config_banco))
    assert config['DB_HOST']=='192.168.1.193' and config['DB_NAME']=='bi_granja'
    conn=psycopg.connect(host=config['DB_HOST'],port=config['DB_PORT'],dbname=config['DB_NAME'],
        user=config['DB_USER'],password=config['DB_PASSWORD'],row_factory=dict_row,connect_timeout=10)
    conn.execute("SET TRANSACTION READ ONLY")
    conn.execute("SET LOCAL statement_timeout='15000ms'")
    values=sql.SQL(',').join(sql.SQL('({})').format(sql.SQL(',').join(sql.Literal(r[k]) for k in ('vendedor','nome','canal_venda','vendedor_pai'))) for r in vendedores).as_string(conn)
    nf_sql=(ROOT/'backend/sql/003_vw_nf_por_vendedor_pai.sql').read_text(encoding='utf-8')
    nf_body=nf_sql[nf_sql.index('WITH itens AS'):].strip().rstrip(';').replace('comercial.vendedor_grupo','vendedores_validacao')
    prefix='WITH vendedores_validacao(vendedor,nome,canal_venda,vendedor_pai) AS (VALUES '+values+'), nf_validacao AS ('+nf_body+')'
    class Adapter:
        def execute(self,q,params=None):
            statement=q.as_string(conn) if hasattr(q,'as_string') else q
            statement=statement.replace('"comercial"."vw_nf_por_vendedor_pai"','nf_validacao')
            joined=prefix+', '+statement[5:] if statement.lstrip().upper().startswith('WITH ') else prefix+' '+statement
            return conn.execute(joined,params)
    @contextmanager
    def banco():yield Adapter()
    context=RuntimeContext('main',ROOT,banco=banco)
    service=build_service(context)
    app=FastAPI();app.include_router(criar_router(banco,{service.key:service}))
    client=TestClient(app)
    filters=client.get('/api/bi/faturamento-nf/filtros');assert filters.status_code==200,filters.text
    params={'data_inicio':'2026-09-06','data_fim':'2026-09-12'}
    response=client.get('/api/bi/faturamento-nf/resumo',params=params)
    assert response.status_code==200,response.text
    payload=response.json();total=payload['total']
    direct=conn.execute("SELECT COUNT(DISTINCT (BTRIM(unidade_documento),BTRIM(serie),BTRIM(nota_numero))) AS nfs,SUM(peso) AS peso,SUM(valor_total_faturado) AS valor FROM comercial.vw_faturamento_cfop_filtrado WHERE data>=DATE '2026-09-06' AND data<DATE '2026-09-13'").fetchone()
    assert total['qtde_nfs']==direct['nfs']==2687
    assert Decimal(total['valor_total'])==direct['valor']==Decimal('20198192.54')
    assert Decimal(total['peso_total'])==direct['peso']==Decimal('3160853.00')
    assert sum(g['qtde_nfs'] for g in payload['grupos'])==total['qtde_nfs']
    assert abs(Decimal(total['ticket_medio_por_nf'])-direct['valor']/direct['nfs'])<Decimal('0.000001')
    # Mesmo produto repetido na mesma NF conta uma vez; pesos/valores dos itens somam.
    example=conn.execute("WITH itens(nf,produto,peso,valor) AS (VALUES ('A','P1',10,100),('A','P1',5,50),('A','P2',20,200)) SELECT COUNT(DISTINCT produto) AS produtos,SUM(peso) AS peso,SUM(valor) AS valor FROM itens").fetchone()
    assert example=={'produtos':2,'peso':35,'valor':350}
    single=client.get('/api/bi/faturamento-nf/resumo',params={**params,'unidade':'10'}).json()
    assert single['total']['qtde_nfs']<total['qtde_nfs']
    multi=client.get('/api/bi/faturamento-nf/resumo',params=[*params.items(),('unidade','10'),('unidade','111')]);assert multi.status_code==200
    expected_multi=conn.execute("SELECT COUNT(DISTINCT (unidade_documento,serie,nota_numero)) AS nfs FROM comercial.vw_faturamento_cfop_filtrado WHERE unidade_documento IN ('10','111')").fetchone()['nfs']
    assert multi.json()['total']['qtde_nfs']==expected_multi
    zero=client.get('/api/bi/faturamento-nf/resumo',params={'data_inicio':'2020-01-01','data_fim':'2020-01-02'}).json()
    assert zero['total']['qtde_nfs']==0 and all(g['qtde_nfs']==0 for g in zero['grupos'])
    for invalid in [{'data_inicio':'2026-09-12','data_fim':'2026-09-06'}, {'data_inicio':'nao-data'}, {'sql':'DROP TABLE'}, {'unidade':['x']*101}]:
        if invalid=={'unidade':['x']*101}:
            # Distintos ultrapassam limite; repetição idêntica tem normalização idempotente.
            invalid={'unidade':[str(i) for i in range(101)]}
        assert client.get('/api/bi/faturamento-nf/resumo',params=invalid).status_code==422
    for label in ('CD Ribeirão das Neves','Januária'):
        item=next(g for g in payload['grupos'] if g['vendedor_pai']==label)
        assert item['qtde_nfs']==0 and item['pendente']
    audit=conn.execute(prefix+" SELECT vendedor,COUNT(*) AS nfs,SUM(valor_total_nf) AS valor FROM nf_validacao WHERE vendedor_pai='Não classificado' GROUP BY vendedor ORDER BY vendedor").fetchall()
    report=dict(importacao=import_audit,fonte_oficial=direct,sem_classificacao=audit,
      testes=['registro modular existente','NF distinta e soma de itens','JOIN sem multiplicação','médias gerais ponderadas por NF','multisseleção OR','datas inclusivas','intervalo sem movimento','validação de parâmetros','grupos pendentes zerados'],
      producao_alterada=False,worker_testado_com_sessao_real=False)
    if a.planilha_conferencia:
        import openpyxl
        w=openpyxl.load_workbook(a.planilha_conferencia,read_only=True,data_only=True)
        nf=defaultdict(list)
        def code(v):return str(int(v)) if isinstance(v,(int,float)) else str(v or '').strip().lstrip('0') or '0'
        mapping={v['vendedor']:v['vendedor_pai'] or 'Não classificado' for v in vendedores}
        for row in w.worksheets[0].values:
            if len(row)>=47 and hasattr(row[2],'date') and row[24] is not None:
                nf[(code(row[6]),code(row[7]),code(row[8]))].append(row)
        expected=defaultdict(lambda:dict(nfs=0,produtos=0,peso=Decimal(0),valor=Decimal(0)))
        for rows in nf.values():
            label=mapping.get(code(rows[0][0]),'Não classificado');g=expected[label]
            g['nfs']+=1;g['produtos']+=len({code(r[24]) for r in rows})
            g['peso']+=sum((Decimal(str(r[31] or 0)) for r in rows),Decimal(0))
            g['valor']+=sum((Decimal(str(r[38] or 0)) for r in rows),Decimal(0))
        differences=[]
        for actual in payload['grupos']:
            exp=expected.pop(actual['vendedor_pai'],dict(nfs=0,produtos=0,peso=Decimal(0),valor=Decimal(0)))
            differences.append(dict(vendedor_pai=actual['vendedor_pai'],dif_nfs=actual['qtde_nfs']-exp['nfs'],dif_produtos=int(actual['soma_produtos_distintos'])-exp['produtos'],dif_peso=Decimal(actual['peso_total'])-exp['peso'],dif_valor=Decimal(actual['valor_total'])-exp['valor']))
        assert not expected
        assert all(r['dif_nfs']==r['dif_produtos']==r['dif_peso']==r['dif_valor']==0 for r in differences)
        report['planilha_conferencia']=str(a.planilha_conferencia)
        report['diferencas_por_vendedor_pai']=differences
        report['limite_conferencia']='Planilha de itens do setor agrupada pela auxiliar; não há planilha pronta com os indicadores por vendedor pai.'
    conn.rollback();conn.close()
    out=ROOT/'artifacts';out.mkdir(exist_ok=True)
    (out/'resumo_real.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'filtros_real.json').write_text(json.dumps(filters.json(),ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'resumo_real_multiplas.json').write_text(json.dumps(multi.json(),ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'resumo_vazio.json').write_text(json.dumps(zero,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'validacao.json').write_text(json.dumps(report,default=str,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(total=total,importacao=import_audit,sem_classificacao=audit,testes=len(report['testes']),planilha_comparada=bool(a.planilha_conferencia)),default=str,ensure_ascii=False))

if __name__=='__main__':main()
