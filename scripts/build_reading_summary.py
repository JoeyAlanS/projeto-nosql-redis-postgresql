"""Gera o resumo editável das melhorias e rotas a partir do código e medições locais.

Autoria opcional: python-docx. Renderize e confira o Word antes da entrega.
"""
from pathlib import Path
import json
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
report=json.loads((ROOT/'results/live/benchmark.json').read_text())
doc=Document();section=doc.sections[0]
section.page_width=Inches(8.5);section.page_height=Inches(11)
section.left_margin=section.right_margin=Inches(.8)
section.top_margin=Inches(.65);section.bottom_margin=Inches(.65)
section.header_distance=section.footer_distance=Inches(.3)
styles=doc.styles
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','List Bullet','Caption']:
 st=styles[name];st.font.name='Noto Sans';st.font.color.rgb=RGBColor(0,0,0)
styles['Normal'].font.size=Pt(10.5)
styles['Normal'].paragraph_format.line_spacing=1.12
styles['Normal'].paragraph_format.space_after=Pt(7)
styles['Title'].font.size=Pt(23);styles['Title'].paragraph_format.space_after=Pt(10)
styles['Subtitle'].font.size=Pt(11)
for name,size in [('Heading 1',17),('Heading 2',12)]:
 st=styles[name];st.font.size=Pt(size);st.paragraph_format.space_before=Pt(10);st.paragraph_format.space_after=Pt(7);st.paragraph_format.keep_with_next=True
styles['List Bullet'].paragraph_format.space_after=Pt(6)
code=styles.add_style('Code Sample',1);code.font.name='DejaVu Sans Mono';code.font.size=Pt(8.5);code.font.color.rgb=RGBColor(0,0,0)
code.paragraph_format.space_after=Pt(0);code.paragraph_format.space_before=Pt(0);code.paragraph_format.line_spacing=1.08
code.paragraph_format.left_indent=Inches(.08);code.paragraph_format.right_indent=Inches(.08)
for name in ['Normal','List Bullet','Code Sample']:styles[name].paragraph_format.widow_control=True
footer=section.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
footer.add_run('Projeto IoT  |  Resumo técnico  |  ').font.size=Pt(8)
f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),'PAGE');footer._p.append(f)
header=section.header.paragraphs[0];header.add_run('REDIS E POSTGRESQL').font.size=Pt(8)
props=doc.core_properties;props.title='Melhorias e rotas de leitura do projeto IoT';props.author='Joey Alan e Thiago Rabelo';props.subject='Resumo das mudanças e dos caminhos de leitura';props.comments='';props.keywords='Redis PostgreSQL IoT rotas leitura desempenho'

def p(text,style=None):return doc.add_paragraph(text,style)
def h(text):doc.add_heading(text,level=2)
def bullet(label,text):
 para=doc.add_paragraph(style='List Bullet');para.add_run(label+' ').bold=True;para.add_run(text)
def block(text):
 lines=text.strip().splitlines()
 for i,line in enumerate(lines):
  para=p(line,'Code Sample');para.paragraph_format.keep_with_next=i<len(lines)-1
  shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'F3F5F7');para._p.get_or_add_pPr().append(shade)
 doc.add_paragraph().paragraph_format.space_after=Pt(1)
def table(headers,rows,widths):
 t=doc.add_table(rows=1,cols=len(headers));t.autofit=False;t.alignment=WD_TABLE_ALIGNMENT.CENTER
 for col,w in zip(t.columns,widths):col.width=Inches(w)
 for i,values in enumerate([headers]+rows):
  cells=t.rows[0].cells if i==0 else t.add_row().cells
  trpr=cells[0]._tc.getparent().get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
  if i==0:trpr.append(OxmlElement('w:tblHeader'))
  for j,(cell,value,w) in enumerate(zip(cells,values,widths)):
   cell.width=Inches(w);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   tcpr=cell._tc.get_or_add_tcPr();b=OxmlElement('w:tcBorders')
   for edge in ['top','left','bottom','right']:
    e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');b.append(e)
   tcpr.append(b)
   mar=OxmlElement('w:tcMar')
   for edge in ['top','left','bottom','right']:
    e=OxmlElement('w:'+edge);e.set(qn('w:w'),'85');e.set(qn('w:type'),'dxa');mar.append(e)
   tcpr.append(mar)
   if i==0:
    shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E7EEF5');tcpr.append(shade)
   para=cell.paragraphs[0];para.paragraph_format.space_after=Pt(1);para.paragraph_format.line_spacing=1.08
   run=para.add_run(str(value));run.bold=i==0;run.font.size=Pt(9.5);run.font.color.rgb=RGBColor(0,0,0)
   if j>0 and len(str(value))<20:para.alignment=WD_ALIGN_PARAGRAPH.CENTER
 doc.add_paragraph().paragraph_format.space_after=Pt(1)
