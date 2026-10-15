/* Apresentação apenas: médias e totais são recebidos do PostgreSQL/backend. */
(() => {
  const $ = id => document.getElementById(id);
  const formats = {
    inteiro: new Intl.NumberFormat("pt-BR", {maximumFractionDigits: 0}),
    media: new Intl.NumberFormat("pt-BR", {minimumFractionDigits: 1, maximumFractionDigits: 1})
  };
  let controller = null, sequence = 0;
  let opcoes = {};
  let grupos = [], ordenacao = null;
  const sortKeys = ["vendedor_pai", "qtde_nfs", "qtde_produto_por_nf", "peso_por_nf", "ticket_medio_por_nf"];
  const collator = new Intl.Collator("pt-BR", {sensitivity: "base", numeric: true});
  const headers = [...document.querySelectorAll("thead th")];
  const sortButtons = headers.map((th, index) => {
    const button = document.createElement("button");
    button.type = "button"; button.className = "sort-button";
    button.dataset.label = th.textContent;
    button.addEventListener("click", () => {
      const key = sortKeys[index];
      ordenacao = ordenacao?.key === key
        ? (ordenacao.direction === "asc" ? {key, direction: "desc"} : null)
        : {key, direction: "asc"};
      updateSorting();
      if (grupos.length) renderGroups();
    });
    th.replaceChildren(button);
    return button;
  });
  const sortTools = document.createElement("div"); sortTools.className = "sort-tools";
  const sortHint = document.createElement("span"); sortHint.textContent = "Clique nas colunas para ordenar";
  const resetSort = document.createElement("button"); resetSort.type = "button";
  resetSort.textContent = "Ordem padrão";
  resetSort.addEventListener("click", () => {ordenacao = null; updateSorting(); if (grupos.length) renderGroups();});
  sortTools.append(sortHint, resetSort);
  document.querySelector(".table-scroll").before(sortTools);
  function updateSorting() {
    headers.forEach((th, index) => {
      const active = ordenacao?.key === sortKeys[index];
      th.setAttribute("aria-sort", active ? (ordenacao.direction === "asc" ? "ascending" : "descending") : "none");
      const button = sortButtons[index];
      button.textContent = button.dataset.label + (active ? (ordenacao.direction === "asc" ? " ↑" : " ↓") : " ↕");
      button.title = active && ordenacao.direction === "desc" ? "Restaurar ordem padrão" :
        active ? "Ordenar do maior para o menor" : "Ordenar do menor para o maior";
    });
    resetSort.disabled = ordenacao === null;
  }
  updateSorting();
  const filters = new FilterController({
    fields: [{id: "filter-unidade", apiKey: "unidade", multi: true, search: true}],
    includeDependentRefresh: false, optionsProvider: async () => opcoes,
    onChange: () => status("Filtros alterados. Clique em Consultar relatório.", "info")
  });
  filters.register();
  $("filter-unidade").querySelector("button").setAttribute("aria-labelledby", "unidade-label");
  document.addEventListener("keydown", e => {if (e.key === "Escape") filters.closeAll();});

  function status(message, kind = "info") {
    $("status").textContent = message;
    $("status").className = `status ${kind}`;
  }
  function formatDate(value) {return value ? value.split("-").reverse().join("/") : "—";}
  function num(value) {
    if (value === null || value === "" || value === undefined) throw new Error("A API retornou um indicador ausente.");
    const number = Number(value);
    if (!Number.isFinite(number)) throw new Error("A API retornou um indicador inválido.");
    return number;
  }
  function row(item, total = false) {
    const tr = document.createElement("tr");
    if (item.pendente) tr.className = "pending-row";
    const label = document.createElement("th");
    label.scope = "row"; label.textContent = total ? "Total" : item.vendedor_pai;
    if (item.pendente) {const badge = document.createElement("span");badge.className="pending-badge";badge.textContent="Em definição";label.append(badge);}
    tr.append(label);
    for (const [key,format] of [["qtde_nfs","inteiro"],["qtde_produto_por_nf","media"],["peso_por_nf","inteiro"],["ticket_medio_por_nf","media"]]) {
      const td=document.createElement("td");td.textContent=formats[format].format(num(item[key]));tr.append(td);
    }
    return tr;
  }
  function renderGroups() {
    const ordered = grupos.map((item, index) => ({item, index}));
    if (ordenacao) ordered.sort((a, b) => {
      const key = ordenacao.key;
      const comparison = key === "vendedor_pai"
        ? collator.compare(a.item[key], b.item[key]) : num(a.item[key]) - num(b.item[key]);
      return (ordenacao.direction === "asc" ? comparison : -comparison) || a.index - b.index;
    });
    const body = document.createDocumentFragment();
    for (const {item} of ordered) body.append(row(item));
    $("report-body").replaceChildren(body);
  }
  function render(payload) {
    if (!Array.isArray(payload.grupos) || !payload.total) throw new Error("Formato de resposta inesperado da API.");
    grupos = payload.grupos;
    renderGroups();
    const total = row(payload.total, true);
    $("report-total").replaceChildren(total);
    $("period-label").textContent = `${formatDate(payload.periodo?.data_inicio)} a ${formatDate(payload.periodo?.data_fim)}`;
    $("units-label").textContent = payload.unidades?.length ? `Unidades: ${payload.unidades.join(" · ")}` : "Todas as unidades disponíveis";
    const updated = payload.total.atualizado_em;
    $("updated-label").textContent = updated ? `Carga mais recente: ${new Date(updated).toLocaleString("pt-BR")}` : "Consulta concluída pela API da Granja Brasília.";
    status(num(payload.total.qtde_nfs) === 0 ? "Nenhuma NF encontrada para os filtros selecionados." : "Relatório atualizado.", "success");
  }
  function clearReport() {
    grupos = [];
    const tr = document.createElement("tr"),td=document.createElement("td");td.colSpan=5;td.className="empty";td.textContent="Consulta não disponível. Confira a mensagem acima.";tr.append(td);
    $("report-body").replaceChildren(tr);$("report-total").replaceChildren();$("period-label").textContent="—";
  }
  async function consultar() {
    const inicio = $("data-inicio").value, fim = $("data-fim").value;
    if (!inicio || !fim || inicio > fim) {status("Informe um período válido, com a data inicial anterior ou igual à final.", "error");return;}
    controller?.abort();controller=new AbortController();const own=++sequence;
    filters.closeAll();$("report-body").closest("section").setAttribute("aria-busy", "true");
    status("Consultando notas fiscais e indicadores…");
    try {
      const result=await apiGet(APP_CONFIG.endpoints.resumo,{data_inicio:inicio,data_fim:fim,...filters.values()},{signal:controller.signal});
      if (own!==sequence)return;
      render(result);
    } catch(error) {
      if (error.name==="AbortError" || own!==sequence)return;
      clearReport();status(error.message,"error");
    } finally {if(own===sequence)$("report-body").closest("section").setAttribute("aria-busy","false");}
  }
  $("filters-form").addEventListener("submit",e=>{e.preventDefault();consultar();});
  for (const id of ["data-inicio","data-fim"]) $(id).addEventListener("change",()=>status("Período alterado. Clique em Consultar relatório."));
  async function iniciar() {
    try {
      opcoes=await apiGet(APP_CONFIG.endpoints.filtros);
      await filters.loadOptions({preserve:false});
      $("data-inicio").value=opcoes.periodo_disponivel?.data_inicio || "";
      $("data-fim").value=opcoes.periodo_disponivel?.data_fim || "";
      if ($("data-inicio").value && $("data-fim").value) await consultar();
      else status("A fonte ainda não tem notas fiscais disponíveis.");
    } catch(error) {clearReport();status(error.message,"error");}
  }
  iniciar();
})();
