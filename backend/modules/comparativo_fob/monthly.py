"""Cadastro mensal: utiliza autenticação e writer da API final de frete manual."""
import logging
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from fob.freight import MONTHLY_TABLE, OCTOBER, competence, monthly_rate

logger=logging.getLogger(__name__)
MONTHLY_PATH='/api/comercial-html/fretes-manuais/custos-januaria'


def public(value):
    # Mesmo formato decimal plano da API final de fretes (inclusive zero NUMERIC).
    if isinstance(value,Decimal):return format(value,'f')
    if hasattr(value,'isoformat'):return value.isoformat()
    if isinstance(value,dict):return {k:public(v) for k,v in value.items()}
    if isinstance(value,list):return [public(v) for v in value]
    return value


def parse_competence(value):
    if not isinstance(value,str) or len(value)!=7 or value[4]!='-':raise ValueError('Use competência AAAA-MM.')
    result=competence(value)
    if not 2000<=result.year<=2100 or result.strftime('%Y-%m')!=value:raise ValueError('Competência inválida (2000–2100).')
    return result


class MonthlyCost(BaseModel):
    model_config=ConfigDict(extra='forbid')
    competencia:str
    custo_kg:Decimal=Field(ge=0,max_digits=18,decimal_places=10,allow_inf_nan=False)
    versao:int=Field(ge=0,le=2147483646,strict=True)

    @field_validator('competencia')
    @classmethod
    def validate_competence(cls,value):parse_competence(value);return value

    @field_validator('custo_kg',mode='before')
    @classmethod
    def reject_bool(cls,value):
        if isinstance(value,bool):raise ValueError('Custo decimal inválido.')
        return value


def query_costs(conn,requested,page,size):
    selected=conn.execute('SELECT * FROM '+MONTHLY_TABLE+' WHERE competencia IN (%s,%s)',[requested,OCTOBER]).fetchall()
    mapping={r['competencia']:r for r in selected}
    own=mapping.get(requested)
    applied=monthly_rate(requested,mapping)
    rows=conn.execute('SELECT * FROM '+MONTHLY_TABLE+' ORDER BY competencia DESC LIMIT %s OFFSET %s',
                      [size+1,(page-1)*size]).fetchall()
    return public(dict(competencia=requested.strftime('%Y-%m'),custo_proprio=own,
        custo_aplicado=dict(custo_kg=applied.value,status=applied.status,origem=applied.origin,**applied.inputs),
        custos=rows[:size],pagina=page,tem_proxima=len(rows)>size))


def save_cost(writer,item,user_id):
    day=parse_competence(item.competencia)
    if item.versao==0:
        row=writer.execute('INSERT INTO '+MONTHLY_TABLE+''' (competencia,custo_kg,criado_por,atualizado_por)
            VALUES (%s,%s,%s,%s) ON CONFLICT (competencia) DO NOTHING RETURNING *''',
            [day,item.custo_kg,user_id,user_id]).fetchone()
    else:
        row=writer.execute('UPDATE '+MONTHLY_TABLE+''' SET custo_kg=%s,atualizado_por=%s,
            atualizado_em=clock_timestamp(),versao=versao+1
            WHERE competencia=%s AND versao=%s RETURNING *''',
            [item.custo_kg,user_id,day,item.versao]).fetchone()
    if row is None:raise HTTPException(409,'Custo mensal alterado por outra sessão. Consulte novamente e revise o valor.')
    return row


def create_monthly_router(banco,escrita=None,authorize=None):
    # Imports da API fornecida; nenhuma identidade/permissão é reinventada aqui.
    from frete_manual import banco_escrita
    from frete_manual_auth import authorize_frete
    import psycopg
    escrita=escrita or banco_escrita;authorize=authorize or authorize_frete
    router=APIRouter(prefix=MONTHLY_PATH,tags=['Custo mensal Januária'])

    @router.get('')
    def consultar(competencia:str,pagina:int=Query(1,ge=1,le=1000),tamanho:int=Query(20,ge=1,le=100),
                  user_id:str=Depends(authorize)):
        try:day=parse_competence(competencia)
        except ValueError as error:raise HTTPException(422,str(error)) from None
        try:
            with banco() as conn:return query_costs(conn,day,pagina,tamanho)
        except psycopg.Error:
            logger.warning('Falha PostgreSQL ao consultar custos mensais.')
            raise HTTPException(503,'Não foi possível consultar os custos mensais.') from None

    @router.put('')
    def salvar(item:MonthlyCost,user_id:str=Depends(authorize)):
        try:
            with escrita() as conn:row=save_cost(conn,item,user_id)
            return dict(ok=True,custo=public(row))
        except (psycopg.errors.SerializationFailure,psycopg.errors.DeadlockDetected,psycopg.errors.LockNotAvailable):
            raise HTTPException(409,'Conflito concorrente. Consulte a competência novamente.') from None
        except psycopg.Error:
            logger.warning('Gravação mensal não confirmada.')
            raise HTTPException(503,'Não foi possível confirmar a gravação. Consulte antes de reenviar.') from None
    return router
