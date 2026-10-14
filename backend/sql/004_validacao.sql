-- Executar após implantação dos scripts 001, 002 e 003.
-- Auditoria cadastral: a PK já impede duplicidades.
SELECT COUNT(*) AS registros,COUNT(DISTINCT vendedor) AS codigos_unicos
FROM comercial.vendedor_grupo;

-- Divergências bloqueiam o relatório, evitando escolher vendedor arbitrário.
SELECT chave_nf,unidade_documento,serie,nota_numero,vendedor,divergencia_nf
FROM comercial.vw_nf_por_vendedor_pai WHERE divergencia_nf;

-- NF distinta na origem deve ser igual a uma linha por NF na view analítica.
SELECT 'origem' AS fonte,
       COUNT(DISTINCT (BTRIM(unidade_documento),BTRIM(serie),BTRIM(nota_numero))) AS nfs,
       SUM(peso) AS peso,SUM(valor_total_faturado) AS valor
FROM comercial.vw_faturamento_cfop_filtrado
WHERE data>=DATE '2026-09-06' AND data<DATE '2026-09-13'
UNION ALL
SELECT 'view_nf',COUNT(*),SUM(peso_total_nf),SUM(valor_total_nf)
FROM comercial.vw_nf_por_vendedor_pai
WHERE data>=DATE '2026-09-06' AND data<DATE '2026-09-13';

SELECT vendedor_pai,COUNT(*) AS qtde_nfs,
       SUM(qtde_produtos_distintos)::NUMERIC/NULLIF(COUNT(*),0) AS qtde_produto_por_nf,
       SUM(peso_total_nf)/NULLIF(COUNT(*),0) AS peso_por_nf,
       SUM(valor_total_nf)/NULLIF(COUNT(*),0) AS ticket_medio_por_nf
FROM comercial.vw_nf_por_vendedor_pai
WHERE data>=DATE '2026-09-06' AND data<DATE '2026-09-13'
GROUP BY vendedor_pai ORDER BY vendedor_pai;

-- Não classificado NÃO é Sem Vínculo; nada é excluído dos totais.
SELECT vendedor,COUNT(*) AS nfs,SUM(valor_total_nf) AS valor
FROM comercial.vw_nf_por_vendedor_pai
WHERE vendedor_pai='Não classificado'
  AND data>=DATE '2026-09-06' AND data<DATE '2026-09-13'
GROUP BY vendedor ORDER BY vendedor;