def page(title):
 para=doc.add_heading(title,level=1);para.paragraph_format.page_break_before=True

p('Melhorias e rotas de leitura do projeto IoT','Title')
p('Resumo para estudar o código e apresentar o trabalho','Subtitle')
p('Revisão de 20 de novembro de 2026  |  Código de referência fddc8ba').runs[0].font.size=Pt(9)
p('O projeto foi melhorado em duas etapas: reduzir o custo das consultas históricas e criar uma central operacional de estado atual e alertas. O ganho principal da central vem de manter os indicadores em cada escrita, para que a consulta encontre um resultado pronto. PostgreSQL e Redis implementam esse mesmo contrato.')
table(['Conjunto','Quantidade em cada banco','Finalidade'],[
 ['Histórico principal','1.000.000 leituras','Buscar uma medição e analisar períodos'],
 ['Central operacional','1.000 estados e 11 resumos','Consultar o estado de 1.000 sensores em 10 locais']],[1.35,1.9,3.65])
p('A central é inicializada pela última leitura de cada sensor. Depois, recebe alterações próprias por PUT. O histórico e a central evoluem independentemente; o PUT da central não acrescenta uma leitura ao histórico. Remover um estado muda a contagem atual, sem apagar o sensor ou suas leituras históricas.')
h('Alterações implementadas e justificativas')
bullet('Histórico em um comando.', 'O sorted set otimizado passou a guardar os cinco campos completos. A consulta de até 200 leituras usa um ZRANGE, evitando buscar um hash para cada registro.')
bullet('Agregados diários.', 'Contagem, somas, alertas e extremos por sensor e dia reduzem o trabalho de resumo. Bordas parciais ainda leem registros exatos e há loops por sensor e dia.')
bullet('Menos preparação e conversão.', 'sensor_ids() seleciona somente os IDs necessários; a busca pontual não enumera sensores. hiredis acelera o parser do cliente Redis. No ensaio específico, o histórico passou de 1,490 para 1,124 ms.')
bullet('Central com leitura direta.', 'Hashes guardam estado e resumos global/local. Sorted sets ordenam temperaturas. A escrita ajusta apenas os dois escopos do sensor.')
bullet('Comparação equivalente.', 'A função SQL mantém estado, índices e resumos dentro de uma transação. O benchmark alterna os bancos e compara os retornos.')
bullet('Interface e proteção dos dados.', 'A dashboard consulta, grava e remove estados, mostra HTTP/JSON e aceita um banco ou Ambos. A carga protege a central contra substituição acidental.')

page('Como o histórico é consultado')
p('A aplicação expõe a mesma rota HTTP para os dois bancos. O parâmetro source escolhe o adaptador; operation escolhe a consulta. Os limites de período são inclusivos e o histórico retorna as primeiras leituras do intervalo em ordem crescente, até o limite solicitado.')
h('Uma leitura pelo seu identificador')
block('''GET /api/readings/500001?source=postgres
GET /api/readings/500001?source=redis

PostgreSQL: SELECT * FROM readings WHERE id = 500001;
Redis:      HGETALL iot:reading:500001''')
p('Fluxo: read_reading() em app/main.py chama store(source), que abre a conexão e entrega PostgresStore ou RedisStore. O método point() executa a consulta. O SQL usa a chave primária; o Redis localiza o hash pela chave. O resultado é convertido em JSON. Nesta rota, um registro ausente gera HTTP 404.')
p('Exemplo real conferido em 20/11: a leitura 500001 pertence ao sensor 1 e contém temperature_centi=3059 e humidity_centi=4573, isto é, 30,59 °C e 45,73%. O ID da leitura identifica um evento histórico, não o sensor.')
h('Histórico de um sensor por período')
block('''GET /api/query?source=postgres&operation=history&sensor_id=501&limit=200
GET /api/query?source=redis&operation=history&sensor_id=501&limit=200

-- SQL parametrizado no código
SELECT * FROM readings
WHERE sensor_id=%s AND ts BETWEEN %s AND %s
ORDER BY ts,id LIMIT %s;

# Redis otimizado; START e END representam timestamps UTC
ZRANGE iot:opt:v1:sensor:501:full START END BYSCORE LIMIT 0 200''')
p('Fluxo: query() chama run_query(); store() escolhe o banco; history() retorna os registros. O SQL tem índice por sensor/instante/ID com temperatura e umidade incluídas. O Redis otimizado devolve membros CSV completos; unpack() os converte em dicionários. Essa conversão dos resultados continua existindo.')
p('redis_mode=auto usa a estrutura otimizada quando ela está pronta. baseline força a implementação antiga: Lua faz ZRANGEBYSCORE dos IDs e HMGET de cada leitura. optimized exige os índices e responde 503 se ainda não estiverem prontos.')
h('Resumo por período')
p('Com operation=summary, run_query() seleciona os IDs e chama summary(). PostgreSQL calcula COUNT, SUM, MIN e MAX sobre readings. Redis combina os agregados diários e lê as bordas parciais. A rota SQL normal continua usando dados brutos; a view pré-agregada pertence aos experimentos. Não foi eliminada a agregação do histórico por muitos sensores.')

