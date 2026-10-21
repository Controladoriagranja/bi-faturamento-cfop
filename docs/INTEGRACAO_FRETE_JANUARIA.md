# Frete manual e Januária — preparação local de 21/10/2026

Implementação preparada para uma única integração futura. Não houve acesso ao servidor, SQL de produção, Docker, deploy ou commit. Nenhum ZIP foi criado ou sobrescrito. O módulo pronto está em `artifacts/integracao_fob/bi_generic/comparativo_fob/`; ele contém apenas o módulo FOB, com imports relativos e o catálogo original preservado. Não contém uma cópia do serviço principal nem de outros BIs.

## Regras implementadas

Unidade 102: custo próprio do mês/ano da emissão da NF; se não houver, custo de outubro/2026; se outubro não estiver cadastrado, pendência. A regra vale para todos os tipos de frete, inclusive 2/3/4/5/9. O custo mensal substitui todo o frete e não acumula original, manual por NF nem redespacho. Não foi cadastrado valor de outubro; 0,6127658 não é um padrão deste código. Zero mensal explícito é aceito, não é ausência.

Outras unidades: manual válido da view substitui todo o frete; sem manual válido, mantém o motor anterior. Chave: empresa_contexto exata, BTRIM de unidade/série/NF e ano da emissão. Isso reproduz a definição de `vw_frete_manual_nf` fornecida pelo usuário e preserva zeros à esquerda. A chave antiga `item_key` continua sendo usada somente para o perímetro do Excel.

A view existente identifica candidatos com ao menos um item de frete tipo 1 zerado/nulo na view filtrada e calcula o peso pela NF integral de `comercial.faturamento_cfop`. A integração lê `frete_manual_kg` dessa view, valida identificação, total/peso positivos, quantidade de itens, versão, datas/clientes distintos e unicidade; não recalcula denominador com itens da família, canal, período ou página. Duplicidade invalida a substituição sem multiplicar itens. O frete original é mantido para auditoria. Quando uma NF sai da view de candidatos, o manual não é aplicado automaticamente pelo simples fato de continuar na tabela auxiliar.

A definição fornecida recalcula kg com o peso atual e não mantém o peso do momento do cadastro na tabela auxiliar. Portanto esta integração segue a taxa atual da view; não pode detectar retrospectivamente troca de um cliente único por outro ou comparar com um peso cadastrado inexistente. Não foi inventado histórico/snapshot nem alterado o schema de frete por NF.

O cálculo continua no backend com Decimal; a tela somente formata/apresenta os resultados. Em 01–04/10, perímetro, CFOPs, famílias, canais e demais despesas foram preservados. A regra nova altera legitimamente Januária, inclusive notas que antes tinham frete zero por tipo, e notas com manual válido. Excel permanece como comparação, sem forçar coincidência dos totais.

No histórico, somente o componente frete comprovado é conhecido; comissão e demais despesas continuam pendentes, assim como o FOB. Resumo e detalhes usam o mesmo conjunto filtrado e a mesma fonte do substituto. Agrupamento de manuais protege os JOINs contra multiplicação. O resultado financeiro não fica mais no cache de 45 segundos: cada consulta relê os dados atuais. Após salvar, o usuário deve consultar novamente o comparativo. O catálogo de despesas do Excel continua imutável/em cache.

## Endpoints definitivos do cadastro mensal

GET e PUT: `/api/comercial-html/fretes-manuais/custos-januaria`.

Autenticação: Basic técnico do serviço existente, mais sessão CENTRAL encaminhada pelo Worker. O navegador envia somente o Bearer existente. As duas operações reutilizam `frete_manual_auth.authorize_frete`, incluindo `comercial.frete.editar` e o ID permanente do funcionário. O writer é `frete_manual.banco_escrita`, que usa `FRETE_WRITE_DATABASE_URL`; não há fallback para a conexão de leitura nem contrato novo da CENTRAL.

GET: `competencia=AAAA-MM` obrigatório; `pagina` padrão 1 (1–1000), `tamanho` padrão 20 (1–100). Retorna:

```json
{
  "competencia": "2026-10",
  "custo_proprio": null,
  "custo_aplicado": {
    "custo_kg": null,
    "status": "pendente_custo_mensal",
    "origem": "comercial.custo_mensal_januaria",
    "competencia_nf": "2026-10",
    "competencia_origem": "2026-10"
  },
  "custos": [],
  "pagina": 1,
  "tem_proxima": false
}
```

Quando existem, `custo_proprio` e cada linha de `custos` contêm `competencia` (AAAA-MM-01), `custo_kg` (string decimal), `versao`, `criado_por`, `criado_em`, `atualizado_por`, `atualizado_em`. `custo_aplicado.status` é `mensal`, `mensal_provisorio` ou `pendente_custo_mensal`; quando há custo inclui também versão, última alteração e `provisorio` booleano. A paginação é do histórico de cadastros, não de um histórico completo de todas as revisões.

PUT recebe somente `competencia`, `custo_kg` e `versao`. Exemplo exclusivamente fictício de estrutura, não aplicado como cadastro:

