import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';

const root=process.cwd();
const runtime=process.env.IOT_ARTIFACT_RUNTIME;
const skill=process.env.IOT_PRESENTATION_SKILL;
if(!runtime || !skill) throw new Error('Defina IOT_ARTIFACT_RUNTIME e IOT_PRESENTATION_SKILL conforme docs/AUTORIA.md.');
process.env.RUNTIME_NODE_MODULES ||= path.join(runtime,'node/node_modules');
const requireRuntime=createRequire(path.join(runtime,'node/package.json'));
const {Presentation, PresentationFile, FileBlob}=await import(pathToFileURL(requireRuntime.resolve('@oai/artifact-tool')).href);
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const b=JSON.parse(await fs.readFile(path.join(root,'results/benchmark.json')));
const l=JSON.parse(await fs.readFile(path.join(root,'results/load.json')));
const id=JSON.parse(await fs.readFile(path.join(root,'docs/identificacao.json')));
const [q1,q2,q3]=b.queries;
const fmt=(v,d=3)=>Number(v).toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
const colors={ink:'#173544',green:'#16846d',muted:'#637d8b',bg:'#f6f8fa',pg:'#6587b5',redis:'#e67462'};
const font='Noto Sans';
const p=Presentation.create({slideSize:{width:1280,height:720}});

function text(s,content,x,y,w,h,size=28,color=colors.ink,bold=false){
 const sh=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 sh.text=content;sh.text.style={typeface:font,fontSize:size,color,bold,insets:0,autoFit:'none',verticalAlignment:'top',wrap:'square'};return sh;
}
function slide(title,notes=''){
 const s=p.slides.add();s.background.fill=colors.bg;
 text(s,title,70,52,1140,85,44,colors.ink,true);
 text(s,'OBSERVATÓRIO IoT / PROJETO 3',70,670,1020,25,14,colors.muted);
 text(s,String(p.slides.items.length).padStart(2,'0'),1160,670,50,25,14,colors.muted);
 s.speakerNotes.text=notes;return s;
}
function table(s,values,{x=70,y=165,w=1140,h=360,sizes=[],fontSize=24}={}){
 const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,
  ...(sizes.length?{columnWidths:sizes}:{}),values});
 t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({
  textStyle:{typeface:font,fontSize,color:colors.ink},margins:{top:12,bottom:12,left:14,right:14},anchor:'center'});
 t.borders.assign({style:'solid',fill:'#dce5e9',width:1});
 for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){
  t.getCell(r,c).fill=r===0?'#e0efe9':r%2?'#ffffff':'#edf2f5';
  if(r===0)t.getCell(r,c).text.style={typeface:font,fontSize,bold:true,color:colors.green};
 }
 return t;
}

