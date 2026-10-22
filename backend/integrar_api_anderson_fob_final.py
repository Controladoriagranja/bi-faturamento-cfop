"""Integração conservadora sobre o ZIP oficial, sem executar a API ou o banco."""
import argparse
import ast
import hashlib
import json
from pathlib import Path,PurePosixPath
from zipfile import ZipFile,ZIP_DEFLATED

from empacotar_comparativo_fob import module_files

ROOT=Path(__file__).resolve().parents[1]
PREFIX='api_zootecnico/'
MODULE=PREFIX+'bi_generic/comparativo_fob/'
NEW=('master_data.py','master_repository.py','feeding.py','costs_views.py')
MODIFIED=(MODULE+'service.py',MODULE+'routes.py')


def digest(data):return hashlib.sha256(data).hexdigest()


def source_files(path):
    with ZipFile(path) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP de origem com CRC inválido.')
        names=archive.namelist()
        if len(names)!=len(set(names)):raise ValueError('ZIP com caminhos duplicados.')
        for name in names:
            part=PurePosixPath(name)
            if not name.startswith(PREFIX) or part.is_absolute() or '..' in part.parts or '\\' in name:
                raise ValueError('Caminho inválido no ZIP oficial.')
        return {name:archive.read(name) for name in names if not name.endswith('/')},archive.infolist()


def insert_once(data,anchor,extra,before=False):
    if data.count(anchor)!=1:raise ValueError('Ponto de mesclagem não é único; preservar e revisar a fonte oficial.')
    return data.replace(anchor,extra+anchor if before else anchor+extra,1)


def merge(original):
    files=dict(original)
    snapshot=original[MODULE+'referencia_excel.json']
    prepared=module_files(snapshot)
    # Os arquivos existentes são a autoridade. Divergências inesperadas exigem
    # revisão; não substituir por uma cópia do projeto local.
    for rel,data in prepared.items():
        name=PREFIX+rel
        if name in original and name not in MODIFIED and original[name]!=data:
            raise ValueError('Arquivo FOB existente diverge e requer mesclagem explícita: '+name)
    for name in NEW:
        target=MODULE+name
        if target in original:raise ValueError('Arquivo novo já existe na API oficial: '+target)
        files[target]=prepared['bi_generic/comparativo_fob/'+name]
    service=MODULE+'service.py'
    addition=(b'        from .feeding import enabled,execute_master\n'
              b'        if enabled():\n'
              b'            return execute_master(self,operation,start,end,choices,search,single,catalog)\n')
    anchor=b'        if start.isoformat()<catalog.period[0] or end.isoformat()>catalog.period[1]:\n'
    files[service]=insert_once(original[service],anchor,addition,before=True)
    routes=MODULE+'routes.py'
    files[routes]=insert_once(original[routes],b'    from .monthly import create_monthly_router\n',
        b'    from .costs_views import create_costs_router\n')
    files[routes]=insert_once(files[routes],b'    router.include_router(create_monthly_router(banco))\n',
        b'    router.include_router(create_costs_router(banco))\n')
    # Prova de que somente as cinco linhas necessárias foram acrescentadas.
    assert files[service].replace(addition,b'',1)==original[service]
    assert files[routes].replace(b'    from .costs_views import create_costs_router\n',b'',1).replace(
        b'    router.include_router(create_costs_router(banco))\n',b'',1)==original[routes]
    for name in files:
        if name.endswith('.py'):ast.parse(files[name].decode('utf-8-sig'),filename=name)
    return files


def structural_report(original,final):
    removed=sorted(set(original)-set(final))
    changed=sorted(name for name in original if original[name]!=final.get(name))
    added=sorted(set(final)-set(original))
    if removed or changed!=sorted(MODIFIED):raise ValueError('A estrutura não corresponde ao escopo aprovado.')
    if any(name in original and name not in MODIFIED and original[name]!=data for name,data in final.items()):
        raise ValueError('Arquivo externo ao módulo FOB foi modificado.')
    forbidden=[name for name in final if PurePosixPath(name).name.startswith('.env') and PurePosixPath(name).name!='.env.example']
    forbidden += [name for name in final if name.endswith(('.pem','.key','.pfx','.xlsx','.sqlite','.db'))]
    if forbidden:raise ValueError('Arquivo local sensível no pacote; revisar sem divulgar conteúdo.')
    example=final.get(PREFIX+'.env.example',b'').decode('utf-8-sig')
    for line in example.splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1)
            if key.strip() in ('PGPASSWORD','FRETE_WRITE_DATABASE_URL') and value.strip():
                raise ValueError('O exemplo contém credencial/DSN não vazio; revisar antes de entregar.')
    return dict(arquivos_originais=len(original),originais_preservados=len(original)-len(changed),
        originais_removidos=removed,originais_modificados=changed,novos=added,
        hashes_originais=[dict(arquivo=name,sha256_base=digest(data),sha256_final=digest(final[name]),
            estado='MODIFICADO' if name in changed else 'IDENTICO') for name,data in sorted(original.items())])


