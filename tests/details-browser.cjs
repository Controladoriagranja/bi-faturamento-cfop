/* Serviço real do módulo com SQL em DuckDB; somente dados sintéticos locais. */
const {spawn}=require('node:child_process');
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict'), net=require('node:net');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root=path.resolve(__dirname,'..');
const artifacts=path.join(root,'artifacts');fs.mkdirSync(artifacts,{recursive:true});
(async()=>{
  const socket=net.createServer();await new Promise(r=>socket.listen(0,'127.0.0.1',r));const port=socket.address().port;await new Promise(r=>socket.close(r));
  const server=spawn(process.env.PYTHON_EXECUTABLE || 'python',[process.env.DETAILS_TEST_SERVER || path.join(__dirname,'validar_detalhes.py'),'--serve',String(port)],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
  let logs='';server.stdout.on('data',b=>logs+=b);server.stderr.on('data',b=>logs+=b);server.on('error',e=>logs+=e.message);
  let browser;
  try {
    const url=`http://127.0.0.1:${port}`;
    let ready=false;
    for(let attempt=0;attempt<100;attempt++) {try{ready=(await fetch(url+'/api/bi/faturamento-nf/filtros')).ok;}catch{}if(ready)break;await new Promise(r=>setTimeout(r,100));}
    assert.ok(ready,logs);
    browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
    const page=await context.newPage(), errors=[], requests=[];
    page.on('pageerror',e=>errors.push(e.message));
    await context.addInitScript(()=>sessionStorage.setItem('granjabi_auth_token','teste-local'));
    await page.route('**/assets/js/config.js',async route=>{
      const response=await route.fetch();await route.fulfill({response,body:(await response.text())+'\nAPP_CONFIG.API_URL = location.origin;'});
    });
    let fail=false, delay=false;
    await page.route('**/api/bi/faturamento-nf/detalhes?**',async route=>{
      const req=route.request();assert.equal(req.headers().authorization,'Bearer teste-local');requests.push(new URL(req.url()).searchParams);
      if(fail){await route.fulfill({status:401,json:{detail:'Sessão expirada no teste.'}});return;}
      if(delay)await new Promise(r=>setTimeout(r,500));
      await route.continue();
    });
    const wait=()=>page.locator('#details-status').filter({hasText:'Detalhes carregados.'}).waitFor();
    await page.goto(url);await page.getByText('Relatório atualizado.',{exact:true}).waitFor();
    const first=page.locator('#report-body tr').first();
    // Mudar o formulário sem consultar não muda os filtros do detalhamento.
    await page.locator('#data-inicio').fill('2026-10-04');
    await first.locator('th button').click();await wait();
    assert.equal(requests.at(-1).get('data_inicio'),'2026-10-01');
    assert.equal(requests.at(-1).get('vendedor_pai'),'Varejo Centro-Oeste');
    assert.equal(requests.at(-1).get('visao'),'itens');
    assert.ok((await page.locator('#details-page').textContent()).includes('624 registros'));
    assert.equal(await page.locator('#details-body tr').count(),50);
    await page.locator('#details-next').click();await wait();assert.equal(requests.at(-1).get('pagina'),'2');
    await page.locator('#details-prev').click();await wait();
    await page.locator('.details-columns summary').click();
    await page.locator('#details-columns label').filter({hasText:/^ID$/}).locator('input').check();
    assert.ok((await page.locator('#details-head').textContent()).includes('ID'));
    await page.locator('.details-columns summary').click();
    await page.locator('#details-head button[data-column="id"]').click();await wait();
    assert.equal(requests.at(-1).get('ordenar_por'),'id');assert.equal(requests.at(-1).get('ordem'),'asc');
    assert.equal(await page.locator('#details-head button[data-column="id"]').locator('..').getAttribute('aria-sort'),'ascending');
    await page.locator('#details-next').click();await wait();assert.equal(requests.at(-1).get('ordenar_por'),'id');
    await page.locator('#details-head button[data-column="id"]').click();await wait();
    assert.equal(requests.at(-1).get('ordem'),'desc');assert.equal(requests.at(-1).get('pagina'),'1');
    assert.ok((await page.locator('#details-body tr').first().textContent()).includes('624.00'));
    await page.screenshot({path:path.join(artifacts,'details-desktop.png')});
    // Exporta todas as páginas, e não só as 50 linhas visíveis.
    const downloadPromise=page.waitForEvent('download');await page.locator('#details-export').click();const download=await downloadPromise;
    const downloaded=path.join(artifacts,'details-export.csv');await download.saveAs(downloaded);
    const csv=fs.readFileSync(downloaded,'utf8');assert.equal(csv.trim().split(/\r?\n/).length,625);
    assert.ok(csv.includes('"ID"'));
    assert.equal(requests.at(-1).get('ordem'),'desc');
    await page.locator('#details-head button[data-column="id"]').click();await wait();
    assert.equal(requests.at(-1).get('ordenar_por'),null);assert.ok(await page.locator('#details-reset-sort').isDisabled());
    await page.locator('#details-head button[data-column="peso"]').click();await wait();
    await page.locator('#details-reset-sort').click();await wait();assert.equal(requests.at(-1).get('ordenar_por'),null);
    await page.locator('#details-close').click();assert.equal(await page.locator('dialog[open]').count(),0);
    // Cada indicador abre a visão correspondente; notas permitem expandir os itens.
    for(let index=0;index<4;index++) {
      await first.locator('td button').nth(index).click();await wait();
      assert.equal(requests.at(-1).get('indicador'),['qtde_nfs','qtde_produto_por_nf','peso_por_nf','ticket_medio_por_nf'][index]);
      assert.equal(requests.at(-1).get('visao'),'notas');
      if(index===0) {
        await page.locator('#details-body button').first().click();await wait();
        assert.ok(requests.at(-1).get('chave_nf'));assert.equal(await page.locator('#details-body tr').count(),12);
        await page.locator('#details-all').click();await wait();assert.equal(requests.at(-1).get('chave_nf'),null);
      }
      await page.keyboard.press('Escape');
    }
    await first.locator('th button').click();await wait();
    await page.locator('#details-query').fill('especial');await page.locator('#details-search button').click();await wait();
    assert.equal(await page.locator('#details-body tr').count(),12);
    await page.locator('#details-query').fill('sem resultados');await page.locator('#details-search button').click();
    await page.getByText('Nenhum registro encontrado para este filtro.',{exact:true}).waitFor();
    assert.ok(await page.locator('#details-export').isDisabled());
    await page.locator('#details-close').click();
    // Total não filtra por grupo; tela pequena, tema escuro e retorno preservado.
    await page.locator('#report-total td button').first().click();await wait();assert.equal(requests.at(-1).get('vendedor_pai'),null);
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>document.documentElement.dataset.theme='dark');
    await page.screenshot({path:path.join(artifacts,'details-mobile-dark.png')});
    assert.ok(await page.locator('.details-dialog').evaluate(e=>e.getBoundingClientRect().right<=innerWidth));
    assert.ok(await page.locator('.details-grid').evaluate(e=>e.scrollWidth>e.clientWidth));
    await page.locator('#details-close').click();
    await page.setViewportSize({width:1440,height:1000});
    // Erro de autenticação não mantém registros antigos; fechar cancela consulta pendente.
    fail=true;await first.locator('th button').click();await page.getByText('Sessão expirada no teste.',{exact:true}).waitFor();
    assert.equal(await page.locator('#details-body tr').count(),0);await page.locator('#details-close').click();fail=false;
    delay=true;await first.locator('th button').click();await page.locator('#details-close').click();await page.waitForTimeout(700);
    assert.equal(await page.locator('dialog[open]').count(),0);assert.deepEqual(errors,[]);
    console.log('OK: cliques em todas as células, filtros da consulta exibida, notas/itens, paginação, colunas, CSV completo, busca, vazio, total, mobile/escuro, Escape, 401 e cancelamento.');
    await context.close();
  } finally {if(browser)await browser.close();server.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
