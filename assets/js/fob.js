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
  function referenceVisible(){return $('fob-reference').checked&&payload?.contexto?.referencia_disponivel!==false;}
  function secondary(parent,text){parent.append(node('small',text,'fob-secondary'));}
  function provisionalParameters(data=payload){
    const context=data?.contexto||{},periods=context.ultima_importacao_valida?.resumo?.cobertura_provisoria||[];
    return context.modo==='planilhas_mestre'&&periods.some(p=>p.origem==='REPLICA_OUTUBRO_2026'&&p.inicio<=context.data_fim&&p.fim>=context.data_inicio);
  }
  const itemProvisional=item=>Object.values(item.componentes||{}).some(c=>String(c?.origin||c?.origem||'').includes('REPLICA_OUTUBRO_2026'));
  function openButton(parent,text,scope){const b=node('button',text,'fob-data-button');b.type='button';b.addEventListener('click',()=>openItems(scope));parent.append(b);return b;}
  const freightCount=group=>Number(group.fretes_a_preencher??group.componentes?.frete?.pendentes??0);
  function valueShown(group,key){
    if(exists(group[key]))return group[key];
    return group[{valor_fob:'valor_fob_disponivel',pm_fob_kg:'pm_fob_disponivel_kg'}[key]]??(key==='valor_fob'?group.valor_fob_parcial:null);
  }
  function valueNote(group){
    const freight=freightCount(group),other=Object.entries(group.componentes||{}).filter(([key,c])=>key!=='frete'&&c.pendentes).map(([key])=>costs[key]);
    return ['Valor provisório: desconta somente os custos já informados.',freight?`Preenchimento de frete: ${freight} itens no Fretes.xlsx. Clique no valor para ver os itens desse recorte.`:'',other.length?'Dados a conferir: '+other.join(', ')+'.':'',group.itens_sem_valor_disponivel?`${group.itens_sem_valor_disponivel} itens sem base de valor não estão incluídos.`:''].filter(Boolean).join(' ');
  }
  function valueButton(parent,group,key,kind,scope){
    const warning=group.pendentes>0,value=valueShown(group,key),freight=freightCount(group);
    const button=openButton(parent,fmt(value,kind),{...scope,...(warning&&freight?{preencher_frete:true}:{})});
    if(warning){button.classList.add('fob-value-warning');button.title=valueNote(group);button.setAttribute('aria-label',fmt(value,kind)+'. '+button.title);const mark=node('span','!','fob-warning-mark');mark.setAttribute('aria-hidden','true');button.append(mark);}
    return button;
  }
  function renderCards(){
    const frag=document.createDocumentFragment();
    for(const channel of payload.canais){
      const card=node('article',undefined,'fob-card'),heading=node('div',undefined,'fob-card-title');
      heading.append(node('h3',channel.canal),badge(freightCount(channel)?`${freightCount(channel)} fretes a preencher`:channel.pendentes?'Dados a conferir':channel.itens?'Calculado':'Sem movimento',channel.pendentes?'pending':''));
      card.append(heading,node('strong',`${fmt(channel.peso)} kg`));
      const amount=node('p',undefined,'fob-card-amount');amount.append(document.createTextNode('FOB '));valueButton(amount,channel,'valor_fob','money',{canal:channel.canal});card.append(amount);
      if(payload.contexto.modo==='historico')card.append(node('p',`Preço praticado: ${fmt(channel.preco_praticado_kg,'unit')} R$/kg`));
      else if(channel.pendentes)card.append(node('p','Valor provisório; passe o mouse no ! para conferir.'));
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
    for(const [key,kind] of [['peso','number'],['valor_fob','money'],['pm_fob_kg','unit'],['fretes_a_preencher','number']]){
      const td=node('td',undefined,total?'fob-total-cell':'');
      if(key==='fretes_a_preencher')td.classList.add('fob-group-end');
      if(!group){td.textContent='—';tr.append(td);continue;}
      if(['pm_fob_kg','valor_fob'].includes(key))valueButton(td,group,key,kind,scope);
      else openButton(td,fmt(key==='fretes_a_preencher'?freightCount(group):group[key],kind),key==='fretes_a_preencher'?{...scope,preencher_frete:true}:scope);
      if(referenceVisible()&&key==='valor_fob')secondary(td,'Excel '+fmt(group.valor_fob_excel,'money'));
      if(referenceVisible()&&key==='pm_fob_kg')secondary(td,'Excel '+fmt(group.pm_fob_excel,'unit'));
      if(key==='valor_fob'&&group.provisorios)secondary(td,`${group.provisorios} provisório`);
      tr.append(td);
    }
  }
  function tableColumns(columns){
    const table=$('fob-table'),group=node('colgroup');
    const widths={weight:106,amount:154,price:130,pending:132,channel:150,cost:120};
    let width=0;
    for(const type of columns){group.append(node('col',undefined,'fob-col-'+type));width+=widths[type]||0;}
    table.querySelector('colgroup')?.remove();table.prepend(group);
    table.style.width=`calc(var(--fob-family-width) + ${width}px)`;
  }
  function renderMatrix(){
    tableColumns(['family',...Array.from({length:channels.length+1},()=>['weight','amount','price','pending']).flat()]);
    const top=node('tr'),bottom=node('tr'),label=node('th','Família','fob-family-heading');label.rowSpan=2;label.scope='col';top.append(label);
    for(const channel of [...channels,'Total']){
      const th=node('th',channel,'fob-channel-heading');th.colSpan=4;th.scope='colgroup';top.append(th);
      for(const text of ['Peso (kg)','Faturamento FOB','PM FOB (R$/kg)','Fretes a preencher']){const cell=node('th',text,text==='Fretes a preencher'?'fob-group-end':undefined);cell.scope='col';bottom.append(cell);}
    }
    $('fob-table').tHead.replaceChildren(top,bottom);
    const body=document.createDocumentFragment();
    for(const family of orderedFamilies()){
      const tr=node('tr'),th=node('th',undefined,'fob-family');th.scope='row';openButton(th,family.familia,{familia:family.familia});tr.append(th);
      for(const channel of channels)matrixValues(tr,payload.grupos.find(g=>g.familia===family.familia&&g.canal===channel),{familia:family.familia,canal:channel});
      matrixValues(tr,family,{familia:family.familia},true);body.append(tr);
    }
    if(!payload.familias.length){const tr=node('tr'),td=node('td','Nenhum item encontrado para os filtros.','empty');td.colSpan=1+(channels.length+1)*4;tr.append(td);body.append(tr);}
    $('fob-table').tBodies[0].replaceChildren(body);
    const total=node('tr');total.append(node('th','Total','fob-family'));
    for(const channel of channels)matrixValues(total,payload.canais.find(g=>g.canal===channel),{canal:channel});
    matrixValues(total,payload.total,{},true);$('fob-table').tFoot.replaceChildren(total);
  }
  function renderCosts(){
    tableColumns(['family','channel','weight','price',...Object.keys(costs).map(()=>'cost'),'price','amount','pending']);
    const head=node('tr');
    for(const label of ['Família','Canal','Peso (kg)','Praticado (R$/kg)',...Object.values(costs).map(n=>n+' /kg'),'PM FOB (R$/kg)','Valor FOB','Fretes a preencher']){const th=node('th',label,label==='Família'?'fob-family-heading':undefined);th.scope='col';head.append(th);}
    $('fob-table').tHead.replaceChildren(head);
    const body=document.createDocumentFragment();
    function row(group,total=false){
      const tr=node('tr'),th=node('th',undefined,'fob-family');openButton(th,total?'Total':group.familia,total?{}:{familia:group.familia,canal:group.canal});tr.append(th,node('td',group.canal||'Todos'),node('td',fmt(group.peso)),node('td',fmt(group.preco_praticado_kg,'unit')));
      const scope=total?{}:{familia:group.familia,canal:group.canal};
      for(const key of Object.keys(costs)){
        const c=group.componentes[key],td=node('td');
        const b=openButton(td,fmt(c.media_kg??c.media_disponivel_kg,'unit'),key==='frete'?{...scope,preencher_frete:true}:scope);
        if(c.pendentes){b.title=key==='frete'?valueNote(group):`Valor parcial; ${c.pendentes} itens aguardam ${costs[key]}.`;b.append(node('span','!','fob-warning-mark'));}
        tr.append(td);
      }
      const pm=node('td'),amount=node('td'),pending=node('td');valueButton(pm,group,'pm_fob_kg','unit',scope);valueButton(amount,group,'valor_fob','money',scope);openButton(pending,fmt(freightCount(group)),{...scope,preencher_frete:true});tr.append(pm,amount,pending);return tr;
    }
    for(const group of orderedGroups())body.append(row(group));
    if(!payload.grupos.length){const tr=node('tr'),td=node('td','Nenhum item encontrado.','empty');td.colSpan=15;tr.append(td);body.append(tr);}
    $('fob-table').tBodies[0].replaceChildren(body);$('fob-table').tFoot.replaceChildren(row(payload.total,true));
  }
  function render(){
    channels.splice(0,channels.length,...new Set(['Varejo','Atacado','Subprodutos',...payload.canais.map(c=>c.canal)]));
    $('fob-reference').disabled=payload.contexto.referencia_disponivel===false;
    document.querySelector('.fob-reference-tag').textContent=provisionalParameters()?'PROVISÓRIO · réplica de outubro/2026':payload.contexto.modo==='planilhas_mestre'?'Planilhas-mestre · parâmetros com vigência':payload.contexto.modo==='historico'?'Histórico do banco · FOB aguarda despesas':'Referência de 01 a 04/10/2026';
    renderCards();if(mode==='matrix')renderMatrix();else renderCosts();
    const total=payload.total,context=payload.contexto;
    $('fob-period').textContent=`${date(context.data_inicio)} a ${date(context.data_fim)}`;
    $('fob-source').textContent=context.modo==='planilhas_mestre'?'PostgreSQL · Planilhas-mestre com vigência · Sem arredondamento intermediário':context.modo==='historico'?'PostgreSQL · Despesas históricas ainda não cadastradas · Canal do cadastro atual':'PostgreSQL · Cadastros iniciais do Excel · Sem arredondamento intermediário';
    $('fob-count').textContent=context.modo==='historico'||context.modo==='planilhas_mestre'?`${fmt(total.itens)} itens no período consultado`:`${fmt(total.itens)} itens · ${fmt(context.linhas_fora_perimetro)} fora do perímetro na base de referência`;
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
      payload=result;applied=structuredClone(params);state.save({applied});render();status('Comparativo atualizado. Valores com ! têm dados a preencher.'+(!state.matchesDraft(params)?' Há filtros alterados; consulte para aplicá-los.':''));
    }catch(error){
      if(error.name==='AbortError'||own!==summarySeq)return;
      payload=null;applied=null;$('fob-cards').replaceChildren();
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
      state.restore(options.periodo_referencia||bounds);initialized=true;await query(state.applied());
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
  const itemColumns=[['data','Data'],['empresa_contexto','Empresa'],['unidade_documento','Unidade'],['serie','Série'],['nota_numero','NF'],['cliente','Cliente'],['produto','Produto'],['familia','Família'],['canal','Canal'],['peso','Peso'],['preco_praticado_kg','Praticado/kg'],...Object.entries(costs).map(([k,v])=>[k+'_kg',v+'/kg']),['preco_fob_kg','FOB/kg'],['valor_fob','Valor FOB']];
  let detail=null,detailPayload=null,detailController,exportController,detailSeq=0,detailLoaded=false,exporting=false;
  function detailParams(page=detail.pagina,size=50){return {...detail.base,familia:detail.familia?[detail.familia]:detail.base.familia,canal:detail.canal?[detail.canal]:detail.base.canal,pendentes:$('fob-items-pending').checked?'1':'0',...(detail.preencher_frete?{preencher_frete:'1'}:{}),busca:detail.busca,pagina:page,por_pagina:size,ordenar_por:detail.sort,ordem:detail.direction};}
  function closeItems(){detailController?.abort();exportController?.abort();detailSeq++;exporting=false;if(dialog.open)dialog.close();}
  function openItems(scope){
    if(!applied)return;
    detail={...scope,base:structuredClone(applied),pagina:1,busca:'',sort:'nota_numero',direction:'asc'};
    $('fob-items-title').textContent=(scope.preencher_frete?'Fretes.xlsx — itens a preencher · ':'')+([scope.familia,scope.canal].filter(Boolean).join(' · ')||'Todos os itens do comparativo');
    $('fob-items-context').textContent=`${date(applied.data_inicio)} a ${date(applied.data_fim)} · ${scope.preencher_frete?'Mesmos itens de frete para preenchimento, dentro do recorte clicado':'Valores e fontes por item'}`;
    $('fob-items-pending').checked=Boolean(scope.preencher_frete);$('fob-items-pending').disabled=Boolean(scope.preencher_frete);$('fob-items-query').value='';dialog.showModal();loadItems();
  }
  function auditRow(item,cols){
    const tr=node('tr',undefined,'fob-item-audit'),td=node('td');td.colSpan=cols;
    const grid=node('div',undefined,'fob-audit-grid');
    const source=node('div',undefined,'fob-audit-part');source.append(node('strong','Origem e comparação'),node('p',item.origem_registro||'Registro ausente na origem'),node('p',item.origem_excel||''),node('p',`Referência Excel: ${fmt(item.valor_fob_excel,'money')}`));
    source.append(node('p',item.produto_descricao||''),node('p',`CFOP: ${item.identificacao?.cfop||'—'} · Tipo de frete: ${item.dados_entrada?.frete??'—'}`));
    source.append(node('code',`${item.formula_preco_fob||'preco_praticado - soma(componentes/kg)'}\nPraticado/kg: ${item.preco_praticado_kg??'pendente'}\nFOB/kg: ${item.preco_fob_kg??'pendente'}\n${item.formula_valor_fob||'peso * preco_fob_kg'}\nPeso: ${item.peso??'ausente'} · Valor FOB: ${item.valor_fob??'pendente'}`));
    if(item.provisorio)source.append(node('p','Origem provisória: NF ainda não conciliada.'));
    if(item.pendencias?.length)source.append(node('p','Pendências: '+item.pendencias.join(', ')));
    if(item.avisos_frete?.length)source.append(node('p','Conferir frete: '+item.avisos_frete.join(', ')));
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
      for(const [key] of itemColumns){
        let value=item[key]??item.identificacao?.[key],warning=false;
        if(!exists(value)&&['preco_fob_kg','valor_fob'].includes(key)){value=item[key==='valor_fob'?'valor_fob_disponivel':'preco_fob_disponivel_kg'];warning=exists(value);}
        const text=key==='data'?date(value):['produto','cliente','empresa_contexto','serie','unidade_documento','nota_numero','familia','canal'].includes(key)?String(value??'—'):value===null||value===undefined?(key==='frete_kg'&&detail.preencher_frete?'A preencher':'—'):fmt(value,key==='valor_fob'?'money':key.endsWith('_kg')?'unit':'number');
        const td=node('td',text);if(warning){td.append(node('span','!','fob-warning-mark'));td.title='Valor provisório, sem os custos ainda não informados. Preencha o frete no Fretes.xlsx.';}tr.append(td);
      }
      const state=node('td');state.append(badge(detail.preencher_frete?'Preencher frete':item.valor_fob===null?'Dados a conferir':'Calculado',item.valor_fob===null?'pending':''));if(item.provisorio)state.append(badge('Provisório','provisional'));tr.append(state);
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
      renderItems();detailLoaded=true;itemPagination();$('fob-items-status').textContent=`${fmt(result.total.peso)} kg · ${detail.preencher_frete?`${result.total_registros} itens a preencher no Fretes.xlsx`:result.total.pendentes+' itens com dados a conferir'} · Abra “Ver cálculo” para conferir as origens.`;
    }catch(error){if(error.name!=='AbortError'&&own===detailSeq)$('fob-items-status').textContent=error.message;}
  }
  $('fob-export').addEventListener('click',()=>{
    if(!payload||!applied)return;
    const button=$('fob-export');button.disabled=true;button.textContent='Gerando CSV…';
    try{
      const provisional=provisionalParameters()?'REPLICA_OUTUBRO_2026':'Não';
      let headers,rows,numeric;
      if(mode==='matrix'){
        headers=['Família'];numeric=[];
        for(const channel of [...channels,'Total']){
          const start=headers.length;
          headers.push(...['Peso (kg)','Faturamento FOB','PM FOB (R$/kg)','Fretes a preencher'].map(label=>channel+' - '+label));
          numeric.push(start,start+1,start+2,start+3);
          if(referenceVisible()){numeric.push(headers.length,headers.length+1);headers.push(channel+' - FOB Excel',channel+' - PM FOB Excel');}
          headers.push(channel+' - Aviso');
        }
        const groups=new Map(payload.grupos.map(g=>[JSON.stringify([g.familia,g.canal]),g]));
        rows=[...orderedFamilies(),{...payload.total,familia:'Total',total:true}].map(family=>{
          const row=[family.familia];
          for(const channel of [...channels,'Total']){
            const group=channel==='Total'?family:family.total?payload.canais.find(c=>c.canal===channel):groups.get(JSON.stringify([family.familia,channel]));
            row.push(group?.peso??null,group?valueShown(group,'valor_fob'):null,group?valueShown(group,'pm_fob_kg'):null,group?freightCount(group):null);
            if(referenceVisible())row.push(group?.valor_fob_excel,group?.pm_fob_excel);
            row.push(group?.pendentes?valueNote(group):'');
          }
          return [...row,provisional];
        });
      }else{
        headers=['Família','Canal','Peso kg','Praticado kg',...Object.values(costs).map(c=>c+' kg'),'PM FOB disponível kg','Valor FOB disponível','Parcial concluído','Fretes a preencher','Provisórios','Aviso'];
        numeric=Array.from({length:15},(_,i)=>i+2);
        if(referenceVisible()){numeric.push(headers.length);headers.push('Referência Excel');}
        rows=[...orderedGroups(),payload.total].map(g=>{
          const row=[g.familia||'Total',g.canal||'Todos',g.peso,g.preco_praticado_kg,...Object.keys(costs).map(k=>g.componentes?.[k]?.media_kg??g.componentes?.[k]?.media_disponivel_kg),valueShown(g,'pm_fob_kg'),valueShown(g,'valor_fob'),g.valor_fob_parcial,freightCount(g),g.provisorios,g.pendentes?valueNote(g):''];
          if(referenceVisible())row.push(g.valor_fob_excel);
          return [...row,provisional];
        });
      }
      headers.push('Parâmetros provisórios no período');
      const output=CsvExport.writer(headers,numeric);output.append(rows);
      output.download(`${mode==='matrix'?'comparativo':'composicao'}-fob-${applied.data_inicio}-${applied.data_fim}.csv`);
      status(`CSV exportado com ${fmt(rows.length)} linhas, conforme a visão exibida.`);
    }catch(error){status('Não foi possível exportar o resumo: '+error.message,true);}
    finally{button.disabled=!payload?.grupos.length;button.textContent='Exportar resumo CSV';}
  });
  $('fob-items-export').addEventListener('click',async()=>{
    if(exporting){exportController.abort();exporting=false;$('fob-items-export').textContent='Exportar itens CSV';$('fob-items-status').textContent='Exportação cancelada.';return;}
    if(!detailLoaded)return;exporting=true;exportController=new AbortController();const signal=exportController.signal,own=detailSeq;$('fob-items-export').textContent='Cancelar exportação';
    const columns=[...itemColumns],query=structuredClone(detailParams(1,500));
    const numeric=columns.flatMap(([key],i)=>key==='peso'||key==='valor_fob'||key.endsWith('_kg')?[i]:[]);numeric.push(columns.length+3);
    const output=CsvExport.writer([...columns.map(c=>c[1]),'Estado','Provisório','Origem','Referência Excel','Parâmetros provisórios do item','Chave do item Fretes.xlsx','Aviso do valor'],numeric);
    const filename=`itens-fob-${detail.base.data_inicio}-${detail.base.data_fim}.csv`;
    $('fob-items-status').textContent='Preparando exportação dos itens…';
    try{
      await CsvExport.pages({total:detailPayload.total_registros,signal,cached:detailPayload,
        request:(pagina,por_pagina,pageSignal)=>apiGet(APP_CONFIG.fob.detalhes,{...query,pagina,por_pagina},{signal:pageSignal}),
        onPage:items=>{
          output.append(items.map(item=>[...columns.map(([k])=>item[k]??item.identificacao?.[k]??(k==='valor_fob'?item.valor_fob_disponivel:k==='preco_fob_kg'?item.preco_fob_disponivel_kg:null)),item.status,item.provisorio?'Sim':'Não',item.origem_registro,item.valor_fob_excel,itemProvisional(item)?'REPLICA_OUTUBRO_2026':'Não',item.chave_item,item.valor_fob===null?'Valor provisório, sem os custos ainda não informados':'']));
          if(own===detailSeq&&!signal.aborted)$('fob-items-status').textContent=`Exportando ${fmt(output.count)} de ${fmt(detailPayload.total_registros)} itens…`;
        }
      });
      if(own!==detailSeq||signal.aborted)return;
      output.download(filename);$('fob-items-status').textContent=`${fmt(output.count)} itens exportados.`;
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
