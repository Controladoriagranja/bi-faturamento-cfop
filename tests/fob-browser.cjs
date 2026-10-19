/* Somente frontend estático + respostas sintéticas interceptadas. Nenhum backend é iniciado. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..'),artifacts=path.join(root,'artifacts/fob/tela');fs.mkdirSync(artifacts,{recursive:true});
const costs=['frete','comissao','adicional_comissao','contrato','contrato_administracao','logistica_reversa','pallet','descarga'];
// Fixture explicitamente sintética; nunca é incluída em assets/ nem na aplicação.
const rows=Array.from({length:65},(_,i)=>{
  const pending=i<60&&i%17===0,canal=i<60?'Varejo':i<63?'Atacado':'Subprodutos';
  return {identificacao:{data:'2026-10-01',unidade_documento:i%2?'111':'10',nota_numero:String(1000+i),produto:'349',cliente:'9880',cfop:'5102'},
    familia:i%2?'FILÉ DE PEITO':'FRANGO INTEIRO',canal,peso:'10',peso_excel:'10',preco_praticado_kg:'10',preco_fob_kg:pending?null:'9.7',valor_fob:pending?null:'97',valor_fob_excel:'97',
    origem_registro:'Origem sintética de teste',origem_excel:'Referência sintética!7',status:pending?'pendente':'calculado',provisorio:i===1,
    divergencias_entrada:{},pendencias:pending?['frete']:[],dados_entrada:{frete:'1'},
    componentes:Object.fromEntries(costs.map(k=>[k,{value:k==='frete'?(pending?null:'0.2'):k==='comissao'?'0.1':'0',origin:'Cadastro sintético de teste',formula:'Fórmula sintética para inspeção',status:k==='frete'&&pending?'pendente_manual':'calculado'}])),
    ...Object.fromEntries(costs.map(k=>[k+'_kg',k==='frete'?(pending?null:'0.2'):k==='comissao'?'0.1':'0']))};
});
function total(list){
  const weight=list.length*10,pending=list.filter(r=>r.valor_fob===null).length,partial=list.filter(r=>r.valor_fob!==null).length*97;
  return {itens:list.length,peso:String(weight),peso_excel:String(weight),diferenca_peso:'0',peso_pendente:String(pending*10),pendentes:pending,ausentes:0,provisorios:list.filter(r=>r.provisorio).length,divergencias:0,preco_praticado_kg:list.length?'10':null,
    valor_fob:pending?null:String(partial),valor_fob_parcial:String(partial),pm_fob_kg:pending||!weight?null:'9.7',valor_fob_excel:String(list.length*97),pm_fob_excel:weight?'9.7':null,diferenca_fob:pending?null:'0',
    componentes:Object.fromEntries(costs.map(k=>[k,{valor:k==='frete'&&pending?null:'0',valor_parcial:'0',media_kg:k==='frete'?(pending?null:'0.2'):k==='comissao'?'0.1':'0',pendentes:k==='frete'?pending:0}]))};
}
function select(params){return rows.filter(row=>['familia','canal','unidade'].every(k=>!params.getAll(k).length||params.getAll(k).includes(k==='unidade'?row.identificacao.unidade_documento:row[k]))&&
  (params.get('pendentes')!=='1'||row.valor_fob===null)&&(!params.get('busca')||JSON.stringify(row.identificacao).includes(params.get('busca'))));}
function summary(list){
  const families=[...new Set(list.map(r=>r.familia))].sort(),channels=['Varejo','Atacado','Subprodutos'];
  return {contexto:{data_inicio:'2026-10-01',data_fim:'2026-10-04',linhas_fora_perimetro:41,consulta_nf_806684:'consulta_bruta_indisponivel'},total:total(list),
    grupos:families.flatMap(familia=>channels.map(canal=>({familia,canal,...total(list.filter(r=>r.familia===familia&&r.canal===canal))}))),
    familias:families.map(familia=>({familia,...total(list.filter(r=>r.familia===familia))})),canais:channels.map(canal=>({canal,...total(list.filter(r=>r.canal===canal))}))};
}
const mime={'.html':'text/html','.css':'text/css','.js':'text/javascript','.png':'image/png','.woff2':'font/woff2'};
const server=http.createServer((req,res)=>{
  const requested=decodeURIComponent(new URL(req.url,'http://localhost').pathname),file=path.resolve(root,'.'+(requested==='/'?'/index.html':requested));
  if(!file.startsWith(root+path.sep)||!(/\/assets\//.test(requested)||['/','/index.html','/comparativo-fob.html'].includes(requested))){res.writeHead(404).end();return;}
  fs.readFile(file,(error,data)=>{res.writeHead(error?404:200,{'content-type':mime[path.extname(file)]||'application/octet-stream'});res.end(error?'':data);});
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
  try{
    browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    const context=await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true}),page=await context.newPage(),errors=[],requests=[];
    await context.addInitScript(()=>{sessionStorage.setItem('granjabi_auth_token','teste-local');if(!localStorage.getItem('bi-zootecnico-theme'))localStorage.setItem('bi-zootecnico-theme','light');});
    page.on('pageerror',error=>errors.push(error.message));let fail=0,delay=false;
    const options={unidade:[{value:'10',label:'10 — Ave Nova'},{value:'111',label:'111 — Real Alimentos'}],familia:['FILÉ DE PEITO','FRANGO INTEIRO'],canal:['Varejo','Atacado','Subprodutos'],periodo_disponivel:{data_inicio:'2026-10-01',data_fim:'2026-10-04'}};
    const old={vendedor_pai:'Varejo Centro-Oeste',qtde_nfs:10,qtde_produto_por_nf:'2.5',peso_por_nf:'200',ticket_medio_por_nf:'1000'};
    await page.route('https://api-bi-granja.controladoriagb05.workers.dev/**',async route=>{
      const url=new URL(route.request().url()),params=url.searchParams,isFOB=url.pathname.includes('comparativo-fob');requests.push({path:url.pathname,params});
      assert.equal(route.request().headers().authorization,'Bearer teste-local');
      if(isFOB&&fail){await route.fulfill({status:fail,json:{mensagem:fail===503?'Falha sintética de conexão.':'Rota ausente.'}});return;}
      if(isFOB&&delay)await new Promise(resolve=>setTimeout(resolve,180));
      let data;
      if(url.pathname.endsWith('/filtros'))data=options;
      else if(!isFOB)data=url.pathname.endsWith('/resumo')?{grupos:[old],total:old,periodo:options.periodo_disponivel,unidades:[]}:
        {linhas:[{data:'2026-10-01',nota_numero:'1000',produto:'349',peso:'10'}],colunas:['data','nota_numero','produto','peso'],total_registros:1,totais:{qtde_nfs:1,qtde_itens:1,peso_total:'10',valor_total:'100'}};
      else {
        const list=select(params);data=summary(list);
        if(url.pathname.endsWith('/detalhes')){
          const sort=params.get('ordenar_por')||'nota_numero',direction=params.get('ordem')==='desc'?-1:1;
          list.sort((a,b)=>direction*String(a[sort]??a.identificacao[sort]??'').localeCompare(String(b[sort]??b.identificacao[sort]??''),'pt-BR',{numeric:true}));
          const pageNum=Number(params.get('pagina')||1),size=Number(params.get('por_pagina')||50);
          Object.assign(data,{linhas:list.slice((pageNum-1)*size,pageNum*size),total_registros:list.length,pagina:pageNum,por_pagina:size});
        }
      }
      await route.fulfill({status:200,json:data});
    });
    const ready=()=>page.locator('#fob-status').filter({hasText:'Comparativo atualizado.'}).waitFor();
    const detailReady=()=>page.locator('#fob-items-status').filter({hasText:'Abra “Ver cálculo”'}).waitFor();
    const nav=async name=>{
      const file=name==='faturamento'?'index.html':'comparativo-fob.html';
      await page.getByRole('button',{name:'Abrir menu',exact:true}).click();
      await Promise.all([page.waitForURL('**/'+file),page.locator(`.side-nav-link[href="${file}"]`).click()]);
    };
    await page.goto(`http://127.0.0.1:${server.address().port}`);await page.getByText('Relatório atualizado.',{exact:true}).waitFor();
    assert.equal(requests.filter(r=>r.path.includes('comparativo-fob')).length,0);
    const oldHTML=await page.locator('#report-body').innerHTML();assert.equal(await page.locator('#view-faturamento .sort-button').count(),5);
    assert.equal(await page.locator('#view-comparativo-fob, script[src="assets/js/fob.js"]').count(),0);
    assert.equal(await page.locator('.side-nav-link[aria-current=page]').getAttribute('href'),'index.html');
    // Preserva também filtros editados antes de consultar, sem mudar a consulta exibida.
    await page.locator('#data-inicio').fill('2026-10-02');
    await page.locator('#filter-unidade button').click();await page.locator('#filter-unidade input[value="10"]').check();await page.keyboard.press('Escape');
    const beforeFOB=requests.length;
    await nav('comparativo-fob');await ready();assert.equal(await page.locator('#fob-cards article').count(),3);assert.equal(await page.locator('#view-faturamento').count(),0);
    assert.equal(requests.slice(beforeFOB).filter(r=>r.path.includes('faturamento-nf')).length,0);
    assert.equal(await page.locator('script[src="assets/js/dashboard.js"], .details-dialog').count(),0);
    assert.equal(await page.locator('.side-nav-link[aria-current=page]').getAttribute('href'),'comparativo-fob.html');
    assert.ok((await page.locator('#fob-cards article').first().textContent()).includes('FOB em aberto'));
    await page.locator('#fob-reference').check();assert.ok((await page.locator('#fob-cards').textContent()).includes('Diferença de peso'));
    await page.screenshot({path:path.join(artifacts,'comparativo-desktop.png'),fullPage:true});
    await page.locator('#fob-cards article').first().getByRole('button').click();await detailReady();
    assert.equal(requests.at(-1).params.get('canal'),'Varejo');assert.equal(await page.locator('#fob-items-body tr').count(),50);
    await page.locator('#fob-items-next').click();await detailReady();assert.equal(requests.at(-1).params.get('pagina'),'2');assert.equal(await page.locator('#fob-items-body tr').count(),10);
    await page.locator('#fob-items-head button').filter({hasText:/^Peso /}).click();await detailReady();assert.equal(requests.at(-1).params.get('ordenar_por'),'peso');assert.equal(requests.at(-1).params.get('pagina'),'1');
    await page.locator('#fob-items-body button').first().click();assert.ok((await page.locator('.fob-item-audit').textContent()).includes('Cadastro sintético de teste'));
    assert.ok((await page.locator('.fob-item-audit').textContent()).includes('peso * preco_fob_kg'));
    await page.screenshot({path:path.join(artifacts,'itens-auditoria.png')});
    await page.locator('#fob-items-pending').check();await detailReady();assert.equal(requests.at(-1).params.get('pendentes'),'1');assert.equal(await page.locator('#fob-items-body tr').count(),4);
    await page.locator('#fob-items-pending').uncheck();await detailReady();
    const downloadPromise=page.waitForEvent('download');await page.locator('#fob-items-export').click();const download=await downloadPromise;
    const csvPath=path.join(artifacts,'itens-teste.csv');await download.saveAs(csvPath);assert.equal(fs.readFileSync(csvPath,'utf8').trim().split(/\r?\n/).length,61);
    await page.keyboard.press('Escape');assert.equal(await page.locator('dialog[open]').count(),0);
    await page.locator('[data-fob-mode=costs]').click();assert.ok((await page.locator('#fob-table thead').textContent()).includes('Logística reversa /kg'));
    await page.locator('[data-fob-mode=matrix]').click();
    await page.locator('#fob-filter-unidade button').click();await page.locator('#fob-filter-unidade input[value="10"]').check();await page.locator('#fob-filter-unidade input[value="111"]').check();await page.keyboard.press('Escape');
    await page.locator('#fob-filters button[type=submit]').click();await ready();assert.deepEqual(requests.at(-1).params.getAll('unidade'),['10','111']);
    // Detalhe sempre mantém os filtros efetivamente aplicados, mesmo após mudar o formulário.
    await page.locator('#fob-inicio').fill('2026-10-02');await page.locator('#fob-table tbody th button').first().click();await detailReady();assert.equal(requests.at(-1).params.get('data_inicio'),'2026-10-01');
    await page.locator('#fob-items-query').fill('ausente');await page.locator('#fob-items-search button').click();await detailReady();assert.ok(await page.locator('#fob-items-export').isDisabled());
    await page.locator('#fob-items-close').click();await page.locator('#fob-inicio').fill('2026-10-01');
    await page.setViewportSize({width:390,height:844});await page.locator('[data-theme-toggle]').click();
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.ok(await page.locator('.fob-table-scroll').evaluate(e=>e.scrollWidth>e.clientWidth));
    await page.screenshot({path:path.join(artifacts,'comparativo-mobile-dark.png'),fullPage:true});
    await page.locator('#fob-cards article').first().getByRole('button').click();await detailReady();
    assert.ok(await page.locator('.fob-dialog').evaluate(e=>e.getBoundingClientRect().right<=innerWidth));await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Abrir menu',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('.side-nav-panel').getBoundingClientRect().left>=-1);
    assert.ok(await page.locator('.side-nav-link[aria-current=page]').isVisible());
    await page.screenshot({path:path.join(artifacts,'menu-mobile.png')});await page.keyboard.press('Escape');
    assert.equal(await page.locator('.side-nav-rail').getAttribute('aria-expanded'),'false');
    // Formulário FOB e preferências têm estado próprio, incluindo rascunho não consultado.
    await page.locator('#fob-fim').fill('2026-10-03');
    await page.locator('#fob-filter-familia button').click();await page.locator('#fob-filter-familia input[value="FILÉ DE PEITO"]').check();await page.keyboard.press('Escape');
    await page.locator('#fob-filter-canal button').click();await page.locator('#fob-filter-canal input[value="Atacado"]').check();await page.keyboard.press('Escape');
    await page.locator('[data-fob-mode=costs]').click();
    await nav('faturamento');await page.locator('#status').filter({hasText:'Relatório atualizado.'}).waitFor();
    assert.equal(await page.locator('#report-body').innerHTML(),oldHTML);
    assert.equal(await page.locator('#data-inicio').inputValue(),'2026-10-02');assert.ok(await page.locator('#filter-unidade input[value="10"]').isChecked());
    assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
    await page.locator('#report-body th button').click();await page.locator('#details-status').filter({hasText:'Detalhes carregados.'}).waitFor();
    assert.equal(requests.at(-1).params.get('data_inicio'),'2026-10-01');assert.equal(requests.at(-1).params.get('unidade'),null);await page.keyboard.press('Escape');
    await page.locator('#filters-form button[type=submit]').click();await page.locator('#status').filter({hasText:'Relatório atualizado.'}).waitFor();
    assert.equal(requests.at(-1).params.get('data_inicio'),'2026-10-02');assert.deepEqual(requests.at(-1).params.getAll('unidade'),['10']);
    await nav('comparativo-fob');await ready();
    assert.equal(await page.locator('#fob-fim').inputValue(),'2026-10-03');assert.ok(await page.locator('#fob-filter-familia input[value="FILÉ DE PEITO"]').isChecked());
    assert.ok(await page.locator('#fob-filter-canal input[value="Atacado"]').isChecked());assert.ok(await page.locator('#fob-filter-unidade input[value="111"]').isChecked());
    assert.ok(await page.locator('#fob-reference').isChecked());assert.equal(await page.locator('[data-fob-mode=costs]').getAttribute('aria-pressed'),'true');
    assert.equal(requests.at(-1).params.get('data_fim'),'2026-10-04');assert.equal(requests.at(-1).params.get('familia'),null);
    // Aplica o rascunho, recarrega e navega pelo histórico: os filtros continuam por página.
    await page.locator('#fob-filters button[type=submit]').click();await ready();assert.equal(requests.at(-1).params.get('canal'),'Atacado');
    await page.reload();await ready();assert.equal(requests.at(-1).params.get('data_fim'),'2026-10-03');assert.equal(requests.at(-1).params.get('familia'),'FILÉ DE PEITO');
    await page.goBack();await page.locator('#status').filter({hasText:'Relatório atualizado.'}).waitFor();assert.equal(await page.locator('#data-inicio').inputValue(),'2026-10-02');
    await page.goForward();await ready();assert.equal(await page.locator('#fob-fim').inputValue(),'2026-10-03');
    // Acesso direto independente, sem disparar consultas do relatório inicial.
    const direct=await context.newPage();await direct.route('https://api-bi-granja.controladoriagb05.workers.dev/**',route=>route.fulfill({json:route.request().url().includes('/filtros')?options:summary(rows)}));
    await direct.goto(`http://127.0.0.1:${server.address().port}/comparativo-fob.html`);await direct.locator('#fob-cards article').first().waitFor();
    assert.equal(await direct.locator('body').getAttribute('data-page'),'comparativo-fob');assert.equal(await direct.locator('#report-body').count(),0);await direct.close();
    fail=503;await page.locator('#fob-filters button[type=submit]').click();await page.getByText('Erro na API: 503 - Falha sintética de conexão.',{exact:true}).waitFor();
    assert.equal(await page.locator('#fob-cards article').count(),0);assert.equal(await page.locator('#fob-table tfoot tr').count(),0);
    fail=0;await page.locator('#fob-filters button[type=submit]').click();await ready();
    delay=true;await page.locator('#fob-cards article').first().getByRole('button').click();await page.locator('#fob-items-close').click();await page.waitForTimeout(250);assert.equal(await page.locator('dialog[open]').count(),0);delay=false;
    fail=404;await page.reload();await page.locator('#fob-status').filter({hasText:'O módulo Comparativo FOB ainda não está disponível'}).waitFor();
    fail=0;await page.goto(`http://127.0.0.1:${server.address().port}/index.html#comparativo-fob`);await page.waitForURL('**/comparativo-fob.html');await ready();
    assert.deepEqual(errors,[]);await context.close();
    console.log('OK: dois HTMLs independentes, acesso direto e hash antigo, menu/ativo, filtros separados (rascunho e consulta), recarga/histórico, tema, relatório preservado, matriz/custos, itens/auditoria, CSV, paginação/ordenação, mobile, 503/404 e cancelamento. Nenhum backend/banco executado.');
  }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
