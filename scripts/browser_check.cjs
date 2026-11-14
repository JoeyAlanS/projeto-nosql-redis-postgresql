// npm ci && npx playwright install chromium && npm run test:browser
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_BIN?{executablePath:process.env.CHROME_BIN}:{}),args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1512,height:1100},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const calls=[];page.on('request',r=>{if(r.url().includes('/api/query'))calls.push(r.url());});
 const root=path.resolve(__dirname,'..');const evidence=path.join(root,'results/evidencias');fs.mkdirSync(evidence,{recursive:true});
 await page.goto('http://localhost:8000',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>document.getElementById('count').textContent==='1.000.000');
 await page.waitForFunction(()=>document.getElementById('benchmark-chart').children.length===3);
 const initial=await page.locator('#count').innerText();
 await page.screenshot({path:path.join(evidence,'dashboard_completo.png'),fullPage:true});
 await page.selectOption('#location','Biblioteca');
 await page.waitForFunction(()=>document.getElementById('count').textContent==='100.000');
 const postgres=await page.locator('.metrics').innerText();
 await page.click('[data-source=redis]');
 await page.waitForFunction(()=>document.getElementById('query-time').textContent.includes('Redis')&&!document.getElementById('query-time').textContent.includes('Consultando'));
 const redis=await page.locator('.metrics').innerText();
 if(postgres!==redis)throw new Error('Indicadores divergem ao trocar a fonte');
 await page.selectOption('#sensor','2');
 await page.waitForFunction(()=>document.getElementById('count').textContent==='1.000');
 await page.fill('#end','2026-11-01T12:00');await page.click('#apply');
 await page.waitForFunction(()=>document.getElementById('count').textContent==='145');
 await page.screenshot({path:path.join(evidence,'dashboard_redis_filtrado.png'),fullPage:true});
 await page.fill('#reading-id','500001');await page.click('#lookup');
 await page.waitForFunction(()=>!document.getElementById('lookup').disabled&&document.getElementById('equivalence').textContent==='Resultados equivalentes');
 await page.locator('#comparison').screenshot({path:path.join(evidence,'consulta_ao_vivo.png')});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(evidence,'dashboard_mobile.png'),fullPage:true});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
 if(overflow)throw new Error('Overflow horizontal na tela móvel');
 await page.fill('#reading-id','9000000000999');await page.click('#lookup');
 await page.waitForFunction(()=>document.getElementById('reading-detail').textContent.includes('nenhuma das fontes'));
 // Simula divergência de resposta sem modificar a massa do experimento.
 await page.route('**/api/compare?*',async route=>{
   const response=await route.fetch();const result=await response.json();
   result.results[0].data=null;result.equivalent=false;
   await route.fulfill({response,json:result});
 });
 await page.fill('#reading-id','500001');await page.click('#lookup');
 await page.waitForFunction(()=>document.getElementById('reading-detail').textContent.includes('Redis: registro encontrado'));
 const mismatch=await page.locator('#reading-detail').innerText();
 if(!mismatch.includes('PostgreSQL: leitura não encontrada'))throw new Error('Ausência em uma fonte foi informada incorretamente');
 await page.unroute('**/api/compare?*');
 await page.fill('#end','2026-10-01T12:00');await page.click('#apply');
 await page.waitForFunction(()=>!document.getElementById('error').hidden&&document.getElementById('error').textContent.includes('Fim deve'));
 await page.fill('#end','2026-11-01T12:00');await page.click('#apply');
 await page.waitForFunction(()=>document.getElementById('error').hidden&&!document.getElementById('apply').disabled);
 if(errors.length)throw new Error(errors.join('\n'));
 const result={initial_count:initial,source_switch_equivalent:true,location_count:100000,sensor_count:1000,
  filtered_count:145,live_equivalent:true,missing_reading_handled:true,divergent_sources_handled:true,
  invalid_dates_handled:true,query_requests:calls.length,console_errors:errors,mobile_horizontal_overflow:overflow,passed:true};
 fs.writeFileSync(path.join(root,'results/browser.json'),JSON.stringify(result,null,2)+'\n');console.log(result);
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