def readme(report):
    return '''# API Anderson + FOB — entrega final de 22/10/2026

Base oficial exclusiva: api_zootecnico(4).zip, obtida do ambiente atual em 22/10.
O pacote contém a API completa. Foram preservados todos os 103 arquivos originais:
101 idênticos e dois com inclusões pontuais. Não foram removidos backups, módulos
legados, documentos, exemplos vazios ou caches que já pertenciam ao ZIP oficial.

## Arquivos da integração

Novos em bi_generic/comparativo_fob/:
master_data.py, master_repository.py, feeding.py, costs_views.py.

Modificados no mesmo módulo:
service.py: três linhas delegam para a nova alimentação quando a flag é 1.
routes.py: duas linhas registram os GETs de custos na factory FOB existente.
Todas as demais linhas desses arquivos foram preservadas. Manifesto registra hashes
de cada original. servico_zootecnico.py, portal_router.py, módulos compartilhados,
modules/comparativo_fob/, fob/, Dockerfiles, requisitos e autenticação são idênticos.

## Atualização futura pelo Anderson — não executada nesta entrega

1. Guardar cópia da API instalada e das variáveis/configuração atuais. A base oficial
   api_zootecnico(4).zip é o backup de código anterior, sem credenciais.
2. Na pasta instalada api_zootecnico (onde está servico_zootecnico.py), copiar os quatro arquivos novos e
   substituir SOMENTE bi_generic/comparativo_fob/service.py e routes.py. O ZIP também
   contém o restante da API oficial completo para conferência; não é necessário
   substituir os arquivos idênticos. Não apagar a pasta bi_generic existente.
3. Manter o registro existente criar_router_comparativo_fob(banco). Nenhum outro
   registro, patch, script, instalação de dependência ou SQL deve ser executado.
4. Preservar todas as variáveis de ambiente existentes. Preparar FOB_MASTER_ENABLED=0
   no serviço atual e reconstruir o Docker pelo procedimento habitual. Após validar
   a instalação, ativar de forma controlada FOB_MASTER_ENABLED=1 pelo mecanismo de
   configuração/recriação usado no ambiente. Os detalhes do Compose não vieram no
   ZIP; não foi inventado nome de serviço, caminho de .env ou comando de build.
5. Publicar o frontend somente coordenado com a API correspondente. Depois do aceite,
   legacyFreightEditor=false mantém o Portal apenas para consulta de custos, com os
   preenchimentos feitos nas planilhas. Os endpoints de edição legados continuam.

## Ambiente

Única opção nova: FOB_MASTER_ENABLED. Ausente ou 0 conserva o cálculo anterior;
1 utiliza comercial.fob_cadastro, fob_importacao e custo_mensal_januaria. Não foi
ativada automaticamente na entrega. Manter PGHOST, PGPORT, PGDATABASE, PGUSER,
PGPASSWORD e variáveis atuais do ambiente. FRETE_WRITE_DATABASE_URL continua apenas
para os endpoints legados; os novos GETs não escrevem. A API não precisa das
credenciais/configurações do robô nem de openpyxl. Nenhuma credencial real ou DSN
configurada é entregue; o exemplo oficial mantém apenas o modelo comentado.

O PGUSER informado é admin. SELECT nas origens/tabelas e USAGE no esquema já foram
conferidos em leitura, sem GRANT. Não foram alterados privilégios ou contas.
SQL 006 e a primeira importação já foram concluídos: NÃO repetir. Lote existente:
dc32563f-f0b9-4148-9ae8-a9432b78aece, 4.175 cadastros, históricos e outubro/2026 de
Januária a 0,6127658079 R$/kg, ator técnico 900000000006. Idempotência confirmada.

## Contratos e regras

Preservados: GET /api/comercial/comparativo-fob/filtros, /resumo e /detalhes;
GET/PUT /api/comercial-html/fretes-manuais e /fretes-manuais/custos-januaria;
todas as rotas dos outros BIs.
Acrescentados SOMENTE GET /api/comercial/comparativo-fob/custos/status e
GET /api/comercial/comparativo-fob/custos/pendencias.
As despesas/comissões faltantes são identificadas nos componentes do resumo e
nos detalhes existentes. O painel recebe situação do lote, cadastros, competências,
pendências e origens; nenhum campo salarial é retornado.

Frete original válido do PostgreSQL é utilizado diretamente. Tipo 1 zero/NULL
consulta o preenchimento importado; o manual válido substitui no escopo NF/item,
sem somar fretes. Januária mantém custo mensal para todos os tipos. Não se exige
FreteANeRA, ControleFrete ou FOBxRefaturamento. Ausência não significa zero;
identificação ambígua/assinatura inconsistente e cadastro ausente seguem pendentes.

Na referência de 01–04/10: 2.340 itens, Varejo 203.818 kg, Atacado 931.381 kg,
Subprodutos 510.740 kg. Permanecem 8 itens pendentes: 5 manuais e 3 com frete NULL
(NF 657822/unidade 10/tipo 2, NFs 806684 e 806687/unidade 111/tipo 9).
Subprodutos FOB R$ 383.055,00. Varejo e Atacado permanecem em aberto, sem forçar a
igualdade com o Excel histórico. Januária validada nos 346 itens do recorte.

## Conferência após a instalação

Usar o caminho autenticado já existente no Portal/Worker, preservando Basic técnico
e X-Portal-Authorization. Não enviar senha/token em URL. Conferir primeiro filtros,
resumo e detalhes com a flag 0. Os GETs novos retornam 503 explicativo nesse modo.
Com a flag 1, consultar resumo com data_inicio=2026-10-01&data_fim=2026-10-04:
contexto.modo=planilhas_mestre e lote acima. Conferir os três pesos e oito pendências.
Detalhes com unidade=102 devem exibir frete_kg 0.6127658079. Consultar custos/status
e custos/pendencias no mesmo período, com alcance Comercial geral autenticado.
Os GETs do painel exigem a identidade CENTRAL existente, sem nova permissão de edição.
O Worker deve encaminhar esses GETs; Worker/CENTRAL não foram alterados. Nenhum PUT
é necessário para homologar esta entrega. Rotas reais de outros BIs devem continuar
respondendo como antes, usando seus filtros usuais.

## Testes locais

O manifesto inclui o relatório efetivamente executado: imports/inicialização das
aplicações oficial e integrada, comparação de rotas, hashes de todos os originais,
flags 0/1, filtros/resumo/detalhes, painel e regras de frete/Januária. Integrações
externas de autenticação usam respostas controladas nos testes locais; não se afirma
homologação do Worker/CENTRAL ou do Docker remoto. Cálculo real usa somente SELECTs
com a conexão READ ONLY, sem cargas, extratores, importação ou SQL de escrita.
As 71 rotas originais foram preservadas; a integrada possui 73, sem duplicidades.
Foram aprovadas 54 verificações ASGI (12 da base, 42 da integrada) e 23 com o banco
real. Os payloads de filtros/resumo/detalhes e mensal com flag 0 são idênticos aos
da base no cenário controlado. Nenhum código dos demais BIs foi alterado.
O MANIFEST_SHA256.json preexistente é preservado como documento da base anterior;
para os arquivos desta entrega, usar MANIFESTO_FOB_FINAL.json, com hashes e testes.

## Rollback

Definir FOB_MASTER_ENABLED=0 restaura o caminho anterior, sem apagar os novos dados.
Se também for necessário reverter código, restaurar SOMENTE os dois arquivos do
módulo a partir de api_zootecnico(4).zip, preservando alterações posteriores dos
outros BIs. Os quatro arquivos novos podem permanecer inativos. Não remover tabelas,
histórico ou cadastros. A competência mensal de Januária é compartilhada e já estava
gravada antes desta entrega: a flag não a apaga. Qualquer reversão financeira é
uma operação separada, autorizada e conferida por versão/histórico.
Não foi executado Docker, deploy, commit, push ou instalação no Anderson.
'''.encode('utf-8')