page('Como a central consulta e mantém o estado')
p('A rota /api/live chama live_store(source), que abre a conexão e verifica se a central está pronta. live_query() direciona state para latest(), summary para summary() e alerts para alerts(). O resultado aparece no campo data, junto de source, operation e elapsed_ms.')
table(['Operação','PostgreSQL','Redis'],[
 ['state e sensor_id','Linha em live_states por PK','Hash iot:live:v1:sensor:ID'],
 ['summary','Linha em live_summaries por scope','Hash ...:group:ESCOPO:summary'],
 ['alerts e limit','Índice de temperatura com LIMIT','Faixa do sorted set de temperaturas']],[1.25,2.65,3])
h('Exemplos equivalentes dentro dos bancos')
block('''-- Estado e resumo global
SELECT * FROM live_states WHERE sensor_id=501;
SELECT * FROM live_summaries WHERE scope='all';
-- Ranking de alertas
SELECT sensor_id,temperature_centi FROM live_states
WHERE temperature_centi>3200
ORDER BY temperature_centi DESC,sensor_id DESC LIMIT 20;

HGETALL iot:live:v1:sensor:501
HGETALL iot:live:v1:group:all:summary
ZREVRANGEBYSCORE iot:live:v1:group:all:temperatures \\
  +inf '(3200' WITHSCORES LIMIT 0 20''')
p('location=Laboratório consulta o escopo location:Laboratório. O hash do resumo tem até seis campos; HGETALL percorre esse pequeno hash. O ranking retorna até 20 itens, sem buscar cada sensor novamente. No shell, mantenha as aspas em \'(3200\'.')
h('O trabalho foi transferido para a escrita')
p('PUT /api/live/sensors/501 substitui o estado. Redis executa WRITE_LUA; PostgreSQL executa live_write(). Ambos leem o estado anterior, ajustam contagem, somas e alertas por diferença e mantêm os índices. No Redis há exatamente duas chamadas adjust: global e local. A leitura da central não usa esse script.')
p('Exemplo didático: passar de 28 °C para 36 °C acrescenta 800 centésimos à soma e um alerta, pois cruza o limite de 32 °C. A quantidade de sensores não muda. ZADD/ZREM e os índices SQL mantêm extremos e ranking, inclusive com temperaturas iguais. O DELETE mantém as mesmas estruturas ao remover o estado.')
p('Redis usa um script atômico em uma instância; SQL usa transação e um bloqueio para o resumo global compartilhado. Ambos na dashboard significa duas requisições independentes, sem commit conjunto. O timestamp do PUT é uma substituição explícita; a API ainda não rejeita eventos fora de ordem.')

page('Resultados e limites da comparação')
p('As tabelas usam medições já executadas. Histórico e estado atual respondem perguntas diferentes; não se deve calcular um ganho percentual entre esses dois contratos.')
h('Histórico antes e depois da otimização')
table(['Massa e operação','Redis original ms','Redis otimizado ms','SQL equivalente ms'],[
 ['1M e 200 leituras','7,084','2,179','1,803'],
 ['5M e 200 leituras','4,490','1,473','1,189'],
 ['1M e resumo completo','4.133,741','40,807','7,407'],
 ['5M e resumo completo','21.396,262','138,197','23,157']],[2.3,1.5,1.55,1.55])
