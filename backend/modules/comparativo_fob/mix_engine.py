"""Comparativo Mix: método versionado, preços do motor FOB e parâmetros do banco."""
from collections import defaultdict
from decimal import Decimal,DecimalException,localcontext
from functools import lru_cache
import json
from pathlib import Path
import re

from fob.calculator import code
from .mix_formula import Evaluator,Range,MissingInput,FormulaError,equal,number

PRICE='PrecoMedioXEmbalagemAN-RA-RN'


@lru_cache(maxsize=1)
def method():return json.loads(Path(__file__).with_name('mix_method.json').read_text(encoding='utf-8'))


def column(value):
    n=0
    for char in value:n=n*26+ord(char)-64
    return n


def letters(n):
    result=''
    while n:n,r=divmod(n-1,26);result=chr(65+r)+result
    return result


def address(value):
    match=re.fullmatch(r'([A-Z]+)(\d*)',value)
    if not match:raise FormulaError('Referência inválida.')
    return column(match[1]),int(match[2]) if match[2] else None


def resolution(reason):
    if reason.startswith(('FOB pendente','Frete pendente')):
        return 'Abra o produto no Comparativo PM FOB e confira os itens pendentes. Corrija/valide a origem indicada no cadastro operacional de fretes ou custos e importe pelo robô; não use o FOB parcial como preço do grupo.'
    if '383' in reason and 'CPV-Frango' in reason:
        return 'Conferir o produto 383 na aba CPV-Frango com o responsável. Confirmar código e custo da competência antes do cadastro; não presumir custo zero nem usar outro produto.'
    if 'CPV-Farinha' in reason:
        return 'Responsável industrial deve confirmar o CPV-Farinha de outubro. O cabeçalho da fonte indica julho; não importar esse custo como outubro sem validação.'
    if 'BeiraRio' in reason:
        return 'Identificar e homologar a base de vendas de farinha e óleo que alimenta PreçoMedioBeiraRio; disponibilizá-la no PostgreSQL para calcular as médias. Não cadastrar a média histórica como preço final do Portal.'
    return 'Conferir o parâmetro na prévia de rendimentos/formulações/custos, validar a competência com o responsável e autorizar o cadastro mensal Mix no PostgreSQL. A prévia ainda não foi importada.'


