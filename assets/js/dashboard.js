/* Apresentação apenas: médias e totais são recebidos do PostgreSQL/backend. */
(() => {
  const $ = id => document.getElementById(id);
  const formats = {
    inteiro: new Intl.NumberFormat("pt-BR", {maximumFractionDigits: 0}),
    media: new Intl.NumberFormat("pt-BR", {minimumFractionDigits: 1, maximumFractionDigits: 1})
  };
  let controller = null, sequence = 0;
  let opcoes = {};
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
  function render(payload) {
    if (!Array.isArray(payload.grupos) || !payload.total) throw new Error("Formato de resposta inesperado da API.");
    const body = document.createDocumentFragment();
    for (const item of payload.grupos) body.append(row(item));
    const total = row(payload.total, true);
    $("report-body").replaceChildren(body);$("report-total").replaceChildren(total);
    $("period-label").textContent = `${formatDate(payload.periodo?.data_inicio)} a ${formatDate(payload.periodo?.data_fim)}`;
    $("units-label").textContent = payload.unidades?.length ? `Unidades: ${payload.unidades.join(" · ")}` : "Todas as unidades disponíveis";
    const updated = payload.total.atualizado_em;
    $("updated-label").textContent = updated ? `Carga mais recente: ${new Date(updated).toLocaleString("pt-BR")}` : "Consulta concluída pela API da Granja Brasília.";
    status(num(payload.total.qtde_nfs) === 0 ? "Nenhuma NF encontrada para os filtros selecionados." : "Relatório atualizado.", "success");
  }
  function clearReport() {
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
