# BI de Faturamento por Vendedor Pai

Projeto independente em HTML/CSS/JavaScript. Reutiliza o cliente HTTP, token da CENTRAL, multisseleção e identidade visual da referência Bi-Matrizes. Não altera esse projeto nem importa suas regras de negócio. Não foi publicado.

## Abrir o frontend

Sirva esta pasta com um servidor estático, por exemplo `python -m http.server 8000 --bind 127.0.0.1`, e abra http://127.0.0.1:8000. Abrir como file:// não é o fluxo recomendado.

O frontend consulta exclusivamente o Worker público configurado em assets/js/config.js. O token precisa existir no sessionStorage da origem/aba compatível com a CENTRAL, na chave granjabi_auth_token. Sem sessão, informa que o usuário deve entrar pelo Portal. Não há dados de demonstração, senha, Basic Auth ou token fixo no frontend. Não transfere tokens em query strings. Servir localmente não cria automaticamente uma sessão da CENTRAL.

**Os endpoints novos ainda precisam ser implantados no backend compartilhado.** Antes disso, uma sessão válida não basta para disponibilizar o relatório. A integração foi testada localmente com o módulo/roteador real e o PostgreSQL em modo leitura; o Worker com sessão real não foi homologado. O browser de teste intercepta respostas calculadas no SQL real, apenas em contexto isolado.

## Objetos e implantação futura

Objetos novos preparados, sem execução em produção:

1. comercial.vendedor_grupo: auxiliar, vendedor único.
2. comercial.vw_nf_por_vendedor_pai: agrega unidade + série + número antes do JOIN.
3. modules/faturamento_nf: módulo do mesmo backend FastAPI.

Revisar e executar os SQLs em ordem: backend/sql/001_vendedor_grupo.sql, 002_carga_vendedores.sql e 003_vw_nf_por_vendedor_pai.sql. O schema comercial e a fonte comercial.vw_faturamento_cfop_filtrado já existem e são preservados. Conferir permissões do usuário da API: leitura dos objetos necessários e USAGE do schema, sem permissões de escrita. A importação usa conta separada, fora da API.

Para regenerar a carga a partir da primeira aba/cabeçalho na segunda linha:

```text
python backend/importar_vendedores.py "CAMINHO/Tabela_de_vendedor.xlsx" --gerar-sql backend/sql/002_carga_vendedores.sql
```

O importador só gera SQL; não conecta ao banco. Usa TRIM, normalização de código, Varejo Grande BH e ON CONFLICT. Duplicidades idênticas são consolidadas; conflitos de classificação interrompem a geração. Preserva Inativo, Sem Vínculo e grupos de nomes próprios. Não remove automaticamente vendedores antigos ausentes em uma versão posterior do XLSX.

## Integração com a API existente

A implementação foi preparada contra a cópia local api-db/api_zootecnico, que tem core.contracts.ModuleSpec, core.registry.discover_modules, core.bootstrap.register_modules e bi_generic.router.criar_router. A pasta antiga _backend-zootecnico-referencia possui outra versão e não foi tratada como código atual de implantação. Confirmar a versão efetiva em produção antes de instalar.

Copiar somente backend/modules/faturamento_nf para modules/faturamento_nf do backend compartilhado. O registrador já descobre o pacote e o roteador genérico atende:

- GET /api/bi/faturamento-nf/filtros
- GET /api/bi/faturamento-nf/resumo

Filtros: data_inicio/data_fim (AAAA-MM-DD), unidade repetida para multisseleção. OR entre unidades; AND com datas. Data final inclusiva via limite exclusivo do dia seguinte. Todas as consultas são parametrizadas; agregações ocorrem no PostgreSQL. O usuário vê as médias prontas; o JavaScript só formata.

O endpoint genérico detalhes existe no padrão, mas retorna 404 para este módulo porque a tabela resumida não precisa dele. Não cria app, autenticação, porta, Tunnel ou container novo. O módulo usa context.banco, com a política somente leitura existente. Não altera os arquivos de Matrizes, registry, bootstrap, router ou serviço principal.

A autenticação interna continua no middleware existente; o Worker continua recebendo Bearer da CENTRAL e encaminhando autenticação interna. Verificar se o Worker já encaminha /api/bi/* e permite esse BI no cadastro de permissões. Se usa allowlist, acrescentar essas duas rotas conforme a implantação aprovada. Nenhum código/secrets de Worker foi fornecido, alterado ou publicado.

## Regras e pendências

- Uma nota tem chave unidade_documento + serie + nota_numero.
- Produto distinto dentro da nota conta uma vez; pesos e valores somam os itens reais.
- Total recalcula médias sobre todas as NFs, nunca média simples das categorias.
- Vendedor sem cadastro vira Não classificado e permanece no total.
- NF com data/vendedor divergente ou chave incompleta interrompe o resumo com 409; não escolhe vendedor arbitrário.
- CD Ribeirão das Neves e Januária são placeholders zerados; não há inferência por cliente/cidade/unidade. Se um futuro cadastro tentar usar esses nomes antes da definição, as NFs permanecem em Não classificado até a regra ser aprovada.
- A fonte atual é uma view sobre tabela de cópia de teste, para a semana de setembro. Esta entrega não conecta automaticamente essa cópia ao extrator nem muda sua janela de dados.
- As diferenças de condição de pagamento/desconto financeiro encontradas entre a planilha e a fonte em etapa anterior não mudam as métricas deste relatório, que usam contagem, produtos, peso e valor_total_faturado.
- A imagem mencionada na tarefa não foi anexada nesta mensagem. O layout segue o título, cores, colunas, formatos e sequência especificados; não houve homologação visual contra uma imagem ausente.

## Validação

Consulte docs/VALIDACAO.md e backend/sql/004_validacao.sql. Foram comparados PostgreSQL e a planilha de itens relatorio (3).xlsx agrupada pela auxiliar de vendedores. Não foi fornecida uma planilha pronta com os indicadores por vendedor pai; o relatório deixa essa distinção explícita.

Reexecutar testes exige as dependências de backend/requirements-testes.txt e a cópia do backend atual; os comandos estão em docs/VALIDACAO.md. Não executar robôs ou implantar em produção para testar esta entrega.
