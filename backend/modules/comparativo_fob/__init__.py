"""Projeto FOB. Descoberta pelo contrato modular; importável no legado sem core."""
def __getattr__(name):
    if name=='MODULE':
        from core.contracts import ModuleSpec
        from .config import CONFIG
        return ModuleSpec('comparativo_fob',46,('main',),CONFIG)
    raise AttributeError(name)
