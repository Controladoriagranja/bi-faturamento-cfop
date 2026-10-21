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
    for name in ('calculator','reference','repository','snapshot','workbook','freight'):
        files[f'{PACKAGE}/{name}.py']=(ROOT/f'backend/fob/{name}.py').read_bytes()
    for name in ('aggregation','config','service','historical','monthly'):
        source=(ROOT/f'backend/modules/comparativo_fob/{name}.py').read_text(encoding='utf-8')
        source=source.replace('from fob.calculator import ','from .calculator import ')
        source=source.replace('from fob.repository import ','from .repository import ')
        source=source.replace('from fob.snapshot import ','from .snapshot import ')
        source=source.replace('from fob.freight import ','from .freight import ')
        source=source.replace("Path(__file__).resolve().parent/'data'/'referencia_excel.json'","Path(__file__).with_name('referencia_excel.json')")
        files[f'{PACKAGE}/{name}.py']=source.encode('utf-8')
    routes=(ROOT/'backend/modules/comparativo_fob/routes.py').read_text(encoding='utf-8')
    routes=routes.split('\ndef build_routes(',1)[0].rstrip()+'''


def criar_router_comparativo_fob(banco):
    from types import SimpleNamespace
    from .service import build_service
    from .monthly import create_monthly_router
    router=APIRouter()
    router.include_router(create_router(build_service(SimpleNamespace(banco=banco))))
    router.include_router(create_monthly_router(banco))
    return router
'''
    files[f'{PACKAGE}/routes.py']=routes.encode('utf-8')
    files[f'{PACKAGE}/__init__.py']=b'"""Comparativo PM FOB integrado a API existente por factory banco()."""\n'
    files[f'{PACKAGE}/referencia_excel.json']=snapshot
    for name,data in files.items():
        if name.endswith('.py'):ast.parse(data.decode('utf-8-sig'),filename=name)
    return files


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
