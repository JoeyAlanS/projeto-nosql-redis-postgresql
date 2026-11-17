import {readingFields, labels, compareReadings, describeChange, formatField, readingState} from './reading-comparison.mjs';
import {names, actions, compareResults} from './operations-core.mjs';
const el = id => document.getElementById(id);
const node = (tag, text, className) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; };
function fieldsTable(row, different, redis) {
  const table = node('table', undefined, 'reading-fields');
  table.append(node('caption', redis ? 'Campos do hash' : 'Uma linha da tabela readings'));
  if (!redis) {
    table.classList.add('postgres-row');
    const header = table.createTHead().insertRow();
    const values = table.createTBody().insertRow();
    for (const key of readingFields) {
      const th = node('th', key); th.scope = 'col'; header.append(th);
      const td = values.insertCell(); td.append(node('strong', String(row[key])));
      if (different.includes(key)) {
        th.className = 'field-diff'; td.className = 'field-diff';
        td.append(node('span', 'Diferente', 'diff-label'));
      }
    }
    const scroll = node('div', undefined, 'postgres-table-scroll'); scroll.append(table);
    return scroll;
  }
  const head = table.createTHead().insertRow();
  for (const name of [redis ? 'Campo do hash' : 'Coluna', 'Valor armazenado']) { const th = node('th', name); th.scope = 'col'; head.append(th); }
  const body = table.createTBody();
  for (const key of readingFields) {
    const tr = body.insertRow();
    if (different.includes(key)) tr.className = 'field-diff';
    tr.append(node('th', key)); tr.lastChild.scope = 'row';
    const td = tr.insertCell(); td.append(node('strong', String(row[key])));
    if (different.includes(key)) td.append(node('span', 'Diferente', 'diff-label'));
  }
  return table;
}
export function renderReadingPair({id, after, before = [], action, results = [], onEdit}) {
  const comparison = compareReadings(after);
  const target = el('reading-visual');
  target.replaceChildren(); target.dataset.state = comparison.kind;
  el('visual-id').textContent = `Leitura #${id}`;
  el('visual-status').textContent = comparison.message;
  el('visual-status').dataset.state = comparison.kind;
  el('visual-observed').textContent = `Última consulta: ${new Date().toLocaleTimeString('pt-BR')} · leituras independentes nos dois bancos`;
  const feedback = el('visual-operation');
  feedback.hidden = !before.length;
  if (before.length) {
    const outcome = compareResults(results, action);
    feedback.dataset.state = outcome.kind;
    feedback.textContent = `${actions[action]} · ${results.map(r => `${names[r.source]}: ${r.status ? 'HTTP ' + r.status : 'sem resposta'}`).join(' · ')}. ${outcome.message}`;
  }
  const cards = node('div', undefined, 'database-pair');
  for (const source of ['postgres', 'redis']) {
    const current = after.find(r => r.source === source);
    const previous = before.find(r => r.source === source);
    const state = comparison.states[source];
    const card = node('article', undefined, `database-card ${source}`);
    const header = node('div', undefined, 'database-heading');
    header.append(node('h4', names[source]), node('span', source === 'postgres' ? 'RELACIONAL · LINHA' : 'CHAVE-VALOR · HASH', 'database-model'));
    card.append(header);
    card.append(node('code', source === 'postgres' ? `readings WHERE id = ${id}` : `iot:reading:${id}`, 'database-key'));
    if (state.kind === 'found') {
      const metric = node('div', undefined, 'database-metric');
      metric.append(node('strong', formatField('temperature_centi', state.row.temperature_centi)), node('span', `Umidade ${formatField('humidity_centi', state.row.humidity_centi)} · sensor ${state.row.sensor_id}`));
      if (comparison.fields.includes('temperature_centi')) metric.classList.add('metric-diff');
      card.append(metric);
      card.append(fieldsTable(state.row, comparison.fields, source === 'redis'));
      const edit = node('button', `Editar no ${names[source]}`, 'secondary visual-edit'); edit.type = 'button';
      edit.addEventListener('click', () => onEdit(state.row, source)); card.append(edit);
    } else {
      card.append(node('div', state.kind === 'missing' ? 'Registro não encontrado · HTTP 404' : `Leitura não confirmada · ${current?.status ? 'HTTP ' + current.status : 'sem resposta'}`, 'database-empty'));
    }
    if (before.length) {
      const change = describeChange(previous, current);
      const timeline = node('div', undefined, 'reading-change'); timeline.dataset.change = change.kind;
      timeline.append(node('strong', change.message));
      const mutation = results.find(r => r.source === source);
      timeline.append(node('small', mutation ? `Escrita: ${mutation.request.method} · ${mutation.status ? 'HTTP ' + mutation.status : 'sem resposta HTTP'}` : 'Não foi enviada escrita a este banco.'));
      if (change.fields.length) {
        const list = node('ul');
        for (const field of change.fields) list.append(node('li', `${labels[field]}: ${formatField(field, readingState(previous).row?.[field])} → ${formatField(field, state.row?.[field])}`));
        timeline.append(list);
      }
      card.append(timeline);
    }
    card.append(node('p', source === 'postgres'
      ? 'A tabela define colunas e restrições. O índice de chave primária localiza esta linha.'
      : 'A chave localiza o hash. Neste projeto, scripts Lua também mantêm o índice por sensor e a unicidade.', 'database-explanation'));
    cards.append(card);
  }
  target.append(cards);
  let explanation = 'Mesma leitura lógica, duas estruturas. O formato de armazenamento não exige valores diferentes.';
  if (comparison.kind === 'different') explanation = 'Os bancos guardam cópias independentes. Alterar apenas uma fonte não replica a mudança para a outra. A divergência é dos dados; não é uma falha do modelo Redis ou PostgreSQL.';
  else if (comparison.kind === 'unknown') explanation = 'Uma falha de conexão não significa que o registro foi excluído. Consulte novamente para confirmar o estado.';
  else if (comparison.kind === 'absent') explanation = 'Nenhum banco retornou esta leitura. Você pode criar o exemplo de demonstração abaixo.';
  const note = node('p', explanation, 'visual-explanation');
  if (action && before.length) note.append(document.createTextNode(' O antes/depois foi consultado separadamente e pode incluir alterações de outra sessão.'));
  target.append(note);
}
export function renderAggregate(results, action) {
  const target = el('aggregate-visual'); target.hidden = false; target.replaceChildren();
  target.append(node('h4', action === 'summary' ? 'Resumo retornado pelos bancos' : 'Histórico retornado pelos bancos'));
  const cards = node('div', undefined, 'aggregate-pair');
  for (const result of results) {
    const card = node('article', undefined, 'aggregate-card ' + result.source); card.append(node('h4', names[result.source]));
    if (!result.ok) card.append(node('p', `Consulta não concluída · HTTP ${result.status ?? 'indisponível'}`));
    else if (action === 'summary') {
      const d = result.response.data;
      card.append(node('strong', `${d.count.toLocaleString('pt-BR')} leituras`));
      card.append(node('p', `${d.sensors.toLocaleString('pt-BR')} sensores · ${d.alerts.toLocaleString('pt-BR')} alertas`));
      card.append(node('p', d.count ? `Média: ${formatField('temperature_centi', d.temperature_sum / d.count)}` : 'Sem leituras neste intervalo.'));
    } else {
      const rows = result.response.data;
      card.append(node('strong', `${rows.length.toLocaleString('pt-BR')} leituras retornadas`));
      card.append(node('p', rows.length ? `Primeiro ID: ${rows[0].id} · Último ID: ${rows.at(-1).id}` : 'Nenhuma leitura neste intervalo.'));
    }
    cards.append(card);
  }
  target.append(cards, node('p', 'Filtros e retornos completos no console. Este resumo não altera a leitura individual mostrada acima.', 'visual-explanation'));
}
