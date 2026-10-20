# Origens do Comparativo PM FOB

O comparativo atual usa faturamento do PostgreSQL e um catálogo JSON extraído do Excel AnalisePreco01a04.xlsx. Não lê o arquivo XLSX a cada consulta. Os parâmetros desse catálogo estão comprovados somente para 01–04/10/2026.

| Informação | Origem atual | O que levantar para usar o banco em outros meses |
| --- | --- | --- |
| Data, unidade, NF, série, cliente, rede, vendedor, produto, família, UF, peso | comercial.vw_faturamento_cfop_filtrado | Conferir disponibilidade histórica e regras de inclusão da view. |
| Preço praticado e valor total faturado | Mesma view, preco_praticado e valor_total_faturado | Já são entradas do banco; não são o preço FOB nem seu valor final. |
| Canal | No recorte conferido: classificação do Excel. No histórico: comercial.vendedor_grupo.canal_venda; SUBPRODUTOS separado pela família | Cadastro de vendedor/canal com vigência. O cadastro atual não comprova o canal de janeiro. |
| Frete | Tipo frete, frete_kg, OC e redespacho vêm da view; a fórmula também consulta FOBxRefaturamento, FreteANeRA e ControleFrete do Excel | Valores por NF/cliente e período, transportes, rateios e redespacho. Frete da view pode ser substituído/complementado pela fórmula do Excel. Januária exige informação manual nos casos previstos; tipo 1 nulo/zero continua pendente. |
| Comissão AN/RA/RN | Aba Comissão, vendedor E → valor R$/kg AK já calculado para o recorte | Regra de comissão por vendedor/unidade e vigência; bases, percentuais e ajustes que geram o R$/kg. Não replicar a média de outubro para janeiro. |
| Comissão e adicional de Januária | Despesas N:P e N:Q; percentual × valor_total_faturado ÷ peso | Percentuais por unidade, vigência e base de incidência. |
| Contrato | Despesas Z:AE por cliente; fallback S:X por rede; percentual × valor_total_faturado ÷ peso | Cliente/rede, percentual, vigência e prioridade. Zero explícito por cliente deve preservar a prioridade sobre rede. |
| Administração RN | Literal da fórmula do Excel: 0,25 + 0,07 + 0,06 R$/kg | Confirmar componentes, unidades e datas em que se aplicam. Não assumir validade anual. |
| Logística reversa | Despesas AS:AX; Januária AZ:BE, chave unidade/produto/UF | Valor R$/kg por unidade, produto, UF e vigência. |
| Pallet | Lista de clientes Despesas AG:AH e parâmetro AI3 ÷ 1.000 | Clientes abrangidos, parâmetro, base/unidade de rateio e vigência. |
| Descarga | Despesas BG:BI por cliente | Cliente, valor R$/kg e vigência. |
| FOB/kg e valor FOB | Calculados pelo motor; não são campos prontos da view | Preço praticado menos despesas/kg; multiplicar pelo peso. Despesa desconhecida impede considerar FOB concluído. |
| Referências e perímetro de outubro | Linhas das abas FaturamentoANeRA, FaturamentoRN e FaturamentoJA | Formalizar inclusões/exclusões do histórico. Não generalizar a exceção do CFOP 5151-06 nem a NF 806684. |

NF 806684, unidade 111, cliente 9880: o motor primeiro busca na origem e faz SELECT pontual na tabela bruta comercial.faturamento_cfop se necessário. Se não conciliada, usa provisoriamente FaturamentoANeRA linha 422 (40 kg), com identificação explícita. Isso não cria registro no banco nem autoriza outras notas provisórias.

Para cada cadastro de despesas, reunir ao menos a chave aplicável (unidade/vendedor/cliente/rede/produto/UF), valor, tipo de cálculo (percentual ou R$/kg), início/fim de vigência e documento de origem. Identificar separadamente valor zero confirmado e informação ausente. Este documento é um levantamento; não cria tabelas ou CRUD.

Consultas fora de 01–04/10/2026 usam o perímetro da view, sem whitelist do Excel e sem acrescentar notas provisórias. Mostram peso e preço praticado; despesas/FOB permanecem pendentes. Períodos mistos seguem esse mesmo modo histórico. Não existe conciliação do ano com a planilha de quatro dias.
