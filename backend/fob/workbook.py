"""Inspeção somente leitura e limitada às linhas usadas do Excel de referência."""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def extract(path, sheets, max_row=1300):
    result = {}
    with ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            for _, element in ET.iterparse(archive.open('xl/sharedStrings.xml'), events=('end',)):
                if element.tag == NS+'si':
                    strings.append(''.join(t.text or '' for t in element.iter(NS+'t')))
                    element.clear()
        relationships = {r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        for sheet in workbook.find(NS+'sheets'):
            name = sheet.attrib['name']
            if not any(s.casefold() in name.casefold() for s in sheets): continue
            target = relationships[sheet.attrib[REL+'id']]
            target = target.lstrip('/') if target.startswith('/') else 'xl/'+target
            data = {'state':sheet.attrib.get('state','visible'),'columns':[], 'rows':{}, 'hidden_rows':[], 'shared_formulas':{}}
            for _, element in ET.iterparse(archive.open(target), events=('end',)):
                if element.tag == NS+'dimension': data['dimension'] = element.attrib['ref']
                if element.tag == NS+'col': data['columns'].append(element.attrib.copy())
                if element.tag == NS+'autoFilter': data['auto_filter'] = element.attrib.copy()
                if element.tag == NS+'row':
                    number=int(element.attrib['r'])
                    if number>max_row: break
                    if element.attrib.get('hidden')=='1': data['hidden_rows'].append(number)
                    row={}
                    for cell in element:
                        if cell.tag!=NS+'c': continue
                        value=cell.find(NS+'v'); formula=cell.find(NS+'f')
                        value=value.text if value is not None else None
                        kind=cell.attrib.get('t')
                        if kind=='s' and value is not None:value=strings[int(value)]
                        elif kind=='inlineStr': value=''.join(t.text or '' for t in cell.iter(NS+'t'))
                        if value is None and formula is None:continue
                        column=re.match('[A-Z]+',cell.attrib['r'])[0]
                        record={'v':value}
                        if formula is not None:
                            record['f']=formula.text or ''
                            if formula.attrib:
                                record['fa']=formula.attrib.copy()
                                if formula.text:data['shared_formulas'][formula.attrib.get('si',cell.attrib['r'])]={'cell':cell.attrib['r'],'f':formula.text,'attrs':formula.attrib}
                        if kind:record['t']=kind
                        row[column]=record
                    if row:data['rows'][str(number)]=row
                    element.clear()
            result[name]=data
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arquivo',type=Path)
    parser.add_argument('--saida',type=Path,required=True)
    parser.add_argument('--max-linha',type=int,default=1300)
    parser.add_argument('--abas',nargs='+',default=['FaturamentoANeRA','FaturamentoRN','FaturamentoJA','Comiss','Despesas','Tabelas','AnaliseMixPMInclusiveCDs','Peso Varejo'])
    args=parser.parse_args()
    data=extract(args.arquivo,args.abas,args.max_linha)
    args.saida.parent.mkdir(parents=True,exist_ok=True)
    args.saida.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    for name,sheet in data.items():
        print(name,sheet.get('dimension'),'linhas lidas',len(sheet['rows']),'ocultas',len(sheet['hidden_rows']))


if __name__=='__main__':main()
