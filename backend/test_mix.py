"""Verificações pequenas do método Mix; sem banco, rede ou dados financeiros reais."""
from decimal import Decimal as D
import unittest
from modules.comparativo_fob.mix_formula import Evaluator,MissingInput
from modules.comparativo_fob.mix_engine import Reader,PRICE


class MixTests(unittest.TestCase):
    def test_iferror_nao_converte_cadastro_ausente_em_zero(self):
        class Source:
            def cell(self,*args):raise MissingInput('cadastro ausente')
        with self.assertRaises(MissingInput):Evaluator(Source()).formula('=IFERROR(A1,0)','Teste')

    def test_if_avalia_somente_ramo_necessario(self):
        self.assertEqual(Evaluator(None).formula('=IF(1=1,4.5,1/0)','Teste'),D('4.5'))

    def test_iferror_preserva_regra_divisao(self):
        self.assertEqual(Evaluator(None).formula('=IFERROR(1/0,3)','Teste'),D(3))

    def test_procv_usa_primeira_ocorrencia(self):
        spec={'sheets':{'Tabela':{'max_row':3,'cells':{'B1':{'number':'10'},'C1':{'number':'2'},'B2':{'number':'10'},'C2':{'number':'9'}}}}}
        self.assertEqual(Reader(spec,{},[]).evaluator.formula('=VLOOKUP(10,Tabela!B:C,2,0)','Outra'),D(2))

    def test_procv_ausente_nao_vira_zero(self):
        spec={'sheets':{'Tabela':{'max_row':1,'cells':{'B1':{'number':'10'}}}}}
        with self.assertRaises(MissingInput):Reader(spec,{},[]).evaluator.formula('=IFERROR(VLOOKUP(99,Tabela!B:C,2,0),0)','Outra')

    def test_preco_ponderado_vem_dos_itens(self):
        spec={'sheets':{PRICE:{'max_row':4,'cells':{'B4':{'number':'12'}}}}}
        rows=[{'identificacao':{'produto':'00012'},'peso':D(2),'valor_fob':D(10)}, {'identificacao':{'produto':'12'},'peso':D(8),'valor_fob':D(24)}]
        reader=Reader(spec,{'cells':{PRICE:{'D4':'999','E4':'999'}}},rows)
        self.assertEqual(reader.cell(PRICE,'E4')/reader.cell(PRICE,'D4'),D('3.4'))

    def test_preco_pendente_nao_usa_parcial(self):
        spec={'sheets':{PRICE:{'max_row':4,'cells':{'B4':{'number':'12'}}}}}
        rows=[{'identificacao':{'produto':'12'},'peso':D(8),'valor_fob':None}]
        with self.assertRaises(MissingInput):Reader(spec,{},rows).cell(PRICE,'E4')

    def test_soma_frete_respeita_unidade_e_familia(self):
        rows=[dict(identificacao=dict(produto='12',unidade_documento=u),peso=D(10),frete_kg=D(f),dados_entrada=dict(familia='PÉS')) for u,f in [('10','2'),('111','3'),('180','9')]]
        reader=Reader({'sheets':{}},{},rows)
        self.assertEqual(reader.evaluator.formula('=SUMIF(FaturamentoANeRA!AA:AA,"pés",FaturamentoANeRA!BH:BH)','Teste'),D(50))

    def test_sem_cadastro_nao_utiliza_valor_excel(self):
        reader=Reader({'sheets':{'AnaliseMix':{'max_row':4,'cells':{'C4':{'input':True}}}}},{},[])
        with self.assertRaises(MissingInput):reader.cell('AnaliseMix','C4')


if __name__=='__main__':unittest.main()
