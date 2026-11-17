"""Aplica linhas preparadas pelo Artifact Tool preservando originais e precisão."""
from copy import deepcopy
from datetime import date,datetime
from decimal import Decimal
from io import BytesIO
from pathlib import PurePosixPath
import posixpath,re
import xml.etree.ElementTree as ET
from zipfile import ZipFile,ZIP_DEFLATED

from .planilhas import NS,column

N='{'+NS+'}'
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def part(archive,sheet):
    book=ET.fromstring(archive.read('xl/workbook.xml'))
    rels={r.get('Id'):r.get('Target') for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
    selected=next(s for s in book.find(N+'sheets') if s.get('name')==sheet)
    target=rels[selected.get(REL)]
    return target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)


def shared_strings(archive):
    if 'xl/sharedStrings.xml' not in archive.namelist():return []
    return [''.join(t.text or '' for t in si.iter(N+'t')) for si in ET.fromstring(archive.read('xl/sharedStrings.xml'))]


def text(cell,strings):
    if cell is None:return None
    value=cell.find(N+'v')
    if cell.get('t')=='s':return strings[int(value.text)]
    if cell.get('t')=='inlineStr':return ''.join(t.text or '' for t in cell.iter(N+'t'))
    return value.text if value is not None else None


def append_generated(original,generated,specs):
    patches={};ET.register_namespace('',NS)
    with ZipFile(BytesIO(original)) as before,ZipFile(BytesIO(generated)) as addition:
        original_strings=shared_strings(before);new_strings=shared_strings(addition)
        for spec in specs:
            name=part(before,spec['aba']);root=ET.fromstring(before.read(name));data=root.find(N+'sheetData')
            source_data=ET.fromstring(addition.read(part(addition,spec['aba']))).find(N+'sheetData')
            source_rows=[r for r in source_data if int(r.get('r'))>=6 and text(r.find(N+'c'),new_strings)]
            if len(source_rows)!=len(spec['linhas']):raise ValueError('Quantidade preparada diverge do plano.')
            originals={text(r.find(N+'c'),original_strings):r for r in data if int(r.get('r'))>=6 and text(r.find(N+'c'),original_strings)}
            rowmap={int(r.get('r')):r for r in data}
            old_rows={k:ET.tostring(r) for k,r in originals.items()}
            if any(row['registro'] in originals for row in spec['linhas']):raise ValueError('Réplica já existe na planilha; refaça a prévia.')
            headers=list(spec['linhas'][0]);last=max([5,*[int(r.get('r')) for r in originals.values()]])
            for record,row in zip(spec['linhas'],source_rows):
                # O identificador de origem fica explícito no texto auditável.
                origin=record['origem'].split(' | parâmetro de ',1)[1].split(' | ',1)[0]
                source=originals.get(origin)
                if source is None:raise ValueError('Linha original da réplica não encontrada.')
                last+=1;new=deepcopy(source);new.set('r',str(last))
                template={re.sub(r'\d+','',c.get('r')):c for c in source}
                modified={'registro','inicio','fim','origem','gestor1','gestor2','gestor3','dias_mes','dias_periodo'}
                for cell in new:cell.set('r',re.sub(r'\d+','',cell.get('r'))+str(last))
                for prepared_cell in row:
                    cell=deepcopy(prepared_cell)
                    letter=re.sub(r'\d+','',cell.get('r'));idx=next(i for i in range(len(headers)) if column(i+1)==letter)
                    if headers[idx] not in modified:continue
                    original_cell=template.get(letter)
                    cell.set('r',letter+str(last))
                    if original_cell is not None and original_cell.get('s'):cell.set('s',original_cell.get('s'))
                    else:cell.attrib.pop('s',None)
                    if cell.get('t')=='s':
                        value=text(cell,new_strings)
                        for child in list(cell):cell.remove(child)
                        cell.set('t','inlineStr');ET.SubElement(ET.SubElement(cell,N+'is'),N+'t').text=value
                    for old in list(new):
                        if old.get('r')==cell.get('r'):new.remove(old)
                    new.append(cell)
                new[:]=sorted(new,key=lambda c:next(i for i in range(len(headers)) if c.get('r')==column(i+1)+str(last)))
                rowmap[last]=new
            data[:]=[r for _,r in sorted(rowmap.items())]
            for key,source in originals.items():
                if ET.tostring(source)!=old_rows[key]:raise ValueError('Uma linha original seria modificada.')
            used=max(int(r.get('r')) for r in data)
            dimension=root.find(N+'dimension')
            if dimension is not None:dimension.set('ref','A1:'+column(len(headers))+str(used))
            for validation in root.iter(N+'dataValidation'):
                ref=validation.get('sqref','');match=re.fullmatch(r'([A-Z]+)6:\1(\d+)',ref)
                if match:validation.set('sqref',f'{match[1]}6:{match[1]}{max(last,int(match[2]))}')
            for filt in root.findall(N+'autoFilter'):filt.set('ref','A5:'+column(len(headers))+str(last))
            # Expandir a tabela nativa sem reescrever colunas, estilos ou outros objetos.
            relpath=posixpath.dirname(name)+'/_rels/'+posixpath.basename(name)+'.rels'
            rels={r.get('Id'):r.get('Target') for r in ET.fromstring(before.read(relpath))} if relpath in before.namelist() else {}
            for tablepart in root.iter(N+'tablePart'):
                target=rels[tablepart.get(REL)]
                tablepath=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(name)+'/'+target)
                table=ET.fromstring(before.read(tablepath));table.set('ref','A5:'+column(len(headers))+str(last))
                for filt in table.findall(N+'autoFilter'):filt.set('ref',table.get('ref'))
                patches[tablepath]=ET.tostring(table,encoding='utf-8',xml_declaration=True)
            patches[name]=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        out=BytesIO()
        with ZipFile(out,'w',ZIP_DEFLATED) as archive:
            for entry in before.infolist():archive.writestr(entry,patches.get(entry.filename,before.read(entry.filename)))
    return out.getvalue(),set(patches)


