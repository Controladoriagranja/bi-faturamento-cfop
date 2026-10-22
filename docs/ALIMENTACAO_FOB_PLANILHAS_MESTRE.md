# Alimentação FOB por planilhas-mestre — atualização de 22/10/2026

## Integração final com a API oficial do Anderson — concluída localmente

Base exclusiva: `api_zootecnico(4).zip`, recebida do ambiente atual de 22/10/2026.
SHA-256: `599366c79d4af8f979f0fb6b194523a9f107dc74847048dfef64aefffdfa8999`.
A comparação confirmou o registro ativo em `bi_generic/comparativo_fob/` pela
factory já incluída em `servico_zootecnico.py`. Os pacotes `modules/comparativo_fob/`
e `fob/` permanecem como recebidos, sem novo registro ou remoção.

Entrega: `artifacts/api_zootecnico_ANDERSON_FOB_FINAL.zip`, API oficial completa,
SHA-256 `496b31fd3998bb025734c3dfb0b5a9041df21c30ff74ab32ee924cae2732058e`,
gerada por `backend/integrar_api_anderson_fob_final.py`. Todos os 103 arquivos
originais permanecem: **101 idênticos e dois com cinco linhas acrescentadas**.
Nenhum arquivo de outro BI, autenticação, conexão compartilhada, Dockerfile ou
requisitos foi modificado. Nenhuma dependência nova, SQL ou importação necessária.

Todos os caminhos abaixo são relativos à raiz `api_zootecnico/`:

* Novos: `bi_generic/comparativo_fob/master_data.py`, `master_repository.py`,
  `feeding.py` e `costs_views.py`.
* Substituir pelos arquivos mesclados: `bi_generic/comparativo_fob/service.py`
  (três linhas de delegação condicionada) e `routes.py` (duas linhas de registro).
* Instruções e prova no ZIP: `LEIA-ME_FOB_FINAL.md` e `MANIFESTO_FOB_FINAL.json`.

Verificações aprovadas: 12 ASGI da base, 42 da integrada e 23 com PostgreSQL real
pela factory oficial REPEATABLE READ READ ONLY. As 71 rotas originais continuam;
somente dois GETs novos, totalizando 73, sem duplicidades. Aplicações inicializadas
sem conexão externa no import; versões dos requisitos oficiais usadas nos testes.
Flag ausente/0 preserva os payloads anteriores de filtros, resumo, detalhes e mensal
no cenário controlado. Identidade CENTRAL foi simulada; Worker, Docker e autenticação
remotos ainda exigem conferência no ambiente instalado.

Com `FOB_MASTER_ENABLED=1`, o cálculo real confirmou 2.340 itens, pesos 203.818 /
931.381 / 510.740 kg e oito pendências: cinco manuais não preenchidas e três fretes
NULL na origem. Demais componentes completos no recorte de 01–04/10. Januária:
346 itens a 0,6127658079 R$/kg. NF 806684 conciliada na tabela bruta, sem registro
provisório. Subprodutos: FOB R$ 383.055,00. Varejo e Atacado seguem em aberto.
Painel confirmou lote existente, 4.175 cadastros, uma competência e cinco candidatos
em três NFs, sem ambiguidade de identificação. Nenhuma escrita foi executada.

Instalação futura: guardar backup, copiar quatro novos e substituir somente os dois
arquivos mesclados na pasta instalada; reconstruir pelo procedimento habitual com
`FOB_MASTER_ENABLED=0`. Após conferir a instalação, configurar `=1` de forma
controlada pelo mecanismo de ambiente/recriação já utilizado. Preservar as demais
variáveis; não copiar o `.env.local` do robô. Não repetir SQL 006 nem sincronização.
Não foi fornecido Compose; nenhum comando ou nome de serviço foi presumido.
Rollback: flag 0 retorna ao caminho anterior; se necessário, restaurar apenas os
dois arquivos originais do ZIP (4), mantendo dados e demais BIs. A flag não desfaz
o custo mensal compartilhado que já estava gravado antes desta entrega.

As seções históricas abaixo registram a preparação anterior. Onde mencionavam
aguardar os arquivos atuais do Anderson, a dependência foi resolvida pelo ZIP (4).
A preparação com `.proposta` não é mais o pacote para instalação.

## Escopo definitivo de frete — correção de 22/10/2026

O novo fluxo **não exige nem reproduz fórmulas de FreteANeRA, FOBxRefaturamento,
ControleFrete ou outras abas históricas**. O Excel continua como referência de
comparação/perímetro, sem determinar o frete operacional. A fonte financeira é
PostgreSQL, com cadastros alimentados pelas três planilhas-mestre permanentes.

* Frete original válido é aplicado diretamente, com origem e valor na auditoria.
  Não zerar o valor apenas por tipo de frete e não exigir fórmula de redespacho.
* Tipo 1 com zero/NULL permanece pendente para Fretes.xlsx. A funcionária preenche;
  o robô importa; o cadastro validado substitui o frete no escopo NF/item, sem soma.
* Se a origem integral da NF resolve a pendência, o valor original atual volta a
  ser utilizado; não bloquear por assinatura de um preenchimento antigo dispensado.
* Januária 102 mantém custo mensal para todos os tipos, sem somar frete original.
* Ausência de valor nos demais tipos, frete inválido, identificação ambígua,
  assinatura inconsistente de cadastro ainda aplicável e despesas ausentes mantêm
  pendências reais. Nada é convertido implicitamente em zero.

Removidos do novo motor: freight_guards, consulta a reference.freight() para impor
bloqueios, pendente_regra_frete, pendente_redespacho e zeros por tipo herdados das
fórmulas históricas. Comissão e despesas já importadas mantêm as regras de aplicação.
O caminho legado de rollback foi preservado, sem alteração do banco ou da importação.

