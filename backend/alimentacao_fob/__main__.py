"""Único ponto de execução. Sem argumentos: apenas valida os arquivos locais."""
import argparse
from contextlib import ExitStack
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path

from fob.master_data import invoice_key,pending_rows
from fob.master_repository import read_candidates,read_invoices
from .planilhas import locked,read_bundle,update_pending,publish_pending
from .importador import import_bundle,Unchanged,record_rejection
from .configuracao import load_config,connect,safe_error

DEFAULT_FOLDER=r'\\192.168.1.139\Controladoria\BI_Granja\Planilhas_Faturamento_Cfop'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,help='Configuração privada; padrão alimentacao_fob/.env.local.')
    parser.add_argument('--pasta',type=Path)
    actions=parser.add_mutually_exclusive_group()
    actions.add_argument('--sincronizar',action='store_true',help='Escreve somente os cadastros, em lote único transacional.')
    actions.add_argument('--atualizar-pendencias',action='store_true',help='Consulta PostgreSQL e atualiza só a aba automática.')
    actions.add_argument('--conferir-banco',action='store_true',help='Confere identidade, tabelas e privilégios com SELECTs.')
    actions.add_argument('--preparar-importacao',action='store_true',help='Prévia e backup privado; nenhuma escrita PostgreSQL.')
    parser.add_argument('--inicio',type=date.fromisoformat)
    parser.add_argument('--fim',type=date.fromisoformat)
    args=parser.parse_args(argv)
    try:load_config(args.config)
    except ValueError as error:
        print(json.dumps(dict(ok=False,erro=str(error)),ensure_ascii=False));return 1
    args.pasta=args.pasta or Path(os.environ.get('FOB_PLANILHAS_DIR',DEFAULT_FOLDER))
    if args.atualizar_pendencias and (not args.inicio or not args.fim or not 0<=(args.fim-args.inicio).days<=31):
        parser.error('Pendências exigem --inicio/--fim com até 32 dias inclusivos.')
    contents={};files={};result={}
    try:
        if args.conferir_banco:
            from .verificacao import inspect_database
            with connect() as conn:
                with conn.transaction():
                    conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                    result=inspect_database(conn)
            print(json.dumps(dict(ok=True,modo='conferencia_somente_leitura',**result),ensure_ascii=False));return 0
        with ExitStack() as stack:
            for name in ('Fretes.xlsx','Despesas.xlsx','Comissoes.xlsx'):
                handle=stack.enter_context(locked(args.pasta/name))
                contents[name]=handle.read()
                files[name]=dict(sha256=sha256(contents[name]).hexdigest(),arquivo=name)
            rules,monthly=read_bundle(contents)
            result=dict(modo='validacao',cadastros=len(rules),competencias=len(monthly))
            if args.preparar_importacao:
                from .verificacao import build_plan,save_plan
                with connect() as conn:
                    with conn.transaction():
                        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                        plan=build_plan(conn,rules,monthly,files,os.environ.get('FOB_ROBOT_ACTOR_ID',''))
                target=save_plan(plan,contents)
                result=dict(modo='previa_sem_escrita_postgresql',plano=str(target),**plan['resumo'])
            if args.sincronizar:
                actor=os.environ.get('FOB_ROBOT_ACTOR_ID','')
                with connect('FOB_PG_WRITE_DSN',True) as conn:
                    try:result=dict(modo='sincronizacao',**import_bundle(conn,rules,monthly,files,actor))
                    except Unchanged as unchanged:result=dict(modo='sem_alteracoes',**unchanged.summary)
        if args.atualizar_pendencias:
            with connect('FOB_PG_READ_DSN') as conn:
                with conn.transaction():
                    conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                    items=read_candidates(conn,args.inicio,args.fim)
                    invoices=read_invoices(conn,[invoice_key(i) for i in items])
                    pending=pending_rows(items,invoices)
            content=contents['Fretes.xlsx']
            updated=update_pending(content,pending)
            backup=publish_pending(args.pasta/'Fretes.xlsx',files['Fretes.xlsx']['sha256'],updated)
            keys={tuple(r.get(k) for k in ('empresa_contexto','unidade_documento','serie','nota_numero','ano_nf')) for r in pending if r.get('empresa_contexto')}
            result.update(pendencias=len(pending),notas=len(keys),revisar_identificacao=sum(r['situacao']!='PENDENTE' for r in pending),
                          backup=str(backup),preenchimentos_preservados=True,periodo=[str(args.inicio),str(args.fim)])
        print(json.dumps(dict(ok=True,**result),ensure_ascii=False))
        return 0
    except Exception as error:
        # Nunca imprimir DSN, senha, argumentos SQL ou dados salariais.
        message=safe_error(error)
        if args.sincronizar:
            try:
                with connect('FOB_PG_WRITE_DSN',True) as conn:record_rejection(conn,files,message)
            except Exception:message+=' Não foi possível registrar a rejeição no PostgreSQL.'
        print(json.dumps(dict(ok=False,erro=message),ensure_ascii=False))
        return 1


if __name__=='__main__':raise SystemExit(main())
