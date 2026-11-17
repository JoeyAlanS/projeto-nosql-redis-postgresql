import {actions, names, demo, period, buildOperation, describeCommand, compareResults, errorHint} from './operations-core.mjs';

const el = id => document.getElementById(id);
const form = el('operation-form');
const log = el('operation-log');
const entries = [];
let sequence = 0;
let running = false;
const formatMs = value => value.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' ms';
function node(tag, text, className) {
  const result = document.createElement(tag);
  if (text !== undefined) result.textContent = text;
  if (className) result.className = className;
  return result;
}
function inputs() {
  return Object.fromEntries(['source', 'action', 'id', 'sensor', 'ts', 'temperature', 'humidity', 'start', 'end', 'limit'].map(key => [key, el('op-' + key).value]));
}
function status(message, error = false) {
  el('operation-status').textContent = message;
  el('operation-status').dataset.error = String(error);
}
function updateForm() {
  const action = el('op-action').value;
  for (const label of form.querySelectorAll('[data-ops]')) {
    const visible = label.dataset.ops.split(' ').includes(action);
    label.hidden = !visible;
    for (const input of label.querySelectorAll('input')) input.disabled = !visible;
  }
  el('op-sensor-help').textContent = action === 'summary' ? 'Deixe vazio para resumir todos os sensores.' : 'Use um sensor existente, de 1 a 1000.';
  const mutation = ['create', 'update', 'delete'].includes(action);
  el('operation-help').classList.toggle('is-write', mutation);
  el('operation-help').textContent = mutation
    ? `Esta operação ${action === 'delete' ? 'exclui' : 'grava'} uma leitura real no destino escolhido. ${el('op-source').value === 'both' ? 'Em Ambos, cada banco confirma separadamente; uma falha não desfaz o outro.' : 'O outro banco não é alterado.'} ${action === 'update' ? 'Atualizar substitui todos os campos pelos valores informados. ' : ''}Use o exemplo de CRUD para praticar fora da massa original.`
    : action === 'summary' ? 'Os limites do período são inclusivos. Sem sensor, o resumo considera todos. Consultas amplas podem levar alguns segundos.'
    : action === 'history' ? 'Leituras ordenadas por instante. O limite controla quantos registros retornam, até 1000.'
    : 'A consulta busca a leitura pelo ID. Em Ambos, o console compara os cinco campos retornados.';
  try {
    const operation = buildOperation(inputs());
    el('operation-preview').textContent = operation.requests.map(request => `${names[request.source]}\n${request.method} ${request.path}${request.body ? '\nCorpo JSON: ' + JSON.stringify(request.body, null, 2) : ''}\n\n${describeCommand(operation, request.source)}`).join('\n\n────────────────────────────\n\n');
  } catch (error) {
    el('operation-preview').textContent = error.message;
  }
}
function preset(name) {
  el('op-source').value = 'both';
  if (name === 'point') {
    el('op-action').value = 'point'; el('op-id').value = '500001';
  } else if (name === 'demo') {
    el('op-action').value = 'create';
    for (const [key, value] of Object.entries(demo)) el('op-' + key).value = value;
  } else {
    el('op-action').value = 'summary'; el('op-sensor').value = '';
    for (const [key, value] of Object.entries(period)) el('op-' + key).value = value;
  }
  updateForm();
  status('Exemplo preenchido. Clique em Executar operação para enviá-lo ao banco.');
}
function toggleBusy(value) {
  running = value;
  el('operation-fields').disabled = value;
  document.querySelectorAll('[data-preset]').forEach(button => { button.disabled = value; });
  el('operation-run').textContent = value ? 'Executando…' : 'Executar operação →';
  el('console-clear').disabled = value || !entries.length;
  el('console-export').disabled = value || !entries.length;
}
async function send(request) {
  const start = performance.now();
  try {
    const response = await fetch(request.path, {
      method: request.method,
      headers: request.body ? {'Content-Type': 'application/json'} : {},
      ...(request.body ? {body: JSON.stringify(request.body)} : {}),
      cache: 'no-store',
    });
    const text = await response.text();
    let body;
    try { body = JSON.parse(text); } catch { body = text || '(resposta vazia)'; }
    return {source: request.source, request, status: response.status, ok: response.ok, elapsed_ms: performance.now() - start, response: body};
  } catch (error) {
    return {source: request.source, request, status: null, ok: false, elapsed_ms: performance.now() - start, response: {detail: error.message}};
  }
}
function renderResult(result, operation) {
  const section = node('section', undefined, 'console-result');
  section.append(node('h4', `${names[result.source]} · ${result.status === null ? 'Sem resposta HTTP' : 'HTTP ' + result.status}`, result.ok ? 'console-success' : 'console-error'));
  section.append(node('p', `Ponta a ponta: ${formatMs(result.elapsed_ms)}`));
  if (result.ok && ['history', 'summary'].includes(operation.action) && Number.isFinite(result.response.elapsed_ms)) {
    section.append(node('p', `Trecho da consulta no backend: ${formatMs(result.response.elapsed_ms)} (exclui abertura da conexão e seleção dos sensores).`));
  }
  if (!result.ok) section.append(node('p', errorHint(result.status), 'console-error'));
  const request = node('details');
  request.append(node('summary', 'Ver requisição enviada'), node('pre', `${result.request.method} ${result.request.path}${result.request.body ? '\n' + JSON.stringify(result.request.body, null, 2) : ''}`));
  section.append(request, node('pre', typeof result.response === 'string' ? result.response : JSON.stringify(result.response, null, 2)));
  if (result.ok && operation.action === 'point' && result.response?.id) {
    const edit = node('button', 'Preparar edição no ' + names[result.source], 'console-edit');
    edit.type = 'button';
    edit.addEventListener('click', () => {
      if (running) return;
      const row = result.response;
      const values = {source: result.source, action: 'update', id: row.id, sensor: row.sensor_id,
        ts: new Date(row.ts * 1000).toISOString().slice(0, 19),
        temperature: (row.temperature_centi / 100).toFixed(2), humidity: (row.humidity_centi / 100).toFixed(2)};
      for (const [key, value] of Object.entries(values)) el('op-' + key).value = value;
      updateForm();
      status('Campos preenchidos com a leitura consultada. Revise os valores e execute para salvar.');
      el('op-temperature').focus();
    });
    section.append(edit);
  }
  return section;
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (running) return;
  let operation;
  try { operation = buildOperation(inputs()); }
  catch (error) { status('Validação local: ' + error.message + ' Nenhuma requisição enviada.', true); return; }
  toggleBusy(true);
  status('Executando nos bancos selecionados…');
  const entry = {number: ++sequence, executed_at: new Date().toISOString(), operation, results: []};
  const container = node('details', undefined, 'console-run'); container.open = true;
  const title = node('summary');
  title.append(node('strong', `#${entry.number} · ${actions[operation.action]}`), node('span', new Date(entry.executed_at).toLocaleTimeString('pt-BR') + ' · Executando…'));
  container.append(title);
  if (!entries.length) log.replaceChildren();
  for (const previous of log.querySelectorAll(':scope > details')) previous.open = false;
  log.prepend(container); log.scrollTop = 0;
  try {
    // Requisições independentes: renderiza a primeira mesmo se a segunda falhar.
    for (const request of operation.requests) {
      status(`Executando ${actions[operation.action].toLowerCase()} em ${names[request.source]}…`);
      const result = await send(request);
      entry.results.push(result);
      container.append(renderResult(result, operation));
    }
    entry.comparison = compareResults(entry.results, operation.action);
    const verdict = node('div', undefined, 'console-comparison console-' + entry.comparison.kind);
    verdict.append(node('p', entry.comparison.message));
    if (entry.comparison.differences?.length) {
      const list = node('ul');
      for (const diff of entry.comparison.differences) list.append(node('li', `${diff.field}: PostgreSQL ${JSON.stringify(diff.postgres)} → Redis ${JSON.stringify(diff.redis)}`));
      verdict.append(list, node('p', 'Até 20 diferenças exibidas. Os retornos completos estão abaixo.'));
    }
    container.insertBefore(verdict, title.nextSibling);
    title.lastElementChild.textContent = new Date(entry.executed_at).toLocaleTimeString('pt-BR') + ' · ' + entry.results.map(r => `${names[r.source]} ${r.status ?? 'sem resposta'}`).join(' / ');
    entries.unshift(entry);
    if (entries.length > 30) { entries.pop(); log.lastElementChild.remove(); }
    el('console-count').textContent = `${entries.length} ${entries.length === 1 ? 'execução' : 'execuções'}`;
    status(entry.comparison.message, entry.comparison.kind === 'error');
  } finally { toggleBusy(false); }
});
form.addEventListener('input', updateForm);
form.addEventListener('change', updateForm);
document.querySelectorAll('[data-preset]').forEach(button => button.addEventListener('click', () => preset(button.dataset.preset)));
el('console-clear').addEventListener('click', () => {
  if (running) return;
  entries.length = 0;
  log.replaceChildren(node('p', 'Console limpo. Os dados dos bancos não foram alterados.', 'console-empty'));
  el('console-count').textContent = '0 execuções'; toggleBusy(false);
  status('Histórico visual limpo. Os dados dos bancos não foram alterados.');
});
el('console-export').addEventListener('click', () => {
  const blob = new Blob([JSON.stringify({exported_at: new Date().toISOString(), scope: 'Base principal local; tempos HTTP de ponta a ponta', entries}, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const link = node('a'); link.href = url; link.download = 'console-operacoes-iot.json';
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  status('Histórico exportado em console-operacoes-iot.json.');
});
for (const [key, value] of Object.entries({...demo, ...period})) el('op-' + key).value = value;
el('op-id').value = '500001';
updateForm();
function highlightSection() {
  const selected = location.hash || '#overview';
  document.querySelectorAll('aside a.nav').forEach(link => {
    const active = link.getAttribute('href') === selected;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
}
addEventListener('hashchange', highlightSection);
highlightSection();
