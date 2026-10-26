"""Janelas mensais de recuperação e janela recente da execução diária."""
from collections import Counter
from contextlib import ExitStack
from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
import json,os
from pathlib import Path

from fob.master_data import MasterCatalog,invoice_key,pending_rows
from fob.master_repository import read_candidates,read_invoices
from .configuracao import connect,safe_error
from .planilhas import locked,merge_pending,publish_pending,read_bundle,table,PENDING_HEADERS,NF,input_date
from .verificacao import build_plan,save_plan
from .importador import import_bundle,Unchanged

NAMES=('Fretes.xlsx','Despesas.xlsx','Comissoes.xlsx')


def month_windows(start,end):
    if start>end:raise ValueError('Período invertido.')
    cursor=start
    while cursor<=end:
        following=date(cursor.year+(cursor.month==12),cursor.month%12+1,1)
        stop=min(end,following-timedelta(days=1))
        yield cursor,stop
        cursor=stop+timedelta(days=1)


def refresh_window(folder,start,end):
    if not 0<=(end-start).days<=31:raise ValueError('Janela de pendências excede 32 dias.')
    path=Path(folder)/'Fretes.xlsx'
    with locked(path) as handle:content=handle.read()
    with connect() as conn:
        with conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            items=read_candidates(conn,start,end)
            invoices=read_invoices(conn,[invoice_key(i) for i in items])
            records=pending_rows(items,invoices)
            # Só valores já efetivados no PostgreSQL resolvem uma pendência.
            rules=conn.execute('''SELECT * FROM comercial.fob_cadastro
                WHERE ativo AND tipo='frete' AND inicio<=%s AND fim>=%s ORDER BY registro''',[end,start]).fetchall()
            catalog=MasterCatalog(rules,invoices=invoices)
            unresolved=[]
            for item,record in zip(items,records):
                rate=catalog.freight(item)
                if record['situacao']=='PENDENTE' and rate.value is not None and rate.status=='planilha_mestre':continue
                if rate.status in ('revisar_identificacao','pendente_ambiguidade'):
                    record.update(situacao='REVISAR_IDENTIFICACAO',motivo='Preenchimento importado exige revisão: '+rate.status)
                unresolved.append(record)
    updated,total=merge_pending(content,unresolved,start,end)
    backup=publish_pending(path,sha256(content).hexdigest(),updated) if updated!=content else None
    keys={invoice_key(i) for i in unresolved if i.get('empresa_contexto')}
    return dict(inicio=str(start),fim=str(end),itens=len(unresolved),notas=len(keys),
        revisar=sum(r['situacao']!='PENDENTE' for r in unresolved),itens_acumulados=total,
        backup=str(backup) if backup else None,alterado=updated!=content,preenchimentos_preservados=True)


def capture_bundle(folder):
    contents={}
    with ExitStack() as stack:
        for name in NAMES:contents[name]=stack.enter_context(locked(Path(folder)/name)).read()
    files={name:dict(arquivo=name,sha256=sha256(data).hexdigest()) for name,data in contents.items()}
    rules,monthly=read_bundle(contents)
    return contents,files,rules,monthly


def prepare_sync(folder,save_unchanged=True):
    contents,files,rules,monthly=capture_bundle(folder)
    with connect() as conn:
        with conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            plan=build_plan(conn,rules,monthly,files,os.environ.get('FOB_ROBOT_ACTOR_ID',''))
    changed=plan['resumo']['novos'] or plan['resumo']['alterados'] or plan['resumo']['competencias_a_alterar']
    target=save_plan(plan,contents) if changed or save_unchanged else None
    return target,plan,files


def recent(folder,window_days=14,until=None):
    """Somente pendências após o faturamento; não importa custos."""
    if not 1<=window_days<=32:raise ValueError('FOB_JANELA_DIAS deve ser de 1 a 32.')
    end=until or date.today();start=end-timedelta(days=window_days-1)
    return [refresh_window(folder,a,b) for a,b in month_windows(start,end)]


