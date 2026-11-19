import test from 'node:test';
import assert from 'node:assert/strict';
import {buildOperation, compareResults, differences, demo, period} from '../../web/operations-core.mjs';
const base = {source: 'both', action: 'point', ...demo, ...period, limit: '20'};
test('seleção da variante só muda a consulta Redis e rejeita estratégia desconhecida', () => {
  for (const mode of ['auto','baseline','optimized']) {
    const operation = buildOperation({...base, action:'summary', 'redis-mode':mode});
    assert.equal(new URL(operation.requests[1].path,'http://localhost').searchParams.get('redis_mode'), mode);
    assert.equal(new URL(operation.requests[0].path,'http://localhost').searchParams.has('redis_mode'), false);
  }
  assert.throws(() => buildOperation({...base, 'redis-mode':'invalid'}));
});
test('CRUD envia inteiros exatos e fontes separadas para os endpoints existentes', () => {
  for (const [action, method] of [['point', 'GET'], ['create', 'POST'], ['update', 'PUT'], ['delete', 'DELETE']]) {
    const {requests} = buildOperation({...base, action});
    assert.deepEqual(requests.map(r => r.source), ['postgres', 'redis']);
    for (const r of requests) {
      assert.equal(r.method, method);
      assert.equal(r.path, `/api/readings${action === 'create' ? '' : '/' + demo.id}?source=${r.source}`);
      if (['create', 'update'].includes(action)) {
        assert.equal(r.body.temperature_centi, 2850);
        assert.equal(r.body.humidity_centi, 5500);
        assert.equal(r.body.id, 9000000010);
        assert.equal(r.body.ts, Date.UTC(2026, 10, 18, 12) / 1000);
      } else assert.equal(r.body, undefined);
    }
  }
});
test('resumo de 10 mil usa todos os sensores; histórico requer um sensor e limite', () => {
  const summary = buildOperation({...base, action: 'summary', sensor: ''});
  const url = new URL(summary.requests[0].path, 'http://localhost');
  assert.equal(url.searchParams.get('start'), '1793491200');
  assert.equal(url.searchParams.get('end'), '1793493900');
  assert.equal(url.searchParams.has('sensor_id'), false);
  assert.throws(() => buildOperation({...base, action: 'history', sensor: ''}));
  assert.throws(() => buildOperation({...base, action: 'history', limit: '1001'}));
  assert.equal(buildOperation({...base, action: 'history', source: 'redis'}).requests.length, 1);
});
test('rejeita entradas vazias, imprecisas, fora dos limites e datas inexistentes', () => {
  for (const patch of [{id: ''}, {id: '9000000000000001'}, {id: '1.5'}, {source: 'sqlite'}, {action: 'drop'}, {action: 'create', temperature: '28.501'}, {action: 'create', humidity: '101'}, {action: 'create', temperature: ''}, {action: 'create', ts: '2026-02-30T12:00'}, {action: 'summary', start: period.end, end: period.start}]) assert.throws(() => buildOperation({...base, ...patch}));
});
test('comparação ignora a ordem de propriedades e tempos, mas detecta tipos, campos e listas diferentes', () => {
  assert.deepEqual(differences({id: 1, temperature_centi: 2850}, {temperature_centi: 2850, id: 1}), []);
  const results = [1, 2].map(elapsed_ms => ({ok: true, response: {elapsed_ms, data: {count: 10000}}}));
  assert.equal(compareResults(results, 'summary').kind, 'success');
  assert.equal(compareResults([{ok: true, response: {temperature_centi: 2850}}, {ok: true, response: {temperature_centi: 3350}}], 'point').differences[0].field, '$.temperature_centi');
  assert.equal(differences({id: 1}, {id: '1'}).length, 1);
  assert.equal(differences([1, 2], [2, 1]).length, 2);
  assert.equal(differences({id: 1}, {}).length, 1);
});
test('falha parcial não aparece como equivalência nem como reversão confirmada', () => {
  assert.equal(compareResults([{ok: true, response: {}}, {ok: false, status: 409}], 'create').kind, 'error');
  assert.match(compareResults([{ok: true}, {ok: false}], 'create').message, /parcial/);
  assert.equal(compareResults([{ok: false}, {ok: false}], 'point').kind, 'error');
});
