# Cópia mensal da análise comercial

Esta ação pertence ao robô existente em `backend/alimentacao_fob`. Não é um novo serviço da API, não exige Docker e não é executada pelas ações de sincronização das três planilhas-mestre.

## Executar

Na instalação que já contém o robô FOB:

```bat
backend\alimentacao_fob\atualizar_fob.bat --analise-comercial 2026-10
```

A competência é explícita. Novembro não usa outubro automaticamente. Não foi criado agendamento.

Origem exclusivamente de leitura:

```text
\\192.168.1.139\Controladoria\Paulo\FechamentoCusto\Fechamento\03.AnaliseComercial.xlsx
```

Destino:

```text
\\192.168.1.139\Controladoria\BI_Granja\Planilhas_BI\Faturamento-CFOP
```

Executar com a conta e sessão de rede já utilizadas pelos robôs que acessam esses compartilhamentos. Não há senha, alteração de ACL, troca de proprietário, mapeamento de unidade ou credencial nova no código. Esta sessão de desenvolvimento recebeu acesso negado na rede; a publicação nesses caminhos não foi executada aqui.

## Comportamento

- Lê o arquivo original sem abri-lo para escrita e sem impor bloqueio de acesso.
- Recusa origem em edição (arquivo temporário do Excel presente) ou alterada durante a leitura. A pessoa continua podendo editar; o robô é que desiste da execução.
- Confere a aba exata da competência, os rótulos de linhas e colunas e os valores numéricos salvos.
- Confere C109 contra C82:D108 e, quando reconhecida, a fórmula de C89 contra base−E76−E78.
- Não recalcula Excel, macros ou vínculos externos. Salvar e recalcular previamente no Excel continua necessário; modo de cálculo manual é recusado.
- Valida antes de escrever qualquer arquivo de destino.
- Mantém o arquivo anterior em `.analise-comercial/backups/<sha256>.xlsx`, um retrato de cada versão em `.analise-comercial/versoes/` e a prévia em `.analise-comercial/previas/AAAA-MM/<sha256>.json`, sempre no destino.
- Não modifica nem formata o XLSX: a cópia é byte a byte. Se a versão não mudou, a cópia não é substituída novamente.
- Nunca cria temporários, backups ou relatórios na pasta de origem. Destinos sobrepostos à origem são recusados.

## Saída e limites

A prévia identifica competência, aba, hash do arquivo, fórmulas/células e as parcelas: despesa administrativa, financeira, comercial total, comissão, comercial sem comissão e logística. Guarda também as parcelas da conta C89. São valores salvos pelo Excel, com a precisão original.

O estado é `PREVIA_NAO_IMPORTADA` e `banco_alterado=false`. Nenhuma conexão PostgreSQL é aberta nesta ação. Não altera faturamento, fretes, despesas/comissões operacionais já importadas, CPV ou API. Os JSONs devem permanecer fora de pastas publicadas do frontend.

Para aplicar ao Portal, ainda é necessário homologar o destino desses custos mensais no banco e o seu uso no resultado projetado. O Excel de faturamento analisado aponta para Ago26; copiar Out26 não muda silenciosamente essa regra. Não sobrecarregar tipos financeiros do cadastro FOB existente para guardar despesas administrativas sem definir o contrato de cálculo.

## Arquivos

- Novo: `backend/alimentacao_fob/analise_comercial.py`.
- Alterados: `backend/alimentacao_fob/__main__.py` e `backend/alimentacao_fob/atualizar_fob.bat`.
- Backup anterior: `artifacts/backup-robo-analise-comercial-20261118/`.

O ZIP de entrega contém apenas esses três arquivos e um manifesto/guia. Instalar sobre a cópia existente deste robô, mantendo as dependências e `.env.local` que já funcionam. Se os dois arquivos compartilhados foram modificados no computador de execução, mesclar a nova ação preservando as alterações locais.

Validação local em 18/11/2026 com a cópia de Downloads: Out26, idempotência, backup antes de substituição, cópia byte a byte, origem preservada, recusa de Nov26 ausente, competência inválida e destino na origem. A entrada CLI e o BAT foram exercitados; nenhuma escrita financeira foi executada.