def payload(source,test_report=None):
    original,infos=source_files(source);files=merge(original)
    report=structural_report(original,files)
    files[PREFIX+'LEIA-ME_FOB_FINAL.md']=readme(report)
    manifest=dict(base_arquivo=Path(source).name,base_sha256=digest(Path(source).read_bytes()),
        data='2026-10-22',**report,flag_padrao='0',dependencias_novas=[],sql_a_executar=[],
        conta_ou_permissoes_alteradas=False,rotas_novas=[
            'GET /api/comercial/comparativo-fob/custos/status',
            'GET /api/comercial/comparativo-fob/custos/pendencias'],
        papeis_dos_pacotes=dict(ativo='bi_generic/comparativo_fob pela factory já registrada',
            legado='modules/comparativo_fob e fob preservados; não registrar novamente'),
        testes=test_report or dict(estado='PREPARACAO_LOCAL_NAO_ENTREGAR'),
        arquivos_novos_runtime=[MODULE+n for n in NEW],
        arquivos_pacote=[dict(arquivo=name,sha256=digest(data)) for name,data in sorted(files.items())])
    files[PREFIX+'MANIFESTO_FOB_FINAL.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    return files,manifest,infos


def stage(source,directory):
    original,_=source_files(source);files,manifest,_=payload(source)
    for label,bundle in [('base',original),('integrada',files)]:
        folder=Path(directory)/label
        folder.mkdir(parents=True,exist_ok=True)
        for name,data in bundle.items():
            path=folder/PurePosixPath(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return manifest


def write_final(source,target,test_report):
    if not test_report.get('ok'):raise ValueError('Relatório de testes aprovados obrigatório para o ZIP final.')
    if test_report.get('origem_sha256')!=digest(Path(source).read_bytes()):
        raise ValueError('O relatório não corresponde ao ZIP oficial informado.')
    tested=merge(source_files(source)[0])
    if test_report.get('codigo_testado_sha256')!={name:digest(data) for name,data in tested.items()}:
        raise ValueError('Código alterado após a validação; conferir antes de empacotar.')
    files,manifest,infos=payload(source,test_report)
    Path(target).parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=9) as archive:
        # Retém inclusive diretórios e atributos dos originais. Não acrescenta caches.
        for info in infos:archive.writestr(info,files[info.filename] if not info.is_dir() else b'')
        for name in sorted(set(files)-{i.filename for i in infos}):archive.writestr(name,files[name])
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        actual={n:archive.read(n) for n in archive.namelist() if not n.endswith('/')}
        structural_report(source_files(source)[0],actual)
        assert actual==files
        for row in manifest['arquivos_pacote']:assert digest(actual[row['arquivo']])==row['sha256']
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-oficial',type=Path,required=True)
    parser.add_argument('--preparar-testes',type=Path)
    parser.add_argument('--relatorio-testes',type=Path)
    parser.add_argument('--saida',type=Path,default=ROOT/'artifacts/api_zootecnico_ANDERSON_FOB_FINAL.zip')
    args=parser.parse_args()
    if args.preparar_testes:
        manifest=stage(args.api_oficial,args.preparar_testes)
        print(json.dumps(dict(ok=True,modo='preparacao_testes',originais=manifest['arquivos_originais'],
            preservados=manifest['originais_preservados'],modificados=manifest['originais_modificados'],
            novos=manifest['novos'],removidos=manifest['originais_removidos']),ensure_ascii=False));return
    if not args.relatorio_testes:parser.error('Informe o relatório de testes locais aprovados.')
    manifest=write_final(args.api_oficial,args.saida,json.loads(args.relatorio_testes.read_text(encoding='utf-8')))
    print(json.dumps(dict(ok=True,zip=str(args.saida),sha256=digest(args.saida.read_bytes()),
        originais=manifest['arquivos_originais'],preservados=manifest['originais_preservados'],
        removidos=manifest['originais_removidos'],modificados=manifest['originais_modificados'],
        novos_runtime=manifest['arquivos_novos_runtime']),ensure_ascii=False))


if __name__=='__main__':main()
