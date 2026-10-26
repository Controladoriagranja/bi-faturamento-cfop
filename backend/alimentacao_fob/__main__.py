"""Único ponto de execução. Sem argumentos: apenas valida os arquivos locais."""
import argparse
from contextlib import ExitStack
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path

from .planilhas import locked,read_bundle
from .importador import record_rejection
from .configuracao import load_config,connect,safe_error

DEFAULT_FOLDER=r'\\192.168.1.139\Controladoria\BI_Granja\Planilhas_Faturamento_Cfop'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,help='Configuração privada; padrão alimentacao_fob/.env.local.')
    parser.add_argument('--pasta',type=Path)
    actions=parser.add_mutually_exclusive_group()
    actions.add_argument('--sincronizar',action='store_true',help='Prévia, backup, alterações transacionais e baixa das pendências preenchidas.')
    actions.add_argument('--atualizar-recentes',action='store_true',help='Somente pendências da janela recente; não importa custos.')
    actions.add_argument('--atualizar-pendencias',action='store_true',help='Consulta PostgreSQL e atualiza só a aba automática.')
    actions.add_argument('--conferir-banco',action='store_true',help='Confere identidade, tabelas e privilégios com SELECTs.')
    actions.add_argument('--preparar-importacao',action='store_true',help='Prévia e backup privado; nenhuma escrita PostgreSQL.')
    actions.add_argument('--recuperar-pendencias',action='store_true',help='Recupera mês a mês, acumulando Pendências; sem importar.')
    actions.add_argument('--rotina-diaria',action='store_true',help='Janela recente, prévia/backup e sincronização; só após sucesso do faturamento.')
    actions.add_argument('--preparar-historico',action='store_true',help='Backup e réplicas provisórias mensais em plano privado; sem escrita financeira.')
    actions.add_argument('--publicar-historico',type=Path,metavar='PLANO',help='Publica mestres preparados e gera prévia; não importa no PostgreSQL.')
    parser.add_argument('--calendario-replica',choices=['REPLICAR_26_5'],help='Somente após aceite do calendário provisório da folha.')
    parser.add_argument('--inicio',type=date.fromisoformat)
    parser.add_argument('--fim',type=date.fromisoformat)
    args=parser.parse_args(argv)
    try:load_config(args.config)
    except ValueError as error:
        print(json.dumps(dict(ok=False,erro=str(error)),ensure_ascii=False));return 1
    args.pasta=args.pasta or Path(os.environ.get('FOB_PLANILHAS_DIR',DEFAULT_FOLDER))
    if args.atualizar_pendencias and (not args.inicio or not args.fim or not 0<=(args.fim-args.inicio).days<=31):
        parser.error('Pendências exigem --inicio/--fim com até 32 dias inclusivos.')
    if args.recuperar_pendencias and (not args.inicio or not args.fim or args.inicio>args.fim):
        parser.error('Recuperação exige --inicio/--fim válidos; as consultas são mensais.')
    contents={};files={};result={}
    try:
        if args.sincronizar or args.atualizar_recentes:
            from .rotina import synchronize,recent,log_result
            if args.inicio or args.fim:raise ValueError('Use --atualizar-pendencias para um intervalo explícito.')
            result=synchronize(args.pasta) if args.sincronizar else dict(
                modo='pendencias_recentes',pendencias=recent(args.pasta,int(os.environ.get('FOB_JANELA_DIAS','14'))))
            ok=not result.get('pendencias_falhas')
            log_result(dict(ok=ok,**result))
            print(json.dumps(dict(ok=ok,**result),ensure_ascii=False));return 0 if ok else 1
        if args.publicar_historico:
            from .historico import publish_history
            result=publish_history(args.pasta,args.publicar_historico,args.calendario_replica)
            print(json.dumps(dict(modo='mestres_publicados_sincronizacao_pendente',**result),ensure_ascii=False));return 0
        if args.preparar_historico:
            from .historico import prepare_history
            result=prepare_history(args.pasta,args.calendario_replica)
            print(json.dumps(dict(ok=True,modo='previa_historica_sem_escrita',**result),ensure_ascii=False));return 0
        if args.recuperar_pendencias or args.rotina_diaria or args.atualizar_pendencias:
            from .rotina import daily,month_windows,refresh_window,log_result
            if args.rotina_diaria:
                if args.inicio or args.fim:raise ValueError('Rotina diária usa FOB_JANELA_DIAS; datas pertencem à recuperação histórica.')
                result=daily(args.pasta,int(os.environ.get('FOB_JANELA_DIAS','14')))
            else:
                periods=list(month_windows(args.inicio,args.fim)) if args.recuperar_pendencias else [(args.inicio,args.fim)]
                reports=[]
                for start,end in periods:
                    report=refresh_window(args.pasta,start,end);reports.append(report)
                    print(json.dumps(dict(ok=True,etapa='pendencias_mensais',**report),ensure_ascii=False),flush=True)
                result=dict(modo='recuperacao_pendencias' if args.recuperar_pendencias else 'atualizacao_pendencias',meses=reports)
            ok=not result.get('pendencias_falhas')
            log_result(dict(ok=ok,**result))
            print(json.dumps(dict(ok=ok,**result),ensure_ascii=False));return 0 if ok else 1
        if args.conferir_banco:
            from .verificacao import inspect_database
            with connect() as conn:
                with conn.transaction():
                    conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                    result=inspect_database(conn)
            from .rotina import log_result
            log_result(dict(ok=True,modo='conferencia_somente_leitura',tabelas_conferidas=len(result['tabelas'])))
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
        from .rotina import log_result
        log_result(dict(ok=True,**result))
        print(json.dumps(dict(ok=True,**result),ensure_ascii=False))
        return 0
    except Exception as error:
        # Nunca imprimir DSN, senha, argumentos SQL ou dados salariais.
        message=safe_error(error)
        from .rotina import log_result
        try:log_result(dict(ok=False,erro=message))
        except OSError:pass
        if args.sincronizar and not result.get('banco_confirmado'):
            try:
                with connect('FOB_PG_WRITE_DSN',True) as conn:record_rejection(conn,files,message)
            except Exception:message+=' Não foi possível registrar a rejeição no PostgreSQL.'
        print(json.dumps(dict(ok=False,erro=message,**result),ensure_ascii=False))
        return 1


if __name__=='__main__':raise SystemExit(main())