Os três arquivos operacionais já estão na UNC. A validação real dessa pasta nesta
rodada retornou **4.175 cadastros e uma competência**. Python/dependências estão
disponíveis. Segundo confirmação do responsável, o SQL 006 já foi executado e as
quatro tabelas novas existem; `custo_mensal_januaria` já existia. **Não reaplicar
006 nem recriar tabelas.** Agora existência, colunas e permissões também foram
conferidas nesta sessão no PostgreSQL, exclusivamente em leitura.

TCP em 192.168.1.193:5432 confirmado acessível em 223 ms. Após preenchimento local
da senha pelo responsável, autenticação confirmada como `admin` no `bi_granja`.
Conferências e cálculos usaram `transaction_read_only=on` e timeout de consulta de
15 s. Depois de autorização explícita, a primeira importação foi gravada somente
nas cinco tabelas previstas. A conta é superusuária; nenhum privilégio foi alterado.
Para operação permanente, ainda definir uma conta técnica apropriada, sem bloquear
qualquer conta existente. Não executar --sincronizar sem autorização específica.
Nenhum Docker, deploy, commit ou push foi executado. As fórmulas, os relatórios e
o módulo do Anderson já preparados foram preservados.

Foi criado e verificado um backup do Fretes.xlsx, sem alterar seu conteúdo:
`.backups/Fretes.preparacao.20261022T121953924045Z.74dcc603429a.bak`, na própria UNC.
SHA-256 do original e do backup:
`74dcc603429a49ecdcdafbb191ea80762746b7ad466b8dd053a23ccf40980323`.
A leitura, backup e troca do arquivo na rede funcionaram nas duas atualizações
reais abaixo. Concorrência com Excel simultaneamente aberto na UNC ainda não foi
homologada; a rotina mantém as recusas por bloqueio/arquivo ~$ e hash alterado.

## Resultado real de 22/10/2026 — primeira importação concluída

| Verificação | Resultado |
|---|---|
| PostgreSQL | Login válido; banco bi_granja; leitura em faturamento, tabelas FOB e mensal; colunas esperadas presentes |
| Cadastro de canais da API | vendedor_grupo possui vendedor/canal_venda e permite SELECT |
| Pendências 01–04/10 | 5 itens, 3 NFs; nenhuma inconsistência de identificação |
| Pendências 01–22/10 | 146 itens, 65 NFs; nenhuma inconsistência ou duplicação |
| Unidades no arquivo final | 111: 83 itens; 180: 39; 10: 24; Januária 102 excluída |
| Preenchimentos | Aba preservada, ainda sem lançamentos; nenhum frete manual é proposto para importação |
| Demais abas/arquivos | Todas as entradas OOXML fora de Pendências preservadas; Despesas.xlsx e Comissoes.xlsx não alterados |
| Cadastros importados | 4.175 novos e 4.175 históricos, versão 1; conteúdo conferido com os arquivos aprovados |
| Januária | Outubro/2026 gravado: 0,6127658079 R$/kg, versão 1, ator técnico 900000000006 e histórico antes/depois |
| Fretes legados | frete_manual_nf existe, mas a consulta EXISTS não encontrou registros na data da conferência |
| Auditoria | FOB_ROBOT_ACTOR_ID=900000000006 configurado localmente; reserva técnica documentada abaixo |

Os 4.175 cadastros importados são: contrato 1.330, descarga 1.504, administração 4,
pallet 232, logística reversa 996, adicional de comissão 4, comissão 1, folha 95 e
gestores 9. A primeira importação acrescentou 4.175 versões de histórico, um lote
e a competência mensal com seu histórico. Não alterou faturamento nem frete_manual_nf.

Backups das atualizações reais, na pasta `.backups` da UNC:

* `Fretes.20261022T123133148058Z.74dcc603429a.bak`: antes da atualização 01–04/10.
* `Fretes.20261022T123255485522Z.b34618f4099c.bak`: antes da ampliação para 01–22/10.

SHA-256 do Fretes.xlsx final:
`a949f6b44edab0d9533e7fdcc09724ebe3d12eef2662bcde7ded1965c1afbde3`.
Plano e snapshot privado anterior, com cópias dos três arquivos:
`C:\Users\vchaves\AppData\Local\GranjaBrasilia\FOB\20261022T123312277297Z-50473403\plano-importacao.json`.
Esse plano não autoriza sincronização e não deve ser publicado: contém cadastros
restritos. Antes da primeira escrita, reconferir hashes/estado e obter autorização.

Auditoria, importação e verificação de idempotência concluídas. O módulo da API
foi executado localmente com os cadastros reais; a integração na versão atual do
Anderson foi concluída sobre o ZIP (4), conforme a entrega final acima.
Despesas de períodos sem cadastro e valores de frete realmente ausentes continuam
pendentes; os 146 itens são candidatos a frete manual em outubro, não a contagem
de componentes pendentes do FOB no recorte de quatro dias.

## Primeira importação — reserva técnica, autorização e execução

Em 22/10/2026, após solicitação explícita do responsável, foi proposto e configurado
localmente **900000000006**, finalidade **ROBO_FOB_PLANILHAS_MESTRE**. É identificador
técnico exclusivo deste processo na auditoria comercial, não identidade de
funcionário, usuário CENTRAL ou conta PostgreSQL; não concede acesso a sistemas.
Não foi encontrado identificador técnico prévio na configuração/documentação.

Conflitos verificados em leitura nos campos criado_por/atualizado_por das tabelas
reais custo_mensal_januaria e frete_manual_nf: nenhum uso do número proposto.
Os campos são textuais e a restrição real da mensal aceita inteiro positivo
escrito como texto; não possuem FK para usuários. Nenhuma consulta ao Neon/CENTRAL
foi feita e nenhum cadastro de funcionário foi reutilizado. A exclusividade desta
reserva vale para este processo; preservar o número para o robô nas próximas cargas.

`FOB_ROBOT_ACTOR_ID` e a DSN privada foram preparados no .env.local ignorado. Para
esta primeira importação foi usada a conexão `admin` já fornecida, sem criar
contas ou alterar privilégios. Não usar essa conta administrativa como decisão
automática para o agendamento permanente. Nenhuma ACL/permissão Windows foi alterada.

