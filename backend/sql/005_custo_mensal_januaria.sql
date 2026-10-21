-- Aplicação futura pelo administrador. NÃO executar por extrator/API.
-- Não altera comercial.frete_manual_nf nem comercial.vw_frete_manual_nf.
BEGIN;
CREATE TABLE comercial.custo_mensal_januaria (
    competencia date PRIMARY KEY,
    custo_kg numeric(18,10) NOT NULL,
    versao integer NOT NULL DEFAULT 1 CHECK (versao BETWEEN 1 AND 2147483647),
    criado_por text NOT NULL CHECK (criado_por ~ '^[1-9][0-9]*$'),
    criado_em timestamptz NOT NULL DEFAULT clock_timestamp(),
    atualizado_por text NOT NULL CHECK (atualizado_por ~ '^[1-9][0-9]*$'),
    atualizado_em timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (competencia >= DATE '2000-01-01' AND competencia <= DATE '2100-12-01'
        AND EXTRACT(DAY FROM competencia) = 1),
    CHECK (custo_kg >= 0 AND custo_kg <> 'NaN'::numeric)
);
REVOKE ALL ON comercial.custo_mensal_januaria FROM PUBLIC;
GRANT SELECT ON comercial.custo_mensal_januaria TO portal_bi_writer;
GRANT INSERT (competencia,custo_kg,criado_por,atualizado_por)
    ON comercial.custo_mensal_januaria TO portal_bi_writer;
GRANT UPDATE (custo_kg,atualizado_por,atualizado_em,versao)
    ON comercial.custo_mensal_januaria TO portal_bi_writer;
-- Sem DELETE, sem sequence/identity e sem alteração dos privilégios de outros objetos.
COMMIT;

-- O administrador deve conceder SELECT ao papel efetivamente usado por banco().
-- O nome desse papel não foi fornecido; NÃO presumir nem conceder a PUBLIC:
-- GRANT SELECT ON comercial.custo_mensal_januaria TO "PAPEL_REAL_DE_LEITURA";
-- O mesmo papel já precisa de SELECT em comercial.vw_frete_manual_nf.
-- Não há INSERT de outubro/2026: seu valor ainda não foi informado.