// 1: capa tipográfica, sem dados ou imagens decorativas inventados.
{
 const s=p.slides.add();s.background.fill=colors.ink;
 text(s,'PROJETO 3 / BANCOS DE DADOS NoSQL',76,70,1120,35,22,'#80d1b5',true);
 text(s,'Redis e\nPostgreSQL',76,195,1120,225,88,'#ffffff',true);
 text(s,'Monitoramento ambiental com um milhão de leituras',80,463,1100,90,32,'#d9e6ed');
 text(s,id.integrantes.length?id.integrantes.join(', '):'Tema 3: chave-valor / cache',80,625,1100,40,20,'#a9bfcb');
 s.speakerNotes.text='0:00-1:00. Apresente a equipe e o problema: recuperar leituras ambientais e comparar bancos com os mesmos dados. Fonte: enunciado fornecido e docs/01_pesquisa.md. Identificação acadêmica em docs/identificacao.json.';
}
{
 const s=slide('Telemetria de um campus','1:00. Cada leitura reúne temperatura e umidade de um sensor em um instante. Os dados são sintéticos e não representam medições ambientais reais. Fonte: scripts/load.py e results/load.json.');
 text(s,'Sensores registram temperatura e umidade a cada cinco minutos.',70,175,650,140,34);
 text(s,'1.000.000',780,177,430,110,70,colors.green,true);
 text(s,'leituras em cada banco',790,295,400,55,26,colors.muted);
 table(s,[['Necessidade','Operação comparada'],['Localizar uma medição','Busca por ID'],['Acompanhar um sensor','Histórico por período'],['Analisar o campus','Contagem, médias e alertas']],{y:375,h:235,sizes:[540,600],fontSize:23});
}
{
 const s=slide('Chave-valor e aplicações','1:30-2:30. Explique chaves e estruturas. Memcached atende cache simples e reconstruível. Redis amplia o modelo. MEO: streaming. Axis Bank: leitura bancária. WRSTBND: PostgreSQL como registro e Redis operacional. Relatos do fornecedor, sem substituir o experimento. Fontes: https://redis.io/docs/latest/develop/data-types/ ; https://docs.memcached.org/userguide/faq/ ; https://redis.io/customers/meo/ ; https://redis.io/customers/axis-bank/ ; https://redis.io/customers/wrstbnd/');
 table(s,[['Aspecto','Redis','Memcached'],['Organização','Chaves e estruturas nativas','Itens simples de cache'],['Recursos usados aqui','Hashes, sorted sets e Lua','Referência teórica'],['Persistência','RDB e AOF configuráveis','Cache tradicional efêmero'],['Aplicações','Sessões, contadores e IoT','Resultados reconstruíveis']],{y:160,h:350,sizes:[260,455,425],fontSize:23});
 text(s,'Casos públicos: MEO, Axis Bank e WRSTBND',70,550,1140,45,29,colors.green,true);
 text(s,'Relatos do fornecedor. Os resultados do projeto vêm do experimento.',70,601,1140,42,22,colors.muted);
}
{
 const s=slide('Arquitetura da implementação','2:30-3:30. Frontend envia HTTP/JSON. API valida filtros e mede o acesso ao banco. As duas cópias são independentes. Não há sincronização contínua nem transação distribuída. Fonte: app/main.py, app/store.py, compose.yaml e docs/modelos/arquitetura.svg.');
 table(s,[['Camada','Implementação','Responsabilidade'],['Interface','HTML, CSS e JavaScript','Filtros e visualizações'],['API','Python e FastAPI','Validação, CRUD e tempos'],['Relacional','PostgreSQL 17.12','Tabelas, índices e WAL'],['NoSQL','Redis 8.10.3','Hashes, índices e AOF']],{y:160,h:360,sizes:[230,400,510],fontSize:24});
 text(s,'Um CSV canônico abastece as duas bases.',70,558,1140,50,31,colors.green,true);
 text(s,'Os scripts automatizam carga, verificação integral e experimentos.',70,612,1140,36,23,colors.muted);
}
{
 const s=slide('Duas representações da mesma leitura','3:30-5:00. Mostre os SVGs do modelo se necessário. PostgreSQL mantém FK e UNIQUE. Redis mantém referências em Lua e usa índice temporal explícito. Inteiros em centésimos evitam divergências de arredondamento. Atualizações removem as referências antigas. Fonte: docs/02_modelagem.md, sql/schema.sql e app/store.py.');
 table(s,[['Conceito','PostgreSQL','Redis'],['Sensor','sensors, chave primária','Hash iot:sensor:id'],['Leitura','readings, chave primária','Hash iot:reading:id'],['Associação','FK sensor_id','Referência e validação Lua'],['Histórico','Índice por sensor e instante','Sorted set por sensor'],['Unicidade','UNIQUE(sensor_id, ts)','Hash por sensor/instante']],{y:157,h:410,sizes:[230,455,455],fontSize:23});
 text(s,'CRUD equivalente: criar, ler, atualizar e excluir nos dois bancos.',70,605,1140,42,26,colors.green,true);
}
{
 const s=slide('Persistência e escalabilidade','5:00-6:00. Ressalte diferença de confirmação de escrita. Redis AOF everysec pode perder escritas em falhas. Noeviction impede expulsão automática, mas falta de RAM ainda pode causar erros. O protótipo é single instance. Redis Cluster tem 16.384 slots e exige redesenho das chaves e operações multichave deste modelo. Fontes: https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/ ; https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/ ; results/benchmark.json.');
 text(s,'PostgreSQL',70,170,525,55,34,colors.pg,true);
 text(s,'WAL com fsync ativo\nConfirmação síncrona\nRestrições e rollback\nÍndices mantidos pelo banco',70,250,525,230,29);
 text(s,'Redis',690,170,520,55,34,colors.redis,true);
 text(s,'AOF com fsync a cada segundo\nDados em memória\nScripts atômicos, sem rollback geral\nÍndices mantidos pela aplicação',690,250,520,240,29);
 text(s,'Cluster é possibilidade teórica: esta implementação usa uma instância e exige redesenho para distribuir as chaves.',70,550,1140,90,26,colors.muted);
}
{
 const s=slide('Massa verificada integralmente','6:00-7:00. Registro lógico é uma leitura, sem contar índices ou metadados. 1000 sensores, 1000 instantes por sensor, 10 locais, seed 42. CSV, PostgreSQL e Redis têm SHA-256 igual. A verificação compara todas as leituras e os índices temporais e de unicidade. Fontes: results/load.json e results/verification.json.');
 text(s,'1 milhão',70,160,730,125,88,colors.green,true);
 text(s,'de leituras comparadas individualmente',75,300,1100,65,35);
 text(s,'1.000 sensores\n10 locais\nSeed 42',75,405,440,150,31);
 text(s,'CSV: '+fmt(l.csv_bytes/1048576,2)+' MiB\nCarga PostgreSQL: '+fmt(l.postgres_load_seconds,2)+' s\nCarga Redis: '+fmt(l.redis_load_seconds,2)+' s',600,405,600,150,28);
 text(s,'SHA-256 igual nas três representações. Índices Redis também verificados.',75,595,1130,50,24,colors.muted);
}
{
 const s=slide('Método experimental','7:00-8:00. Explique cronômetro do cliente, rede e materialização completa. Conexões reutilizadas. Sem cache de resultados e sem limpar cache de SO. Ordem alternada. As diferenças de durabilidade continuam relevantes. Outros serviços estavam ativos no host. Fontes: scripts/benchmark.py, results/benchmark.json e results/benchmark_raw.csv.');
 table(s,[['Etapa','Procedimento'],['Preparação','5 aquecimentos por operação e fonte'],['Coleta','30 repetições, com ordem alternada'],['Comparação','Resultados idênticos em cada par'],['Estatística','Mediana e p95 de tempos do cliente'],['Ambiente','Cache aquecido e um cliente por vez']],{y:165,h:410,sizes:[300,840],fontSize:26});
 text(s,'180 amostras preservadas no CSV bruto.',70,604,1140,42,28,colors.green,true);
}
{
 const reduction=(1-q1.metrics.redis.median_ms/q1.metrics.postgres.median_ms)*100;
 const s=slide('Acesso por ID: Redis com menor mediana','8:00-9:30. Q1 busca a leitura 500001 e retorna os mesmos cinco campos. Redis usa HGETALL e PostgreSQL usa Index Scan pela chave primária. Ganho modesto: distribuições sobrepostas, sem teste formal de significância. A amostra ao vivo pode inverter. Fonte: results/benchmark_raw.csv, results/benchmark.json e results/plans.json.');
 const chart=s.charts.add('bar',{position:{left:65,top:170,width:715,height:385},title:'Mediana em milissegundos',titleTextStyle:{fontSize:24,typeface:font,color:colors.ink},
  categories:['Leitura #500001'],series:[{name:'PostgreSQL',values:[q1.metrics.postgres.median_ms],fill:colors.pg},{name:'Redis',values:[q1.metrics.redis.median_ms],fill:colors.redis}],
  hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:22,typeface:font}},barOptions:{direction:'column',grouping:'clustered'},
  xAxis:{textStyle:{fontSize:21,typeface:font}},yAxis:{min:0,max:0.42,majorUnit:0.1,numberFormatCode:'0.000',textStyle:{fontSize:18,typeface:font},majorGridlines:{fill:'#dce5e9',width:1}},
  dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.000',textStyle:{fontSize:23,typeface:font}},chartFill:colors.bg,plotAreaFill:colors.bg});
 applyPresentationChartFont(chart,{fontFamily:font});
 text(s,fmt(reduction,0)+'%',845,230,350,120,85,colors.green,true);
 text(s,'de redução na mediana\ndo acesso por chave',850,365,350,115,28);
 text(s,'A diferença é modesta e varia entre amostras. O ganho vale para este ensaio.',70,594,1140,55,25,colors.muted);
}
{
 const s=slide('Histórico e agregação favorecem PostgreSQL','9:30-11:00. Q2 retorna 200 registros. O índice que cobre os campos evita acessos ao heap. Q3 calcula resumo sobre 1000 sensores, um milhão de leituras. Redis Lua percorre hashes e ocupa a instância por aproximadamente 3 segundos. Não há respostas pré-agregadas em nenhuma fonte. Fonte: results/benchmark.json e results/plans.json.');
 table(s,[['Operação','PostgreSQL','Redis','Razão Redis/PG'],['Q2: histórico',fmt(q2.metrics.postgres.median_ms)+' ms',fmt(q2.metrics.redis.median_ms)+' ms',fmt(1/q2.postgres_over_redis,2)],['Q3: resumo',fmt(q3.metrics.postgres.median_ms)+' ms',fmt(q3.metrics.redis.median_ms)+' ms',fmt(1/q3.postgres_over_redis,2)]],{y:185,h:240,sizes:[340,260,270,270],fontSize:25});
 text(s,'Q2 usa o índice que cobre os campos retornados.',70,465,1140,70,30);
 text(s,'Q3 mostra o custo de percorrer um milhão de hashes em Lua.',70,552,1140,75,30,colors.muted);
}
{
 const s=slide('Dashboard sobre os bancos reais','11:00-12:30. Alterne local e sensor, aplique datas e troque a fonte. Os indicadores fazem novas consultas. O quadro inferior mostra o experimento salvo e a consulta pontual mede a chamada atual. A imagem é captura da execução, não substitui demonstração ao vivo. Fonte: results/evidencias/dashboard_painel.png e results/browser.json.');
 s.images.add({blob:new Uint8Array(await fs.readFile(path.join(root,'results/evidencias/dashboard_painel.png'))),contentType:'image/png',alt:'Filtros e indicadores do dashboard em execução com um milhão de leituras',fit:'contain',position:{left:70,top:165,width:1140,height:400}});
 text(s,'Filtros de local, sensor e período. Alternância entre PostgreSQL e Redis.',70,600,1140,52,27,colors.green,true);
}
{
 const s=slide('Demonstração ao vivo','12:30-16:00. Abra localhost:8000. Use Biblioteca, Sensor 0002 e 01/11 até 12:00 UTC, que resultam em 145 leituras. Troque de fonte. Compare ID 500001. Se uma amostra oscilar, mostre as medianas. Execute docker compose exec -T app python -m scripts.crud_demo e exiba results/crud.json. Confira os hashes na verificação. Fonte: docs/roteiro_apresentacao.md.');
 text(s,'1. Filtrar o campus e conferir os indicadores',70,175,1140,65,33);
 text(s,'2. Alternar a fonte mantendo os filtros',70,265,1140,65,33);
 text(s,'3. Comparar a leitura 500001 e as medianas',70,355,1140,65,33);
 text(s,'4. Executar o CRUD e mostrar a equivalência',70,445,1140,65,33);
 text(s,'http://localhost:8000',70,565,1140,65,34,colors.green,true);
}
{
 const s=slide('Critérios de escolha','16:00-18:00. Redis atende acessos operacionais por chave quando o benefício justifica RAM e manutenção de índices. PostgreSQL favorece relações e agregações neste protótipo. Memcached é alternativa de cache reconstruível. Diferencie confirmação de escrita, atomicidade de scripts e transações com rollback. Fontes: docs/02_modelagem.md, resultados e https://redis.io/docs/latest/develop/programmability/eval-intro/ .');
 text(s,'Redis',70,175,510,60,37,colors.redis,true);
 text(s,'Acesso frequente por chave\nEstruturas de dados especializadas\nRAM e índices na aplicação\nPersistência conforme o risco aceito',70,270,525,270,29);
 text(s,'PostgreSQL',680,175,530,60,37,colors.pg,true);
 text(s,'Integridade declarativa\nRelações e consultas ad hoc\nAgregações neste experimento\nTransações com rollback',680,270,530,270,29);
 text(s,'Uma arquitetura complementar pode usar histórico relacional e Redis para acessos selecionados.',70,585,1140,65,26,colors.muted);
}
{
 const s=slide('Conclusões e perguntas','18:00-20:00. Redis teve menor mediana em Q1. PostgreSQL venceu Q2 e Q3. As conclusões se restringem a um cliente, cache quente e esta configuração. Próximos ensaios: concorrência, cache frio, falhas, réplica e custo. Fontes completas em docs/referencias.md e evidências em results/. Documentos fornecidos: Projeto_3_NoSQL_Instrucoes_Atualizadas.pdf, entregáveis-1.pdf e Entrega_1_NoSQL_Chave_Valor_Redis_Memcached.pdf.');
 text(s,'O ganho do Redis apareceu na busca por ID.',70,178,1140,100,39,colors.green,true);
 text(s,'O relacional foi mais rápido no histórico e no resumo.',70,300,1140,100,35);
 text(s,'Os dados e resultados foram verificados em ambos os bancos.',70,415,1140,100,32);
 text(s,'Limites: cache aquecido, um cliente, sem testes de falha ou Cluster.',70,550,1140,75,26,colors.muted);
}

const build=path.join(root,'tmp/slides');const finalDir=path.join(root,'output/apresentacao');
await fs.mkdir(build,{recursive:true});await fs.mkdir(finalDir,{recursive:true});
const candidatePath=path.join(build,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidatePath);
const finalPath=path.join(finalDir,process.env.IOT_DECK_NAME||'Apresentacao_Final_Projeto_3.pptx');
await finalizePresentation({workspaceDir:root,candidatePath,finalPath,
 pythonExecutable:path.join(runtime,'python/bin/python3'),
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',
  ...[2,3,4,5,8,10].flatMap(n=>['--require-native-table-slide',String(n)])],
 explicitTotalSlideCount:14,requiredNativeTableOwnerSlides:[2,3,4,5,8,10],requiredNativeChartOwnerSlides:[9],
 materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,
 receiptPath:path.join(build,path.basename(finalPath)+'.validation.json')});
// Renderização a partir do PPTX final, não somente do objeto anterior à exportação.
const final=await PresentationFile.importPptx(await FileBlob.load(finalPath));
for(let i=0;i<final.slides.items.length;i++){
 const png=await final.export({slide:final.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(build,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
}
console.log(finalPath);
