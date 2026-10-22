"""Painel somente leitura. Sem nova permissão de escrita e sem campos salariais."""
from datetime import date
from fastapi import APIRouter,Depends,HTTPException,Query
from fob.master_data import invoice_key,pending_rows
from fob.master_repository import read_candidates,read_invoices,read_monthly,read_status
from .aggregation import public
from .feeding import enabled


def create_costs_router(banco):
    from comercial_acesso import authorize,current
    router=APIRouter(prefix='/api/comercial/comparativo-fob/custos',tags=['Custos FOB'],dependencies=[Depends(authorize)])
    def check():
        if not enabled():raise HTTPException(503,'Nova alimentação ainda não homologada; modo anterior preservado.')
        # Não presumir que a autorização de edição implica acesso geral aos dados.
        if current().mode!='general':
            raise HTTPException(403,'Painel disponível apenas para alcance comercial geral; recorte por equipe ainda não homologado.')

    @router.get('/status')
    def status():
        check()
        try:
            with banco() as conn:
                data=read_status(conn)
                data['competencias_januaria']=read_monthly(conn)
                data['cadastros']=conn.execute('''SELECT tipo,count(*) quantidade,min(inicio) inicio,max(fim) fim
                    FROM comercial.fob_cadastro WHERE ativo GROUP BY tipo ORDER BY tipo''').fetchall()
            # Não retornar identidade CENTRAL, salários, parâmetros de folha ou JSON de cadastro.
            data['competencias_januaria']=[{k:r[k] for k in ('competencia','custo_kg','versao','atualizado_em')} for r in data['competencias_januaria']]
            return public(data)
        except Exception:raise HTTPException(503,'Não foi possível ler a situação da alimentação.') from None

    @router.get('/pendencias')
    def pendencias(data_inicio:date,data_fim:date,pagina:int=Query(1,ge=1,le=10000),por_pagina:int=Query(50,ge=1,le=200)):
        check()
        if not 0<=(data_fim-data_inicio).days<=31:raise HTTPException(422,'Consulte até 32 dias inclusivos.')
        try:
            with banco() as conn:
                rows=read_candidates(conn,data_inicio,data_fim)
                invoices=read_invoices(conn,[invoice_key(i) for i in rows])
                records=pending_rows(rows,invoices)
                from fob.master_data import MasterCatalog
                from fob.master_repository import read_current
                catalog=MasterCatalog(read_current(conn,data_inicio,data_fim),invoices=invoices)
                for original,record in zip(rows,records):
                    rate=catalog.freight(original)
                    record.update(custo_kg=rate.value,origem_custo=rate.origin,status_custo=rate.status)
            return public(dict(linhas=records[(pagina-1)*por_pagina:pagina*por_pagina],
                               total_registros=len(records),pagina=pagina,por_pagina=por_pagina))
        except ValueError as error:raise HTTPException(422,str(error)) from None
        except Exception:raise HTTPException(503,'Não foi possível ler as pendências. A view de frete manual não é utilizada.') from None
    return router
