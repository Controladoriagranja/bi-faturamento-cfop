"""Réplicas mensais determinísticas: parâmetros, nunca resultados FOB."""
from calendar import monthrange
from copy import deepcopy
from datetime import date,timedelta
from collections import defaultdict

from fob.calculator import code
from fob.master_data import digest,day,validate_rules
from .planilhas import table,RULE_HEADERS,PAYROLL_HEADERS,MANAGER_HEADERS,read_bundle
from .rotina import month_windows

MARKER='REPLICA_OUTUBRO_2026'
SHEETS=(('Despesas.xlsx','Cadastros',RULE_HEADERS),('Comissoes.xlsx','Percentuais',RULE_HEADERS),
        ('Comissoes.xlsx','Vendedores',PAYROLL_HEADERS),('Comissoes.xlsx','Gestores',MANAGER_HEADERS))


def selection(rule):
    dims={k:code(v) if k in ('unidade_documento','vendedor','cliente','rede','produto') else v for k,v in rule['dimensoes'].items()}
    return rule['tipo'],digest(dims)


def gaps(start,end,covered):
    cursor=start
    for a,b in sorted(covered):
        if b<cursor or a>end:continue
        if a>cursor:yield cursor,min(end,a-timedelta(days=1))
        cursor=max(cursor,b+timedelta(days=1))
        if cursor>end:return
    if cursor<=end:yield cursor,end


def replica_id(source,start,end):
    return 'replica:2026-10:'+str(start)+':'+str(end)+':'+source


def prepare_rows(contents,current,calendar_policy=None):
    """Cobre jan–out apenas nas lacunas da mesma seleção. Nada substitui o original."""
    rules,monthly=read_bundle(contents)
    combined={r['registro']:r for r in current}
    combined.update({r['registro']:r for r in rules})
    validate_rules(list(combined.values()))
    sources={r['registro']:r for r in rules if r['ativo'] and r['tipo']!='frete' and
        MARKER not in r['origem'] and day(r['inicio'])<=date(2026,10,1)<=day(r['fim'])}
    if not sources:raise ValueError('Não há parâmetros originais de outubro nos arquivos-mestre.')
    covered=defaultdict(list)
    for rule in combined.values():
        if rule.get('ativo',True):covered[selection(rule)].append((day(rule['inicio']),day(rule['fim'])))
    additions=defaultdict(list);source_count=0;calendar_waiting=0
    for filename,sheet,headers in SHEETS:
        for original in table(contents[filename],sheet,headers):
            source=sources.get(original['registro'])
            if not source:continue
            source_count+=1
            for month_start,month_end in month_windows(date(2026,1,1),date(2026,10,31)):
                # Gestores têm código por competência para os vínculos da folha.
                # Para os demais cadastros, a seleção e suas vigências têm precedência.
                periods=list(gaps(month_start,month_end,covered[selection(source)]))
                for start,end in periods:
                    register=replica_id(source['registro'],start,end)
                    if register in combined:continue
                    row={k:deepcopy(v) for k,v in original.items() if k!='_linha'}
                    row.update(registro=register,inicio=str(start),fim=str(end),
                        origem=MARKER+' | parâmetro de '+source['registro']+' | '+str(original.get('origem') or ''))
                    if source['tipo'] in ('folha','gestor'):
                        if calendar_policy!='REPLICAR_26_5':calendar_waiting+=1
                        row['dias_mes']=monthrange(start.year,start.month)[1]
                        row['dias_periodo']=(end-start).days+1
                        # Dias úteis/DSR e encargos permanecem como parâmetros provisórios
                        # da origem; não se inventa calendário de feriados.
                        if source['tipo']=='folha':
                            for field in ('gestor1','gestor2','gestor3'):
                                manager=row.get(field)
                                if manager:
                                    if manager not in sources:raise ValueError('Gestor da réplica não está na origem de outubro.')
                                    row[field]=replica_id(manager,start,end)
                    additions[filename,sheet].append(row)
    # Não produzir uma folha com gestores em vigências diferentes silenciosamente.
    known_ids=set(combined)|{r['registro'] for rows in additions.values() for r in rows}
    for row in additions.get(('Comissoes.xlsx','Vendedores'),[]):
        if any(row.get(k) and row[k] not in known_ids for k in ('gestor1','gestor2','gestor3')):
            raise ValueError('Vigência histórica real exige conciliação dos gestores; nenhuma substituição automática.')
    return additions,dict(originais=len(rules),fontes_outubro=source_count,
        novos=sum(map(len,additions.values())),por_aba={f+' / '+s:len(v) for (f,s),v in additions.items()},
        calendario_pendente=calendar_waiting,competencias_januaria_preservadas=len(monthly),
        marcador=MARKER,politica_calendario=calendar_policy,
        observacao_januaria='Competências próprias preservadas; fallback de outubro já existente não cria competências históricas.')


