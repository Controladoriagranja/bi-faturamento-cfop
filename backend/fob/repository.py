"""SELECTs pequenos opcionais. Não abre conexões nem é registrado na API."""
from .freight import FreightOverrides, MONTHLY_TABLE, invoice_key


def read_freight_overrides(conn, items):
    """Leitura em lote; peso integral é sempre o da view, não o do filtro FOB."""
    monthly=conn.execute('SELECT * FROM '+MONTHLY_TABLE+' ORDER BY competencia').fetchall()
    keys=set()
    for item in items:
        if str(item.get('unidade_documento')).strip(' ')=='102':continue
        try:keys.add(invoice_key(item))
        except ValueError:continue
    manuals=[];keys=sorted(keys)
    for offset in range(0,len(keys),500):
        chunk=keys[offset:offset+500]
        placeholders=','.join(['(%s,%s,%s,%s,%s)']*len(chunk))
        rows=conn.execute('SELECT * FROM comercial.vw_frete_manual_nf '
            'WHERE (empresa,unidade,serie,nf,ano_nf) IN ('+placeholders+') LIMIT %s',
            [*(value for key in chunk for value in key),len(chunk)*2+1]).fetchall()
        if len(rows)>len(chunk)*2:raise ValueError('Identificação ambígua na view de fretes manuais.')
        manuals.extend(rows)
    return FreightOverrides(monthly,manuals)
def read_invoice(conn, *, unit, invoice, customer=None, raw=False):
    """Mesmo contrato de conexão somente leitura da API; limite de 100 itens."""
    table='comercial.faturamento_cfop' if raw else 'comercial.vw_faturamento_cfop_filtrado'
    # Identificadores vêm exclusivamente destas duas constantes.
    query='SELECT * FROM '+table+' WHERE unidade_documento = %s AND nota_numero = %s'
    params=[str(unit),str(invoice)]
    if customer is not None:
        # Normaliza apenas o código do cliente (CSV contém zeros à esquerda).
        query+=" AND COALESCE(NULLIF(LTRIM(BTRIM(cliente),'0'),''),'0') = %s"
        params.append(str(customer).strip().lstrip('0') or '0')
    query+=' LIMIT 101'
    rows=conn.execute(query,params).fetchall()
    if len(rows)>100:raise ValueError('Mais de 100 itens: restrinja a seleção; nenhuma consulta ampla será feita.')
    return [{**row,'_source':table} for row in rows]
