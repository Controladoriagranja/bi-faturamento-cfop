/* Interface de frete manual. Identidade, peso, versão e cálculo final pertencem à API. */
(() => {
  if(APP_CONFIG.legacyFreightEditor===false){location.replace(new URL('custos-pendencias.html',location.href));return;}
  const $=id=>document.getElementById(id);
  const endpoint=APP_CONFIG.fretesManuais, storageKey='granja-faturamento:fretes:filtros:v1';
  const units=['10','111','180','102'], statuses=['PENDENTE','PREENCHIDO','REVISAR_IDENTIFICACAO','TODOS'];
  const labels={PENDENTE:'Pendente',PREENCHIDO:'Preenchido',REVISAR_IDENTIFICACAO:'Revisar identificação'};
  const money=new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'});
  const kg=new Intl.NumberFormat('pt-BR',{maximumFractionDigits:4});
  const rate=new Intl.NumberFormat('pt-BR',{minimumFractionDigits:4,maximumFractionDigits:6});
  let rows=[], applied=null, page=1, next=false, busy=false, mustReload=false, denied=false, leaveApproved=false;
  const drafts=new Map(), controls=new Map();
  const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
  const number=(value,formatter=kg)=>value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value))?formatter.format(Number(value)):'—';
  const identity=row=>JSON.stringify([row.empresa,row.unidade,row.serie,row.nf,row.ano_nf]);
  const editable=row=>['PENDENTE','PREENCHIDO'].includes(row.status_frete);
  const hasSession=()=>Boolean(getPortalToken());
  const message=(text,type='info')=>{const node=$('freight-message');node.textContent=text;node.className='status '+type;};

  // Conversão textual: nenhuma multiplicação em ponto flutuante para obter centavos.
  function amount(value){
    let text=String(value).trim();
    if(!text)throw new Error('Informe um valor. Campo vazio não equivale a zero.');
    if(text.includes(',')){
      if(!/^(?:\d+|\d{1,3}(?:\.\d{3})+),\d{1,2}$/.test(text))throw new Error('Use 150,00 ou 1.234,56, com até dois centavos.');
      text=text.replaceAll('.','').replace(',','.');
    }else if(/^\d{1,3}(?:\.\d{3})+$/.test(text))text=text.replaceAll('.','');
    else if(!/^\d+(?:\.\d{1,2})?$/.test(text))throw new Error('Informe um valor positivo ou zero, com até duas casas decimais.');
    const [whole,fraction='']=text.split('.');
    if(!/[1-9]/.test(whole+fraction))throw new Error('O total de frete por NF deve ser maior que zero, conforme a API.');
    if(whole.replace(/^0+/,'').length>16)throw new Error('O frete total aceita até 16 dígitos inteiros.');
    return whole.replace(/^0+(?=\d)/,'')+'.'+fraction.padEnd(2,'0');
  }
  function original(row){
    if(row.frete_manual_total===null||row.frete_manual_total===undefined)return '';
    // Valores do servidor já são decimais, não usam separador de milhar.
    const text=String(row.frete_manual_total);
    if(!/^\d+(?:\.\d{1,2})?$/.test(text))return text;
    const [whole,fraction='']=text.split('.');
    return whole.replace(/^0+(?=\d)/,'')+','+fraction.padEnd(2,'0');
  }
  function validRow(row){
    return row&&typeof row.empresa==='string'&&units.includes(row.unidade)&&
      typeof row.serie==='string'&&typeof row.nf==='string'&&row.nf.length>0&&
      Number.isInteger(row.ano_nf)&&Number.isInteger(row.versao)&&row.versao>=0&&
      (typeof row.peso_total_nf==='string'||typeof row.peso_total_nf==='number')&&
      Number.isFinite(Number(row.peso_total_nf));
  }
  function filters(){
    const empresa=$('freight-company').value,unidade=$('freight-unit').value;
    const ano_nf=Number($('freight-year').value),status=$('freight-status-filter').value,tamanho=Number($('freight-size').value);
    if(!empresa.trim()||empresa.length>100||!units.includes(unidade)||!Number.isInteger(ano_nf)||ano_nf<2000||ano_nf>2100||!statuses.includes(status)||!Number.isInteger(tamanho)||tamanho<1||tamanho>200)throw new Error('Informe empresa exata, unidade e ano válidos (2000–2100).');
    return {empresa,unidade,ano_nf,status,tamanho};
  }
  function storeFilters(){try{sessionStorage.setItem(storageKey,JSON.stringify(filters()));}catch(_){} }
  function markReload(text){mustReload=true;$('freight-reconcile').hidden=false;$('freight-reconcile-text').textContent=text;}
  function discardAllowed(){
    if(busy){message('Aguarde a operação em andamento antes de sair ou mudar a consulta.');return false;}
    return !drafts.size||window.confirm(mustReload?
      'Consultar novamente e substituir os valores digitados pelos valores atuais do servidor? Confira-os antes de editar e salvar novamente.':
      `Existem ${drafts.size} notas com alterações não salvas. Deseja descartá-las e continuar?`);
  }
  function updateState(){
    const invalid=[...drafts.values()].some(d=>d.error),count=drafts.size;
    $('freight-dirty-count').textContent=count?`${count} ${count===1?'nota alterada':'notas alteradas'}${invalid?' · confira os valores':''}`:'Nenhuma alteração';
    $('freight-save').textContent=busy?'Aguarde…':count?`Salvar alterações (${count})`:'Salvar alterações';
    $('freight-save').disabled=busy||mustReload||denied||!hasSession()||!count||count>100||invalid;
    $('freight-discard').disabled=busy||!count;
    $('freight-query').disabled=busy;
    $('freight-prev').disabled=busy||!applied||page<=1;
    $('freight-next').disabled=busy||!applied||!next||page>=1000;
    $('freight-filters').querySelectorAll('input,select').forEach(input=>input.disabled=busy);
    if(count>100)$('freight-save-hint').textContent='O limite é 100 notas por lote. Reverta as alterações excedentes antes de salvar.';
    else $('freight-save-hint').textContent='Até 100 notas por salvamento. O total por NF deve ser positivo; campo vazio não é zero.';
    for(const {input,reset} of controls.values()){
      input.disabled=busy||mustReload||denied||!hasSession();reset.disabled=busy;
    }
    $('freight-report').setAttribute('aria-busy',String(busy));
  }
  function updateInput(row){
    const key=identity(row),control=controls.get(key),draft=drafts.get(key);
    control.tr.classList.toggle('freight-changed',Boolean(draft));
    control.input.setAttribute('aria-invalid',String(Boolean(draft?.error)));
    control.error.textContent=draft?.error||'';control.reset.hidden=!draft;
    control.preview.textContent='';
    if(draft&&!draft.error){
      const weight=Number(row.peso_total_nf),preview=Number(draft.value)/weight;
      control.preview.textContent=weight>0&&Number.isFinite(preview)?`Prévia: ${rate.format(preview)} R$/kg`:'Sem prévia: peso inválido para rateio.';
    }
    updateState();
  }
  function change(row){
    const key=identity(row),input=controls.get(key).input,text=input.value;
    let value=null,error='';try{value=amount(text);}catch(e){error=e.message;}
    let baseline=null;try{if(original(row)!=='')baseline=amount(original(row));}catch(_){}
    if(text===original(row)||(!error&&value===baseline))drafts.delete(key);
    else drafts.set(key,{text,value,error});
    updateInput(row);
  }
  function timestamp(value){if(!value)return '—';const date=new Date(value);return Number.isNaN(date.getTime())?String(value):date.toLocaleString('pt-BR');}
  function render(){
    const body=document.createDocumentFragment();controls.clear();
    for(const row of rows){
      const tr=el('tr'),company=el('td',row.empresa);company.append(el('small','Unidade '+row.unidade,'freight-secondary'));
      tr.append(company,el('td',row.serie),el('td',row.nf),el('td',String(row.ano_nf)),el('td',number(row.quantidade_itens)),el('td',number(row.peso_total_nf)));
      const status=el('td'),badge=el('span',labels[row.status_frete]||'Situação não reconhecida','freight-badge '+(row.status_frete==='PREENCHIDO'?'filled':row.status_frete==='PENDENTE'?'':'review'));
      status.append(badge);tr.append(status,el('td',number(row.frete_manual_total,money)),el('td',number(row.frete_manual_kg,rate)),
        el('td',String(row.atualizado_por??row.criado_por??'—')),el('td',timestamp(row.atualizado_em??row.criado_em)));
      const field=el('td');
      if(editable(row)){
        const key=identity(row),input=el('input',undefined,'freight-input'),index=controls.size;
        input.type='text';input.inputMode='decimal';input.maxLength=40;input.autocomplete='off';input.spellcheck=false;
        input.setAttribute('aria-label',`Frete total da NF ${row.nf}, série ${row.serie}`);
        input.value=drafts.get(key)?.text??original(row);input.placeholder='0,00';
        const error=el('span',undefined,'freight-error'),preview=el('small',undefined,'freight-secondary'),reset=el('button','Reverter','freight-reset');
        error.id='freight-input-error-'+index;input.setAttribute('aria-describedby',error.id);reset.type='button';reset.hidden=!drafts.has(key);
        reset.setAttribute('aria-label',`Reverter alteração da NF ${row.nf}`);
        controls.set(key,{input,error,preview,reset,tr});
        input.addEventListener('input',()=>change(row));
        reset.addEventListener('click',()=>{input.value=original(row);drafts.delete(key);updateInput(row);});
        field.append(input,error,preview,reset);
      }else field.append(el('span',row.status_frete==='REVISAR_IDENTIFICACAO'?'Identificação inconsistente: corrigir na origem.':'Situação não permite edição.','freight-secondary'));
      tr.append(field);body.append(tr);
    }
    if(!rows.length){const tr=el('tr'),td=el('td','Nenhuma nota encontrada para os filtros desta página.','empty');td.colSpan=12;tr.append(td);body.append(tr);}
    $('freight-body').replaceChildren(body);
    for(const row of rows)if(controls.has(identity(row)))updateInput(row);
    $('freight-context').textContent=applied?`${applied.empresa} · Unidade ${applied.unidade} · Ano ${applied.ano_nf} · ${applied.status==='TODOS'?'Todos':labels[applied.status]}`:'Aguardando consulta';
    $('freight-page-label').textContent=applied?`Página ${page}${next?' · há mais notas':''}`:'—';
    localSearch();updateState();
  }
  function localSearch(){
    const term=$('freight-local-search').value.trim().toLocaleLowerCase('pt-BR');let visible=0;
    [...$('freight-body').rows].forEach((tr,index)=>{
      const row=rows[index];if(!row)return;
      const match=!term||[row.empresa,row.unidade,row.serie,row.nf,row.criado_por,row.atualizado_por].join(' ').toLocaleLowerCase('pt-BR').includes(term);
      tr.hidden=!match;if(match)visible++;
    });
    $('freight-count').textContent=applied?`${visible} de ${rows.length} notas nesta página`:'Nenhuma página carregada';
  }
  async function read(params,target){
    if(!hasSession())throw freightApiError(401);
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),30000);
    let response;
    try{response=await apiGet(endpoint,{...params,pagina:target},{signal:controller.signal});}
    catch(error){if(error.name==='AbortError')throw new Error('A consulta excedeu o tempo de espera. Consulte novamente.');throw error;}
    finally{clearTimeout(timeout);}
    if(!response||!Array.isArray(response.notas)||response.pagina!==target||typeof response.tem_proxima!=='boolean'||response.notas.length>params.tamanho||
      response.notas.some(row=>!validRow(row)||row.empresa!==params.empresa||row.unidade!==params.unidade||row.ano_nf!==params.ano_nf)||
      new Set(response.notas.map(identity)).size!==response.notas.length)throw new Error('Resposta de notas inconsistente. Confira o contrato da API antes de preencher.');
    return response;
  }
  function accept(response,params,target){
    rows=response.notas;applied={...params};page=target;next=response.tem_proxima;
    drafts.clear();mustReload=false;denied=false;$('freight-reconcile').hidden=true;
    $('freight-local-search').value='';render();
  }
  async function query(params,target=1){
    if(!discardAllowed())return;
    busy=true;updateState();message('Consultando notas…');
    try{
      const response=await read(params,target);accept(response,params,target);storeFilters();
      message(`${rows.length} notas carregadas. Informe o valor total das notas que deseja preencher.`);
    }catch(error){
      if(error.status===401||error.status===403||!hasSession())denied=true;
      markReload('A consulta não foi concluída; a tabela anterior, se houver, foi preservada.');message(error.message,'error');
    }finally{busy=false;updateState();}
  }
  async function save(){
    if(busy||mustReload||denied||!drafts.size||drafts.size>100||[...drafts.values()].some(d=>d.error))return;
    if(!hasSession()){denied=true;message(freightApiError(401).message,'error');updateState();return;}
    const changes=rows.filter(row=>drafts.has(identity(row)));
    const fretes=changes.map(row=>({empresa:row.empresa,unidade:row.unidade,serie:row.serie,nf:row.nf,
      ano_nf:row.ano_nf,frete_total:drafts.get(identity(row)).value,peso_total_nf:row.peso_total_nf,versao:row.versao}));
    busy=true;updateState();message(`Salvando ${fretes.length} notas em um único lote…`);
    try{
      const result=await apiPut(endpoint,{fretes});
      const expected=new Set(fretes.map(identity));
      if(result?.ok!==true||!Array.isArray(result.fretes)||result.fretes.length!==fretes.length||
        new Set(result.fretes.map(identity)).size!==expected.size||result.fretes.some(row=>!expected.has(identity(row)))){
        const error=new Error('A API não confirmou o lote completo. Consulte novamente antes de tentar salvar.');error.uncertain=true;throw error;
      }
      // O lote foi confirmado, mas a próxima edição precisa da versão/peso atuais.
      drafts.clear();markReload('O lote foi salvo; atualizando os valores e versões retornados pelo servidor.');
      message('Fretes salvos. Atualizando a página…','success');
      try{
        const response=await read(applied,page);accept(response,applied,page);
        message(`${fretes.length} ${fretes.length===1?'nota salva':'notas salvas'} com sucesso. Valores e versões atualizados pela API.`,'success');
      }catch(error){
        markReload('O lote foi confirmado como salvo, mas não foi possível atualizar a lista.');
        if(error.status===401||error.status===403)denied=true;
        message(`Fretes salvos. ${error.message} Consulte novamente para continuar.`,'error');
      }
    }catch(error){
      if(error.status===409||error.uncertain)markReload(error.status===409?'Conflito de versão ou peso. Revise a nota após uma nova consulta.':'Resultado do salvamento incerto. Consulte os valores no servidor antes de qualquer nova tentativa.');
      if(error.status===401||error.status===403)denied=true;
      message(error.message,'error');
    }finally{busy=false;updateState();}
  }
  $('freight-filters').addEventListener('submit',event=>{event.preventDefault();try{query(filters());}catch(error){message(error.message,'error');}});
  $('freight-filters').addEventListener('change',()=>{storeFilters();if(applied)message('Filtros alterados. A tabela mantém a consulta anterior até clicar em Consultar notas.');});
  $('freight-local-search').addEventListener('input',localSearch);
  $('freight-prev').addEventListener('click',()=>query(applied,page-1));
  $('freight-next').addEventListener('click',()=>query(applied,page+1));
  $('freight-save').addEventListener('click',save);
  $('freight-discard').addEventListener('click',()=>{if(discardAllowed()){drafts.clear();render();message(mustReload?'Alterações descartadas. Consulte novamente para continuar.':'Alterações descartadas.');}});
  window.addEventListener('beforeunload',event=>{if(!leaveApproved&&(drafts.size||busy)){event.preventDefault();event.returnValue='';}});
  document.addEventListener('click',event=>{
    const link=event.target.closest('a[href]');
    if(!link||event.defaultPrevented||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||link.target==='_blank'||link.href===location.href)return;
    if(!discardAllowed()){event.preventDefault();event.stopImmediatePropagation();}else leaveApproved=true;
  },true);
  window.addEventListener('pageshow',()=>{leaveApproved=false;updateState();});
  $('freight-year').value=String(new Date().getFullYear());
  try{
    const stored=JSON.parse(sessionStorage.getItem(storageKey)||'null');
    if(stored&&typeof stored.empresa==='string'&&units.includes(stored.unidade)){
      $('freight-company').value=stored.empresa;$('freight-unit').value=stored.unidade;
      if(Number.isInteger(stored.ano_nf)&&stored.ano_nf>0&&stored.ano_nf<=9999)$('freight-year').value=String(stored.ano_nf);
      if(statuses.includes(stored.status))$('freight-status-filter').value=stored.status;
      if([25,50,100,200].includes(stored.tamanho))$('freight-size').value=String(stored.tamanho);
    }
  }catch(_){}
  updateState();if(!hasSession()){denied=true;message(freightApiError(401).message,'error');updateState();}
})();
