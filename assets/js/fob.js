/* Apresentação do Comparativo. Cálculos, totais e médias pertencem ao servidor. */
(() => {
  const $=id=>document.getElementById(id),channels=['Varejo','Atacado','Subprodutos'];
  // Ordem de apresentação: FaturamentoANeRA!AK860:AK889. Não altera agrupamentos/cálculos.
  const familyOrder=['ASA INTEIRA','COXINHA DA ASA','MEIO DA ASA','COXA SOBRECOXA','LEG QUARTER (CSCD)','SOBRECOXA','COXA','DORSO','PEITO','FILÉ DE PEITO','FRANGO PASSARINHO','MOELA','FÍGADO','CORAÇÃO','PESCOÇO','PÉS','SAMBIQUIRA','LINGUIÇA','FRANGO INTEIRO TEMPERADO','FRANGO INTEIRO','CARNE MECANICAMENTE SEPARADA (CMS)','DORSO E PELE A GRANEL','PELES (PEITO/COXAS)','SUBPRODUTOS'];
  const familyKey=value=>String(value).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toUpperCase();
  const familyRank=new Map(familyOrder.map((name,index)=>[familyKey(name),index]));
  const compareFamilies=(a,b)=>(familyRank.get(familyKey(a))??familyOrder.length)-(familyRank.get(familyKey(b))??familyOrder.length)||String(a).localeCompare(String(b),'pt-BR');
  const orderedFamilies=()=>[...payload.familias].sort((a,b)=>compareFamilies(a.familia,b.familia));
  const orderedGroups=()=>[...payload.grupos].sort((a,b)=>compareFamilies(a.familia,b.familia)||channels.indexOf(a.canal)-channels.indexOf(b.canal));
  const costs={frete:'Frete',comissao:'Comissão',adicional_comissao:'Adicional comissão',contrato:'Contrato',contrato_administracao:'Administração',logistica_reversa:'Logística reversa',pallet:'Pallet',descarga:'Descarga'};
  const number=new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2});
  const money=new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'});
  const unitMoney=new Intl.NumberFormat('pt-BR',{minimumFractionDigits:4,maximumFractionDigits:4});
  const exists=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const fmt=(v,kind='number')=>exists(v)?(kind==='money'?money:kind==='unit'?unitMoney:number).format(Number(v)):'—';
  const date=v=>v?.split('-').reverse().join('/')||'—';
  const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
  const badge=(text,cls='pending')=>node('span',text,'fob-badge '+cls);
  let options={},initializing=false,initialized=false,payload=null,applied=null,mode='matrix',summaryController,summarySeq=0;
  const filters=new FilterController({fields:[{id:'fob-filter-unidade',apiKey:'unidade',multi:true,search:true},{id:'fob-filter-familia',apiKey:'familia',multi:true,search:true},{id:'fob-filter-canal',apiKey:'canal',multi:true,search:false}],includeDependentRefresh:false,optionsProvider:async()=>options,onChange:()=>status('Filtros alterados. Consulte o comparativo para atualizar.')});
  const state=new ReportState('comparativo-fob');
  filters.register();
  state.bind({form:'fob-filters',filters,dates:{data_inicio:'fob-inicio',data_fim:'fob-fim'}});
  mode=state.get('mode')==='costs'?'costs':'matrix';
  $('fob-reference').checked=state.get('reference')===true;
  document.querySelectorAll('[data-fob-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.fobMode===mode)));
  for(const key of ['unidade','familia','canal'])$('fob-filter-'+key).querySelector('button').setAttribute('aria-labelledby',{'unidade':'fob-unit-label','familia':'fob-family-label','canal':'fob-channel-label'}[key]);
  document.addEventListener('keydown',event=>{if(event.key==='Escape')filters.closeAll();});
  function status(text,error=false){$('fob-status').textContent=text;$('fob-status').className='status '+(error?'error':'info');}
  function referenceVisible(){return $('fob-reference').checked;}
  function secondary(parent,text){parent.append(node('small',text,'fob-secondary'));}
  function openButton(parent,text,scope){const b=node('button',text,'fob-data-button');b.type='button';b.addEventListener('click',()=>openItems(scope));parent.append(b);return b;}
  function renderCards(){
    const frag=document.createDocumentFragment();
    for(const channel of payload.canais){
      const card=node('article',undefined,'fob-card'),heading=node('div',undefined,'fob-card-title');
      heading.append(node('h3',channel.canal),badge(channel.pendentes?`${channel.pendentes} pendentes`:channel.itens?'Calculado':'Sem movimento',channel.pendentes?'pending':''));
      card.append(heading,node('strong',`${fmt(channel.peso)} kg`));
      card.append(node('p',channel.valor_fob===null?'FOB em aberto':`FOB ${fmt(channel.valor_fob,'money')}`));
      if(channel.pendentes)card.append(node('p',`Parcial concluído: ${fmt(channel.valor_fob_parcial,'money')}`));
      else card.append(node('p',`PM FOB: ${fmt(channel.pm_fob_kg,'unit')} R$/kg`));
      if(channel.provisorios)card.append(badge(`${channel.provisorios} item provisório`,'provisional'));
      if(referenceVisible()){
        card.append(node('p',`Excel: ${fmt(channel.peso_excel)} kg · ${fmt(channel.valor_fob_excel,'money')}`));
        card.append(node('p',`Diferença de peso: ${fmt(channel.diferenca_peso)} kg · FOB: ${channel.valor_fob===null?'aguarda pendências':fmt(channel.diferenca_fob,'money')}`));
      }
      const action=node('button','Investigar itens →');action.type='button';action.addEventListener('click',()=>openItems({canal:channel.canal}));card.append(action);frag.append(card);
    }
    $('fob-cards').replaceChildren(frag);
  }
  function matrixValues(tr,group,scope,total=false){
    for(const [key,kind] of [['peso','number'],['valor_fob','money'],['pm_fob_kg','unit'],['pendentes','number']]){
      const td=node('td',undefined,total?'fob-total-cell':'');
      if(!group){td.textContent='—';tr.append(td);continue;}
      const pending=group.pendentes&&['pm_fob_kg','valor_fob'].includes(key);
      const b=openButton(td,pending?'Pendente':fmt(group[key],kind),scope);
      if(pending)b.append(document.createTextNode(' · '+group.pendentes));
      if(referenceVisible()&&key==='valor_fob')secondary(td,'Excel '+fmt(group.valor_fob_excel,'money'));
      if(referenceVisible()&&key==='pm_fob_kg')secondary(td,'Excel '+fmt(group.pm_fob_excel,'unit'));
      if(key==='valor_fob'&&group.provisorios)secondary(td,`${group.provisorios} provisório`);
      tr.append(td);
    }
  }
  function renderMatrix(){
    const top=node('tr'),bottom=node('tr'),label=node('th','Família');label.rowSpan=2;label.scope='col';top.append(label);
    for(const channel of [...channels,'Total']){
      const th=node('th',channel);th.colSpan=4;th.scope='colgroup';top.append(th);
      for(const text of ['Peso (kg)','Faturamento FOB','PM FOB (R$/kg)','Pendências'])bottom.append(node('th',text));
    }
    $('fob-table').tHead.replaceChildren(top,bottom);
    const body=document.createDocumentFragment();
    for(const family of orderedFamilies()){
      const tr=node('tr'),th=node('th',undefined,'fob-family');th.scope='row';openButton(th,family.familia,{familia:family.familia});tr.append(th);
      for(const channel of channels)matrixValues(tr,payload.grupos.find(g=>g.familia===family.familia&&g.canal===channel),{familia:family.familia,canal:channel});
      matrixValues(tr,family,{familia:family.familia},true);body.append(tr);
    }
    if(!payload.familias.length){const tr=node('tr'),td=node('td','Nenhum item encontrado para os filtros.','empty');td.colSpan=17;tr.append(td);body.append(tr);}
    $('fob-table').tBodies[0].replaceChildren(body);
    const total=node('tr');total.append(node('th','Total','fob-family'));
    for(const channel of channels)matrixValues(total,payload.canais.find(g=>g.canal===channel),{canal:channel});
    matrixValues(total,payload.total,{},true);$('fob-table').tFoot.replaceChildren(total);
  }
  function renderCosts(){
    const head=node('tr');
    for(const label of ['Família','Canal','Peso (kg)','Praticado (R$/kg)',...Object.values(costs).map(n=>n+' /kg'),'PM FOB (R$/kg)','Valor FOB','Pendências'])head.append(node('th',label));
    $('fob-table').tHead.replaceChildren(head);
    const body=document.createDocumentFragment();
    function row(group,total=false){
      const tr=node('tr'),th=node('th',undefined,'fob-family');openButton(th,total?'Total':group.familia,total?{}:{familia:group.familia,canal:group.canal});tr.append(th,node('td',group.canal||'Todos'),node('td',fmt(group.peso)),node('td',fmt(group.preco_praticado_kg,'unit')));
      for(const key of Object.keys(costs)){const c=group.componentes[key];tr.append(node('td',c.pendentes?'Pendente':fmt(c.media_kg,'unit')));}
      tr.append(node('td',group.pendentes?'Pendente':fmt(group.pm_fob_kg,'unit')),node('td',group.pendentes?'Pendente':fmt(group.valor_fob,'money')),node('td',fmt(group.pendentes)));return tr;
    }
    for(const group of orderedGroups())body.append(row(group));
    if(!payload.grupos.length){const tr=node('tr'),td=node('td','Nenhum item encontrado.','empty');td.colSpan=15;tr.append(td);body.append(tr);}
    $('fob-table').tBodies[0].replaceChildren(body);$('fob-table').tFoot.replaceChildren(row(payload.total,true));
  }
  function render(){
    renderCards();if(mode==='matrix')renderMatrix();else renderCosts();
    const total=payload.total,context=payload.contexto;
    const notices=[];
    if(total.pendentes)notices.push(`${total.pendentes} itens aguardam dados: ${fmt(total.peso_pendente)} kg. O FOB total permanece em aberto.`);
    if(total.ausentes)notices.push(`${total.ausentes} itens da referência não foram encontrados na origem; o peso apresentado está incompleto.`);
    if(total.provisorios)notices.push(`NF 806684: ${total.provisorios} item provisório do Excel. Conciliação: ${context.consulta_nf_806684.replaceAll('_',' ')}.`);
    if(total.divergencias)notices.push(`${total.divergencias} itens com diferença de entrada ou origem em relação ao Excel. Esse aviso pode coincidir com uma pendência. Abra “Ver cálculo” nos itens para comparar os valores.`);
    $('fob-alert').textContent=notices.join(' ');$('fob-alert').hidden=!notices.length;
    $('fob-period').textContent=`${date(context.data_inicio)} a ${date(context.data_fim)}`;
    $('fob-source').textContent='PostgreSQL · Cadastros iniciais do Excel · Sem arredondamento intermediário';
    $('fob-count').textContent=`${fmt(total.itens)} itens · ${fmt(context.linhas_fora_perimetro)} fora do perímetro na base de referência`;
    $('fob-export').disabled=!payload.grupos.length;
  }
  async function query(restored=null){
    const params=restored||state.current();
    const start=params.data_inicio,end=params.data_fim;
    if(!start||!end||start>end){status('Informe um período válido.',true);return;}
    summaryController?.abort();summaryController=new AbortController();const own=++summarySeq;
    state.saveDraft();filters.closeAll();
    status('Consultando preços, despesas e pendências…');$('view-comparativo-fob').setAttribute('aria-busy','true');$('fob-export').disabled=true;
    try{
      const result=await apiGet(APP_CONFIG.fob.resumo,params,{signal:summaryController.signal});
      if(own!==summarySeq)return;
      if(!Array.isArray(result.grupos)||!Array.isArray(result.familias)||!result.total)throw new Error('Resposta do comparativo inválida.');
      payload=result;applied=structuredClone(params);state.save({applied});render();status('Comparativo atualizado. Os itens pendentes permanecem em aberto.'+(!state.matchesDraft(params)?' Há filtros alterados; consulte para aplicá-los.':''));
    }catch(error){
      if(error.name==='AbortError'||own!==summarySeq)return;
      payload=null;applied=null;$('fob-cards').replaceChildren();$('fob-alert').hidden=true;
      const tr=node('tr'),td=node('td','Consulta indisponível. Confira a mensagem acima.','empty');td.colSpan=17;tr.append(td);$('fob-table').tBodies[0].replaceChildren(tr);$('fob-table').tFoot.replaceChildren();$('fob-period').textContent='—';$('fob-count').textContent='—';status(error.message,true);
    }finally{if(own===summarySeq)$('view-comparativo-fob').setAttribute('aria-busy','false');}
  }
  async function initialize(){
    if(initializing||initialized)return;initializing=true;
    try{
      status('Carregando filtros do Comparativo FOB…');options=await apiGet(APP_CONFIG.fob.filtros);
      options.familia=[...(options.familia||[])].sort(compareFamilies);
      await filters.loadOptions({preserve:false});
      const bounds=options.periodo_disponivel;
      for(const id of ['fob-inicio','fob-fim']){$(id).min=bounds.data_inicio;$(id).max=bounds.data_fim;}
      state.restore(bounds);initialized=true;await query(state.applied());
    }catch(error){status(error.message,true);}finally{initializing=false;}
  }
  $('fob-filters').addEventListener('submit',event=>{event.preventDefault();if(initialized)query();else initialize();});
  for(const id of ['fob-inicio','fob-fim'])$(id).addEventListener('change',()=>status('Período alterado. Consulte para atualizar.'));
  $('fob-reference').addEventListener('change',()=>{state.save({reference:referenceVisible()});if(payload)render();});
  document.querySelectorAll('[data-fob-mode]').forEach(button=>button.addEventListener('click',()=>{mode=button.dataset.fobMode;state.save({mode});document.querySelectorAll('[data-fob-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));if(payload)render();}));

  // Detalhamento auditável por item, na mesma aplicação.
  const dialog=node('dialog',undefined,'fob-dialog');dialog.setAttribute('aria-labelledby','fob-items-title');
  dialog.innerHTML=`<div class="fob-dialog-shell"><header class="fob-dialog-header"><div><span class="eyebrow">FORMAÇÃO DO FOB POR ITEM</span><h2 id="fob-items-title"></h2><p id="fob-items-context"></p></div><button id="fob-items-close" type="button">← Voltar ao comparativo</button></header><div class="fob-dialog-tools"><label><input id="fob-items-pending" type="checkbox">Somente pendentes</label><form id="fob-items-search"><input id="fob-items-query" type="search" maxlength="200" placeholder="NF, produto ou cliente" aria-label="Buscar itens"><button>Buscar</button></form><button type="button" id="fob-items-export">Exportar itens CSV</button></div><p id="fob-items-status" role="status" aria-live="polite"></p><div class="fob-items-scroll" tabindex="0" aria-label="Itens e componentes do FOB"><table><thead id="fob-items-head"></thead><tbody id="fob-items-body"></tbody></table></div><footer class="fob-dialog-footer"><button type="button" id="fob-items-prev">← Anterior</button><span id="fob-items-page"></span><button type="button" id="fob-items-next">Próxima →</button></footer></div>`;
  document.body.append(dialog);
  const itemColumns=[['data','Data'],['unidade_documento','Unidade'],['nota_numero','NF'],['cliente','Cliente'],['produto','Produto'],['familia','Família'],['canal','Canal'],['peso','Peso'],['preco_praticado_kg','Praticado/kg'],...Object.entries(costs).map(([k,v])=>[k+'_kg',v+'/kg']),['preco_fob_kg','FOB/kg'],['valor_fob','Valor FOB']];
  let detail=null,detailPayload=null,detailController,exportController,detailSeq=0,detailLoaded=false,exporting=false;
  function detailParams(page=detail.pagina,size=50){return {...detail.base,familia:detail.familia?[detail.familia]:detail.base.familia,canal:detail.canal?[detail.canal]:detail.base.canal,pendentes:$('fob-items-pending').checked?'1':'0',busca:detail.busca,pagina:page,por_pagina:size,ordenar_por:detail.sort,ordem:detail.direction};}
  function closeItems(){detailController?.abort();exportController?.abort();detailSeq++;exporting=false;if(dialog.open)dialog.close();}
  function openItems(scope){
    if(!applied)return;
    detail={...scope,base:structuredClone(applied),pagina:1,busca:'',sort:'nota_numero',direction:'asc'};
    $('fob-items-title').textContent=[scope.familia,scope.canal].filter(Boolean).join(' · ')||'Todos os itens do comparativo';
    $('fob-items-context').textContent=`${date(applied.data_inicio)} a ${date(applied.data_fim)} · Valores e fontes por item`;
    $('fob-items-pending').checked=false;$('fob-items-query').value='';dialog.showModal();loadItems();
  }
  function auditRow(item,cols){
    const tr=node('tr',undefined,'fob-item-audit'),td=node('td');td.colSpan=cols;
    const grid=node('div',undefined,'fob-audit-grid');
    const source=node('div',undefined,'fob-audit-part');source.append(node('strong','Origem e comparação'),node('p',item.origem_registro||'Registro ausente na origem'),node('p',item.origem_excel||''),node('p',`Referência Excel: ${fmt(item.valor_fob_excel,'money')}`));
    source.append(node('p',item.produto_descricao||''),node('p',`CFOP: ${item.identificacao?.cfop||'—'} · Tipo de frete: ${item.dados_entrada?.frete??'—'}`));
    source.append(node('code',`${item.formula_preco_fob||'preco_praticado - soma(componentes/kg)'}\nPraticado/kg: ${item.preco_praticado_kg??'pendente'}\nFOB/kg: ${item.preco_fob_kg??'pendente'}\n${item.formula_valor_fob||'peso * preco_fob_kg'}\nPeso: ${item.peso??'ausente'} · Valor FOB: ${item.valor_fob??'pendente'}`));
    if(item.provisorio)source.append(node('p','Origem provisória: NF ainda não conciliada.'));
    if(item.pendencias?.length)source.append(node('p','Pendências: '+item.pendencias.join(', ')));
    for(const [field,diff] of Object.entries(item.divergencias_entrada||{}))source.append(node('p',`${field}: origem ${diff.origem??'ausente'} · Excel ${diff.excel??'ausente'}`));
    grid.append(source);
    for(const [key,c] of Object.entries(item.componentes||{})){
      const part=node('div',undefined,'fob-audit-part');part.append(node('strong',`${costs[key]||key}: ${c.value===null?'Pendente':fmt(c.value,'unit')+' R$/kg'}`),node('p',c.origin),node('p','Estado: '+c.status),node('code',c.formula||'Valor de cadastro'));
      if(c.inputs)part.append(node('p',Object.entries(c.inputs).map(([k,v])=>`${k}: ${v}`).join(' · ')));grid.append(part);
    }
    td.append(grid);tr.append(td);return tr;
  }
  function renderItems(){
    const head=node('tr');
    for(const [key,label] of itemColumns){const th=node('th'),button=node('button',label+(detail.sort===key?(detail.direction==='asc'?' ↑':' ↓'):' ↕'),'fob-sort');button.type='button';th.scope='col';th.setAttribute('aria-sort',detail.sort===key?(detail.direction==='asc'?'ascending':'descending'):'none');button.addEventListener('click',()=>{detail.direction=detail.sort===key&&detail.direction==='asc'?'desc':'asc';detail.sort=key;detail.pagina=1;loadItems();});th.append(button);head.append(th);}
    head.append(node('th','Situação'),node('th','Investigar'));$('fob-items-head').replaceChildren(head);
    const body=document.createDocumentFragment();
    for(const item of detailPayload.linhas){
      const tr=node('tr');
      for(const [key] of itemColumns){let value=item[key]??item.identificacao?.[key];const text=key==='data'?date(value):['produto','cliente','unidade_documento','nota_numero','familia','canal'].includes(key)?String(value??'—'):value===null||value===undefined?(key.endsWith('_kg')||key==='valor_fob'?'Pendente':'—'):fmt(value,key==='valor_fob'?'money':key.endsWith('_kg')?'unit':'number');tr.append(node('td',text));}
      const state=node('td');state.append(badge(item.valor_fob===null?'Pendente':'Calculado',item.valor_fob===null?'pending':''));if(item.provisorio)state.append(badge('Provisório','provisional'));tr.append(state);
      if(Object.keys(item.divergencias_entrada||{}).length)state.append(badge('Diferença de entrada','review'));
      const action=node('td'),button=node('button','Ver cálculo');button.type='button';button.setAttribute('aria-expanded','false');
      button.addEventListener('click',()=>{const expanded=button.getAttribute('aria-expanded')==='true';button.setAttribute('aria-expanded',String(!expanded));button.textContent=expanded?'Ver cálculo':'Fechar cálculo';if(expanded)tr.nextElementSibling?.remove();else tr.after(auditRow(item,itemColumns.length+2));});action.append(button);tr.append(action);body.append(tr);
    }
    if(!detailPayload.linhas.length){const tr=node('tr'),td=node('td','Nenhum item para os filtros selecionados.','empty');td.colSpan=itemColumns.length+2;tr.append(td);body.append(tr);}
    $('fob-items-body').replaceChildren(body);
  }
  function itemPagination(){
    const pages=Math.max(1,Math.ceil((detailPayload?.total_registros||0)/50));
    $('fob-items-prev').disabled=!detailLoaded||detail.pagina<=1;$('fob-items-next').disabled=!detailLoaded||detail.pagina>=pages;$('fob-items-export').disabled=!detailLoaded||!detailPayload?.total_registros;
    $('fob-items-page').textContent=detailLoaded?`Página ${detail.pagina} de ${pages} · ${fmt(detailPayload.total_registros)} itens`:'';
  }
  async function loadItems(){
    detailController?.abort();exportController?.abort();exporting=false;$('fob-items-export').textContent='Exportar itens CSV';detailController=new AbortController();const own=++detailSeq;
    detailLoaded=false;itemPagination();$('fob-items-body').replaceChildren();$('fob-items-status').textContent='Carregando itens e despesas…';
    try{
      const result=await apiGet(APP_CONFIG.fob.detalhes,detailParams(),{signal:detailController.signal});if(own!==detailSeq)return;
      if(!Array.isArray(result.linhas)||!Number.isSafeInteger(result.total_registros))throw new Error('Resposta de itens inválida.');detailPayload=result;
      const pages=Math.max(1,Math.ceil(result.total_registros/50));if(detail.pagina>pages){detail.pagina=pages;return loadItems();}
      renderItems();detailLoaded=true;itemPagination();$('fob-items-status').textContent=`${fmt(result.total.peso)} kg · ${result.total.pendentes} pendentes · Abra “Ver cálculo” para conferir as origens.`;
    }catch(error){if(error.name!=='AbortError'&&own===detailSeq)$('fob-items-status').textContent=error.message;}
  }
  function csv(value){let text=value===null||value===undefined?'':String(value);if(/^\s*[=+@-]/.test(text)&&!/^-[0-9]+(?:\.[0-9]+)?$/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"';}
  function download(lines,name){const url=URL.createObjectURL(new Blob(['\uFEFF',lines.map(r=>r.map(csv).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=node('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  $('fob-export').addEventListener('click',()=>{
    if(!payload)return;
    const headers=['Família','Canal','Peso kg','Praticado kg',...Object.values(costs).map(c=>c+' kg'),'PM FOB kg','Valor FOB','Parcial calculado','Pendências','Provisórios','Referência Excel'];
    const rows=orderedGroups().map(g=>[g.familia,g.canal,g.peso,g.preco_praticado_kg,...Object.keys(costs).map(k=>g.componentes[k].media_kg),g.pm_fob_kg,g.valor_fob,g.valor_fob_parcial,g.pendentes,g.provisorios,g.valor_fob_excel]);
    rows.push(['Total','',payload.total.peso,payload.total.preco_praticado_kg,...Object.keys(costs).map(k=>payload.total.componentes[k].media_kg),payload.total.pm_fob_kg,payload.total.valor_fob,payload.total.valor_fob_parcial,payload.total.pendentes,payload.total.provisorios,payload.total.valor_fob_excel]);
    download([headers,...rows],`comparativo-fob-${applied.data_inicio}-${applied.data_fim}.csv`);
  });
  $('fob-items-export').addEventListener('click',async()=>{
    if(exporting){exportController.abort();exporting=false;$('fob-items-export').textContent='Exportar itens CSV';$('fob-items-status').textContent='Exportação cancelada.';return;}
    if(!detailLoaded)return;exporting=true;exportController=new AbortController();const signal=exportController.signal,own=detailSeq;$('fob-items-export').textContent='Cancelar exportação';
    const lines=[[...itemColumns.map(c=>c[1]),'Estado','Provisório','Origem','Referência Excel']];
    try{
      let count=null;
      for(let page=1;;page++){
        const data=await apiGet(APP_CONFIG.fob.detalhes,detailParams(page,500),{signal});if(own!==detailSeq||signal.aborted)return;
        if(count===null)count=data.total_registros;if(count!==data.total_registros)throw new Error('A fonte mudou durante a exportação. Repita a consulta.');
        for(const item of data.linhas)lines.push([...itemColumns.map(([k])=>item[k]??item.identificacao?.[k]??null),item.status,item.provisorio?'Sim':'Não',item.origem_registro,item.valor_fob_excel]);
        $('fob-items-status').textContent=`Exportando ${lines.length-1} de ${count} itens…`;
        if(page*500>=count)break;if(!data.linhas.length)throw new Error('Página incompleta na exportação.');
      }
      if(lines.length-1!==count)throw new Error('Quantidade de itens alterada. Repita a consulta.');download(lines,`itens-fob-${detail.base.data_inicio}-${detail.base.data_fim}.csv`);$('fob-items-status').textContent=`${count} itens exportados.`;
    }catch(error){if(error.name!=='AbortError'&&own===detailSeq)$('fob-items-status').textContent=error.message;}
    finally{if(own===detailSeq&&exportController.signal===signal){exporting=false;$('fob-items-export').textContent='Exportar itens CSV';}}
  });
  $('fob-items-close').addEventListener('click',closeItems);dialog.addEventListener('cancel',event=>{event.preventDefault();closeItems();});
  $('fob-items-pending').addEventListener('change',()=>{detail.pagina=1;loadItems();});
  $('fob-items-search').addEventListener('submit',event=>{event.preventDefault();detail.busca=$('fob-items-query').value.trim();detail.pagina=1;loadItems();});
  $('fob-items-prev').addEventListener('click',()=>{detail.pagina--;loadItems();});$('fob-items-next').addEventListener('click',()=>{detail.pagina++;loadItems();});
  window.addEventListener('pagehide',closeItems);
  initialize();
})();
