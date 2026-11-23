-- Cadastros de fechamento separados dos fretes/despesas comerciais por item.
-- Não altera objetos existentes nem faturamento.
CREATE TABLE IF NOT EXISTS comercial.fob_fechamento_lote (
 lote uuid PRIMARY KEY,
 competencia date NOT NULL,
 arquivos jsonb NOT NULL,
 resumo jsonb NOT NULL,
 ator bigint NOT NULL,
 executado_em timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS comercial.fob_fechamento_mensal (
 competencia date PRIMARY KEY CHECK (extract(day FROM competencia)=1),
 conteudo jsonb NOT NULL CHECK (jsonb_typeof(conteudo)='object'),
 assinatura text NOT NULL CHECK (length(assinatura)=64),
 versao integer NOT NULL CHECK (versao>0),
 lote uuid NOT NULL REFERENCES comercial.fob_fechamento_lote(lote),
 atualizado_por bigint NOT NULL,
 atualizado_em timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS comercial.fob_fechamento_mensal_historico (
 competencia date NOT NULL,
 versao integer NOT NULL,
 lote uuid NOT NULL REFERENCES comercial.fob_fechamento_lote(lote),
 conteudo jsonb NOT NULL,
 assinatura text NOT NULL,
 registrado_por bigint NOT NULL,
 registrado_em timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (competencia,versao)
);
