"""Um lote para os três arquivos, com histórico e preservação do último válido."""
from datetime import date
from decimal import Decimal
import json
from uuid import uuid4

from fob.master_data import digest, item_identity, validate_rules
from fob.master_repository import read_invoices

LOCK = 697123006


def plain(value):
    return json.loads(json.dumps(value,default=str,ensure_ascii=False))


def same(before,after):
    # O JSON PostgreSQL preserva strings decimais; normalização dos tipos na borda.
    fields=('registro','tipo','inicio','fim','dimensoes','modalidade','parametros','origem','ativo')
    return Decimal(str(before['valor']))==Decimal(str(after['valor'])) and \
        digest({k:before.get(k) for k in fields})==digest({k:after.get(k) for k in fields})


def validate_freight(conn,rules):
    freight=[r for r in rules if r['tipo']=='frete' and r.get('ativo',True)]
    keys=[tuple(r['dimensoes'][k] for k in ('empresa_contexto','unidade_documento','serie','nota_numero','ano_nf')) for r in freight]
    invoices=read_invoices(conn,keys)
    from fob.master_data import MasterCatalog
    catalog=MasterCatalog(freight,invoices=invoices)
    for r,key in zip(freight,keys):
        rows=invoices.get(key,[])
        if not rows:raise ValueError('NF de frete não encontrada na origem integral.')
        targeted=[i for i in rows if 'chave_item' not in r['dimensoes'] or
                  item_identity(i)==r['dimensoes']['chave_item']]
        if not targeted:raise ValueError('Item de frete não encontrado na NF integral.')
        for item in targeted:
            resolved=catalog.freight(item)
            if resolved.value is None or resolved.status!='planilha_mestre':
                raise ValueError('Frete inválido: '+resolved.status)


def import_bundle(conn,rules,monthly,files,actor):
    """O chamador mantém os arquivos bloqueados e usa uma conexão transacional."""
    from psycopg.types.json import Jsonb
    if not actor.isdecimal() or int(actor)<=0:raise ValueError('Defina FOB_ROBOT_ACTOR_ID técnico, reservado pelo administrador.')
    lote=str(uuid4());changed=0;monthly_changed=0
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(%s)',[LOCK])
        conn.execute("SET LOCAL lock_timeout='3s'")
        conn.execute("SET LOCAL statement_timeout='15s'")
        current=conn.execute('SELECT * FROM comercial.fob_cadastro ORDER BY registro FOR UPDATE').fetchall()
        indexed={r['registro']:r for r in current}
        merged={**indexed,**{r['registro']:r for r in rules}}
        # Remover uma linha do XLSX não revoga silenciosamente um cadastro histórico.
        validate_rules(list(merged.values()))
        validate_freight(conn,rules)
        conn.execute('INSERT INTO comercial.fob_importacao(lote,status,arquivos) VALUES (%s,\'VALIDADO\',%s)',
                     [lote,Jsonb(files)])
        for rule in rules:
            old=indexed.get(rule['registro'])
            if old and same(old,rule):continue
            version=old['versao']+1 if old else 1
            values=[rule[k] for k in ('registro','tipo','inicio','fim')]
            values += [Jsonb(plain(rule['dimensoes'])),rule['modalidade'],rule['valor'],Jsonb(plain(rule['parametros'])),
                       rule['origem'],rule['ativo'],version,lote]
            saved=conn.execute('''INSERT INTO comercial.fob_cadastro
              (registro,tipo,inicio,fim,dimensoes,modalidade,valor,parametros,origem,ativo,versao,lote)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
              ON CONFLICT (registro) DO UPDATE SET tipo=excluded.tipo,inicio=excluded.inicio,fim=excluded.fim,
              dimensoes=excluded.dimensoes,modalidade=excluded.modalidade,valor=excluded.valor,
              parametros=excluded.parametros,origem=excluded.origem,ativo=excluded.ativo,
              versao=excluded.versao,lote=excluded.lote,atualizado_em=clock_timestamp() RETURNING *''',values).fetchone()
            if old:
                conn.execute('''INSERT INTO comercial.fob_cadastro_historico(registro,versao,lote,conteudo)
                  VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                  [old['registro'],old['versao'],old['lote'],Jsonb(plain(old))])
            conn.execute('INSERT INTO comercial.fob_cadastro_historico(registro,versao,lote,conteudo) VALUES (%s,%s,%s,%s)',
                         [saved['registro'],version,lote,Jsonb(plain(saved))])
            changed+=1
        for cost in monthly:
            before=conn.execute('SELECT * FROM comercial.custo_mensal_januaria WHERE competencia=%s FOR UPDATE',
                                [cost['competencia']]).fetchone()
            if before and before['custo_kg']==cost['custo_kg']:continue
            # Reutiliza a tabela mensal e a versão existentes; sem tabela mensal concorrente.
            after=conn.execute('''INSERT INTO comercial.custo_mensal_januaria
              (competencia,custo_kg,criado_por,atualizado_por) VALUES (%s,%s,%s,%s)
              ON CONFLICT (competencia) DO UPDATE SET custo_kg=excluded.custo_kg,
              atualizado_por=excluded.atualizado_por,atualizado_em=clock_timestamp(),
              versao=comercial.custo_mensal_januaria.versao+1 RETURNING *''',
              [cost['competencia'],cost['custo_kg'],actor,actor]).fetchone()
            conn.execute('INSERT INTO comercial.fob_januaria_historico(lote,competencia,antes,depois) VALUES (%s,%s,%s,%s)',
                         [lote,cost['competencia'],Jsonb(plain(before)) if before else None,Jsonb(plain(after))])
            monthly_changed+=1
        summary=dict(cadastros_alterados=changed,competencias_alteradas=monthly_changed,
                     cadastros_lidos=len(rules),competencias_lidas=len(monthly))
        if not changed and not monthly_changed:
            # A transação sem alterações NÃO acrescenta outro lote válido.
            raise Unchanged(summary)
        conn.execute('UPDATE comercial.fob_importacao SET resumo=%s WHERE lote=%s',[Jsonb(summary),lote])
    return dict(lote=lote,**summary)


class Unchanged(Exception):
    def __init__(self,summary):self.summary=summary


def record_rejection(conn,files,message):
    from psycopg.types.json import Jsonb
    with conn.transaction():
        conn.execute('INSERT INTO comercial.fob_importacao(lote,status,arquivos,erros) VALUES (%s,\'REJEITADO\',%s,%s)',
            [str(uuid4()),Jsonb(files),Jsonb([message])])
