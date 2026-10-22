"""Rotas próprias, com autenticação e conexão herdadas da aplicação existente."""
from fastapi import APIRouter, Request
from .config import CONFIG


def create_router(service):
    router=APIRouter(prefix=CONFIG['prefix'],tags=['Comparativo FOB'])
    @router.get('/filtros')
    def filtros(request:Request):return service.execute('filtros',request)
    @router.get('/resumo')
    def resumo(request:Request):return service.execute('resumo',request)
    @router.get('/detalhes')
    def detalhes(request:Request):return service.execute('detalhes',request)
    return router


def build_routes(service,context):
    from core.contracts import RouteSet
    from .monthly import create_monthly_router
    from .costs_views import create_costs_router
    return RouteSet(routers=[(46,create_router(service)),(47,create_monthly_router(context.banco)),
                            (48,create_costs_router(context.banco))])


def create_integrated_router(context):
    from .service import build_service
    from .monthly import create_monthly_router
    router=APIRouter()
    router.include_router(create_router(build_service(context)))
    router.include_router(create_monthly_router(context.banco))
    from .costs_views import create_costs_router
    router.include_router(create_costs_router(context.banco))
    return router
