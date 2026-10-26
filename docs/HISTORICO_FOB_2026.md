> Atualização de 22/10/2026: a carga dos fechamentos reais de janeiro–setembro foi aplicada no lote `62f7ab1d-a274-46bc-90c7-9e6ce881cf55`. As réplicas abaixo registram a etapa anterior. Resultado e validações em [HISTORICO_REAL_JAN_SET_2026.md](HISTORICO_REAL_JAN_SET_2026.md). O ajuste de valores com ! e clique em itens do Fretes.xlsx está testado no projeto; publicação da interface/API ainda pendente.

# Histórico FOB de 2026 e chamada pelo atualizador

## Preparação de 22/10/2026

Os mesmos três arquivos de rede continuam sendo a entrada do robô. Não foram
alterados relatórios Excel históricos, tabelas de faturamento ou a API instalada.

Foram preparados e colocados nos mestres **41.750 cadastros provisórios novos**:
4.175 por mês de janeiro a setembro e 4.175 para 05–31/10. Os 4.175 originais de
01–04/10 permanecem idênticos. Total nos arquivos: 45.925. Os novos registros têm
IDs próprios e origem `REPLICA_OUTUBRO_2026`; seus parâmetros continuam editáveis
nas abas atuais. São copiadas dimensões, percentuais, encargos e valores de entrada,
nunca preço FOB ou resultados já calculados.

Calendário provisório confirmado pelo responsável: 26 dias úteis e cinco
domingos/feriados por competência. `dias_mes` respeita o mês civil e `dias_periodo`
o intervalo coberto. Folhas e gestores têm registros e vínculos separados por
competência. O intervalo de 01–04/10 mantém o cadastro original; 05–31/10 tem
parâmetros provisórios próprios. Não foi inventado calendário de feriados.

O custo mensal próprio de Januária de outubro permanece 0,6127658079 R$/kg.
Não foram criadas competências anteriores fictícias. O motor já usa outubro como
fallback provisório quando não há competência própria, com essa origem na auditoria.

Backups anteriores à expansão em `.backups` da pasta de rede. Plano financeiro e
cópias privadas em `%LOCALAPPDATA%\GranjaBrasilia\FOB`, fora do Git. A prévia final
foi gravada em `20261022T172846684417Z-71e8b80e/plano-importacao.json`:
41.750 inclusões, zero alterações de cadastros originais e zero alterações mensais.
Depois da prévia, o responsável autorizou explicitamente a escrita. Importação
concluída no lote `71635668-1c61-4af3-b587-207426dbbf9c`, com ator técnico
900000000006: 41.750 cadastros e 41.750 históricos novos. Total: 45.925 cadastros
distintos e 45.925 históricos distintos, todos na versão 1. Originais e mensal
comparados por hash com o estado anterior: idênticos. A prévia posterior de
idempotência encontrou zero inclusões, zero alterações e zero mudanças mensais,
sem executar outra sincronização. O lote original não foi repetido.

## Pendências reais recuperadas

Consultas realizadas mensalmente, de 01/01 até 22/10, somente leitura. A atualização
substitui apenas a janela consultada dentro de Pendências, preservando os demais
meses e todas as outras partes do XLSX, inclusive Preenchimentos. A chave inclui
empresa, unidade, série, NF, ano e item, preservando zeros. Preenchimentos já válidos
no PostgreSQL deixam de ser pendências; assinaturas/identificação inconsistentes
continuam em revisão. Reconsulta idêntica não deve alterar conteúdo ou timestamp.

| Mês de 2026 | Itens | NFs |
|---|---:|---:|
| Janeiro | 676 | 479 |
| Fevereiro | 448 | 379 |
| Março | 464 | 401 |
| Abril | 455 | 383 |
| Maio | 413 | 318 |
| Junho | 158 | 83 |
| Julho | 193 | 89 |
| Agosto | 110 | 46 |
| Setembro | 85 | 37 |
| Outubro até 22/10 | 153 | 68 |
| Total | 3.155 | 2.283 |

Nenhuma inconsistência de identificação encontrada nessa recuperação. Quantidades
podem mudar com novas cargas/preenchimentos; não são o total de componentes FOB
pendentes. Preenchimentos continuou sem lançamentos na conferência.

## Cálculo validado após importar os cadastros

