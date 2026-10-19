# Detalhamento ao clicar nas células

Implementação local de 19/10/2026. Cada célula, inclusive no Total, abre um painel sobre o relatório. Fechar ou pressionar Escape retorna à tabela na mesma posição. Os filtros são uma cópia da última consulta exibida, sem incorporar alterações ainda não consultadas no formulário.

O nome do grupo abre os itens; os indicadores abrem NFs, ordenadas por data ou pelo indicador correspondente. O painel permite alternar as duas visões, abrir os itens de uma NF, buscar, paginar, escolher colunas e exportar todas as páginas das colunas selecionadas em CSV UTF-8. Valores exportados preservam a representação recebida da API, com ponto decimal; códigos de texto são preservados no arquivo. O programa de planilha pode inferir tipos ao importar.

A busca por número da nota, série, cliente, razão social, nome fantasia, vendedor, produto ou CFOP seleciona **notas completas**, mantendo todos os itens das notas encontradas. Não filtra apenas os produtos correspondentes dentro da nota. A classificação é sempre a da view canônica usada no resumo, incluindo as regras efetivamente implantadas por unidade. Esta alteração não recria nem modifica views de produção.

## API

`GET /api/bi/faturamento-nf/detalhes` usa a mesma autenticação, serviço e conexão somente leitura do resumo.

| Parâmetro | Uso |
|---|---|
| `data_inicio`, `data_fim`, `unidade` repetida | Iguais ao resumo |
| `vendedor_pai` | Nome exato; ausente no Total |
| `visao` | `notas` ou `itens` |
| `indicador` | `vendedor_pai`, `qtde_nfs`, `qtde_produto_por_nf`, `peso_por_nf`, `ticket_medio_por_nf` |
| `pagina`, `por_pagina` | Página a partir de 1; padrão 50, máximo 500 registros |
| `busca` | Até 200 caracteres, busca literal sem diferenciação de maiúsculas |
| `chave_nf` | Array JSON de unidade, série e número, recebido da nota; combinado com os demais filtros |
| `ordenar_por`, `ordem` | Coluna da visão atual e `asc`/`desc`; ausentes restauram a ordem padrão |

A resposta contém `linhas`, `colunas`, `total_registros`, `pagina`, `por_pagina`, `visao`, `totais`, `vendedor_pai`, `periodo` e `unidades`. `totais` descreve todas as notas selecionadas, inclusive quando a página mostra itens.

O backend seleciona as NFs em `comercial.vw_nf_por_vendedor_pai` e associa os itens de `comercial.vw_faturamento_cfop_filtrado` por unidade + série + número, normalizando espaços como na view de notas. Não replica a classificação no JavaScript. Valores e filtros usam parâmetros SQL; as opções de ordenação são fixas. Notas divergentes impedem a consulta com 409, como no resumo.

## Correção do detalhamento do grupo e ordenação — 19/10/2026

A estrutura de produção foi conferida pelo usuário: `qtde_itens` e as demais colunas esperadas existem. O usuário relatou sucesso para uma NF e para 01–04/10, mas falha no grupo com períodos maiores. Isso sugere custo da consulta; o SQLSTATE/tempo do erro original não foi obtido para confirmar timeout.

A nova implementação materializa somente as notas selecionadas e calcula totais e página numa única instrução SQL, evitando executar duas vezes a agregação da view de NFs. Na ordem padrão dos itens, usa a soma acumulada de `qtde_itens` para selecionar primeiro as notas que contêm a página desejada, incluindo páginas que começam ou terminam no meio de uma nota. Somente essas notas entram no JOIN da página com a view de itens. O filtro de datas também é aplicado à fonte dos itens, preservando datas NULL dentro de notas válidas. Não há alteração das views nem aumento do timeout.

Todas as colunas das duas visões permitem crescente → decrescente → padrão. O servidor ordena os dados antes da paginação; a exportação segue a mesma ordem. A ordenação por uma coluna do item precisa considerar todos os itens filtrados, portanto utiliza o caminho global em lugar da seleção prévia das notas da página. Colunas vêm de uma lista permitida e são escapadas como identificadores; a direção aceita somente `asc`/`desc`.

O detalhe agora registra exceções PostgreSQL no log da API com SQLSTATE. Cancelamento pelo banco (57014) recebe HTTP 504 com mensagem específica. Outros erros continuam no tratamento existente. O limite de 15 segundos configurado na API permanece.

Validação adicional: 27 páginas sem repetição/perda de itens, uma instrução SQL por consulta, período amplo com dados sintéticos, ordenação de todas as 60 colunas de itens e 12 colunas de notas, ordem numérica, decimais exatos, data NULL, parâmetros inválidos, ciclo de ordenação no navegador e exportação ordenada. A sintaxe de 66 variantes foi conferida com o parser PostgreSQL (pglast). A suíte também passou na estrutura `bi_generic/faturamento_nf` com as dependências da API enviada. Isso não mede o plano nem o tempo do PostgreSQL real; a consulta ampla ainda precisa ser homologada após a troca.

## Publicação pendente

Atualizar `index.html`, `assets/js/config.js`, `assets/js/api.js`, `assets/js/dashboard.js`, `assets/js/details.js`, `assets/css/app.css` e o pacote completo `backend/modules/faturamento_nf` nos destinos existentes. O roteador compartilhado já expõe a operação `detalhes`. Conferir a permissão dessa rota no Worker e a leitura da view de itens pelo usuário técnico. Não é necessário executar os SQLs antigos para instalar esta funcionalidade.

Homologar com sessão real do Portal, comparando NFs, peso e faturamento dos detalhes com o resumo, inclusive unidades 180/102, Não classificado e Total. A exportação faz consultas paginadas; alterações da fonte durante o download podem mudar os registros. Mudanças na contagem interrompem a exportação. A API não oferece snapshot histórico entre requisições.

## Validação local

Instalar `backend/requirements-testes.txt`. A suíte precisa do backend de referência para `core.contracts`; por padrão usa a pasta vizinha `api-db/api_zootecnico`. A variável `BACKEND_REFERENCE` permite outro caminho.

```powershell
python tests/validar_detalhes.py
node tests/details-browser.cjs
```

O navegador requer Playwright e Chrome. `PYTHON_EXECUTABLE`, `PLAYWRIGHT_MODULE` e `CHROME_EXECUTABLE` permitem apontar os executáveis/pacotes locais.

As duas suítes passaram com dados sintéticos em DuckDB, sem PostgreSQL/Worker de produção. Foram conferidos: conciliação com o resumo, grupos/unidades, NFs com produtos repetidos, datas inclusivas, 60 colunas, busca por notas completas, paginação, parâmetros inválidos e bloqueio de divergência. No Chrome: cliques em todas as células, filtros da consulta exibida, expansão de NF, seleção de colunas, exportação de 624 itens em duas requisições, vazio, Total, tela pequena, tema escuro, Escape, erro 401 e cancelamento. Capturas ficam em `artifacts/details-desktop.png` e `artifacts/details-mobile-dark.png`.
