"""Comparação offline limitada ao Excel 01–04/10. Não conecta ao banco."""
import argparse
from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal, ROUND_HALF_UP, localcontext
import csv
import json
from pathlib import Path

from .calculator import ZERO, ManualFreight, calculate_item, combine, decimal, item_key
from .reference import WorkbookCatalog, LAYOUTS, column_number, formula

TARGETS={'Varejo':(Decimal('203818'),Decimal('1949811.06')),
         'Atacado':(Decimal('931381'),Decimal('7900355.54')),
         'Subprodutos':(Decimal('510740'),None)}


def serial(value):
    if isinstance(value,Decimal):return str(value)
    if hasattr(value,'isoformat'):return value.isoformat()
    raise TypeError(type(value).__name__)


def write_json(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=serial),encoding='utf-8')


def run(workbook, source_csv, output, manual_file=None, raw_csv=None):
    with localcontext() as context:
        context.prec=38
        return _run(workbook,source_csv,output,manual_file,raw_csv)


def _run(workbook, source_csv, output, manual_file, raw_csv):
    catalog=WorkbookCatalog(workbook)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    manual=json.loads(Path(manual_file).read_text(encoding='utf-8')) if manual_file else {}
    source=[]
    for path,table in [(source_csv,'comercial.vw_faturamento_cfop_filtrado'),(raw_csv,'comercial.faturamento_cfop')]:
        if path:
            with open(path,encoding='utf-8-sig',newline='') as stream:
                rows=list(csv.DictReader(stream))
            if len(rows)>5000:raise ValueError('Esta validação inicial aceita no máximo 5.000 linhas por CSV.')
            source.extend({**row,'_source':table} for row in rows)
    # Primeiro a view; a tabela bruta só complementa itens comprovados ausentes.
    indexed={};duplicates=[]
    for item in source:
        key=item_key(item)
        if key in indexed:
            if item['_source']=='comercial.faturamento_cfop':continue
            duplicates.append(key)
        else:indexed[key]=item
    if duplicates:raise ValueError('CSV com chaves duplicadas: '+str(duplicates[:3]))
    missing=[]
    for ref in catalog.items:
        key=item_key(ref.fields)
        if key in indexed:continue
        missing.append({'origem_excel':ref.origin,'chave':key,'peso':ref.fields['peso']})
        # Única referência provisória expressamente autorizada pelo usuário.
        if (ref.sheet,ref.row,ref.fields['unidade_documento'],ref.fields['nota_numero'],ref.fields['cliente'],ref.fields['peso'])==('FaturamentoANeRA',422,'111','806684','9880','40'):
            indexed[key]={**ref.fields,'_source':ref.origin+' (provisória; banco não conciliado)','_provisional':True}
    results=[]
    for key,item in indexed.items():
        entry=manual.get('|'.join(key))
        freight=ManualFreight(decimal(entry['valor_kg']),entry['origem']) if entry else None
        result=calculate_item(item,catalog,freight)
        result.update(chave_item=key,provisorio=bool(item.get('_provisional')))
        ref=catalog.locate(item)
        if ref:
            result['valor_fob_excel']=ref.cached['valor_fob']
            result['diferenca_fob_excel']=result['valor_fob']-ref.cached['valor_fob'] if result['valor_fob'] is not None else None
            result['divergencias_entrada']={}
            for field in ('preco_praticado','valor_total_faturado','frete_kg'):
                actual,expected=decimal(item.get(field)),decimal(ref.fields.get(field))
                if actual!=expected and (actual is None or expected is None or abs(actual-expected)>Decimal('0.00000001')):
                    result['divergencias_entrada'][field]={'origem':actual,'excel':expected}
            if result['provisorio'] and result['status']=='calculado':result['status']='calculado_provisorio'
        results.append(result)

    # Replay separado: AU de Januária é somente referência salva do arquivo
    # externo. Nunca preenche nem libera o resultado operacional pendente.
    replay=[]
    with localcontext() as ctx:
        ctx.prec=38
        for ref in catalog.items:
            components=catalog.components(ref.fields,ref)
            freight=catalog.freight(ref.fields,ref)
            if ref.sheet=='FaturamentoJA' and freight.value is None:
                from .calculator import Rate
                freight=Rate(ref.cached['frete'],ref.origin+': AU salvo (dependência externa; apenas comparação)',ref.formulas['frete'],'referencia_nao_manual')
            components={'frete':freight,**components}
            price,value=combine(decimal(ref.fields['preco_praticado']),decimal(ref.fields['peso']),components)
            differences={key:rate.value-ref.cached[key] for key,rate in components.items() if key in ref.cached and rate.value is not None}
            replay.append(dict(origem=ref.origin,categoria=ref.category,peso=decimal(ref.fields['peso']),
                preco_fob_reproduzido=price,valor_fob_reproduzido=value,valor_fob_salvo=ref.cached['valor_fob'],
                diferenca=value-ref.cached['valor_fob'] if value is not None else None,
                diferencas_componentes=differences,
                componentes={key:asdict(rate) for key,rate in components.items()},
                dependencias=['Frete externo de Januária: valor salvo usado só para replay'] if freight.status=='referencia_nao_manual' else []))
    summary={}
    for category,(target_weight,target_value) in TARGETS.items():
        relevant=[r for r in results if r.get('incluido') and r.get('categoria')==category]
        reference=[r for r in replay if r['categoria']==category]
        weight=sum((r.get('peso') or ZERO for r in relevant),ZERO)
        partial=sum((r['valor_fob'] for r in relevant if r['valor_fob'] is not None),ZERO)
        pending=sum(r['valor_fob'] is None for r in relevant)
        absent=[r for r in catalog.items if r.category==category and item_key(r.fields) not in indexed]
        completed=partial if not pending and not absent else None
        value=sum((r['valor_fob_reproduzido'] for r in reference if r['valor_fob_reproduzido'] is not None),ZERO)
        if any(r['valor_fob_reproduzido'] is None for r in reference):value=None
        excel=sum((r['valor_fob_salvo'] for r in reference),ZERO)
        summary[category]=dict(itens=len(relevant),peso=weight,peso_referencia=target_weight,diferenca_peso=weight-target_weight,
            itens_pendentes=pending,itens_ausentes_sem_fallback=len(absent),
            peso_pendente=sum((r.get('peso') or ZERO for r in relevant if r['valor_fob'] is None),ZERO),
            itens_provisorios=sum(r['provisorio'] for r in relevant),
            valor_fob=completed,valor_fob_parcial_itens_concluidos=partial,
            valor_fob_referencia_excel=excel,valor_fob_reproduzido_excel=value,
            meta_fob=target_value,diferenca_replay_meta=value-target_value if value is not None and target_value is not None else None,
            diferenca_replay_cache=value-excel if value is not None else None,
            replay_arredondado=value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP) if value is not None else None,
            pm_fob_kg=completed/weight if completed is not None and weight else None)
    report=dict(workbook=str(Path(workbook).resolve()),sha256=catalog.sha256,periodo=['2026-10-01','2026-10-04'],
        resumos=summary,linhas_csv=len(source),linhas_fora_perimetro=sum(r.get('incluido') is False for r in results),
        registros_ausentes_na_view=missing,
        itens_com_divergencia_entrada=sum(bool(r.get('divergencias_entrada')) for r in results),
        consulta_nf_806684='Ver arquivo consulta_nf_806684.json, quando disponível. O motor offline não realiza consultas.',
        itens_replay_divergentes=sum(r['diferenca'] is None or abs(r['diferenca'])>Decimal('0.00001') or any(abs(d)>Decimal('0.00000001') for d in r['diferencas_componentes'].values()) for r in replay),
        observacoes=['Cadastros de comissão AK são um snapshot calculado no Excel, com fórmulas/colunas ocultas no mapa.',
                     'Replay do Excel e resultado operacional são saídas separadas. Frete pendente nunca entra no FOB calculado.',
                     'O perímetro por item é comprovado apenas para este arquivo/período. Não é uma regra geral por cliente/CFOP.'])
    write_json(output/'resumo.json',report)
    write_json(output/'replay_excel.json',replay)
    write_json(output/'cadastros_snapshot.json',dict(sha256=catalog.sha256,tabelas=catalog.tables,
        frete_por_cliente=dict(catalog.freight_totals),
        comissao_base_com_colunas_ocultas=catalog.sheets[catalog.commission_sheet],
        descricao='Valores e fórmulas salvos no Excel. AK é cadastro inicial congelado, não folha recalculada pelo motor.'))
    with (output/'itens_auditaveis.jsonl').open('w',encoding='utf-8') as stream:
        for row in results:stream.write(json.dumps(row,ensure_ascii=False,default=serial)+'\n')
    with (output/'mapa_formulas.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['aba','celula','aba_oculta','coluna_oculta','formula','valor_salvo'])
        for name,sheet in catalog.sheets.items():
            for number,row in sheet['rows'].items():
                for col,cell in row.items():
                    if 'f' not in cell:continue
                    hidden=any(int(c['min'])<=column_number(col)<=int(c['max']) and c.get('hidden')=='1' for c in sheet['columns'])
                    expression=formula(sheet,int(number),col)
                    writer.writerow([name,col+number,sheet['state']!='visible',hidden,"'"+expression if expression else '',cell.get('v')])
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--excel',type=Path,required=True)
    parser.add_argument('--csv',type=Path,required=True)
    parser.add_argument('--csv-bruto',type=Path)
    parser.add_argument('--fretes-manuais',type=Path)
    parser.add_argument('--saida',type=Path,required=True)
    args=parser.parse_args()
    report=run(args.excel,args.csv,args.saida,args.fretes_manuais,args.csv_bruto)
    print(json.dumps(report['resumos'],ensure_ascii=False,default=serial,indent=2))


if __name__=='__main__':main()
