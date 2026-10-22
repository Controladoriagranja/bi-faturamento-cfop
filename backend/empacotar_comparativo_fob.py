"""Pacote no padrão da API fornecida: uma pasta bi_generic/comparativo_fob e um registro."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
PACKAGE='bi_generic/comparativo_fob'
REGISTRATION=b'''# Comparativo PM FOB: mesma factory banco() e autenticacao da API existente.
from bi_generic.comparativo_fob.routes import criar_router_comparativo_fob
app.include_router(criar_router_comparativo_fob(banco))
'''


def module_files(snapshot):
    """Prepara só o módulo para mesclar à API mais recente; não gera ZIP/serviço."""
    files={}
    # Mantém o motor já validado. Só a localização do pacote muda.
    for name in ('calculator','reference','repository','snapshot','workbook','freight','master_data','master_repository'):
        files[f'{PACKAGE}/{name}.py']=(ROOT/f'backend/fob/{name}.py').read_bytes()
    for name in ('aggregation','config','service','historical','monthly','feeding','costs_views'):
        source=(ROOT/f'backend/modules/comparativo_fob/{name}.py').read_text(encoding='utf-8')
        source=source.replace('from fob.calculator import ','from .calculator import ')
        source=source.replace('from fob.repository import ','from .repository import ')
        source=source.replace('from fob.snapshot import ','from .snapshot import ')
        source=source.replace('from fob.freight import ','from .freight import ')
        source=source.replace('from fob.master_data import ','from .master_data import ')
        source=source.replace('from fob.master_repository import ','from .master_repository import ')
        source=source.replace("Path(__file__).resolve().parent/'data'/'referencia_excel.json'","Path(__file__).with_name('referencia_excel.json')")
        files[f'{PACKAGE}/{name}.py']=source.encode('utf-8')
    routes=(ROOT/'backend/modules/comparativo_fob/routes.py').read_text(encoding='utf-8')
    routes=routes.split('\ndef build_routes(',1)[0].rstrip()+'''


def criar_router_comparativo_fob(banco):
    from types import SimpleNamespace
    from .service import build_service
    from .monthly import create_monthly_router
    from .costs_views import create_costs_router
    router=APIRouter()
    router.include_router(create_router(build_service(SimpleNamespace(banco=banco))))
    router.include_router(create_monthly_router(banco))
    router.include_router(create_costs_router(banco))
    return router
'''
    files[f'{PACKAGE}/routes.py']=routes.encode('utf-8')
    files[f'{PACKAGE}/__init__.py']=b'"""Comparativo PM FOB integrado a API existente por factory banco()."""\n'
    files[f'{PACKAGE}/referencia_excel.json']=snapshot
    for name,data in files.items():
        if name.endswith('.py'):ast.parse(data.decode('utf-8-sig'),filename=name)
    return files


def build_master_patch(api_reference,snapshot):
    """Delta do módulo já registrado; preserva serviço, autenticação e outros BIs."""
    current=module_files(snapshot);files={};entries=[]
    with ZipFile(api_reference) as baseline:
        service=baseline.read('api_zootecnico/servico_zootecnico.py')
        if b'app.include_router(criar_router_comparativo_fob(banco))' not in service:
            raise ValueError('Base sem factory FOB já registrada; conferir integração antes de empacotar.')
        for name,data in sorted(current.items()):
            previous='api_zootecnico/'+name
            before=baseline.read(previous) if previous in baseline.namelist() else None
            action='PRESERVAR' if before==data else 'ADICIONAR' if before is None else 'SUBSTITUIR'
            delivered=name+'.proposta' if action=='SUBSTITUIR' else name
            entries.append(dict(caminho=name,acao=action,arquivo_no_pacote=delivered if action!='PRESERVAR' else None,
                sha256_base=hashlib.sha256(before).hexdigest() if before is not None else None,
                sha256_entregue=hashlib.sha256(data).hexdigest()))
            if action!='PRESERVAR':files[delivered]=data
    manifest=dict(tipo='delta_modulo_fob_planilhas_mestre',data='2026-10-22',
        base_arquivo=Path(api_reference).name,
        base_sha256=hashlib.sha256(Path(api_reference).read_bytes()).hexdigest(),
        destino='API/api_zootecnico, mesclando somente bi_generic/comparativo_fob/',
        estado='PREPARACAO_PARA_MESCLAGEM_NAO_INSTALAR_DIRETAMENTE',
        servidor_tem_alteracoes_posteriores_confirmadas=True,
        versao_instalada_no_servidor_confirmada=False,
        servico_principal_incluido=False,sql_a_executar=[],dependencias_novas_api=[],
        ativacao='FOB_MASTER_ENABLED=1 somente na atualização futura autorizada e com pendências financeiras conhecidas.',
        cadastro_producao=dict(lote='dc32563f-f0b9-4148-9ae8-a9432b78aece',
            cadastros=4175,competencia_januaria='2026-10-01',custo_kg_januaria='0.6127658079',
            ator_tecnico='900000000006',idempotencia_verificada=True),
        leitor_api=dict(pguser_confirmado_pelo_responsavel='admin',select_e_usage_conferidos=True,grants_executados=False),
        politica_frete='Original válido do PostgreSQL; tipo 1 zero/nulo aguarda planilha; Januária mensal; sem fórmulas históricas de frete.',
        preservar=['servico_zootecnico.py','core/','config.py','comercial_acesso.py',
            'frete_manual_auth.py','bi_generic/router.py','bi_generic/registry.py',
            'Dockerfile','Dockerfile.zootecnico','requirements.txt','.env*'],arquivos=entries)
    readme='''# API Anderson — PREPARAÇÃO PARA MESCLAGEM; NÃO INSTALAR DIRETAMENTE

O responsável confirmou que routes.py/service.py do Anderson foram alterados
depois da base de 21/10 e que as versões atuais não estão disponíveis nesta rodada.
Por isso, os dois arquivos são entregues com sufixo .py.proposta: não substituem
o código instalado. A mesclagem final depende de comparar os dois arquivos atuais.

Destino: pasta da API que já contém servico_zootecnico.py e bi_generic/.
No layout fornecido: API/api_zootecnico/.

1. Obter e preservar os dois arquivos atuais do módulo, routes.py e service.py.
2. Conferir o MANIFESTO: sha256_base identifica a base de 21/10 usada nas propostas.
3. Mesclar a leitura opt-in e o registro do painel nessas versões atuais; os quatro
   novos .py estão completos, mas não ativam a integração sem a mesclagem das rotas.
4. Na futura atualização autorizada, copiar apenas os arquivos consolidados para
   bi_generic/comparativo_fob/, preservando os demais arquivos da API.
5. Preservar o registro atual criar_router_comparativo_fob(banco). Não registrar
   uma segunda factory. Serviço principal, autenticação e Docker não são entregues.

Nenhum SQL é necessário: o 006 já foi aplicado e a primeira importação foi concluída.
O leitor PostgreSQL da API precisa de SELECT nas tabelas fob_importacao,
fob_cadastro, custo_mensal_januaria, faturamento_cfop, vw_faturamento_cfop_filtrado
e vendedor_grupo do esquema comercial, e USAGE nesse esquema. O PGUSER do contêiner
foi confirmado pelo responsável como admin e seus privilégios
SELECT/USAGE foram conferidos em leitura no banco; nenhum GRANT foi necessário.
Não enviar senha nem copiar o .env do robô.

A flag FOB_MASTER_ENABLED mantém padrão 0. Na futura intervenção autorizada,
configurar 1 para usar os cadastros importados; não há ativação ou deploy automático.
O robô Windows, as planilhas e suas credenciais ficam fora do Docker.

Rotas anteriores preservadas: filtros, resumo e detalhes do Comparativo FOB e
cadastro mensal legado. Novos GETs no mesmo prefixo /api/comercial/comparativo-fob:
/custos/status e /custos/pendencias. O painel reutiliza comercial_acesso.authorize
e exige alcance Comercial geral. O Worker deve encaminhar os GETs desse prefixo;
nenhuma mudança de Worker/CENTRAL integra este pacote.

Validação local contra PostgreSQL real: 2.340 itens de 01–04/10; pesos Varejo
203.818 kg, Atacado 931.381 kg, Subprodutos 510.740 kg. NF 806684 conciliada na
bruta; 346 itens de Januária usando 0,6127658079 R$/kg. Comissão e demais despesas
sem componentes pendentes nesse recorte. Subprodutos FOB R$ 383.055,00.

Correção definitiva de escopo: não reproduzir FreteANeRA, FOBxRefaturamento,
ControleFrete ou exigir suas fórmulas para liberar o FOB. Frete original válido
é aplicado diretamente, inclusive quando há redespacho informado. Tipo 1 zero/nulo
aguarda preenchimento em Fretes.xlsx e importação; o manual válido substitui o frete
no escopo NF/item, sem acumular valores. Januária mantém o custo mensal para todos
os tipos. Fretes originais ausentes/negativos, associações ambíguas e cadastros
ausentes continuam pendentes; não converter ausência em zero.

Revalidação real após a correção: 8 itens pendentes, sendo 5 de frete manual e
3 com frete_kg original NULL (NF 657822, unidade 10, tipo 2; NFs 806684 e 806687,
unidade 111, tipo 9). Varejo: 7 pendentes, parcial R$ 1.924.678,54; Atacado: 1
pendente, parcial R$ 7.644.714,91. Esses parciais não são totais FOB concluídos.
Subprodutos: R$ 383.055,00 concluídos. Os 1.839 itens não são mais bloqueados pela
ausência das fórmulas históricas. Diferenças frente ao Excel antigo são comparativas.
No arquivo operacional de 01–22/10 há 146 itens/65 NFs candidatas a preenchimento.

Para validação da futura instalação: conferir modo planilhas_mestre e o lote
dc32563f-f0b9-4148-9ae8-a9432b78aece no resumo; consultar status/detalhes; confirmar
pesos, custo mensal, pendências e acesso autorizado pelo caminho Worker existente.
Publicar o frontend somente em coordenação com essa API. O frontend já preparado
mantém o editor legado até a troca; após aceite, legacyFreightEditor=false deixa
o Portal somente para consulta dos custos, com os preenchimentos pelas planilhas.

Rollback: restaurar os arquivos anteriores do módulo e a flag anterior. Este ZIP
não altera dados. Como outubro de Januária foi gravado na tabela mensal compartilhada,
desativar a flag não remove esse custo do caminho anterior. Qualquer restauração
financeira deve conferir versão atual e histórico do lote, com autorização própria.

O pacote está preparado, sem execução de Docker, deploy, registro de tarefas ou
alteração de permissões. A versão atual do servidor não foi acessada nesta máquina.
'''
    files['LEIA-ME-API-FOB.md']=readme.encode('utf-8')
    manifest['arquivos_pacote']=[dict(caminho=name,sha256=hashlib.sha256(data).hexdigest())
                                for name,data in sorted(files.items())]
    files['MANIFESTO-API-FOB.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    return files,manifest


def build(api_reference,snapshot):
    """Montagem legada completa; não usar para sobrescrever uma API já integrada."""
    files=module_files(snapshot)
    with ZipFile(api_reference) as baseline:
        original=baseline.read('api_zootecnico/servico_zootecnico.py')
        docker=baseline.read('api_zootecnico/Dockerfile.zootecnico')
        assert 'api_zootecnico/bi_generic/__init__.py' in baseline.namelist()
        if 'api_zootecnico/frete_manual_auth.py' not in baseline.namelist():
            raise ValueError('Esta integração exige a API final de frete manual. Não usar a base antiga sem autenticação/writer de fretes.')
        if b'COPY API/api_zootecnico/bi_generic ./bi_generic' not in docker:
            raise ValueError('Dockerfile fornecido nao copia bi_generic como esperado; revisar a base antes de empacotar.')
    if b'comparativo_fob' in original:
        raise ValueError('A base ja contem registro FOB; nao acrescentar registro duplicado automaticamente.')
    nl=b'\r\r\n' if b'\r\r\n' in original else b'\r\n' if b'\r\n' in original else b'\n'
    files['servico_zootecnico.py']=original+nl+nl+REGISTRATION.replace(b'\n',nl)
    for name,data in files.items():
        if name.endswith('.py'):ast.parse(data.decode('utf-8-sig'),filename=name)
    reference=json.loads(snapshot)
    manifest=dict(pacote='api_anderson_comparativo_fob.zip',data='2026-10-20',
        destino='API/api_zootecnico (pasta que ja contem servico_zootecnico.py e bi_generic/)',
        api_referencia_arquivo=Path(api_reference).name,
        api_referencia_sha256=hashlib.sha256(Path(api_reference).read_bytes()).hexdigest(),
        modo_instalacao='Copiar/mesclar uma pasta e substituir servico_zootecnico.py; registro ja aplicado.',
        pastas_novas=[PACKAGE],scripts_pos_copia=[],dockerfile_incluido=False,sql_ddl_necessario=False,
        origem_excel_sha256=reference['sha256'],sha256_catalogo=hashlib.sha256(snapshot).hexdigest(),
        arquivos_compartilhados_modificados=[dict(arquivo='servico_zootecnico.py',
            sha256_base=hashlib.sha256(original).hexdigest(),
            sha256_entregue=hashlib.sha256(files['servico_zootecnico.py']).hexdigest(),
            mudanca='Conteudo original integral preservado; acrescentados comentario e duas linhas de importacao/registro FOB ao final.')],
        nao_substituir=['bi_generic/router.py','bi_generic/registry.py','bi_generic/faturamento_nf/',
            'bi_generic/gpd_fases.py','Dockerfile.zootecnico','core/','config.py','requirements.txt'],
        rotas=['/api/comercial/comparativo-fob/'+operation for operation in ('filtros','resumo','detalhes')])
    readme='''COMPARATIVO PM FOB — UMA PASTA NOVA, NO PADRÃO DA API FORNECIDA

ONDE COLOCAR
Na mesma pasta da sua API que já contém servico_zootecnico.py e bi_generic/.
No contexto do Dockerfile fornecido, essa pasta é API/api_zootecnico.

O QUE COPIAR / SUBSTITUIR
1. Mescle a pasta bi_generic deste ZIP com a bi_generic existente.
   Isso adiciona SOMENTE bi_generic/comparativo_fob/, com todos os arquivos do FOB e do comparativo de preços praticado/FOB, incluindo o catálogo JSON.
   Não apague nem substitua a pasta bi_generic inteira.
2. Substitua servico_zootecnico.py pelo arquivo deste ZIP.
   Base: api_zootecnico(1).zip fornecido. O arquivo original é preservado integralmente; somente o registro do Comparativo PM FOB foi acrescentado ao final.
3. Reconstrua seu Docker como já faz. Não há script Python, integrador, patch, SQL ou cadastro para executar.

ESTRUTURA FINAL
API/api_zootecnico/
  servico_zootecnico.py             SUBSTITUIR
  bi_generic/
    comparativo_fob/               ADICIONAR (única pasta nova)
      __init__.py
      aggregation.py
      calculator.py
      config.py
      historical.py
      reference.py
      referencia_excel.json
      repository.py
      routes.py
      service.py
      snapshot.py
      workbook.py

O Dockerfile fornecido já contém COPY API/api_zootecnico/bi_generic ./bi_generic, que inclui automaticamente a nova pasta. Nenhum Dockerfile é entregue ou alterado. Não copie as pastas fob/ ou modules/ dos pacotes anteriores; este pacote substitui aquela organização.

Não substitui router.py, registry.py, faturamento_nf/, gpd_fases.py, Suprimentos, PCP, autenticação, requisitos ou credenciais. MANIFESTO.json e este LEIA-ME são apenas documentação, não precisam ir para a imagem.

O QUE ATENDE
As três rotas já usadas pelo frontend oficial permanecem:
GET /api/comercial/comparativo-fob/filtros
GET /api/comercial/comparativo-fob/resumo
GET /api/comercial/comparativo-fob/detalhes

Preço praticado, componentes de despesas, preço FOB, valor FOB, médias por família/canal, pendências e auditoria por item são os já implementados. Nenhuma regra ou valor de referência foi recalculado para este empacotamento. O catálogo do pacote anterior foi mantido byte a byte. O relatório faturamento-nf continua com o código fornecido na sua API.

HISTÓRICO E LIMITES
Consultas desde 01/01/2026 até a data atual, com agregação e paginação no PostgreSQL. Fora de 01–04/10/2026, peso e preço praticado vêm da view existente; FOB e despesas ficam pendentes, sem aplicar cadastros de outubro a outros meses. O canal vem do cadastro atual comercial.vendedor_grupo.canal_venda (sem vigência histórica); família SUBPRODUTOS é separada. Canais adicionais permanecem visíveis. Períodos mistos também usam o modo histórico, sem comparação com o Excel. As inclusões/exclusões históricas são as da view, sem extrapolar exceções pontuais do Excel. Filtros iniciais de famílias/unidades usam o catálogo de referência; selecione Todos para incluir outras existentes no histórico.
Cadastros comprovados somente para 01–04/10/2026. Fretes manuais não confirmados continuam pendentes; a NF 806684 pode aparecer provisória até conciliação. Não há CRUD, SQL DDL ou gravação no PostgreSQL. Se o módulo já estiver instalado, atualize todos os arquivos de bi_generic/comparativo_fob; o registro em servico_zootecnico.py continua o mesmo, não duplique.

VALIDAÇÃO
Verificações pequenas de sintaxe, imports internos, integridade do pacote e cálculos puros. Nenhuma API, carga, job, consulta ao banco ou deploy foi executado nesta máquina. O acesso pelo endereço público depende do Worker encaminhar/autorizar as rotas acima; o código do Worker não faz parte do ZIP fornecido e não foi alterado.
'''
    files['LEIA-ME-INTEGRACAO.txt']=readme.encode('utf-8')
    manifest['arquivos']=[dict(caminho=name,acao='SUBSTITUIR' if name=='servico_zootecnico.py' else 'DOCUMENTACAO' if '/' not in name else 'ADICIONAR / ATUALIZAR SOMENTE ESTE MODULO',
        sha256=hashlib.sha256(data).hexdigest()) for name,data in sorted(files.items())]
    files['MANIFESTO.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    return files,manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sources=parser.add_mutually_exclusive_group()
    sources.add_argument('--excel',type=Path)
    sources.add_argument('--catalogo-zip',type=Path)
    parser.add_argument('--api-referencia',type=Path,default=Path.home()/'Downloads/api_zootecnico(1).zip')
    parser.add_argument('--saida',type=Path,default=ROOT/'artifacts/api_anderson_comparativo_fob.zip')
    args=parser.parse_args()
    if args.excel:
        from fob.reference import WorkbookCatalog
        from fob.snapshot import export_snapshot
        snapshot=json.dumps(export_snapshot(WorkbookCatalog(args.excel)),ensure_ascii=False,default=str,separators=(',',':')).encode('utf-8')
    else:
        with ZipFile(args.catalogo_zip or ROOT/'artifacts/api_anderson_comparativo_fob.zip') as previous:
            member=f'{PACKAGE}/referencia_excel.json'
            if member not in previous.namelist():member='modules/comparativo_fob/data/referencia_excel.json'
            snapshot=previous.read(member)
    files,manifest=build(args.api_referencia,snapshot)
    args.saida.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(args.saida,'w',ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):archive.writestr(name,data)
    with ZipFile(args.saida) as archive:
        assert archive.testzip() is None
        for row in manifest['arquivos']:assert hashlib.sha256(archive.read(row['caminho'])).hexdigest()==row['sha256']
    print(json.dumps(dict(zip=str(args.saida),arquivos=len(files),bytes=args.saida.stat().st_size,
        pasta_nova=PACKAGE,substituir=['servico_zootecnico.py'],sha256_catalogo=manifest['sha256_catalogo']),ensure_ascii=False))


if __name__=='__main__':main()
