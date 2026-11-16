# Exclusões do Faturamento por Vendedor Pai

## Situação em 16/11/2026

As duas views exclusivas abaixo foram criadas e validadas no PostgreSQL.
A integração dos GETs foi preparada sobre `api_zootecnico(7).zip`, enviado
em 16/11/2026. O pacote altera somente três arquivos do módulo. A API
instalada ainda depende de receber esses arquivos.

| Uso | Fonte |
| --- | --- |
| Filtros, resumo e seleção de NFs nos detalhes | `comercial.vw_nf_por_vendedor_pai_faturamento` |
| Itens, busca e exportação dos detalhes | `comercial.vw_faturamento_vendedor_pai_itens` |

`config.py` aponta filtros, resumo e seleção de NFs para a nova view de NFs.
`details.py` aponta itens, busca e exportação para a nova view de itens.
`service.py` informa a fonte configurada e a versão
`faturamento-nf-exclusoes-2026-11-16` na resposta do resumo.
Endpoints, parâmetros, autenticação, paginação e contratos de colunas permanecem
iguais. Nenhum arquivo de outro módulo foi incluído na substituição.

Na consulta de itens, `SET LOCAL enable_nestloop = off` evita que o plano
revarra os itens para cada nota. O plano original subestimava a quantidade de
NFs e a ordenação ultrapassou 15 segundos na validação. O ajuste é restrito à
transação do GET, encerrada pelo contexto da conexão da API atual. Não altera
configuração do servidor, outras conexões ou o limite existente de 15 segundos.

## Regras

Aplicadas por item, antes da agregação de NFs, para qualquer período:

1. Excluir descrição do CFOP contendo `transferencia` ou `bonificacao`,
   ignorando maiúsculas/minúsculas e os acentos normalizados no SQL.
2. Excluir CFOP de prefixo 5/6 e final 118, 119 ou 122, com qualquer sufixo.
3. Excluir produto 384, normalizando espaços e zeros à esquerda.

Não há lista fixa de notas. As NFs 659057, 659075 e 660315 da unidade 10
e 808715 da unidade 111 permanecem porque seus itens são elegíveis.
Notas mistas mantêm somente os itens elegíveis; os pesos, valores,
produtos distintos e quantidades de itens são recalculados antes das médias.

A classificação mantém a definição vigente consultada em produção:
unidade 180 recebe CD Ribeirão das Neves; unidade 102 recebe Januária;
as demais usam `comercial.vendedor_grupo`.
A chave continua unidade, série e NF, normalizando espaços, preservando zeros.
Não foram alteradas regras de condição de pagamento, preço, frete ou ticket.

## Validação de outubro

| Medida | Antes | Nas views novas |
| --- | ---: | ---: |
| NFs | 12.040 | 11.938 |
| Itens | 27.415 | 26.927 |
| Peso kg | 16.276.863,29 | 14.691.917,00 |
| Valor total faturado R$ | 112.990.219,55 | 98.700.493,55 |

Foram excluídos 465 itens de transferência, 8 de bonificação, 11 dos CFOPs
118/119/122 e 4 do produto 384. São 102 NFs integralmente excluídas no mês.
Não há NF parcialmente excluída nesse recorte atual.

As 102 NFs incluem as 101 adicionais identificadas e a NF 808965, unidade 111,
que também existe no Excel como bonificação. A regra geral autorizada exclui
essa nota. Por isso, o novo total é 11.935 do Excel + 4 mantidas - 1 bonificação.

Os cinco casos de vendedor pai divergente e a base AJ/AL do ticket de Januária
continuam separados desta mudança. Não foram criadas classificações artificiais
nem copiados valores financeiros do Excel.

Foram executados 15 casos curtos de regras com SELECT, um caso sintético de NF
mista e conferências reais de totais, quatro notas mantidas, contratos de colunas
e preservação das definições das fontes vigentes. A transação de criação foi
confirmada somente após as verificações.

## Arquivos e preservação

- SQL: `backend/sql/007_faturamento_nf_exclusoes.sql`.
- Validação: `tests/validar_faturamento_nf_exclusoes.py`.
- Integração da API: `backend/integrar_api_anderson_faturamento_nf.py`.
- Consultas do serviço: `tests/validar_gets_faturamento_nf_views.py`.
- Pacote: `outputs/atualizacao-faturamento-nf-20261116/api_anderson_faturamento_nf_20261116.zip`.
  Copiar `bi_generic/` para a raiz da API do Anderson e substituir somente
  `bi_generic/faturamento_nf/config.py`, `details.py` e `service.py`.
  Atualizar o contêiner pelo procedimento habitual. O manifesto contém hashes
  anteriores/novos e o pacote contém instruções de reversão.
- Backup: `artifacts/backups/aplicacao-faturamento-outubro-20261116-130334/`.
  Contém definições originais, recorte de dados, arquivos anteriores e resultado
  `validacao-views-criadas.json`. `api_atual_7/` preserva o ZIP fornecido e os
  três arquivos anteriores.

O SQL já foi executado na produção nesta sessão. Não é necessário reaplicá-lo
para integrar a API. `CREATE OR REPLACE VIEW` está no script para instalações
controladas; nenhuma tabela financeira é modificada.

As fontes `comercial.vw_faturamento_cfop_filtrado` e
`comercial.vw_nf_por_vendedor_pai` mantiveram suas definições originais.
Não houve alteração de faturamento bruto, cadastros financeiros, arquivos Excel,
FOB, Worker, Docker, frontend, agendamento ou API instalada. Os três arquivos
locais do módulo foram sincronizados com a API fornecida e com as alterações
descritas acima. O Portal continua na fonte anterior até instalar a atualização
dos GETs.

As consultas preparadas para filtros, resumo, detalhes de notas/itens,
ordenação, paginação, nota mantida, nota excluída e busca são verificadas
diretamente no PostgreSQL, em transações somente leitura. A camada HTTP,
autenticação e Worker precisam ser homologados depois da instalação.
