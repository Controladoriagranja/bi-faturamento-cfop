"""Leitura estrita dos modelos; atualização OOXML preserva outras abas byte a byte."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

from fob.master_data import DIMENSIONS, digest, invoice_key, validate_rules
from fob.calculator import decimal

NF = ('empresa_contexto','unidade_documento','serie','nota_numero','ano_nf')
FREIGHT_HEADERS = (*NF,'chave_item','assinatura_nf','peso_total_nf','peso_item','escopo','modalidade','valor','observacao')
PENDING_HEADERS = (*NF,'chave_item','assinatura_nf','peso_total_nf','peso_item','data','produto',
                   'cliente','produto_descricao','quantidade','frete_original','situacao','motivo')
RULE_HEADERS = ('registro','inicio','fim','tipo',*DIMENSIONS,'modalidade','valor','divisor','ativo','origem')
CHARGES = ('fgts','inss_empresa','inss_terceiros','sat','fap','decimo_terceiro',
           'fgts_decimo','inss_decimo','ferias','fgts_ferias','inss_ferias')
PAYROLL_HEADERS = ('registro','inicio','fim','vendedor','gestor1','gestor2','gestor3','salario','premio',
    'percentual','adicional_percentual','adicional_modo','dsr_comissao','dsr_premio','base_encargos',
    'dias_uteis','domingos_feriados','dias_mes','dias_periodo',*CHARGES,'ativo','origem')
MANAGER_HEADERS = ('registro','inicio','fim','base_manual','nivel','salario','premio','percentual','adicional_percentual',
    'adicional_modo','dsr_comissao','dsr_premio','base_encargos',
    'dias_uteis','domingos_feriados','dias_mes','dias_periodo',*CHARGES,'ativo','origem')
MONTH_HEADERS = ('competencia','custo_kg','origem')
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


@contextmanager
def locked(path,write=False):
    """Recusa ~$ e usa bloqueio real do arquivo; mantém o handle durante leitura."""
    path=Path(path)
    if path.with_name('~$'+path.name).exists():raise ValueError('Arquivo aberto no Excel: '+path.name)
    if os.name=='nt':
        import ctypes,msvcrt
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        create=kernel.CreateFileW
        create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,
                         wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        create.restype=wintypes.HANDLE
        # Compartilha somente DELETE para permitir replace atômico enquanto o handle
        # bloqueia abertura para leitura/escrita pelo Excel e por outro robô.
        raw=create(str(path.resolve()),0x80000000|(0x40000000 if write else 0),4,None,3,0x80,None)
        if raw==wintypes.HANDLE(-1).value:raise ValueError('Arquivo aberto, indisponível ou sem acesso: '+path.name)
        handle=os.fdopen(msvcrt.open_osfhandle(raw,os.O_BINARY|(os.O_RDWR if write else os.O_RDONLY)),
                         'r+b' if write else 'rb')
    else:handle=path.open('r+b' if write else 'rb')
    try:
        if os.name!='nt':
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        handle.seek(0)
        yield handle
    finally:
        handle.close()


def table(content,sheet,headers):
    from openpyxl import load_workbook
    wb=load_workbook(BytesIO(content),read_only=True,data_only=False,keep_links=False)
    try:
        if sheet not in wb.sheetnames:raise ValueError('Aba ausente: '+sheet)
        if (wb[sheet].max_row or 0)>50005 or (wb[sheet].max_column or 0)>len(headers):
            raise ValueError('Área excede o modelo ou 50.000 linhas: '+sheet)
        rows=wb[sheet].iter_rows(min_row=5,values_only=True)
        actual=next(rows,())
        if tuple(actual[:len(headers)])!=tuple(headers):raise ValueError('Cabeçalhos divergentes: '+sheet)
        if any(v is not None for v in actual[len(headers):]):raise ValueError('Colunas não reconhecidas: '+sheet)
        for number,values in enumerate(rows,6):
            if number>50005:raise ValueError('Mais de 50.000 linhas: '+sheet)
            if not any(v is not None and v!='' for v in values):continue
            if any(v is not None for v in values[len(headers):]):raise ValueError('Colunas extras: '+sheet)
            row=dict(zip(headers,values));row['_linha']=number
            if any(isinstance(v,str) and v.startswith('=') for v in values):
                raise ValueError(f'{sheet}!{number}: fórmulas não são entradas; informe o parâmetro.')
            yield row
    finally:wb.close()


def identifier(value):
    if not isinstance(value,str) or not value.strip() or any(ord(c)<32 for c in value):
        raise ValueError('Identificador deve ser texto; preserve zeros à esquerda.')
    return value.strip(' ')


def input_date(value):
    if isinstance(value,datetime):return value.date().isoformat()
    if isinstance(value,date):return value.isoformat()
    return date.fromisoformat(str(value)).isoformat()


def active(value):
    if value not in ('SIM','NAO'):raise ValueError('ativo deve ser SIM ou NAO.')
    return value=='SIM'


def base_rule(row,filename,kind=None):
    return dict(registro=identifier(row['registro']),inicio=input_date(row['inicio']),fim=input_date(row['fim']),
        tipo=kind or row['tipo'],dimensoes={},modalidade='KG',valor=Decimal(0),parametros={},
        ativo=active(row['ativo']),origem=f"{filename}!{row['_linha']} — {row.get('origem') or ''}")


def payroll_params(row):
    keys=('salario','premio','percentual','adicional_percentual','dias_uteis','domingos_feriados','dias_mes','dias_periodo')
    params={k:decimal(row.get(k)) for k in keys}
    mode=row.get('adicional_modo')
    if mode not in ('DIGITADO','UM_DOZE'):raise ValueError('adicional_modo deve ser DIGITADO ou UM_DOZE.')
    if mode=='UM_DOZE':params['adicional_percentual']=Decimal(0)
    params['adicional_modo']=mode
    for flag in ('dsr_comissao','dsr_premio','base_encargos'):params[flag]=active(row.get(flag))
    if any(params[k] is None or params[k]<0 for k in keys):raise ValueError('Parâmetro de folha ausente/negativo.')
    if params['dias_uteis']<=0 or params['dias_mes']<=0 or params['dias_periodo']<=0 or params['dias_periodo']>params['dias_mes']:
        raise ValueError('Dias de folha inconsistentes.')
    if params['percentual']>1 or params['adicional_percentual']>1:raise ValueError('Percentual inválido.')
    params['encargos']=[decimal(row.get(k)) for k in CHARGES]
    if any(v is None or not -1<=v<=1 for v in params['encargos']):raise ValueError('Encargo ausente ou inválido.')
    return params


def read_bundle(contents):
    for name in ('Fretes.xlsx','Despesas.xlsx','Comissoes.xlsx'):
        try:
            with ZipFile(BytesIO(contents[name])) as archive:
                if archive.testzip() is not None:raise BadZipFile()
        except BadZipFile:
            raise ValueError('Arquivo XLSX inválido: '+name+'. Corrija ou restaure uma cópia válida antes de repetir.') from None
    rules=[];monthly=[]
    for r in table(contents['Despesas.xlsx'],'Cadastros',RULE_HEADERS):
        item=base_rule(r,'Despesas.xlsx')
        item.update(dimensoes={k:identifier(r[k]) for k in DIMENSIONS if r.get(k) not in (None,'')},
                    modalidade=r['modalidade'],valor=decimal(r['valor']))
        item['parametros']={'divisor':decimal(r.get('divisor') if r.get('divisor') is not None else 1)}
        if item['parametros']['divisor']<=0:raise ValueError('Divisor deve ser positivo.')
        if item['tipo'] in ('frete','folha','gestor','comissao','adicional_comissao'):
            raise ValueError('Categoria deve ficar em Fretes ou Comissoes.xlsx.')
        rules.append(item)
    for r in table(contents['Comissoes.xlsx'],'Percentuais',RULE_HEADERS):
        item=base_rule(r,'Comissoes.xlsx')
        item.update(dimensoes={k:identifier(r[k]) for k in DIMENSIONS if r.get(k) not in (None,'')},
                    modalidade=r['modalidade'],valor=decimal(r['valor']))
        item['parametros']={'divisor':decimal(r.get('divisor') if r.get('divisor') is not None else 1)}
        if item['parametros']['divisor']<=0:raise ValueError('Divisor deve ser positivo.')
        if item['tipo'] not in ('comissao','adicional_comissao'):raise ValueError('Categoria de comissão inválida.')
        rules.append(item)
    for sheet,headers,kind in [('Vendedores',PAYROLL_HEADERS,'folha'),('Gestores',MANAGER_HEADERS,'gestor')]:
        for r in table(contents['Comissoes.xlsx'],sheet,headers):
            item=base_rule(r,'Comissoes.xlsx/'+sheet,kind)
            item['modalidade']='FOLHA'
            if kind=='gestor' and r.get('base_manual') is not None:
                amount=decimal(r['base_manual'])
                if amount is None or amount<0:raise ValueError('Base de gestor inválida.')
                params={'base_manual':amount}
            else:params=payroll_params(r)
            if kind=='gestor':
                level=int(r.get('nivel') or 0)
                if level not in (1,2,3):raise ValueError('Gestor exige nível 1, 2 ou 3 comprovado na fórmula L/M.')
                params['nivel']=level
            if kind=='folha':
                item['dimensoes']={'vendedor':identifier(r['vendedor'])}
                params['gestores']=[identifier(r[k]) if r.get(k) else '' for k in ('gestor1','gestor2','gestor3')]
            else:item['dimensoes']={'vendedor':item['registro']} # diferencia gestores sem afetar itens
            item['parametros']=params;rules.append(item)
    for r in table(contents['Fretes.xlsx'],'Preenchimentos',FREIGHT_HEADERS):
        # Linhas preparadas mas ainda não preenchidas NÃO apagam cadastro válido.
        if r.get('valor') is None:continue
        values={k:identifier(r[k]) for k in NF if k!='ano_nf'}
        year=int(r['ano_nf'])
        if decimal(r['ano_nf'])!=year:raise ValueError('Ano da NF deve ser inteiro.')
        if not 2000<=year<=2100:raise ValueError('Ano da NF inválido.')
        scope=r['escopo'];mode=r['modalidade'];amount=decimal(r['valor'])
        if scope not in ('NF','ITEM') or mode not in ('TOTAL','KG') or amount is None or amount<=0:
            raise ValueError('Frete exige NF/ITEM, TOTAL/KG e valor positivo.')
        if values['unidade_documento']=='102':raise ValueError('Januária usa somente custo mensal.')
        values['ano_nf']=year
        if scope=='ITEM':values['chave_item']=identifier(r['chave_item'])
        elif r.get('chave_item') not in (None,''):raise ValueError('Frete NF deve deixar chave_item vazia.')
        signature=identifier(r['assinatura_nf'])
        if len(signature)!=64:raise ValueError('Copie a assinatura da aba Pendências.')
        rules.append(dict(registro='frete:'+digest(values),inicio=f'{year}-01-01',fim=f'{year}-12-31',
            tipo='frete',dimensoes=values,modalidade=('TOTAL_'+scope) if mode=='TOTAL' else 'KG',
            valor=amount,parametros={'assinatura_nf':signature},ativo=True,
            origem=f"Fretes.xlsx/Preenchimentos!{r['_linha']}"))
    seen=set()
    for r in table(contents['Despesas.xlsx'],'Custo Mensal Januária',MONTH_HEADERS):
        value=decimal(r.get('custo_kg'));competence=input_date(r['competencia'])
        if competence[-2:]!='01' or competence in seen:raise ValueError('Competência deve ser única e dia 01.')
        if not '2000-01-01'<=competence<='2100-12-01':raise ValueError('Competência fora do limite.')
        if value is None or value<0 or value>=Decimal('1e8') or value.as_tuple().exponent < -10:
            raise ValueError('Custo mensal fora de NUMERIC(18,10).')
        seen.add(competence);monthly.append(dict(competencia=competence,custo_kg=value,origem=r['origem']))
    validate_rules(rules)
    return rules,monthly


def column(number):
    text=''
    while number:number,digit=divmod(number-1,26);text=chr(65+digit)+text
    return text


def update_pending(content,records):
    """Reescreve somente sheetData de Pendências; Preenchimentos não é serializada."""
    ns='{'+NS+'}';ET.register_namespace('',NS)
    out=BytesIO()
    with ZipFile(BytesIO(content)) as source:
        workbook=ET.fromstring(source.read('xl/workbook.xml'))
        rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(source.read('xl/_rels/workbook.xml.rels'))}
        sheet=next(s for s in workbook.find(ns+'sheets') if s.attrib['name']=='Pendências')
        target=rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
        target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
        root=ET.fromstring(source.read(target));data=root.find(ns+'sheetData')
        for row in list(data):
            if int(row.attrib['r'])>=6:data.remove(row)
        for i,record in enumerate(records,6):
            row=ET.SubElement(data,ns+'row',{'r':str(i)})
            for j,key in enumerate(PENDING_HEADERS,1):
                value=record.get(key)
                if value is None:continue
                cell=ET.SubElement(row,ns+'c',{'r':column(j)+str(i)})
                if key in ('peso_total_nf','peso_item','quantidade','frete_original','ano_nf'):
                    ET.SubElement(cell,ns+'v').text=str(value)
                else:
                    cell.set('t','inlineStr');ET.SubElement(ET.SubElement(cell,ns+'is'),ns+'t').text=str(value)
        dimension=root.find(ns+'dimension')
        if dimension is not None:dimension.set('ref',f'A1:{column(len(PENDING_HEADERS))}{max(6,len(records)+5)}')
        for filt in root.findall(ns+'autoFilter'):filt.set('ref',f'A5:{column(len(PENDING_HEADERS))}{max(6,len(records)+5)}')
        # Timestamp não altera o contrato da primeira linha de dados.
        for cell in data.iter(ns+'c'):
            if cell.get('r')=='A3':
                cell.clear();cell.attrib.update(r='A3',t='inlineStr')
                ET.SubElement(ET.SubElement(cell,ns+'is'),ns+'t').text='Atualizado UTC: '+datetime.now(timezone.utc).isoformat()
        with ZipFile(out,'w',ZIP_DEFLATED) as archive:
            for entry in source.infolist():
                archive.writestr(entry,ET.tostring(root,encoding='utf-8',xml_declaration=True) if entry.filename==target else source.read(entry.filename))
    return out.getvalue()


def merge_pending(content,records,start,end):
    """Substitui só a janela consultada; preserva meses não consultados."""
    def key(row):
        values=tuple(str(row.get(k) or '') for k in (*NF,'chave_item'))
        if not all(values):raise ValueError('Pendência sem chave completa; revisar identificação antes de acumular.')
        return values
    merged={};previous=[]
    for row in table(content,'Pendências',PENDING_HEADERS):
        current=input_date(row['data'])
        previous.append({**{k:v for k,v in row.items() if k!='_linha'},'data':current})
        if str(start)<=current<=str(end):continue
        row={k:v for k,v in row.items() if k!='_linha'};row['data']=current
        identity=key(row)
        if identity in merged:raise ValueError('Pendência anterior duplicada; arquivo preservado.')
        merged[identity]=row
    refreshed=set()
    for row in records:
        current=input_date(row.get('data'))
        if not str(start)<=current<=str(end):raise ValueError('Pendência fora da janela consultada.')
        identity=key(row)
        if identity in refreshed:raise ValueError('Itens indistinguíveis na janela; arquivo preservado.')
        refreshed.add(identity);merged[identity]=row
    result=sorted(merged.values(),key=lambda r:(input_date(r['data']),key(r)))
    if len(result)>50000:raise ValueError('Mais de 50.000 pendências; nenhum registro foi truncado.')
    def comparable(rows):
        return sorted((tuple(str(r.get(k)) if r.get(k) not in (None,'') and k not in
            ('peso_total_nf','peso_item','quantidade','frete_original','ano_nf') else
            decimal(r[k]) if r.get(k) not in (None,'') else None for k in PENDING_HEADERS) for r in rows),key=str)
    if comparable(previous)==comparable(result):return content,len(result)
    return update_pending(content,result),len(result)


def publish_pending(path,expected_hash,updated,allowed_parts=None):
    """Arquivo temporário no mesmo volume e troca atômica; nunca salva sobre edição."""
    path=Path(path);temp=None;backup=None
    try:
        with locked(path,write=True) as handle:
            original=handle.read()
            if sha256(original).hexdigest()!=expected_hash:raise ValueError('Fretes.xlsx mudou durante a execução.')
            # Verificar preservação antes de tocar no arquivo operacional.
            with ZipFile(BytesIO(original)) as before,ZipFile(BytesIO(updated)) as after:
                if set(before.namelist())!=set(after.namelist()) or after.testzip() is not None:
                    raise ValueError('Atualização XLSX inválida.')
                ns='{'+NS+'}'
                book=ET.fromstring(before.read('xl/workbook.xml'))
                relationships={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(before.read('xl/_rels/workbook.xml.rels'))}
                if allowed_parts is None:
                    sheet=next(s for s in book.find(ns+'sheets') if s.attrib['name']=='Pendências')
                    target=relationships[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
                    target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
                    allowed_parts={target}
                if any(before.read(name)!=after.read(name) for name in before.namelist() if name not in allowed_parts):
                    raise ValueError('A atualização alteraria outra aba; arquivo original preservado.')
            folder=path.parent/'.backups';folder.mkdir(exist_ok=True)
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup=folder/f'{path.stem}.{stamp}.{expected_hash[:12]}.bak'
            with backup.open('xb') as output:
                output.write(original);output.flush();os.fsync(output.fileno())
            if sha256(backup.read_bytes()).hexdigest()!=expected_hash:
                raise ValueError('Falha na conferência do backup; original não substituído.')
            with tempfile.NamedTemporaryFile(dir=path.parent,suffix='.tmp',delete=False) as output:
                temp=Path(output.name);output.write(updated);output.flush();os.fsync(output.fileno())
        # Windows não permite substituir o destino enquanto nosso próprio handle está
        # aberto. Conferir novamente após fechá-lo. Se Excel abrir, replace falha sem
        # truncar o arquivo; nunca reabrir o original em modo de gravação destrutiva.
        if path.with_name('~$'+path.name).exists() or sha256(path.read_bytes()).hexdigest()!=expected_hash:
            raise ValueError('Fretes.xlsx entrou em edição; atualização cancelada.')
        os.replace(temp,path)
        return backup
    finally:
        if temp and temp.exists():temp.unlink()
