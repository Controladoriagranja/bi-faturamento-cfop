/* Detalhamento sob demanda. Filtros são uma cópia da consulta exibida. */
const FaturamentoDetails = (() => {
  const labels = {data:"Data", unidade_documento:"Unidade", serie:"Série", nota_numero:"Nota fiscal",
    vendedor:"Cód. vendedor", vendedor_nome:"Vendedor", vendedor_pai:"Vendedor pai", cliente:"Cód. cliente",
    razao_social:"Razão social", produto:"Cód. produto", produto_descricao:"Produto", cfop:"CFOP",
    cfop_descricao:"Descrição CFOP", peso:"Peso", valor_total_faturado:"Valor faturado",
    qtde_itens:"Itens", qtde_produtos_distintos:"Produtos distintos", peso_total_nf:"Peso da NF",
    valor_total_nf:"Valor da NF", carregado_em:"Carregado em", chave_nf:"Chave da NF",
    id:"ID", empresa_contexto:"Empresa da extração", unidade_contexto:"Unidade da extração",
    processo:"Processo", periodo_inicio:"Início da extração", periodo_fim:"Fim da extração",
    mes:"Mês", meio_venda:"Meio de venda", devolucao:"Devolução", pedido:"Pedido",
    oc_principal:"OC principal", redespacho:"Redespacho", romaneio:"Romaneio", frete:"Frete",
    rede:"Rede", tipo_de_cliente:"Tipo de cliente", nome_fantasia:"Nome fantasia",
    rota_cliente:"Rota do cliente", rota_pedido:"Rota do pedido", cidade:"Cidade", uf:"UF",
    ramo_ativ:"Ramo de atividade", um:"Unidade de medida", familia:"Família", volumes:"Volumes",
    lista:"Lista", ocorr:"Ocorrência", pre_base:"Preço base", preco_praticado:"Preço praticado",
    valor_produto:"Valor do produto", desconto_comercial:"Desconto comercial", desc_finan:"Desconto financeiro",
    frete_kg:"Frete por kg", nota_refaturada:"Nota refaturada", romaneio_refaturada:"Romaneio refaturado",
    nota_devolucao:"Nota de devolução", cliente_original:"Cliente original",
    cond_pag_cliente:"Condição de pagamento do cliente", cond_pag_nota:"Condição de pagamento da nota",
    ano_semana:"Ano da semana", numero_semana:"Semana", frete_sem_valor:"Frete sem valor",
    cond_pag_nota_original:"Condição de pagamento original", cond_pag_nota_status:"Situação da condição de pagamento",
    id_venda_correspondente:"ID da venda correspondente"};
  const defaults = {
    notas:["data","unidade_documento","serie","nota_numero","vendedor","qtde_itens","qtde_produtos_distintos","peso_total_nf","valor_total_nf"],
    itens:["data","unidade_documento","serie","nota_numero","vendedor_nome","razao_social","produto","produto_descricao","cfop","peso","valor_total_faturado"]
  };
  const decimals = new Set("peso valor_total_faturado peso_total_nf valor_total_nf volumes pre_base preco_praticado valor_produto desconto_comercial desc_finan frete_kg".split(" "));
  const integer = new Intl.NumberFormat("pt-BR");
  const decimal = new Intl.NumberFormat("pt-BR", {minimumFractionDigits:2, maximumFractionDigits:2});
  const metricLabels = {vendedor_pai:"Itens do grupo",qtde_nfs:"Quantidade de NFs",qtde_produto_por_nf:"Produtos por NF",peso_por_nf:"Peso por NF",ticket_medio_por_nf:"Ticket médio por NF"};
  const dialog = document.createElement("dialog");
  dialog.className = "details-dialog";
  dialog.setAttribute("aria-labelledby", "details-title");
  dialog.innerHTML = `
    <div class="details-shell">
      <header class="details-header"><div><span class="eyebrow">DETALHAMENTO</span><h2 id="details-title"></h2><p id="details-context"></p></div><button type="button" id="details-close">← Voltar ao relatório</button></header>
      <div class="details-tools">
        <div class="details-tabs" role="group" aria-label="Visão dos detalhes"><button type="button" data-view="notas">Por nota fiscal</button><button type="button" data-view="itens">Itens da view</button></div>
        <form id="details-search"><label for="details-query">Buscar notas por cliente, vendedor, produto, CFOP ou número</label><div><input id="details-query" type="search" maxlength="200" placeholder="Buscar nas notas do filtro"><button>Buscar</button></div></form>
        <button type="button" id="details-export">Exportar CSV</button>
      </div>
      <p class="details-search-note">A busca seleciona notas completas e mantém todos os seus itens.</p>
      <div class="details-note" id="details-note" hidden><span></span><button type="button" id="details-all">Ver todas as notas do grupo</button></div>
      <details class="details-columns"><summary>Selecionar colunas</summary><div id="details-columns"></div></details>
      <p id="details-totals" class="details-totals"></p>
      <p id="details-status" role="status" aria-live="polite"></p>
      <div class="details-grid" tabindex="0" aria-label="Linhas do detalhamento"><table><thead id="details-head"></thead><tbody id="details-body"></tbody></table></div>
      <footer class="details-pagination"><button type="button" id="details-prev">← Anterior</button><span id="details-page"></span><label>Por página <select id="details-size"><option>25</option><option selected>50</option><option>100</option><option>200</option></select></label><button type="button" id="details-next">Próxima →</button></footer>
    </div>`;
  document.body.append(dialog);
  const $ = id => dialog.querySelector(`#details-${id}`);
  let state, payload, controller, exportController, generation = 0, exporting = false, loaded = false;
  const selected = {notas:new Set(defaults.notas), itens:new Set(defaults.itens)};
  function message(text, error = false) {$("status").textContent = text; $("status").classList.toggle("error",error);}
  function params(page = state.pagina, size = state.por_pagina) {
    return {...state.filtros, vendedor_pai:state.grupo, visao:state.visao, indicador:state.indicador,
      busca:state.busca, chave_nf:state.chave, pagina:page, por_pagina:size};
  }
  function date(value) {return value ? value.split("-").reverse().join("/") : "—";}
  function updateContext() {
    $("title").textContent = state.grupo || "Todas as notas";
    $("context").textContent = `${metricLabels[state.indicador]} · ${date(state.filtros.data_inicio)} a ${date(state.filtros.data_fim)} · ${state.filtros.unidade?.length ? "Unidades: " + state.filtros.unidade.join(", ") : "Todas as unidades"}`;
    dialog.querySelectorAll("[data-view]").forEach(button => button.setAttribute("aria-pressed",String(button.dataset.view === state.visao)));
    $("note").hidden = !state.chave;
    if (state.chave) $("note").querySelector("span").textContent = `Itens da NF ${JSON.parse(state.chave)[2]} · `;
  }
  function display(value, column) {
    if (value === null || value === undefined || value === "") return "—";
    if (decimals.has(column) && Number.isFinite(Number(value))) return decimal.format(Number(value));
    if (["data","periodo_inicio","periodo_fim"].includes(column)) return date(value);
    if (typeof value === "boolean") return value ? "Sim" : "Não";
    return String(value);
  }
  function visibleColumns() {return [...selected[state.visao]].filter(column => payload.colunas.includes(column));}
  function renderTable() {
    const columns = visibleColumns();
    const head = document.createElement("tr");
    for (const column of columns) {const th = document.createElement("th");th.scope="col";th.textContent=labels[column] || column;head.append(th);}
    if (state.visao === "notas") {const th=document.createElement("th");th.textContent="Detalhar";head.append(th);}
    $("head").replaceChildren(head);
    const body = document.createDocumentFragment();
    for (const item of payload.linhas) {
      const tr = document.createElement("tr");
      for (const column of columns) {const td=document.createElement("td");td.textContent=display(item[column],column);tr.append(td);}
      if (state.visao === "notas") {
        const td=document.createElement("td"), button=document.createElement("button");
        button.type="button";button.textContent="Ver itens";button.setAttribute("aria-label",`Ver itens da nota ${item.nota_numero}, série ${item.serie}, unidade ${item.unidade_documento}`);
        button.addEventListener("click",()=>{state.chave=item.chave_nf;state.visao="itens";state.pagina=1;load();});
        td.append(button);tr.append(td);
      }
      body.append(tr);
    }
    if (!payload.linhas.length) {const tr=document.createElement("tr"), td=document.createElement("td");td.colSpan=columns.length+1;td.className="empty";td.textContent="Nenhum registro encontrado para este filtro.";tr.append(td);body.append(tr);}
    $("body").replaceChildren(body);
  }
  function renderColumns() {
    const fragment = document.createDocumentFragment();
    for (const column of payload.colunas) {
      const label=document.createElement("label"), input=document.createElement("input");input.type="checkbox";input.checked=selected[state.visao].has(column);
      input.addEventListener("change",()=>{
        const set=selected[state.visao];
        if (!input.checked && set.size === 1) {input.checked=true;return;}
        if(input.checked)set.add(column);else set.delete(column);
        renderTable();
      });
      label.append(input,document.createTextNode(labels[column] || column));fragment.append(label);
    }
    $("columns").replaceChildren(fragment);
  }
  function pagination() {
    const pages = Math.max(1,Math.ceil((payload?.total_registros || 0)/state.por_pagina));
    $("prev").disabled=!loaded || state.pagina<=1;
    $("next").disabled=!loaded || state.pagina>=pages;
    $("export").disabled=!loaded || !payload?.total_registros;
    $("page").textContent=loaded ? `Página ${state.pagina} de ${integer.format(pages)} · ${integer.format(payload.total_registros)} registros` : "";
  }
  function cancelExport() {exportController?.abort();exporting=false;$("export").textContent="Exportar CSV";}
  async function load() {
    controller?.abort();cancelExport();controller=new AbortController();const own=++generation;
    loaded=false;pagination();updateContext();message("Carregando detalhes…");$("body").replaceChildren();$("head").replaceChildren();$("totals").textContent="";$("columns").replaceChildren();
    dialog.setAttribute("aria-busy","true");
    try {
      const result=await apiGet(APP_CONFIG.endpoints.detalhes,params(),{signal:controller.signal});
      if(own!==generation)return;
      if(!Array.isArray(result.linhas)||!Array.isArray(result.colunas)||!Number.isSafeInteger(result.total_registros))throw new Error("Resposta de detalhes inválida.");
      payload=result;
      const pages=Math.max(1,Math.ceil(payload.total_registros/state.por_pagina));
      if(state.pagina>pages){state.pagina=pages;return load();}
      renderColumns();renderTable();loaded=true;pagination();
      const totals=payload.totais;
      $("totals").textContent=`${integer.format(totals.qtde_nfs)} NFs · ${integer.format(totals.qtde_itens)} itens · Peso: ${decimal.format(Number(totals.peso_total))} · Faturamento: R$ ${decimal.format(Number(totals.valor_total))}`;
      message(payload.total_registros ? "Detalhes carregados. A exportação inclui todas as páginas e as colunas selecionadas." : "Nenhum registro encontrado.");
    } catch(error) {if(error.name!=="AbortError" && own===generation)message(error.message,true);}
    finally {if(own===generation)dialog.setAttribute("aria-busy","false");}
  }
  function csv(value) {
    let text=value==null ? "" : String(value);
    // Evita fórmulas executáveis ao abrir o CSV em uma planilha.
    if (/^[\s]*[=+@-]/.test(text) && !/^-?\d+(\.\d+)?$/.test(text)) text="'"+text;
    return '"'+text.replaceAll('"','""')+'"';
  }
  async function exportCsv() {
    if(exporting){cancelExport();message("Exportação cancelada.");return;}
    if(!loaded || !payload.total_registros)return;
    exporting=true;exportController=new AbortController();const signal=exportController.signal, own=generation;
    $("export").textContent="Cancelar exportação";
    const columns=visibleColumns(), lines=[columns.map(c=>csv(labels[c]||c)).join(";")];
    try {
      let total=null;
      for(let page=1; ;page++) {
        const result=await apiGet(APP_CONFIG.endpoints.detalhes,params(page,500),{signal});
        if(own!==generation || signal.aborted)return;
        if(total===null)total=result.total_registros;
        if(result.total_registros!==total)throw new Error("A fonte mudou durante a exportação. Consulte novamente e repita.");
        for(const item of result.linhas)lines.push(columns.map(c=>csv(item[c])).join(";"));
        message(`Exportando ${integer.format(lines.length-1)} de ${integer.format(total)} registros…`);
        if(page*500>=total)break;
        if(!result.linhas.length)throw new Error("A API retornou uma página incompleta. Repita a consulta.");
      }
      if(lines.length-1!==total)throw new Error("A fonte mudou durante a exportação. Consulte novamente e repita.");
      const url=URL.createObjectURL(new Blob(["\uFEFF",lines.join("\r\n")],{type:"text/csv;charset=utf-8"}));
      const link=document.createElement("a");link.href=url;link.download=`faturamento-${state.visao}-${state.filtros.data_inicio}-${state.filtros.data_fim}.csv`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      message(`CSV exportado com ${integer.format(total)} registros.`);
    } catch(error) {if(error.name!=="AbortError" && own===generation)message(error.message,true);}
    finally {if(own===generation && exportController.signal===signal){exporting=false;$("export").textContent="Exportar CSV";}}
  }
  function close() {controller?.abort();cancelExport();generation++;if(dialog.open)dialog.close();}
  dialog.addEventListener("cancel",event=>{event.preventDefault();close();});
  $("close").addEventListener("click",close);
  $("search").addEventListener("submit",event=>{event.preventDefault();state.busca=$("query").value.trim();state.pagina=1;load();});
  dialog.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>{state.visao=button.dataset.view;state.chave=null;state.pagina=1;load();}));
  $("all").addEventListener("click",()=>{state.chave=null;state.pagina=1;load();});
  $("prev").addEventListener("click",()=>{state.pagina--;load();});
  $("next").addEventListener("click",()=>{state.pagina++;load();});
  $("size").addEventListener("change",()=>{state.por_pagina=Number($("size").value);state.pagina=1;load();});
  $("export").addEventListener("click",exportCsv);
  return {close, open(options) {
    state={...options,filtros:structuredClone(options.filtros),pagina:1,por_pagina:50,busca:"",chave:null};
    $("query").value="";$("size").value="50";dialog.querySelector(".details-columns").open=false;
    if(!dialog.open)dialog.showModal();load();
  }};
})();
