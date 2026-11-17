/* Apresentação apenas. Valores financeiros e percentuais são calculados na API. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), endpoint='/api/comercial/comparativo-fob/analise-vendedor-pai';
  const state=new ReportState('analise-vendedor-pai'), form=$('seller-filters');
  const columns=[['regional','Regional de Venda','text'],['peso','Peso Faturado','weight'],['percentual_peso','% Peso','percent'],['fob','Faturamento FOB','money'],['percentual_fob','% Fat. FOB','percent'],['diferenca','Dif. Fat. FOB','money'],['percentual_diferenca','% Dif.','percent'],['resultado','Resultado Projetado Produtos','pending'],['percentual_resultado','% Resultado','pending'],['frete_kg','Frete Calculado / Kg','rate'],['comissao_kg','Comissão Calculada / Kg','rate'],['contrato_kg','Contrato Calculado / Kg','rate']];
  const productColumns=[['produto','Produto','text'],['descricao','Descrição','text'],['peso','Peso (kg)','weight'],['fob','Faturamento FOB','money'],['pm_fob','PM Regional','rate'],['pm_geral','PM Global','rate'],['diferenca','Impacto financeiro','money'],['frete_kg','Frete/kg','rate'],['comissao_kg','Comissão + adicional/kg','rate'],['contrato_kg','Contrato/kg','rate']];
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
  function fillSelect(id,items,labelKey,valueKey){const select=$(id),old=select.value;select.replaceChildren(select.options[0]);for(const item of items){const o=node('option',typeof item==='string'?item:item[labelKey]);o.value=typeof item==='string'?item:item[valueKey];select.append(o);}select.value=old;}
  function head(table,cols,sortable=false){const row=node('tr');for(const [key,label,type] of cols){const th=node('th');th.scope='col';if(sortable&&type!=='pending'){th.setAttribute('aria-sort',sorted&&sortKey===key?(direction===1?'ascending':'descending'):'none');const button=node('button',label+' ↕');button.type='button';button.className='seller-sort';button.addEventListener('click',()=>{direction=sortKey===key?-direction:1;sortKey=key;sorted=true;persist();render();});th.append(button);}else th.textContent=label;row.append(th);}table.tHead.replaceChildren(row);}
  function rowCells(data,cols,clickable=false){const tr=node('tr');for(const [key,,type] of cols){const td=node('td');
    if(clickable&&key==='regional'){const b=node('button',data[key]+(data.fora_catalogo_regional?' *':''));b.className='seller-region-link';b.type='button';b.addEventListener('click',()=>openDetail(data[key]));td.append(b);}else if(data.financeiro_pendente){td.textContent=key==='regional'?data.regional:(key==='resultado'?'Pendente de custos':'—');}else td.textContent=key in data||type==='pending'?value(data[key],type):'?';
    if(type==='pending'||data[key]==null){td.classList.add('seller-pending');td.title=type==='pending'?'Aguardando CPV, despesas administrativas e regras de fechamento.':'Valor indisponível ou critério ainda não definido. Ausência não é zero.';}
    if(key==='diferenca'&&data[key]!=null)td.classList.add(Number(data[key])<0?'seller-negative':'seller-positive');tr.append(td);}return tr;}
  function render(){if(!payload)return;const table=$('seller-table');head(table,columns,true);const rows=[...payload.linhas];if(sorted)rows.sort((a,b)=>{const x=a[sortKey],y=b[sortKey];if(x==null)return y==null?0:1;if(y==null)return -1;return direction*(sortKey==='regional'?String(x).localeCompare(String(y),'pt-BR'):Number(x)-Number(y));});table.tBodies[0].replaceChildren(...rows.map(r=>rowCells(r,columns,true)));table.tFoot.replaceChildren(...payload.consolidacoes.map(r=>rowCells(r,columns)));}
  async function query(override){
    const own=++sequence;controller?.abort();controller=new AbortController();payload=null;$('seller-export').disabled=true;if($('seller-dialog').open)$('seller-dialog').close();
    $('seller-table').tBodies[0].replaceChildren();$('seller-table').tFoot.replaceChildren();$('seller-period').textContent='—';$('seller-validation').textContent='—';
    const p=override||params();persist();status('Calculando a análise com o motor FOB operacional…');form.setAttribute('aria-busy','true');
    try{const data=await apiGet(endpoint,p,{signal:controller.signal});if(own!==sequence)return;
      if(!Array.isArray(data.linhas)||!Array.isArray(data.produtos)||!Array.isArray(data.consolidacoes))throw new Error('Resposta incompleta da análise regional.');
      payload=data;applied={...p};state.save({applied});fillSelect('seller-region',data.filtros.regionais);fillSelect('seller-product',data.filtros.produtos.map(r=>({...r,label:r.codigo+' — '+r.descricao})),'label','codigo');
      for(const [id,key] of [['seller-unit','unidade'],['seller-region','regional'],['seller-product','produto']])$(id).value=p[key]||'';
      render();$('seller-period').textContent=p.data_inicio.split('-').reverse().join('/')+' a '+p.data_fim.split('-').reverse().join('/');
      const v=data.validacao;$('seller-validation').textContent='Soma das diferenças antes do filtro regional: '+value(v.diferenca_global,'money');
      $('seller-scope').textContent=`${v.itens_fora_catalogo} itens (${value(v.peso_fora_catalogo,'weight')} kg) fora dos blocos do catálogo. Peso da base selecionada: ${value(v.peso_base,'weight')} kg. Regionais adicionais: ${v.regionais_adicionais.join(', ')||'nenhuma'}. Este equilíbrio não comprova igualdade com o Excel.`;
      const pending=data.linhas.reduce((n,r)=>n+r.pendentes,0);status('Consulta concluída. '+(pending?pending+' itens com FOB pendente. ':'')+'Resultados projetados e impostos aguardam dados de custos.');$('seller-export').disabled=false;
    }catch(error){if(error.name==='AbortError'||own!==sequence)return;status(error.message,true);const tr=node('tr'),td=node('td','Consulta indisponível. Verifique a mensagem acima.');td.colSpan=12;tr.append(td);$('seller-table').tBodies[0].replaceChildren(tr);}finally{if(own===sequence)form.removeAttribute('aria-busy');}
  }
  function openDetail(regional){detailRows=payload.produtos.filter(r=>r.regional===regional);$('seller-detail-title').textContent=regional;$('seller-detail-count').textContent=detailRows.length+' produtos · '+$('seller-period').textContent;const table=$('seller-products');head(table,productColumns);table.tBodies[0].replaceChildren(...detailRows.map(r=>rowCells(r,productColumns)));if(!detailRows.length){const tr=node('tr'),td=node('td','Nenhum produto no recorte.');td.colSpan=10;tr.append(td);table.tBodies[0].append(tr);}$('seller-dialog').showModal();}
  function csv(rows,cols,name){const writer=CsvExport.writer(cols.map(c=>c[1]),cols.flatMap((c,i)=>!['text','pending'].includes(c[2])?[i]:[]));writer.append(rows.map(r=>cols.map(([key,,type])=>type==='pending'?'Pendente de custos':r.financeiro_pendente?(key==='regional'?r.regional:key==='resultado'?'Pendente de custos':''):key in r?(r[key]??'Pendente'):'')));writer.download(name);}
  $('seller-export').addEventListener('click',()=>{if(payload)csv([...payload.linhas,...payload.consolidacoes],columns,`analise-vendedor-pai-${applied.data_inicio}-${applied.data_fim}.csv`);});
  $('seller-detail-export').addEventListener('click',()=>csv(detailRows,productColumns,`produtos-regional-${applied.data_inicio}-${applied.data_fim}.csv`));
  $('seller-close').addEventListener('click',()=>$('seller-dialog').close());
  form.addEventListener('submit',e=>{e.preventDefault();query();});form.addEventListener('change',()=>{persist();if(payload)status('Filtros alterados. Consulte para aplicá-los.');});window.addEventListener('pagehide',persist);
  const saved=state.get('draft',{});sortKey=state.get('sortKey','regional');direction=state.get('direction',1);sorted=state.get('sorted',false);
  for(const [id,key] of [['seller-start','data_inicio'],['seller-end','data_fim'],['seller-unit','unidade']])if(typeof saved[key]==='string')$(id).value=saved[key];
  for(const [id,key] of [['seller-region','regional'],['seller-product','produto']])if(saved[key]){const o=node('option',saved[key]);o.value=saved[key];$(id).append(o);$(id).value=saved[key];}
  for(const id of ['seller-start','seller-end'])$(id).max=new Date().toLocaleDateString('en-CA');
  query();
})();
