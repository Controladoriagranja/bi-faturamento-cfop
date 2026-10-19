"""Testes rápidos do motor. Não conectam ao PostgreSQL nem executam jobs."""
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from fob.calculator import ManualFreight, calculate_item
from fob.reference import WorkbookCatalog, formula
from fob.repository import read_invoice


class CatalogFake:
    def locate(self,item):
        from types import SimpleNamespace
        return SimpleNamespace(category='Varejo',origin='Teste') if item.get('nota_numero')=='1' else None
    def components(self,item,reference):
        from fob.calculator import Rate
        return {'comissao':Rate(Decimal('0.1'),'cadastro de teste')}
    def freight(self,item,reference):
        from fob.calculator import Rate
        return Rate(Decimal('0.2'),'frete calculado de teste')


class FOBTest(unittest.TestCase):
    def setUp(self):
        self.catalog=CatalogFake()
        self.item=dict(data='2026-10-01',unidade_documento='111',serie='001',nota_numero='1',produto='001',cliente='123',peso='3',preco_praticado='10',frete='1',frete_kg='0.3')

    def test_decimal(self):
        result=calculate_item(self.item,self.catalog)
        self.assertEqual(result['valor_fob'],Decimal('29.1'))
        self.assertEqual(result['comissao_kg'],Decimal('.1'))

    def test_missing_price_preserves_known_weight_as_pending(self):
        result=calculate_item({**self.item,'preco_praticado':None},self.catalog)
        self.assertEqual(result['peso'],Decimal('3'))
        self.assertIsNone(result['preco_praticado_kg'])
        self.assertIsNone(result['valor_fob'])
        self.assertEqual(result['status'],'pendente')

    def test_manual_pendente_zero_e_nulo(self):
        for value in ('0',None):
            result=calculate_item({**self.item,'frete_kg':value},self.catalog)
            self.assertEqual(result['status'],'pendente')
            self.assertIsNone(result['valor_fob'])
            self.assertIsNone(result['frete_kg'])

    def test_manual_zero_explicito(self):
        result=calculate_item({**self.item,'frete_kg':'0'},self.catalog,ManualFreight(Decimal(0),'preenchimento confirmado no teste'))
        self.assertEqual(result['status'],'calculado')
        self.assertEqual(result['valor_fob'],Decimal('29.7'))
        with self.assertRaises(ValueError):ManualFreight(Decimal('.2'),'')

    def test_januaria_exige_manual(self):
        result=calculate_item({**self.item,'unidade_documento':'102'},self.catalog)
        self.assertIsNone(result['valor_fob'])

    def test_fora_perimetro_nao_vira_regra_por_cfop(self):
        result=calculate_item({**self.item,'nota_numero':'2','cfop':'5151-06'},self.catalog)
        self.assertFalse(result['incluido'])
        self.assertIsNone(result['valor_fob'])

    def test_formulas_ocultas_horizontal_e_vertical(self):
        sheet={'rows':{'5':{'T':{'fa':{'si':'1'}}},'6':{'T':{'fa':{'si':'1'}}}},
               'shared_formulas':{'1':{'cell':'R5','f':'$Q5*R$3'}}}
        self.assertEqual(formula(sheet,5,'T'),'=$Q5*T$3')
        self.assertEqual(formula(sheet,6,'T'),'=$Q6*T$3')

    def test_repositorio_select_pontual_parametrizado(self):
        class Connection:
            def execute(inner,q,p):
                inner.q,inner.p=q,p
                return inner
            def fetchall(inner):return [{'id':123}]
        conn=Connection()
        result=read_invoice(conn,unit='111',invoice='806684',customer='9880',raw=True)
        self.assertTrue(conn.q.startswith('SELECT * FROM comercial.faturamento_cfop'))
        self.assertIn('LIMIT 101',conn.q)
        self.assertEqual(conn.p,['111','806684','9880'])
        self.assertEqual(result[0]['_source'],'comercial.faturamento_cfop')


if __name__=='__main__':unittest.main(verbosity=2)
