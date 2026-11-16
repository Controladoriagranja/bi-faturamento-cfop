-- Faturamento por Vendedor Pai: fontes exclusivas do relatório.
-- Aplicar antes de apontar os GETs de filtros/resumo/detalhes para estas views.
-- As views anteriores e a fonte do Comparativo FOB permanecem preservadas.
-- Regra por ITEM, antes do agrupamento: uma NF mista conserva suas vendas.
-- Descrição: ignorar caixa e acentos em transferência/bonificação.
-- CFOP: finais 118, 119 e 122 com prefixo 5/6 e qualquer sufixo.
-- Produto: excluir 384, inclusive quando representado como 00384.
-- Não há lista de NFs: as quatro vendas válidas de outubro continuam elegíveis.
BEGIN;

CREATE OR REPLACE VIEW comercial.vw_faturamento_vendedor_pai_itens AS
SELECT f.*
FROM comercial.vw_faturamento_cfop_filtrado AS f
-- BEGIN_FILTRO_FATURAMENTO_NF
WHERE TRANSLATE(
        LOWER(COALESCE(f.cfop_descricao, '')),
        'áàâãäéèêëíìîïóòôõöúùûüç',
        'aaaaaeeeeiiiiooooouuuuc'
      ) !~ '(transferencia|bonificacao)'
  AND COALESCE(BTRIM(f.cfop), '') !~ '^[56](118|119|122)(-|$)'
  AND COALESCE(LTRIM(BTRIM(f.produto), '0'), '') <> '384';
-- END_FILTRO_FATURAMENTO_NF

-- Mesma chave e classificação da view vigente, conferida em 16/11/2026.
-- Altera somente a fonte dos itens, preservando as regras por unidade.
CREATE OR REPLACE VIEW comercial.vw_nf_por_vendedor_pai_faturamento AS
WITH itens AS (
    SELECT NULLIF(BTRIM(unidade_documento), '') AS unidade_documento,
           NULLIF(BTRIM(serie), '') AS serie,
           NULLIF(BTRIM(nota_numero), '') AS nota_numero,
           data,
           CASE WHEN NULLIF(BTRIM(vendedor), '') IS NULL THEN NULL
                ELSE COALESCE(NULLIF(LTRIM(BTRIM(vendedor), '0'), ''), '0')
           END AS vendedor,
           NULLIF(BTRIM(produto), '') AS produto,
           peso, valor_total_faturado, carregado_em
    FROM comercial.vw_faturamento_vendedor_pai_itens
), notas AS (
    SELECT unidade_documento, serie, nota_numero,
           MIN(data) AS data,
           CASE WHEN COUNT(DISTINCT vendedor) = 1 THEN MIN(vendedor) END AS vendedor,
           COUNT(DISTINCT vendedor) AS vendedores_distintos,
           COUNT(DISTINCT data) AS datas_distintas,
           COUNT(DISTINCT produto) AS qtde_produtos_distintos,
           COALESCE(SUM(peso), 0::numeric) AS peso_total_nf,
           COALESCE(SUM(valor_total_faturado), 0::numeric) AS valor_total_nf,
           COUNT(*) AS qtde_itens,
           MAX(carregado_em) AS carregado_em
    FROM itens
    GROUP BY unidade_documento, serie, nota_numero
)
SELECT JSONB_BUILD_ARRAY(n.unidade_documento, n.serie, n.nota_numero)::text AS chave_nf,
       n.data, n.unidade_documento, n.serie, n.nota_numero, n.vendedor,
       CASE
           WHEN LTRIM(BTRIM(n.unidade_documento), '0') = '180' THEN 'CD Ribeirão das Neves'
           WHEN LTRIM(BTRIM(n.unidade_documento), '0') = '102' THEN 'Januária'
           ELSE COALESCE(NULLIF(BTRIM(g.vendedor_pai), ''), 'Não classificado')
       END AS vendedor_pai,
       n.qtde_produtos_distintos, n.peso_total_nf, n.valor_total_nf, n.qtde_itens,
       n.carregado_em,
       (n.vendedores_distintos > 1 OR n.datas_distintas > 1
        OR n.unidade_documento IS NULL OR n.serie IS NULL OR n.nota_numero IS NULL
        OR n.data IS NULL) AS divergencia_nf
FROM notas AS n
LEFT JOIN comercial.vendedor_grupo AS g ON g.vendedor = n.vendedor;

COMMENT ON VIEW comercial.vw_faturamento_vendedor_pai_itens IS
    'Itens do Faturamento por Vendedor Pai: exclui transferencias, bonificacoes, CFOPs 5/6 finais 118/119/122 e produto 384. Fonte FOB preservada.';
COMMENT ON VIEW comercial.vw_nf_por_vendedor_pai_faturamento IS
    'NFs do Faturamento por Vendedor Pai agregadas apos as exclusoes. Resumo e detalhes devem usar as duas views exclusivas do relatorio.';

COMMIT;
