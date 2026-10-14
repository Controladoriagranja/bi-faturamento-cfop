-- Implantação futura em bi_granja: tabela auxiliar apenas do módulo Comercial.
CREATE TABLE IF NOT EXISTS comercial.vendedor_grupo (
    vendedor TEXT PRIMARY KEY CHECK (vendedor = BTRIM(vendedor) AND vendedor <> ''),
    nome TEXT NOT NULL,
    canal_venda TEXT NOT NULL,
    vendedor_pai TEXT NOT NULL
);