def filled_windows(content,rules):
    """Reconsulta apenas datas das pendências que têm preenchimento cadastrado.

    Inclui NFs antigas, sem reprocessar o ano. Também permite recuperar uma falha
    de publicação ocorrida depois do commit na execução anterior.
    """
    freight={}
    for rule in rules:
        if rule['tipo']!='frete' or not rule.get('ativo',True):continue
        dims=rule['dimensoes'];key=tuple(dims[k] for k in NF)
        freight.setdefault(key,[]).append(dims.get('chave_item'))
    if not freight:return []
    months={}
    for row in table(content,'Pendências',PENDING_HEADERS):
        key=tuple(int(row[k]) if k=='ano_nf' else row[k] for k in NF)
        scopes=freight.get(key,[])
        if not any(scope is None or scope==row['chave_item'] for scope in scopes):continue
        current=date.fromisoformat(input_date(row['data']))
        months.setdefault(current.replace(day=1),[]).append(current)
    return [(min(days),max(days)) for _,days in sorted(months.items())]


def synchronize(folder):
    """Prévia e backup antes de escrever; nenhuma conexão de escrita se nada mudou."""
    target,plan,expected=prepare_sync(folder,save_unchanged=False)
    with ExitStack() as stack:
        contents={name:stack.enter_context(locked(Path(folder)/name)).read() for name in NAMES}
        files={name:dict(arquivo=name,sha256=sha256(data).hexdigest()) for name,data in contents.items()}
        if files!=expected:raise ValueError('Planilhas mudaram após a prévia; sincronização cancelada.')
        rules,monthly=read_bundle(contents)
        cleanup={r['registro']:r for r in plan.get('estado_antes',{}).get('cadastros',[])}
        cleanup.update({r['registro']:r for r in rules})
        windows=filled_windows(contents['Fretes.xlsx'],cleanup.values())
        summary=plan['resumo']
        if not (summary['novos'] or summary['alterados'] or summary['competencias_a_alterar']):
            result=dict(modo='sem_alteracoes',cadastros_alterados=0,competencias_alteradas=0,
                        cadastros_lidos=len(rules),competencias_lidas=len(monthly))
        else:
            # Os três backups e a prévia existem antes da conexão de escrita.
            with connect('FOB_PG_WRITE_DSN',True) as conn:
                try:result=dict(modo='sincronizacao',**import_bundle(conn,rules,monthly,files,os.environ.get('FOB_ROBOT_ACTOR_ID','')))
                except Unchanged as unchanged:result=dict(modo='sem_alteracoes',**unchanged.summary)
    result.update(plano=str(target) if target else None,banco_confirmado=True)
    # Se a publicação SMB falhar após o commit, não registrar falsa rejeição do lote.
    reports=[];failures=[]
    try:log_result(dict(ok=True,etapa='banco_confirmado',**result))
    except OSError:failures.append(dict(etapa='log',erro='Banco conferido, mas não foi possível gravar o log local.'))
    for start,end in windows:
        try:reports.append(refresh_window(folder,start,end))
        except Exception as error:failures.append(dict(inicio=str(start),fim=str(end),erro=safe_error(error)))
    return dict(**result,pendencias=reports,pendencias_falhas=failures)


def daily(folder,window_days=14,until=None):
    """Compatibilidade: sincroniza mestres e depois atualiza a janela recente."""
    if not 1<=window_days<=32:raise ValueError('FOB_JANELA_DIAS deve ser de 1 a 32.')
    result=synchronize(folder)
    try:result['pendencias_recentes']=recent(folder,window_days,until)
    except Exception as error:result['pendencias_falhas'].append(dict(etapa='janela_recente',erro=safe_error(error)))
    return result


def log_result(result):
    # Apenas resumo operacional, sem linhas financeiras, parâmetros de folha ou DSN.
    root=Path(os.environ.get('FOB_ESTADO_DIR') or Path(os.environ.get('LOCALAPPDATA',Path.home()))/'GranjaBrasilia/FOB')/'logs'
    root.mkdir(parents=True,exist_ok=True)
    path=root/(datetime.now(timezone.utc).strftime('%Y-%m-%d')+'.jsonl')
    with path.open('a',encoding='utf-8') as output:
        output.write(json.dumps(dict(executado_em=datetime.now(timezone.utc).isoformat(),**result),ensure_ascii=False,default=str)+'\n')
    return str(path)
