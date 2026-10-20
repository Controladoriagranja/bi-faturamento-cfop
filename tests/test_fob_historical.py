"""Verificação curta com conexão simulada. Não inicia API nem consulta banco."""
from contextlib import contextmanager
from datetime import date
from decimal import Decimal as D
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
# A máquina de frontend não precisa instalar FastAPI para verificar SQL/serialização.
try:
    import fastapi
except ImportError:
    fastapi=ModuleType('fastapi')
    class HTTPException(Exception):
        def __init__(self,status_code,detail):self.status_code=status_code;self.detail=detail
    fastapi.HTTPException=HTTPException
    sys.modules['fastapi']=fastapi
from modules.comparativo_fob.historical import aggregate_groups,audit_item,execute_history
from modules.comparativo_fob.service import ComparativoFOBService


class Params(dict):
    def getlist(self,key):return [self[key]] if key in self else []


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.group=dict(familia='PEITO',canal='Sem Vínculo',itens=2,peso=D('40'),
            pesos_ausentes=0,precos_ausentes=0,valor_praticado_observado=D('400'))
        self.row=dict(id=1,data=date(2026,1,1),familia_grupo='PEITO',canal_grupo='Sem Vínculo',
            peso=D(20),preco_praticado=D(10),frete='1',frete_kg=D(0))
        test=self
        class Conn:
            def execute(self,sql,params):
                test.calls.append((sql,params))
                return SimpleNamespace(fetchall=lambda:[test.row] if 'SELECT * FROM filtrado ORDER BY' in sql else [test.group])
        @contextmanager
        def banco():yield Conn()
        self.context=SimpleNamespace(banco=banco)

    def test_no_invented_expenses_or_excel_and_unknown_channels_retained(self):
        result=execute_history(self.context,'resumo',date(2026,1,1),date(2026,1,31),
            dict(unidade=[],familia=[],canal=[]),'',lambda k,d='':d)
        self.assertEqual(result['total']['peso'],'40')
        self.assertEqual(D(result['total']['preco_praticado_kg']),D(10))
        self.assertEqual(result['total']['pendentes'],2)
        for key in ('valor_fob','valor_fob_excel','valor_fob_parcial'):self.assertIsNone(result['total'][key])
        self.assertIn('Sem Vínculo',[g['canal'] for g in result['canais']])
        self.assertTrue(all(g['media_kg'] is None for g in result['total']['componentes'].values()))

    def test_pagination_and_filters_are_bound_parameters(self):
        params=dict(pagina='2',por_pagina='50',ordenar_por='peso',ordem='desc')
        result=execute_history(self.context,'detalhes',date(2026,1,1),date(2026,1,31),
            dict(unidade=['111'],familia=["x' OR TRUE --"],canal=[]),'a%_',lambda k,d='':params.get(k,d))
        sql,args=self.calls[-1]
        self.assertNotIn("x' OR TRUE",sql);self.assertIn(["x' OR TRUE --"],args)
        self.assertEqual(args[-2:],[50,50]);self.assertIn('peso desc NULLS LAST, id ASC',sql)
        self.assertEqual(result['linhas'][0]['componentes']['frete']['status'],'pendente_manual')
        self.assertTrue(all(sql.lstrip().startswith('WITH ') for sql,_ in self.calls))

    def test_missing_weight_or_price_prevents_practiced_average(self):
        self.group['precos_ausentes']=1
        self.assertIsNone(aggregate_groups([self.group])['preco_praticado_kg'])

    def test_service_dispatches_january_and_preserves_reference_path(self):
        catalog=SimpleNamespace(period=('2026-10-01','2026-10-04'))
        service=ComparativoFOBService(self.context)
        with patch('modules.comparativo_fob.service.load_catalog',return_value=catalog):
            result=service.execute('resumo',SimpleNamespace(query_params=Params(data_inicio='2026-01-01',data_fim='2026-01-31')))
            self.assertEqual(result['contexto']['modo'],'historico')
            with patch.object(service,'_read',side_effect=RuntimeError('reference path')):
                with self.assertRaisesRegex(RuntimeError,'reference path'):
                    service.execute('resumo',SimpleNamespace(query_params=Params()))

    def test_disallows_dynamic_sort_injection(self):
        with self.assertRaises(fastapi.HTTPException):
            execute_history(self.context,'detalhes',date(2026,1,1),date(2026,1,31),{},'',
                lambda k,d='': 'peso; DELETE' if k=='ordenar_por' else d)
        self.assertEqual(self.calls,[])


if __name__=='__main__':unittest.main(verbosity=2)