class Reader:
    def __init__(self,spec,parameters,rows,closure=None,overrides=None,bindings=None):
        self.spec=spec;self.params=parameters or {};self.rows=rows;self.closure=closure or {};self.overrides=overrides or {}
        self.bindings=bindings or {};self.cache={};self.active=set();self.trace={};self.evaluator=Evaluator(self)
        self.products=defaultdict(list)
        for row in rows:self.products[code(row['identificacao']['produto'])].append(row)

    def cell(self,sheet,ref):
        key=(sheet,ref)
        if key in self.cache:
            self.trace[key]=self.cache[key];return self.cache[key]
        if key in self.active:raise MissingInput('Referência circular no método: '+sheet+'!'+ref)
        if len(self.active)>200:raise MissingInput('Dependência excede o limite de cálculo.')
        self.active.add(key)
        try:
            value=self._cell(sheet,ref)
            self.cache[key]=value;self.trace[key]=value;return value
        finally:self.active.remove(key)

    def _cell(self,sheet,ref):
        if (sheet,ref) in self.bindings:return self.bindings[sheet,ref]
        if sheet=='AnaliseMix' and ref in self.overrides:return Decimal(str(self.overrides[ref]))
        if sheet in self.params.get('bloqueios',{}):raise MissingInput(self.params['bloqueios'][sheet])
        if sheet not in self.spec['sheets']:
            raise MissingInput('Fonte '+sheet+' ainda não homologada no PostgreSQL. Conferir origem/competência; não copiar preço final para liberar o resultado.')
        info=self.spec['sheets'][sheet];cell=info['cells'].get(ref)
        col,rn=address(ref)
        if sheet==PRICE and letters(col) in ('D','E') and rn>=4:
            product=self.cell(sheet,'B'+str(rn));items=self.products.get(code(product),[])
            if letters(col)=='D':return sum((r['peso'] for r in items),Decimal(0))
            if any(r.get('valor_fob') is None for r in items):
                raise MissingInput('FOB pendente no produto '+code(product)+'. Conferir fretes/custos na tela Comparativo PM FOB e importar os cadastros validados.')
            return sum((r['valor_fob'] for r in items),Decimal(0))
        if cell is None:return Decimal(0)  # célula vazia conhecida do modelo, não um cadastro ausente
        if 'formula' in cell:return self.evaluator.formula(cell['formula'],sheet)
        if 'number' in cell:return Decimal(cell['number'])
        if 'text' in cell:return cell['text']
        if cell.get('input'):
            raw=self.params.get('cells',{}).get(sheet,{}).get(ref)
            if raw is not None:return Decimal(str(raw))
            # Dados industriais já importados no fechamento mensal (primeira ocorrência do PROCV).
            if sheet=='CPV-Frango':
                product=code(self.cell(sheet,'B'+str(rn)))
                entry=self.closure.get('cpv',{}).get(product,{})
                raw=entry.get('parcelas',{}).get(letters(col))
                if raw is not None:return Decimal(str(raw))
            raise MissingInput('Parâmetro '+sheet+'!'+ref+' não importado para esta competência. Conferir a prévia e homologar o cadastro no banco.')
        raise MissingInput('Origem da célula '+sheet+'!'+ref+' não confirmada.')

    def grid(self,range_):
        if range_.sheet not in self.spec['sheets']:raise MissingInput('Fonte '+range_.sheet+' não homologada no banco.')
        a,r1=address(range_.first);b,r2=address(range_.last)
        limit=self.spec['sheets'][range_.sheet]['max_row']
        r1=r1 or 1;r2=r2 or limit
        if r2-r1>500 or b-a>17000:raise FormulaError('Intervalo fora do limite do modelo.')
        return a,b,r1,min(r2,limit)

    def values(self,range_):
        a,b,r1,r2=self.grid(range_)
        if (b-a+1)*(r2-r1+1)>30000:raise FormulaError('Intervalo amplo não permitido em soma.')
        return [self.cell(range_.sheet,letters(c)+str(r)) for r in range(r1,r2+1) for c in range(a,b+1)]

    def lookup(self,value,range_,index,exact=0):
        if number(exact)!=0:raise MissingInput('PROCV aproximado não homologado.')
        a,b,r1,r2=self.grid(range_);target=a+int(number(index))-1
        if target>b:raise FormulaError('Coluna PROCV fora do intervalo.')
        for row in range(r1,r2+1):
            candidate=self.cell(range_.sheet,letters(a)+str(row))
            if equal(candidate,value) or isinstance(candidate,Decimal) and code(candidate)==code(value):
                return self.cell(range_.sheet,letters(target)+str(row))
        raise MissingInput('Código '+str(value)+' sem cadastro em '+range_.sheet+'. Conferir o cadastro da competência.')

    def raw(self,sheet,col):
        units={'FaturamentoANeRA':('10','111'),'FaturamentoRN':('180',)}
        if sheet not in units:raise MissingInput('Fonte de faturamento '+sheet+' não homologada para o Mix.')
        def value(row):
            ident=row['identificacao'];inputs=row.get('dados_entrada',{})
            if col=='X':return Decimal(code(ident['produto']))
            if col=='G':return Decimal(code(ident['unidade_documento']))
            if col=='AA':return inputs.get('familia') or row.get('familia') or ''
            if col=='AE':return row['peso']
            if col in ('BB','BC'):
                if row.get('valor_fob') is None:raise MissingInput('FOB pendente na base do Mix. Conferir custos/fretes dos itens no Comparativo FOB.')
                return row['valor_fob']
            if col=='BH':
                if row.get('frete_kg') is None:raise MissingInput('Frete pendente no grupo usado pelo Mix. Conferir Fretes.xlsx e importar o cadastro validado.')
                return row['peso']*row['frete_kg']
            raise MissingInput('Coluna de origem '+sheet+'!'+col+' não homologada.')
        return [(r,value) for r in self.rows if code(r['identificacao']['unidade_documento']) in units[sheet]]

    def sumif(self,name,args):
        if name=='SUMIF':criteria=[(args[0],args[1])];summed=args[2] if len(args)>2 else args[0]
        else:summed=args[0];criteria=list(zip(args[1::2],args[2::2]))
        # Na fonte de faturamento, os limites de linhas do arquivo são substituídos
        # pelo conjunto integral do período consultado (nunca truncar no mês seguinte).
        if summed.sheet in ('FaturamentoANeRA','FaturamentoRN'):
            total=Decimal(0)
            for row,read in self.raw(summed.sheet,re.sub(r'\d','',summed.first)):
                matches=True
                for range_,wanted in criteria:
                    if range_.sheet!=summed.sheet:raise MissingInput('Critérios de fontes distintas não homologados.')
                    getter=self.raw_value(row,re.sub(r'\d','',range_.first))
                    if not equal(getter,wanted):matches=False;break
                if matches:total+=number(read(row))
            return total
        total=Decimal(0);sums=self.values(summed);series=[self.values(r) for r,_ in criteria]
        for i,value in enumerate(sums):
            if all(i<len(values) and equal(values[i],wanted) for values,(_,wanted) in zip(series,criteria)):total+=number(value)
        return total

    def raw_value(self,row,col):
        if col=='X':return Decimal(code(row['identificacao']['produto']))
        if col=='G':return Decimal(code(row['identificacao']['unidade_documento']))
        if col=='AA':return row.get('dados_entrada',{}).get('familia') or row.get('familia') or ''
        raise MissingInput('Critério de faturamento '+col+' não homologado.')


def calculate(spec,parameters,rows,closure=None,overrides=None,bindings=None):
    result=[]
    with localcontext() as context:
        context.prec=38
        for pair in spec['comparacoes']:
            line=dict(id=pair['id'],familia_a=pair['familia_a'],familia_b=pair['familia_b'])
            for side in ('a','b'):
                reader=Reader(spec,parameters,rows,closure,overrides,bindings)
                ref=pair['celula_'+side]
                try:
                    value=reader.cell('ComparativoMix',ref)
                    if isinstance(value,str):state='sem_venda' if 'venda' in value.lower() else 'sem_preco';amount=None;reason=value
                    else:state='calculado';amount=number(value);reason=None
                    output=dict(valor=amount,status=state,motivo=reason,como_resolver=None if state=='calculado' else 'Conferir vendas/preços do grupo no período. Não substituir ausência de venda por preço de outra competência.')
                except MissingInput as error:
                    output=dict(valor=None,status='pendente',motivo=str(error),como_resolver=resolution(str(error)))
                except (FormulaError,DecimalException,ValueError) as error:
                    output=dict(valor=None,status='conferir_calculo',motivo='Fórmula sem base válida: '+str(error),como_resolver='Responsável deve conferir os denominadores, vendas e regra original antes de aprovar o cálculo. Ausência não vira zero.')
                output.update(origem='ComparativoMix!'+ref,formula=spec['sheets']['ComparativoMix']['cells'][ref].get('formula'),
                    auditoria=[dict(aba=s,celula=c,valor=v) for (s,c),v in sorted(reader.trace.items())][:250])
                line[side]=output
            result.append(line)
    return result
