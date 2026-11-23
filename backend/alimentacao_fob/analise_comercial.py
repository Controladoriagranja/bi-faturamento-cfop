"""Cópia e prévia mensal. A origem é exclusivamente lida; não abre PostgreSQL."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

SOURCE = Path(r'\\192.168.1.139\Controladoria\Paulo\FechamentoCusto\Fechamento\03.AnaliseComercial.xlsx')
DESTINATION = Path(r'\\192.168.1.139\Controladoria\BI_Granja\Planilhas_BI\Faturamento-CFOP')
MONTHS = ('Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez')
NS = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def text(value):
    return ''.join(c for c in unicodedata.normalize('NFD',str(value)) if not unicodedata.combining(c)).lower().strip()


def month_sheet(competence):
    if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', competence):
        raise ValueError('Informe a competência como AAAA-MM, por exemplo 2026-10.')
    year,month = map(int,competence.split('-'))
    return MONTHS[month-1]+str(year)[-2:]


def preview(content, competence):
    sheet = month_sheet(competence)
    try:
        with ZipFile(BytesIO(content)) as archive:
            workbook = ET.fromstring(archive.read('xl/workbook.xml'))
            calc = workbook.find('m:calcPr',NS)
            if calc is not None and calc.get('calcMode') == 'manual':
                raise ValueError('Arquivo em cálculo manual. Recalcule e salve no Excel antes de copiar.')
            matches = [s for s in workbook.find('m:sheets',NS) if s.get('name') == sheet]
            if len(matches) != 1:raise ValueError(f'Aba {sheet} ausente ou ambígua. Nenhuma outra competência será usada.')
            rels = {r.get('Id'):r.get('Target') for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
            target = rels[matches[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            target = target.lstrip('/') if target.startswith('/') else 'xl/'+target
            strings = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                for element in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si',NS):
                    strings.append(''.join(n.text or '' for n in element.iterfind('.//m:t',NS)))
            cells = {}
            for row in ET.fromstring(archive.read(target)).findall('m:sheetData/m:row',NS):
                if not 74 <= int(row.get('r')) <= 110:continue
                for cell in row.findall('m:c',NS):
                    value = cell.find('m:v',NS); raw = value.text if value is not None else None
                    kind = cell.get('t'); formula = cell.find('m:f',NS)
                    if kind == 's': raw = strings[int(raw)] if raw is not None else None
                    if kind == 'inlineStr':raw = ''.join(n.text or '' for n in cell.iterfind('.//m:t',NS))
                    cells[cell.get('r')] = dict(valor=raw,formula=formula.text if formula is not None else None,tipo=kind)
    except (BadZipFile,KeyError,ET.ParseError,IndexError) as error:
        raise ValueError('Arquivo XLSX inválido ou estrutura não reconhecida; cópia cancelada.') from error
    for address,label in [('A76','comercial'),('A77','comissao'),('A78','logistica'),('A109','totais'),('A110','despesa financeira')]:
        if label not in text(cells.get(address,{}).get('valor','')):
            raise ValueError(f'Layout de {sheet}!{address} mudou. Revise o mapeamento antes de importar.')
    for address,label in [('C75','ave nova'),('D75','real alimentos'),('E75','escritorio pm'),('F75','januaria'),('G75','neves')]:
        if label not in text(cells.get(address,{}).get('valor','')):
            raise ValueError(f'Coluna {sheet}!{address} não corresponde ao cadastro conhecido.')

    def number(address, optional=False):
        cell = cells.get(address,{})
        value = cell.get('valor')
        if value in (None,''):
            if optional and not cell.get('formula'):return Decimal(0)
            raise ValueError(f'{sheet}!{address} sem valor salvo. Recalcule e salve no Excel; vazio não é zero.')
        try:
            result = Decimal(value)
            if not result.is_finite() or cell.get('tipo') == 'e':raise InvalidOperation
            return result
        except (InvalidOperation,ValueError,TypeError) as error:
            raise ValueError(f'{sheet}!{address} não contém um valor numérico válido.') from error

    commercial = sum((number(f'{col}76') for col in 'CDEFG'),Decimal(0))
    commission = sum((number(f'{col}77') for col in 'CDEFG'),Decimal(0))
    logistics = sum((number(f'{col}{row}') for col in 'CDEFG' for row in (78,79)),Decimal(0))
    administration = number('C109'); financial = number('C110')
    admin_check = sum((number(f'{col}{row}',True) for col in 'CD' for row in range(82,109)),Decimal(0))
    if abs(administration-admin_check)>Decimal('.005'):
        raise ValueError(f'{sheet}!C109 não confere com C82:D108. Salve os cálculos atualizados.')
    formula = cells.get('C89',{}).get('formula') or ''
    match = re.fullmatch(r'\s*([0-9]+(?:\.[0-9]+)?)\s*-\s*\$?E\$?76\s*-\s*\$?E\$?78\s*',formula,re.I)
    if match and abs(number('C89')-(Decimal(match[1])-number('E76')-number('E78')))>Decimal('.005'):
        raise ValueError(f'{sheet}!C89 não confere com a base e as deduções; cópia cancelada.')
    return dict(competencia=competence,aba=sheet,estado='PREVIA_NAO_IMPORTADA',
        valores={k:str(v) for k,v in dict(despesa_administrativa=administration,despesa_financeira=financial,
            comercial_total= commercial,comissao_total=commission,comercial_sem_comissao=commercial-commission,
            logistica_total=logistics).items()},
        conta_c89=dict(base_digitada=match[1] if match else None,deducao_e76=str(number('E76')),
            deducao_e78=str(number('E78')),resultado=str(number('C89')),formula=formula),
        origem_celulas={a:cells[a] for a in cells if a in ('C89','C109','C110') or re.fullmatch('[C-G](76|77|78|79)',a)},
        avisos=['Valores são os salvos pelo Excel; o robô não recalcula fórmulas nem atualiza vínculos externos.',
                'Não grava no PostgreSQL nem muda a competência/regra usada pelo Portal.'])


def digest(data):return sha256(data).hexdigest()


def file_error(action, path, error):
    reason = ('caminho/arquivo não encontrado ou compartilhamento indisponível' if isinstance(error,FileNotFoundError)
              else 'acesso negado nesta sessão do Windows' if isinstance(error,PermissionError)
              else 'falha de acesso ao arquivo ou à rede')
    number = getattr(error,'winerror',None) or getattr(error,'errno',None)
    return ValueError(f'{action}: {path}. Motivo: {reason} (código {number}).')


def resolve_path(path, role):
    try:return Path(path).resolve()
    except OSError as error:raise file_error('Não foi possível localizar '+role,path,error) from None


def stable_read(source):
    if source.name.startswith('~$'):
        raise ValueError('Origem aberta no Excel; aguarde salvar e fechar. O robô não bloqueará o arquivo.')
    try:
        before = source.stat()
        if source.with_name('~$'+source.name).exists():
            raise ValueError('Origem aberta no Excel; aguarde salvar e fechar. O robô não bloqueará o arquivo.')
        content = source.read_bytes(); after = source.stat()
    except OSError as error:raise file_error('Não foi possível ler a planilha de origem',source,error) from None
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or len(content)!=after.st_size:
        raise ValueError('Origem mudou durante a leitura. Nenhuma cópia foi publicada.')
    return content, (after.st_size,after.st_mtime_ns)


def atomic_write(path, content):
    path.parent.mkdir(parents=True,exist_ok=True)
    handle,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(handle,'wb') as stream:stream.write(content)
        if digest(Path(name).read_bytes())!=digest(content):raise ValueError('Cópia temporária não conferiu.')
        os.replace(name,path)
    finally:
        if Path(name).exists():Path(name).unlink()


def prepare(competence, source=SOURCE, destination=DESTINATION, copy=False):
    try:return _prepare(competence,source,destination,copy)
    except OSError as error:
        failed = getattr(error,'filename',None) or str(destination)
        raise file_error('Falha durante a cópia/preparação',failed,error) from None


def _prepare(competence, source, destination, copy):
    month_sheet(competence)
    source=resolve_path(source,'a origem'); destination=resolve_path(destination,'o destino')
    # Nem arquivos temporários, backups ou relatórios podem ser criados na origem.
    if destination==source.parent or source.parent in destination.parents or destination in source.parents:
        raise ValueError('Origem e destino devem ser separados; escrita na pasta de origem é proibida.')
    content,stamp=stable_read(source)
    report=preview(content,competence); version=digest(content)
    report.update(arquivo_origem=str(source),arquivo_sha256=version,origem_mtime_ns=stamp[1],
                  copia_publicada=False,banco_alterado=False)
    if not copy:return report
    target=destination/source.name
    if target.with_name('~$'+target.name).exists():raise ValueError('Cópia de destino aberta no Excel. Nada será substituído.')
    previous=target.read_bytes() if target.exists() else None
    state=destination/'.analise-comercial'
    report_path=state/'previas'/competence/(version+'.json')
    changed=previous is None or digest(previous)!=version
    # Valida novamente a origem antes de publicar; nunca abre para escrita ou impõe lock.
    check,check_stamp=stable_read(source)
    if digest(check)!=version or check_stamp!=stamp:raise ValueError('Origem mudou; repita após salvar e fechar.')
    backup=None
    if changed and previous is not None:
        backup=state/'backups'/(digest(previous)+'.xlsx')
        if backup.exists():
            if digest(backup.read_bytes())!=digest(previous):raise ValueError('Backup existente não confere.')
        else:atomic_write(backup,previous)
    # Mantém um retrato por versão, inclusive na primeira cópia.
    snapshot=state/'versoes'/(version+'.xlsx')
    if snapshot.exists():
        if digest(snapshot.read_bytes())!=version:raise ValueError('Retrato da versão não confere.')
    else:atomic_write(snapshot,content)
    current=target.read_bytes() if target.exists() else None
    if (current is None)!=(previous is None) or (current is not None and digest(current)!=digest(previous)):
        raise ValueError('Destino mudou durante o processamento; substituição cancelada.')
    if changed:atomic_write(target,content)
    report.update(copia_publicada=True,copia_alterada=changed,destino=str(target),
        backup=str(backup) if backup else None,previa=str(report_path),snapshot=str(snapshot))
    if not report_path.exists():
        saved=dict(report,preparado_em=datetime.now(timezone.utc).isoformat())
        atomic_write(report_path,json.dumps(saved,ensure_ascii=False,indent=2).encode('utf-8'))
    return report
