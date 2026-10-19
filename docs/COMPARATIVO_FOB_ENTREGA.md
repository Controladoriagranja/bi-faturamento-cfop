# Comparativo PM FOB — entrega integrada

## Frontend oficial

A implementação usa dois HTMLs independentes neste mesmo projeto: `index.html` contém exclusivamente Faturamento por Vendedor Pai e `comparativo-fob.html` contém o Comparativo PM FOB. Ambos funcionam por acesso direto. Como no Bi-Matrizes, `data-page` identifica a página e um menu compartilhado usa links para os arquivos, com indicação da página ativa. O endereço antigo `index.html#comparativo-fob` redireciona para `comparativo-fob.html`.

Cada relatório preserva separadamente suas datas e multisseleções no `sessionStorage` da aba, ao navegar, recarregar ou usar voltar/avançar. Também distingue o formulário editado da última consulta concluída: ao retornar, restaura os filtros editados, mas mantém o detalhamento associado à consulta efetivamente exibida até clicar em Consultar. O FOB preserva a preferência por matriz/composição e a exibição da referência Excel. A preferência de tema continua compartilhada no `localStorage`, como antes. Nenhum resultado financeiro ou credencial é gravado pelo componente de estado.

Inclui período, múltiplas unidades/famílias/canais, totalizadores por canal, matriz Família × Canal Venda, composição ponderada de despesas, totais e referência Excel opcional com diferenças. Células, famílias e cartões abrem os itens do filtro efetivamente consultado. Os itens têm paginação, ordenação por coluna, busca, filtro de pendências, CSV completo e expansão “Ver cálculo”, com origem, fórmula, precisão integral e diferenças de entrada. As despesas não são recalculadas pelo JavaScript.

Os dados de teste e a planilha não estão nos assets públicos. Sem a extensão instalada ou a rota encaminhada no Worker, a tela informa que a API está indisponível. Ela não substitui dados reais por exemplos.

| Arquivo do frontend | Ação |
|---|---|
| `index.html` | Exclusivamente o relatório inicial, sem seção, script ou CSS do comparativo |
| `comparativo-fob.html` | Página própria com toda a apresentação do FOB transferida, sem duplicação do relatório inicial |
| `assets/js/config.js` | Acrescenta três endpoints FOB; mantém os anteriores |
| `assets/js/api.js` | Acrescenta mensagem de 404 específica do FOB |
| `assets/js/navigation.js` | Menu compartilhado, página ativa e compatibilidade com o endereço antigo |
| `assets/css/navigation.css` | Estilos compartilhados do menu e comportamento mobile, extraídos de `fob.css` |
| `assets/js/report-state.js` | Persistência compartilhada dos filtros, com chaves separadas por relatório |
| `assets/js/dashboard.js` | Preservação e restauração dos filtros do relatório inicial, sem alterar cálculos ou endpoints |
| `assets/js/fob.js` | Inicialização independente e restauração de filtros/preferências; matriz, despesas, itens, auditoria e CSV reaproveitados |
| `assets/css/fob.css` | Estilos exclusivos do comparativo, responsividade e tema escuro reaproveitados |

O componente de filtros, cliente HTTP, tema, tipografia Geist e estilos atuais são compartilhados entre as páginas. Cada HTML carrega somente o script do seu relatório; os componentes de detalhamento também permanecem separados. Nenhum motor, regra comercial, valor de referência, endpoint ou arquivo de backend foi modificado na separação dos HTMLs. O ZIP do Anderson permanece exatamente igual.

## ZIP para o Anderson

Arquivo: `artifacts/api_anderson_comparativo_fob.zip`. Seus caminhos são relativos à raiz da API que contém `servico_zootecnico.py`, e não à raiz deste frontend.

Conteúdo necessário:

