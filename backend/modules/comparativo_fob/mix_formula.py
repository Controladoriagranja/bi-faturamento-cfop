"""Avaliação limitada do método Mix: sem eval, macros, arquivos ou execução de código."""
from dataclasses import dataclass
from decimal import Decimal, DecimalException
import re


class MissingInput(Exception):
    """Ausência de cadastro não é um erro que IFERROR possa transformar em zero."""


class FormulaError(Exception):pass


@dataclass(frozen=True)
class Range:
    sheet:str
    first:str
    last:str


REFERENCE=re.compile(r"(?:(?:'(?P<quoted>[^']+)'|(?P<sheet>[\w]+))!)?(?P<address>\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?|\$?[A-Z]{1,3}:\$?[A-Z]{1,3})(?![\w])")


def parse(source, sheet):
    tokens=[];pos=0;source=source.lstrip('=')
    while pos<len(source):
        if source[pos].isspace():pos+=1;continue
        match=REFERENCE.match(source,pos)
        if match:
            target=match['quoted'] or match['sheet'] or sheet;address=match['address'].replace('$','')
            tokens.append(('ref',(target,address)));pos=match.end();continue
        match=re.match(r'"(?:[^"]|"")*"',source[pos:])
        if match:tokens.append(('text',match[0][1:-1].replace('""','"')));pos+=len(match[0]);continue
        match=re.match(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?',source[pos:])
        if match:tokens.append(('number',Decimal(match[0])));pos+=len(match[0]);continue
        match=re.match(r'[A-Za-z_][A-Za-z_0-9.]*',source[pos:])
        if match:tokens.append(('name',match[0].upper()));pos+=len(match[0]);continue
        match=re.match(r'>=|<=|<>|[=><+*/^(),-]',source[pos:])
        if not match:raise MissingInput('Método contém uma expressão não suportada; conferir a fórmula de origem.')
        tokens.append((match[0],match[0]));pos+=len(match[0])
    tokens.append(('end','end'));cursor=0
    precedence={'=':10,'<>':10,'>':10,'<':10,'>=':10,'<=':10,'+':20,'-':20,'*':30,'/':30,'^':40}
    def expression(minimum=0):
        nonlocal cursor
        kind,value=tokens[cursor];cursor+=1
        if kind in ('number','text','ref'):left=(kind,value)
        elif kind in ('+','-'):left=('unary',kind,expression(35))
        elif kind=='(':
            left=expression()
            if tokens[cursor][0]!=')':raise FormulaError('Parêntese inválido.')
            cursor+=1
        elif kind=='name':
            if value in ('TRUE','FALSE') and tokens[cursor][0]!='(':left=('number',Decimal(value=='TRUE'))
            else:
                if tokens[cursor][0]!='(':raise FormulaError('Função inválida.')
                cursor+=1;args=[]
                if tokens[cursor][0]!=')':
                    while True:
                        args.append(expression())
                        if tokens[cursor][0]!=',':break
                        cursor+=1
                if tokens[cursor][0]!=')':raise FormulaError('Argumentos inválidos.')
                cursor+=1;left=('call',value,args)
        else:raise FormulaError('Expressão inválida.')
        while tokens[cursor][0] in precedence and precedence[tokens[cursor][0]]>=minimum:
            op=tokens[cursor][0];cursor+=1
            left=('binary',op,left,expression(precedence[op]+(0 if op=='^' else 1)))
        return left
    result=expression()
    if tokens[cursor][0]!='end':raise FormulaError('Expressão incompleta.')
    return result


def number(value):
    if value is None:return Decimal(0)
    if isinstance(value,(Decimal,int,bool)):return Decimal(value)
    raise FormulaError('Operação numérica contém texto: '+str(value))


def equal(left,right):
    if isinstance(left,str) and isinstance(right,str):return left.casefold()==right.casefold()
    return left==right


class Evaluator:
    def __init__(self,reader):self.reader=reader;self.parsed={}

    def formula(self,source,sheet):
        key=(source,sheet)
        if key not in self.parsed:self.parsed[key]=parse(source,sheet)
        return self.evaluate(self.parsed[key])

    def evaluate(self,node):
        kind=node[0]
        if kind in ('number','text'):return node[1]
        if kind=='ref':
            sheet,address=node[1]
            if ':' in address:return Range(sheet,*address.split(':'))
            return self.reader.cell(sheet,address)
        if kind=='unary':return number(self.evaluate(node[2]))*(-1 if node[1]=='-' else 1)
        if kind=='binary':
            op=node[1];a=self.evaluate(node[2]);b=self.evaluate(node[3])
            if op=='=':return equal(a,b)
            if op=='<>':return not equal(a,b)
            if op in ('>','<','>=','<='):
                if not isinstance(a,str) or not isinstance(b,str):a,b=number(a),number(b)
                return {'>':lambda:a>b,'<':lambda:a<b,'>=':lambda:a>=b,'<=':lambda:a<=b}[op]()
            a,b=number(a),number(b)
            return {'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a/b,'^':lambda:a**b}[op]()
        name,args=node[1:]
        if name=='IF':return self.evaluate(args[1] if self.evaluate(args[0]) else args[2])
        if name=='IFERROR':
            try:return self.evaluate(args[0])
            except (FormulaError,DecimalException):return self.evaluate(args[1])
        if name in ('AND','OR'):
            values=[bool(self.evaluate(arg)) for arg in args]
            return all(values) if name=='AND' else any(values)
        values=[self.evaluate(arg) for arg in args]
        def flatten(value):return self.reader.values(value) if isinstance(value,Range) else [value]
        if name=='SUM':return sum((v for arg in values for v in flatten(arg) if isinstance(v,(Decimal,int,bool))),Decimal(0))
        if name=='LARGE':
            numbers=sorted((number(v) for v in flatten(values[0]) if not isinstance(v,str)),reverse=True)
            try:return numbers[int(number(values[1]))-1]
            except IndexError:raise FormulaError('Posição LARGE fora da base.') from None
        if name=='VLOOKUP':return self.reader.lookup(*values)
        if name in ('SUMIF','SUMIFS'):return self.reader.sumif(name,values)
        raise MissingInput('Função '+name+' depende de uma fonte/regra ainda não homologada no Mix.')
