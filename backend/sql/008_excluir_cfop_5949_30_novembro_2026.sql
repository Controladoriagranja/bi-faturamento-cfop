-- Exclusão pontual autorizada: CFOP exato 5949-30, somente novembro/2026.
-- Duas telas usam esta fonte; nenhum registro original é apagado.
-- Preserva colunas, proprietário e permissões da view existente.
-- Definição anterior salva antes da aplicação; não recria a view agregada.
BEGIN;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '15s';
CREATE OR REPLACE VIEW comercial.vw_faturamento_vendedor_pai_itens AS
SELECT f.*
FROM (
SELECT id,
    empresa_contexto,
    unidade_contexto,
    processo,
    periodo_inicio,
    periodo_fim,
    carregado_em,
    vendedor,
    vendedor_nome,
    data,
    mes,
    meio_venda,
    devolucao,
    unidade_documento,
    serie,
    nota_numero,
    pedido,
    oc_principal,
    redespacho,
    romaneio,
    frete,
    cliente,
    rede,
    razao_social,
    tipo_de_cliente,
    nome_fantasia,
    rota_cliente,
    rota_pedido,
    cidade,
    uf,
    ramo_ativ,
    produto,
    produto_descricao,
    um,
    familia,
    cfop,
    cfop_descricao,
    volumes,
    peso,
    lista,
    ocorr,
    pre_base,
    preco_praticado,
    valor_produto,
    desconto_comercial,
    valor_total_faturado,
    desc_finan,
    frete_kg,
    nota_refaturada,
    romaneio_refaturada,
    nota_devolucao,
    cliente_original,
    cond_pag_cliente,
    cond_pag_nota,
    ano_semana,
    numero_semana,
    frete_sem_valor,
    cond_pag_nota_original,
    cond_pag_nota_status,
    id_venda_correspondente
   FROM comercial.vw_faturamento_cfop_filtrado f
  WHERE translate(lower(COALESCE(cfop_descricao, ''::text)), 'áàâãäéèêëíìîïóòôõöúùûüç'::text, 'aaaaaeeeeiiiiooooouuuuc'::text) !~ '(transferencia|bonificacao)'::text AND COALESCE(btrim(cfop), ''::text) !~ '^[56](118|119|122)(-|$)'::text AND COALESCE(ltrim(btrim(produto), '0'::text), ''::text) <> '384'::text
) AS f
WHERE NOT (COALESCE((f.data >= DATE '2026-11-01' AND f.data < DATE '2026-12-01' AND BTRIM(f.cfop) = '5949-30'), FALSE));
COMMIT;
