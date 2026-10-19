"""Integração pontual no Anderson. Sem --aplicar, apenas mostra o diff. Não inicia API."""
import argparse
import ast
import difflib
from pathlib import Path
import re

MARKER=b'# Comparativo FOB: registro isolado, mesma conexao e autenticacao.'
REGISTRATION=b'''from types import SimpleNamespace as _FOBContext
from modules.comparativo_fob.service import build_service as _build_fob_service
from modules.comparativo_fob.routes import create_router as _create_fob_router
app.include_router(_create_fob_router(_build_fob_service(_FOBContext(banco=banco))))'''


def newline(raw):
    return b'\r\r\n' if b'\r\r\n' in raw else b'\r\n' if b'\r\n' in raw else b'\n'


def plan(root):
    root=Path(root).resolve()
    service=root/'servico_zootecnico.py';docker=root/'Dockerfile.zootecnico'
    if not service.is_file() or not docker.is_file():
        raise ValueError('Use a raiz da API que contem servico_zootecnico.py e Dockerfile.zootecnico.')
    before=service.read_bytes();docker_before=docker.read_bytes();changes=[]
    modular=b'from core.bootstrap import register_modules' in before
    if not modular and MARKER not in before:
        if b'comparativo_fob' in before:raise ValueError('Ja existe registro FOB diferente; confira o diff manualmente.')
        if not re.search(rb'def banco\s*\(',before) or b'FastAPI(' not in before:
            raise ValueError('Factory banco/FastAPI nao reconhecida; nenhum arquivo foi alterado.')
        nl=newline(before)
        after=before+nl+nl+MARKER+nl+REGISTRATION.replace(b'\n',nl)+nl
        ast.parse(after.decode('utf-8-sig'),filename=str(service))
        changes.append((service,before,after))
    # Mantem o prefixo do contexto de build efetivo, sem substituir o Dockerfile.
    anchor=re.search(rb'(?m)^COPY\s+([^\s]+)/bi_generic\s+\./bi_generic[^\r\n]*',docker_before)
    if not anchor:anchor=re.search(rb'(?m)^COPY\s+([^\s]+)/modules\s+\./modules[^\r\n]*',docker_before)
    if not anchor:raise ValueError('COPY de bi_generic/modules nao reconhecido no Dockerfile; nenhum arquivo foi alterado.')
    prefix=anchor.group(1);required=[(prefix+b'/fob',b'./fob')]
    if not re.search(rb'(?m)^COPY\s+[^\s]+/modules\s+\./modules\s*$',docker_before):
        required.append((prefix+b'/modules/comparativo_fob',b'./modules/comparativo_fob'))
    additions=[]
    for source,target in required:
        pattern=rb'(?m)^COPY\s+'+re.escape(source)+rb'\s+'+re.escape(target)+rb'\s*$'
        if not re.search(pattern,docker_before):additions.append(b'COPY '+source+b' '+target)
    if additions:
        command=re.search(rb'(?m)^CMD\b',docker_before)
        if not command:raise ValueError('CMD nao reconhecido; nenhum arquivo foi alterado.')
        nl=newline(docker_before);point=command.start()
        after=docker_before[:point]+nl.join(additions)+nl+nl+docker_before[point:]
        changes.append((docker,docker_before,after))
    return changes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--aplicar',action='store_true')
    args=parser.parse_args();changes=plan(args.raiz)
    for path,before,after in changes:
        print(''.join(difflib.unified_diff(before.decode('utf-8-sig').splitlines(keepends=True),
            after.decode('utf-8-sig').splitlines(keepends=True),fromfile=path.name,tofile=path.name+' (FOB)')))
    if not changes:print('Integracao ja presente; nenhum arquivo alterado.');return
    if not args.aplicar:print('Somente diff. Para aplicar: python integrar_comparativo_fob.py --aplicar');return
    # Valida todos os backups antes de modificar qualquer alvo.
    for path,before,_ in changes:
        backup=path.with_name(path.name+'.antes_comparativo_fob.bak')
        if backup.exists() and backup.read_bytes()!=before:
            raise ValueError('Backup anterior diferente: '+str(backup)+'. Preserve-o e revise a integracao.')
    for path,before,after in changes:
        path.with_name(path.name+'.antes_comparativo_fob.bak').write_bytes(before)
        path.write_bytes(after);print('Atualizado:',path)


if __name__=='__main__':main()
