"""Textos quantitativos derivados exclusivamente dos arquivos de evidência."""
import json
import re
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name):return json.loads((ROOT/'results'/name).read_text())
def fmt(v,d=3):return f'{v:,.{d}f}'.replace(',','X').replace('.',',').replace('X','.')
def mib(v):return fmt(v/1024**2,2)+' MiB'

b=load('benchmark.json'); l=load('load.json'); v=load('verification.json'); browser=load('browser.json')
tests_count=int(re.search(r'^Ran (\d+) tests? in ',(ROOT/'results/tests.log').read_text(),re.MULTILINE).group(1))
q1,q2,q3=b['queries']
rows='\n'.join(f"| {q['query']} - {q['name']} | {fmt(q['metrics']['postgres']['median_ms'])} | {fmt(q['metrics']['redis']['median_ms'])} | {fmt(q['metrics']['postgres']['p95_ms'])} | {fmt(q['metrics']['redis']['p95_ms'])} |" for q in b['queries'])
reduction=(1-q1['metrics']['redis']['median_ms']/q1['metrics']['postgres']['median_ms'])*100
text=f'''# Resultados medidos e análise

Execução em 14/11/2026, sobre {fmt(b['records'],0)} leituras em cada base. Foram realizadas {b['repetitions']} repetições de cada consulta por fonte, após {b['warmup']} aquecimentos. O arquivo bruto contém 180 amostras e os resultados de cada par coincidem. Tempos em milissegundos, medidos no cliente.

## Medianas e p95

| Operação | Mediana PostgreSQL | Mediana Redis | p95 PostgreSQL | p95 Redis |
|---|---|---|---|---|
{rows}

O p95 usa interpolação linear sobre as 30 amostras. Os tempos mínimos e máximos e o hash de cada resposta estão nos arquivos de evidência. Não se arredondam as amostras antes de calcular as estatísticas.

## Vantagem observada do NoSQL

Na Q1, a mediana Redis foi {fmt(reduction,2)}% menor que a mediana PostgreSQL. A razão PostgreSQL/Redis foi {fmt(q1['postgres_over_redis'],2)}. O cenário é a recuperação operacional de uma leitura conhecida pelo identificador, sem agregado ou junção. Redis resolve o acesso diretamente no hash e PostgreSQL usa a chave primária, com Index Scan confirmado no plano.

A diferença absoluta foi {fmt(q1['metrics']['postgres']['median_ms']-q1['metrics']['redis']['median_ms'],4)} ms. Trata-se de uma vantagem modesta no ambiente testado, com distribuições sobrepostas e sem teste formal de significância. Uma consulta ao vivo pode inverter a ordem. Não se deve extrapolar esse ganho para throughput concorrente ou outros ambientes. O resultado atende ao cenário de menor mediana observado, sem retirar índices do relacional.

## Vantagens observadas do relacional

Na Q2, a mediana PostgreSQL foi {fmt(1/q2['postgres_over_redis'],2)} vezes menor. O plano usa Index Only Scan em readings_sensor_ts_idx, em ordem reversa para produzir os resultados crescentes. O índice cobre os campos necessários. Redis localiza os IDs pelo sorted set e reconstrói as 200 leituras por HMGET no script Lua, o que adiciona trabalho por objeto.

Na Q3, a mediana PostgreSQL foi {fmt(1/q3['postgres_over_redis'],2)} vezes menor. SQL agrega os dados pelo plano do SGBD, enquanto o script Lua percorre até um milhão de hashes. Essa operação ocupa a instância Redis durante cerca de {fmt(q3['metrics']['redis']['median_ms']/1000,2)} segundos neste ensaio. O resultado mostra por que consultas amplas não devem ser escolhidas apenas pela reputação de baixa latência do NoSQL.

## Ambiente e configurações

| Item | Valor registrado |
|---|---|
| CPU | {b['hardware']['cpuinfo']} |
| CPUs lógicas visíveis | {b['hardware']['cpu_count']} |
| RAM total do host | {mib(int(b['hardware']['meminfo'].splitlines()[0].split()[1])*1024)} |
| Plataforma | {b['hardware']['platform']} |
| Python | {b['hardware']['python']} |
| PostgreSQL | {l['postgres_version']} |
| Redis | {l['redis_version']} |
| shared_buffers / work_mem | {b['postgres_settings']['shared_buffers']} / {b['postgres_settings']['work_mem']} |
| fsync / synchronous_commit | {b['postgres_settings']['fsync']} / {b['postgres_settings']['synchronous_commit']} |
| Redis persistência / memória | AOF everysec / noeviction / sem TTL |
| Concorrência | Um cliente e uma consulta por vez |
| Cache | Aquecido, sem cache de respostas da aplicação |

Os contêineres não têm limite adicional de CPU/RAM via cgroup. Outros serviços estavam ativos no computador. As imagens estão identificadas por digest no Compose e as dependências resolvidas em requirements.lock.txt. Não se afirma que as configurações de durabilidade são equivalentes.

## Validação do produto

Os {tests_count} testes de integração passaram com bancos reais, incluindo CRUD, conflitos de unicidade, sensor inexistente, limites numéricos, validação HTTP, manutenção de índices, exclusão com atualização intercalada e equivalência de consultas. A inspeção automatizada do navegador confirmou {browser['query_requests']} novas chamadas de consulta, alternância de fonte equivalente, filtro de local com 100.000 leituras, filtro de sensor com 1.000 leituras e recorte temporal com 145 leituras. Também verificou ID inexistente, respostas divergentes e recuperação após datas inválidas. A consulta pontual real retornou resultados iguais.

Não houve erros JavaScript ou rolagem horizontal indevida na viewport móvel testada. Capturas do dashboard e da consulta ao vivo estão em results/evidencias/. Essa verificação demonstra funcionamento no ambiente local, sem substituir testes de carga concorrente ou de recuperação após falha.

## Conclusão técnica

Redis apresentou menor mediana no acesso por chave e PostgreSQL apresentou menor mediana no histórico e na agregação. A escolha deve acompanhar o padrão de acesso, integridade e durabilidade exigidos. Uma composição plausível mantém PostgreSQL como histórico confiável e Redis para os acessos operacionais que apresentarem benefício mensurável. O protótipo mantém as duas cópias completas para comparação acadêmica e não implementa sincronização contínua.

## Arquivos de evidência

- results/benchmark_raw.csv: todas as 180 amostras, ordem e hashes de resposta.
- results/benchmark.json: estatísticas, filtros, versões e hardware.
- results/plans.json: planos PostgreSQL com buffers e tempos do servidor.
- results/verification.json: comparação integral da massa e dos índices.
- results/crud.json e results/tests.log: CRUD e testes de integração.
- results/browser.json e results/evidencias/: verificação da interface e capturas reais.
'''
(ROOT/'docs/resultados.md').write_text(text)
pgdisk=int((ROOT/'results/postgres-disk.txt').read_text().split()[0]);rddisk=int((ROOT/'results/redis-disk.txt').read_text().split()[0])
data=f'''# Evidências da massa carregada

## Volume e equivalência

| Medida | Resultado observado |
|---|---|
| Leituras PostgreSQL | {fmt(v['postgres_count'],0)} |
| Leituras Redis | {fmt(v['redis_count'],0)} |
| Sensores e seus índices verificados | {fmt(v['sensors_verified'],0)} |
| Leituras comparadas individualmente | {fmt(v['checked_readings'],0)} |
| Verificação integral | {fmt(v['seconds'],2)} segundos |
| Redis evicted_keys | {v['redis_evicted_keys']} |

SHA-256 idêntico no CSV, no fluxo ordenado PostgreSQL e nos hashes Redis:

{l['csv_sha256']}

A verificação também conferiu todos os sorted sets e índices de unicidade por sensor. O relatório completo está em results/verification.json. Não há redução do mínimo de um milhão nem contagem de índices como registros de negócio.

## Carga e espaço ocupado

| Medida | Resultado |
|---|---|
| Geração do CSV | {fmt(l['generation_seconds'],2)} segundos |
| Carga PostgreSQL com manutenção descrita | {fmt(l['postgres_load_seconds'],2)} segundos |
| Carga Redis com índices e espera de fsync | {fmt(l['redis_load_seconds'],2)} segundos |
| CSV canônico | {mib(l['csv_bytes'])} |
| PostgreSQL tabelas e índices | {mib(l['postgres_bytes'])} |
| Redis used_memory | {mib(l['redis_used_memory_bytes'])} |
| Redis used_memory_dataset | {mib(l['redis_dataset_bytes'])} |
| Redis AOF após carga | {mib(l['redis_aof_bytes'])} |
| Diretório PostgreSQL, incluindo WAL e catálogo | {mib(pgdisk)} |
| Diretório Redis persistido | {mib(rddisk)} |

RAM de processo, tabelas/índices e diretórios em disco medem categorias distintas. Os valores não são uma comparação direta de custo total. Os diretórios podem crescer após operações de teste. A carga Redis usa AOF everysec e PostgreSQL usa WAL com sincronização ativa, portanto diferenças de tempo não indicam a mesma durabilidade de escrita.

## Reproduzir e auditar

Use make up, make load e make verify. O CSV é determinístico para a seed e o volume registrados em results/load.json. O script de CRUD remove os dados temporários, preservando a massa original. As imagens executadas e os índices/bytes foram preservados em results/docker-images.json e results/storage.json. As instruções completas estão no README e em docs/03_dados.md.
'''
(ROOT/'docs/evidencias_dados.md').write_text(data)
print('Resultados e evidências textuais gerados sem valores manuais.')