p('Ensaio de 19/11, revisão 0d7a74a: 10 repetições e dois aquecimentos, antes do hiredis. SQL é indexado para histórico e pré-agregado para resumo. A view SQL era atualizada antes do teste; Redis mantém os agregados no CRUD. Os custos de manutenção diferem.')
h('Nova central com o mesmo contrato nos dois bancos')
labels={'estado_sensor':'Estado do sensor','resumo_global':'Resumo global pronto','resumo_local':'Resumo local pronto','top_20_alertas':'Top 20 alertas','atualizar_estado_e_indicadores':'Atualizar estado e indicadores'}
fmt=lambda v:f'{v:.3f}'.replace('.',',')
table(['Operação','PostgreSQL ms','Redis ms'],[[labels[k],fmt(v['postgres']['median_ms']),fmt(v['redis']['median_ms'])] for k,v in report['results'].items()],[3.6,1.65,1.65])
p('Ensaio de 19/11: 30 repetições, três aquecimentos, um cliente, ordem alternada e conexões reutilizadas; 300 tempos individuais. Os retornos foram iguais. Redis teve menor mediana nos cinco cenários nesta execução. A escrita repete o sensor 501 com os mesmos valores e inclui manutenção em ambos.')
p('SQL confirma COMMIT com synchronous_commit; Redis usa AOF everysec. As garantias de durabilidade diferem. Não é um teste de saturação. A API abre conexão por requisição; pools não foram implantados. elapsed_ms mede a consulta; o navegador mede HTTP completo.')
p('O plano da central mostrou Index Scan para estado, Seq Scan de apenas 11 resumos e Limit com Index Only Scan para alertas, com acessos ao heap. No Redis, três consultas após inicialização fizeram dois HGETALL e um ZREVRANGEBYSCORE, sem Lua, SCAN ou KEYS.')

page('Como demonstrar as rotas e encontrar o código')
p('No terminal do VS Code, dentro do repositório, execute os comandos abaixo. preparar-central preserva os estados existentes. Somente numa instalação vazia, execute make load antes de preparar.')
block('''make up
make preparar-central
make test-central
make benchmark-central
make graficos-central''')
p('O gráfico exige .venv-graficos com requirements-graficos.txt. Acesse localhost:8000/#live, /#operations e /docs. Portas locais: API 8000, PostgreSQL 55432 e Redis 56379. Dentro do Docker, a API acessa postgres:5432 e redis:6379. Cada banco possui volume persistente próprio.')
h('Consultar pelos mesmos parâmetros em cada banco')
block('''curl 'http://localhost:8000/api/readings/500001?source=postgres'
curl 'http://localhost:8000/api/readings/500001?source=redis'
curl 'http://localhost:8000/api/compare?operation=history&sensor_id=501&limit=3'
curl 'http://localhost:8000/api/live?source=postgres&operation=state&sensor_id=501'
curl 'http://localhost:8000/api/live?source=redis&operation=state&sensor_id=501'
curl 'http://localhost:8000/api/live?source=redis&operation=summary'
curl 'http://localhost:8000/api/live?source=redis&operation=alerts&limit=20' ''')
p('As leituras foram conferidas nos bancos locais, sem escritas. /api/compare consulta ambos e retorna equivalent. O histórico foi conferido com limit=3; seu padrão é 200. Na central, alertas têm limite de 100 na API e 20 na tela.')
h('Alterar pela central')
block('''curl -X PUT 'http://localhost:8000/api/live/sensors/501?source=redis' \\
  -H 'Content-Type: application/json' \\
  -d '{"ts":1900000000,"temperature_centi":3600,"humidity_centi":5100}' ''')
p('O comando altera o Redis com um instante de exemplo; troque source para postgres para repetir no SQL. Na dashboard, Ambos envia os mesmos valores e instante aos dois. Consulte estado, resumo e ranking. O sensor só entra no top 20 se estiver entre os mais quentes. Use a API para manter os indicadores junto com o estado.')
h('Onde mostrar cada parte na apresentação')
p('app/main.py: read_reading, run_query e live_query. app/store.py: point, history e summary dos dois adaptadores. app/redis_optimized.py: agregados diários. app/live.py: latest, summary, alerts e WRITE_LUA. sql/live.sql: live_write e índices. scripts/benchmark_live.py: método das medições.')
p('Fontes: results/live/benchmark.json, samples.json e checks.json; results/verification.json; docs/RESULTADOS_OTIMIZACAO.md; results/diagnostico/depois/latency.json. Os 52 testes e a verificação integral de 1M são evidências anteriores. Esta revisão conferiu rotas e preservou os benchmarks.')

# Remove qualquer decoração de título herdada do Word.
for st in doc.styles:
 if st.type==1 and st.element.pPr is not None:
  for border in list(st.element.pPr.findall(qn('w:pBdr'))):st.element.pPr.remove(border)
out=ROOT/'output/documentos/Resumo_Melhorias_Rotas_Redis_PostgreSQL.docx';out.parent.mkdir(parents=True,exist_ok=True);doc.save(out)
print(out)