Nova prévia privada:
`C:\Users\vchaves\AppData\Local\GranjaBrasilia\FOB\20261022T124140468477Z-d1da823d\plano-importacao.json`.
SHA-256: `652f6d5c7f3776b4041126f71fd951fc9460730bb2032434ee59fe462e885791`.
Os três backups foram relidos e conferidos com as planilhas operacionais, e o
fingerprint do estado atual do banco confere com a prévia. A credencial preparada
para escrita teve autenticação e privilégios verificados em conexão somente leitura.

Todas as cinco tabelas de destino estavam vazias. Efeito autorizado e conferido:

| Tabela comercial | Efeito da primeira sincronização |
|---|---|
| fob_importacao | 1 lote VALIDADO; resumo atualizado ao final da mesma transação |
| fob_cadastro | 4.175 registros novos, versão 1 |
| fob_cadastro_historico | 4.175 registros de histórico |
| custo_mensal_januaria | 1 competência: 01/10/2026, 0,6127658079 R$/kg, versão 1, ator técnico acima |
| fob_januaria_historico | 1 registro antes/depois; estado anterior é ausência |

Nenhum cadastro anterior foi apagado; faturamento_cfop, views e frete_manual_nf
não receberam escrita. Fretes.xlsx não tem valores manuais preenchidos, portanto
nenhum frete manual foi incluído neste lote.

**O responsável autorizou explicitamente a importação e a verificação de idempotência.**
Lote confirmado: **dc32563f-f0b9-4148-9ae8-a9432b78aece**, status VALIDADO.
A execução foi condicionada aos hashes aprovados, backups conferidos, estado do
banco idêntico à prévia e tabelas ainda vazias, sob advisory lock e transação única.

A conferência leu todos os 4.175 cadastros e históricos e comparou cada conteúdo com
os arquivos aprovados, incluindo versões/lote. Mensal e histórico de Januária
conferidos, sem duplicidades. A segunda sincronização retornou `sem_alteracoes`,
com zero cadastros e competências alterados. As contagens permaneceram 1 lote,
4.175 cadastros, 4.175 históricos, 1 competência e 1 histórico mensal. Hashes de
conteúdo, timestamps/versões, lotes e históricos permaneceram idênticos.
Evidências privadas na pasta da prévia: `resultado-importacao.json`,
`verificacao-importacao.json` e `verificacao-idempotencia.json`.

## Validação real do módulo e preparação do Anderson

O módulo `artifacts/integracao_fob/bi_generic/comparativo_fob/` foi importado e
executado localmente contra o PostgreSQL real, com `FOB_MASTER_ENABLED=1` somente
no processo de validação. Nenhuma configuração da API instalada foi alterada.
Foram consultados resumo e detalhes de 01–04/10/2026; o cálculo identificou o lote
importado e os 2.340 itens, sem ausentes ou registros provisórios. A NF 806684 foi
conciliada na tabela bruta. Os 346 itens de Januária aplicaram 0,6127658079 R$/kg,
com peso e composição auditável dos detalhes conferidos e sem parâmetros salariais
na resposta pública.

| Canal | Peso real | Pendentes | Resultado FOB | Parcial dos itens concluídos |
|---|---:|---:|---|---:|
| Varejo | 203.818 kg | 7 | Em aberto | R$ 1.924.678,54 |
| Atacado | 931.381 kg | 1 | Em aberto | R$ 7.644.714,91 |
| Subprodutos | 510.740 kg | 0 | R$ 383.055,00 | R$ 383.055,00 |

Comissão, adicional, contrato, administração, logística reversa, pallet e descarga
não apresentaram componentes pendentes nesse recorte. Após a correção de escopo,
restaram **8 itens**: **5** com pendente_manual e **3** com pendente_frete_origem.
Os três têm frete_kg NULL: NF 657822/unidade 10/tipo 2 (35.000 kg),
NF 806684/unidade 111/tipo 9 (40 kg, consultada na tabela bruta) e
NF 806687/unidade 111/tipo 9 (20 kg). Não presumir zero para essas notas.
O bloqueio anterior de 1.839 itens por fórmulas históricas foi removido.
Parciais não equivalem ao FOB total e não permitem calcular a divergência final
frente às metas antigas. Dados iniciais mantêm a vigência comprovada;
o primeiro lote não estende automaticamente regras a janeiro ou outros meses.
Relatórios privados atuais: `validacao-api-frete-simplificado.json` e
`itens-pendentes-frete-simplificado.json` na mesma pasta da prévia. O relatório
anterior validacao-api-banco-real.json foi preservado como histórico da etapa
anterior; suas 1.844 pendências não descrevem mais a política atual.

O responsável confirmou que o PGUSER da API é `admin`; SELECT nas seis origens
necessárias e USAGE no esquema foram conferidos. Nenhum GRANT ou alteração de
contas foi necessário. Também confirmou alterações posteriores do Anderson em
routes.py/service.py, indisponíveis nesta rodada: **não substituir esses arquivos
por versões da base antiga**.

Preparação em `artifacts/api_anderson_fob_planilhas_mestre_preparacao.zip`:

SHA-256 do pacote conferido:
`c34783b39e15f8b6f04fd4703ca1f6c55558df828cd12af90ac83e7106afe80f`.
CRC, hashes, sintaxe e composição do módulo de 18 arquivos sobre a base de 21/10
foram conferidos em memória. O ZIP completo anterior permaneceu com o hash original.

* Quatro novos arquivos na base de referência, sob bi_generic/comparativo_fob/:
  master_data.py, master_repository.py, feeding.py e costs_views.py.
* routes.py.proposta e service.py.proposta para mesclar com os dois arquivos atuais;
  os nomes com sufixo impedem substituição direta dos arquivos .py instalados.
* Manifesto com hashes/base/ações, instruções de integração, validação e rollback.

