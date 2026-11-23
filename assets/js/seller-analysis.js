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
  function pendingInfo(data,key){
    const freight=(payload?.total_pendencias_itens||0)>0;
    const monthlyBlocked=(payload?.contexto?.fechamento||[]).some(m=>m.cadastrada&&m.pool_mensal==null&&m.itens_resultado_pendente>0);
    const instructions={
      percentual_fob:['Aguardando FOB total','FOB da regional ÷ FOB total. O denominador está incompleto, mesmo que esta regional já tenha FOB calculado.','Conferir os itens com FOB pendente, validar seus custos e reimportar os cadastros pelo robô. Depois consultar novamente.'],
      percentual_diferenca:['Aguardando diferença FOB','A conta depende da diferença FOB e do PM global dos produtos, ainda incompletos.','Resolver as pendências dos produtos na base global, inclusive em outras regionais; depois recalcular a consulta.'],
      percentual_peso:['Aguardando base de peso','O peso total usado no denominador está indisponível ou não é positivo.','Conferir os pesos do faturamento e o período selecionado com o responsável pela origem.'],
      percentual_resultado:data.resultado==null?['Aguardando resultado','Resultado projetado ÷ valor dos produtos. O resultado ainda não foi concluído.','Concluir a base mensal do FOB e seu rateio; se houver CPV ausente, cadastrar o custo da competência e importar pelo robô.']:['Verificar base do percentual','O resultado existe, mas a base de valor dos produtos está ausente ou não é positiva.','Conferir valor_produto do faturamento da regional e as notas do recorte com o responsável pela origem.'],
      fob:['Aguardando custos do FOB','Há itens cujos componentes não puderam ser validados. O total não considera ausência como zero.','Abra os itens pendentes. Confira o motivo, o arquivo, a aba e a linha indicados antes de corrigir e importar pelo robô.'],
      frete_kg:['Aguardando frete','Frete ausente ou cadastro em revisão de identificação; um valor já informado também pode estar bloqueado.','Conferir Fretes.xlsx, abas Pendências e Preenchimentos. Em revisão de identificação, preservar o valor confirmado e pedir ao responsável a conciliação do vínculo.'],
      diferenca:['Aguardando PM global','A diferença é calculada por produto contra o PM global. Pendências em outra regional também podem impedir esta conta.','Consultar os produtos da regional e resolver os itens pendentes da base global. Não substituir a comparação por uma média simples.'],
      pm_fob:['Aguardando FOB do produto','O PM é FOB ÷ peso; o FOB do grupo ainda está incompleto.','Validar os custos dos itens do produto e consultar novamente.'],
      pm_geral:['Aguardando PM global','O FOB global do mesmo código ainda tem itens pendentes nas quatro unidades.','Conferir os itens do produto em todas as regionais/unidades no período e resolver as pendências de custos.'],
      resultado:freight||monthlyBlocked?['Aguardando base mensal','O rateio usa o FOB do mês completo. Itens com FOB ou pallet pendente impedem fechar o rateio, mesmo com CPV e despesas cadastrados.','Conferir os itens pendentes do mês inteiro, sem restringir regional/unidade. Validar os vínculos de frete e demais componentes indicados e importar os cadastros pelo robô.']:['Aguardando custos mensais','CPV, fechamento mensal ou universo de rateio do produto ainda não está disponível para concluir o resultado.','Responsável deve conferir o CPV e as despesas da própria competência e importar os insumos pelo robô; não repetir outro mês automaticamente.'],
      despesas_kg:['Aguardando rateio mensal','O fechamento ou a base completa de FOB/pallet do mês ainda não permite distribuir as despesas.','Conferir o cadastro da competência e os itens pendentes do mês inteiro. Resolver a origem e consultar novamente.'],
      cpv_kg:['Aguardando CPV','Não há custo industrial válido para o produto/competência nesta consulta.','Conferir CPV-Frango do mês correspondente e importar o cadastro pelo robô de fechamento; não informar o resultado final manualmente.'],
      origem_cpv:['Conferir origem do CPV','A origem do custo do produto não está disponível nesta resposta.','Conferir o cadastro de CPV da competência e sua versão de importação.'],
      contrato_kg:['Contrato em conferência','O cadastro está ausente ou a regra da coluna ainda precisa ser aprovada. Em RN e Januária, o Excel tinha zeros fixos, sem fórmula comprovada.','Responsável comercial deve definir a regra. Se for cadastro ausente, corrigir Despesas.xlsx respeitando unidade, cliente/rede e vigência, e importar pelo robô.'],
      comissao_kg:['Aguardando comissão','Comissão ou adicional não pôde ser calculado com os cadastros e a base da vigência.','Conferir Comissoes.xlsx e a base de faturamento da vigência; corrigir o cadastro indicado e importar pelo robô.'],
      peso:['Conferir peso','O peso necessário para a conta não está disponível.','Conferir a nota e o item no relatório de origem do faturamento; não inventar um peso.']
    };
    if(data.financeiro_pendente)return {label:'Em conferência',reason:'Impostos e resultado líquido aguardam aprovação de alíquotas, bases e abrangência de CMS/resíduos. Nenhum imposto foi aplicado.',action:'Responsáveis pelo fechamento devem conferir e aprovar os critérios. Após aprovação, atualizar os parâmetros e o cálculo; não preencher manualmente o resultado líquido.'};
    const entry=instructions[key]||['Conferir origem','O dado necessário para este indicador não foi disponibilizado ou validado.','Conferir a origem indicada no detalhamento com o responsável pelo cadastro, antes de corrigir e importar novamente.'];
    return {label:entry[0],reason:entry[1],action:entry[2]};
  }
  const reasonDialog=node('dialog');reasonDialog.id='seller-reason-dialog';reasonDialog.setAttribute('aria-labelledby','seller-reason-title');
  const reasonTitle=node('h2');reasonTitle.id='seller-reason-title';
  const reasonText=node('p'),actionText=node('p'),reasonItems=node('button','Ver itens e locais de preenchimento'),reasonClose=node('button','Fechar');
  reasonItems.type=reasonClose.type='button';reasonDialog.append(reasonTitle,node('strong','Por que está pendente'),reasonText,node('strong','Como resolver'),actionText,reasonItems,reasonClose);document.body.append(reasonDialog);
  reasonClose.addEventListener('click',()=>reasonDialog.close());
  reasonItems.addEventListener('click',()=>{reasonDialog.close();openPending();});
  function addWarning(cell,info){
    const mark=node('button','!');mark.type='button';mark.className='seller-warning-mark';
    mark.title=info.reason+' Como resolver: '+info.action;mark.setAttribute('aria-label',info.label+'. '+mark.title);cell.title=mark.title;
    mark.addEventListener('click',()=>{reasonTitle.textContent=info.label;reasonText.textContent=info.reason;actionText.textContent=info.action;reasonItems.hidden=!payload?.total_pendencias_itens;if(!reasonDialog.open)reasonDialog.showModal();});cell.append(mark);
  }
  function cellPending(data,key){
    if(data.financeiro_pendente)return key==='resultado';
    if(data.itens===0)return false;
    return Object.prototype.hasOwnProperty.call(data,key)&&data[key]==null||key==='origem_cpv'&&/pendente/i.test(data[key]||'');
  }
  function rowCells(data,cols,clickable=false){
    const tr=node('tr');
    for(const [key,,type] of cols){
      const td=node('td');
      if(clickable&&key==='regional'){
        const b=node('button',data[key]+(data.fora_catalogo_regional?' *':''));b.className='seller-region-link';b.type='button';b.addEventListener('click',()=>openDetail(data[key]));td.append(b);
      }else if(cellPending(data,key)){
        const info=pendingInfo(data,key);td.textContent=info.label;td.classList.add('seller-pending');addWarning(td,info);
      }else if(data.financeiro_pendente&&key!=='regional'||data[key]==null||data[key]===''){
        td.textContent='\u2014';if(data.itens===0)td.title='Sem movimento no recorte; indicador nao aplicavel.';
      }else td.textContent=value(data[key],type);
      if(key==='diferenca'&&data[key]!=null)td.classList.add(Number(data[key])<0?'seller-negative':'seller-positive');
      tr.append(td);
    }
    return tr;
  }
  function render(){if(!payload)return;const table=$('seller-table');head(table,columns,true);const rows=[...payload.linhas];if(sorted)rows.sort((a,b)=>{const x=a[sortKey],y=b[sortKey];if(x==null)return y==null?0:1;if(y==null)return -1;return direction*(sortKey==='regional'?String(x).localeCompare(String(y),'pt-BR'):Number(x)-Number(y));});table.tBodies[0].replaceChildren(...rows.map(r=>rowCells(r,columns,true)));table.tFoot.replaceChildren(...payload.consolidacoes.map(r=>rowCells(r,columns)));}
  async function query(override){
    const own=++sequence;controller?.abort();controller=new AbortController();payload=null;$('seller-pending-items').hidden=true;$('seller-export').disabled=true;if($('seller-dialog').open)$('seller-dialog').close();if(reasonDialog.open)reasonDialog.close();
    $('seller-table').tBodies[0].replaceChildren();$('seller-table').tFoot.replaceChildren();$('seller-period').textContent='—';$('seller-validation').textContent='—';
    const p=override||params();persist();status('Calculando a análise com o motor FOB operacional…');form.setAttribute('aria-busy','true');
    try{const data=await apiGet(endpoint,p,{signal:controller.signal});if(own!==sequence)return;
      if(!Array.isArray(data.linhas)||!Array.isArray(data.produtos)||!Array.isArray(data.consolidacoes))throw new Error('Resposta incompleta da análise regional.');
      payload=data;applied={...p};$('seller-pending-items').hidden=!data.total_pendencias_itens;$('seller-pending-items').textContent='Ver '+data.total_pendencias_itens+' itens pendentes';state.save({applied});fillSelect('seller-region',data.filtros.regionais);fillSelect('seller-product',data.filtros.produtos.map(r=>({...r,label:r.codigo+' — '+r.descricao})),'label','codigo');
      for(const [id,key] of [['seller-unit','unidade'],['seller-region','regional'],['seller-product','produto']])$(id).value=p[key]||'';
      render();$('seller-period').textContent=p.data_inicio.split('-').reverse().join('/')+' a '+p.data_fim.split('-').reverse().join('/');
      const v=data.validacao;$('seller-validation').textContent='Soma das diferenças antes do filtro regional: '+value(v.diferenca_global,'money');if(v.diferenca_global==null)addWarning($('seller-validation'),pendingInfo({},'diferenca'));
      $('seller-scope').textContent=`${v.itens_fora_catalogo} itens (${value(v.peso_fora_catalogo,'weight')} kg) fora dos blocos do catálogo. Peso da base selecionada: ${value(v.peso_base,'weight')} kg. Regionais adicionais: ${v.regionais_adicionais.join(', ')||'nenhuma'}. Este equilíbrio não comprova igualdade com o Excel.`;
      const pending=data.linhas.reduce((n,r)=>n+r.pendentes,0);const costsPending=data.linhas.reduce((n,r)=>n+(r.pendentes_resultado??(r.resultado==null&&Number(r.peso)>0?r.itens:0)),0);$('seller-cost-status').textContent=costsPending?costsPending+' itens aguardam CPV ou rateio mensal.':'Resultado projetado calculado com os custos disponíveis da competência.';status('Consulta concluída. '+(pending?pending+' itens com FOB pendente. ':'')+'Impostos e abrangência dos consolidados aguardam conferência dos responsáveis.');$('seller-export').disabled=false;
      const months=data.contexto?.fechamento||[];
      if(data.total_pendencias_itens>0&&months.length&&months.every(m=>m.cadastrada))$('seller-cost-status').textContent=`CPV e despesas mensais cadastrados. ${data.total_pendencias_itens} itens com FOB pendente impedem concluir o rateio. Clique no ! para conferir motivos e orientações.`;
    }catch(error){if(error.name==='AbortError'||own!==sequence)return;status(error.message,true);const tr=node('tr'),td=node('td','Consulta indisponível. Verifique a mensagem acima.');td.colSpan=12;tr.append(td);$('seller-table').tBodies[0].replaceChildren(tr);}finally{if(own===sequence)form.removeAttribute('aria-busy');}
  }
  function openDetail(regional){$('seller-pending-help').hidden=true;$('seller-products').classList.remove('seller-pending-table');detailColumns=productColumns;detailRows=payload.produtos.filter(r=>r.regional===regional).map(r=>({...r,motivo_pendencia:(r.motivos_pendencia||[]).join('; ')}));$('seller-detail-title').textContent=regional;$('seller-detail-count').textContent=detailRows.length+' produtos · '+$('seller-period').textContent;const table=$('seller-products');head(table,productColumns);table.tBodies[0].replaceChildren(...detailRows.map(r=>rowCells(r,productColumns)));if(!detailRows.length){const tr=node('tr'),td=node('td','Nenhum produto no recorte.');td.colSpan=productColumns.length;tr.append(td);table.tBodies[0].append(tr);}$('seller-dialog').showModal();}
  function csv(rows,cols,name){
    const writer=CsvExport.writer([...cols.map(c=>c[1]),'Motivos das pendencias','Como resolver'],cols.flatMap((c,i)=>!['text','pending'].includes(c[2])?[i]:[]));
    writer.append(rows.map(r=>{
      const pending=cols.filter(([key])=>cellPending(r,key));
      return [...cols.map(([key])=>cellPending(r,key)?pendingInfo(r,key).label:r[key]??''),pending.map(([key,label])=>label+': '+pendingInfo(r,key).reason).join(' | '),pending.map(([key,label])=>label+': '+pendingInfo(r,key).action).join(' | ')];
    }));writer.download(name);
  }
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
  document.querySelectorAll('.seller-note span.seller-review-flag').forEach(el=>addWarning(el,pendingInfo({financeiro_pendente:true},'resultado')));
  $('seller-pending-items').addEventListener('click',()=>openPending());
  $('seller-export').addEventListener('click',()=>{if(payload)csv([...payload.linhas,...payload.consolidacoes],columns,`analise-vendedor-pai-${applied.data_inicio}-${applied.data_fim}.csv`);});
  $('seller-detail-export').addEventListener('click',()=>csv(detailRows,detailColumns,`produtos-regional-${applied.data_inicio}-${applied.data_fim}.csv`));
  $('seller-close').addEventListener('click',()=>$('seller-dialog').close());
  form.addEventListener('submit',e=>{e.preventDefault();query();});form.addEventListener('change',()=>{persist();if(payload)status('Filtros alterados. Consulte para aplicá-los.');});window.addEventListener('pagehide',persist);
  $('seller-clear-filters').addEventListener('click',()=>{
    controller?.abort();sequence++;payload=null;applied=null;$('seller-pending-items').hidden=true;
    for(const id of ['seller-start','seller-end','seller-unit','seller-region','seller-product'])$(id).value='';
    state.save({applied:null});persist();if($('seller-dialog').open)$('seller-dialog').close();if(reasonDialog.open)reasonDialog.close();
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
