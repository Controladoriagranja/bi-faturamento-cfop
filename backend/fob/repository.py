"""SELECTs pequenos opcionais. Não abre conexões nem é registrado na API."""
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
