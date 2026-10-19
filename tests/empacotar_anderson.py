"""Combina a API enviada, a atualização GPD e o detalhamento CFOP em uma entrega."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def extract(source, target, prefix=''):
    with zipfile.ZipFile(source) as archive:
        for entry in archive.infolist():
            if entry.is_dir(): continue
            name = entry.filename
            if prefix:
                if not name.startswith(prefix): raise ValueError('Raiz inesperada: '+name)
                name = name[len(prefix):]
            rel = Path(name)
            if '__pycache__' in rel.parts or rel.suffix in ('.pyc', '.bak'): continue
            destination = (target / rel).resolve()
            if not destination.is_relative_to(target.resolve()): raise ValueError('Caminho inválido')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(entry))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', type=Path, required=True)
    parser.add_argument('--atualizacao', type=Path, required=True)
    parser.add_argument('--saida', type=Path, required=True)
    args = parser.parse_args()
    delivery = args.saida.resolve()
    delivery.mkdir(parents=True, exist_ok=False)
    api = delivery / 'api_zootecnico'
    extract(args.api, api, 'api_zootecnico/')
    extract(args.atualizacao, api)
    # O ZIP incremental referencia suporte a product e efficiency_index que
    # não acompanha os três arquivos. Acrescenta somente esse suporte faltante.
    helpers_path = api / 'bi_generic/sql_utils.py'
    helpers = helpers_path.read_text(encoding='utf-8')
    before = '    numerator, denominator = formula_components(component, number)'
    after = """    if 'product' in component:
        return sql.SQL(' * ').join(sql.SQL('({})').format(formula_part_expr(part,number)) for part in component['product'])
    numerator, denominator = formula_components(component, number)"""
    assert helpers.count(before) == 1
    helpers = helpers.replace(before, after, 1)
    before = 'def metrica_expr(metrica):'
    after = '''def efficiency_index_expr(gpd, mortality, feed_conversion):
    """IEP sobre resultados consolidados; GPD em g/dia, mortalidade em %."""
    return sql.SQL('(({gpd}) / 1000) * (100 - ({mortality})) / NULLIF(({ca}),0) * 100').format(
        gpd=gpd,mortality=mortality,ca=feed_conversion)


def metrica_expr(metrica):
    if metrica['aggregation'] == 'efficiency_index':
        components = metrica['components']
        return efficiency_index_expr(*(metrica_expr(components[key]) for key in ('gmd','mortalidade','ca')))'''
    assert helpers.count(before) == 1
    helpers_path.write_text(helpers.replace(before, after, 1), encoding='utf-8')
    service_path = api / 'bi_generic/faturamento_nf/service.py'
    service = service_path.read_text(encoding='utf-8')
    before = "def filtros_request(request):\n    permitidos={'data_inicio','data_fim','unidade'}"
    after = "def filtros_request(request, extras=()):\n    permitidos={'data_inicio','data_fim','unidade',*extras}"
    assert service.count(before) == 1
    service = service.replace(before, after, 1)
    before = "        if operation not in ('filtros','resumo'):raise HTTPException(404,'Detalhes não são necessários para este relatório.')"
    after = """        if operation == 'detalhes':
            from .details import detalhes
            return detalhes(self.context, request)
        if operation not in ('filtros','resumo'):raise HTTPException(404,'Operação não disponível.')"""
    assert service.count(before) == 1
    service_path.write_text(service.replace(before, after, 1), encoding='utf-8')
    shutil.copyfile(ROOT / 'backend/modules/faturamento_nf/details.py', api / 'bi_generic/faturamento_nf/details.py')

    frontend = delivery / 'frontend_faturamento_cfop'
    frontend.mkdir()
    shutil.copyfile(ROOT / 'index.html', frontend / 'index.html')
    shutil.copytree(ROOT / 'assets', frontend / 'assets')

    # Mesma regressão, agora importando a estrutura real enviada pelo Anderson.
    test = (ROOT / 'tests/validar_detalhes.py').read_text(encoding='utf-8')
    start = test.index('sys.path[:0]')
    end = test.index('sys.dont_write_bytecode', start)
    test = test[:start] + "sys.path[:0] = [os.environ.get('CFOP_TEST_DEPS', str(ROOT / '.dev_deps')), str(ROOT)]\n" + test[end:]
    test = test.replace("import modules\nmodules.__path__.insert(0, str(ROOT / 'backend' / 'modules'))\n", '')
    test = test.replace('from modules.faturamento_nf.', 'from bi_generic.faturamento_nf.')
    test = test.replace('from bi_generic.faturamento_nf.service import build_service', 'from bi_generic.faturamento_nf.service import build_service\nfrom bi_generic.router import criar_router')
    start = test.index("    @app.get('/api/bi/faturamento-nf/{operation}')")
    end = test.index('    return app, conn', start)
    test = test[:start] + "    app.include_router(criar_router(banco))\n    app.mount('/', StaticFiles(directory=ROOT.parent / 'frontend_faturamento_cfop', html=True), name='frontend')\n" + test[end:]
    (api / 'tests/validar_detalhamento_local.py').write_text(test, encoding='utf-8')

    changed = []
    with zipfile.ZipFile(args.api) as original:
        old = {entry.filename.removeprefix('api_zootecnico/'): original.read(entry)
               for entry in original.infolist() if not entry.is_dir() and '__pycache__' not in entry.filename and not entry.filename.endswith(('.pyc','.bak'))}
    for path in sorted(api.rglob('*')):
        if path.is_file():
            relative = path.relative_to(api).as_posix()
            if relative not in old or path.read_bytes() != old[relative]: changed.append(relative)
            if path.suffix == '.py': ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    # A atualização GPD é preservada byte a byte, sem mescla destrutiva.
    with zipfile.ZipFile(args.atualizacao) as update:
        for entry in update.infolist():
            if not entry.is_dir(): assert (api / entry.filename).read_bytes() == update.read(entry)
    assert (api / 'bi_generic/faturamento_nf/config.py').read_bytes() == old['bi_generic/faturamento_nf/config.py']
    assert (api / 'requirements.txt').read_bytes() == old['requirements.txt']

    (delivery / 'LEIA-ME-PRIMEIRO.txt').write_text('''ATUALIZAÇÃO ANDERSON — 19/10/2026

1. Faça uma cópia da pasta api_zootecnico atual para poder voltar à versão anterior.
2. Copie o conteúdo da pasta api_zootecnico deste ZIP sobre a pasta api_zootecnico existente, substituindo os arquivos. Mantenha arquivos locais adicionais e configurações do ambiente.
   Evite criar api_zootecnico dentro de outra api_zootecnico.
3. A atualização de GPD por fase já está incorporada. Não reaplique o ZIP antigo depois desta entrega.
4. Recrie/reinicie a API pelo procedimento que já é usado. O Dockerfile.zootecnico copia os arquivos durante a construção: nesse caso é necessário reconstruir a imagem e recriar o container, não apenas reiniciar o container antigo. Preserve o .env, variáveis PG*, portas, volumes e a configuração do Compose existentes. O Compose não foi fornecido, por isso não há comando com nome de serviço presumido.
5. Publique o conteúdo de frontend_faturamento_cfop no local que já hospeda a tela de Faturamento CFOP. Esta pasta não deve substituir o portal inteiro nem outros relatórios. Se a tela é hospedada fora do PC do Anderson, publique nesse destino. Recarregue a tela após atualizar os arquivos.
6. Confira se o Worker permite GET /api/bi/faturamento-nf/detalhes. Se já encaminha /api/bi/*, pode não precisar de mudança. A autenticação existente foi preservada.
7. Abra pelo Portal e confira: clique no grupo e em cada indicador, notas/itens, filtros, Total, busca e CSV. Compare as quantidades e os valores com o resumo.

BANCO
Não execute os SQLs antigos nem recrie as views por causa desta atualização. O resumo existente continua usando comercial.vw_nf_por_vendedor_pai. O detalhamento também lê comercial.vw_faturamento_cfop_filtrado; o usuário técnico da API precisa ter SELECT nas duas views e USAGE no schema comercial.

CONTEÚDO
api_zootecnico: API completa recebida, com os três arquivos da atualização GPD mais recente, o suporte SQL faltante para product/efficiency_index e o detalhamento CFOP adaptado a bi_generic/faturamento_nf.
frontend_faturamento_cfop: tela atualizada com cliques, painel de notas/itens, busca, colunas e CSV.
MANIFESTO.json: relação de arquivos e hashes para conferência.

Não foram incluídos caches Python, arquivos .bak, ambiente virtual ou credenciais novas. Os arquivos de implantação e as dependências de produção foram preservados.

VALIDAÇÃO
Os resultados executados para esta entrega estão em VALIDACAO.txt. Os testes locais usam dados sintéticos e não substituem homologação no PostgreSQL e no Worker do ambiente real.
''', encoding='utf-8')
    manifest = {'data':'2026-10-19', 'origens':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.api,args.atualizacao)},
                'arquivos_backend_alterados_ou_novos':changed,
                'arquivos':{p.relative_to(delivery).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(delivery.rglob('*')) if p.is_file()}}
    (delivery / 'MANIFESTO.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'pasta':str(delivery),'alterados':changed}, ensure_ascii=False))


if __name__ == '__main__': main()
