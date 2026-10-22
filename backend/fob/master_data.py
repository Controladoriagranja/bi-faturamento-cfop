"""Contrato puro das planilhas-mestre: identidade textual, vigência e auditoria."""
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date
from decimal import Decimal, localcontext
from hashlib import sha256
import json

from .calculator import Rate, calculate_item, code, decimal
from .freight import invoice_key, monthly_rate

COSTS = ('frete','comissao','adicional_comissao','contrato','contrato_administracao',
         'logistica_reversa','pallet','descarga')
DIMENSIONS = ('unidade_documento','vendedor','cliente','rede','produto','familia','uf','rota_cliente')
ITEM_FIELDS = ('data','produto','cliente','cfop','pedido','oc_principal','um')


def day(value):
    return value if isinstance(value,date) else date.fromisoformat(str(value))


def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,default=str,
                             separators=(',',':')).encode('utf-8')).hexdigest()


def item_identity(item):
    # Peso e IDs de carga NÃO fazem parte da identidade. Não há conversão numérica.
    fields = [str(item.get(k) or '').strip(' ') for k in ITEM_FIELDS]
    if not fields[0] or not fields[1] or not fields[2]:
        raise ValueError('Item sem data, produto ou cliente.')
    return digest([invoice_key(item),fields])


def invoice_signature(items):
    def numeric(value):
        value=decimal(value)
        if value is None:return None
        text=format(value,'f')
        return text.rstrip('0').rstrip('.') if '.' in text else text
    return digest(sorted((item_identity(i),numeric(i.get('peso')),
                          str(i.get('frete')),numeric(i.get('frete_kg'))) for i in items))


def eligible(item):
    return str(item.get('unidade_documento')).strip(' ') != '102' and \
        str(item.get('frete')).strip(' ') == '1' and decimal(item.get('frete_kg')) in (None,Decimal(0))


def pending_rows(items, invoices):
    """Itens da view; denominadores e ambiguidade da NF integral da tabela bruta."""
    result=[]
    for item in items:
        if not eligible(item):continue
        try:
            key=invoice_key(item); full=invoices.get(key,[])
            identities=Counter(item_identity(i) for i in full)
            token=item_identity(item); weights=[decimal(i.get('peso')) for i in full]
            valid=bool(full) and all(w is not None and w>0 for w in weights)
            weight=sum(weights,Decimal(0)) if valid else None
            valid=valid and len({str(i['data']) for i in full})==1 and len({str(i.get('cliente')) for i in full})==1
            unique=identities[token]==1
            status='PENDENTE' if valid and unique else 'REVISAR_IDENTIFICACAO'
            result.append(dict(empresa_contexto=key[0],unidade_documento=key[1],serie=key[2],
                nota_numero=key[3],ano_nf=key[4],chave_item=token,assinatura_nf=invoice_signature(full),
                peso_total_nf=weight,peso_item=decimal(item.get('peso')),data=str(item['data']),
                produto=str(item.get('produto') or ''),cliente=str(item.get('cliente') or ''),
                produto_descricao=item.get('produto_descricao'),quantidade=item.get('volumes'),
                frete_original=item.get('frete_kg'),situacao=status,
                motivo='' if status=='PENDENTE' else 'NF incompleta, peso inválido ou item indistinguível; não preencher.'))
        except (ValueError,TypeError,ArithmeticError) as error:
            result.append(dict(situacao='REVISAR_IDENTIFICACAO',motivo=str(error),
                               nota_numero=item.get('nota_numero'),produto=item.get('produto')))
    return result


def overlaps(a,b):
    return day(a['inicio'])<=day(b['fim']) and day(b['inicio'])<=day(a['fim'])