O pacote é **preparação para mesclagem**, não uma atualização pronta para instalar
na versão alterada do Anderson. Não inclui serviço principal, core, autenticação,
Dockerfile, SQL, credenciais, planilhas ou parâmetros salariais. O SQL 006 não deve
ser reaplicado. A função `build_master_patch()` no empacotador reproduz a preparação.
Falta obter e comparar os dois arquivos atuais, consolidá-los e coordenar a única
atualização futura da API/frontend, preservando as pendências financeiras explícitas.
Agendamento segue desativado; nenhum Docker, deploy, commit ou push executado.

Os modelos locais em `outputs/fob-mestres-20261021/` continuam ignorados pelo Git:
contêm parâmetros de folha e NÃO devem ser publicados no GitHub Pages nem como
assets. O `.env.local` privado tem regra explícita no `.gitignore` e não está
versionado. Sua ACL permite a conta Windows `vchaves`, SYSTEM e a conta local do
ambiente Codex que criou o arquivo; herança desativada. O acesso de leitura/gravação
de `vchaves` foi confirmado sem alterar o conteúdo. Não enviar senha no chat.

## Entrega e ativação

| Parte | Arquivos |
|---|---|
| Modelos operacionais | `Fretes.xlsx`, `Despesas.xlsx`, `Comissoes.xlsx`, na UNC operacional; cópias iniciais privadas em `outputs/fob-mestres-20261021/` |
| Robô independente | `backend/alimentacao_fob/`: `__main__.py`, `planilhas.py`, `importador.py`, `configuracao.py`, `verificacao.py` |
| Configuração / dependências | `backend/alimentacao_fob/configuracao.env.example`, `backend/requirements-alimentacao-fob.txt` |
| Contrato e cálculos reutilizáveis | `backend/fob/master_data.py`, `master_repository.py` |
| Integração API | `backend/modules/comparativo_fob/feeding.py`, `costs_views.py`, três linhas adicionais em `service.py`, registro em `routes.py` |
| Preparação do módulo Anderson | `backend/empacotar_comparativo_fob.py`, função `module_files()`; módulo isolado em `artifacts/integracao_fob/bi_generic/comparativo_fob/` |
| Banco | `backend/sql/006_alimentacao_fob.sql` (já executado pelo responsável; não repetir) |
| Operação Windows | `backend/alimentacao_fob/agendamento-desativado.xml` (não registrado, desativado e sem gatilhos) |
| Painel somente consulta | `custos-pendencias.html`, `assets/js/custos-pendencias.js`, `assets/css/custos-pendencias.css` |
| Navegação / apresentação | `config.js`, `navigation.js`, rótulos condicionais em `fob.js`; duas proteções de desativação nos scripts dos editores legados |

`FOB_MASTER_ENABLED=0` é o padrão na API: mantém integralmente o caminho anterior.
Somente `=1` utiliza as novas tabelas no resumo e nos detalhes. Não existe fallback
silencioso do novo catálogo para despesas financeiras do snapshot antigo.
O snapshot permanece para perímetro/conciliação da referência e rollback.

`APP_CONFIG.legacyFreightEditor=true` mantém o editor anterior durante a transição.
Após homologar, `false` remove sua entrada do menu e redireciona o endereço direto
`frete-pendente.html` para o painel. Os handlers antigos não são inicializados nesse
modo. Não foram apagados HTMLs, tabelas, writers ou endpoints legados.

## Contrato dos três arquivos

Os mesmos três nomes permanecem na UNC configurada; nunca gerar arquivos mensais
ou semanais adicionais. Cabeçalhos ficam na linha 5, dados a partir da linha 6.
Não renomear colunas/abas. Identificadores devem ser células de TEXTO, especialmente
empresa, unidade, série, NF, cliente e produto. Datas são datas Excel; percentuais
são frações (3% = 0,03). Zero explícito e campo vazio têm significados diferentes.
Não há fórmulas nem links externos nos modelos operacionais.

### Fretes.xlsx

* `Pendências`: somente o robô atualiza. Consulta itens da view filtrada, tipo 1,
  zero/NULL, excluindo unidade 102. Consulta a tabela bruta separadamente para obter
  **todos** os itens e o peso integral de cada NF. Não consulta a view lenta de frete
  manual. Mostra produto, cliente, volumes, peso, identificação e inconsistências.
* `Preenchimentos`: somente a funcionária edita. Copiar os identificadores e a
  assinatura da aba automática. Para `escopo=NF`, deixar `chave_item` vazia e usar
  uma única linha por NF. Para `ITEM`, copiar também `chave_item`.
* `modalidade=TOTAL`: `valor` é R$, dividido pelo peso integral da NF ou peso do
  item, conforme o escopo. `KG`: `valor` já é R$/kg. Valor deve ser positivo.
* NF substitui o frete de seus itens; ITEM substitui somente o respectivo item.
  Nunca somar frete original, manual e redespacho. NF e ITEM simultâneos são erro.
* Chave da NF: empresa exata + unidade/série/NF com BTRIM + ano da emissão. Nenhuma
  conversão numérica desses identificadores. A identidade do item acrescenta data,
  produto, cliente, CFOP, pedido, OC e UM; não usa ID da carga nem peso na chave.
* Duas linhas indistinguíveis por essa identificação são ambíguas: não se escolhe
  uma delas. Peso não positivo, datas/clientes divergentes ou NF ausente também
  impedem aplicação. A assinatura inclui composição, pesos e fretes originais;
  alteração posterior exige revisão. Variação apenas de escala decimal não muda
  a assinatura.
* Para NF mista, o preenchimento substitui TODO o frete, com denominador integral,
  nunca o peso da página, família ou canal. Sem pendência elegível na NF, o cadastro
  não passa a sobrepor automaticamente um frete resolvido na origem.
* Linhas sem `valor` não são importadas e não apagam valores já validados. A aba de
  preenchimentos é preservada byte a byte durante a atualização automática.

### Despesas.xlsx