- `modules/comparativo_fob/{__init__,config,routes,service,aggregation}.py`: extensão, consulta limitada, consolidação e rotas.
- `modules/comparativo_fob/data/referencia_excel.json`: catálogo inicial privado, incluindo perímetro por item, valores de referência, fórmulas e auxiliares extraídos do Excel.
- `fob/{__init__,calculator,reference,repository,snapshot,workbook}.py`: biblioteca reutilizável do cálculo e leitura do catálogo.
- `integrar_comparativo_fob.py`: integrador pontual, com diff antes da aplicação, backup e execução idempotente.
- `MANIFESTO.json`, `INTEGRACAO-ANDERSON.patch` e `LEIA-ME-INTEGRACAO.txt`: hashes, arquivos novos, alterações compartilhadas e instruções.

A API fornecida em `api_zootecnico.zip` é anterior à descoberta por `core/bootstrap.py`. A atualização `backend_atualizacao_gpd_por_fase.zip` contém apenas `bi_generic/registry.py`, `router.py` e `gpd_fases.py`. Esses três arquivos permanecem preservados: o módulo FOB usa um prefixo independente, sem interferir no roteador genérico. O contrato também suporta a versão modular já identificada em `api-db`, sem tornar essa versão uma dependência de instalação.

**Arquivos compartilhados que mudam na API fornecida:** `servico_zootecnico.py`, para acrescentar quatro linhas de importação/registro das novas rotas; e `Dockerfile.zootecnico`, para acrescentar dois COPY. O ZIP não inclui cópias completas desses arquivos para sobrescrever atualizações. O integrador preserva os bytes existentes, mostra o diff e cria os backups antes de acrescentar os trechos. Se detectar a API modular, preserva o serviço principal e acrescenta somente os COPY ainda ausentes. Não modifica `core/`, `config.py`, registro de outros BIs, requisitos ou credenciais.

Passos no Anderson:

1. Copiar o conteúdo do ZIP para a raiz da API, mesclando as pastas sem remover módulos existentes.
2. Nessa raiz, rodar `python integrar_comparativo_fob.py` para conferir o diff.
3. Rodar `python integrar_comparativo_fob.py --aplicar` para acrescentar os trechos e criar os backups `*.antes_comparativo_fob.bak`.
4. Reconstruir a imagem e recriar o container pelo procedimento habitual.
5. Conferir o encaminhamento e a permissão no Worker para os três GET `/api/comercial/comparativo-fob/filtros`, `/resumo` e `/detalhes`. O código do Worker não foi fornecido; nenhuma configuração ou publicação foi feita nele. A autenticação continua a mesma: Bearer do Portal para o Worker e autenticação interna existente para a API.

Nenhum SQL de criação ou alteração é necessário. As fontes continuam sendo `comercial.vw_faturamento_cfop_filtrado` e `comercial.faturamento_cfop`, com leitura pelo `banco()` existente. A consulta tem período restrito, limite de 5.000 linhas (exceder gera erro, sem truncar totais) e cache de 45 segundos. A consulta pontual da NF tem limite de 100 itens. Não há extratores, cargas ou gravações no módulo.

## Resultado e limites dos dados

O catálogo inicial está **restrito a 01–04/10/2026**. Outros períodos são recusados até validar os cadastros e o perímetro; o Excel recebido não comprova regras para meses futuros. As diferenças de CFOP 5151-06 seguem a associação dos itens comprovados, sem criar exclusão universal do CFOP.

O arquivo Excel disponível mudou de hash durante o trabalho. O catálogo final usa a versão atual, identificada no manifesto do ZIP. A comparação de suas 2.340 linhas com os artefatos originais não encontrou diferenças nos pesos, canais, FOB salvo, custos ou fórmulas presentes; tabelas auxiliares e chaves também são iguais. A conferência está em `artifacts/fob/validacao_catalogo.json`; os artefatos antigos conservam o hash original.

| Canal | Peso do recorte conciliado com o Excel | FOB da reprodução das fórmulas | Estado operacional observado no CSV fornecido |
|---|---:|---:|---|
| Varejo | 203.818 kg | R$ 1.949.811,06 | 335 itens pendentes; FOB total e PM permanecem abertos |
| Atacado | 931.381 kg | R$ 7.900.355,54 | Calculado com os cadastros iniciais do Excel |
| Subprodutos | 510.740 kg | R$ 383.055,00 | Calculado com os cadastros iniciais do Excel |

