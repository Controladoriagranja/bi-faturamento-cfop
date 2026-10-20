# Comparativo PM FOB — entrega integrada

## Atualização: consulta desde janeiro

O intervalo aceito agora é 01/01/2026 até a data atual. Consultas totalmente dentro de 01–04/10 mantêm o motor e o perímetro conferidos no Excel. Os demais intervalos (inclusive mistos) usam `historical.py`: SELECT agregado por família/canal e SELECT paginado de até 500 itens, sem carregar o ano em memória e sem o limite de 5.000 itens da referência. Não foram executadas consultas reais nesta máquina; desempenho e disponibilidade histórica precisam ser conferidos no ambiente do Anderson.

O histórico usa os registros existentes da view, preço praticado e peso do banco. Não aplica whitelist, despesas ou referências financeiras de outubro, nem a nota provisória. O canal vem do cadastro atual `comercial.vendedor_grupo.canal_venda`, com agrupamento da família SUBPRODUTOS; canais adicionais permanecem visíveis. Sem vigência histórica desse cadastro, a classificação de janeiro ainda precisa de validação. Despesas e FOB ficam nulos/pendentes, sem parcial fictício ou referência Excel. Pesos/preços ausentes são sinalizados. O detalhe mostra os dados originais, inclusive frete, e o motivo da pendência.

Os filtros iniciais de famílias/unidades ainda usam as opções do catálogo; Todos inclui também as opções adicionais existentes na view. O pacote do Anderson foi atualizado na mesma pasta `bi_generic/comparativo_fob/`, com novo `historical.py` e ajuste de `service.py`. Atualize todos os arquivos desse módulo; o registro compartilhado continua igual, sem duplicá-lo. Nenhum SQL DDL, job, API de outro BI ou motor de outubro foi alterado. Levantamento das fontes em [FOB_ORIGENS_E_CADASTROS.md](FOB_ORIGENS_E_CADASTROS.md).

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

O componente de filtros, cliente HTTP, tema, tipografia Geist e estilos atuais são compartilhados entre as páginas. Cada HTML carrega somente o script do seu relatório; os componentes de detalhamento também permanecem separados. Nenhum motor, regra comercial, valor de referência ou endpoint foi modificado na separação dos HTMLs. Em 20/10, o pacote do Anderson foi reorganizado no padrão do ZIP fornecido: uma única pasta nova dentro de `bi_generic`, sem integrador e sem Dockerfile.

### Cabeçalho, ordem e interpretação dos avisos

O cabeçalho da matriz tem prioridade sobre as células fixas de Família durante a rolagem vertical e horizontal. A célula Família cobre as duas linhas de cabeçalho e permanece alinhada, em ambos os temas e no celular. A apresentação segue as famílias de `FaturamentoANeRA!AK860:AK889`, com Peso → Faturamento FOB → PM FOB em cada canal, mantendo a coluna de pendências. Composição de custos, filtro de famílias e resumo CSV usam a mesma sequência. Famílias novas sem posição na referência vêm ao final, sem descartar registros.

Os avisos medem situações diferentes e podem se sobrepor:

- **Pendente:** falta um componente necessário. No CSV analisado havia 335 itens: 330 de Januária com frete manual ainda não confirmado e 5 com tipo de frete 1 sem valor na origem (2 na unidade 111 e 3 na 180), totalizando 28.185 kg. Isso impede fechar o Varejo; o parcial não é o total.
- **Diferença de entrada/origem:** os dados usados são comparados ao Excel, incluindo preço praticado, valor faturado e frete de origem; ausência ou origem provisória também pode gerar o aviso. No CSV anterior eram 333 diferenças, todas de `frete_kg`. Dessas, 328 já tinham FOB calculado, sem diferença absoluta de um centavo ou mais contra o Excel; 5 estavam pendentes. O frete aplicado pode vir de tabelas e fórmulas e não ser igual ao frete bruto. Portanto uma diferença de entrada não comprova erro no resultado FOB. A contagem de 334 no print atual depende da origem consultada agora e não identifica por si só qual item adicional mudou.

A tela inclui uma explicação expansível e destaca “Diferença de entrada” por item. Abra uma família/canal e “Ver cálculo” para conferir origem, referência e fórmula. Valide qual dado está correto antes de corrigir a fonte ou confirmar o frete. Não ajuste valores apenas para coincidir com o Excel. Os valores aprovados de frete manual de Januária ainda precisam ser conectados à API por item; não há campo de preenchimento nem persistência nessa tela. Alterar somente o frete bruto não confirma automaticamente o frete manual de Januária. Esta entrega visual não altera o backend nem o ZIP do Anderson.

