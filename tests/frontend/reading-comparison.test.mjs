import test from 'node:test';
import assert from 'node:assert/strict';
import {readingState, compareReadings, describeChange, formatField, executeWithSnapshots} from '../../web/reading-comparison.mjs';
import {buildOperation, demo, period} from '../../web/operations-core.mjs';
const row = {id:9000000010,sensor_id:1,ts:1795003200,temperature_centi:2850,humidity_centi:5500};
const found = (source, value = row) => ({source,ok:true,status:200,response:value});
const missing = source => ({source,ok:false,status:404,response:{detail:'Leitura não encontrada'}});
const unavailable = source => ({source,ok:false,status:null,response:{detail:'Falha de rede'}});
const input = {source:'both',action:'create',...demo,...period,limit:'20'};
test('404 confirma ausência; falha HTTP, rede e JSON incorreto permanecem desconhecidos', () => {
  assert.equal(readingState(missing('redis')).kind,'missing');
  for (const result of [unavailable('redis'),{ok:false,status:503},{ok:true,status:200,response:{}},undefined]) assert.equal(readingState(result).kind,'unknown');
});
test('comparação separa equivalência, diferença de campo, ausência e comparação incompleta', () => {
  assert.equal(compareReadings([found('postgres'),found('redis')]).kind,'equal');
  assert.deepEqual(compareReadings([found('postgres'),found('redis',{...row,temperature_centi:3350})]).fields,['temperature_centi']);
  assert.equal(compareReadings([found('postgres'),missing('redis')]).kind,'different');
  assert.equal(compareReadings([missing('postgres'),missing('redis')]).kind,'absent');
  assert.equal(compareReadings([missing('postgres'),unavailable('redis')]).kind,'unknown');
});
test('antes/depois não inventa mudança quando uma das consultas falha', () => {
  assert.equal(describeChange(missing('redis'),found('redis')).kind,'created');
  assert.equal(describeChange(found('redis'),missing('redis')).kind,'deleted');
  assert.deepEqual(describeChange(found('redis'),found('redis',{...row,temperature_centi:3350})).fields,['temperature_centi']);
  assert.equal(describeChange(found('postgres'),found('postgres')).kind,'unchanged');
  assert.equal(describeChange(unavailable('redis'),found('redis')).kind,'unknown');
});
test('captura ambos antes e depois; falha parcial não repete nem reverte escritas', async () => {
  const stored={postgres:row,redis:null},calls=[];
  const send=async request=>{
    calls.push([request.method,request.source]);
    if(request.method==='GET') return stored[request.source]?found(request.source,stored[request.source]):missing(request.source);
    if(stored[request.source]) return {source:request.source,status:409,ok:false};
    stored[request.source]=request.body;
    return {source:request.source,status:201,ok:true,response:request.body};
  };
  const result=await executeWithSnapshots(buildOperation(input),send);
  assert.deepEqual(calls,[['GET','postgres'],['GET','redis'],['POST','postgres'],['POST','redis'],['GET','postgres'],['GET','redis']]);
  assert.deepEqual(result.results.map(r=>r.status),[409,201]);
  assert.equal(compareReadings(result.before).kind,'different');
  assert.equal(compareReadings(result.after).kind,'equal');
});
test('consulta depois da escrita determina a tela; uma resposta de sucesso não substitui a confirmação', async () => {
  let calls=0;
  const send=async request=>{calls++;return calls>3?unavailable(request.source):found(request.source);};
  const result=await executeWithSnapshots(buildOperation({...input,action:'update',source:'redis'}),send);
  assert.equal(result.results[0].ok,true);
  assert.equal(compareReadings(result.after).kind,'unknown');
  assert.equal(result.results.length,1);
});
test('consulta por ID usa somente GET e unidades são convertidas sem alterar os valores armazenados', async () => {
  const methods=[];
  const result=await executeWithSnapshots(buildOperation({...input,action:'point'}),async r=>{methods.push(r.method);return found(r.source);});
  assert.deepEqual(methods,['GET','GET']);assert.equal(result.before.length,0);assert.equal(result.after.length,2);
  assert.equal(formatField('temperature_centi',2850),'28,50 °C');
  assert.equal(formatField('ts',1795003200),'2026-11-18 12:00:00 UTC');
});