`Cadastros`: 4.066 linhas iniciais herdadas dos cadastros comprovados, incluindo
replicação explícita por unidade onde o Excel usava o mesmo lookup. Não são linhas
de faturamento importadas. `valor / divisor` permite manter, por exemplo, o preço
do pallet e o divisor 1.000 separados, sem copiar um resultado semanal pronto.

`Custo Mensal Januária`: única fonte operacional do frete fixo da unidade 102.
Competência é dia 01 do mês de emissão. Todos os tipos de frete utilizam o valor
do mês; sem mês próprio, outubro/2026 provisório; sem outubro, pendência. O modelo
traz **0,6127658079 R$/kg em outubro/2026**, confirmado pelo usuário. Não é um literal
de fallback no motor: depende do cadastro importado. Zero mensal explícito é válido.

O robô reutiliza `comercial.custo_mensal_januaria`; não cria uma mensal concorrente.
Guarda antes/depois e lote em `fob_januaria_historico`. A tabela legada exige um
identificador numérico de auditoria: `FOB_ROBOT_ACTOR_ID` deve ser reservado pelo
administrador para o robô. Não usar nome de funcionário, token ou credencial CENTRAL
como se a execução tivesse sido feita por essa pessoa.

### Comissoes.xlsx

95 vendedores, 9 gestores e 5 regras de percentuais/adicionais iniciais.
As abas restritas preservam somente entradas necessárias à fórmula, sem nomes
individuais no painel. Restringir o compartilhamento desse arquivo na rede.

* `Vendedores`: salário/prêmio, percentuais, modo do adicional, DSR, base de encargos,
  calendário, encargos e códigos dos três superiores. Não contém AK pronto.
* `Gestores`: entradas e nível da equipe (1/2/3), comprovado na fórmula L/M de cada
  gestor. Gestor 103/104 usa Superior 1, 105 usa Superior 2 e 106–111 Superior 3.
* `Percentuais`: comissão geral de Januária, adicional com divisor 12 e os zeros
  literais do adicional das demais unidades, apenas na vigência conferida.
* Em `adicional_modo=UM_DOZE`, o backend deriva percentual/12. Em `DIGITADO`, usa o
  adicional explicitamente informado. Os campos DSR/base de encargos distinguem
  fórmulas efetivas de O/P/Q dos zeros literais das linhas de representantes.

O cálculo da folha lê faturamento e peso de todas as unidades AN/RA/RN da vigência
antes de família, canal, busca ou paginação. A base é `valor_produto` (AJ), não o
valor líquido de contrato. O período de folha é explícito no cadastro. Consultar um
dia não transforma o custo mensal/da vigência em custo daquele dia.

## Regras comprovadas no Excel

Arquivo inspecionado: `Downloads/AnalisePreco01a04.xlsx`. A leitura de origem para os
modelos foi restrita às abas Comissão/Despesas e às linhas necessárias dos cadastros.
A referência já existente foi reaproveitada para comparação dos 2.340 itens.

| Componente | Origem e cálculo |
|---|---|
| Base dos vendedores | Comissão L/M: SUMIF por vendedor sobre peso AE e valor_produto AJ de ANeRA e RN |
| Comissão | N = M × (J + K); adicional K digitado ou J/12, conforme a célula original |
| DSR | O = N / dias úteis × domingos/feriados; P equivalente sobre prêmio; ou zero literal por linha |
| Encargos | Q = H+I+N+O+P, ou zero literal; R:AB = Q × cada percentual de R3:AB3, incluindo FAP negativo |
| Comissão/kg | AC=N+O; AD=H+I+P+SUM(R:AB); AE=AC/L; AF=(AD/dias_mês×dias_período)/L; AG=AE+AF |
| Gestores | AE do gestor=AC+AD; AH/AI/AJ rateiam por participação do faturamento no superior correspondente, calendário e peso; AK=AG+AH+AI+AJ |
| Contrato | Despesas AE por cliente precede X por rede, inclusive cliente com zero explícito; percentual × valor_total_faturado / peso |
| Pallet | Cliente em AG:AH; AI3 / 1.000 |
| Logística reversa | AS:AX ou AZ:BE, por unidade/produto/UF, R$/kg; ausência permanece pendente |
| Descarga | BG:BI por cliente, R$/kg; IFERROR original zero somente na vigência comprovada |
| Administração RN | 0,25 + 0,07 + 0,06 R$/kg; cadastro inicial 0,38, somente na vigência comprovada |
| Januária comissão | N:P/Q de Despesas; P e P/12 sobre valor_total_faturado / peso |
| FOB | preço_praticado − soma dos componentes/kg; valor FOB = peso × FOB/kg, Decimal com precisão 38 |

Os defaults zero dos contratos, pallet e descarga foram herdados dos IFERROR/literais,
com vigência limitada a **01–04/10/2026**. Não viraram ausência=zero no catálogo novo.
No novo cadastro, sem regra vigente o componente fica pendente. Impostos AP:AQ e
classificações auxiliares que não entram na fórmula FOB não foram adicionados como
novas deduções. As anotações em contratos não foram reinterpretadas como percentuais.

Para correção, editar a regra vigente identificada por `registro`: gera nova versão.
Para outro período, adicionar outro `registro` com início/fim próprios, mantendo as
linhas anteriores. Usar `ativo=NAO` para revogar explicitamente; apagar linha do XLSX
não exclui automaticamente o histórico no banco. Não sobrepor regras da mesma chave.
Vínculos de gestor precisam apontar para o registro do gestor da vigência correta.

## Pendências e limites de homologação

1. Leituras reais concluídas, Fretes.xlsx atualizado com 146 itens/65 NFs de 01–22/10
   e primeira importação autorizada concluída, com idempotência real confirmada.
2. A consulta real não encontrou registros em frete_manual_nf nesta data. Se houver
   lançamentos posteriores no Portal antes da troca, conciliar e transportar para
   o mestre, validando contra as NFs integrais. Nenhum frete legado foi apagado.
