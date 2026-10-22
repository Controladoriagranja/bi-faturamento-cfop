/* Somente GET. Valores financeiros e associações são resolvidos pela API. */
(() => {
  const $=id=>document.getElementById(id), key='bi-faturamento-custos-filtros-v1';
  const base=APP_CONFIG.custosFOB;
  const escape=value=>String(value??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number=(value,digits=3)=>value===null||value===undefined?'Pendente':Number(value).toLocaleString('pt-BR',{maximumFractionDigits:digits});
  const time=value=>value?new Date(value).toLocaleString('pt-BR'):'—';
  let page=1,total=0,applied=null,request=0;
  function save(){try{sessionStorage.setItem(key,JSON.stringify({inicio:$('costs-start').value,fim:$('costs-end').value}));}catch(_){}}
  function restore(){
    const now=new Date(),month=new Date(now.getFullYear(),now.getMonth(),1);
    const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    $('costs-start').value=iso(month);$('costs-end').value=iso(now);
    try{const old=JSON.parse(sessionStorage.getItem(key)||'null');if(old){$('costs-start').value=old.inicio;$('costs-end').value=old.fim;}}catch(_){}
  }
  async function status(){
    $('costs-refresh').disabled=true;$('costs-status').textContent='Consultando alimentação…';
    try{
      const data=await apiGet(base+'/status'),valid=data.ultima_importacao_valida;
      const latest=data.execucoes?.[0];
      $('costs-status').textContent=valid?`Último lote válido: ${time(valid.executado_em)}.${latest?.status==='REJEITADO'?' A última tentativa foi rejeitada; o lote válido continua aplicado.':''}`:'Nenhuma importação válida registrada.';
      $('costs-files').innerHTML=['Fretes.xlsx','Despesas.xlsx','Comissoes.xlsx'].map(name=>`<article class="costs-file"><strong>${name}</strong><p>${valid?.arquivos?.[name]?'Arquivo recebido no último lote válido':'Sem importação válida'}</p><p>${valid?escape(time(valid.executado_em)):'Aguardando alimentação'}</p></article>`).join('');
      $('costs-coverage').textContent=(data.cadastros||[]).map(r=>`${r.tipo}: ${r.quantidade} cadastros (${r.inicio} a ${r.fim})`).join(' · ')||'Sem cadastros ativos. Comissão e demais despesas ausentes mantêm o FOB pendente.';
      $('costs-monthly').innerHTML=(data.competencias_januaria||[]).map(r=>`<tr><td>${escape(r.competencia)}</td><td>${escape(number(r.custo_kg,10))}</td><td>${escape(r.versao)}</td><td>${escape(time(r.atualizado_em))}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Sem competências cadastradas; frete fixo de Januária pendente.</td></tr>';
    }catch(error){$('costs-status').textContent=error.message;$('costs-files').replaceChildren();$('costs-coverage').textContent='Nenhum dado foi presumido. A integração depende da homologação do banco e da API.';$('costs-monthly').innerHTML='<tr><td colspan="4" class="empty">Consulta indisponível.</td></tr>';}
    finally{$('costs-refresh').disabled=false;}
  }
  async function query(){
    if(!applied)return;
    const current=++request;$('costs-message').textContent='Consultando itens…';
    $('costs-prev').disabled=true;$('costs-next').disabled=true;
    try{
      const data=await apiGet(base+'/pendencias',{...applied,pagina:page,por_pagina:50});
      if(current!==request)return;
      total=data.total_registros;
      $('costs-body').innerHTML=(data.linhas||[]).map(r=>`<tr><td>${escape(r.empresa_contexto)} / ${escape(r.unidade_documento)}</td><td>${escape(r.serie)} / ${escape(r.nota_numero)} / ${escape(r.ano_nf)}</td><td>${escape(r.produto)} · ${escape(r.produto_descricao)}<br>Cliente ${escape(r.cliente)}</td><td>${escape(number(r.peso_item))}</td><td>${escape(number(r.peso_total_nf))}</td><td>${escape(r.situacao)}<br>${escape(r.status_custo)}</td><td>${escape(number(r.custo_kg,10))}</td><td>${escape(r.origem_custo)}<br>${escape(r.motivo)}</td></tr>`).join('')||'<tr><td colspan="8" class="empty">Nenhuma pendência na origem para este período.</td></tr>';
      $('costs-count').textContent=`${total.toLocaleString('pt-BR')} itens`;
      $('costs-page').textContent=`Página ${page} de ${Math.max(1,Math.ceil(total/50))}`;
      $('costs-message').textContent=`Consulta de ${applied.data_inicio} a ${applied.data_fim}. Itens tipo 1 com frete zerado ou ausente na origem. Preenchimentos importados substituem o frete, sem duplicação; o frete original válido continua utilizado.`;
      $('costs-prev').disabled=page<=1;$('costs-next').disabled=page*50>=total;
    }catch(error){if(current===request){$('costs-message').textContent=error.message;$('costs-body').innerHTML='<tr><td colspan="8" class="empty">Consulta indisponível; não são exibidos valores antigos como atuais.</td></tr>';$('costs-count').textContent='—';$('costs-page').textContent='—';}}
  }
  restore();$('costs-refresh').addEventListener('click',status);
  $('costs-components-query').addEventListener('click',async()=>{
    const start=$('costs-start').value,end=$('costs-end').value;
    if(!start||!end||end<start){$('costs-components').textContent='Selecione um período válido.';return;}
    $('costs-components-query').disabled=true;$('costs-components').textContent='Conferindo componentes…';
    try{
      const data=await apiGet(APP_CONFIG.fob.resumo,{data_inicio:start,data_fim:end});
      if(data.contexto?.modo!=='planilhas_mestre'){$('costs-components').textContent='A nova alimentação ainda não está ativa na API. O comparativo anterior continua preservado.';return;}
      const names={frete:'Frete',comissao:'Comissão',adicional_comissao:'Adicional',contrato:'Contrato',contrato_administracao:'Administração',logistica_reversa:'Logística reversa',pallet:'Pallet',descarga:'Descarga'};
      const text=Object.entries(data.total?.componentes||{}).map(([name,c])=>`${names[name]||name}: ${c.pendentes} itens pendentes`).join(' · ');
      $('costs-components').textContent=text?`${start} a ${end} · ${text}`:'Nenhum componente disponível.';
    }catch(error){$('costs-components').textContent=error.message;}
    finally{$('costs-components-query').disabled=false;}
  });
  $('costs-filters').addEventListener('change',save);
  $('costs-filters').addEventListener('submit',event=>{event.preventDefault();save();const start=$('costs-start').value,end=$('costs-end').value;const days=(Date.parse(end)-Date.parse(start))/86400000;if(!Number.isFinite(days)||days<0||days>31){$('costs-message').textContent='Selecione até 32 dias, com data final igual ou posterior à inicial.';return;}applied={data_inicio:start,data_fim:end};page=1;query();});
  $('costs-prev').addEventListener('click',()=>{if(page>1){page--;query();}});
  $('costs-next').addEventListener('click',()=>{if(page*50<total){page++;query();}});
})();