```json
{"competencia":"2026-11","custo_kg":"0.1234567890","versao":0}
```

`versao=0` cria; versão atual positiva altera com concorrência otimista. Custo não negativo, NUMERIC(18,10): até 8 dígitos inteiros e 10 casas. Competência entre 2000-01 e 2100-12. Campos extras/booleanos inválidos são rejeitados; funcionário é derivado da CENTRAL. Resposta 200: `{"ok":true,"custo":{...registro completo...}}`. Sem exclusão. Erros: 401 sessão, 403 operação, 409 concorrência, 422 validação e 503 indisponibilidade/confirmação incerta. Após 409/resultado incerto, a tela exige consulta/revisão e não reenvia automaticamente.

Os GET/PUT existentes `/api/comercial-html/fretes-manuais` permanecem na API original, sem mudanças. A tela por NF foi alinhada à restrição positiva real: zero é rejeitado para total por NF; zero mensal continua permitido.

## SQL para aplicação posterior

`backend/sql/005_custo_mensal_januaria.sql` cria exclusivamente `comercial.custo_mensal_januaria`, competência única, NUMERIC(18,10), auditoria e versão. Não usa sequence/identity nem concede DELETE. Para `portal_bi_writer`, concede SELECT e INSERT/UPDATE apenas das colunas necessárias. O administrador precisa confirmar o papel efetivamente usado por `banco()` e conceder SELECT nele; o nome não foi presumido. Não altera nem recria as duas estruturas existentes de frete manual. Não há INSERT de custo real.

## Arquivos da futura integração no Anderson

Conferir primeiro a versão mais recente do servidor. Mesclar SOMENTE a pasta `bi_generic/comparativo_fob/`; não substituir `bi_generic/` inteira. Comparação com `api_zootecnico_frete_manual_final.zip`:

| Arquivo relativo em bi_generic/comparativo_fob/ | Ação |
| --- | --- |
| `freight.py` | Novo: resolução pura e auditoria de substitutos |
| `monthly.py` | Novo: cadastro mensal e reutilização da autorização/writer existentes |
| `historical.py` | Novo nessa base: histórico com despesas pendentes e frete comprovado |
| `calculator.py` | Alterado: precedência mensal e manual |
| `repository.py` | Alterado: leituras em lote dos cadastros |
| `service.py` | Alterado: integração por item, histórico e remoção do cache financeiro |
| `routes.py` | Alterado: factory registra as três rotas FOB e as duas mensais |
| `config.py` | Alterado: cache financeiro desativado; localização relativa do catálogo |
| `aggregation.py` | Preservado na base recebida |
| `reference.py`, `snapshot.py`, `workbook.py`, `__init__.py`, `referencia_excel.json` | Preservados na base recebida |

O ZIP final já importa `criar_router_comparativo_fob` e registra o módulo. A factory nova mantém esse mesmo nome e inclui os dois conjuntos de rotas. Não acrescentar registro duplicado nem substituir `servico_zootecnico.py`. Não modificar `modules/comparativo_fob/` legado, que não é o pacote importado nesse registro.

Preservar `frete_manual.py`, `frete_manual_auth.py`, `comercial_acesso.py`, autenticação, configuração, Dockerfile e demais BIs da versão mais atual. Nenhum desses arquivos é entregue como substituição. O helper local `module_files()` em `backend/empacotar_comparativo_fob.py` apenas prepara o módulo; não se executou o CLI gerador de ZIP/serviço.

## Validação e homologação

Testes temporários fora do projeto: rotas FastAPI/Pydantic com ASGI em memória; autorização real do ZIP com chamada CENTRAL simulada; writer/reader simulados; SQL histórico em DuckDB em memória com fixtures pequenas. Cobrem cadastro/correção/consulta, 401/403/409/422, casas decimais, todos os tipos de Januária, virada mês/ano, fallback/ausência, prioridade, notas com vários itens, zeros à esquerda, filtros sem mudar denominador, duplicação, atualização de custo sem cache e resumo/detalhes. Os 1.994 itens não Januária da referência foram comparados com o motor anterior e mantiveram o mesmo resultado sem manual.

Navegador com respostas simuladas: cadastro mensal, histórico, próprio/provisório/pendente, correção/versionamento, falha incerta sem retry, rascunho por NF preservado entre abas, temas e mobile; regressão de lote de 100 NFs, falhas 401/403/409/422/503 e das páginas Faturamento/FOB. Nenhum teste permanente foi criado no projeto.

Ainda homologar: SQL/privilégios reais, conexão writer, sessão CENTRAL e permissão concedida/revogada, transações concorrentes reais, comportamento/precisão e desempenho PostgreSQL da consulta histórica, custo de outubro informado pelo usuário e rota mensal pública. A rota mensal está dentro do namespace de fretes existente; não se propõe mudança na CENTRAL/Worker. Se o Worker permitir somente caminhos exatos, seu encaminhamento atual precisará ser conferido antes da instalação. Nenhuma configuração foi alterada para presumir essa disponibilidade.
