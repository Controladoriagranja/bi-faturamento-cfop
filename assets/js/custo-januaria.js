/* Cadastro mensal independente do formulário por NF. Sem cálculo financeiro do FOB. */
(() => {
  const $=id=>document.getElementById(id), endpoint=APP_CONFIG.custosJanuaria;
  const formatter=new Intl.NumberFormat('pt-BR',{maximumFractionDigits:10,minimumFractionDigits:4});
  let loaded=null,busy=false,locked=true,baseline='',dirty=false,version=0,page=1,next=false,leaveApproved=false;
  const node=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
  const message=(text,error=false)=>{$('monthly-message').textContent=text;$('monthly-message').className='status '+(error?'error':'info');};
  const date=value=>value?new Date(value).toLocaleString('pt-BR'):'—';
  const decimal=text=>{
    text=String(text).trim();
    if(text.includes(',')){
      if(!/^(?:\d+|\d{1,3}(?:\.\d{3})+),\d{1,10}$/.test(text))throw new Error('Informe R$/kg com até 10 casas decimais.');
      text=text.replaceAll('.','').replace(',','.');
    }
    if(!/^\d+(?:\.\d{1,10})?$/.test(text))throw new Error('Informe zero ou um custo positivo, com até 10 casas decimais.');
    const [whole,fraction='']=text.split('.');
    return whole.replace(/^0+(?=\d)/,'')+(fraction?'.'+fraction:'');
  };
  function update(){
    const session=Boolean(getPortalToken());
    $('monthly-query').disabled=busy;$('monthly-competence').disabled=busy;
    $('monthly-value').disabled=busy||locked||!session;
    let valid=false;try{decimal($('monthly-value').value);valid=true;}catch(_){}
    $('monthly-save').disabled=busy||locked||!session||!dirty||!valid;
    $('monthly-save').textContent=busy?'Aguarde…':'Salvar custo';
    $('monthly-prev').disabled=busy||!loaded||page<=1;$('monthly-next').disabled=busy||!loaded||!next;
    $('monthly-dirty').textContent=dirty?'Alteração não salva. Consultar outra competência substituirá o valor digitado.':'Nenhuma alteração.';
    $('monthly-history').querySelectorAll('button').forEach(b=>b.disabled=busy);
  }
  function guard(){return !busy&&(!dirty||confirm('Existe um custo mensal não salvo. Deseja descartar o valor digitado e continuar?'));}
  function validMonth(value){return /^\d{4}-(0[1-9]|1[0-2])$/.test(value)&&value>='2000-01'&&value<='2100-12';}
  function render(data,month,target){
    if(data.competencia!==month||!Array.isArray(data.custos)||data.pagina!==target||typeof data.tem_proxima!=='boolean'||!data.custo_aplicado)throw new Error('Resposta do cadastro mensal inválida.');
    const own=data.custo_proprio;
    if(own&&(!Number.isInteger(own.versao)||own.versao<1||String(own.competencia).slice(0,7)!==month))throw new Error('Versão/competência inválida no cadastro mensal.');
    const effective=data.custo_aplicado;
    if(!['mensal','mensal_provisorio','pendente_custo_mensal'].includes(effective.status))throw new Error('Situação de custo mensal inválida.');
    if(own)decimal(own.custo_kg);
    if(effective.custo_kg!==null)decimal(effective.custo_kg);
    loaded=month;page=target;next=data.tem_proxima;version=own?.versao??0;
    baseline=own?String(own.custo_kg).replace('.',','):'';
    $('monthly-value').value=baseline;dirty=false;locked=false;
    $('monthly-competence').value=month;
    $('monthly-effective').textContent=effective.custo_kg===null?'Pendente: não há custo próprio nem custo de outubro/2026 cadastrado.':
      effective.status==='mensal_provisorio'?`Provisório herdado de outubro/2026: ${formatter.format(Number(effective.custo_kg))} R$/kg. Cadastre o custo próprio para substituí-lo.`:
      `Custo próprio de ${month.slice(5)}/${month.slice(0,4)}: ${formatter.format(Number(effective.custo_kg))} R$/kg.`;
    $('monthly-effective').dataset.kind=effective.status;
    $('monthly-audit').textContent=own?`Versão ${own.versao} · Criado por ${own.criado_por} em ${date(own.criado_em)} · Alterado por ${own.atualizado_por} em ${date(own.atualizado_em)}`:'Competência sem cadastro próprio. Ao salvar, será criada com versão inicial.';
    const body=document.createDocumentFragment();
    for(const row of data.custos){
      const tr=node('tr'),competencia=String(row.competencia).slice(0,7);
      tr.append(node('td',competencia.slice(5)+'/'+competencia.slice(0,4)),node('td',formatter.format(Number(row.custo_kg))),
        node('td',`${row.criado_por} · ${date(row.criado_em)}`),node('td',`${row.atualizado_por} · ${date(row.atualizado_em)}`),node('td',String(row.versao)));
      const cell=node('td'),button=node('button','Consultar / corrigir');button.type='button';button.addEventListener('click',()=>query(competencia));cell.append(button);tr.append(cell);body.append(tr);
    }
    if(!data.custos.length){const tr=node('tr'),td=node('td','Nenhuma competência cadastrada.');td.colSpan=6;td.className='empty';tr.append(td);body.append(tr);}
    $('monthly-history').replaceChildren(body);$('monthly-page').textContent='Página '+page;
  }
  async function read(month,target){
    if(!getPortalToken())throw freightApiError(401);
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
    try{return await apiGet(endpoint,{competencia:month,pagina:target,tamanho:20},{signal:controller.signal});}
    catch(error){if(error.name==='AbortError')throw new Error('Tempo de consulta excedido. Consulte novamente.');throw error;}
    finally{clearTimeout(timer);}
  }
  async function query(month=$('monthly-competence').value,target=1){
    if(!validMonth(month)){message('Informe uma competência entre 01/2000 e 12/2100.',true);return;}
    if(!guard())return;
    busy=true;update();message('Consultando custo e competências cadastradas…');
    try{render(await read(month,target),month,target);message('Cadastro atualizado. O custo próprio tem prioridade sobre a referência de outubro.');}
    catch(error){locked=true;message(error.message+' Consulte novamente antes de salvar.',true);}
    finally{busy=false;update();}
  }
  async function save(event){
    event.preventDefault();if(busy||locked||!dirty)return;
    if($('monthly-competence').value!==loaded){message('Consulte a competência selecionada antes de salvar.',true);return;}
    let value;try{value=decimal($('monthly-value').value);}catch(error){message(error.message,true);return;}
    if(!getPortalToken()){locked=true;message(freightApiError(401).message,true);update();return;}
    busy=true;update();message('Salvando custo mensal…');
    try{
      const result=await apiPut(endpoint,{competencia:loaded,custo_kg:value,versao:version});
      if(result?.ok!==true||!result.custo||String(result.custo.competencia).slice(0,7)!==loaded||result.custo.versao!==version+1){
        const error=new Error('Resposta de gravação não confirmada. Consulte a competência antes de reenviar.');error.uncertain=true;throw error;
      }
      dirty=false;locked=true;
      try{render(await read(loaded,page),loaded,page);message('Custo mensal salvo com sucesso. A API atualizou o valor e a versão.');}
      catch(error){message('Custo salvo, mas a lista não pôde ser atualizada. '+error.message+' Consulte novamente.',true);}
    }catch(error){
      if(error.uncertain||[401,403,409].includes(error.status))locked=true;
      message(error.message+(locked?' Nova consulta obrigatória antes de salvar.':''),true);
    }finally{busy=false;update();}
  }
  $('monthly-query').addEventListener('click',()=>query());$('monthly-form').addEventListener('submit',save);
  $('monthly-value').addEventListener('input',()=>{dirty=$('monthly-value').value!==baseline;update();});
  $('monthly-competence').addEventListener('change',()=>{locked=true;message('Competência alterada. Consulte antes de preencher.');update();});
  $('monthly-prev').addEventListener('click',()=>query(loaded,page-1));$('monthly-next').addEventListener('click',()=>query(loaded,page+1));
  document.querySelectorAll('[data-freight-panel]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelectorAll('[data-freight-panel]').forEach(b=>{const active=b===button;b.setAttribute('aria-pressed',String(active));$(b.dataset.freightPanel).hidden=!active;});
  }));
  document.addEventListener('click',event=>{
    const link=event.target.closest('a[href]');
    if(!link||event.defaultPrevented||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||link.target==='_blank'||link.href===location.href)return;
    if(!guard()){event.preventDefault();event.stopImmediatePropagation();}else leaveApproved=true;
  },true);
  window.addEventListener('beforeunload',event=>{if(!leaveApproved&&(dirty||busy)){event.preventDefault();event.returnValue='';}});
  window.addEventListener('pageshow',()=>{leaveApproved=false;update();});
  const now=new Date();$('monthly-competence').value=now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0');update();
})();
