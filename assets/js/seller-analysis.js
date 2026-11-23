/* Apresentação apenas. Valores financeiros e percentuais são calculados na API. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), endpoint='/api/comercial/comparativo-fob/analise-vendedor-pai';
  const state=new ReportState('analise-vendedor-pai'), form=$('seller-filters');
  const columns=[['regional','Regional de Venda','text'],['peso','Peso Faturado','weight'],['percentual_peso','% Peso','percent'],['fob','Faturamento FOB','money'],['percentual_fob','% Fat. FOB','percent'],['diferenca','Dif. Fat. FOB','money'],['percentual_diferenca','% Dif.','percent'],['resultado','Resultado Projetado Produtos','money'],['percentual_resultado','% Resultado','percent'],['frete_kg','Frete Calculado / Kg','rate'],['comissao_kg','Comissão Calculada / Kg','rate'],['contrato_kg','Contrato Calculado / Kg','rate']];
  const productColumns=[['produto','Produto','text'],['descricao','Descrição','text'],['peso','Peso (kg)','weight'],['fob','Faturamento FOB','money'],['pm_fob','PM Regional','rate'],['pm_geral','PM Global','rate'],['diferenca','Impacto financeiro','money'],['frete_kg','Frete/kg','rate'],['comissao_kg','Comissão + adicional/kg','rate'],['contrato_kg','Contrato/kg','rate'],['cpv_kg','CPV/kg','rate'],['despesas_kg','Rateio de despesas/kg','rate'],['resultado','Resultado projetado','money'],['origem_cpv','Origem do CPV','text'],['motivo_pendencia','Pendencias a conferir','text']];
  let detailColumns=productColumns;
  let payload=null, applied=null, controller=null, sequence=0, sortKey='regional', direction=1, sorted=false, detailRows=[];
  const node=(tag,text)=>{const el=document.createElement(tag);if(text!=null)el.textContent=text;return el;};
  function value(v,type){
    if(type==='pending')return 'Pendente de custos';
    if(v==null)return 'Pendente';
    if(type==='text')return String(v);
    const n=Number(v);if(!Number.isFinite(n))return '—';
    if(type==='money')return n.toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
    if(type==='percent')return n.toLocaleString('pt-BR',{style:'percent',minimumFractionDigits:2,maximumFractionDigits:2});
    return n.toLocaleString('pt-BR',{minimumFractionDigits:type==='rate'?4:0,maximumFractionDigits:type==='rate'?4:3});
  }
  function params(){return {data_inicio:$('seller-start').value,data_fim:$('seller-end').value,unidade:$('seller-unit').value,regional:$('seller-region').value,produto:$('seller-product').value};}
  function persist(){state.save({draft:params(),sortKey,direction,sorted});}
  function status(text,error=false){$('seller-status').textContent=text;$('seller-status').classList.toggle('error',error);}
  const freightPath='\\\\192.168.1.139\\Controladoria\\BI_Granja\\Planilhas_BI\\Faturamento-CFOP\\Fretes.xlsx';
  $('seller-freight-path').textContent=freightPath;
  function pendingHelp(item){
    const reasons=(item.motivos||[]).join('; '),plain=reasons.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
    const location=reasons.match(/Fretes\.xlsx\/([^!;]+)!(\d+)/i);
    const review=plain.includes('revisar identifica')||plain.includes('revisar_identificacao');
    const freight=plain.includes('frete');
    return {...item,motivo_pendencia:reasons,
      onde_conferir:location?`Fretes.xlsx → ${location[1]} → linha ${location[2]}`:freight?'Fretes.xlsx → Pendências e Preenchimentos':'Conferir a origem indicada no motivo',
      como_resolver:review?'Valor já informado. Conferir a identificação, os itens e pesos da NF; responsável valida o vínculo e reimporta. Preservar o valor confirmado; não editar assinatura manualmente.':freight?'Conferir NF na aba Pendências. Informar o valor confirmado em Preenchimentos, conforme escopo/modalidade; salvar, fechar e importar pelo robô.':'Solicitar ao responsável a conferência do cadastro indicado, sem assumir custo zero.'};
  }
  function fillSelect(id,items,labelKey,valueKey){const select=$(id),old=select.value;select.replaceChildren(select.options[0]);for(const item of items){const o=node('option',typeof item==='string'?item:item[labelKey]);o.value=typeof item==='string'?item:item[valueKey];select.append(o);}select.value=old;}
  function head(table,cols,sortable=false){const row=node('tr');for(const [key,label,type] of cols){const th=node('th');th.scope='col';if(sortable&&type!=='pending'){th.setAttribute('aria-sort',sorted&&sortKey===key?(direction===1?'ascending':'descending'):'none');const button=node('button',label+' ↕');button.type='button';button.className='seller-sort';button.addEventListener('click',()=>{direction=sortKey===key?-direction:1;sortKey=key;sorted=true;persist();render();});th.append(button);}else th.textContent=label;row.append(th);}table.tHead.replaceChildren(row);}
  function rowCells(data,cols,clickable=false){const tr=node('tr');for(const [key,,type] of cols){const td=node('td');
    if(clickable&&key==='regional'){const b=node('button',data[key]+(data.fora_catalogo_regional?' *':''));b.className='seller-region-link';b.type='button';b.addEventListener('click',()=>openDetail(data[key]));td.append(b);}else if(data.financeiro_pendente){td.textContent=key==='regional'?data.regional:(key==='resultado'?'Em conferência':'—');}else td.textContent=key==='resultado'&&data[key]==null?'Pendente de custos':key in data||type==='pending'?value(data[key],type):'—';
    if(type==='pending'||data[key]==null){td.classList.add('seller-pending');td.title=type==='pending'?'Aguardando CPV, despesas administrativas e regras de fechamento.':'Valor indisponível ou critério ainda não definido. Ausência não é zero.';}
    const noMovement=data.itens===0&&!data.financeiro_pendente;
    if(noMovement&&data[key]==null&&type!=='text'){td.textContent='—';td.title='Sem movimento no recorte; indicador não aplicável.';}
    const missing=data[key]==null&&Number(data.peso)>0;
    if(!data.financeiro_pendente&&!noMovement&&((key==='fob'&&data.pendentes>0)||(missing&&['resultado','diferenca','frete_kg','contrato_kg','percentual_fob','percentual_diferenca','percentual_resultado','pm_fob','pm_geral','cpv_kg','despesas_kg'].includes(key)))){
      const hasFreight=(payload?.total_pendencias_itens||0)>0;
      const reason=key==='percentual_fob'?'O percentual depende do FOB total do catálogo, ainda incompleto por itens pendentes, mesmo que o FOB desta regional esteja calculado. Clique para conferir os itens.':key==='percentual_diferenca'?'O percentual depende da diferença FOB e do PM global por produto, ainda pendentes. Clique para ver os produtos.':key==='percentual_resultado'?'O percentual depende do resultado projetado, que aguarda a conclusão dos custos e do rateio mensal.':key==='fob'||key==='frete_kg'?'Frete pendente de conferência. Clique para ver o motivo, a nota e onde conferir/preencher no Fretes.xlsx.':['diferenca','pm_fob','pm_geral'].includes(key)?'O PM global depende de produtos com dados pendentes, inclusive em outras regionais.':key==='contrato_kg'?'Critério de contrato desta unidade aguarda conferência.':hasFreight?'O resultado depende do rateio mensal, que aguarda a validação dos fretes pendentes. CPV e despesas podem já estar cadastrados. Clique para ver as notas, motivos e orientações.':'Resultado aguarda CPV ou a base mensal completa do rateio. '+(data.motivos_pendencia||[]).join('; ');
      const mark=node('button','!');mark.type='button';mark.className='seller-warning-mark';mark.title=reason;mark.setAttribute('aria-label',reason);
      mark.addEventListener('click',()=>{if(['fob','frete_kg'].includes(key))openPending(data.regional,data.produto);else if((['resultado','percentual_resultado','percentual_fob','despesas_kg'].includes(key))&&hasFreight)openPending();else if(payload.linhas.some(r=>r.regional===data.regional))openDetail(data.regional);else openPending();});td.append(mark);td.title=reason;
    }
    if(key==='diferenca'&&data[key]!=null)td.classList.add(Number(data[key])<0?'seller-negative':'seller-positive');tr.append(td);}return tr;}
  function render(){if(!payload)return;const table=$('seller-table');head(table,columns,true);const rows=[...payload.linhas];if(sorted)rows.sort((a,b)=>{const x=a[sortKey],y=b[sortKey];if(x==null)return y==null?0:1;if(y==null)return -1;return direction*(sortKey==='regional'?String(x).localeCompare(String(y),'pt-BR'):Number(x)-Number(y));});table.tBodies[0].replaceChildren(...rows.map(r=>rowCells(r,columns,true)));table.tFoot.replaceChildren(...payload.consolidacoes.map(r=>rowCells(r,columns)));}
  async function query(override){
    const own=++sequence;controller?.abort();controller=new AbortController();payload=null;$('seller-pending-items').hidden=true;$('seller-export').disabled=true;if($('seller-dialog').open)$('seller-dialog').close();
    $('seller-table').tBodies[0].replaceChildren();$('seller-table').tFoot.replaceChildren();$('seller-period').textContent='—';$('seller-validation').textContent='—';
    const p=override||params();persist();status('Calculando a análise com o motor FOB operacional…');form.setAttribute('aria-busy','true');
    try{const data=await apiGet(endpoint,p,{signal:controller.signal});if(own!==sequence)return;
      if(!Array.isArray(data.linhas)||!Array.isArray(data.produtos)||!Array.isArray(data.consolidacoes))throw new Error('Resposta incompleta da análise regional.');
      payload=data;applied={...p};$('seller-pending-items').hidden=!data.total_pendencias_itens;$('seller-pending-items').textContent='Ver '+data.total_pendencias_itens+' itens pendentes';state.save({applied});fillSelect('seller-region',data.filtros.regionais);fillSelect('seller-product',data.filtros.produtos.map(r=>({...r,label:r.codigo+' — '+r.descricao})),'label','codigo');
      for(const [id,key] of [['seller-unit','unidade'],['seller-region','regional'],['seller-product','produto']])$(id).value=p[key]||'';
      render();$('seller-period').textContent=p.data_inicio.split('-').reverse().join('/')+' a '+p.data_fim.split('-').reverse().join('/');
      const v=data.validacao;$('seller-validation').textContent='Soma das diferenças antes do filtro regional: '+value(v.diferenca_global,'money');
      $('seller-scope').textContent=`${v.itens_fora_catalogo} itens (${value(v.peso_fora_catalogo,'weight')} kg) fora dos blocos do catálogo. Peso da base selecionada: ${value(v.peso_base,'weight')} kg. Regionais adicionais: ${v.regionais_adicionais.join(', ')||'nenhuma'}. Este equilíbrio não comprova igualdade com o Excel.`;
      const pending=data.linhas.reduce((n,r)=>n+r.pendentes,0);const costsPending=data.linhas.reduce((n,r)=>n+(r.pendentes_resultado??(r.resultado==null&&Number(r.peso)>0?r.itens:0)),0);$('seller-cost-status').textContent=costsPending?costsPending+' itens aguardam CPV ou rateio mensal.':'Resultado projetado calculado com os custos disponíveis da competência.';status('Consulta concluída. '+(pending?pending+' itens com FOB pendente. ':'')+'Impostos e abrangência dos consolidados aguardam conferência dos responsáveis.');$('seller-export').disabled=false;
      const months=data.contexto?.fechamento||[];
      if(data.total_pendencias_itens>0&&months.length&&months.every(m=>m.cadastrada))$('seller-cost-status').textContent=`CPV e despesas mensais cadastrados. ${data.total_pendencias_itens} itens com FOB pendente impedem concluir o rateio. Clique no ! para conferir motivos e orientações.`;
    }catch(error){if(error.name==='AbortError'||own!==sequence)return;status(error.message,true);const tr=node('tr'),td=node('td','Consulta indisponível. Verifique a mensagem acima.');td.colSpan=12;tr.append(td);$('seller-table').tBodies[0].replaceChildren(tr);}finally{if(own===sequence)form.removeAttribute('aria-busy');}
  }
  function openDetail(regional){$('seller-pending-help').hidden=true;$('seller-products').classList.remove('seller-pending-table');detailColumns=productColumns;detailRows=payload.produtos.filter(r=>r.regional===regional).map(r=>({...r,motivo_pendencia:(r.motivos_pendencia||[]).join('; ')}));$('seller-detail-title').textContent=regional;$('seller-detail-count').textContent=detailRows.length+' produtos · '+$('seller-period').textContent;const table=$('seller-products');head(table,productColumns);table.tBodies[0].replaceChildren(...detailRows.map(r=>rowCells(r,productColumns)));if(!detailRows.length){const tr=node('tr'),td=node('td','Nenhum produto no recorte.');td.colSpan=productColumns.length;tr.append(td);table.tBodies[0].append(tr);}$('seller-dialog').showModal();}
  function csv(rows,cols,name){const writer=CsvExport.writer(cols.map(c=>c[1]),cols.flatMap((c,i)=>!['text','pending'].includes(c[2])?[i]:[]));writer.append(rows.map(r=>cols.map(([key,,type])=>type==='pending'?'Pendente de custos':r.financeiro_pendente?(key==='regional'?r.regional:key==='resultado'?'Em conferência':''):key in r?(r[key]??'Pendente'):'')));writer.download(name);}
  function openPending(regional=null,product=null){
    $('seller-pending-help').hidden=false;
    const known=payload.linhas.some(r=>r.regional===regional);
    detailColumns=[['regional','Regional','text'],['data','Data','text'],['empresa_contexto','Empresa','text'],['unidade_documento','Unidade','text'],['serie','Série','text'],['nota_numero','NF','text'],['produto','Produto','text'],['peso','Peso (kg)','weight'],['motivo_pendencia','Motivo / origem','text'],['onde_conferir','Onde conferir','text'],['como_resolver','Como resolver / preencher','text']];
    detailRows=(payload.pendencias_itens||[]).filter(r=>(!known||r.regional===regional)&&(!product||String(r.produto).replace(/^0+/,'')===String(product).replace(/^0+/,''))).map(pendingHelp);
    $('seller-detail-title').textContent='Itens para conferência'+(known?' · '+regional:'');$('seller-detail-count').textContent=detailRows.length+' itens · '+$('seller-period').textContent+(payload.pendencias_truncadas?' · Lista limitada a 500; restrinja os filtros.':'');
    const table=$('seller-products');table.classList.add('seller-pending-table');head(table,detailColumns);table.tBodies[0].replaceChildren(...detailRows.map(r=>rowCells(r,detailColumns)));
    if(!detailRows.length){const tr=node('tr'),td=node('td','Nenhum item pendente neste recorte. A dependência pode estar na base mensal de outra regional.');td.colSpan=detailColumns.length;tr.append(td);table.tBodies[0].append(tr);}
    if(!$('seller-dialog').open)$('seller-dialog').showModal();
  }
  $('seller-pending-items').addEventListener('click',()=>openPending());
  $('seller-export').addEventListener('click',()=>{if(payload)csv([...payload.linhas,...payload.consolidacoes],columns,`analise-vendedor-pai-${applied.data_inicio}-${applied.data_fim}.csv`);});
  $('seller-detail-export').addEventListener('click',()=>csv(detailRows,detailColumns,`produtos-regional-${applied.data_inicio}-${applied.data_fim}.csv`));
  $('seller-close').addEventListener('click',()=>$('seller-dialog').close());
  form.addEventListener('submit',e=>{e.preventDefault();query();});form.addEventListener('change',()=>{persist();if(payload)status('Filtros alterados. Consulte para aplicá-los.');});window.addEventListener('pagehide',persist);
  $('seller-clear-filters').addEventListener('click',()=>{
    controller?.abort();sequence++;payload=null;applied=null;$('seller-pending-items').hidden=true;
    for(const id of ['seller-start','seller-end','seller-unit','seller-region','seller-product'])$(id).value='';
    state.save({applied:null});persist();if($('seller-dialog').open)$('seller-dialog').close();
    $('seller-export').disabled=true;$('seller-table').tFoot.replaceChildren();
    const tr=node('tr'),td=node('td','Selecione o período e consulte a análise.');td.colSpan=12;tr.append(td);$('seller-table').tBodies[0].replaceChildren(tr);
    $('seller-period').textContent='—';$('seller-validation').textContent='—';$('seller-scope').textContent='Consulte para verificar a cobertura do catálogo.';
    form.removeAttribute('aria-busy');status('Filtros limpos. Selecione o período e clique em Consultar análise.');$('seller-start').focus();
  });
  const saved=state.get('draft',{});sortKey=state.get('sortKey','regional');direction=state.get('direction',1);sorted=state.get('sorted',false);
  for(const [id,key] of [['seller-start','data_inicio'],['seller-end','data_fim'],['seller-unit','unidade']])if(typeof saved[key]==='string')$(id).value=saved[key];
  for(const [id,key] of [['seller-region','regional'],['seller-product','produto']])if(saved[key]){const o=node('option',saved[key]);o.value=saved[key];$(id).append(o);$(id).value=saved[key];}
  for(const id of ['seller-start','seller-end'])$(id).max=new Date().toLocaleDateString('en-CA');
  if($('seller-start').value&&$('seller-end').value)query();else status('Selecione o período e clique em Consultar análise.');
})();
