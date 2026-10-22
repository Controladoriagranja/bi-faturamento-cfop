/* Padrão do Bi-Matrizes: HTMLs próprios, data-page e menu compartilhado. */
(() => {
  function redirectLegacyHash(){
    if(document.body.dataset.page==='faturamento'&&location.hash==='#comparativo-fob'){
      location.replace(new URL('comparativo-fob.html',location.href));return true;
    }
    return false;
  }
  if(redirectLegacyHash())return;
  window.addEventListener('hashchange',redirectLegacyHash);
  const current=document.body.dataset.page;
  const pages=[{id:'faturamento',href:'index.html',label:'Faturamento por Vendedor Pai'},{id:'comparativo-fob',href:'comparativo-fob.html',label:'Comparativo PM FOB'},{id:'custos-pendencias',href:'custos-pendencias.html',label:'Custos e Pendências'}];
  if(APP_CONFIG.legacyFreightEditor)pages.push({id:'frete-pendente',href:'frete-pendente.html',label:'Fretes · versão anterior'});
  const root=document.createElement('div');root.className='side-nav-root';
  root.innerHTML=`<button class="side-nav-rail" type="button" aria-label="Abrir menu" aria-expanded="false" aria-controls="comercial-menu"><span class="side-nav-hamburger" aria-hidden="true"><i></i><i></i><i></i></span></button><div class="side-nav-overlay" aria-hidden="true"></div><aside id="comercial-menu" class="side-nav-panel" aria-label="Navegação principal" aria-hidden="true" inert><div class="side-nav-panel-head"><img src="assets/img/logo-granja-brasilia-clara.png" alt="Granja Brasília"><button class="side-nav-close" type="button" aria-label="Fechar menu">×</button></div><div class="side-nav-section-title">COMERCIAL · FATURAMENTO</div><nav>${pages.map(page=>`<a href="${page.href}" class="side-nav-link ${page.id===current?'active':''}" ${page.id===current?'aria-current="page"':''}>${page.label}</a>`).join('')}</nav><p class="side-nav-foot">Granja Brasília<br>Inteligência comercial</p></aside>`;
  document.body.prepend(root);document.body.classList.add('has-side-nav');
  const rail=root.querySelector('.side-nav-rail'),panel=root.querySelector('aside'),close=root.querySelector('.side-nav-close');
  function setOpen(open,focus=true){
    root.classList.toggle('open',open);rail.setAttribute('aria-expanded',String(open));panel.setAttribute('aria-hidden',String(!open));panel.inert=!open;document.body.classList.toggle('side-nav-open',open);
    if(focus)(open?close:rail).focus();
  }
  rail.addEventListener('click',()=>setOpen(true));close.addEventListener('click',()=>setOpen(false));root.querySelector('.side-nav-overlay').addEventListener('click',()=>setOpen(false));
  document.addEventListener('keydown',event=>{
    if(!root.classList.contains('open'))return;
    if(event.key==='Escape'){setOpen(false);return;}
    if(event.key==='Tab'){
      const all=[close,...panel.querySelectorAll('a')],first=all[0],last=all.at(-1);
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    }
  });
  root.querySelectorAll('a').forEach(link=>link.addEventListener('click',event=>{
    if(link.getAttribute('aria-current')==='page'&&!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey){event.preventDefault();setOpen(false);}
  }));
  // Ao voltar pelo navegador, a página pode ser restaurada com o menu aberto.
  window.addEventListener('pageshow',()=>setOpen(false,false));
})();
