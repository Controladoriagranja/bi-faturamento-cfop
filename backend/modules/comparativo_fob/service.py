"""Referência conferida do Excel e histórico separado da view, somente leitura."""
from collections import defaultdict
from datetime import date,timedelta
from decimal import Decimal
from functools import lru_cache
import logging
from threading import RLock

from fastapi import HTTPException
from fob.calculator import calculate_item,code,decimal,item_key
from fob.repository import read_invoice,read_freight_overrides
from fob.snapshot import SnapshotCatalog
from .aggregation import aggregate,public,order_items
from .config import CATALOG_PATH,CHANNELS,CONFIG,COSTS,UNITS
from .historical import execute_history

logger=logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_catalog():return SnapshotCatalog(CATALOG_PATH)


class ComparativoFOBService:
    def __init__(self,context):
        self.context=context;self._lock=RLock()

    def _read(self):
        with self._lock:
            catalog=load_catalog();start,end=(date.fromisoformat(d) for d in catalog.period)
            with self.context.banco() as conn:
                rows=conn.execute('''SELECT * FROM comercial.vw_faturamento_cfop_filtrado
                    WHERE data >= %s AND data < %s ORDER BY id LIMIT %s''',
                    [start,end+timedelta(days=1),CONFIG['max_itens']+1]).fetchall()
                if len(rows)>CONFIG['max_itens']:raise HTTPException(422,'Período excede o limite desta primeira entrega; consulta não será truncada.')
                try:overrides=read_freight_overrides(conn,rows)
                except ValueError as error:raise HTTPException(409,str(error)) from None
                except Exception:
                    raise HTTPException(503,'Não foi possível consultar os cadastros de frete/custo mensal.') from None
            indexed={};excluded=0
            for row in rows:
                row={**row,'_source':'comercial.vw_faturamento_cfop_filtrado'}
                try:key=item_key(row)
                except Exception as error:raise HTTPException(409,'Há item com chave ou peso inválido na origem.') from error
                if key not in catalog.index:excluded+=1;continue
                if key in indexed:raise HTTPException(409,'Há itens com identificação duplicada. Auditar antes de consolidar FOB.')
                indexed[key]=row
            note_ref=next(r for r in catalog.items if r.sheet=='FaturamentoANeRA' and r.row==422)
            note_key=item_key(note_ref.fields)
            raw_status='presente_na_view'
            if note_key not in indexed:
                try:
                    with self.context.banco() as conn:
                        raw=read_invoice(conn,unit='111',invoice='806684',customer='9880',raw=True)
                    candidates=[r for r in raw if item_key(r)==note_key]
                    if len(candidates)>1:raise HTTPException(409,'NF 806684 ambígua na tabela bruta.')
                    if candidates:indexed[note_key]=candidates[0];raw_status='conciliada_na_tabela_bruta'
                    else:raw_status='encontrada_com_itens_divergentes' if raw else 'nao_encontrada_na_tabela_bruta'
                except HTTPException:raise
                except Exception:
                    logger.exception('Falha no SELECT pontual da NF 806684; referência provisória será identificada.')
                    raw_status='consulta_bruta_indisponivel'
                if note_key not in indexed:
                    indexed[note_key]={**note_ref.fields,'_source':note_ref.origin+' — referência provisória','_provisional':True}
            result=[]
            for ref in catalog.items:
                key=item_key(ref.fields);item=indexed.get(key)
                if item is None:
                    row=dict(incluido=True,status='ausente_origem',ausente_origem=True,id=None,
                        identificacao={k:ref.fields.get(k) for k in ('data','unidade_documento','serie','nota_numero','produto','cliente')},
                        peso=None,origem_excel=ref.origin,valor_fob=None,preco_fob_kg=None,
                        componentes={},pendencias=['Registro de referência não encontrado na origem'],provisorio=False)
                else:
                    override,warning=overrides.resolve(item)
                    row=calculate_item(item,catalog,freight_override=override)
                    if warning:row['avisos_frete']=[warning]
                    row['provisorio']=bool(item.get('_provisional'))
                    row['divergencias_entrada']={}
                    for field in ('preco_praticado','valor_total_faturado','frete_kg'):
                        actual,expected=decimal(item.get(field)),decimal(ref.fields.get(field))
                        if actual!=expected and (actual is None or expected is None or abs(actual-expected)>Decimal('0.00000001')):
                            row['divergencias_entrada'][field]=dict(origem=actual,excel=expected)
                row.update(familia=ref.fields.get('familia') or 'Sem família',canal=ref.category,chave_item='|'.join(key),
                    peso_excel=decimal(ref.fields['peso']),
                    produto_descricao=(item or ref.fields).get('produto_descricao'),valor_fob_excel=ref.cached['valor_fob'],
                    formulas_excel=ref.formulas)
                row['divergente']=bool(row.get('divergencias_entrada') or row.get('ausente_origem') or row['provisorio'])
                result.append(row)
            payload=dict(rows=result,contexto=dict(periodo_disponivel=catalog.period,sha256_excel=catalog.sha256,
                origem='PostgreSQL com cadastros de referência do Excel',consulta_nf_806684=raw_status,
                linhas_fora_perimetro=excluded,limite_itens=CONFIG['max_itens'],
                observacao='Despesas Excel de 01–04/10/2026; frete manual validado e custo mensal 102 têm precedência. '
                    'Januária sem competência própria usa outubro/2026; sem outubro, permanece pendente.',
                cache_frete_segundos=0))
            return payload

    def execute(self,operation,request):
        catalog=load_catalog()
        if operation=='filtros':
            if request.query_params:raise HTTPException(422,'Filtros não são aceitos nesta operação.')
            return dict(unidade=[dict(value=k,label=v) for k,v in UNITS.items()],
                familia=sorted({r.fields.get('familia') or 'Sem família' for r in catalog.items}),canal=list(CHANNELS),
                periodo_disponivel=dict(data_inicio='2026-01-01',data_fim=date.today().isoformat()),
                periodo_referencia=dict(data_inicio=catalog.period[0],data_fim=catalog.period[1]),
                observacao='Histórico da view desde janeiro. Despesas validadas somente de 01 a 04/10/2026.')
        allowed={'data_inicio','data_fim','unidade','familia','canal','pendentes','busca','pagina','por_pagina','ordenar_por','ordem'}
        if set(request.query_params)-allowed:raise HTTPException(422,'Filtro não configurado.')
        def single(name,default=''):
            values=request.query_params.getlist(name)
            if len(values)>1:raise HTTPException(422,'Parâmetro duplicado: '+name)
            return values[0] if values else default
        try:start,end=(date.fromisoformat(single(k,catalog.period[i])) for i,k in enumerate(('data_inicio','data_fim')))
        except ValueError:raise HTTPException(422,'Data inválida. Use AAAA-MM-DD.')
        if start>end or start<date(2026,1,1) or end>date.today():
            raise HTTPException(422,'Consulte entre 01/01/2026 e a data atual.')
        choices={key:request.query_params.getlist(key) for key in ('unidade','familia','canal')}
        if any(len(vals)>100 or any(len(v)>150 for v in vals) for vals in choices.values()):raise HTTPException(422,'Limite de filtro excedido.')
        only_pending=single('pendentes','0');search=single('busca').strip().casefold()
        if only_pending not in ('0','1') or len(search)>200:raise HTTPException(422,'Busca ou estado inválido.')
        from .feeding import enabled,execute_master
        if enabled():
            return execute_master(self,operation,start,end,choices,search,single,catalog)
        if start.isoformat()<catalog.period[0] or end.isoformat()>catalog.period[1]:
            return execute_history(self.context,operation,start,end,choices,search,single)
        payload=self._read();rows=[]
        for row in payload['rows']:
            identity=row['identificacao'];day=str(identity['data'])
            if not start.isoformat()<=day<=end.isoformat():continue
            if choices['unidade'] and code(identity.get('unidade_documento')) not in choices['unidade']:continue
            if any(choices[k] and row[k] not in choices[k] for k in ('familia','canal')):continue
            if only_pending=='1' and row.get('valor_fob') is not None:continue
            if search and search not in ' '.join(str(identity.get(k) or '') for k in ('nota_numero','produto','cliente')).casefold()+' '+str(row.get('produto_descricao') or '').casefold():continue
            rows.append(row)
        common=dict(contexto={**payload['contexto'],'data_inicio':start,'data_fim':end},total=aggregate(rows))
        if operation=='resumo':
            grouped=defaultdict(list)
            for row in rows:grouped[row['familia'],row['canal']].append(row)
            groups=[dict(familia=family,canal=channel,**aggregate(items)) for (family,channel),items in sorted(grouped.items())]
            return public(dict(**common,grupos=groups,
                familias=[dict(familia=family,**aggregate([r for r in rows if r['familia']==family])) for family in sorted({r['familia'] for r in rows})],
                canais=[dict(canal=channel,**aggregate([r for r in rows if r['canal']==channel])) for channel in CHANNELS]))
        if operation!='detalhes':raise HTTPException(404,'Operação não disponível.')
        try:page,size=int(single('pagina','1')),int(single('por_pagina','50'))
        except ValueError:raise HTTPException(422,'Paginação inválida.')
        if not 1<=page<=100000 or not 1<=size<=500:raise HTTPException(422,'Paginação fora do limite.')
        sort=single('ordenar_por','nota_numero');direction=single('ordem','asc')
        keys={'data','unidade_documento','nota_numero','cliente','produto','peso','preco_praticado_kg','valor_fob','preco_fob_kg','familia','canal',*(k+'_kg' for k in COSTS)}
        if sort not in keys or direction not in ('asc','desc'):raise HTTPException(422,'Ordenação inválida.')
        ordered=order_items(rows,sort,direction)
        return public(dict(**common,linhas=ordered[(page-1)*size:page*size],total_registros=len(rows),pagina=page,por_pagina=size))


def build_service(context):return ComparativoFOBService(context)