def provisional_coverage(rules):
    """Metadados públicos do lote, sem folha/salários e sem modificar a API."""
    periods=defaultdict(int)
    for r in rules:
        if r.get('ativo',True) and MARKER in r.get('origem',''):
            periods[str(r['inicio']),str(r['fim'])]+=1
    return [dict(inicio=a,fim=b,cadastros=count,origem=MARKER) for (a,b),count in sorted(periods.items())]


def prepare_history(folder,calendar_policy=None):
    """Backup e plano privado. Não altera planilha de rede nem PostgreSQL."""
    import json,os
    from .rotina import capture_bundle
    from .configuracao import connect
    from .verificacao import build_plan,save_plan
    contents,files,rules,monthly=capture_bundle(folder)
    with connect() as conn:
        with conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            plan=build_plan(conn,rules,monthly,files,os.environ.get('FOB_ROBOT_ACTOR_ID',''))
            additions,summary=prepare_rows(contents,plan['estado_antes']['cadastros'],calendar_policy)
    path=save_plan(plan,contents)
    target=path.with_name('replica-historica.json')
    data=dict(resumo=summary,arquivos_origem=files,
        planilhas=[dict(arquivo=f,aba=s,linhas=rows) for (f,s),rows in additions.items()])
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    return dict(plano=str(target),**summary)


def publish_history(folder,plan_path,calendar_policy):
    """Publica os mestres já validados e prepara a sincronização; não escreve no banco."""
    import json,os
    from pathlib import Path
    from hashlib import sha256
    from .rotina import capture_bundle
    from .configuracao import connect
    from .verificacao import build_plan,save_plan
    from .importador import same
    from .planilhas import publish_pending
    from .replica_planilhas import part
    from zipfile import ZipFile
    from io import BytesIO
    if calendar_policy!='REPLICAR_26_5':raise ValueError('Confirmar o calendário provisório antes de publicar os parâmetros.')
    source=Path(plan_path);proposal=json.loads(source.read_text(encoding='utf-8'))
    contents,files,originals,monthly=capture_bundle(folder)
    staged=dict(contents);allowed={}
    for name in ('Despesas.xlsx','Comissoes.xlsx'):
        if files[name]!=proposal['arquivos_origem'][name]:raise ValueError(name+' mudou após o backup; refaça a prévia.')
        staged[name]=source.with_name(name.replace('.xlsx','.preparada.xlsx')).read_bytes()
        with ZipFile(BytesIO(contents[name])) as before,ZipFile(BytesIO(staged[name])) as after:
            if set(before.namelist())!=set(after.namelist()):raise ValueError('Estrutura XLSX divergente da origem.')
            allowed[name]={p for p in before.namelist() if before.read(p)!=after.read(p)}
            expected_sheets={part(before,s['aba']) for s in proposal['planilhas'] if s['arquivo']==name}
            if not allowed[name] or any(p not in expected_sheets and not p.startswith('xl/tables/') for p in allowed[name]):
                raise ValueError('A réplica alteraria conteúdo fora das abas previstas.')
    rules,costs=read_bundle(staged);indexed={r['registro']:r for r in rules}
    if costs!=monthly or any(r['registro'] not in indexed or not same(r,indexed[r['registro']]) for r in originals):
        raise ValueError('Originais ou custo mensal seriam alterados; operação cancelada.')
    staged_files={n:dict(arquivo=n,sha256=sha256(data).hexdigest()) for n,data in staged.items()}
    with connect() as conn:
        with conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            plan=build_plan(conn,rules,costs,staged_files,os.environ.get('FOB_ROBOT_ACTOR_ID',''))
    if plan['resumo']['alterados'] or plan['resumo']['competencias_a_alterar']:
        raise ValueError('Prévia detectou alteração financeira anterior; conferir antes de publicar.')
    target=save_plan(plan,staged)
    backups=[]
    for name in ('Despesas.xlsx','Comissoes.xlsx'):
        backups.append(str(publish_pending(Path(folder)/name,files[name]['sha256'],staged[name],allowed[name])))
    receipt=dict(ok=True,plano=str(target),backups=backups,politica_calendario=calendar_policy,
        escrita_postgresql=False,**plan['resumo'])
    source.with_name('publicacao-mestres.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    return receipt
