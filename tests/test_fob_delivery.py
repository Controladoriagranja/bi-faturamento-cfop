"""Verificações rápidas e locais: funções puras e conteúdo do ZIP, sem API/banco."""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from fob.calculator import calculate_item,code
from fob.snapshot import SnapshotCatalog
from modules.comparativo_fob.aggregation import aggregate,public,order_items
from modules.comparativo_fob.config import COSTS
from integrar_comparativo_fob import plan,MARKER


def item(weight,value,reference):
    return dict(peso=D(weight),peso_excel=D(weight),valor_fob=D(value) if value else None,
        valor_fob_excel=D(reference),preco_praticado_kg=D('10'),
        **{key+'_kg':D('0') for key in COSTS})


class AggregationTest(unittest.TestCase):
    def test_sort_mixes_database_date_with_provisional_excel_and_nulls(self):
        from datetime import date
        rows=[dict(identificacao=dict(data=date(2026,10,2),nota_numero='10'),valor_fob=D(10)),
              dict(identificacao=dict(data='2026-10-01',nota_numero='2'),valor_fob=None)]
        self.assertEqual(order_items(rows,'data','asc'),rows[::-1])
        self.assertEqual(order_items(rows,'nota_numero','asc'),rows[::-1])
        self.assertEqual(order_items(rows,'valor_fob','desc'),rows)
    def test_pending_does_not_become_complete_or_zero(self):
        complete=item('3','27','27');pending=item('7',None,'63');pending['frete_kg']=None
        result=aggregate([complete,pending])
        self.assertEqual(result['peso'],D(10));self.assertEqual(result['peso_pendente'],D(7))
        self.assertEqual(result['valor_fob_parcial'],D(27))
        self.assertIsNone(result['valor_fob']);self.assertIsNone(result['pm_fob_kg'])
        self.assertIsNone(result['componentes']['frete']['media_kg'])
        self.assertEqual(result['componentes']['comissao']['media_kg'],D(0))

    def test_weighted_average_and_decimal_serialization(self):
        result=aggregate([item('1','9','9'),item('3','18','18')])
        self.assertEqual(result['pm_fob_kg'],D('6.75'))
        self.assertEqual(result['diferenca_fob'],D(0))
        self.assertEqual(public(result)['valor_fob'],'27')

    def test_missing_source_does_not_invent_weight(self):
        row=item('0',None,'100');row.update(peso=None,peso_excel=D(10),ausente_origem=True)
        result=aggregate([row])
        self.assertEqual(result['peso'],D(0));self.assertEqual(result['peso_excel'],D(10))
        self.assertEqual(result['diferenca_peso'],D(-10));self.assertEqual(result['ausentes'],1)
        self.assertIsNone(result['preco_praticado_kg']);self.assertIsNone(result['valor_fob'])

    def test_missing_price_is_not_averaged_as_zero(self):
        row=item('10',None,'100');row['preco_praticado_kg']=None
        result=aggregate([row])
        self.assertEqual(result['peso'],D(10));self.assertIsNone(result['preco_praticado_kg'])


class IntegrationPlanTest(unittest.TestCase):
    def test_legacy_additions_preserve_existing_bytes_and_are_idempotent(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);service=b'app = FastAPI()\r\ndef banco():\r\n    pass\r\n# API existente\r\n'
            docker=b'FROM python:3.12-slim\r\r\nCOPY API/api_zootecnico/bi_generic ./bi_generic\r\r\nCMD ["uvicorn"]\r\r\n'
            (root/'servico_zootecnico.py').write_bytes(service);(root/'Dockerfile.zootecnico').write_bytes(docker)
            changes=plan(root);self.assertEqual(len(changes),2)
            self.assertTrue(changes[0][2].startswith(service));self.assertIn(MARKER,changes[0][2])
            for path,_,after in changes:path.write_bytes(after)
            self.assertEqual(plan(root),[])
            self.assertIn(b'COPY API/api_zootecnico/bi_generic ./bi_generic\r\r\n',(root/'Dockerfile.zootecnico').read_bytes())

    def test_modular_api_never_changes_main_service(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'servico_zootecnico.py').write_text('from core.bootstrap import register_modules\n',encoding='utf-8')
            (root/'Dockerfile.zootecnico').write_text('COPY API/api_zootecnico/modules ./modules\nCMD ["uvicorn"]\n',encoding='utf-8')
            changes=plan(root);self.assertEqual([p.name for p,_,_ in changes],['Dockerfile.zootecnico'])
            self.assertNotIn(b'/modules/comparativo_fob',changes[0][2]);self.assertIn(b'/fob ./fob',changes[0][2])

    def test_unknown_docker_context_changes_nothing(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);service=b'app = FastAPI()\ndef banco():\n    pass\n'
            (root/'servico_zootecnico.py').write_bytes(service);(root/'Dockerfile.zootecnico').write_text('FROM python\n',encoding='utf-8')
            with self.assertRaises(ValueError):plan(root)
            self.assertEqual((root/'servico_zootecnico.py').read_bytes(),service)


