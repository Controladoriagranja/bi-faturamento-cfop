"""Conferência e plano de importação: todas as instruções SQL são SELECT."""
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

from fob.master_data import digest,validate_rules
from fob.master_repository import FIELDS
from .importador import plain,same,validate_freight

TABLES={
 'faturamento_cfop':tuple(FIELDS.split(',')),
 'vw_faturamento_cfop_filtrado':tuple(FIELDS.split(',')),
 'fob_importacao':('lote','executado_em','status','arquivos','resumo','erros'),
 'fob_cadastro':('registro','tipo','inicio','fim','dimensoes','modalidade','valor','parametros','origem','ativo','versao','lote','atualizado_em'),
 'fob_cadastro_historico':('registro','versao','lote','conteudo','registrado_em'),
 'fob_januaria_historico':('lote','competencia','antes','depois'),
 'custo_mensal_januaria':('competencia','custo_kg','versao','criado_por','criado_em','atualizado_por','atualizado_em'),
}
INSERT_COLUMNS={
 'fob_importacao':('lote','status','arquivos','erros'),
 'fob_cadastro':('registro','tipo','inicio','fim','dimensoes','modalidade','valor','parametros','origem','ativo','versao','lote'),
 'fob_cadastro_historico':('registro','versao','lote','conteudo'),
 'fob_januaria_historico':('lote','competencia','antes','depois'),
 'custo_mensal_januaria':('competencia','custo_kg','criado_por','atualizado_por'),
}
UPDATE_COLUMNS={
 'fob_importacao':('resumo',),
 'fob_cadastro':('tipo','inicio','fim','dimensoes','modalidade','valor','parametros','origem','ativo','versao','lote','atualizado_em'),
 'custo_mensal_januaria':('custo_kg','versao','atualizado_por','atualizado_em'),
}


def inspect_database(conn):
    identity=conn.execute('''SELECT current_database() banco,current_user usuario,
      current_setting('transaction_read_only') somente_leitura,
      inet_server_addr()::text servidor,inet_server_port() porta,
      r.rolsuper administrador,r.rolcreaterole cria_papeis,r.rolcreatedb cria_bancos
      FROM pg_roles r WHERE r.rolname=current_user''').fetchone()
    if identity['banco']!='bi_granja' or identity['somente_leitura']!='on':
        raise ValueError('Conferência exige bi_granja e conexão somente leitura.')
    tables=[];permissions=[]
    for table,columns in TABLES.items():
        name='comercial.'+table
        found=conn.execute('SELECT to_regclass(%s)::text objeto',[name]).fetchone()['objeto']
        if not found:
            tables.append(dict(tabela=name,existe=False,colunas_ausentes=list(columns)));continue
        actual=conn.execute('''SELECT a.attname coluna FROM pg_attribute a
          WHERE a.attrelid=to_regclass(%s) AND a.attnum>0 AND NOT a.attisdropped''',[name]).fetchall()
        existing={r['coluna'] for r in actual};missing=sorted(set(columns)-existing)
        can_read=conn.execute('SELECT has_table_privilege(current_user,%s,\'SELECT\') permitido',[name]).fetchone()['permitido']
        tables.append(dict(tabela=name,existe=True,colunas_ausentes=missing,leitura=can_read))
        for action,mapping in [('INSERT',INSERT_COLUMNS),('UPDATE',UPDATE_COLUMNS)]:
            for column in mapping.get(table,()):
                permissions.append((name,column,action))
    if permissions:
        values=','.join(['(%s::text,%s::text,%s::text)']*len(permissions))
        rights=conn.execute('''WITH pedidos(tabela,coluna,operacao) AS (VALUES '''+values+''')
          SELECT tabela,coluna,operacao,CASE WHEN EXISTS(
            SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass(tabela)
             AND a.attname=coluna AND a.attnum>0 AND NOT a.attisdropped)
          THEN has_column_privilege(current_user,tabela,coluna,operacao) ELSE false END permitido
          FROM pedidos ORDER BY tabela,operacao,coluna''',[v for row in permissions for v in row]).fetchall()
    else:rights=[]
    return dict(identidade=identity,tabelas=tables,privilegios_escrita=rights,
                escrita_habilitada=False,conta_administrativa_nao_recomendada_para_operacao=bool(identity['administrador']))