3. Frete original válido é utilizado diretamente; não há pendência pela ausência
   de fórmulas históricas de transporte/refaturamento/redespacho. A funcionária
   alimenta os valores necessários nos mestres. Zero/NULL do tipo 1 exige manual;
   os três NULL de outros tipos no recorte seguem identificados, sem presumir zero.
4. A NF 806684/111/9880 e o CFOP 5151-06 mantêm o perímetro pontual do catálogo em
   01–04/10. A nota é buscada pontualmente na bruta e, se ausente, usa referência
   provisória explícita de 40 kg; sem empresa/identificação completa não se associa
   frete manual. Não se insere nota nem se altera view. O denominador da folha de
   referência mantém esse perímetro mesmo em consulta de período misto.
5. Fora da referência, o perímetro é o da view e o canal é o cadastro atual de
   `vendedor_grupo`, sem vigência histórica comprovada. Não prometer canal histórico
   validado. Não estender despesas de outubro para janeiro automaticamente.
6. Não estavam disponíveis amostras de março, junho e setembro. Os arquivos
   históricos de rede não foram alterados. A homologação desses meses permanece
   pendente; não foram somadas semanas sobrepostas/cumulativas.
7. Validar definição/plano real da view, índices, permissões, concorrência PostgreSQL
   e semântica de bloqueio/rename no SMB. A atualização não trunca o original:
   arquivo ~$ / aberto, hash diferente ou erro no replace cancelam a publicação.
   Bloqueio/replace foram testados localmente. Leitura, backup e replace na UNC
   funcionaram em 22/10; concorrência SMB com edição simultânea continua pendente.
8. O painel requer alcance Comercial geral autenticado. Não usa a operação de
   edição de frete. Acesso restrito por equipe é negado nesse painel até homologar
   o recorte, evitando vazar outras NFs. Os relatórios existentes mantêm seu acesso.

## Preparação operacional de 22/10 — sem conexão PostgreSQL nesta rodada

`configuracao.py` lê somente chaves conhecidas de `backend/alimentacao_fob/.env.local`.
Variáveis já definidas no ambiente têm precedência. Não executa shell, expande
variáveis ou imprime credenciais. O arquivo de exemplo foi atualizado para esse
mesmo contrato. O arquivo privado está sendo preenchido pelo responsável; não
sobrescrevê-lo.

Para leitura: PGHOST, PGPORT, PGDATABASE=bi_granja, PGUSER e PGPASSWORD; alternativamente
FOB_PG_READ_DSN com dbname explícito. Conexões de leitura têm timeout de conexão
de 5 s, statement_timeout de 15 s e default_transaction_read_only=on. Escrita exige
FOB_PG_WRITE_DSN separada e FOB_ROBOT_ACTOR_ID reservado; a configuração PG* de
leitura nunca é reutilizada implicitamente como conexão de escrita.

Foram acrescentadas duas operações que **não escrevem no PostgreSQL**:

* `--conferir-banco`: identidade, banco, modo somente leitura, colunas e privilégios
  reais por tabela/coluna. Os privilégios reportados pertencem à conta de leitura
  conectada; não comprovam os direitos de uma conta de escrita diferente.
* `--preparar-importacao`: valida o conjunto resultante e fretes contra NFs integrais,
  calcula novos/alterados/inalterados e alterações da mensal, aponta se existem
  fretes legados e salva snapshot anterior e cópias dos três arquivos em
  `%LOCALAPPDATA%\GranjaBrasilia\FOB\<execucao>`, fora do frontend. Opcionalmente,
  FOB_ESTADO_DIR define outro destino privado. O plano contém parâmetros de folha;
  não publicar seu JSON. A saída no console contém somente o resumo.

A prévia lista as cinco tabelas que poderão receber escrita: fob_importacao,
fob_cadastro, fob_cadastro_historico, fob_januaria_historico e custo_mensal_januaria.
Não altera faturamento_cfop, as views nem frete_manual_nf. O snapshot não é um
dump completo nem restaura automaticamente dados: preserva os cadastros e as
competências afetadas para restauração dirigida, mantendo o histórico do banco.
Antes da primeira escrita, reconferir hashes/estado do banco contra o plano,
privilégios da conta técnica, auditoria e fretes legados; apresentar resumo e obter
autorização explícita. Gerar a prévia **não autoriza** executar --sincronizar.

Toda publicação da aba Pendências agora cria um `.bak` exclusivo em `.backups`
da pasta operacional, confere seu SHA-256 e o CRC do XLSX e verifica preservação
byte a byte de todas as entradas do arquivo, exceto o XML da aba Pendências.
Se outra aba mudar, o backup falhar, o arquivo estiver aberto ou o hash mudar,
não substitui o original. Duas atualizações reais foram concluídas e conferidas
em 22/10; nenhuma outra aba foi alterada.

Usar a entrada Python existente; a política Windows desta máquina bloqueia scripts
PowerShell e não foi alterada. O agendamento preparado chama Python diretamente,
sem depender desses scripts. Os comandos abaixo já foram executados em 22/10
com a configuração privada;
servem também para a operação futura autorizada, sem repetir SQL 006:

```powershell
# A partir de backend/, sem banco:
py -B -m alimentacao_fob

# Somente após liberação das leituras pelo responsável:
py -B -m alimentacao_fob --conferir-banco
py -B -m alimentacao_fob --atualizar-pendencias --inicio 2026-10-01 --fim 2026-10-04
py -B -m alimentacao_fob --preparar-importacao
```

O XML de agendamento é só um modelo: Enabled=false, nenhum gatilho, sem credenciais
e ação inicial Validar. Nenhuma tarefa foi registrada. Após homologação manual,
definir conta Windows com acesso à UNC, diretório/Python, frequência e ações de
atualização/importação separadas; só então habilitar. O modo Sincronizar já exige
configuração de escrita e não foi acionado nesta rodada.

## Operação do robô — primeiro lote de produção concluído