Esses resultados vêm da conciliação offline anterior e da conferência do catálogo; não são uma homologação do banco atual. A reprodução usa os valores de frete externos salvos no Excel apenas para comparação. O resultado operacional não usa esses valores para resolver pendências. Não foi acrescentado ajuste para fazer os totais coincidirem.

Pendências identificadas:

- **Fretes:** 330 itens de Januária e 5 itens de tipo 1 com frete de origem zero/nulo, totalizando 28.185 kg. O parcial concluído de Varejo é R$ 1.693.957,947978…; ele não substitui o FOB total. Tipos sem dedução de frete pelo Excel preservam o zero, inclusive os 16 itens de tipo 5 de Januária.
- **NF 806684 / unidade 111 / cliente 9880:** 40 kg, incluídos no Varejo conforme FaturamentoANeRA!422. Ausente no CSV da view. Falta configuração local de acesso ao banco, portanto o SELECT bruto ainda não foi executado e a nota não pode ser declarada inexistente. A API tentará conciliá-la na tabela bruta antes de usar somente essa referência provisória autorizada. Consulta indisponível, ausência ou identificação divergente são distinguidas. Outros itens ausentes não recebem fallback inventado.
- **Diferenças de origem:** 333 itens com diferenças entre CSV e Excel, principalmente frete. A auditoria expõe os dois valores. A origem provisória é indicada separadamente.
- **Cadastros:** comissão AK é referência congelada do Excel, com cadeia de fórmulas mapeada em `docs/FOB.md`. Não há CRUD, folha recalculada, histórico avançado nem persistência de preenchimento manual nesta entrega. O contrato `Catalog` e `ManualFreight` permitem futura origem PostgreSQL sem mudar as fórmulas.

Preço praticado, frete, comissão, adicional de comissão, contrato, administração RN, logística reversa, pallet, descarga, preço FOB e valor FOB são separados. Componentes não aplicáveis têm zero e origem explícita; componentes pendentes têm `null`. A precisão do cálculo é Decimal de 38 dígitos, sem arredondamento intermediário. JSON/CSV preservam decimais como texto; a tela formata os valores para leitura.

## Verificações e homologação

Foram executados somente testes locais rápidos de funções puras e do conteúdo do ZIP, análise de sintaxe e teste do frontend com servidor de arquivos estáticos e respostas sintéticas interceptadas. **A API não foi iniciada nesta máquina e o banco não foi acessado ou alterado nesta etapa.**

```powershell
python -m unittest discover -s tests -p 'test_fob*.py' -v
node tests/fob-browser.cjs
```

O teste de navegador requer Playwright e Chrome; aceita os caminhos por `PLAYWRIGHT_MODULE` e `CHROME_EXECUTABLE`. Verifica os dois HTMLs independentes, acesso direto, redirecionamento do hash antigo, menu/página ativa, preservação dos filtros consultados e editados por relatório, recarga/histórico e tema compartilhado. Também verifica matriz/custos, referência, itens, paginação/ordenação, auditoria, CSV, vazio, celular/escuro, Escape, erros 503/404 e cancelamento. A verificação da reorganização levou cerca de seis segundos, usando somente frontend estático e respostas interceptadas, sem executar API ou banco. Screenshots em `artifacts/fob/tela/` contêm somente a fixture sintética, não resultados reais.

Após instalar, validar a sessão real do Portal/Worker, as permissões SELECT, o resultado da consulta da NF, os pesos e os componentes de alguns itens nas três unidades/abas do Excel. Confirmar que as rotas e o relatório de faturamento anteriores continuam funcionando. A homologação com banco/API de produção e o fechamento dos fretes permanecem pendentes.

Para regenerar o pacote, sem iniciar API nem consultar banco:

```powershell
python backend/empacotar_comparativo_fob.py --excel 'CAMINHO/AnalisePreco01a04.xlsx' --api-referencia 'CAMINHO/api_zootecnico.zip'
```