def validate_rules(rules):
    ids=set()
    for row in rules:
        if row['registro'] in ids:raise ValueError('Registro duplicado: '+row['registro'])
        ids.add(row['registro'])
        if day(row['inicio'])>day(row['fim']):raise ValueError('Vigência invertida: '+row['registro'])
        if row['tipo'] not in (*COSTS,'folha','gestor'):raise ValueError('Categoria desconhecida.')
        if row['modalidade'] not in ('KG','PERCENTUAL','FOLHA','TOTAL_NF','TOTAL_ITEM'):
            raise ValueError('Modalidade desconhecida.')
        value=decimal(row['valor'])
        if value is None or value<0 or value>=Decimal('1e18') or value.as_tuple().exponent < -20:
            raise ValueError('Valor ausente, negativo ou fora de NUMERIC(38,20).')
        if row['modalidade']=='PERCENTUAL' and value>1:raise ValueError('Percentual deve ser fração entre 0 e 1.')
        if not row.get('origem'):raise ValueError('Cadastro exige origem auditável.')
        if any(v is None or isinstance(v,bool) or not str(v).strip() for v in row['dimensoes'].values()):
            raise ValueError('Dimensão vazia ou inválida.')
        if row['tipo']=='frete':
            required={'empresa_contexto','unidade_documento','serie','nota_numero','ano_nf'}
            if not required<=set(row['dimensoes']):raise ValueError('Frete exige a chave completa da NF.')
            if str(row['dimensoes']['unidade_documento'])=='102':raise ValueError('Januária tem frete fixo mensal.')
            if row['modalidade']=='TOTAL_ITEM' and 'chave_item' not in row['dimensoes']:
                raise ValueError('Frete de item exige chave_item.')
        if set(row['dimensoes'])-set((*DIMENSIONS,'empresa_contexto','serie','nota_numero','ano_nf','chave_item')):
            raise ValueError('Dimensão desconhecida.')
    # Sobreposição com mesma seleção é erro; cliente > rede > regra geral é explícito.
    groups=defaultdict(list)
    for row in rules:
        if not row.get('ativo',True):continue
        dims={k:code(v) if row['tipo']!='frete' and k in ('unidade_documento','vendedor','cliente','rede','produto') else v
              for k,v in row['dimensoes'].items()}
        key=(row['tipo'],json.dumps(dims,sort_keys=True))
        for other in groups[key]:
            if overlaps(row,other):raise ValueError('Vigências sobrepostas: '+row['registro']+' / '+other['registro'])
        groups[key].append(row)


def matches(rule,item):
    def compare(k,v):
        if rule['tipo']!='frete' and k in ('unidade_documento','vendedor','cliente','rede','produto'):
            return code(item.get(k))==code(v)
        return str(item.get(k) or '').strip(' ')==str(v)
    return rule.get('ativo',True) and day(rule['inicio'])<=day(item['data'])<=day(rule['fim']) and all(compare(k,v) for k,v in rule['dimensoes'].items())


def priority(rule):
    dims=rule['dimensoes']
    return ('cliente' in dims,'rede' in dims,len(dims))