| Período | Itens | Itens pendentes | FOB parcial dos itens completos |
|---|---:|---:|---:|
| Janeiro completo | 27.279 | 3.920 | R$ 71.136.910,72 |
| 01–22/10 | 19.695 | 233 | R$ 67.716.143,01 |

Os totais FOB permanecem em aberto. Janeiro: frete pendente em 714 itens, comissão
em 3.226 e outros componentes em um item. Outubro: frete em 163, comissão em 69 e
logística reversa em três. As contagens por componente podem coincidir no mesmo
item. Uma agregação mensal confirmou 3.225 itens de janeiro com 23 vendedores
ausentes do cadastro de folha de outubro. Réplica de outubro não inventa cadastros
para vendedores/dimensões ausentes; os casos restantes precisam de revisão nas
mesmas planilhas. Os cálculos foram executados no motor local com faturamento e
cadastros realmente importados, por READ ONLY. Reproduziram a prévia numérica.
Isso não comprova que a API instalada já esteja com o novo motor ativado.

O painel e o comparativo usam `ultima_importacao_valida.resumo.cobertura_provisoria`,
metadado acrescentado pelo importador ao lote existente. Assim, a API não precisa de
mudanças. O Portal avisa quando há parâmetros provisórios no período; a origem de
cada componente e o CSV dos itens identificam as réplicas efetivamente utilizadas.
O CSV do resumo sinaliza a presença de cadastros provisórios no período, sem
atribuir falsamente essa origem individual a todos os grupos.

A conferência real da API em 22/10 ainda retornou `modo=historico` para janeiro:
aplicar `FOB_MASTER_ENABLED=1` no ambiente do serviço e recriar o contêiner pela
rotina existente, sem rebuild da imagem. Nenhuma alteração de código ou Docker foi
executada nesta preparação. Uma sessão CENTRAL válida continua necessária para
homologar os GETs do painel pelo Portal.

## Execução diária independente

BAT: `backend/alimentacao_fob/atualizar_fob.bat`. Não cria nem modifica agendamento.
Não foi confirmada a instalação de `Atualizador_BI_Granja.bat`; nenhum script de
outro projeto foi alterado.

No futuro, colocar esta chamada imediatamente no ramo de sucesso da etapa de
faturamento do atualizador efetivamente utilizado:

```bat
if errorlevel 1 exit /b %errorlevel%
call "CAMINHO_REAL\backend\alimentacao_fob\atualizar_fob.bat" --faturamento-ok
if errorlevel 1 exit /b %errorlevel%
```

O argumento impede execução acidental sem a confirmação de sucesso do chamador.
O BAT usa `python` do ambiente ou o executável definido em `FOB_PYTHON`; reutilizar
o Python do atualizador, com as dependências já listadas em
`backend/requirements-alimentacao-fob.txt`. Manter juntos `backend/alimentacao_fob/`
e `backend/fob/`, respeitando a estrutura já existente, fora do Docker/Render/Neon.
Não copiar credenciais de uma máquina para outra dentro de pacotes públicos.

Configuração privada na máquina de execução: `alimentacao_fob/.env.local`, com as
conexões e o ator técnico já reservados, sem credenciais no BAT ou nos logs.
`FOB_JANELA_DIAS=14` é o padrão; permite 1–32 dias. A execução divide a janela nas
fronteiras mensais, atualiza pendências, faz prévia/backup e sincroniza somente
cadastros modificados. Exclusão de linha no Excel não apaga histórico do banco.
Não altera o banco de faturamento. Logs operacionais sem folha/salários em
`%LOCALAPPDATA%\GranjaBrasilia\FOB\logs`, ou sob `FOB_ESTADO_DIR` configurado.

Recuperação eventual, separada da rotina diária, a partir de `backend/`:

```bat
python -B -m alimentacao_fob --recuperar-pendencias --inicio 2026-01-01 --fim 2026-10-22
```

Esse comando não importa custos. Não adicioná-lo à execução diária. Não criar uma
segunda tarefa no Agendador. Não executar `--sincronizar` para repetir o lote
original; mudanças futuras devem sempre passar pela prévia correspondente.

## Verificações focadas

Todos os originais conferidos por comparação dos parâmetros e da origem; novos
IDs únicos e vigências validadas; vínculos mensais de gestores resolvidos. Uma
segunda preparação encontrou zero registros novos. Teste de acumulação confirmou
que janeiro/fevereiro preservam outubro, Preenchimentos não é serializada e uma
reconsulta idêntica não muda bytes. Sintaxe Python/JavaScript conferida. Não foram
repetidas baterias extensas, executados extratores, migrações, deploy ou Docker.

