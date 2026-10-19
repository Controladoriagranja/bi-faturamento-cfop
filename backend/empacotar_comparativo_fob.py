"""Gera apenas a extensão da API do Anderson; não executa a API nem consulta banco."""
import argparse
import ast
import hashlib
import json
import difflib
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED
from fob.reference import WorkbookCatalog
from fob.snapshot import export_snapshot
from integrar_comparativo_fob import plan

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--excel',type=Path,required=True)
    parser.add_argument('--api-referencia',type=Path,default=Path.home()/'Downloads/api_zootecnico.zip')
    parser.add_argument('--saida',type=Path,default=ROOT/'artifacts/api_anderson_comparativo_fob.zip')
    args=parser.parse_args()
    catalog=WorkbookCatalog(args.excel)
    snapshot=json.dumps(export_snapshot(catalog),ensure_ascii=False,default=str,separators=(',',':')).encode('utf-8')
    files={}
    for folder in ['modules/comparativo_fob','fob']:
        for path in (ROOT/'backend'/folder).glob('*.py'):
            if path.name=='__main__.py':continue
            ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
            files[path.relative_to(ROOT/'backend').as_posix()]=path.read_bytes()
    files['modules/comparativo_fob/data/referencia_excel.json']=snapshot
    files['integrar_comparativo_fob.py']=(ROOT/'backend/integrar_comparativo_fob.py').read_bytes()
    with TemporaryDirectory() as temporary:
        with ZipFile(args.api_referencia) as reference:
            for name in ('servico_zootecnico.py','Dockerfile.zootecnico'):
                (Path(temporary)/name).write_bytes(reference.read('api_zootecnico/'+name))
        changes=plan(temporary)
        patch=''.join(''.join(difflib.unified_diff(before.decode('utf-8-sig').splitlines(keepends=True),
            after.decode('utf-8-sig').splitlines(keepends=True),fromfile=path.name,tofile=path.name)) for path,before,after in changes)
        files['INTEGRACAO-ANDERSON.patch']=patch.encode('utf-8')
        integration=[dict(arquivo=path.name,sha256_base=hashlib.sha256(before).hexdigest(),
            mudanca='Acrescentar registro isolado FOB' if path.suffix=='.py' else 'Acrescentar COPY de fob e modules/comparativo_fob') for path,before,_ in changes]
    manifest=dict(pacote='api_anderson_comparativo_fob.zip',data='2026-10-19',
        destino='Raiz da API que contém servico_zootecnico.py e Dockerfile.zootecnico. Não copiar para assets/ do frontend.',
        api_alvo='API fornecida api_zootecnico.zip + atualização pontual bi_generic/ do GPD; compatível também com descoberta ModuleSpec / RuntimeContext / RouteSet',
        api_referencia_sha256=hashlib.sha256(args.api_referencia.read_bytes()).hexdigest(),
        arquivos_compartilhados_modificados=[],sql_ddl_necessario=False,
        arquivos_compartilhados_alterados_pelo_integrador=integration,
        origem_excel_sha256=catalog.sha256,
        arquivos=[dict(caminho=name,acao='Adicionar (ou substituir somente esta extensão FOB, se já instalada)',sha256=hashlib.sha256(data).hexdigest()) for name,data in sorted(files.items())])
    readme='''COMPARATIVO PM FOB — INTEGRAÇÃO NA API DO ANDERSON

INSTALAÇÃO NA API FORNECIDA
1. Copie os arquivos deste ZIP para a raiz da API existente (ao lado de servico_zootecnico.py), respeitando seus caminhos. Preserve os demais módulos. Não substitua a pasta modules inteira.
2. Nessa raiz, execute: python integrar_comparativo_fob.py
   O comando apenas mostra o diff; não inicia a API nem acessa banco. O patch INTEGRACAO-ANDERSON.patch mostra antecipadamente a alteração exata contra o api_zootecnico.zip fornecido. A atualização backend_atualizacao_gpd_por_fase.zip contém somente bi_generic/{registry,router,gpd_fases}.py; estes arquivos não são tocados pelo pacote FOB.
3. Aplique: python integrar_comparativo_fob.py --aplicar
   Na API fornecida, acrescenta somente o registro das rotas em servico_zootecnico.py e dois COPY no Dockerfile.zootecnico. Cria backup *.antes_comparativo_fob.bak. O restante dos bytes dos arquivos é preservado; não substitui os serviços de outros BIs. Repetir não duplica a integração.
   Se a API já tiver core/bootstrap.py e descoberta de módulos, o integrador detecta esse padrão: não toca no serviço principal, e inclui somente os COPY ainda necessários. O MODULE fornece RouteSet/RuntimeContext sem mudar core/.
4. Reconstrua a imagem e recrie o container pelo procedimento já usado. Preserve variáveis de ambiente, portas, volumes e credenciais.
5. Confira o encaminhamento e a permissão das três rotas GET abaixo no Worker. A autorização continua no middleware existente e no Portal; o frontend mantém o Bearer, e o Worker deve manter a tradução da autenticação interna já usada. O código do Worker não foi fornecido nem alterado.

ROTAS
GET /api/comercial/comparativo-fob/filtros
GET /api/comercial/comparativo-fob/resumo
GET /api/comercial/comparativo-fob/detalhes

Estas rotas têm prefixo próprio /api/comercial/comparativo-fob e não interceptam /api/bi/{bi}/... do legado. O integrador reaproveita o prefixo dos COPY existentes (API/api_zootecnico no arquivo fornecido). Não cria aplicação, porta, autenticação nem container adicional. O pacote não sobrescreve versões antigas dos arquivos compartilhados: somente o integrador acrescenta os trechos auditáveis.

BANCO / LIMITES
Nenhum SQL de criação ou alteração é necessário. O usuário da API precisa de leitura em comercial.vw_faturamento_cfop_filtrado e comercial.faturamento_cfop. A leitura está limitada a 01–04/10/2026 e até 5.000 itens. Um SELECT pontual tenta conciliar a NF 806684 na tabela bruta; se ausente/indisponível, somente o item autorizado da linha 422 fica provisório e identificado. Outros itens ausentes são pendências, sem inventar peso/faturamento na origem.

As consultas são somente SELECT e usam o contexto somente leitura da API. O cache em memória dura 45 segundos e não grava dados. As opções iniciais e os cálculos permanecem restritos ao período comprovado; outros períodos são recusados até validar novos cadastros/perímetro. Não há CRUD nem preenchimento manual persistido nesta entrega.

FRETE E AUDITORIA
Frete tipo 1 nulo/zero e frete aplicável de Januária ficam pendentes; não são somados como FOB concluído. O valor salvo no Excel aparece somente como referência. O snapshot da comissão é do arquivo original, não uma folha recalculada. /detalhes expõe componentes, origens, fórmulas, diferenças de entrada e flag provisória.

VALIDAÇÃO PEQUENA APÓS INSTALAR
Abra o frontend oficial, escolha Comparativo PM FOB e consulte 01–04/10/2026. Confira os três pesos e a referência Excel. Varejo pode continuar pendente por frete. Abra uma família e “Ver cálculo”. Confira o relatório antigo e as rotas existentes. O backend não foi iniciado nesta máquina e não houve consulta/deploy em produção nesta entrega.
'''
    manifest['ajustes_explicitos_integracao']=[
        dict(arquivo='servico_zootecnico.py',condicao='API fornecida, sem descoberta modular',mudanca='Acrescentar bloco de registro FOB; integrador preserva conteúdo e gera backup. Ver patch.'),
        dict(arquivo='Dockerfile.zootecnico',condicao='COPY ainda ausente',mudanca='Acrescentar COPY de fob e modules/comparativo_fob, mantendo o contexto e todas as linhas existentes.')]
    files['LEIA-ME-INTEGRACAO.txt']=readme.encode('utf-8')
    manifest['arquivos']=[dict(caminho=name,acao='Adicionar (ou substituir somente esta extensão FOB, se já instalada)',
        sha256=hashlib.sha256(data).hexdigest()) for name,data in sorted(files.items())]
    files['MANIFESTO.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    args.saida.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(args.saida,'w',ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):archive.writestr(name,data)
    with ZipFile(args.saida) as archive:
        assert archive.testzip() is None
        for entry in manifest['arquivos']:assert hashlib.sha256(archive.read(entry['caminho'])).hexdigest()==entry['sha256']
    print(json.dumps(dict(zip=str(args.saida),arquivos=len(files),bytes=args.saida.stat().st_size,sha256_excel=catalog.sha256),ensure_ascii=False))


if __name__=='__main__':main()
