from core.contracts import RouteSet
def build_routes(service, context):
    # Reutiliza /api/bi/{bi}/... do roteador compartilhado, sem outra FastAPI.
    return RouteSet(bi_services={service.key:service})
