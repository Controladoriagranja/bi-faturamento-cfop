# Comparativo PM FOB — primeira entrega

O motor independente em `backend/fob` foi integrado à tela oficial e a uma extensão separada para a API do Anderson. As APIs e o relatório de faturamento existentes são preservados. O cálculo usa somente a biblioteca padrão do Python 3.10+ e recebe dados/cadastros como parâmetros. Instalação, arquivos e validação da entrega visual: [COMPARATIVO_FOB_ENTREGA.md](COMPARATIVO_FOB_ENTREGA.md).

Referências inspecionadas: `AnalisePreco01a04.xlsx`, abas FaturamentoANeRA, FaturamentoRN, FaturamentoJA, Comissão (o nome da aba termina com espaço), Despesas, FOBxRefaturamento, ControleFrete e FreteANeRA. As fórmulas compartilhadas foram expandidas, inclusive referências horizontais nas colunas ocultas N:AB da Comissão. As abas ocultas FOBxRefaturamento e ControleFrete também foram lidas. O arquivo original não foi modificado nem recalculado.

## Fórmulas efetivamente reproduzidas

Os cálculos usam `Decimal` com precisão de 38 dígitos. Não há arredondamento intermediário para atingir metas; apenas a apresentação do total em centavos usa arredondamento. O resumo também preserva os valores completos e as diferenças contra o cache do Excel.

Entradas comuns: `AI = preco_praticado`, `AE = peso`, `AL = valor_total_faturado`. O motor parte de **AI**, não substitui o preço por `AL/AE`. Contrato e comissão de Januária usam **AL**, incluindo os tributos presentes nessa coluna. `desc_finan` é exposto como entrada, mas não foi acrescentado como dedução independente: não faz parte das fórmulas FOB dessas três abas.

| Origem | Preço e valor FOB | Deduções por kg |
|---|---|---|
| FaturamentoANeRA, linhas 7:850 | `BD = AI-SUM(AU,AV,AW,AX,AZ,AY,BA)`; `BB = AE*BD` | AU frete; AV comissão; AW literal 0; AX contrato; AY logística reversa; AZ pallet; BA descarga |
| FaturamentoRN, linhas 7:1156 | `BE = AI-SUM(AU,AV,AW,AX,BA,AZ,BB,AY)`; `BC = AE*BE` | AU frete; AV comissão; AW literal 0; AX contrato; AY administração; AZ logística reversa; BA pallet; BB descarga |
| FaturamentoJA, linhas 7:352 | `AZ = AE*(AI-SUM(AU:AY))` | AU frete; AV comissão; AW adicional de 1/12; AX logística reversa; AY descarga |

### Comissão

AN/RA/RN: `VLOOKUP(vendedor,'Comissão '!E:AK,33,0)`, retornando AK como **valor por kg**, sem multiplicar novamente pelo faturamento do item. O cadastro inicial preserva o valor calculado e salvo no Excel, com origem da célula. O motor não refaz a folha de pagamento nem recalcula salários para outros períodos.

A cadeia real da aba Comissão está registrada em `mapa_formulas.csv` e `cadastros_snapshot.json`:

- L/M somam peso/faturamento por vendedor nas abas AN/RA e RN.
- N = M×J + M×K; O = N/H2×H3; P = I/H2×H3; Q = H+I+N+O+P.
- R:AB aplicam os percentuais da linha 3 à base Q. Estas colunas estão ocultas no Excel; há valores e fórmulas compartilhadas a preservar.
- AC = N+O; AD = H+I+P+SUM(R:AB).
- AE = IFERROR(AC/L,0); AF = IFERROR((AD/K2×K3)/L,0); AG = AF+AE.
- AH/AI/AJ rateiam gestores/supervisores, consultando F102:AE111 e usando participações de faturamento, K2/K3 e peso L. AK = AG+AH+AI+AJ.
- Os valores H2/H3 e K2/K3 são drivers do arquivo, não foram substituídos por calendário presumido. Constantes e eventuais intervenções por célula permanecem no snapshot.

Januária: `AV = AL × Despesas!P[unidade]/AE`; `AW = AL × Despesas!Q[unidade]/AE`. A tabela N4:Q5 guarda 3% em P e P/12 em Q. Estes componentes ficam separados.

### Contrato e demais despesas

- **Contrato AN/RA/RN:** primeiro cliente em Despesas!Z4:AE724. Se não encontrado, rede em S4:X161. O valor é `AL × percentual / AE`. Uma correspondência com percentual zero/vazio permanece zero e não cai para a rede. O Excel usa a primeira correspondência, preservada pelo leitor. Quando ambas as buscas falham, o IFERROR dá zero.
- **Administração RN:** AY = `0.25+0.07+0.06`, total R$ 0,38/kg. Não foi estendido a outras unidades.
- **Logística reversa:** chave `unidade;produto;UF`, primeira correspondência em Despesas!AS:AX; Januária usa AZ:BE. Ausência não vira zero porque o Excel não usa IFERROR nesta busca: o item fica pendente.
- **Pallet AN/RA/RN:** cliente presente em Despesas!AG:AH paga `Despesas!AI3/1000 = 26/1000 = 0,026/kg`. Cliente ausente paga zero. Não acrescentado a Januária.
- **Descarga:** primeira correspondência do cliente em Despesas!BG:BI. Não encontrada: zero, conforme IFERROR.
- Componentes que não integram a fórmula da unidade aparecem com zero e origem “não integra a fórmula”, distintos de pendências.

