/* A interface apenas formata a resposta autenticada; não calcula finanças. */
(() => {
  const $=id=>document.getElementById(id),form=$('mix-filters'),store=new ReportState('comparativo-mix');
  const ids={data_inicio:'mix-start',data_fim:'mix-end',unidade:'mix-unit',comparacao:'mix-comparison',aves:'mix-birds',peso_medio:'mix-weight'};
  const defaults={data_inicio:'2026-10-01',data_fim:'2026-10-31',unidade:'',comparacao:'',aves:'',peso_medio:''};
  const percent=new Intl.NumberFormat('pt-BR',{style:'percent',minimumFractionDigits:1,maximumFractionDigits:2});
  const escape=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  let data=null,busy=false,controller=null,restoreComparison=true;
  function values(){return Object.fromEntries(Object.entries(ids).map(([key,id])=>[key,$(id).value]));}
  function save(){store.save({draft:values()});}
  const saved={...defaults,...store.get('draft',{})};
  for(const [key,id] of Object.entries(ids))if(key!=='comparacao')$(id).value=typeof saved[key]==='string'?saved[key]:defaults[key];
  function status(message,error=false){$('mix-status').textContent=message;$('mix-status').classList.toggle('error',error);}
  function shown(){return (data?.linhas||[]).filter(row=>!$('mix-comparison').value||row.id===$('mix-comparison').value);}
  function label(item){return item.status==='calculado'&&item.valor!=null?percent.format(Number(item.valor)):({pendente:'Pendente',conferir_calculo:'Conferir cálculo',sem_venda:'Sem venda',sem_preco:'Sem preço'}[item.status]||'Pendente');}
  function render(){
    $('mix-table').querySelector('tbody').innerHTML=shown().map(row=>'<tr>'+['a','b'].map(side=>{
      const item=row[side],pending=item.status!=='calculado';
      return `<td>${escape(row['familia_'+side])}</td><td><button type="button" class="mix-value ${pending?'pending':Number(item.valor)<0?'negative':''}" data-row="${escape(row.id)}" data-side="${side}" title="${escape(item.motivo||'Ver fórmula e origem')}" aria-label="${escape(row['familia_'+side]+': '+label(item)+'. Conferir cálculo')}">${escape(label(item))}${pending?'<span class="mix-alert" aria-hidden="true">!</span>':''}</button></td>`;
    }).join('')+'</tr>').join('')||'<tr><td colspan="4" class="empty">Nenhuma comparação neste filtro.</td></tr>';
    $('mix-count').textContent=`${shown().length} comparações`; $('mix-export').disabled=!data||busy;
  }
  function detail(row,side){
    const item=row[side];$('mix-detail-title').textContent=row['familia_'+side];
    $('mix-detail-body').innerHTML=`<p><strong>Resultado:</strong> ${escape(label(item))}</p>${item.motivo?`<p><strong>Motivo:</strong> ${escape(item.motivo)}</p>`:''}${item.como_resolver?`<p><strong>Como e onde resolver:</strong> ${escape(item.como_resolver)}</p>`:''}<p><strong>Origem dos preços:</strong> ${escape(data.origem.precos)}</p><p><strong>Parâmetros:</strong> ${escape(data.origem.parametros)}</p><p><strong>Método:</strong> ${escape(item.origem)}</p><p><code>${escape(item.formula||'')}</code></p><details><summary>Valores percorridos no cálculo (${item.auditoria?.length||0})</summary><div class="table-scroll"><table><thead><tr><th>Aba do método</th><th>Célula</th><th>Valor</th></tr></thead><tbody>${(item.auditoria||[]).map(entry=>`<tr><td>${escape(entry.aba)}</td><td>${escape(entry.celula)}</td><td>${escape(entry.valor)}</td></tr>`).join('')}</tbody></table></div></details>`;
    $('mix-detail').showModal();
  }
  async function load(){
    if(busy)return;if(!form.reportValidity())return;
    const params=values();if(params.data_inicio>params.data_fim||params.data_inicio.slice(0,7)!==params.data_fim.slice(0,7)){status('Selecione datas do mesmo mês, em ordem válida.',true);return;}
    delete params.comparacao;busy=true;save();controller=new AbortController();
    form.querySelector('[type="submit"]').disabled=true;$('mix-export').disabled=true;status('Consultando preços FOB e parâmetros mensais…');
    try{
      const result=await apiGet(APP_CONFIG.comparativoMix,params,{signal:controller.signal});
      if(!Array.isArray(result.linhas)||!result.status||!result.origem)throw new Error('A API não retornou o contrato do Comparativo Mix. Confira o pacote instalado no Anderson.');
      data=result;const selection=restoreComparison?saved.comparacao:$('mix-comparison').value;restoreComparison=false;
      $('mix-comparison').innerHTML='<option value="">Todas as comparações</option>'+data.linhas.map(row=>`<option value="${escape(row.id)}">${escape(row.familia_a+' × '+row.familia_b)}</option>`).join('');
      $('mix-comparison').value=data.linhas.some(row=>row.id===selection)?selection:'';
      $('mix-period').textContent=`${result.periodo.inicio.split('-').reverse().join('/')} a ${result.periodo.fim.split('-').reverse().join('/')}`;
      $('mix-warning').hidden=!result.status.aviso;$('mix-warning').textContent=result.status.aviso||'';
      $('mix-source').textContent=result.status.parametros_importados?'PostgreSQL · FOB e parâmetros mensais':'PostgreSQL · parâmetros Mix aguardam homologação';
      status(`Consulta concluída. ${result.status.resultados_pendentes} resultados aguardam dados. Clique no ! para conferir.`);
      store.save({applied:params});
    }catch(error){
      data=null;$('mix-warning').hidden=true;$('mix-period').textContent='—';$('mix-count').textContent='—';
      $('mix-table').querySelector('tbody').innerHTML='<tr><td colspan="4" class="empty">Consulta não concluída. Nenhum resultado anterior está sendo apresentado.</td></tr>';
      status(error.message,true);
    }finally{busy=false;form.querySelector('[type="submit"]').disabled=false;if(data)render();save();}
  }
  form.addEventListener('submit',event=>{event.preventDefault();load();});
  form.addEventListener('input',()=>{save();if(data)status('Filtros alterados. Consulte para aplicá-los.');});
  $('mix-comparison').addEventListener('change',()=>{render();save();});
  $('mix-clear').addEventListener('click',()=>{controller?.abort();restoreComparison=false;for(const [key,id] of Object.entries(ids))$(id).value=defaults[key];save();if(!busy)load();});
  $('mix-table').addEventListener('click',event=>{const button=event.target.closest('[data-row]');if(button){const row=data?.linhas.find(row=>row.id===button.dataset.row);if(row)detail(row,button.dataset.side);}});
  $('mix-close').addEventListener('click',()=>$('mix-detail').close());
  $('mix-export').addEventListener('click',()=>{
    if(!data)return;const csv=CsvExport.writer(['Família A','Geração caixa A (fração)','Situação A','Motivo A','Como resolver A','Família B','Geração caixa B (fração)','Situação B','Motivo B','Como resolver B','Início','Fim','Origem parâmetros'],[1,6]);
    csv.append(shown().map(row=>[row.familia_a,row.a.valor,row.a.status,row.a.motivo,row.a.como_resolver,row.familia_b,row.b.valor,row.b.status,row.b.motivo,row.b.como_resolver,data.periodo.inicio,data.periodo.fim,data.origem.parametros]));
    csv.download(`comparativo-mix-${data.periodo.inicio}-${data.periodo.fim}.csv`);
  });
  window.addEventListener('pagehide',save);load();
})();
