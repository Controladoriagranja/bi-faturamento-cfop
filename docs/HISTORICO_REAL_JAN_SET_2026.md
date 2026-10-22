# Histórico CFOP 2026: carga aplicada e detalhamento de frete

Data: 22/10/2026.

## Aplicado no banco e nos arquivos-mestre

Lote confirmado: `62f7ab1d-a274-46bc-90c7-9e6ce881cf55`.

- 37.575 cadastros provisórios de janeiro–setembro atualizados ou inativados.
- 5.965 cadastros históricos incluídos.
- 43.540 históricos de auditoria criados; total de 51.890 registros preservando versões anteriores.
- 8.350 cadastros de outubro preservados integralmente.
- Custo mensal de Januária preservado. Não foram criados custos mensais fictícios para janeiro–setembro.
- Arquivos-mestre Despesas.xlsx e Comissoes.xlsx conferidos contra o banco.
- Fretes.xlsx e suas abas não foram alterados por esta carga.
- Prévia posterior: zero inclusões, zero alterações e zero mudanças mensais.
- Nenhuma mudança de Docker, permissões, faturamento ou arquivos CFOP originais.

A API instalada confirmou em GET: modo planilhas_mestre, lote acima e janeiro com 27.279 itens e 714 pendências.

## Efeito sobre os itens pendentes

| Mês | Antes | Depois | Itens de frete iguais ao Fretes.xlsx |
|---|---:|---:|---:|
| Janeiro | 3.920 | 714 | 676 |
| Fevereiro | 3.899 | 454 | 448 |
| Março | 2.804 | 498 | 464 |
| Abril | 1.966 | 471 | 455 |
| Maio | 1.430 | 422 | 413 |
| Junho | 941 | 170 | 158 |
| Julho | 692 | 212 | 193 |
| Agosto | 230 | 231 | 110 |
| Setembro | 200 | 200 | 85 |

**Resultado: 16.082 para 3.372 itens pendentes; 12.710 resolvidos.**

As contagens de componentes podem coincidir no mesmo item. Permanecem frete ausente na origem, 202 itens sem comissão comprovada, três ocorrências de logística reversa e 13 itens com peso zero. Os 3.002 itens de preenchimento de frete de janeiro–setembro coincidem exatamente com os identificadores do Fretes.xlsx; comparação por empresa, unidade, série, NF, ano e chave do item.

## Critério histórico

Fechamento mensal usado como fonte principal. Os 43 arquivos semanais são cortes acumulados e não foram somados. Janeiro–julho usam percentuais históricos de comissão e adicional de Despesas. Agosto–setembro usam Comissão!AK salva, sem reconstruir fórmulas antigas. Administração de RN: maio 0,32 R$/kg, junho 0,37 R$/kg e julho–setembro 0,38 R$/kg.

Duplicidades conflitantes foram registradas na auditoria; a primeira ocorrência foi preservada quando corresponde à busca exata VLOOKUP do fechamento. Nenhum valor foi escolhido silenciosamente. Dados inexistentes nas fontes não foram inventados. A cópia de outubro que sobra ativa corresponde a 05–31/10; o fallback mensal de Januária continua explicitamente provisório para competências sem valor próprio.

## Ajuste solicitado na tela — implementado e testado no projeto

- Número permanece visível com um ! quando existem custos a preencher.
- Valor exibido é provisório: desconta apenas despesas conhecidas; o FOB definitivo continua indisponível até completar as informações.
- Tooltip informa o preenchimento de frete e a quantidade correspondente ao arquivo.
- Clique no valor com aviso de frete ou na coluna Fretes a preencher abre somente os itens de preenchimento, com os filtros efetivamente aplicados de período, unidade, família e canal.
- Comissão ausente, outros tipos de frete, Januária e fretes já preenchidos validamente ficam fora dessa lista.
- Identificadores de empresa, série e NF são preservados, inclusive zeros. A chave do item vai na exportação do recorte.
- O clique não modifica Fretes.xlsx. A lista corresponde à planilha já utilizada pela responsável.

Validação: três testes novos de regra/recorte; 12 testes de agregação/entrega; teste de navegador com aviso, clique, exclusão de pendência de comissão, paginação, filtros, exportação, celular e erros. Diferenças do projeto sem erros de whitespace.

## Publicação do ajuste visual

A carga histórica já está em produção. O ajuste de apresentação e o novo filtro estão no projeto local e no pacote anexo; ainda precisam ser publicados juntos no frontend e na API instalada. Não houve implantação ou operação de Docker. O pacote não inclui credenciais, autenticação, serviço principal ou configuração de contêiner. Conferir a versão atual do módulo antes de mesclar as quatro propostas da API.

## Recuperação

Backup dos mestres: `\\192.168.1.139\Controladoria\BI_Granja\Planilhas_Faturamento_Cfop\.backups\historico-real-20261022T184852Z`.

O banco mantém as versões anteriores no histórico. Qualquer reversão deve criar novas versões a partir do estado anterior conferido, preservando o lote e a trilha de auditoria. Não apagar o lote ou o histórico.

## Fontes

Pasta original: C:\Users\vchaves\Documents\cfop 2026. Pacotes 01 Jan.zip a 09 Set.zip; fechamentos AnalisePreco01a31.xlsx, 01a28.xlsx ou 01a30.xlsx conforme o mês. Abas Despesas, Comissão, FaturamentoANeRA, FaturamentoRN e FaturamentoJA/JAeMC, conforme existentes.

PostgreSQL: comercial.fob_cadastro, comercial.fob_cadastro_historico, comercial.fob_importacao, comercial.custo_mensal_januaria e comercial.vw_faturamento_cfop_filtrado.
