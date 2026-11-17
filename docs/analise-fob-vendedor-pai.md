# Análise FOB por Vendedor Pai

Página: `analise-vendedor-pai.html`. GET: `/api/comercial/comparativo-fob/analise-vendedor-pai`.

## Origem e cálculo

A rota usa o motor operacional de `feeding._month`, sem modificar seu cálculo, suas exclusões ou os relatórios existentes. Faturamento: `comercial.vw_faturamento_vendedor_pai_itens`; cadastros: os mesmos do Comparativo FOB. Vendedor Pai: `comercial.vendedor_grupo`, sem JOIN multiplicador. Cadastros conflitantes após normalização recebem Não classificado. RN e Januária são definidos pela unidade.

`analise_vendedor_catalogo.json` contém códigos, descrições e ordem dos blocos do Excel examinado; não contém valores financeiros. O Excel original não é aberto em tempo de execução. O catálogo de produtos deve ser revisado quando novos códigos forem incluídos no negócio; produtos não contemplados são sinalizados na cobertura.

O benchmark é o FOB/peso do mesmo código nas quatro unidades, no período consultado, antes dos filtros de exibição. Diferença regional = soma por produto de peso × (PM regional − PM global). Percentual diferença = diferença/(FOB−diferença), com a guarda do Excel quando FOB não é positivo. % peso e % FOB usam o catálogo principal nas unidades/produtos selecionados, antes do filtro regional. Não há média simples de médias nem cálculo financeiro no JavaScript.

Comissão inclui o adicional. Contrato significa contrato de cliente/rede. A ausência de FOB em qualquer item impede considerar completo seu grupo e o benchmark do produto, inclusive quando o item pendente está em outra regional.

## Abrangência e pendências

A tabela mantém a ordem das 22 regionais. Regionais adicionais são exibidas com identificação, sem atribuição automática a Atacado ou Varejo. Sem Vínculo pertence ao consolidado Varejo conforme a referência. Granel considera Sem Vínculo nas unidades 10/111. CMS é separado. O total antes dos impostos preserva o universo da linha 165 (Atacado, Varejo e granel), sem inventar resultado projetado.

Resultado projetado, percentual de resultado e impostos são `null` até definir CPV industrial por produto/competência, despesas administrativas/rateio e abrangência fiscal. Contrato/kg regional de RN/JA fica pendente de metodologia: os zeros fixos do Excel não comprovam uma regra. Não reproduzir silenciosamente a inconsistência de CMS/resíduos nem a distribuição adicional de impostos do arquivo histórico.

O equilíbrio das diferenças é uma verificação interna do benchmark, não uma conciliação com o Excel. Ao restringir unidades, a soma exibida pode deixar de ser zero porque a referência continua global. Os valores atuais podem diferir da planilha por composição da base e cadastros. A soma é feita em Decimal, precisão 38, com arredondamento somente na apresentação.

## Integração

Somente uma rota GET adicionada ao router FOB existente. Nenhuma tabela, view, permissão ou dependência nova. A autenticação herdada da API continua obrigatória. Cache separado por credencial e por snapshot estável do banco; sem dados financeiros de referência Excel no novo processamento.

O pacote `artifacts/analise-vendedor-pai-20261117/api_anderson_analise_vendedor_pai.zip` contém dois arquivos novos e `routes.py`, preservando a base `api_zootecnico(8).zip`. Conferir alterações posteriores em routes.py antes de substituí-lo. Não substituir feeding.py, o motor ou módulos compartilhados. A nova rota precisa ser instalada no Anderson e encaminhada/autorizada pela integração atual antes de validar o Portal real.

## Validação local

- `python -B tests/test_seller_analysis.py`: benchmark por produto, denominador, filtros, comissão adicional, pesos zero, propagação de pendências, conflitos de vendedores e catálogo.
- `tests/seller-analysis-browser.cjs`: navegador com resposta interceptada, sem API de produção; tabela, detalhamento, CSV, preservação de filtros, mobile, tema e falha sem manter resultado antigo.
- Agregação dos 26.927 itens da validação anterior de outubro (não é uma leitura nova de todo o faturamento), com cadastro de vendedores consultado por SELECT: 22 regionais, 612 combinações produto/regional, diferença global de 5,416681E-29 (R$ 0,00 na exibição).
- Nenhum teste autenticado da nova rota publicada foi realizado: ela ainda não foi instalada. FastAPI não está instalado no ambiente Python local; foram verificadas a sintaxe dos módulos/ZIP e a agregação independentemente do framework, sem instalar dependências.

Backup dos arquivos existentes alterados: `artifacts/backup-analise-vendedor-pai-20261117/`.
