function optimizationTable(scenarios, optimized) {
  const table = document.createElement('table');
  table.className = 'scale-table';
  const head = document.createElement('tr');
  for (const label of ['Massa / operação','Estratégias comparadas','PostgreSQL · mediana','Redis · mediana']) {
    const th=document.createElement('th'); th.scope='col'; th.textContent=label; head.append(th);
  }
  const thead=document.createElement('thead'); thead.append(head); table.append(thead);
  const tbody=document.createElement('tbody');
  for (const scenario of scenarios) for (const query of scenario.queries) {
    if (optimized && query.query==='Q1') continue; // HGETALL não mudou.
    const pg=optimized && query.query==='Q3' ? 'postgres_materialized' : 'postgres_raw';
    const rd=optimized ? 'redis_optimized' : 'redis_baseline';
    const description=!optimized ? 'Modelos originais' : query.query==='Q2' ? 'Índice SQL coberto × sorted set completo' : 'Pré-agregação nos dois bancos';
    const values=[`${(scenario.records/1e6).toLocaleString('pt-BR')}M · ${query.query}`,description,
      ...[pg,rd].map(source=>query.metrics[source].median_ms.toLocaleString('pt-BR',{maximumFractionDigits:3})+' ms')];
    const tr=document.createElement('tr');
    for (const value of values) {const td=document.createElement('td');td.textContent=value;tr.append(td);}
    tbody.append(tr);
  }
  table.append(tbody); return table;
}
async function loadOptimization() {
  const status=document.getElementById('optimization-status');
  const host=document.getElementById('optimization-results');
  try {
    const response=await fetch('/api/optimization',{cache:'no-store'});
    if (!response.ok) throw new Error('Não foi possível carregar o experimento.');
    const report=await response.json();
    status.textContent=report.state==='ready' ? 'Índices ativos: consultas e alterações do laboratório já usam a nova estrutura.' : 'Índices ainda não ativados. Execute make otimizar-redis no terminal.';
    if (!report.scenarios.length) {host.textContent='Execute make benchmark-otimizado para registrar as medições.';return;}
    host.replaceChildren();
    for (const optimized of [false,true]) {
      const title=document.createElement('h4'); title.textContent=optimized ? '2 · Estratégias otimizadas em ambos' : '1 · Comparação original sobre as leituras';
      host.append(title,optimizationTable(report.scenarios,optimized));
    }
    const note=document.createElement('p'); note.className='small muted';
    note.textContent=report.scenarios.map(s=>`${s.records.toLocaleString('pt-BR')} leituras: ${s.repetitions} repetições, ${s.warmup} aquecimentos, ${new Date(s.executed_at).toLocaleDateString('pt-BR')}.`).join(' ');
    host.append(note);
    const image=document.getElementById('optimization-chart');
    image.onload=()=>{image.hidden=false;}; image.onerror=()=>{image.hidden=true;};
    image.src='/api/optimization/chart';
  } catch(error) {status.textContent=error.message;}
}
loadOptimization();
