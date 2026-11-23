"""Mix somente leitura: parâmetros mensais homologados + FOB operacional."""
from calendar import monthrange
from datetime import date
from decimal import Decimal,InvalidOperation
from hashlib import sha256
from types import SimpleNamespace

from fob.calculator import code
from .aggregation import public
from .mix_engine import calculate,method
from .projected_result import read_months


def response(rows,closure,start,end,units,overrides=None,cache=None):
    parameters=(closure or {}).get('conteudo',{}).get('mix')
    lines=calculate(method(),parameters,rows,(closure or {}).get('conteudo'),overrides)
    count=sum(line[side]['status'] in ('pendente','conferir_calculo') for line in lines for side in ('a','b'))
    return public(dict(versao='mix-v1',periodo=dict(inicio=start,fim=end),linhas=lines,
        status=dict(parametros_importados=bool(parameters),resultados_pendentes=count,
            competencia=str(start)[:7],cache=cache,
            aviso='Parâmetros industriais do Mix ainda não homologados/importados para o mês.' if not parameters else None),
        simulacao=dict(aves=(overrides or {}).get('C4') or (parameters or {}).get('cells',{}).get('AnaliseMix',{}).get('C4'),
            peso_medio=(overrides or {}).get('C5') or (parameters or {}).get('cells',{}).get('AnaliseMix',{}).get('C5')),
        origem=dict(precos='PostgreSQL: motor FOB operacional; sem preços finais do Excel.',
            parametros='comercial.fob_fechamento_mensal.conteudo.mix' if parameters else 'Cadastro mensal Mix ausente; a prévia não é utilizada pelo Portal.',
            unidades=units,fechamento_versao=(closure or {}).get('versao'),
            metodo=method()['referencia_metodo']),
        nota='Geração de caixa é a variação percentual entre alternativas do método Excel, não um valor em reais. Zero pode indicar a melhor alternativa.'))


def execute(service,request):
    from fastapi import HTTPException
    from .feeding import _month,enabled
    if not enabled():raise HTTPException(409,'Comparativo Mix exige FOB_MASTER_ENABLED=1.')
    params=request.query_params
    if set(params)-{'data_inicio','data_fim','unidade','aves','peso_medio'}:raise HTTPException(422,'Filtro não configurado para o Mix.')
    try:
        if any(len(params.getlist(k))!=1 for k in ('data_inicio','data_fim')):raise ValueError('Informe o período.')
        start,end=(date.fromisoformat(params[k]) for k in ('data_inicio','data_fim'))
        if start>end or start<date(2026,1,1) or end>date.today() or (start.year,start.month)!=(end.year,end.month):
            raise ValueError('Consulte um único mês, desde janeiro/2026 até hoje; os parâmetros são mensais.')
        units=params.getlist('unidade') or ['10','111','180']
        if any(u not in ('10','111','180') for u in units) or len(units)>3:raise ValueError('Unidade inválida para o universo do Mix.')
        overrides={}
        for key,cell,limit in [('aves','C4',Decimal('100000000')),('peso_medio','C5',Decimal('100'))]:
            if len(params.getlist(key))>1:raise ValueError('Parâmetro de simulação repetido.')
            if params.get(key):
                value=Decimal(params[key])
                if not value.is_finite() or value<=0 or value>limit or key=='aves' and value!=value.to_integral_value():
                    raise ValueError('Informe aves inteiras e peso médio positivo dentro dos limites.')
                overrides[cell]=value
        scope=sha256(('mix\0'+request.headers.get('authorization','')+'\0'+request.headers.get('x-portal-authorization','')).encode()).hexdigest()
        reference=SimpleNamespace(period=('0001-01-01','0001-01-01'),index={})
        with service.context.banco() as conn:
            bundle,cache=_month(service,conn,start.replace(day=1),end.replace(day=monthrange(end.year,end.month)[1]),reference,scope)
            closure=read_months(conn,start,end).get(str(start)[:7])
        rows=[r for r,_ in bundle['rows'] if start<=date.fromisoformat(str(r['identificacao']['data']))<=end
              and code(r['identificacao']['unidade_documento']) in units]
        return response(rows,closure,start,end,units,overrides,cache)
    except (ValueError,InvalidOperation) as error:raise HTTPException(422,str(error)) from None
