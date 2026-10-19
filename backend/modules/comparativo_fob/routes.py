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
    return RouteSet(routers=[(46,create_router(service))])