Python e dependências já estão disponíveis nesta máquina. Em outra máquina de
execução, instalar `backend/requirements-alimentacao-fob.txt`. O robô não depende
de Portal, Render, Neon, Worker ou Docker do Anderson.
Configurar as variáveis do exemplo, com papéis técnicos próprios e acesso à UNC.
Executar com diretório de trabalho `backend/`:

```powershell
# Somente validar os três arquivos; não abre conexão com banco.
python -B -m alimentacao_fob

# Ler pendências do banco e atualizar somente a aba automática local/de rede.
python -B -m alimentacao_fob --atualizar-pendencias --inicio 2026-10-01 --fim 2026-10-04

# Importar cadastros, depois da autorização de implantação; não altera faturamento.
python -B -m alimentacao_fob --sincronizar
```

`--pasta` permite apontar para uma cópia local em homologação. A UNC padrão é
`\\192.168.1.139\Controladoria\BI_Granja\Planilhas_Faturamento_Cfop`.
Não há execução automática por importar módulos. O agendamento futuro no Windows
deve usar essa mesma entrada, `-B` e as variáveis da conta técnica, sem senha em
argumentos do Agendador nem DSN em logs. Não executar enquanto os arquivos são editados.
Não combinar atualização das pendências com importação em uma execução agendada:
separar os comandos torna explícito o resultado de cada operação.

O importador trava os três arquivos durante a leitura/importação e serializa lotes
com advisory lock PostgreSQL. Valida o conjunto resultante antes de gravar. Uma falha
desfaz o lote inteiro; rejeição é registrada separadamente e preserva o último válido.
Somente novos/alterados recebem UPSERT e versão/histórico; repetição idêntica não cria
cadastros/lotes válidos duplicados. Não usa DELETE+INSERT. Alterações salariais não
aparecem nas respostas do painel nem nos logs de execução.

## Banco e desempenho

006 já criou `fob_importacao`, `fob_cadastro`, `fob_cadastro_historico` e
`fob_januaria_historico`, conforme confirmação do responsável; não repetir. Regras usam
NUMERIC(38,20), valores mensais continuam NUMERIC(18,10). SQL inclui chaves, checks,
índices de vigência/dimensões e modelos de privilégios mínimos com nomes de papéis
para o DBA substituir. Não concede a PUBLIC nem reaproveita automaticamente writer
do Portal. Nunca aplicar novamente 005: a tabela mensal já existe.

Pendências: intervalo explícito de até 32 dias, limite de 30.000 itens, sem truncar;
NFs integrais em lotes de 150 chaves e limite de 20.000 itens por lote. API: até
100.000 itens e no máximo 63 dias para a base estendida da folha, bloqueando consulta
maior em vez de carregar o ano todo. Lookups de custos usam índices em memória por
dimensão. Resumo e detalhes são calculados pelo mesmo motor e conjunto filtrado.

O SQL contém sugestões comentadas de índices na tabela bruta por data e pela chave
textual da NF/ano. O DBA deve conferir índices equivalentes e EXPLAIN antes de criá-los
CONCURRENTLY, fora da transação. Não foi medido tempo real da base de 291 mil linhas.

A factory `banco()` da API fornecida já abre transação REPEATABLE READ READ ONLY.
A nova consulta reutiliza esse contrato para que regras, faturamento e mensal sejam
lidos no mesmo snapshot, sem modificar o arquivo central da API.

## Rotas da nova consulta

Somente GET, sob o namespace FOB já existente:

* `/api/comercial/comparativo-fob/custos/status`
* `/api/comercial/comparativo-fob/custos/pendencias?data_inicio=AAAA-MM-DD&data_fim=AAAA-MM-DD&pagina=1&por_pagina=50`

Reutilizam identidade CENTRAL via `comercial_acesso.authorize`; não há novo login,
token, permissão geral de edição ou endpoint de escrita para o navegador. O painel
consulta o resumo FOB existente para contar pendências de cada componente. Se a
alimentação nova estiver desativada, os novos GETs retornam 503 explicativo.
Conferir se o Worker encaminha esses GETs; seu código não foi alterado nem presumido.

## Roteiro único de implantação e rollback

1. Obter a versão **atual** do módulo no servidor do Anderson e comparar com a
   preparação local. Guardar backup de API/configuração/variáveis, dos três arquivos
   e do banco/cadastro mensal. Não usar o ZIP completo antigo como instalação.
2. Conferir as tabelas já criadas pelo 006, papéis e índices; não reaplicar DDL.
   Após liberação, testar leituras leves e preparar a primeira importação; somente
   após autorização específica, conferir lote, idempotência e histórico reais.
   Revisar identidade técnica da auditoria mensal.
3. Os três arquivos já estão na UNC e a validação passou; preservar os acessos
   existentes e não publicar folha/configuração privada no Git. Conciliar fretes
   legados e preencher apenas as pendências reais nos mestres; importar alterações
   futuras pela rotina validada, sem repetir o primeiro lote já concluído.
4. Mesclar SOMENTE `bi_generic/comparativo_fob/` da preparação com o módulo atual.
   Nenhuma substituição de `servico_zootecnico.py`, core, autenticação, Dockerfile ou
   outro BI é necessária se a factory FOB já está registrada, como na base fornecida.
   Não acrescentar um segundo include_router. Conferir os novos arquivos no manifesto.
5. Planejar uma única reconstrução futura do Docker, com a versão consolidada e a
   configuração de ambiente revisada. Ativar `FOB_MASTER_ENABLED=1` somente depois de
   dados/privilégios e cálculos homologados. Este documento não é autorização de deploy.
6. Conferir encaminhamento dos GETs no Worker e publicar o frontend em uma etapa
   coordenada. Só após aceite, definir `legacyFreightEditor=false` e passar a operação
   exclusivamente para as planilhas. Não publicar os XLSX de folha no frontend.
