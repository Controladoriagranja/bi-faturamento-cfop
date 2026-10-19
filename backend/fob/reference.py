"""Cadastros iniciais e perímetro comprovado, extraídos do Excel sem recalculá-lo."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import hashlib
from pathlib import Path
import re

from .calculator import Rate, ZERO, code, decimal, item_key
from .workbook import extract

RAW_COLUMNS = dict(B='vendedor', C='vendedor_nome', D='data', G='unidade_documento', H='serie', I='nota_numero',
    J='pedido', K='oc_principal', L='redespacho', N='frete', O='cliente', P='rede', Q='razao_social',
    U='cidade', V='uf', X='produto', Y='produto_descricao', AA='familia', AB='cfop', AE='peso',
    AI='preco_praticado', AJ='valor_produto', AL='valor_total_faturado', AM='desc_finan', AN='frete_kg')
LAYOUTS = {
    'FaturamentoANeRA':dict(end=850, channel='BC', price='BD', value='BB', costs=dict(frete='AU',comissao='AV',adicional_comissao='AW',contrato='AX',logistica_reversa='AY',pallet='AZ',descarga='BA')),
    'FaturamentoRN':dict(end=1156, channel='BD', price='BE', value='BC', costs=dict(frete='AU',comissao='AV',adicional_comissao='AW',contrato='AX',contrato_administracao='AY',logistica_reversa='AZ',pallet='BA',descarga='BB')),
    'FaturamentoJA':dict(end=352, channel=None, price=None, value='AZ', costs=dict(frete='AU',comissao='AV',adicional_comissao='AW',logistica_reversa='AX',descarga='AY')),
}


def column_number(column):
    result = 0
    for char in column: result = result*26 + ord(char)-64
    return result


def cell_value(row, column): return row.get(column, {}).get('v')


def formula(sheet, number, column):
    cell = sheet['rows'][str(number)].get(column,{})
    if cell.get('f'): return '='+cell['f']
    shared = sheet['shared_formulas'].get(cell.get('fa',{}).get('si'))
    if not shared: return ''
    start = int(re.search(r'\d+', shared['cell'])[0])
    start_column = column_number(re.match('[A-Z]+',shared['cell'])[0])
    delta_column = column_number(column)-start_column
    def translated(match):
        absolute_col,col,absolute_row,row=match.groups()
        if not absolute_col:
            index=column_number(col)+delta_column
            col=''
            while index:
                index,digit=divmod(index-1,26);col=chr(65+digit)+col
        return absolute_col+col+absolute_row+(row if absolute_row else str(int(row)+number-start))
    # Expande também R:AB nas colunas ocultas da Comissão. Preserva referências
    # absolutas e não altera texto entre aspas.
    parts = re.split(r'("(?:[^"]|"")*")',shared['f'])
    for index in range(0,len(parts),2):
        parts[index]=re.sub(r'(?<![A-Za-z0-9_])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![A-Za-z0-9_!])',translated,parts[index])
    return '='+''.join(parts)


@dataclass
class ExcelItem:
    sheet: str
    row: int
    fields: dict
    category: str
    cached: dict
    formulas: dict

    @property
    def origin(self): return f'{self.sheet}!{self.row}'


class WorkbookCatalog:
    """Snapshot do período 01–04/10/2026. Não generaliza inclusões/exclusões."""
    def __init__(self, path):
        self.path = Path(path)
        self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.sheets = extract(path,[*LAYOUTS,'Comiss','Despesas','FOBxRefaturamento','ControleFrete'],1300)
        self.sheets.update(extract(path,['FreteANeRA'],5000))
        self.commission_sheet = next(name for name in self.sheets if name.startswith('Comiss'))
        self.items = []
        self.index = {}
        for name,layout in LAYOUTS.items():
            sheet = self.sheets[name]
            for number in range(7,layout['end']+1):
                row = sheet['rows'].get(str(number),{})
                if not cell_value(row,'X'): raise ValueError(f'Linha de item ausente: {name}!{number}')
                fields = {field:cell_value(row,column) for column,field in RAW_COLUMNS.items()}
                fields['data'] = (date(1899,12,30)+timedelta(days=int(fields['data']))).isoformat()
                fields['_source'] = f'Excel:{name}!{number}'
                channel = cell_value(row,layout['channel']) if layout['channel'] else 'Varejo'
                category = 'Subprodutos' if str(fields.get('familia','')).upper()=='SUBPRODUTOS' else channel
                cached = {key:decimal(cell_value(row,column)) for key,column in layout['costs'].items()}
                cached['valor_fob'] = decimal(cell_value(row,layout['value']))
                formulas = {key:formula(sheet,number,column) for key,column in layout['costs'].items()}
                formulas['valor_fob'] = formula(sheet,number,layout['value'])
                if layout['price']: formulas['preco_fob'] = formula(sheet,number,layout['price'])
                reference = ExcelItem(name,number,fields,category,cached,formulas)
                key = item_key(fields)
                if key in self.index: raise ValueError('Identificação de item ambígua no Excel: '+str(key))
                self.items.append(reference); self.index[key]=reference
        self.tables = dict(
            commission=self.lookup(self.commission_sheet,'E','AK',5,100),
            client_contract=self.lookup('Despesas','Z','AE',4,724),
            network_contract=self.lookup('Despesas','S','X',4,161),
            reverse=self.lookup('Despesas','AS','AX'), reverse_ja=self.lookup('Despesas','AZ','BE'),
            pallet=self.lookup('Despesas','AG','AH'), unloading=self.lookup('Despesas','BG','BI'),
            cd_commission=self.lookup('Despesas','N','P',4,5), cd_additional=self.lookup('Despesas','N','Q',4,5),
            invoice_freight=self.lookup('FOBxRefaturamento','B','C',3,142),
            client_freight=self.lookup('FOBxRefaturamento','G','H',3,142),
            transport=self.lookup('ControleFrete','B','F',6,1281))
        self.freight_totals = defaultdict(lambda:[ZERO,ZERO,[]])
        for number,row in self.sheets['FreteANeRA']['rows'].items():
            if int(number)<6 or not code(cell_value(row,'O')): continue
            try: weight,total=decimal(cell_value(row,'D')),decimal(cell_value(row,'I'))
            except Exception: continue
            if weight is None or total is None: continue
            key=code(cell_value(row,'O'));record=self.freight_totals[key]
            record[0]+=weight;record[1]+=total;record[2].append(number)

    def lookup(self, sheet_name, key_column, value_column, begin=4, end=1300):
        out={}
        for number,row in self.sheets[sheet_name]['rows'].items():
            if not begin<=int(number)<=end: continue
            key=cell_value(row,key_column)
            if key in (None,''):continue
            key=code(key)
            # VLOOKUP(...,0) usa a primeira ocorrência, inclusive quando zero/vazia.
            if key not in out:
                out[key]=dict(value=cell_value(row,value_column),origin=f'{sheet_name}!{value_column}{number}',
                              formula=formula(self.sheets[sheet_name],int(number),value_column))
        return out

    def locate(self,item): return self.index.get(item_key(item))

    def components(self,item,reference):
        unit,seller,client,network=(code(item.get(k)) for k in ('unidade_documento','vendedor','cliente','rede'))
        weight,total=decimal(item.get('peso')),decimal(item.get('valor_total_faturado'))
        if total is None: raise ValueError('valor_total_faturado ausente (base dos contratos/comissão JA).')
        out={}
        def put(key,value,origin,inputs=None,status='calculado'):
            expression=reference.formulas.get(key) or ('0 (literal no Excel)' if key=='adicional_comissao' and unit!='102' else 'não deduzido nesta unidade pelo Excel')
            out[key]=Rate(value,origin,expression,status,inputs)
        def rate(table,key,default=None):
            record=self.tables[table].get(key)
            return (decimal(record['value']) or ZERO,record['origin']) if record else default
        reverse_key=';'.join((unit,code(item.get('produto')),str(item.get('uf') or '').strip()))
        if unit=='102':
            for component,table in [('comissao','cd_commission'),('adicional_comissao','cd_additional')]:
                found=rate(table,unit)
                if found is None: put(component,None,f'Cadastro ausente: {table}/{unit}',status='pendente_cadastro')
                else: put(component,total*found[0]/weight,found[1],{'base_nf':total,'percentual':found[0],'peso':weight})
            reverse_table='reverse_ja'
        else:
            found=rate('commission',seller)
            if found is None:put('comissao',None,f'Comissão sem vendedor {seller}',status='pendente_cadastro')
            else:put('comissao',found[0],found[1],{'cadastro':'AK já calculado no Excel para este período'},'cadastro_snapshot_excel')
            put('adicional_comissao',ZERO,f'{reference.sheet}!AW{reference.row} (literal 0)')
            found=rate('client_contract',client) or rate('network_contract',network)
            put('contrato',total*found[0]/weight if found else ZERO,found[1] if found else 'IFERROR dos dois VLOOKUPs: 0',{'base_nf':total,'peso':weight,'percentual':found[0] if found else ZERO})
            if unit=='180':put('contrato_administracao',Decimal('0.25')+Decimal('0.07')+Decimal('0.06'),f'FaturamentoRN!AY{reference.row}: =0.25+0.07+0.06')
            pallet_value=decimal(self.sheets['Despesas']['rows']['3']['AI']['v'])
            put('pallet',pallet_value/1000 if client in self.tables['pallet'] else ZERO,'Despesas!AG:AH e AI3',{'valor_pallet':pallet_value,'cliente_consta_cadastro':client in self.tables['pallet']})
            reverse_table='reverse'
        found=rate(reverse_table,reverse_key)
        if found is None:put('logistica_reversa',None,f'VLOOKUP sem chave {reverse_key}',status='pendente_cadastro')
        else:put('logistica_reversa',found[0],found[1],{'chave':reverse_key})
        found=rate('unloading',client)
        put('descarga',found[0] if found else ZERO,found[1] if found else 'IFERROR VLOOKUP descarga: 0')
        # Sem criar deduções inexistentes no cálculo de Januária.
        for key in ('contrato','contrato_administracao','pallet'):
            if key not in out:put(key,ZERO,'Não integra a fórmula FOB desta unidade no Excel')
        return out

    def freight(self,item,reference):
        raw=decimal(item.get('frete_kg'))
        kind=code(item.get('frete'));redelivery=code(item.get('redespacho'))
        def result(value,origin):return Rate(value,origin,reference.formulas['frete'],'calculado' if value is not None else 'pendente_dado')
        if code(item.get('unidade_documento'))=='102':
            if kind in ('2','3','4','5','9'):return result(ZERO,'FaturamentoJA: tipo de frete > 1')
            return Rate(None,'Arquivo externo [1]Fev26/[1]Mai26; informar frete manual',reference.formulas['frete'],'pendente_manual')
        if redelivery:
            found=self.tables['transport'].get(redelivery)
            extra=ZERO
            if found and found['value'] not in (None,'','26024 - COOPERATIVA DE TRANSPORTE MONT'):
                for n,row in self.sheets['ControleFrete']['rows'].items():
                    if code(cell_value(row,'B'))==code(item.get('oc_principal')) and code(cell_value(row,'AC'))==code(item.get('unidade_documento')):
                        extra+=decimal(cell_value(row,'AB')) or ZERO
            return result(raw+extra if raw is not None else None,'ControleFrete!B:F / AB:AC + frete_kg; IFERROR interno=0')
        if kind in ('2','3','4','5','9'):return result(ZERO,'Tipos 2/3/4/5/9 sem redespacho: 0')
        for table,key in [('invoice_freight',code(item.get('nota_numero'))),('client_freight',code(item.get('cliente')))]:
            found=self.tables[table].get(key)
            if found:return result(decimal(found['value']) or ZERO,found['origin'])
        weight,total,_=self.freight_totals.get(code(item.get('cliente')),(ZERO,ZERO,[]))
        if weight:
            return Rate(total/weight,'FreteANeRA!I:I / D:D, agrupado por O:O (cliente, todas as unidades)',reference.formulas['frete'],inputs={'peso_transportado':weight,'total_frete':total})
        return result(raw,'IFERROR externo da fórmula: frete_kg da origem')
