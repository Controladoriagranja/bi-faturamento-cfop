"""Tratativas exclusivas da conferência local; não usadas pela API nem pelo robô."""
from collections import Counter, defaultdict
from decimal import Decimal
import re
import unicodedata


def codigo(value):
    return str(value or '').strip().lstrip('0')


def final_cfop(row):
    found = re.fullmatch(r'[56](\d{3})(?:-.*)?', str(row.get('cfop') or '').strip())
    return found[1] if found else None


def bonificacao(row):
    text = unicodedata.normalize('NFKD', str(row.get('cfop_descricao') or ''))
    return 'bonificacao' in ''.join(c for c in text if not unicodedata.combining(c)).casefold()


def exclui_inicial(row):
    if codigo(row.get('produto')) == '384':
        return '1_PRODUTO_384'
    if bonificacao(row):
        return '2_BONIFICACAO'
    return None


def chave_vinculo(row):
    """Mesma chave da view: cliente/produto/pedido sem zeros, valor exato.

    Não acrescenta empresa, unidade, série ou data. Colisões não são resolvidas
    escolhendo arbitrariamente um registro.
    """
    parts = tuple(codigo(row.get(k)) for k in ('cliente', 'produto', 'pedido'))
    value = row.get('valor_total_faturado')
    return (*parts, Decimal(str(value))) if all(parts) and value is not None else None


def filtro_original(row, incluir_venda=False):
    if codigo(row.get('unidade_documento')) not in ('10', '111', '180', '102'):
        return 'ORIGINAL_UNIDADE'
    cfop = str(row.get('cfop') or '').strip()[-6:]
    if cfop in ('949-26', '949-28', '910-02', '905-01', '401-05') or cfop.startswith('922-'):
        return 'ORIGINAL_CFOP'
    if not incluir_venda and cfop == '118-01':
        return '3_VENDA_118_01'
    if not re.fullmatch(r'[0-9]{3,4}', codigo(row.get('produto'))):
        return 'ORIGINAL_PRODUTO'
    if any('lodo' in str(row.get(k) or '').lower() for k in ('produto_descricao', 'familia')):
        return 'ORIGINAL_LODO'
    if codigo(row.get('cliente')) in ('7768', '9880', '16807', '34748'):
        return 'ORIGINAL_CLIENTE'
    return None


def tratar(raw, view, donors):
    # Confirma que a reprodução dos filtros herdados não mudou o perímetro.
    baseline = {r['id'] for r in raw if filtro_original(r) is None}
    assert baseline == {r['id'] for r in view}, 'Filtros atuais da view diferem da rotina: interromper para revisar.'
    removed, keep_ids = [], set()
    for row in raw:
        reason = exclui_inicial(row)
        original = filtro_original(row)
        if reason is None:
            # Ordem herdada: unidades/CFOP, vendas, produto/lodo/cliente.
            if original in ('ORIGINAL_UNIDADE', 'ORIGINAL_CFOP'):
                reason = original
            elif str(row.get('cfop') or '').strip()[-6:] == '118-01':
                reason = '3_VENDA_118_01'
            elif final_cfop(row) in ('122', '118', '119'):
                reason = '4_VENDA_122_118_119'
            else:
                reason = original
        if reason:
            removed.append(dict(row, regra_exclusao=reason, estava_view_original=row['id'] in baseline))
        else:
            keep_ids.add(row['id'])
    old, expanded = defaultdict(list), defaultdict(list)
    for row in donors:
        if exclui_inicial(row):
            continue
        key = chave_vinculo(row)
        if key is None:
            continue
        if str(row.get('cfop') or '').strip()[-6:] == '118-01':
            old[key].append(row)
        if final_cfop(row) in ('122', '118', '119'):
            expanded[key].append(row)
    result, links = [], []
    for source in view:
        if source['id'] not in keep_ids:
            continue
        row = dict(source, _source='Checagem local sobre comercial.faturamento_cfop; produção preservada')
        if final_cfop(row) not in ('923', '924'):
            result.append(row)
            continue
        original = row.get('cond_pag_nota_original', row.get('cond_pag_nota'))
        previous = row.get('cond_pag_nota')
        # Desfaz somente a cópia derivada da view para reaplicar após exclusões.
        row['cond_pag_nota'] = original
        row['id_venda_correspondente'] = None
        key = chave_vinculo(row)
        existing = old.get(key, []) if str(row.get('cfop') or '').strip()[-6:] == '923-01' else []
        candidates = expanded.get(key, [])
        chosen, rule = None, None
        if len(existing) == 1 and str(existing[0].get('cond_pag_nota') or '').strip():
            chosen, rule = existing[0], '3_EXISTENTE_118_01_923_01'
        elif len(candidates) == 1 and str(candidates[0].get('cond_pag_nota') or '').strip():
            chosen, rule = candidates[0], '4_NOVA_122_118_119_923_924'
        if chosen is not None:
            row['cond_pag_nota'] = chosen['cond_pag_nota']
            row['id_venda_correspondente'] = chosen['id']
            row['cond_pag_nota_status'] = 'COPIADO_DA_VENDA_CHECAGEM'
        else:
            row['cond_pag_nota_status'] = ('CHAVE_INCOMPLETA' if key is None else
                'SEM_VENDA_CORRESPONDENTE' if not candidates else
                'VENDAS_AMBIGUAS' if len(candidates) != 1 else 'VENDA_SEM_CONDICAO')
        links.append(dict(id_remessa=row['id'], empresa=row.get('empresa_contexto'), unidade=row['unidade_documento'],
            serie=row['serie'], nf=row['nota_numero'], produto=row['produto'], cliente=row['cliente'],
            pedido=row.get('pedido'), data=row['data'], cfop_remessa=row['cfop'], valor_chave=row.get('valor_total_faturado'),
            regra_copia=rule, status=row['cond_pag_nota_status'], condicao_original=original,
            condicao_view_producao=previous, condicao_checagem=row['cond_pag_nota'],
            id_venda=chosen['id'] if chosen else None, cfop_venda=chosen['cfop'] if chosen else None,
            data_venda=chosen['data'] if chosen else None, quantidade_vendas_regra3=len(existing),
            quantidade_vendas_regra4=len(candidates), ids_candidatos=', '.join(str(r['id']) for r in candidates),
            valor_alterado=previous != row['cond_pag_nota']))
        result.append(row)
    assert {r['id'] for r in result} == keep_ids
    assert len(removed) + len(result) == len(raw)
    assert not any(exclui_inicial(r) or final_cfop(r) in ('122', '118', '119') for r in result)
    counts = Counter(r['regra_exclusao'] for r in removed)
    copies = Counter(r['regra_copia'] for r in links if r['regra_copia'])
    return result, removed, links, dict(raw=len(raw), view_original=len(view), tratados=len(result),
        excluidas=dict(counts), copias=dict(copies), vinculos_sem_copia=sum(r['regra_copia'] is None for r in links),
        exclusoes_incrementais=dict(Counter(r['regra_exclusao'] for r in removed if r['estava_view_original'])))
