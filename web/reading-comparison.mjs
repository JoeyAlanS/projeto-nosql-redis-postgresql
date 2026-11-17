// Estados de leitura: ausência (404) é diferente de falha de comunicação.
export const readingFields = ['id', 'sensor_id', 'ts', 'temperature_centi', 'humidity_centi'];
export const labels = {id: 'ID', sensor_id: 'Sensor', ts: 'Instante UTC', temperature_centi: 'Temperatura', humidity_centi: 'Umidade'};
export function readRequests(id) {
  return ['postgres', 'redis'].map(source => ({source, method: 'GET', path: `/api/readings/${id}?source=${source}`}));
}
export function readingState(result) {
  if (result?.status === 404) return {kind: 'missing', row: null};
  if (result?.ok && result.status === 200 && readingFields.every(k => Number.isSafeInteger(result.response?.[k]))) return {kind: 'found', row: result.response};
  return {kind: 'unknown', row: null};
}
export function compareReadings(results) {
  const states = Object.fromEntries(['postgres', 'redis'].map(source => [source, readingState(results.find(r => r.source === source))]));
  const {postgres: pg, redis: rd} = states;
  if (pg.kind === 'unknown' || rd.kind === 'unknown') return {states, kind: 'unknown', message: 'Comparação incompleta: um banco não confirmou a leitura.', fields: []};
  if (pg.kind === 'missing' && rd.kind === 'missing') return {states, kind: 'absent', message: 'Leitura ausente nos dois bancos.', fields: []};
  if (pg.kind !== rd.kind) return {states, kind: 'different', message: `Leitura presente somente no ${pg.kind === 'found' ? 'PostgreSQL' : 'Redis'}.`, fields: readingFields};
  const fields = readingFields.filter(k => pg.row[k] !== rd.row[k]);
  return {states, kind: fields.length ? 'different' : 'equal', message: fields.length ? `${fields.length} ${fields.length === 1 ? 'campo diferente' : 'campos diferentes'} entre os bancos.` : 'Mesmos valores nos dois bancos.', fields};
}
export function describeChange(before, after) {
  const previous = readingState(before), current = readingState(after);
  if (previous.kind === 'unknown' || current.kind === 'unknown') return {kind: 'unknown', message: 'Não foi possível confirmar o antes e depois.', fields: []};
  if (previous.kind === 'missing' && current.kind === 'found') return {kind: 'created', message: 'Leitura criada', fields: readingFields};
  if (previous.kind === 'found' && current.kind === 'missing') return {kind: 'deleted', message: 'Leitura excluída', fields: readingFields};
  if (previous.kind === 'missing') return {kind: 'unchanged', message: 'Continua ausente', fields: []};
  const fields = readingFields.filter(k => previous.row[k] !== current.row[k]);
  return {kind: fields.length ? 'updated' : 'unchanged', message: fields.length ? 'Valores alterados' : 'Sem mudança observada', fields};
}
export function formatField(key, value) {
  if (value === undefined || value === null) return '—';
  if (key === 'ts') return new Date(value * 1000).toISOString().slice(0, 19).replace('T', ' ') + ' UTC';
  if (key === 'temperature_centi' || key === 'humidity_centi') return (value / 100).toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + (key === 'temperature_centi' ? ' °C' : ' %');
  return String(value);
}
// As capturas são consultas separadas, não uma transação distribuída.
export async function executeWithSnapshots(operation, send, onResult = () => {}) {
  const readBoth = async () => {
    const outputs = [];
    for (const request of readRequests(operation.data.id)) outputs.push(await send(request));
    return outputs;
  };
  const before = operation.mutation ? await readBoth() : [];
  const results = [];
  for (const request of operation.requests) {
    const result = await send(request);
    results.push(result); onResult(result);
  }
  const after = operation.mutation || (operation.action === 'point' && operation.source !== 'both')
    ? await readBoth() : operation.action === 'point' ? results : [];
  return {before, results, after};
}