## ZIP para o Anderson

Arquivo: `artifacts/api_anderson_comparativo_fob.zip`. Seus caminhos são relativos à raiz da API que contém `servico_zootecnico.py`, e não à raiz deste frontend.

Conteúdo necessário:

- `bi_generic/comparativo_fob/`: **única pasta nova**, reunindo rotas, serviço, agregações, configuração e motor já validado, com imports relativos entre seus arquivos.
- `bi_generic/comparativo_fob/referencia_excel.json`: catálogo inicial privado diretamente na mesma pasta, sem subpasta adicional. Inclui perímetro, referências, fórmulas e auxiliares do Excel.
- `servico_zootecnico.py`: arquivo completo da API fornecida, com o registro FOB já aplicado.
- `MANIFESTO.json` e `LEIA-ME-INTEGRACAO.txt`: documentação dos arquivos, hashes e instruções. Não precisam ir para a imagem.

A base do arquivo completo é a cópia fornecida mais recente, `api_zootecnico(1).zip`, que já registra Suprimentos. A atualização `backend_atualizacao_gpd_por_fase.zip` contém apenas `bi_generic/registry.py`, `router.py` e `gpd_fases.py`. Esses três arquivos não estão no ZIP FOB e permanecem preservados na máquina. O módulo FOB usa um prefixo independente, sem interferir no roteador genérico.

**Único arquivo a substituir:** `servico_zootecnico.py`. O conteúdo de `api_zootecnico(1).zip` é preservado byte a byte, acrescentando ao final somente um comentário e duas linhas:

```python
from bi_generic.comparativo_fob.routes import criar_router_comparativo_fob
app.include_router(criar_router_comparativo_fob(banco))
```

O manifesto contém hashes de origem e entrega. Não há script de instalação, patch para aplicar, Dockerfile, arquivos de Suprimentos ou cópias de outros BIs no pacote. O catálogo do ZIP anterior é reutilizado byte a byte; calculator/reference/repository/snapshot/workbook também são preservados. Os demais ajustes são apenas imports relativos, localização do catálogo e factory de registro, sem mudança de fórmulas, cadastros ou valores de referência.

Passos no Anderson:

1. Na pasta `API/api_zootecnico`, onde já existem `servico_zootecnico.py` e `bi_generic/`, mesclar a pasta `bi_generic/` do ZIP com a existente. Isso adiciona somente `bi_generic/comparativo_fob/`. **Não remover nem substituir `bi_generic/` inteira.**
2. Substituir somente `servico_zootecnico.py` pelo arquivo do ZIP. O serviço já está integrado; não executar Python, integrador ou SQL.
3. Reconstruir o Docker como já faz. O `Dockerfile.zootecnico` fornecido já contém `COPY API/api_zootecnico/bi_generic ./bi_generic`, que inclui a nova pasta e seu JSON automaticamente. Nenhum Dockerfile é entregue ou alterado.

Este ZIP substitui a organização dos pacotes anteriores: não copiar `fob/` nem `modules/`. Não substituir `bi_generic/router.py`, `registry.py`, `gpd_fases.py` ou `faturamento_nf/`; os arquivos dessas áreas não estão neste pacote.

O código do Worker não foi fornecido nem alterado. O acesso público continua dependendo do encaminhamento e da permissão dos três GET `/api/comercial/comparativo-fob/filtros`, `/resumo` e `/detalhes`. A autenticação continua a mesma: Bearer do Portal para o Worker e autenticação interna existente para a API.

Nenhum SQL de criação ou alteração é necessário. As fontes são `comercial.vw_faturamento_cfop_filtrado`, `comercial.faturamento_cfop` e, no histórico, `comercial.vendedor_grupo`, com leitura pelo `banco()` existente. A consulta da referência tem limite de 5.000 linhas (exceder gera erro, sem truncar totais) e cache de 45 segundos; o histórico usa agregação e paginação SQL. A consulta pontual da NF tem limite de 100 itens. Não há extratores, cargas ou gravações no módulo.

## Resultado e limites dos dados

O catálogo inicial está **restrito a 01–04/10/2026**. Outros períodos são consultados no modo histórico descrito acima, com FOB pendente; o Excel recebido não comprova despesas/regras dos outros meses. As diferenças de CFOP 5151-06 no recorte conferido seguem a associação dos itens comprovados, sem criar exclusão universal do CFOP.

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
python backend/empacotar_comparativo_fob.py --api-referencia 'CAMINHO/api_zootecnico(1).zip'
```
