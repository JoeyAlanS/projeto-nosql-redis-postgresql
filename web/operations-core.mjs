// Contrato do laboratório: validação e requisições sem dependência do DOM.
export const names = {postgres: 'PostgreSQL', redis: 'Redis'};
export const actions = {point: 'Consultar por ID', create: 'Criar leitura', update: 'Atualizar leitura', delete: 'Excluir leitura', history: 'Histórico do sensor', summary: 'Resumo do período'};
export const demo = {id: '9000000010', sensor: '1', ts: '2026-11-18T12:00:00', temperature: '28.50', humidity: '55.00'};
export const period = {start: '2026-11-01T00:00:00', end: '2026-11-01T00:45:00'};
const writing = new Set(['create', 'update']);
function integer(value, label, min, max) {
  const result = Number(value);
  if (String(value).trim() === '' || !Number.isSafeInteger(result) || result < min || result > max) throw new Error(`${label}: informe um inteiro entre ${min} e ${max}.`);
  return result;
}
function timestamp(value, label) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(value)) throw new Error(`${label}: informe uma data e hora válidas em UTC.`);
  const seconds = Date.parse(value + 'Z') / 1000;
  if (!Number.isSafeInteger(seconds) || seconds < 1 || seconds > 253402300799 || !new Date(seconds * 1000).toISOString().startsWith(value)) throw new Error(`${label}: data inválida.`);
  return seconds;
}
function centi(value, label, min, max) {
  const decimal = Number(String(value).replace(',', '.'));
  const scaled = decimal * 100;
  if (String(value).trim() === '' || !Number.isFinite(decimal) || decimal < min || decimal > max || Math.abs(scaled - Math.round(scaled)) > 1e-7) throw new Error(`${label}: use um valor de ${min} a ${max}, com até duas casas decimais.`);
  return Math.round(scaled);
}
export function buildOperation(input) {
  const {action, source} = input;
  if (!Object.hasOwn(actions, action) || !['both', 'postgres', 'redis'].includes(source)) throw new Error('Selecione uma operação e um banco válidos.');
  const mutation = ['create', 'update', 'delete'].includes(action);
  const data = {};
  if (['point', 'create', 'update', 'delete'].includes(action)) data.id = integer(input.id, 'ID da leitura', 1, 9000000000000000);
  if (writing.has(action) || action === 'history' || (action === 'summary' && input.sensor.trim())) data.sensor_id = integer(input.sensor, 'ID do sensor', 1, 2147483647);
  if (writing.has(action)) {
    data.ts = timestamp(input.ts, 'Instante da leitura');
    data.temperature_centi = centi(input.temperature, 'Temperatura', -50, 100);
    data.humidity_centi = centi(input.humidity, 'Umidade', 0, 100);
  }
  if (['history', 'summary'].includes(action)) {
    data.start = timestamp(input.start, 'Início do período');
    data.end = timestamp(input.end, 'Fim do período');
    if (data.end < data.start) throw new Error('O fim do período deve ser maior ou igual ao início.');
    if (action === 'history') data.limit = integer(input.limit, 'Máximo de leituras', 1, 1000);
  }
  const requests = (source === 'both' ? ['postgres', 'redis'] : [source]).map(bank => {
    const query = new URLSearchParams({source: bank});
    let path = '/api/readings', method = 'GET';
    if (action === 'history' || action === 'summary') {
      path = '/api/query'; query.set('operation', action);
      for (const [key, value] of Object.entries(data)) query.set(key, value);
    } else if (action === 'create') method = 'POST';
    else {
      path += '/' + data.id;
      if (action === 'update') method = 'PUT';
      if (action === 'delete') method = 'DELETE';
    }
    return {source: bank, method, path: path + '?' + query, ...(writing.has(action) ? {body: data} : {})};
  });
  return {action, source, data, mutation, requests};
}
export function describeCommand(operation, source) {
  const {action, data: d} = operation;
  const fields = 'id,sensor_id,ts,temperature_centi,humidity_centi';
  if (source === 'postgres') {
    if (action === 'point') return `SELECT * FROM readings WHERE id = $1;\nParâmetros: [${d.id}]`;
    if (action === 'create') return `INSERT INTO readings (${fields})\nVALUES ($1,$2,$3,$4,$5);\nParâmetros: ${JSON.stringify(Object.values(d))}\nCOMMIT na saída do contexto da conexão.`;
    if (action === 'update') return `UPDATE readings SET sensor_id=$1, ts=$2,\n  temperature_centi=$3, humidity_centi=$4\nWHERE id=$5 RETURNING *;\nParâmetros: ${JSON.stringify([d.sensor_id,d.ts,d.temperature_centi,d.humidity_centi,d.id])}\nCOMMIT na saída do contexto da conexão.`;
    if (action === 'delete') return `DELETE FROM readings WHERE id=$1 RETURNING *;\nParâmetros: [${d.id}]\nCOMMIT na saída do contexto da conexão.`;
    if (action === 'history') return `SELECT * FROM readings\nWHERE sensor_id=$1 AND ts BETWEEN $2 AND $3\nORDER BY ts,id LIMIT $4;\nParâmetros: ${JSON.stringify([d.sensor_id,d.start,d.end,d.limit])}`;
    return `SELECT count(*) AS count,\n  count(DISTINCT sensor_id) AS sensors,\n  COALESCE(sum(temperature_centi),0) AS temperature_sum,\n  COALESCE(sum(humidity_centi),0) AS humidity_sum,\n  count(*) FILTER (WHERE temperature_centi > 3200) AS alerts,\n  min(temperature_centi) AS minimum,\n  max(temperature_centi) AS maximum\nFROM readings\nWHERE sensor_id=ANY($1) AND ts BETWEEN $2 AND $3;\nSensores: ${d.sensor_id ?? 'todos cadastrados'}\nPeríodo: ${d.start} até ${d.end}`;
  }
  if (action === 'point') return `HGETALL iot:reading:${d.id}\nO Python converte os cinco campos para inteiros.`;
  if (action === 'history') return `Script HISTORY_LUA (execução atômica):\nZRANGEBYSCORE iot:sensor:${d.sensor_id}:readings ${d.start} ${d.end} LIMIT 0 ${d.limit}\nPara cada ID: HMGET iot:reading:<id> ${fields.replaceAll(',', ' ')}\nO Python transforma os resultados em objetos.`;
  if (action === 'summary') return `Script SUMMARY_LUA (execução atômica):\nSensores: ${d.sensor_id ?? 'todos cadastrados'}\nPor sensor: ZRANGEBYSCORE iot:sensor:<id>:readings ${d.start} ${d.end}\nPor leitura: HMGET iot:reading:<id> temperature_centi humidity_centi\nLua calcula contagem, somas, alertas (>3200), mínimo e máximo.\nDurante o script, outras operações Redis aguardam.`;
  if (action === 'delete') return `Script WRITE_LUA, operação delete, ID ${d.id}:\nConfere a existência e lê a versão atual.\nZREM no índice temporal do sensor atual.\nHDEL na unicidade sensor/instante.\nDEL iot:reading:${d.id}\nRetorna os cinco campos excluídos na mesma execução.`;
  return `Script WRITE_LUA, operação ${action}, ID ${d.id}:\nValida existência, sensor e unicidade sensor/instante.\n${action === 'update' ? 'Remove os índices anteriores (ZREM e HDEL).\n' : ''}HSET iot:reading:${d.id} ${Object.entries(d).flat().join(' ')}\nZADD iot:sensor:${d.sensor_id}:readings ${d.ts} ${d.id}\nHSET iot:unique:${d.sensor_id} ${d.ts} ${d.id}\nTodos os passos são atômicos neste Redis standalone.`;
}
// Ignora a ordem das propriedades, preserva ordem de listas e tipos dos valores.
export function differences(left, right, path = '$', output = []) {
  if (Object.is(left, right)) return output;
  const objects = left !== null && right !== null && typeof left === 'object' && typeof right === 'object';
  if (objects && Array.isArray(left) === Array.isArray(right)) {
    for (const key of new Set([...Object.keys(left), ...Object.keys(right)])) {
      if (!Object.hasOwn(left, key) || !Object.hasOwn(right, key)) output.push({field: `${path}.${key}`, postgres: Object.hasOwn(left, key) ? left[key] : '(ausente)', redis: Object.hasOwn(right, key) ? right[key] : '(ausente)'});
      else differences(left[key], right[key], `${path}.${key}`, output);
      if (output.length >= 20) break;
    }
  } else output.push({field: path, postgres: left, redis: right});
  return output;
}
export function compareResults(results, action) {
  if (results.length !== 2) return {kind: results[0]?.ok ? 'success' : 'error', message: results[0]?.ok ? 'Operação concluída no banco selecionado.' : 'A operação não foi concluída. Confira o retorno abaixo.'};
  if (!results.every(r => r.ok)) return {kind: 'error', message: results.some(r => r.ok) ? 'Resultado parcial: um banco concluiu e o outro falhou. Nenhuma reversão automática foi feita.' : 'Os dois bancos retornaram erro. Confira os códigos e as mensagens.'};
  const data = results.map(r => ['history', 'summary'].includes(action) ? r.response.data : r.response);
  const diff = differences(...data);
  return {kind: diff.length ? 'different' : 'success', message: diff.length ? 'Resultados diferentes entre PostgreSQL e Redis.' : 'Resultados equivalentes nos dois bancos.', differences: diff};
}
export function errorHint(status) {
  return ({404: 'Leitura inexistente. Confira o ID e o banco selecionado.', 409: 'Conflito: o ID ou o par sensor/instante já existe. Consulte antes de criar novamente.', 422: 'Dados inválidos. Confira os campos, o sensor e o intervalo informados.', 500: 'Falha interna da API. Confira os logs do serviço app.', 503: 'Banco indisponível. Confira os serviços Docker.'})[status] || 'Não houve confirmação do resultado. Consulte a leitura antes de repetir uma escrita.';
}