### Frete

A fórmula AU foi preservada, incluindo a ordem das decisões:

1. Sem redespacho: tipos 2/3/4/5/9 dão zero. Nos demais casos, consulta a NF em FOBxRefaturamento!B3:D142; depois o cliente em G3:H142; depois `SUMIF(FreteANeRA!O:O,cliente,I:I) / SUMIF(...,D:D)`. O agrupamento é por cliente e inclui todas as unidades presentes nessa tabela, conforme o Excel; não se acrescentou filtro de unidade/período.
2. Com redespacho: consulta o transportador em ControleFrete!B:F. Transportador vazio ou igual ao texto da cooperativa presente na fórmula dá adicional zero. Nos demais casos soma AB para OC principal e unidade AC. Soma esse adicional a AN; o IFERROR interno preserva zero e o externo usa AN. No arquivo recebido, as colunas de dados B:AB do ControleFrete estão vazias; isso explica os fallbacks, sem criar tarifas.
3. **Regra explícita desta implementação:** tipo 1 com `frete_kg` da origem zero/nulo exige preenchimento manual, mesmo quando outra tabela permitiria reproduzir o frete do Excel. Sem esse preenchimento, frete, preço FOB e valor FOB operacionais ficam indisponíveis.
4. **Januária:** a fórmula original consulta `[1]Fev26!I44` ou `[1]Mai26`, vinculados a `03.AnaliseComercial.xlsx`. O valor salvo em AU não é tratado como manual confirmado. Os 330 itens de tipo 1 ficam pendentes. Os 16 itens com tipo 5 preservam o zero previsto pela fórmula.

Uma entrada manual exige valor explícito e origem. Zero manual informado é diferente de ausência. A estrutura permite receber esses dados de um cadastro futuro; não há CRUD nem gravação nesta fase.

## Inclusões e exclusões comprovadas

O cadastro de referência mantém a associação por data + unidade + série + NF + produto + cliente + peso. Ele está restrito aos itens deste arquivo, sem converter uma decisão pontual numa regra universal por CFOP/cliente. Para outro período, o perímetro e as tabelas precisam ser fornecidos/validados; o módulo não assume as mesmas inclusões automaticamente.

O CSV recebido da view filtrada contém 2.380 linhas. Destas, 2.339 correspondem a itens do Excel. Há 41 linhas fora do perímetro: 16 de `5151-06`/unidade 10, 24 de `5151-06`/unidade 111 e 1 de `5152-06`/unidade 180. Elas permanecem na saída auditável com motivo e sem FOB; isso não implanta uma exclusão geral desses CFOPs.

**NF 806684, unidade 111, cliente 9880:** não está no CSV da view, mas está em FaturamentoANeRA!422: produto 349, 40 kg, tipo de frete 9, preço 16,80 e valor total 672. A observação textual F5 manda retirar o cliente 9880, mas a linha foi efetivamente mantida. A implementação segue o conteúdo calculado, não generaliza a observação. Esta única inclusão provisória foi autorizada pelo usuário e recebe `provisorio=true`, origem da linha e status `calculado_provisorio`; não gera registro no banco. Seu valor FOB de referência é aproximadamente R$ 668,6753058807433.

Foi tentada a obtenção da configuração para a consulta pontual na tabela bruta. O arquivo local de conexão indicado pela configuração não existe nesta máquina; **o SELECT não foi executado** e a existência da nota em `comercial.faturamento_cfop` permanece sem confirmação. O diagnóstico está em `artifacts/fob/consulta_nf_806684.json`.

Para conciliar, basta uma consulta pontual autenticada, sem filtros da view, por exemplo:

```sql
SELECT *
FROM comercial.faturamento_cfop
WHERE unidade_documento = '111'
  AND nota_numero = '806684'
  AND COALESCE(NULLIF(LTRIM(BTRIM(cliente),'0'),''),'0') = '9880'
LIMIT 10;
```

`repository.read_invoice()` disponibiliza esse tipo de SELECT parametrizado, com no máximo 100 itens e escolha explícita entre view e tabela bruta. Não abre conexão. O CLI permanece offline; a nova extensão da API recebe a conexão somente leitura existente e chama esse SELECT pontual quando a nota não é localizada na view. Nenhuma conexão ou API foi iniciada nesta máquina nesta etapa.