@unittest.skipUnless((ROOT/'artifacts/api_anderson_comparativo_fob.zip').exists(),'Gere o ZIP para conferir o catálogo de entrega.')
class DeliveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib
        import importlib.util
        cls.tmp=TemporaryDirectory()
        folder=Path(cls.tmp.name)/'comparativo_fob';folder.mkdir()
        with ZipFile(ROOT/'artifacts/api_anderson_comparativo_fob.zip') as archive:
            for name in archive.namelist():
                if name.startswith('bi_generic/comparativo_fob/'):
                    (folder/Path(name).name).write_bytes(archive.read(name))
        spec=importlib.util.spec_from_file_location('_anderson_fob_delivery',folder/'__init__.py',submodule_search_locations=[str(folder)])
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        cls.catalog=importlib.import_module(spec.name+'.snapshot').SnapshotCatalog(folder/'referencia_excel.json')
        cls.calculate_item=staticmethod(importlib.import_module(spec.name+'.calculator').calculate_item)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        for name in list(sys.modules):
            if name=='_anderson_fob_delivery' or name.startswith('_anderson_fob_delivery.'):sys.modules.pop(name)

    def test_catalog_preserves_weights_and_excel_targets(self):
        expected={'Varejo':('203818','1949811.06'),'Atacado':('931381','7900355.54'),'Subprodutos':('510740','383055.00')}
        self.assertEqual(len(self.catalog.items),2340)
        for channel,(weight,value) in expected.items():
            rows=[r for r in self.catalog.items if r.category==channel]
            self.assertEqual(sum(D(r.fields['peso']) for r in rows),D(weight))
            self.assertEqual(sum(r.cached['valor_fob'] for r in rows).quantize(D('.01')),D(value))

    def test_packaged_formulas_and_sources_remain_calculable(self):
        for unit in ('10','111','180'):
            ref=next(r for r in self.catalog.items if code(r.fields['unidade_documento'])==unit and code(r.fields['frete'])=='1' and D(r.fields.get('frete_kg') or 0)>0)
            result=self.calculate_item(ref.fields,self.catalog)
            self.assertEqual(result['status'],'calculado')
            self.assertLess(abs(result['valor_fob']-ref.cached['valor_fob']),D('0.00001'))
            self.assertEqual(len(result['componentes']),8)
        ref=next(r for r in self.catalog.items if r.sheet=='FaturamentoJA' and code(r.fields['frete'])=='1')
        self.assertIsNone(self.calculate_item(ref.fields,self.catalog)['valor_fob'])
        note=next(r for r in self.catalog.items if r.sheet=='FaturamentoANeRA' and r.row==422)
        self.assertEqual(code(note.fields['nota_numero']),'806684')
        self.assertEqual(D(note.fields['peso']),D(40));self.assertEqual(note.category,'Varejo')

    def test_zip_manifest_and_ready_to_copy_shared_files(self):
        with ZipFile(ROOT/'artifacts/api_anderson_comparativo_fob.zip') as archive:
            manifest=json.loads(archive.read('MANIFESTO.json'))
            self.assertEqual({r['arquivo'] for r in manifest['arquivos_compartilhados_modificados']},{'servico_zootecnico.py'})
            self.assertEqual(manifest['scripts_pos_copia'],[])
            self.assertNotIn('integrar_comparativo_fob.py',archive.namelist())
            self.assertFalse(any('Dockerfile' in n for n in archive.namelist()))
            self.assertFalse(manifest['dockerfile_incluido'])
            service=archive.read('servico_zootecnico.py')
            self.assertEqual(service.count(b'from bi_generic.comparativo_fob.routes import criar_router_comparativo_fob'),1)
            self.assertEqual(service.count(b'app.include_router(criar_router_comparativo_fob(banco))'),1)
            self.assertEqual(manifest['pastas_novas'],['bi_generic/comparativo_fob'])
            self.assertTrue(all('/' not in n or n.startswith('bi_generic/comparativo_fob/') and len(n.split('/'))==3 for n in archive.namelist()))
            self.assertFalse(manifest['sql_ddl_necessario'])
            for entry in manifest['arquivos']:
                self.assertNotIn('..',Path(entry['caminho']).parts)
                self.assertEqual(hashlib.sha256(archive.read(entry['caminho'])).hexdigest(),entry['sha256'])
            self.assertFalse(any(n.startswith(('core/','assets/')) or n.endswith('.xlsx') for n in archive.namelist()))

    def test_ready_files_preserve_supplied_api_and_dependency_versions(self):
        import ast
        with ZipFile(ROOT/'artifacts/api_anderson_comparativo_fob.zip') as archive:
            manifest=json.loads(archive.read('MANIFESTO.json'))
            source=Path.home()/'Downloads'/manifest['api_referencia_arquivo']
            if not source.exists():self.skipTest('Arquivo da API de referência não disponível nesta máquina.')
            with ZipFile(source) as baseline:
                original=baseline.read('api_zootecnico/servico_zootecnico.py')
                self.assertTrue(archive.read('servico_zootecnico.py').startswith(original))
                self.assertTrue(all(name not in archive.namelist() for name in ('suprimentos_html.py','comercial_acesso.py','comercial_relatorios.py','bi_generic/router.py','bi_generic/registry.py')))
                self.assertIn(b'COPY API/api_zootecnico/bi_generic ./bi_generic',baseline.read('api_zootecnico/Dockerfile.zootecnico'))
                for row in manifest['arquivos_compartilhados_modificados']:
                    self.assertEqual(hashlib.sha256(archive.read(row['arquivo'])).hexdigest(),row['sha256_entregue'])
                    self.assertEqual(hashlib.sha256(baseline.read('api_zootecnico/'+row['arquivo'])).hexdigest(),row['sha256_base'])
            for name in archive.namelist():
                if not name.endswith('.py'):continue
                tree=ast.parse(archive.read(name).decode('utf-8-sig'),filename=name)
                if name.startswith('bi_generic/comparativo_fob/'):
                    for node in ast.walk(tree):
                        if isinstance(node,ast.ImportFrom):
                            if node.level:
                                self.assertEqual(node.level,1)
                                self.assertIn('bi_generic/comparativo_fob/'+node.module.replace('.','/')+'.py',archive.namelist())
                            else:self.assertFalse(node.module.startswith(('fob','modules','core')))


if __name__=='__main__':unittest.main(verbosity=2)
