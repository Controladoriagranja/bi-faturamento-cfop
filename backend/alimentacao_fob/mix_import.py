"""Cadastro pontual do Mix de outubro, preservando o fechamento já importado."""
from copy import deepcopy
from datetime import date,datetime,timezone
from decimal import Decimal
from hashlib import sha256
import argparse,json,re
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from alimentacao_fob.configuracao import load_config,connect,safe_error
from alimentacao_fob.fechamento import import_month,signature
from modules.comparativo_fob.mix_engine import method

TARGET=ROOT/'artifacts/comparativo-mix-outubro-importacao-20261123'
SOURCE=ROOT/'artifacts/comparativo-mix-20261123/parametros-propostos-outubro.json'


def proposed():
    proposal=json.loads(SOURCE.read_text(encoding='utf-8'))
    if proposal['competencia']!='2026-10':raise ValueError('Importação restrita a outubro/2026.')
    source=Path.home()/'Downloads'/proposal['origem']['arquivo']
    if sha256(source.read_bytes()).hexdigest()!=proposal['origem']['sha256']:
        raise ValueError('O Excel mudou desde a prévia; conferir nova versão antes de importar.')
    if proposal['origem']['sha256']!=method()['referencia_metodo']['sha256']:
        raise ValueError('Prévia e método têm origens diferentes.')
    selected=deepcopy(proposal)
    # Só parâmetros usados pelo modelo. Exclui entradas comerciais avulsas do
    # rodapé da planilha de preços e os custos de farinha de outra competência.
    selected['cells']={sheet:cells for sheet,cells in selected['cells'].items()
        if sheet in ('AnaliseMix','RendimentosXFormulacoes')}
    selected['cells']['CPV-Frango']={ref:value for ref,value in proposal['cells']['CPV-Frango'].items()
        if re.sub(r'\d','',ref) in ('G','K','M','N','AG','CZ')}
    selected['cells']['PrecoMedioXEmbalagemAN-RA-RN']={ref:value for ref,value in proposal['cells']['PrecoMedioXEmbalagemAN-RA-RN'].items()
        if re.fullmatch(r'[HIJ]12[0-3]',ref)}
    if any(Decimal(v)!=0 for v in selected['cells']['PrecoMedioXEmbalagemAN-RA-RN'].values()):
        raise ValueError('Conferir novos parâmetros de embalagem antes de importar.')
    if 'CPV-Farinha' not in selected['bloqueios']:raise ValueError('Bloqueio de competência ausente.')
    for cells in selected['cells'].values():
        if any(not Decimal(v).is_finite() for v in cells.values()):raise ValueError('Parâmetro não finito.')
    selected['estado']='IMPORTADO_OUTUBRO_COM_BLOQUEIOS'
    selected['validacao']='Cadastro inicial de outubro autorizado pelo usuário; sem liberar fontes não comprovadas.'
    return selected


def run(write=False):
    load_config();params=proposed();TARGET.mkdir(parents=True,exist_ok=True)
    with connect() as conn:
        row=conn.execute("SELECT * FROM comercial.fob_fechamento_mensal WHERE competencia=%s",[date(2026,10,1)]).fetchone()
        others=conn.execute("SELECT competencia,assinatura,versao,lote FROM comercial.fob_fechamento_mensal WHERE competencia<>%s ORDER BY competencia",[date(2026,10,1)]).fetchall()
    if not row:raise ValueError('Fechamento de outubro inexistente. Não criar outro fechamento nesta operação.')
    current=row['conteudo'];existing=current.get('mix')
    if existing and existing!=params:raise ValueError('Mix de outubro já possui cadastro diferente; não sobrescrever sem conciliação.')
    content=deepcopy(current);content['mix']=params
    report=dict(competencia='2026-10',tabela='comercial.fob_fechamento_mensal',registros_atualizados=0 if existing else 1,
        historico_novo=0 if existing else 1,lote_novo=0 if existing else 1,
        parametros_por_aba={s:len(c) for s,c in params['cells'].items()},bloqueios=params['bloqueios'],
        despesas_cpv_regra_preservados=all(content[k]==v for k,v in current.items() if k!='mix'))
    (TARGET/'previa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not write:return report
    # Backup completo antes de qualquer escrita; sem alterar acessos/ACLs.
    backup=TARGET/('backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json')
    saved=json.dumps(dict(fechamento_antes=row,outras_competencias=others,proposta=content),default=str,ensure_ascii=False,indent=2)
    backup.write_text(saved,encoding='utf-8')
    if backup.read_text(encoding='utf-8')!=saved:raise ValueError('Backup não conferiu.')
    import os
    actor=os.environ.get('FOB_ROBOT_ACTOR_ID')
    if actor!='900000000006':raise ValueError('Conferir o ator técnico já reservado para o robô FOB.')
    with connect('FOB_PG_WRITE_DSN',write=True) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL lock_timeout='3s'")
            conn.execute('SELECT pg_advisory_xact_lock(%s)',[697123009])
            locked=conn.execute('SELECT * FROM comercial.fob_fechamento_mensal WHERE competencia=%s FOR UPDATE',[date(2026,10,1)]).fetchone()
            if locked['assinatura']!=row['assinatura'] or locked['versao']!=row['versao']:
                raise ValueError('Fechamento mudou após a prévia; operação cancelada.')
            result=import_month(conn,content,actor,TARGET/'backups-importador')
            after=conn.execute('SELECT * FROM comercial.fob_fechamento_mensal WHERE competencia=%s',[date(2026,10,1)]).fetchone()
            if after['conteudo']!=content:raise ValueError('Conteúdo importado não conferiu.')
            if any(after['conteudo'][k]!=v for k,v in current.items() if k!='mix'):
                raise ValueError('Outro componente do fechamento mudou; operação cancelada.')
            remaining=conn.execute("SELECT competencia,assinatura,versao,lote FROM comercial.fob_fechamento_mensal WHERE competencia<>%s ORDER BY competencia",[date(2026,10,1)]).fetchall()
            if remaining!=others:raise ValueError('Outra competência mudou durante a operação; conferir concorrência.')
            # O próprio importador detecta assinatura idêntica antes de criar lote/histórico.
            second=import_month(conn,content,actor,TARGET/'backups-importador')
            if second['alterado'] or second['historicos_novos']:raise ValueError('Idempotência não conferiu.')
            history=conn.execute('SELECT count(*) n FROM comercial.fob_fechamento_mensal_historico WHERE competencia=%s AND versao=%s AND lote=%s',
                [date(2026,10,1),after['versao'],after['lote']]).fetchone()['n']
            if history!=1:raise ValueError('Histórico não conferiu.')
    report.update(importacao=result,idempotencia=second,backup=str(backup),historico_confirmado=history,outras_competencias_preservadas=True)
    (TARGET/'resultado.json').write_text(json.dumps(report,default=str,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--importar',action='store_true');args=parser.parse_args()
    try:print(json.dumps(run(args.importar),default=str,ensure_ascii=True))
    except Exception as error:print(json.dumps(dict(ok=False,motivo=safe_error(error)),ensure_ascii=True));raise SystemExit(1)