class MasterCatalog:
    """Consome apenas cadastros vigentes; desconhecido nunca é zero implícito."""
    def __init__(self,rules,monthly=(),invoices=None,payroll=None):
        self.rules=list(rules);validate_rules(self.rules)
        self.monthly={day(r['competencia']):r for r in monthly}
        self.invoices=invoices or {};self.payroll=payroll or {}
        self.by_kind=defaultdict(list)
        self.index=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
        self.freight_by_invoice=defaultdict(list)
        for r in self.rules:
            self.by_kind[r['tipo']].append(r)
            columns=tuple(sorted(r['dimensoes']))
            values=tuple(self.dimension(r['tipo'],k,r['dimensoes'][k]) for k in columns)
            self.index[r['tipo']][columns][values].append(r)
            if r['tipo']=='frete':
                self.freight_by_invoice[tuple(r['dimensoes'][k] for k in ('empresa_contexto','unidade_documento','serie','nota_numero','ano_nf'))].append(r)

    @staticmethod
    def dimension(kind,key,value):
        return code(value) if kind!='frete' and key in ('unidade_documento','vendedor','cliente','rede','produto') else str(value or '').strip(' ')

    def candidates(self,kind,item):
        found=[]
        for columns,values in self.index[kind].items():
            key=tuple(self.dimension(kind,k,item.get(k)) for k in columns)
            found.extend(r for r in values.get(key,()) if matches(r,item))
        return found

    def locate(self,item):
        from types import SimpleNamespace
        return SimpleNamespace(category=item.get('canal_grupo','Não classificado'),origin='PostgreSQL / planilhas-mestre')

    def select(self,kind,item):
        choices=self.candidates(kind,item)
        if not choices:return None
        highest=max(priority(r) for r in choices)
        best=[r for r in choices if priority(r)==highest]
        if len(best)!=1:raise ValueError('Cadastros concorrentes de '+kind+'; associação ambígua.')
        return best[0]

    def rate(self,kind,item):
        r=self.select(kind,item)
        if r is None:return Rate(None,'Planilha-mestre: cadastro ausente',status='pendente_cadastro_periodo')
        value=decimal(r['valor'])/decimal(r.get('parametros',{}).get('divisor',1)); formula='valor explícito / divisor (R$/kg)'
        if r['modalidade']=='PERCENTUAL':
            weight,total=decimal(item.get('peso')),decimal(item.get('valor_total_faturado'))
            value=total*value/weight if total is not None and weight and weight>0 else None
            formula='valor_total_faturado * (percentual / divisor) / peso'
        elif r['modalidade']!='KG':raise ValueError('Modalidade incompatível com '+kind)
        return Rate(value,r['origem'],formula,'planilha_mestre',
                    dict(registro=r['registro'],versao=r.get('versao'),lote=str(r.get('lote')),
                         inicio=str(r['inicio']),fim=str(r['fim']),modalidade=r['modalidade'],parametro=r['valor'],
                         divisor=r.get('parametros',{}).get('divisor',1)))

    def components(self,item,reference):
        out={k:self.rate(k,item) for k in COSTS if k not in ('frete','comissao')}
        folha=self.select('folha',item) if code(item.get('unidade_documento'))!='102' else None
        if folha:
            amount=self.payroll.get(folha['registro'])
            out['comissao']=Rate(amount,folha['origem'],'Comissão!N:AK recalculada pelo faturamento do período completo',
                'calculado_folha' if amount is not None else 'pendente_base_folha',
                dict(registro=folha['registro'],inicio=str(folha['inicio']),fim=str(folha['fim']),
                     versao=folha.get('versao'),lote=str(folha.get('lote'))))
        else:out['comissao']=self.rate('comissao',item)
        return out

    def freight(self,item,reference=None):
        if str(item.get('unidade_documento')).strip(' ')=='102':return monthly_rate(item['data'],self.monthly)
        key=invoice_key(item);full=self.invoices.get(key,[])
        item_id=item_identity(item)
        keyed={**item, 'ano_nf':key[4], 'chave_item':item_id}
        selected=self.candidates('frete',keyed)
        nf=[r for r in selected if 'chave_item' not in r['dimensoes']]
        detailed=[r for r in selected if 'chave_item' in r['dimensoes']]
        if nf and any(r['tipo']=='frete' and r.get('ativo',True) and 'chave_item' in r['dimensoes'] and
                      matches(r,{**keyed,'chave_item':r['dimensoes']['chave_item']}) for r in self.freight_by_invoice[key]):
            return Rate(None,'Planilha-mestre','NF e ITEM simultâneos','pendente_ambiguidade')
        selected=nf or detailed
        if selected:
            if len(selected)!=1:return Rate(None,'Planilha-mestre','Fretes concorrentes','pendente_ambiguidade')
            r=selected[0];p=r['parametros']
            if full and not any(eligible(i) for i in full):selected=[] # origem já resolveu a pendência
            else:
                if not full or invoice_signature(full)!=p['assinatura_nf']:
                    return Rate(None,r['origem'],'Faturamento mudou após preenchimento','revisar_identificacao')
                weights=[decimal(i.get('peso')) for i in full]
                if any(w is None or w<=0 for w in weights) or len({str(i['data']) for i in full})!=1 or len({str(i.get('cliente')) for i in full})!=1:
                    return Rate(None,r['origem'],'NF integral inconsistente','revisar_identificacao')
                if any(count>1 for count in Counter(item_identity(i) for i in full).values()):
                    return Rate(None,r['origem'],'Itens indistinguíveis','pendente_ambiguidade')
                denominator=decimal(item.get('peso')) if detailed else sum(weights,Decimal(0))
                value=decimal(r['valor'])
                if r['modalidade'] in ('TOTAL_NF','TOTAL_ITEM'):value=value/denominator
                return Rate(value,r['origem'],'total / peso integral NF' if nf else 'frete exclusivo do item',
                    'planilha_mestre',dict(registro=r['registro'],versao=r.get('versao'),lote=str(r.get('lote')),
                    peso_rateio=denominator,assinatura_nf=p['assinatura_nf'],substitui_todo_frete=True))
        if eligible(item):return Rate(None,'Fretes.xlsx','Tipo 1 zero/nulo','pendente_manual')
        original=decimal(item.get('frete_kg'))
        origin=item.get('_source','comercial.vw_faturamento_cfop_filtrado')+'.frete_kg'
        inputs=dict(frete_kg_original=original,tipo_frete=item.get('frete'),substituto_aplicado=False)
        if original is None or original<0:
            return Rate(None,origin,'Frete original ausente ou inválido','pendente_frete_origem',inputs)
        return Rate(original,origin,'frete_kg original válido, sem somar outro frete','calculado',inputs)


