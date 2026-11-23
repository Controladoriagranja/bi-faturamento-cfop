"""Extrai método e proposta auditável do Mix. Não conecta nem escreve no banco."""
from decimal import Decimal
from hashlib import sha256
import json
import re
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from fob.workbook import extract
from fob.reference import formula

SHEETS=('ComparativoMix','AnaliseMix','RendimentosXFormulacoes',
        'PrecoMedioXEmbalagemAN-RA-RN','CPV-Frango','CPV-Farinha')


def build(path):
    before=path.stat()
    digest=sha256(path.read_bytes()).hexdigest()
    data=extract(path,SHEETS,150)
    if data['CPV-Frango']['rows']['1']['C'].get('v')!='CPV - 10/26':
        raise ValueError('Esta prévia exige o modelo de outubro/2026 já analisado; conferir a competência do CPV-Frango.')
    spec=dict(versao=1,referencia_metodo=dict(arquivo=path.name,sha256=digest),sheets={},comparacoes=[])
    params=dict(estado='PREVIA_NAO_IMPORTADA',competencia='2026-10',origem=dict(arquivo=path.name,sha256=digest),cells={},bloqueios={})
    audit=[]
    for name in SHEETS:
        sheet=data[name];cells={};inputs={}
        for rn,row in sheet['rows'].items():
            for col,raw in row.items():
                ref=col+rn;expression=formula(sheet,int(rn),col)
                value=raw.get('v')
                if value is None:continue
                numeric_formula=expression and re.fullmatch(r'[=\d\s.+*/()^%-]+',expression)
                industrial_input=expression and name in ('CPV-Frango','CPV-Farinha') and col!='B'
                if expression and not numeric_formula and not industrial_input:
                    cells[ref]={'formula':expression};continue
                if raw.get('t') in ('s','inlineStr','str'):
                    cells[ref]={'text':str(value)};continue
                try:Decimal(str(value))
                except Exception:cells[ref]={'text':str(value)};continue
                # Código de produto é classificação, nunca preço/rendimento fixado.
                if name in ('CPV-Frango','CPV-Farinha','PrecoMedioXEmbalagemAN-RA-RN') and col=='B':
                    cells[ref]={'number':str(value)};continue
                cells[ref]={'input':True};inputs[ref]=str(value)
                audit.append(dict(aba=name,celula=ref,valor=str(value),formula_origem=expression or '',situacao='PROPOSTO_NAO_IMPORTADO'))
        spec['sheets'][name]=dict(max_row=max(map(int,sheet['rows'])),cells=cells)
        params['cells'][name]=inputs
    header=data['CPV-Farinha']['rows']['1']['C']['v']
    params['bloqueios']['CPV-Farinha']='CPV-Farinha: cabeçalho '+header+'. Competência diferente de outubro/2026; confirmar o custo do mês antes de importar.'
    params['cells'].pop('CPV-Farinha',None)
    for row in audit:
        if row['aba']=='CPV-Farinha':row['situacao']='BLOQUEADO_COMPETENCIA_DIFERENTE'
    sheet=data['ComparativoMix']
    for rn in range(5,27):
        row=sheet['rows'][str(rn)]
        spec['comparacoes'].append(dict(id='mix-'+str(rn),linha_excel=rn,
            familia_a=row['B']['v'],familia_b=row['D']['v'],celula_a='C'+str(rn),celula_b='E'+str(rn)))
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('O Excel mudou durante a leitura; salve uma versão estável e repita.')
    return spec,params,audit


def main():
    import argparse,csv
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arquivo',type=Path)
    args=parser.parse_args()
    spec,params,audit=build(args.arquivo)
    target=ROOT/'artifacts/comparativo-mix-20261123';target.mkdir(parents=True,exist_ok=True)
    (ROOT/'backend/modules/comparativo_fob/mix_method.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
    (target/'parametros-propostos-outubro.json').write_text(json.dumps(params,ensure_ascii=False,indent=2),encoding='utf-8')
    with (target/'parametros-para-conferencia.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(audit[0]),delimiter=';');writer.writeheader();writer.writerows(audit)
    print(json.dumps(dict(comparacoes=len(spec['comparacoes']),parametros=len(audit),bloqueios=params['bloqueios'],banco_alterado=False),ensure_ascii=False))


if __name__=='__main__':main()