def apply_generated_changes(original,generated,specs):
    """Mescla um delta Artifact Tool, preservando abas e células fora do plano.

    Não publica arquivos nem importa PostgreSQL. Valores NUMERIC são escritos
    com seus decimais originais; o XLSX auxiliar fornece estrutura e conferência.
    Cada alteração informa a linha anterior ou None para acréscimo.
    """
    patches={};ET.register_namespace('',NS)
    with ZipFile(BytesIO(original)) as before,ZipFile(BytesIO(generated)) as delta:
        for spec in specs:
            name=part(before,spec['aba']);root=ET.fromstring(before.read(name));data=root.find(N+'sheetData')
            source=ET.fromstring(delta.read(part(delta,spec['aba']))).find(N+'sheetData')
            prepared=[r for r in source if int(r.get('r'))>=6 and len(r)]
            if len(prepared)!=len(spec['alteracoes']):raise ValueError('Quantidade do delta não confere.')
            headers=spec['headers'];numeric=set(spec.get('numericos',[]));dates=set(spec.get('datas',[]))
            rows={int(r.get('r')):r for r in data};last=max(rows)
            template=next((r for n,r in sorted(rows.items()) if n>=6 and len(r)),None)
            if spec.get('nota'):
                label=next((c for r in source if r.get('r')=='3' for c in r if c.get('r')=='A3'),None)
                if label is None:raise ValueError('Nota de revisão ausente no delta.')
                target_row=rows.setdefault(3,ET.Element(N+'row',{'r':'3'}))
                old_label=next((c for c in target_row if c.get('r')=='A3'),None)
                label_text=text(label,shared_strings(delta))
                label=ET.Element(N+'c',{'r':'A3','t':'inlineStr'})
                ET.SubElement(ET.SubElement(label,N+'is'),N+'t').text=label_text
                if old_label is not None:
                    if old_label.get('s'):label.set('s',old_label.get('s'))
                    target_row.remove(old_label)
                target_row.insert(0,label)

            def cell_value(value,letter,number,style=None):
                cell=ET.Element(N+'c',{'r':letter+str(number)})
                if style is not None:cell.set('s',style)
                if value is None or value=='':return cell
                key=headers[next(i for i in range(len(headers)) if column(i+1)==letter)]
                if key in dates:
                    value=value.date() if isinstance(value,datetime) else value if isinstance(value,date) else date.fromisoformat(str(value))
                    ET.SubElement(cell,N+'v').text=str((value-date(1899,12,30)).days)
                elif key in numeric:
                    ET.SubElement(cell,N+'v').text=str(value)
                else:
                    cell.set('t','inlineStr');txt=ET.SubElement(ET.SubElement(cell,N+'is'),N+'t');txt.text=str(value)
                    txt.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
                return cell

            header=rows[5];old_letters={re.sub(r'\d','',c.get('r')):c for c in header}
            delta_cols=ET.fromstring(delta.read(part(delta,spec['aba']))).find(N+'cols')
            for j,key in enumerate(headers,1):
                letter=column(j)
                if letter not in old_letters:
                    cell=ET.Element(N+'c',{'r':letter+'5','t':'inlineStr'})
                    previous=old_letters.get(column(j-1))
                    if previous is not None and previous.get('s'):cell.set('s',previous.get('s'))
                    ET.SubElement(ET.SubElement(cell,N+'is'),N+'t').text=key;header.append(cell)
                    # A coluna nova conserva a largura legível do delta gerado.
                    # Não altera as larguras nem os estilos das colunas anteriores.
                    source_col=next((c for c in delta_cols if int(c.get('min'))<=j<=int(c.get('max'))),None) if delta_cols is not None else None
                    if source_col is not None:
                        cols=root.find(N+'cols')
                        if cols is None:
                            cols=ET.Element(N+'cols');root.insert(list(root).index(data),cols)
                        added=deepcopy(source_col);added.set('min',str(j));added.set('max',str(j));cols.append(added)
            for change,prepared_row in zip(spec['alteracoes'],prepared):
                number=change.get('linha')
                if number is None:last+=1;number=last
                elif number not in rows or number<6:raise ValueError('Linha anterior inválida.')
                old=rows.get(number)
                row=deepcopy(old) if old is not None else ET.Element(N+'row',{'r':str(number)})
                styles={re.sub(r'\d','',c.get('r')):c.get('s') for c in (old if old is not None else template or [])}
                for j,key in enumerate(headers,1):
                    if key not in change['valores']:continue
                    letter=column(j)
                    for cell in list(row):
                        if cell.get('r')==letter+str(number):row.remove(cell)
                    row.append(cell_value(change['valores'][key],letter,number,styles.get(letter)))
                row[:]=sorted(row,key=lambda c:column_number(re.sub(r'\d','',c.get('r'))))
                rows[number]=row
            data[:]=[r for _,r in sorted(rows.items())]
            dimension=root.find(N+'dimension')
            if dimension is not None:dimension.set('ref','A1:'+column(len(headers))+str(last))
            for validation in root.iter(N+'dataValidation'):
                ref=validation.get('sqref','');match=re.fullmatch(r'([A-Z]+)6:\1(\d+)',ref)
                if match:validation.set('sqref',f'{match[1]}6:{match[1]}{max(last,int(match[2]))}')
            for filt in root.findall(N+'autoFilter'):filt.set('ref','A5:'+column(len(headers))+str(last))
            relpath=posixpath.dirname(name)+'/_rels/'+posixpath.basename(name)+'.rels'
            rels={r.get('Id'):r.get('Target') for r in ET.fromstring(before.read(relpath))} if relpath in before.namelist() else {}
            for tablepart in root.iter(N+'tablePart'):
                target=rels[tablepart.get(REL)]
                tablepath=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(name)+'/'+target)
                table=ET.fromstring(before.read(tablepath));table.set('ref','A5:'+column(len(headers))+str(last))
                for filt in table.findall(N+'autoFilter'):filt.set('ref',table.get('ref'))
                cols=table.find(N+'tableColumns')
                if cols is not None:
                    for j in range(len(cols),len(headers)):
                        ET.SubElement(cols,N+'tableColumn',{'id':str(j+1),'name':headers[j]})
                    cols.set('count',str(len(headers)))
                patches[tablepath]=ET.tostring(table,encoding='utf-8',xml_declaration=True)
            patches[name]=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        out=BytesIO()
        with ZipFile(out,'w',ZIP_DEFLATED) as archive:
            for entry in before.infolist():archive.writestr(entry,patches.get(entry.filename,before.read(entry.filename)))
    return out.getvalue(),set(patches)


def column_number(value):
    result=0
    for char in value:result=result*26+ord(char)-64
    return result
