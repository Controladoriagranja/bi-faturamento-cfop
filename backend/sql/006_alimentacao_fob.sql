-- PREPARAÇÃO LOCAL. Aplicação futura pelo DBA, após backup. Não executar pelo robô.
-- Preserva faturamento_cfop, suas views, frete_manual_nf e custo_mensal_januaria.
BEGIN;
CREATE TABLE comercial.fob_importacao (
    lote uuid PRIMARY KEY,
    executado_em timestamptz NOT NULL DEFAULT clock_timestamp(),
    status text NOT NULL CHECK (status IN ('VALIDADO','REJEITADO','REVERTIDO')),
    arquivos jsonb NOT NULL,
    resumo jsonb NOT NULL DEFAULT '{}'::jsonb,
    erros jsonb NOT NULL DEFAULT '[]'::jsonb
);
CREATE TABLE comercial.fob_cadastro (
    registro text PRIMARY KEY,
    tipo text NOT NULL CHECK (tipo IN ('frete','comissao','adicional_comissao','contrato',
        'contrato_administracao','logistica_reversa','pallet','descarga','folha','gestor')),
    inicio date NOT NULL,
    fim date NOT NULL CHECK (fim >= inicio),
    dimensoes jsonb NOT NULL CHECK (jsonb_typeof(dimensoes)='object'),
    modalidade text NOT NULL CHECK (modalidade IN ('KG','PERCENTUAL','FOLHA','TOTAL_NF','TOTAL_ITEM')),
    valor numeric(38,20) NOT NULL CHECK (valor>=0 AND valor<1e18::numeric AND valor<>'NaN'::numeric),
    parametros jsonb NOT NULL DEFAULT '{}'::jsonb,
    origem text NOT NULL,
    ativo boolean NOT NULL DEFAULT true,
    versao integer NOT NULL DEFAULT 1 CHECK (versao>0),
    lote uuid NOT NULL REFERENCES comercial.fob_importacao(lote),
    atualizado_em timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX fob_cadastro_vigencia ON comercial.fob_cadastro(tipo,inicio,fim) WHERE ativo;
CREATE INDEX fob_cadastro_dimensoes ON comercial.fob_cadastro USING gin(dimensoes);
CREATE TABLE comercial.fob_cadastro_historico (
    registro text NOT NULL,
    versao integer NOT NULL,
    lote uuid NOT NULL REFERENCES comercial.fob_importacao(lote),
    conteudo jsonb NOT NULL,
    registrado_em timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (registro,versao)
);
CREATE TABLE comercial.fob_januaria_historico (
    lote uuid NOT NULL REFERENCES comercial.fob_importacao(lote),
    competencia date NOT NULL,
    antes jsonb,
    depois jsonb NOT NULL,
    PRIMARY KEY (lote,competencia)
);
REVOKE ALL ON comercial.fob_importacao,comercial.fob_cadastro,
    comercial.fob_cadastro_historico,comercial.fob_januaria_historico FROM PUBLIC;
COMMIT;

-- Índices NOVOS de apoio (não são views); executar separadamente, fora de transação,
-- após conferir EXPLAIN e índices equivalentes já existentes. Não executados nesta entrega.
-- CREATE INDEX CONCURRENTLY fob_nf_origem ON comercial.faturamento_cfop
-- (empresa_contexto,btrim(unidade_documento),btrim(serie),btrim(nota_numero),
--  (extract(year FROM data)::integer));
-- CREATE INDEX CONCURRENTLY fob_data_origem ON comercial.faturamento_cfop(data);

-- Privilégios: substituir SOMENTE os nomes de papéis após conferência do DBA.
-- Não criar usuário/senha neste arquivo nem reutilizar portal_bi_writer.
-- GRANT USAGE ON SCHEMA comercial TO "PAPEL_ROBO_FOB";
-- GRANT SELECT ON comercial.vw_faturamento_cfop_filtrado,
--   comercial.faturamento_cfop,comercial.custo_mensal_januaria TO "PAPEL_ROBO_FOB";
-- GRANT SELECT,INSERT ON comercial.fob_importacao,comercial.fob_cadastro_historico,
--   comercial.fob_januaria_historico TO "PAPEL_ROBO_FOB";
-- GRANT UPDATE (resumo) ON comercial.fob_importacao TO "PAPEL_ROBO_FOB";
-- GRANT SELECT,INSERT,UPDATE ON comercial.fob_cadastro TO "PAPEL_ROBO_FOB";
-- GRANT INSERT (competencia,custo_kg,criado_por,atualizado_por),
--   UPDATE (custo_kg,versao,atualizado_por,atualizado_em)
--   ON comercial.custo_mensal_januaria TO "PAPEL_ROBO_FOB";
-- GRANT SELECT ON comercial.fob_importacao,comercial.fob_cadastro,
--   comercial.custo_mensal_januaria TO "PAPEL_API_LEITURA";
-- API não precisa de leitura das tabelas de histórico nem de escrita.
