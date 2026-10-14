/* Navegador isolado. Payload obtido no teste SQL real; token apenas de teste. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root=path.resolve(__dirname,'..');
const payload=JSON.parse(fs.readFileSync(path.join(root,'artifacts/resumo_real.json'),'utf8'));
const filters=JSON.parse(fs.readFileSync(path.join(root,'artifacts/filtros_real.json'),'utf8'));
const mime={'.html':'text/html','.css':'text/css','.js':'text/javascript','.png':'image/png','.woff2':'font/woff2'};
const server=http.createServer((req,res)=>{
  const pathname=new URL(req.url,'http://localhost').pathname;
  if(pathname!=='/'&&!pathname.startsWith('/assets/')){res.writeHead(404);res.end();return;}
  const file=path.resolve(root,'.'+(pathname==='/'?'/index.html':pathname));
  if(!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
  fs.readFile(file,(error,data)=>{res.writeHead(error?404:200,{'content-type':mime[path.extname(file)]||'application/octet-stream'});res.end(error?'Não encontrado':data);});
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url=`http://127.0.0.1:${server.address().port}`;
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const context=await browser.newContext({viewport:{width:1440,height:1120}});
  const page=await context.newPage(), errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
    await page.goto(url);await page.getByText('Sessão do Portal BI não encontrada.',{exact:false}).waitFor();
    assert.equal(await page.locator('#report-total tr').count(),0);
    let mode='normal',requests=[];
    await context.addInitScript(()=>sessionStorage.setItem('granjabi_auth_token','token-isolado-de-teste'));
    await page.route('https://api-bi-granja.controladoriagb05.workers.dev/**',async route=>{
      const request=route.request();assert.equal(request.headers().authorization,'Bearer token-isolado-de-teste');
      requests.push(request.url());
      if(mode==='401'){await route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({detail:'Sessão expirada. Entre novamente no Portal BI.'})});return;}
      if(request.url().includes('/filtros')){await route.fulfill({json:filters});return;}
      if(mode==='vazio'){
        const zero=JSON.parse(fs.readFileSync(path.join(root,'artifacts/resumo_vazio.json'),'utf8'));
        await route.fulfill({json:zero});return;
      }
      const selected=new URL(request.url()).searchParams.getAll('unidade');
      const data=selected.length ? JSON.parse(fs.readFileSync(path.join(root,'artifacts/resumo_real_multiplas.json'),'utf8')) : JSON.parse(JSON.stringify(payload));
      const query=new URL(request.url()).searchParams;
      data.periodo={data_inicio:query.get('data_inicio'),data_fim:query.get('data_fim')};
      if(mode==='race'&&query.get('data_inicio')==='2026-09-06')await new Promise(r=>setTimeout(r,600));
      await route.fulfill({json:data});
    });
    await page.reload();await page.getByText('Relatório atualizado.',{exact:true}).waitFor();
    assert.equal(await page.locator('#report-total td').first().textContent(),'2.687');
    assert.ok((await page.locator('#report-total').textContent()).includes('7.517,0'));
    assert.equal(await page.locator('#report-body tr').count(),payload.grupos.length);
    assert.ok((await page.locator('#report-body').textContent()).includes('Não classificado'));
    await page.screenshot({path:path.join(root,'artifacts/desktop.png'),fullPage:true});
    await page.locator('#filter-unidade button').click();
    await page.locator('#filter-unidade input[value="10"]').check();
    await page.locator('#filter-unidade input[value="111"]').check();
    await page.locator('#apply').click();await page.getByText('Relatório atualizado.',{exact:true}).waitFor();
    const last=new URL(requests.at(-1));assert.deepEqual(last.searchParams.getAll('unidade'),['10','111']);
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(root,'artifacts/mobile.png'),fullPage:true});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
    assert.ok(await page.locator('.table-scroll').evaluate(e=>e.scrollWidth>e.clientWidth));
    mode='race';await page.locator('#data-inicio').fill('2026-09-06');await page.locator('#apply').click();
    await page.locator('#data-inicio').fill('2026-09-07');await page.locator('#apply').click();
    await page.getByText('Relatório atualizado.',{exact:true}).waitFor();
    await page.waitForTimeout(750);assert.ok((await page.locator('#period-label').textContent()).startsWith('07/09/2026'));
    mode='vazio';await page.locator('#apply').click();await page.getByText('Nenhuma NF encontrada',{exact:false}).waitFor();
    assert.equal(await page.locator('#report-total td').first().textContent(),'0');
    mode='401';await page.locator('#apply').click();await page.getByText('Sessão expirada.',{exact:false}).waitFor();
    assert.equal(await page.locator('#report-total tr').count(),0);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(root,'artifacts/browser-tests.json'),JSON.stringify({ok:true,tests:['sessão ausente','Bearer','renderização de payload SQL real','ordem e grupo não classificado','filtros multisseleção','layout desktop/mobile','cancelamento de consulta anterior','intervalo sem movimento','sessão expirada','sem erros JavaScript']},null,2));
    console.log('10 verificações de navegador passaram. Capturas em artifacts/.');
  }finally{await context.close();await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
