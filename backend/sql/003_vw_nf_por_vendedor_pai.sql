-- Uma NF é unidade + série + número. Itens NÃO são notas fiscais.
-- Agrega antes do JOIN; vendedor_grupo tem vendedor único.
CREATE OR REPLACE VIEW comercial.vw_nf_por_vendedor_pai AS
WITH itens AS (
    SELECT NULLIF(BTRIM(unidade_documento),'') AS unidade_documento,
           NULLIF(BTRIM(serie),'') AS serie,
           NULLIF(BTRIM(nota_numero),'') AS nota_numero,
           data::DATE AS data,
           CASE WHEN NULLIF(BTRIM(vendedor),'') IS NULL THEN NULL
                ELSE COALESCE(NULLIF(LTRIM(BTRIM(vendedor),'0'),''),'0') END AS vendedor,
           NULLIF(BTRIM(produto),'') AS produto,
           peso,valor_total_faturado,carregado_em
    FROM comercial.vw_faturamento_cfop_filtrado
), notas AS (
    SELECT unidade_documento,serie,nota_numero,
           MIN(data) AS data,
           CASE WHEN COUNT(DISTINCT vendedor)=1 THEN MIN(vendedor) END AS vendedor,
           COUNT(DISTINCT vendedor) AS vendedores_distintos,
           COUNT(DISTINCT data) AS datas_distintas,
           COUNT(DISTINCT produto) AS qtde_produtos_distintos,
           COALESCE(SUM(peso),0) AS peso_total_nf,
           COALESCE(SUM(valor_total_faturado),0) AS valor_total_nf,
           COUNT(*) AS qtde_itens,MAX(carregado_em) AS carregado_em
    FROM itens GROUP BY unidade_documento,serie,nota_numero
)
SELECT JSONB_BUILD_ARRAY(n.unidade_documento,n.serie,n.nota_numero)::TEXT AS chave_nf,
       n.data,n.unidade_documento,n.serie,n.nota_numero,n.vendedor,
       CASE
           -- Grupos ainda sem regra: não atribuir NFs a placeholders zerados.
           WHEN g.vendedor_pai IN ('CD Ribeirão das Neves','Januária') THEN 'Não classificado'
           ELSE COALESCE(NULLIF(BTRIM(g.vendedor_pai),''),'Não classificado')
       END AS vendedor_pai,
       n.qtde_produtos_distintos,n.peso_total_nf,n.valor_total_nf,n.qtde_itens,
       n.carregado_em,
       (n.vendedores_distintos>1 OR n.datas_distintas>1
        OR n.unidade_documento IS NULL OR n.serie IS NULL OR n.nota_numero IS NULL
        OR n.data IS NULL) AS divergencia_nf
FROM notas n
LEFT JOIN comercial.vendedor_grupo g ON g.vendedor=n.vendedor;