## Operação conferida em 26/10/2026

Esta seção substitui as instruções operacionais anteriores do BAT. O frontend e
as fórmulas financeiras não foram alterados nesta rodada.

**Instalação comprovada:** MDE-100154, usuário vchaves, nesta pasta do projeto.
Preparado `backend/.venv-fob` (Python 3.12.14, openpyxl 3.1.5, psycopg 3.3.6).
O ambiente é local e ignorado pelo Git. O BAT usa seu Python por caminho relativo;
`FOB_PYTHON` pode indicar outro executável por caminho absoluto. As credenciais
continuam somente em `backend/alimentacao_fob/.env.local`, ignorado pelo Git.
Nenhuma ACL ou permissão Windows foi alterada.

Conexão real autenticada ao bi_granja por SELECT, com transaction_read_only=on.
Lidos e validados os três Excel oficiais: 51.890 cadastros, dos quais 47.545 ativos,
e uma competência de Januária (outubro/2026). Prévia: zero novos, zero alterados,
51.890 inalterados e nenhuma mudança mensal. Continuam três lotes, 51.890 cadastros,
89.465 históricos de cadastro e um histórico mensal; nenhuma escrita PostgreSQL
foi executada nesta conferência. Nenhum frete mestre importado existia nessa leitura.

**Teste real A:** janela 20–26/10, 28 itens de nove NFs, sem revisão de identificação.
Pendências acumuladas: 3.155 → 3.086. Somente o XML da aba Pendências mudou; os
demais membros do XLSX, incluindo Preenchimentos, permaneceram idênticos. Datas
fora da janela preservadas e chaves sem duplicidades. Repetição sem alteração.
Backup antes da troca em `.backups/Fretes.20261026T113527635300Z.85c7003665ce.bak`,
na pasta oficial. Não foi criada uma NF fictícia para testar uma nova pendência.

**Teste B:** prévia somente leitura, backups dos três arquivos e estado do banco
conferidos. Plano privado em
`%LOCALAPPDATA%/GranjaBrasilia/FOB/20261026T113542819432Z-03ed05bd/plano-importacao.json`.
BAT `--validar` executado com sucesso, sem Python no PATH. Não houve nova escrita
financeira para simular uma importação; a importação efetiva anterior consta nos
três lotes existentes. A API real respondeu HTTP 401; consumo autenticado do
Portal e FOB_MASTER_ENABLED permanecem pendentes por decisão do usuário.
O fluxo corrigido também foi executado com os arquivos reais e qualquer conexão
de escrita explicitamente bloqueada: retornou `sem_alteracoes`, sem novo lote,
sem backup repetido e com contagens/versões do banco idênticas.

**Teste C e correções locais:** seis testes focados em cópias/conexões simuladas
aprovaram arquivo aberto/bloqueado, XLSX inválido, mudança após a prévia, ausência
de conexão de escrita quando nada mudou, importação antes da baixa de pendências
antigas e recuperação da baixa em execução posterior. Não houve testes salariais
em logs nem alteração financeira real nesses testes.
Uma execução real do CLI sobre cópias temporárias inválidas foi rejeitada antes
de acessar o banco e gerou `ok=false` no log. A validação agora informa o nome do
XLSX corrompido, em vez de mostrar somente o tipo genérico BadZipFile.

### Comandos do mesmo BAT

A partir da raiz do projeto, sem executar Python manualmente:

```bat
backend\alimentacao_fob\atualizar_fob.bat --validar
backend\alimentacao_fob\atualizar_fob.bat --sincronizar
```

`--sincronizar` deve ser usado somente para alterações autorizadas das planilhas.
Valida os três arquivos, compara com o banco, salva prévia e backups antes de
alterações, importa transacionalmente apenas as diferenças e registra histórico.
Sem alterações, não abre conexão de escrita nem cria novo lote/backup completo.
Depois confirma as pendências das NFs preenchidas, inclusive antigas, consultando
somente as datas correspondentes, agrupadas por mês. Não reprocessa o ano inteiro.
Se a baixa no Excel falhar após o commit, `banco_confirmado=true` e
`pendencias_falhas` distinguem o banco já atualizado da publicação ainda pendente.
A execução seguinte tenta a baixa mesmo sem nova mudança de cadastro.

Após sucesso do atualizador oficial de faturamento, a integração proposta é:

