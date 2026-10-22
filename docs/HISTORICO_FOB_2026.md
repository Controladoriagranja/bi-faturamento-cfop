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