def read_state(conn,monthly):
    current=conn.execute('SELECT * FROM comercial.fob_cadastro ORDER BY registro LIMIT 100001').fetchall()
    if len(current)>100000:raise ValueError('Prévia excede 100.000 cadastros; nenhuma escrita foi realizada.')
    old_months=[]
    for cost in monthly:
        row=conn.execute('SELECT * FROM comercial.custo_mensal_januaria WHERE competencia=%s',[cost['competencia']]).fetchone()
        if row:old_months.append(row)
    return dict(cadastros=current,januaria=old_months)


def fingerprint(state):
    return digest(plain(dict(cadastros=sorted(state['cadastros'],key=lambda r:r['registro']),
                            januaria=sorted(state['januaria'],key=lambda r:str(r['competencia'])))))


def build_plan(conn,rules,monthly,files,actor):
    state=read_state(conn,monthly);indexed={r['registro']:r for r in state['cadastros']}
    validate_rules(list({**indexed,**{r['registro']:r for r in rules}}.values()))
    validate_freight(conn,rules)
    new=[r for r in rules if r['registro'] not in indexed]
    changed=[r for r in rules if r['registro'] in indexed and not same(indexed[r['registro']],r)]
    old_months={str(r['competencia']):r for r in state['januaria']};monthly_changes=[]
    for cost in monthly:
        before=old_months.get(str(cost['competencia']))
        if before is None or before['custo_kg']!=cost['custo_kg']:
            monthly_changes.append(dict(competencia=str(cost['competencia']),
                antes=before['custo_kg'] if before else None,depois=cost['custo_kg'],versao_antes=before['versao'] if before else None))
    legacy=conn.execute('SELECT to_regclass(\'comercial.frete_manual_nf\') IS NOT NULL existe').fetchone()['existe']
    has_legacy=None
    if legacy:
        has_legacy=conn.execute('SELECT EXISTS(SELECT 1 FROM comercial.frete_manual_nf LIMIT 1) existe').fetchone()['existe']
    summary=dict(cadastros_lidos=len(rules),por_categoria=dict(Counter(r['tipo'] for r in rules)),
        novos=len(new),alterados=len(changed),inalterados=len(rules)-len(new)-len(changed),
        competencias_lidas=len(monthly),competencias_a_alterar=monthly_changes,
        historicos_cadastro_novos=len(new)+len(changed),fretes_legados_presentes=has_legacy,
        tabela_frete_manual_preservada=True,faturamento_preservado=True,
        ator_configurado=bool(actor.isdecimal() and int(actor)>0),
        tabelas_destino=['comercial.'+t for t in INSERT_COLUMNS],
        autorizacao_producao='PENDENTE; este plano não executa nem autoriza a escrita.')
    from .historico import provisional_coverage
    summary['cobertura_provisoria']=provisional_coverage({**indexed,**{r['registro']:r for r in rules}}.values())
    return dict(versao=1,gerado_em=datetime.now(timezone.utc).isoformat(),arquivos=files,
                estado_antes=plain(state),estado_sha256=fingerprint(state),resumo=plain(summary))


def save_plan(plan,contents,directory=None):
    # Fora da raiz publicada do frontend. Não salvar salários em assets/ ou docs/.
    root=Path(directory or os.environ.get('FOB_ESTADO_DIR') or
              Path(os.environ.get('LOCALAPPDATA',Path.home()))/'GranjaBrasilia'/'FOB')
    folder=root/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+str(uuid4())[:8])
    folder.mkdir(parents=True,exist_ok=False)
    for name,content in contents.items():
        target=folder/(name+'.bak');target.write_bytes(content)
        if sha256(target.read_bytes()).hexdigest()!=plan['arquivos'][name]['sha256']:
            raise ValueError('Backup das planilhas não conferiu; nenhuma escrita no banco foi realizada.')
    target=folder/'plano-importacao.json'
    target.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    return target
