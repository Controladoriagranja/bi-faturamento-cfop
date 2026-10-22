"""Configuração explícita, sem execução de shell nem exposição de credenciais."""
from pathlib import Path
import os

DEFAULT_CONFIG=Path(__file__).with_name('.env.local')
ALLOWED={'PGHOST','PGPORT','PGDATABASE','PGUSER','PGPASSWORD','PGSSLMODE','PGPASSFILE',
         'FOB_PG_READ_DSN','FOB_PG_WRITE_DSN','FOB_PLANILHAS_DIR','FOB_ROBOT_ACTOR_ID','FOB_ESTADO_DIR','FOB_JANELA_DIAS'}


def load_config(path=None):
    target=Path(path) if path else DEFAULT_CONFIG
    if not target.exists():
        if path:raise ValueError('Arquivo de configuração informado não encontrado.')
        return
    for number,line in enumerate(target.read_text(encoding='utf-8-sig').splitlines(),1):
        if not line.strip() or line.lstrip().startswith('#'):continue
        if '=' not in line:raise ValueError(f'Configuração inválida na linha {number}; esperado CHAVE=valor.')
        key,value=line.split('=',1);key=key.strip();value=value.strip()
        if key not in ALLOWED:raise ValueError(f'Chave de configuração desconhecida na linha {number}.')
        if len(value)>=2 and value[0]==value[-1] and value[0] in ('"',"'"):value=value[1:-1]
        if value:os.environ.setdefault(key,value)


def connect(env='FOB_PG_READ_DSN',write=False):
    import psycopg
    from psycopg.rows import dict_row
    dsn=os.environ.get(env)
    kwargs=dict(row_factory=dict_row,connect_timeout=5,autocommit=True,
        options='-c statement_timeout=15000'+('' if write else ' -c default_transaction_read_only=on'))
    if dsn:
        # DSN de configuração é lida em memória; nunca incluída em mensagens de erro.
        from psycopg.conninfo import conninfo_to_dict
        try:database=conninfo_to_dict(dsn).get('dbname')
        except Exception:raise ValueError('DSN inválida na configuração privada.') from None
        if database!='bi_granja':raise ValueError('A DSN deve declarar dbname=bi_granja.')
        return psycopg.connect(dsn,**kwargs)
    if write or env=='FOB_PG_WRITE_DSN':raise ValueError('Configure FOB_PG_WRITE_DSN para a conta técnica de escrita.')
    required=('PGHOST','PGPORT','PGDATABASE','PGUSER','PGPASSWORD')
    missing=[key for key in required if not os.environ.get(key)]
    if missing:raise ValueError('Configuração ausente: '+', '.join(missing)+'. Preencha backend/alimentacao_fob/.env.local.')
    if os.environ['PGDATABASE']!='bi_granja':raise ValueError('Esta implantação exige PGDATABASE=bi_granja.')
    try:
        port=int(os.environ['PGPORT'])
        if not 1<=port<=65535:raise ValueError()
    except ValueError:raise ValueError('PGPORT deve ser uma porta válida.') from None
    credentials=dict(host=os.environ['PGHOST'],port=port,dbname=os.environ['PGDATABASE'],
                     user=os.environ['PGUSER'],password=os.environ['PGPASSWORD'])
    if os.environ.get('PGSSLMODE'):credentials['sslmode']=os.environ['PGSSLMODE']
    return psycopg.connect(**credentials,**kwargs)


def safe_error(error):
    """Classifica falhas sem devolver mensagem libpq, DSN ou senha."""
    if isinstance(error,ValueError):return str(error)
    code=getattr(error,'sqlstate',None)
    message=str(error).lower()  # Somente classificação em memória; nunca imprimir.
    if code=='28P01' or 'password authentication failed' in message:
        return 'PostgreSQL recusou a autenticação. Confira PGUSER e PGPASSWORD (28P01).'
    if 'no pg_hba.conf entry' in message:
        return 'PostgreSQL recusou a origem/conexão em pg_hba.conf; conferir liberação com o administrador.'
    if code=='28000':return 'PostgreSQL recusou a autorização da conexão (28000).'
    if code=='3D000':return 'O PostgreSQL acessado não possui o banco bi_granja (3D000).'
    if code=='42501':return 'Privilégio PostgreSQL insuficiente para a operação (42501).'
    if 'connection refused' in message or 'actively refused' in message:
        return 'Conexão TCP recusada; conferir serviço PostgreSQL, endereço e porta, sem alterar o servidor.'
    if 'timeout expired' in message or 'connection timeout' in message:
        return 'Timeout ao conectar; conferir caminho de rede/firewall e disponibilidade do PostgreSQL.'
    if code=='57014':return 'Consulta cancelada por timeout PostgreSQL (57014); reduzir o intervalo e conferir o plano.'
    return 'Falha operacional; último lote válido preservado. Tipo: '+type(error).__name__