def calculate_master_item(item,catalog):
    with localcontext() as ctx:
        ctx.prec=38
        try:freight=catalog.freight(item)
        except (ValueError,KeyError,ArithmeticError) as error:
            freight=Rate(None,str(error),status='revisar_identificacao')
        return calculate_item(item,catalog,freight_override=freight)


def payroll_cost(params,weight,total):
    """N:AG; salário/prêmio ficam somente no processamento, não na resposta pública."""
    p={k:decimal(v) for k,v in params.items() if k not in ('gestores','encargos','base_manual','nivel','adicional_modo',
                                                        'dsr_comissao','dsr_premio','base_encargos')}
    additional=p['percentual']/12 if params.get('adicional_modo')=='UM_DOZE' else p['adicional_percentual']
    n=total*(p['percentual']+additional)
    o=n/p['dias_uteis']*p['domingos_feriados'] if params['dsr_comissao'] else Decimal(0)
    premium=p['premio']/p['dias_uteis']*p['domingos_feriados'] if params['dsr_premio'] else Decimal(0)
    q=p['salario']+p['premio']+n+o+premium if params['base_encargos'] else Decimal(0)
    charges=sum((decimal(v) for v in params['encargos']),Decimal(0))*q
    ac=n+o;ad=p['salario']+p['premio']+premium+charges
    period=p['dias_periodo']/p['dias_mes']
    return ((ac+ad*period)/weight if weight else Decimal(0)), ac+ad


def calculate_payroll(rules,items):
    """L/M: valor_produto e peso, antes dos filtros de família/canal/página."""
    result={};folhas=[r for r in rules if r['tipo']=='folha' and r.get('ativo',True)]
    for period in sorted({(str(r['inicio']),str(r['fim'])) for r in folhas}):
        selected=[r for r in folhas if (str(r['inicio']),str(r['fim']))==period]
        totals={};groups=defaultdict(lambda:Decimal(0)); invalid=False
        for r in selected:
            rows=[i for i in items if day(period[0])<=day(i['data'])<=day(period[1]) and
                  str(i.get('unidade_documento')).strip() in ('10','111','180') and
                  code(i.get('vendedor'))==code(r['dimensoes']['vendedor'])]
            if any(i.get('peso') is None or i.get('valor_produto') is None for i in rows):invalid=True
            w=sum((decimal(i.get('peso')) or Decimal(0) for i in rows),Decimal(0))
            m=sum((decimal(i.get('valor_produto')) or Decimal(0) for i in rows),Decimal(0))
            totals[r['registro']]=(w,m)
            for level,manager in enumerate(r['parametros'].get('gestores',[])):
                groups[level,manager]+=m
        for r in selected:
            if invalid:result[r['registro']]=None;continue
            w,m=totals[r['registro']];p=r['parametros']
            amount,_=payroll_cost(p,w,m)
            for level,manager in enumerate(p.get('gestores',[])):
                if not manager:continue # IFERROR lookup sem gestor: 0 comprovado
                candidates=[g for g in rules if g['tipo']=='gestor' and g['registro']==manager and overlaps(r,g) and g.get('ativo',True)]
                if len(candidates)!=1:amount=None;break
                g=candidates[0];gp=g['parametros'];denominator=groups[level,manager]
                if gp.get('base_manual') is not None:base=decimal(gp['base_manual'])
                else:
                    manager_level=int(gp['nivel'])-1
                    team=[totals[f['registro']] for f in selected if f['parametros'].get('gestores',['','',''])[manager_level]==manager]
                    _,base=payroll_cost(gp,sum((t[0] for t in team),Decimal(0)),sum((t[1] for t in team),Decimal(0)))
                amount+=base*(m/denominator)*decimal(p['dias_periodo'])/decimal(p['dias_mes'])/w if denominator and w else Decimal(0)
            result[r['registro']]=amount
    return result
