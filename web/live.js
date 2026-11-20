const liveEl=id=>document.getElementById(id);
const liveNames={postgres:'PostgreSQL',redis:'Redis'};
const liveText=(tag,text)=>{const el=document.createElement(tag);el.textContent=text;return el;};
const liveMs=n=>n.toLocaleString('pt-BR',{maximumFractionDigits:3})+' ms';
let liveRun=0;
function liveFields(){
  const action=liveEl('live-action').value;
  document.querySelectorAll('[data-live-actions]').forEach(el=>{
    el.hidden=!el.dataset.liveActions.split(' ').includes(action);
    el.querySelectorAll('input,select').forEach(control=>{control.disabled=el.hidden;});
  });
  liveEl('live-run').textContent=action==='write'?'Gravar estado atual':action==='delete'?'Remover estado atual':'Consultar os bancos';
  liveEl('live-help').textContent=['write','delete'].includes(action)?'Esta ação modifica o estado operacional do sensor nos bancos selecionados. Em Ambos, cada banco confirma separadamente. O histórico possui seu próprio laboratório abaixo.':'Consulta direta ao estado atual. Cada resultado informa o banco, tempo HTTP e retorno real.';
}
async function liveRequest(source,action,stamp){
  const sid=Number(liveEl('live-sensor').value),location=liveEl('live-location').value;
  const params=new URLSearchParams({source});let path='/api/live',method='GET',body;
  if(['write','delete'].includes(action)){
    path+='/sensors/'+sid;method=action==='write'?'PUT':'DELETE';
    if(action==='write')body={ts:stamp,temperature_centi:Math.round(Number(liveEl('live-temperature').value)*100),humidity_centi:Math.round(Number(liveEl('live-humidity').value)*100)};
  }else{
    params.set('operation',action);
    if(action==='state')params.set('sensor_id',sid);
    if(action==='alerts')params.set('limit','20');
    if(['summary','alerts'].includes(action)&&location)params.set('location',location);
  }
  const start=performance.now(),request={method,path:path+'?'+params,body};
  try{
    const response=await fetch(request.path,{method,headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{}),cache:'no-store'});
    const result=await response.json();return {source,status:response.status,http_ms:performance.now()-start,request,response:result};
  }catch(error){return {source,status:0,http_ms:performance.now()-start,request,response:{error:'Sem resposta confirmada: '+error.message}};}
}
function liveRender(results){
  const host=liveEl('live-results');host.replaceChildren();
  for(const result of results){
    const card=liveText('article','');card.className='panel';
    card.append(liveText('h3',liveNames[result.source]),liveText('p',`${result.status?'HTTP '+result.status:'Falha de comunicação'} · ponta a ponta ${liveMs(result.http_ms)}`));
    const d=result.response.data;
    if(d&&typeof d.count==='number'){
      card.append(liveText('strong',`${d.count.toLocaleString('pt-BR')} sensores com estado`));
      card.append(liveText('p',`${d.alerts} em alerta · média ${d.count?(d.temperature_sum/d.count/100).toFixed(2):'—'} °C · mínima ${d.minimum===null?'—':d.minimum/100} °C · máxima ${d.maximum===null?'—':d.maximum/100} °C`));
    }else if(Array.isArray(d)){
      const list=document.createElement('ol');for(const row of d)list.append(liveText('li',`Sensor ${row.sensor_id} · ${(row.temperature_centi/100).toFixed(2)} °C`));card.append(list);
    }else if(d?.sensor_id){card.append(liveText('p',`Sensor ${d.sensor_id} · ${d.location} · ${(d.temperature_centi/100).toFixed(2)} °C · ${new Date(d.ts*1000).toISOString()}`));}
    const details=document.createElement('details');details.append(liveText('summary','Ver comandos enviados e JSON'),liveText('pre',JSON.stringify(result,null,2)));card.append(details);host.append(card);
  }
  const canonical=v=>JSON.stringify(v,(_,value)=>value&&typeof value==='object'&&!Array.isArray(value)?Object.fromEntries(Object.entries(value).sort()):value);
  liveEl('live-status').textContent=results.some(r=>!r.status||r.status>=400)?'A operação apresentou erro. Confira o JSON de cada banco; uma escrita sem resposta pode ter sido aplicada.':results.length===2?(canonical(results[0].response.data??results[0].response)===canonical(results[1].response.data??results[1].response)?'Resultados equivalentes nos dois bancos.':'Os estados diferem entre os bancos. Consulte o sensor e confira as alterações.'):'Operação concluída.';
}
liveEl('live-form').addEventListener('submit',async event=>{
  event.preventDefault();const action=liveEl('live-action').value;const destination=liveEl('live-source').value;
  const sources=destination==='both'?(liveRun++%2?['redis','postgres']:['postgres','redis']):[destination];
  liveEl('live-controls').disabled=true;liveEl('live-status').textContent='Executando…';
  const stamp=Math.floor(Date.now()/1000);
  try{const results=[];for(const source of sources)results.push(await liveRequest(source,action,stamp));liveRender(results);}
  catch(error){liveEl('live-status').textContent=error.message;}
  finally{liveEl('live-controls').disabled=false;}
});
liveEl('live-action').addEventListener('change',liveFields);
document.querySelectorAll('[data-live-preset]').forEach(button=>button.addEventListener('click',()=>{liveEl('live-action').value=button.dataset.livePreset;liveFields();}));
liveFields();
async function liveBenchmark(){
  const host=liveEl('live-benchmark');
  try{
    const response=await fetch('/api/live/benchmark');if(!response.ok){host.textContent='Execute make benchmark-central para gerar as medições deste modelo.';return;}
    const report=await response.json();const table=document.createElement('table');table.className='scale-table';
    const names={estado_sensor:'Estado de um sensor',resumo_global:'Indicadores globais prontos',resumo_local:'Indicadores de um local',top_20_alertas:'20 sensores em alerta',atualizar_estado_e_indicadores:'Atualizar estado + índices + indicadores'};
    const head=document.createElement('tr');for(const label of ['Mesmo contrato','PostgreSQL · mediana','Redis · mediana'])head.append(liveText('th',label));table.append(head);
    for(const [code,metrics]of Object.entries(report.results)){const row=document.createElement('tr');for(const value of[names[code],liveMs(metrics.postgres.median_ms),liveMs(metrics.redis.median_ms)])row.append(liveText('td',value));table.append(row);}
    host.replaceChildren(liveText('p',`${report.operational_states.toLocaleString('pt-BR')} estados operacionais · ${report.repetitions} repetições · ${report.warmup} aquecimentos · ${new Date(report.executed_at).toLocaleString('pt-BR')}`),table,liveText('p','Conexões reutilizadas, um cliente, ordem alternada. Ambos mantêm os indicadores em cada escrita. SQL inclui COMMIT; Redis confirma com AOF everysec, com garantia de durabilidade diferente. Estado atual não equivale a agregar todo o histórico.'));
    const chart=document.createElement('img');chart.src='/api/live/chart';chart.alt='Mediana e p95 das consultas e escrita do estado atual, comparando Redis e PostgreSQL';chart.className='live-chart';chart.addEventListener('error',()=>chart.remove());host.append(chart);
  }catch(error){host.textContent=error.message;}
}
liveBenchmark();