7. Conferir pesos, custos/kg, FOB por item/grupo e pendências com dados de produção
   restritos. Diferenças da nova regra fixa de Januária são legítimas e devem ser
   apresentadas, sem calibrar os parâmetros para bater metas.

Rollback preparado pelo caminho anterior preservado: parar o agendamento, desativar
`FOB_MASTER_ENABLED`, restaurar o módulo/configuração anterior e o menu legado. As
tabelas novas podem permanecer, sem leitura pelo caminho antigo. **Desativar a flag
não desfaz alterações da tabela mensal compartilhada**: restaurar apenas as
competências efetivamente alteradas usando backup e `fob_januaria_historico.antes`,
com DBA verificando `depois.versao` contra a versão atual para não desfazer edição
posterior. Para competências criadas no lote, o estado anterior é ausência; isso
exige restauração dirigida pelo DBA, sem limpeza indiscriminada. O último estado
válido dos cadastros está em `fob_cadastro_historico`, por registro/versão/lote.
Não apagar histórico nem usar um ZIP antigo completo para reverter outros BIs.

Conferência histórica da preparação, superada pela base oficial ZIP (4): o projeto vizinho
`api-db/api_zootecnico` utiliza registro modular por `core/bootstrap.py` e não
contém `bi_generic/comparativo_fob/` nem módulo FOB entre seus módulos locais.
Isso **não prova** que seja a versão atualmente instalada no Anderson. A preparação
de 18 arquivos mantém a factory FOB da API anteriormente fornecida; a versão
efetivamente instalada foi recebida no ZIP (4) e o diff foi fechado. Não substituir
core/bootstrap.py, servico_zootecnico.py ou registro central por essa base local.

Consulta de auditoria para preparar essa restauração, sem escrita:

```sql
SELECT h.lote, h.competencia, h.antes, h.depois,
       c.versao AS versao_atual, c.custo_kg AS custo_atual
FROM comercial.fob_januaria_historico h
LEFT JOIN comercial.custo_mensal_januaria c USING (competencia)
WHERE h.lote = 'SUBSTITUIR_PELO_UUID_DO_LOTE'::uuid
ORDER BY h.competencia;
```

## Validação local

Adicional offline em 22/10: oito verificações pequenas aprovadas, com dados locais e
conexões simuladas: carregamento privado/configuração e precedência do ambiente,
conexão somente leitura sem acesso de rede, bloqueio de DSN fora de bi_granja,
backup/preservação das demais abas, falha de replace preservando original/backup,
conferência SQL somente SELECT e prévia/snapshot com contagem de alterações.
Também conferida a classificação de falhas sem imprimir senha ou mensagem libpq.
Sintaxe Python e XML desativado conferidos. Em seguida foram feitas as leituras
PostgreSQL e as duas atualizações SMB descritas no resultado real acima; não foram
executadas importações ou testes de escrita PostgreSQL. Os testes anteriores
abaixo não foram repetidos em lote.

Testes e capturas foram criados em diretório temporário, fora da entrega. Foram
usados dados da referência e conexões simuladas, sem PostgreSQL real:

* 15 testes puros: modelos/leitura, chaves/zeros, NF integral, item, duplicidade,
  alteração da origem, Januária/fallback, vigência, zero explícito, preservação de
  Preenchimentos, bloqueio Windows, importação idempotente e rollback simulado.
* Comissão: 95 vendedores recalculados; demais despesas comparadas nos 2.340 itens,
  nenhuma divergência acima de 1e-9 R$/kg. Isso não valida fretes externos ausentes.
* Testes ASGI locais: resumo/detalhes, pesos por canal, filtragem sem alterar folha,
  somente GET, restrições do painel, modo anterior preservado, paginação, NF provisória
  e estabilidade da folha em período misto. Sete testes aprovados.
* Oito testes preexistentes do motor original aprovados, sem acesso ao banco.
* Navegador com API interceptada: somente GET, menu, filtros persistidos, situação,
  competências, tema claro/escuro e viewport mobile. Sem acesso a endpoints reais.
* SQL analisado por parser PostgreSQL, sem executar. XLSX sem links/fórmulas externas,
  com prévias visuais. Sintaxe de Python/JavaScript e integridade do módulo conferidas.
* Volume sintético: 12.000 cálculos por item, com os 4.175 cadastros indexados, em
  1,79 s neste ambiente. Não é uma medição da consulta PostgreSQL nem do servidor.

Referências de peso: Varejo 203.818 kg, Atacado 931.381 kg e Subprodutos 510.740 kg.
Metas Excel: R$ 1.949.811,06 / R$ 7.900.355,54 / R$ 383.055,00. Totais FOB com
fretes pendentes permanecem abertos; nenhum parâmetro foi forçado para fechá-los.

Histórico da simulação offline anterior à correção definitiva de escopo
(não utilizar seus bloqueios como regras da versão atual):

| Canal | Peso preservado | Meta Excel | Novo total FOB |
|---|---:|---:|---|
| Varejo | 203.818 kg | R$ 1.949.811,06 | Resultado anterior superado pela regra simplificada |
| Atacado | 931.381 kg | R$ 7.900.355,54 | Resultado anterior superado pela regra simplificada |
| Subprodutos | 510.740 kg | R$ 383.055,00 | R$ 383.055,00 |

Essa simulação não mede as pendências atuais do PostgreSQL nem substitui a
conciliação dos 335 itens antes exibidos no Portal. A regra definitiva foi revalidada
em leitura após a importação já concluída: 2.340 itens, oito pendentes (cinco manuais
e três fretes NULL na origem), sem reproduzir as fórmulas históricas de frete.
Doze verificações focadas passaram: fretes originais de todos os tipos, redespacho
sem bloqueio histórico, manual NF/item sem dupla aplicação, assinatura e ambiguidade,
zeros à esquerda, origem resolvida, Januária e cadastro ausente. A verificação do
banco confirmou os mesmos hashes de lote, cadastros, mensal e históricos, sem nova
importação, alteração de valores ou duplicidades.
