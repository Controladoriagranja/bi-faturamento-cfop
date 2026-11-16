"""Prepara somente os três arquivos de Faturamento NF sobre a API fornecida.

Não executa a API, Docker ou SQL. Preserva os demais módulos e não empacota
credenciais, configurações locais ou cópias completas do backend.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'api_zootecnico/bi_generic/faturamento_nf/'
PATCHES = {
    'config.py': (
        b"'table':'vw_nf_por_vendedor_pai'",
        b"'table':'vw_nf_por_vendedor_pai_faturamento'",
    ),
    'details.py': (
        b"sql.Identifier('comercial', 'vw_faturamento_cfop_filtrado')",
        b"sql.Identifier('comercial', 'vw_faturamento_vendedor_pai_itens')",
    ),
    'service.py': (
        b"fonte='comercial.vw_nf_por_vendedor_pai',versao_regras='faturamento-nf-unidades-2026-10-14'",
        b"fonte=CONFIG['bi']['schema']+'.'+CONFIG['bi']['table'],versao_regras='faturamento-nf-exclusoes-2026-11-16'",
    ),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def merge(original):
    result = {}
    for name, (before, after) in PATCHES.items():
        raw = original[name]
        if raw.count(before) != 1:
            raise ValueError('Ponto de integração inesperado em ' + name + '. Revisar a API atual.')
        updated = raw.replace(before, after, 1)
        assert updated.replace(after, before, 1) == raw
        if name == 'details.py':
            # A view estima uma NF e o plano escolhido revarre os itens para
            # cada nota. A orientação fica restrita à transação deste GET.
            anchor = b'            stats = conn.execute(query, params).fetchone()'
            if updated.count(anchor) != 1:
                raise ValueError('Ponto de execução inesperado em details.py.')
            newline = re.search(rb'\r*\n', raw).group(0)
            addition = newline.join([
                b"            if view == 'itens':",
                b'                # Evita revarrer os itens para cada NF em fontes com baixa estimativa.',
                b'                # SET LOCAL vale somente nesta transacao de leitura.',
                b"                conn.execute('SET LOCAL enable_nestloop = off')",
                anchor,
            ])
            previous = updated
            updated = updated.replace(anchor, addition, 1)
            assert updated.replace(addition, anchor, 1) == previous
        ast.parse(updated.decode('utf-8-sig'), filename=name)
        result[name] = updated
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', type=Path, required=True)
    parser.add_argument('--saida', type=Path, required=True)
    args = parser.parse_args()
    source = args.api.resolve()
    destination = args.saida.resolve()
    if source == destination or destination.exists():
        raise ValueError('A saída precisa ser um arquivo novo, diferente do ZIP original.')
    source_hash = digest(source.read_bytes())
    with ZipFile(source) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError('ZIP com entradas duplicadas ou CRC inválido.')
        original = {name: archive.read(PREFIX + name) for name in PATCHES}
    updated = merge(original)
    files = []
    for name, data in updated.items():
        local = ROOT / 'backend/modules/faturamento_nf' / name
        local.write_bytes(data)
        files.append(dict(caminho='bi_generic/faturamento_nf/' + name,
                          acao='SUBSTITUIR', sha256_anterior=digest(original[name]),
                          sha256_novo=digest(data), bytes=len(data)))
    manifest = dict(origem=source.name, sha256_origem=source_hash,
                    arquivos=files, arquivos_novos_na_api=[], outros_modulos_alterados=[],
                    views_necessarias=[
                        'comercial.vw_nf_por_vendedor_pai_faturamento',
                        'comercial.vw_faturamento_vendedor_pai_itens'],
                    views_ja_criadas=True, docker_executado=False, deploy_executado=False)
    instructions = '''ATUALIZAÇÃO DO FATURAMENTO POR VENDEDOR PAI — 16/11/2026

Base: api_zootecnico(7).zip enviado pelo usuário.

1. Faça backup dos três arquivos atuais da pasta da API do Anderson.
2. Extraia este ZIP e copie a pasta bi_generic para a RAIZ da API existente,
   a mesma pasta que já contém bi_generic, preservando as demais pastas.
3. Substitua SOMENTE estes três arquivos:
   bi_generic/faturamento_nf/config.py
   bi_generic/faturamento_nf/details.py
   bi_generic/faturamento_nf/service.py
4. Atualize/reconstrua o contêiner pelo procedimento habitual do Anderson.
   Nenhum comando de Docker ou deploy foi executado nesta entrega.
5. No Portal, consulte outubro/2026. A resposta do resumo deve indicar:
   fonte: comercial.vw_nf_por_vendedor_pai_faturamento
   versao_regras: faturamento-nf-exclusoes-2026-11-16

As duas views já foram criadas e verificadas no banco desta instalação.
Não precisa executar SQL, importar planilhas ou recriar tabelas.

Resumo, filtros e seleção de NFs usam a view de NFs nova. Itens, busca e
exportação usam a view de itens nova. Endpoints e contratos permanecem iguais.
As consultas de itens ajustam o plano somente na sua transação de leitura,
evitando releituras por NF. O limite de 15 segundos e a conexão são preservados.
As alterações adicionais do ZIP original foram preservadas nos três arquivos.
Nenhum arquivo de outro BI, FOB, autenticação, core ou configuração global
foi incluído nesta atualização.

Referência de outubro validada no banco em 16/11:
11.938 NFs, 26.927 itens, 14.691.917,00 kg e R$ 98.700.493,55 faturados.
As NFs 659057, 659075, 660315 e 808715 permanecem.
O total inclui 4 notas a mais que o Excel e exclui a bonificação 808965 que
também estava no Excel. As classificações de vendedores ainda não foram
alteradas, assim como a fórmula do ticket de Januária.

Para reverter a API, restaure somente os três arquivos anteriores. As fontes
anteriores do banco foram preservadas. Não exclua nenhuma tabela ou view.
'''
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        for name, data in updated.items():
            archive.writestr('bi_generic/faturamento_nf/' + name, data)
        archive.writestr('MANIFESTO.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))
        archive.writestr('COMO_SUBSTITUIR.txt', instructions.encode('utf-8-sig'))
    with ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {
            *('bi_generic/faturamento_nf/' + name for name in PATCHES),
            'MANIFESTO.json', 'COMO_SUBSTITUIR.txt'}
        for name, data in updated.items():
            assert archive.read('bi_generic/faturamento_nf/' + name) == data
    assert digest(source.read_bytes()) == source_hash
    print(json.dumps(dict(zip=str(destination), arquivos_substituidos=len(files),
                          sha256=digest(destination.read_bytes()),
                          outros_modulos_preservados=True), ensure_ascii=False))


if __name__ == '__main__':
    main()
