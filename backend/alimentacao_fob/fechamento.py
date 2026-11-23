"""Importação auditável dos insumos mensais, sem copiar resultados finais do Excel."""
from datetime import date,datetime,timezone
from decimal import Decimal,localcontext
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from fob.calculator import code
from fob.workbook import extract
from .analise_comercial import preview,stable_read,month_sheet


def read_saved(path):
    """Snapshot dos bytes salvos, sem lock nem remoção do temporário do Excel."""
    before=path.stat();content=path.read_bytes();after=path.stat()
    stamp=(after.st_size,after.st_mtime_ns)
    if (before.st_size,before.st_mtime_ns)!=stamp or sha256(content).digest()!=sha256(path.read_bytes()).digest():
        raise ValueError('Arquivo mudou durante a leitura; aguarde terminar o salvamento.')
    return content,stamp


def build(competence,commercial,cpv):
    month_sheet(competence)
    commercial=Path(commercial);cpv=Path(cpv)
    source,stamp=stable_read(commercial);cost=preview(source,competence)
    cpv_bytes,cpv_stamp=read_saved(cpv)
    sheets=extract(cpv,['CPV-Frango','AnaliseMixPMInclusiveCDs'],140)
    sheet=sheets['CPV-Frango'];mix=sheets['AnaliseMixPMInclusiveCDs']
    month=sheet['rows']['1']['C']['v']
    year,num=competence.split('-')
    if month.strip()!=f'CPV - {num}/{year[-2:]}':raise ValueError('Competência do CPV não corresponde a '+competence+'.')
    for col,expected in [('B','Código'),('G','Produção'),('AG','Custo'),('BR','Custo')]:
        from .analise_comercial import text
        if text(expected) not in text(sheet['rows']['2'].get(col,{}).get('v','')):raise ValueError('Layout CPV não reconhecido: '+col)
    def number(row,col):
        value=row.get(col,{}).get('v')
        # Células de entrada vazias em somas do Excel equivalem a zero.
        return Decimal(str(value)) if value not in (None,'') else Decimal(0)
    products={}
    with localcontext() as ctx:
        ctx.prec=38
        for rn,row in sheet['rows'].items():
            if int(rn)<3 or not row.get('B',{}).get('v'):continue
            product=code(row['B']['v'])
            if not product.isdecimal():continue
            production=number(row,'G')
            total=sum((number(row,c) for c in ('AG','K','V','W','X')),Decimal(0))
            value=total/production if production>0 else number(row,'BR')
            if not value.is_finite() or value<0:raise ValueError('CPV inválido: produto '+product)
            data=dict(cpv_kg=str(value),descricao=row.get('C',{}).get('v'),origem=f'CPV-Frango!B{rn}:BR{rn}',
                formula='(AG+K+V+W+X)/G se G>0; caso contrário BR',
                parcelas={c:str(number(row,c)) for c in ('G','AG','K','V','W','X','BR','N')})
            if product in products:
                # O Excel usa VLOOKUP exato: vale a primeira ocorrência. Registrar
                # as demais permite auditar sem alterar silenciosamente a seleção.
                products[product].setdefault('ocorrencias_posteriores',[]).append(data)
                continue
            products[product]=data
    scope=[code(mix['rows'][str(r)]['B']['v']) for r in [*range(4,110),*range(113,117)]]
    residues=[code(mix['rows'][str(r)]['B']['v']) for r in range(120,124)]
    # As células E/G desses resíduos estão vazias no Excel (zero na operação).
    for r in range(120,124):
        if any(number(mix['rows'][str(r)],col)!=0 for col in ('E','G')):raise ValueError('Custos de resíduos mudaram; conferir regra antes de importar.')
    if stable_read(commercial)[1]!=stamp or read_saved(cpv)[1]!=cpv_stamp:
        raise ValueError('Arquivo mudou durante a preparação.')
    return dict(competencia=competence,despesas=cost['valores'],origem_despesas=dict(arquivo= commercial.name,
        sha256=sha256(source).hexdigest(),aba=cost['aba'],celulas=cost['origem_celulas'],conta_c89=cost['conta_c89']),
        cpv=products,origem_cpv=dict(arquivo=cpv.name,sha256=sha256(cpv_bytes).hexdigest(),aba='CPV-Frango',competencia=month),
        regra=dict(versao='RATEIO_EXCEL_MENSAL_V1',competencia_despesas=competence,
            produtos_rateio=scope,residuos_sem_cpv_rateio=residues,
            pool='administrativa+financeira+comercial_sem_comissao+logistica-pallet(10,111,180)',
            rateio='FOB produto / FOB universo rateio * pool / peso produto; base integral do mês',
            impostos_status='PENDENTE_CONFERENCIA_RESPONSAVEIS',aliquotas_aprovadas=False))


