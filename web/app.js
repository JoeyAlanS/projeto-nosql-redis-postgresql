const $ = id => document.getElementById(id);
const n = value => Number(value).toLocaleString('pt-BR');
const dec = (value, digits = 2) => Number(value).toLocaleString('pt-BR', {minimumFractionDigits: digits, maximumFractionDigits: digits});
const ms = value => `${dec(value, 3)} ms`;
const state = {source: 'postgres', sensors: [], controller: null};
const datetime = ts => new Date(ts * 1000).toISOString().slice(0,16);
const epoch = id => Math.floor(Date.parse($(id).value + ':00Z') / 1000);
const error = message => { $('error').hidden = !message; $('error').textContent = message || ''; };
async function api(path, signal) {
  const res = await fetch(path, {signal});
  if (!res.ok) { let message = `Erro ${res.status}`; try { const b = await res.json(); message = typeof b.detail === 'string' ? b.detail : 'Confira os filtros informados.'; } catch {} throw new Error(message); }
  return res.json();
}
function sensors() {
  const selected = $('sensor').value;
  const list = state.sensors.filter(s => !$('location').value || s.location === $('location').value);
  $('sensor').replaceChildren(new Option('Todos os sensores',''), ...list.map(s => new Option(s.name, s.id)));
  if (list.some(s => String(s.id) === selected)) $('sensor').value = selected;
}
function filters() {
  const p = new URLSearchParams({source: state.source, start: epoch('start'), end: epoch('end')});
  if ($('location').value) p.set('location', $('location').value);
  if ($('sensor').value) p.set('sensor_id', $('sensor').value);
  return p;
}
function chart(rows) {
  if (!rows.length) { $('chart').innerHTML = '<p class="empty">Nenhuma leitura neste intervalo.</p>'; return; }
  const w=1020,h=230,left=38,right=18,top=12,bottom=28;
  const values = rows.map(r => r.temperature_centi/100);
  const min = Math.floor(Math.min(...values)-1), max = Math.ceil(Math.max(...values)+1);
  const xmin=rows[0].ts, xmax=rows.at(-1).ts;
  const x = ts => left+(ts-xmin)/(xmax-xmin||1)*(w-left-right);
  const y = v => top+(max-v)/(max-min||1)*(h-top-bottom);
  const points=rows.map((r,i)=>`${x(r.ts)},${y(values[i])}`).join(' ');
  const ticks=Array.from({length:5},(_,i)=>min+(max-min)*i/4);
  const grid=ticks.map(v=>`<line x1="${left}" x2="${w-right}" y1="${y(v)}" y2="${y(v)}" stroke="#edf1f3"/><text x="${left-9}" y="${y(v)+4}" text-anchor="end">${dec(v,0)}°</text>`).join('');
  const labels=Array.from({length:5},(_,i)=>{const ts=xmin+(xmax-xmin)*i/4;return `<text x="${x(ts)}" y="${h-4}" text-anchor="${i===0?'start':i===4?'end':'middle'}">${new Date(ts*1000).toISOString().slice(5,16).replace('T',' ')} UTC</text>`;}).join('');
  $('chart').innerHTML=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Temperatura por instante de leitura"><defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#49b89a" stop-opacity=".14"/><stop offset="1" stop-color="#49b89a" stop-opacity="0"/></linearGradient></defs>${grid}<polygon points="${left},${h-bottom} ${points} ${x(rows.at(-1).ts)},${h-bottom}" fill="url(#area)"/><polyline points="${points}" fill="none" stroke="#16846d" stroke-width="2"/>${labels}</svg>`;
}
async function refresh() {
  if (state.controller) state.controller.abort();
  state.controller = new AbortController();
  const signal = state.controller.signal;
  error(''); $('query-time').textContent='Consultando…'; $('apply').disabled=true;
  try {
    const p=filters();
    if (!Number.isFinite(epoch('start')) || !Number.isFinite(epoch('end'))) throw new Error('Informe as duas datas.');
    const available=state.sensors.filter(s=>!$('location').value||s.location===$('location').value);
    const sid=$('sensor').value || available[0]?.id;
    const hp=new URLSearchParams(p); hp.set('sensor_id',sid); hp.set('operation','history');
    p.set('operation','summary');
    const [summary,history]=await Promise.all([api('/api/query?'+p,signal),api('/api/query?'+hp,signal)]);
    const d=summary.data;
    $('count').textContent=n(d.count); $('temperature').textContent=d.count?`${dec(d.temperature_sum/d.count/100)} °C`:'—';
    $('sensor-count').textContent=n(d.sensors); $('alerts').textContent=n(d.alerts);
    $('alert-percentage').textContent=`${dec(d.count?d.alerts/d.count*100:0,1)}% das leituras acima de 32 °C`;
    $('temperature-range').textContent=d.count?`Mín. ${dec(d.minimum/100,1)}° / Máx. ${dec(d.maximum/100,1)}°`:'Sem leituras';
    $('scope').textContent=`${$('location').value||'Todos os locais'} · ${$('sensor').selectedOptions[0].textContent}`;
    $('query-time').textContent=`Resumo · ${state.source==='redis'?'Redis':'PostgreSQL'} · ${ms(summary.elapsed_ms)}`;
    $('history-time').textContent=ms(history.elapsed_ms); $('history-title').textContent=`Histórico · Sensor ${String(sid).padStart(4,'0')}`;
    $('history-note').textContent=`Primeiras ${n(history.data.length)} leituras no período · até 200 pontos`;
    chart(history.data);
  } catch(e) { if(e.name!=='AbortError') {error(e.message);$('query-time').textContent='Consulta não concluída';} }
  finally {if(!signal.aborted)$('apply').disabled=false;}
}
function bars(pg,redis) {
  const max=Math.max(pg,redis,0.001);
  return [['postgres','PostgreSQL',pg],['redis','Redis',redis]].map(([source,label,value])=>`<div class="bar-row"><span>${label}</span><div class="bar-track"><div class="bar-fill ${source}" style="width:${value/max*100}%"></div></div><span class="bar-value">${ms(value)}</span></div>`).join('');
}
async function lookup() {
  $('lookup').disabled=true;error('');
  try {
    const id=Number($('reading-id').value);
    if(!Number.isSafeInteger(id)||id<1) throw new Error('Informe um ID inteiro positivo.');
    const r=await api('/api/compare?operation=point&reading_id='+id);
    $('live-bars').innerHTML=bars(r.results[0].elapsed_ms,r.results[1].elapsed_ms);
    $('equivalence').textContent=r.equivalent?'Resultados equivalentes':'Resultados diferentes';
    $('reading-detail').replaceChildren();
    if(r.results.every(result=>!result.data)) { $('reading-detail').textContent='Leitura não encontrada em nenhuma das fontes.'; return; }
    const details=r.equivalent?[r.results[0]]:r.results;
    for(const result of details) {
    const row=result.data;
    if(!r.equivalent) {
      const source=document.createElement('p');
      source.textContent=`${result.source==='postgres'?'PostgreSQL':'Redis'}: ${row?'registro encontrado':'leitura não encontrada'}`;
      $('reading-detail').append(source);
    }
    if(!row) continue;
    const label=document.createElement('div');label.textContent=`Leitura #${n(row.id)} · Sensor ${String(row.sensor_id).padStart(4,'0')}`;
    $('reading-detail').append(label);
    const values=document.createElement('div');values.className='reading-values';
    values.innerHTML=`<div><strong>${dec(row.temperature_centi/100)}°</strong><small>Temperatura</small></div><div><strong>${dec(row.humidity_centi/100,1)}%</strong><small>Umidade relativa</small></div>`;
    const date=document.createElement('div');date.textContent=new Date(row.ts*1000).toISOString().replace('T',' ').replace('.000Z',' UTC');
    $('reading-detail').append(values,date);
    }
  } catch(e) {error(e.message);} finally {$('lookup').disabled=false;}
}
async function experiment() {
  try {
    const b=await api('/api/benchmark');
    $('benchmark-description').textContent=`${b.repetitions} repetições por banco e operação · ${b.warmup} aquecimentos · ${n(b.records)} registros`;
    $('benchmark-chart').replaceChildren();
    for(const q of b.queries) {
      const row=document.createElement('div');row.className='experiment-row';
      const text=document.createElement('div');const title=document.createElement('h3');title.textContent=`${q.query} · ${q.name}`;
      const caption=document.createElement('p');caption.textContent=q.postgres_over_redis>1?`Redis ${dec(q.postgres_over_redis,2)}× mais rápido nesta medição`:`PostgreSQL ${dec(1/q.postgres_over_redis,2)}× mais rápido nesta medição`;
      text.append(title,caption);const bar=document.createElement('div');bar.innerHTML=bars(q.metrics.postgres.median_ms,q.metrics.redis.median_ms);row.append(text,bar);$('benchmark-chart').append(row);
    }
  } catch(e) { $('benchmark-description').textContent=e.message; }
}
async function init() {
  try {
    await api('/api/health'); $('connection').textContent='PostgreSQL e Redis conectados';
    const meta=await api('/api/meta');state.sensors=meta.sensors;
    for(const l of [...new Set(state.sensors.map(s=>s.location))])$('location').add(new Option(l,l));
    sensors();
    if(!meta.load) throw new Error('A massa ainda não foi carregada.');
    $('start').value=datetime(meta.load.start);$('end').value=datetime(meta.load.end);
    $('reading-id').value=Math.min(500001,meta.load.records);
    $('dataset-info').textContent=`Massa sintética determinística · ${n(meta.load.records)} leituras · ${n(meta.load.sensors)} sensores · seed ${meta.load.seed} · Intervalo de 5 minutos · Horários em UTC`;
    await Promise.all([refresh(),lookup(),experiment()]);
  }catch(e){$('connection').textContent='Conexão não concluída';error(e.message);}
}
document.querySelectorAll('[data-source]').forEach(button=>button.addEventListener('click',()=>{state.source=button.dataset.source;document.querySelectorAll('[data-source]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));refresh();}));
$('location').addEventListener('change',()=>{sensors();refresh();});
$('sensor').addEventListener('change',refresh);
$('apply').addEventListener('click',refresh);$('refresh').addEventListener('click',refresh);$('lookup').addEventListener('click',lookup);
init();