## Comparação executada

| Categoria | Peso reproduzido | Peso de referência | FOB reproduzido do Excel, em centavos | Meta |
|---|---:|---:|---:|---:|
| Varejo | 203.818 kg | 203.818 kg | R$ 1.949.811,06 | R$ 1.949.811,06 |
| Atacado | 931.381 kg | 931.381 kg | R$ 7.900.355,54 | R$ 7.900.355,54 |
| Subprodutos | 510.740 kg | 510.740 kg | R$ 383.055,00 | R$ 383.055,00 |

Varejo agrega 65.518 kg de AN/RA + 87.131 kg de RN + 51.169 kg de JA. Atacado e Subprodutos são os itens correspondentes em AN/RA. As 2.340 linhas foram recalculadas; nenhuma divergência acima de R$ 0,00001 por item ou R$ 0,00000001/kg por componente foi encontrada na reprodução das fórmulas contra o cache. As diferenças completas, inferiores a centavo na agregação, ficam expostas no JSON; não houve ajuste para zerá-las.

**Reprodução do Excel não significa fechamento operacional.** O replay usa o frete externo salvo de JA apenas para comparar. No resultado operacional, Varejo tem 335 itens pendentes: 330 de JA e 5 com frete zerado na origem. Portanto seu `valor_fob` total e PM FOB permanecem `null`. A soma dos itens concluídos é apresentada como parcial, sem entrar no lugar do total. Atacado e Subprodutos têm cálculo completo com os cadastros congelados do Excel. A base de Varejo também contém a NF provisória, identificada separadamente.

Há 333 itens com diferença de entrada entre o CSV e o Excel, sobretudo no frete de origem. As cinco pendências adicionais são IDs 431179, 431180 (NF 806745, unidade 111), 431410, 431411 (NF 73077, unidade 180) e 432887 (NF 73075, unidade 180). As diferenças não foram corrigidas para coincidir com o Excel; valores originais e referências ficam lado a lado por item.

## Arquivos e validação

- `backend/fob/calculator.py`: contrato de cadastros, componentes, Decimal, frete manual e combinação FOB.
- `backend/fob/reference.py`: fórmulas por unidade, tabelas iniciais, primeiras correspondências, perímetro e proveniência de células.
- `backend/fob/workbook.py`: leitor OOXML somente leitura e limitado às linhas necessárias, inclusive colunas/abas ocultas e fórmulas compartilhadas.
- `backend/fob/repository.py`: SELECT pontual opcional; não registra API nem executa cargas.
- `backend/fob/__main__.py`: comparação offline e exportação auditável. `__init__.py` apenas expõe o motor.
- `tests/test_fob.py`: sete testes rápidos de precisão, pendência manual, zero explícito, Januária, perímetro, fórmulas ocultas e SELECT parametrizado.
- `tests/inspecionar_excel_fob.py`: atalho de inspeção do leitor, sem modificar o Excel.

Exemplo de execução a partir deste repositório:

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -m fob --excel "CAMINHO/AnalisePreco01a04.xlsx" --csv "CAMINHO/itens_view.csv" --saida artifacts/fob/resultado
python -m unittest discover -s tests -p test_fob.py -v
```

O comparativo completo levou cerca de 7 segundos nesta máquina; os sete testes unitários levam menos de um segundo. Não foram executados extratores, tratadores, jobs, consultas amplas, testes dos demais BIs ou DDL/DML.

Saídas geradas:

- `resumo.json`: pesos, metas, diferenças completas, parciais e pendências.
- `itens_auditaveis.jsonl`: dados originais, campos `/kg`, origem/fórmula/estado de cada componente, FOB, comparação com o Excel, chave manual e flag provisória.
- `replay_excel.json`: comparação de cada item e componente contra os valores salvos, separada da operação.
- `cadastros_snapshot.json`: tabelas iniciais, frete agregado e cadeia completa da Comissão com os campos ocultos.
- `mapa_formulas.csv`: fórmulas expandidas e valores salvos, com indicação de aba/coluna oculta. Fórmulas são texto para inspeção.

Fretes manuais podem ser fornecidos com `--fretes-manuais arquivo.json`. Cada chave é a junção com `|` dos campos de `chave_item` da saída; o valor é `{"valor_kg":"0.61","origem":"identificação do preenchimento"}`. Não se usa uma taxa única presumida para todas as notas. `--csv-bruto` aceita complemento restrito de dados da tabela bruta; a view tem prioridade e somente itens comprovados entram no comparativo.

Dependências que permanecem: conexão somente leitura ou resultado do SELECT da NF 806684; preenchimento manual dos 335 fretes pendentes; aprovação dos cadastros e do perímetro para períodos futuros. Os valores AK da Comissão são uma referência inicial do Excel, não um motor de folha atualizado. A tela está implementada no frontend oficial; cadastros PostgreSQL e persistência de frete manual ficam para uma próxima etapa.