def signature(content):
    return sha256(json.dumps(content,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def install(conn):
    script=Path(__file__).parents[1]/'sql/009_fob_fechamento_mensal.sql'
    with conn.transaction():
        conn.execute("SET LOCAL lock_timeout='3s'")
        conn.execute(script.read_text(encoding='utf-8'))


def import_month(conn,content,actor,backup_dir):
    from psycopg.types.json import Jsonb
    if not str(actor).isdecimal() or int(actor)<=0:raise ValueError('Ator técnico ausente.')
    competence=date.fromisoformat(content['competencia']+'-01');signed=signature(content)
    folder=Path(backup_dir);folder.mkdir(parents=True,exist_ok=True)
    with conn.transaction():
        conn.execute("SET LOCAL lock_timeout='3s'")
        conn.execute('SELECT pg_advisory_xact_lock(%s)',[697123009])
        before=conn.execute('SELECT * FROM comercial.fob_fechamento_mensal WHERE competencia=%s FOR UPDATE',[competence]).fetchone()
        if before and before['assinatura']==signed:
            return dict(alterado=False,competencia=str(competence),versao=before['versao'],lote=str(before['lote']),historicos_novos=0)
        backup=folder/(content['competencia']+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json')
        saved=dict(antes=before,proposta=content,ator=int(actor),assinatura=signed)
        serialized=json.dumps(saved,default=str,ensure_ascii=False,indent=2)
        backup.write_text(serialized,encoding='utf-8')
        if backup.read_text(encoding='utf-8')!=serialized:raise ValueError('Backup não conferiu; importação cancelada.')
        lote=str(uuid4());version=before['versao']+1 if before else 1
        conn.execute('INSERT INTO comercial.fob_fechamento_lote(lote,competencia,arquivos,resumo,ator) VALUES (%s,%s,%s,%s,%s)',
            [lote,competence,Jsonb([content['origem_despesas'],content['origem_cpv']]),
             Jsonb(dict(tipo='FECHAMENTO_MENSAL',competencia=content['competencia'],produtos_cpv=len(content['cpv']))),int(actor)])
        conn.execute('''INSERT INTO comercial.fob_fechamento_mensal(competencia,conteudo,assinatura,versao,lote,atualizado_por)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(competencia) DO UPDATE SET conteudo=excluded.conteudo,
            assinatura=excluded.assinatura,versao=excluded.versao,lote=excluded.lote,atualizado_por=excluded.atualizado_por,atualizado_em=clock_timestamp()''',
            [competence,Jsonb(content),signed,version,lote,int(actor)])
        conn.execute('''INSERT INTO comercial.fob_fechamento_mensal_historico(competencia,versao,lote,conteudo,assinatura,registrado_por)
            VALUES (%s,%s,%s,%s,%s,%s)''',[competence,version,lote,Jsonb(content),signed,int(actor)])
    return dict(alterado=True,competencia=str(competence),versao=version,lote=lote,historicos_novos=1,backup=str(backup))