```bat
rem Inserir apenas no ramo de sucesso, adaptando o caminho à máquina real.
call "C:\Users\vchaves\Documents\GitHub\bi-faturamento-cfop\backend\alimentacao_fob\atualizar_fob.bat" --faturamento-ok
if errorlevel 1 exit /b %errorlevel%
```

Esse modo atualiza somente Pendências dos últimos 14 dias (FOB_JANELA_DIAS), sem
importar custos. `--rotina-diaria` continua disponível no módulo por compatibilidade:
sincroniza primeiro e atualiza a janela recente depois. Não depende da página
retirada Custos e Pendências. O Portal consulta a API; não abre os Excel da rede.

### Automação preparada, ainda não ativada

Nenhuma tarefa FOB foi encontrada no Agendador local. A tarefa existente `Teste`
executa o agente do Portal, não este robô, e foi preservada. Consulta às tarefas
do Anderson retornou acesso negado; C$ indisponível e WinRM sem resposta. Portanto,
não foi possível confirmar instalação, Python, conta ou chamada pós-faturamento
naquela máquina. Nenhum atualizador foi modificado.

`backend/alimentacao_fob/agendamento-desativado.xml` está preparado para UMA tarefa
`GranjaBrasilia-FOB-Mestres` neste MDE-100154, conta Windows vchaves, a cada 15 minutos
das 07h às 19h, com sessão Windows aberta, rede disponível e sem instâncias
sobrepostas. A ação é o BAT `--sincronizar`. O XML permanece `Enabled=false` e não
foi registrado. O computador precisa permanecer ligado/acordado; não há promessa
de execução no Anderson. Não registrar duas cópias do robô em máquinas diferentes.

Somente depois de autorizar a ativação local, estes comandos PowerShell registram
e habilitam a tarefa revisada (não contêm senha):

```powershell
$fobTaskName = 'GranjaBrasilia-FOB-Mestres'
if (Get-ScheduledTask -TaskName $fobTaskName -ErrorAction SilentlyContinue) {
    throw 'Já existe tarefa FOB: revisar antes de substituir.'
}
$fobXml = Get-Content '.\backend\alimentacao_fob\agendamento-desativado.xml' -Raw -Encoding UTF8
Register-ScheduledTask -TaskName $fobTaskName -Xml $fobXml -ErrorAction Stop
Enable-ScheduledTask -TaskName $fobTaskName -ErrorAction Stop
Get-ScheduledTaskInfo -TaskName $fobTaskName
```

Para instalação definitiva no Anderson, antes é necessário identificar a pasta e
o atualizador realmente utilizados, preparar o Python/dependências naquela máquina
e conferir acesso com a conta Windows de execução. Recriar seu ambiente virtual
com `backend/requirements-alimentacao-fob.txt`; não copiar o `.venv-fob` deste PC
nem publicar `.env.local`. Revisar os caminhos/conta do XML antes de habilitá-lo.

### Falhas e operação diária

A funcionária salva e fecha os arquivos. Edita Fretes/Preenchimentos, cadastros e
competências de Despesas, vendedores/gestores/percentuais de Comissoes, mantendo
chaves e vigências. Editar ou salvar o Excel sozinho não importa nada enquanto
o agendamento não estiver ativo. Depois de uma sincronização confirmada, o Portal
obtém os dados novos na próxima consulta autenticada, se o modo mestre estiver ativo.

Logs sem salários/DSN: `%LOCALAPPDATA%/GranjaBrasilia/FOB/logs/AAAA-MM-DD.jsonl`
(datas UTC), ou `FOB_ESTADO_DIR/logs`. `ok=false` indica falha; em falha após commit,
verificar também `banco_confirmado` e `pendencias_falhas` antes de repetir.
BAT retorna 64 para uso incorreto, 69 para Python/dependências ausentes e 1 para
falha operacional; 0 confirma a operação pedida. Falhas de Python anteriores à
execução do módulo aparecem na mensagem do BAT/resultado do Agendador.

Se Excel estiver aberto, não fechar à força: pedir que a funcionária salve/feche e
repetir o mesmo BAT, ou aguardar a próxima tentativa agendada. Corrigir arquivo
inválido na origem; não apagar cadastros no banco. Exclusão de linha ou valor de
frete deixado em branco não revoga cadastro importado. O último lote válido e os
históricos são preservados. Não repetir migrações, cargas anuais ou Docker.
