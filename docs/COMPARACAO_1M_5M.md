# Comparação real: 1 milhão e 5 milhões

Relatório gerado em 17/11/2026 a partir de ensaios locais; as datas de cada medição estão nos arquivos de evidência. Foram criadas duas bases isoladas: uma com **1.000.000** e outra com **5.000.000 de leituras em cada banco**. A base principal do dashboard continua com um milhão. Os volumes dos cenários continuam locais, separados e preservados após parar os serviços.

## O que significa cada teste

| Teste | O que varia | O que medimos |
|---|---|---|
| Carga inicial | Quantidade a inserir | Segundos para carregar e preparar os dados |
| Volume | 1 milhão ou 5 milhões armazenados | Latência das mesmas três consultas, com um cliente |
| Carga concorrente | 1, 4 e 16 clientes simultâneos | Requisições/s, mediana, p95 e erros de leituras HTTP |
| Estresse | Pressão crescente até ultrapassar a capacidade | Não foi executado; não afirmamos limite máximo |

Ter cinco vezes mais registros não significa ter cinco vezes mais usuários. O primeiro fator altera o tamanho dos dados e índices; o segundo altera a disputa por CPU, conexões e filas. O teste funcional verifica correção; a verificação integral confere todos os registros e índices.

## Carga inicial medida

| Leituras por banco | PostgreSQL (s) | Redis (s) | Geração CSV (s) |
|---|---|---|---|
| 1.000.000 | 17,64 | 59,44 | 4,38 |
| 5.000.000 | 92,76 | 301,05 | 21,66 |

Com 5x mais leituras, o tempo de carga foi multiplicado por **5,26 no PostgreSQL** e **5,06 no Redis**.

O tempo PostgreSQL inclui COPY com os índices existentes, commit e VACUUM ANALYZE. O Redis cria hashes, sorted sets e o índice de unicidade, faz pipeline em lotes e espera 1,1 s para o AOF everysec. O tempo de geração do CSV é separado. Há uma única carga medida por tamanho; estes fatores descrevem esta execução, sem prova de significância estatística e sem igualar garantias de durabilidade.

## Integridade

As duas massas foram verificadas integralmente: leituras, sensores, índices temporais e unicidade. CSV, PostgreSQL e Redis têm SHA-256 idênticos dentro de cada cenário. O hash de 1 milhão é diferente do de 5 milhões porque representam massas diferentes. São 1.000 sensores em ambos: 1.000 ou 5.000 leituras por sensor, em intervalos de cinco minutos. A massa maior prolonga o período, sem aumentar o número de sensores.


# Consultas: efeito do volume

Cada consulta teve **30 repetições por banco**, após cinco aquecimentos, alternando a ordem das fontes. São 180 amostras por cenário, 360 no total. Cada par de respostas foi comparado integralmente. Conexões são reutilizadas; o tempo inclui driver, rede e materialização, mas não HTTP ou criação de conexão.

| Leituras | Consulta | PG mediana (ms) | Redis mediana (ms) | PG p95 (ms) | Redis p95 (ms) |
|---|---|---|---|---|---|
| 1.000.000 | Q1 | 0,113 | 0,110 | 0,397 | 0,310 |
| 1.000.000 | Q2 | 0,758 | 3,713 | 1,097 | 4,184 |
| 1.000.000 | Q3 | 223,687 | 3.883,100 | 248,104 | 4.055,823 |
| 5.000.000 | Q1 | 0,435 | 0,344 | 0,727 | 0,519 |
| 5.000.000 | Q2 | 0,877 | 4,161 | 1,524 | 5,239 |
| 5.000.000 | Q3 | 1.270,031 | 21.690,764 | 1.399,424 | 22.436,753 |

## Como interpretar

- **Q1 - ID:** retorna uma leitura, usando a chave primária no PostgreSQL e um hash no Redis. Aumentar a base não obriga ler todos os registros.
- **Q2 - histórico:** retorna sempre as primeiras 200 leituras do sensor 501. Embora o índice cresça de 1.000 para 5.000 membros por sensor no Redis, o limite de resposta permanece 200. Portanto, esta consulta não lê cinco vezes mais resultados.
- **Q3 - resumo:** agrega todo o período e os mil sensores. Processa efetivamente um ou cinco milhões de leituras. Seu custo tende a crescer mais que a consulta por ID; observe o plano e as medições reais.

| Consulta | Crescimento PG (5M / 1M) | Crescimento Redis (5M / 1M) |
|---|---|---|
| Q1 | 3,86x | 3,12x |
| Q2 | 1,16x | 1,12x |
| Q3 | 5,68x | 5,59x |

Um fator abaixo de 1 significa que a mediana foi menor no cenário maior nesta execução. Isso pode ocorrer por cache, variação da máquina ou plano escolhido; não prova que aumentar o volume deixa o banco mais rápido. Os testes usam cache aquecido, não limpam o cache do SO e compartilham o computador com outros processos. Não foi realizado teste estatístico de significância.

**p95** é o percentil 95 por interpolação das amostras, não o maior tempo nem garantia de latência. Trinta amostras ajudam a ilustrar a distribuição, mas são poucas para caracterizar caudas raras.


# Carga: clientes simultâneos

Foram executadas **1200 requisições por fonte e nível**, com 1, 4 e 16 clientes. Cada cliente envia a próxima requisição após receber a anterior, sem pausa artificial. As mesmas leituras, distribuídas da primeira à última ID, foram consultadas nas duas fontes.

| Leituras | Banco | Clientes | Sucessos/s | Mediana (ms) | p95 (ms) | Erros |
|---|---|---|---|---|---|---|
| 1.000.000 | PG | 1 | 64,6 | 15,147 | 17,632 | 0 |
| 1.000.000 | Redis | 1 | 324,8 | 3,121 | 3,877 | 0 |
| 1.000.000 | PG | 4 | 173,0 | 22,580 | 28,558 | 0 |
| 1.000.000 | Redis | 4 | 476,3 | 8,293 | 10,765 | 0 |
| 1.000.000 | PG | 16 | 196,2 | 78,456 | 112,626 | 0 |
| 1.000.000 | Redis | 16 | 522,2 | 29,752 | 39,006 | 0 |
| 5.000.000 | PG | 1 | 61,6 | 16,078 | 18,220 | 0 |
| 5.000.000 | Redis | 1 | 297,0 | 3,281 | 4,706 | 0 |
| 5.000.000 | PG | 4 | 173,8 | 22,456 | 28,726 | 0 |
| 5.000.000 | Redis | 4 | 485,2 | 8,116 | 10,393 | 0 |
| 5.000.000 | PG | 16 | 199,6 | 76,201 | 110,741 | 0 |
| 5.000.000 | Redis | 16 | 480,0 | 31,657 | 46,989 | 0 |

## O que está sendo medido

O caminho é cliente HTTP, FastAPI, abertura de conexão ao banco, leitura do registro e resposta JSON. Cada resposta teve seus cinco campos conferidos com o gerador determinístico. Uma resposta rápida com HTTP de erro ou campos incorretos é contada como falha, nunca como sucesso.

Esses números não são diretamente comparáveis aos tempos Q1 da página anterior: aqui o escopo inclui HTTP e abertura de conexão; lá é uma operação de banco com conexão reutilizada. Os dois tamanhos usam o mesmo código HTTP, verificado por hash nas evidências.

## Diferença entre volume, carga e estresse

Volume é o tamanho persistido. Carga é a frequência e simultaneidade de operações. Mais clientes podem aumentar a vazão até surgirem filas; a latência, sobretudo o p95, pode crescer mesmo quando a vazão aumenta. Estresse levaria o sistema além de sua capacidade e observaria falhas e recuperação, o que não foi feito.

Este ensaio é curto e executado uma vez por nível/fonte. Não mede escrita simultânea, Q3 concorrente, pico sustentado durante horas ou capacidade máxima. Q3 usa Lua no Redis standalone e bloqueia outras operações enquanto executa; não extrapole o teste de leitura por ID para esse resumo.


# Planos: 1.000.000 leituras

Planos reais do PostgreSQL, capturados com **EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)** fora das amostras cronometradas. A árvore começa no nó final e mostra os nós filhos indentados. Leia o caminho dos filhos até o resultado. Listas ANY extensas estão abreviadas; a versão integral está em plans.json.

## Q1 - PostgreSQL

```text
Index Scan using readings_pkey on readings: cost=0.42..8.44, estimadas=1, linhas reais/loop=1, loops=1, tempo/loop=0.016 ms, blocos hit=4, read=0
  Index Cond: (id = 500001)
Execution Time: 0.034 ms
```

**Redis:** HGETALL iot:reading:500001 -> cinco campos de um único hash.

## Q2 - PostgreSQL

```text
Limit: cost=0.42..14.58, estimadas=200, linhas reais/loop=200, loops=1, tempo/loop=0.112 ms, blocos hit=6, read=0
  Index Only Scan using readings_sensor_ts_idx on readings: cost=0.42..70.79, estimadas=994, linhas reais/loop=200, loops=1, tempo/loop=0.083 ms, blocos hit=6, read=0
    Index Cond: ((sensor_id = '501'::smallint) AND (ts >= 1793491200) AND (ts <= 1793790900))
    Heap Fetches: 0
Execution Time: 0.148 ms
```

**Redis:** EVALSHA HISTORY_LUA -> ZRANGEBYSCORE de 1 sorted set (1000 membros), LIMIT 200 -> 200 HMGET -> 200 leituras.

## Q3 - PostgreSQL

```text
Aggregate: cost=48218.15..48218.16, estimadas=1, linhas reais/loop=1, loops=1, tempo/loop=287.831 ms, blocos hit=11110, read=0
  Index Only Scan using readings_sensor_ts_idx on readings: cost=0.42..35572.05, estimadas=632305, linhas reais/loop=1000000, loops=1, tempo/loop=154.79 ms, blocos hit=11110, read=0
    Index Cond: ((sensor_id = ANY ('{1,2,3,...,1000}'::smallint[] [1000 IDs; lista abreviada])) AND (ts >= 1793491200) AND (ts <= 1793790900))
    Heap Fetches: 0
Execution Time: 287.877 ms
```

**Redis:** EVALSHA SUMMARY_LUA -> 1000 ZRANGEBYSCORE -> 1,000,000 HMGET de temperatura/umidade -> agregação em Lua; bloqueia outras operações Redis durante o script.

## Como ler e comparar

`cost` é uma estimativa em unidades do otimizador, não milissegundos. `estimadas` são linhas previstas; `linhas reais/loop` e `tempo/loop` são médias por execução do nó. `loops` indica quantas vezes ele executou. `hit` indica blocos encontrados em shared_buffers; `read` indica blocos carregados para esse buffer e não prova acesso físico ao disco, pois o SO pode ter cache. Os tempos de nós pai incluem trabalho dos filhos: não some todos como se fossem independentes.

No Redis deste projeto não há SELECT nem plano relacional. O caminho acima é o algoritmo implementado em app/store.py. HGETALL tem custo proporcional aos campos do hash (cinco aqui); ZRANGEBYSCORE depende do índice e dos membros retornados. A agregação Lua visita todas as leituras selecionadas e não usa resultado pré-calculado. Os tempos EXPLAIN são do servidor PostgreSQL e não devem ser usados como se fossem os tempos completos do cliente Python ou do HTTP.


# Planos: 5.000.000 leituras

Planos reais do PostgreSQL, capturados com **EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)** fora das amostras cronometradas. A árvore começa no nó final e mostra os nós filhos indentados. Leia o caminho dos filhos até o resultado. Listas ANY extensas estão abreviadas; a versão integral está em plans.json.

## Q1 - PostgreSQL

```text
Index Scan using readings_pkey on readings: cost=0.43..8.45, estimadas=1, linhas reais/loop=1, loops=1, tempo/loop=9.17 ms, blocos hit=0, read=4
  Index Cond: (id = 500001)
Execution Time: 9.186 ms
```

**Redis:** HGETALL iot:reading:500001 -> cinco campos de um único hash.

## Q2 - PostgreSQL

```text
Limit: cost=0.43..14.41, estimadas=200, linhas reais/loop=200, loops=1, tempo/loop=0.148 ms, blocos hit=3, read=3
  Index Only Scan using readings_sensor_ts_idx on readings: cost=0.43..348.5, estimadas=4981, linhas reais/loop=200, loops=1, tempo/loop=0.116 ms, blocos hit=3, read=3
    Index Cond: ((sensor_id = '501'::smallint) AND (ts >= 1793491200) AND (ts <= 1794990900))
    Heap Fetches: 0
Execution Time: 0.19 ms
```

**Redis:** EVALSHA HISTORY_LUA -> ZRANGEBYSCORE de 1 sorted set (5000 membros), LIMIT 200 -> 200 HMGET -> 200 leituras.

## Q3 - PostgreSQL

```text
Aggregate: cost=238167.08..238167.09, estimadas=1, linhas reais/loop=1, loops=1, tempo/loop=1262.614 ms, blocos hit=2605, read=53504
  Index Only Scan using readings_sensor_ts_idx on readings: cost=0.43..174931.36, estimadas=3161786, linhas reais/loop=5000000, loops=1, tempo/loop=785.328 ms, blocos hit=2605, read=53504
    Index Cond: ((sensor_id = ANY ('{1,2,3,...,1000}'::smallint[] [1000 IDs; lista abreviada])) AND (ts >= 1793491200) AND (ts <= 1794990900))
    Heap Fetches: 0
Execution Time: 1263.21 ms
```

**Redis:** EVALSHA SUMMARY_LUA -> 1000 ZRANGEBYSCORE -> 5,000,000 HMGET de temperatura/umidade -> agregação em Lua; bloqueia outras operações Redis durante o script.

## Como ler e comparar

`cost` é uma estimativa em unidades do otimizador, não milissegundos. `estimadas` são linhas previstas; `linhas reais/loop` e `tempo/loop` são médias por execução do nó. `loops` indica quantas vezes ele executou. `hit` indica blocos encontrados em shared_buffers; `read` indica blocos carregados para esse buffer e não prova acesso físico ao disco, pois o SO pode ter cache. Os tempos de nós pai incluem trabalho dos filhos: não some todos como se fossem independentes.

No Redis deste projeto não há SELECT nem plano relacional. O caminho acima é o algoritmo implementado em app/store.py. HGETALL tem custo proporcional aos campos do hash (cinco aqui); ZRANGEBYSCORE depende do índice e dos membros retornados. A agregação Lua visita todas as leituras selecionadas e não usa resultado pré-calculado. Os tempos EXPLAIN são do servidor PostgreSQL e não devem ser usados como se fossem os tempos completos do cliente Python ou do HTTP.


# Comandos e roteiro de demonstração

Execute no terminal da raiz do projeto. A execução inicial cria volumes independentes e pode levar vários minutos:

```bash
python3 -m scripts.compare_scales
```

Para repetir a verificação, consultas e carga HTTP usando os dados isolados já carregados:

```bash
python3 -m scripts.compare_scales --reuse
```

Para apenas recalcular o resumo dos arquivos existentes, sem consultar os bancos:

```bash
python3 -m scripts.compare_scales --summarize-only
```

Abra http://localhost:8000/#scalability e mostre as três tabelas e os planos expansíveis. Elas usam resultados salvos, sem disparar um teste de cinco milhões ao abrir a página.

## Mostrar ao professor

1. Explique carga inicial, volume e clientes simultâneos.
2. Mostre a confirmação de 1M e 5M em results/escala/<tamanho>/verification.json.
3. Compare os tempos de carga e as medianas Q1, Q2 e Q3.
4. Abra os planos Q1 e Q2: aponte os índices e o limite de 200 resultados.
5. Abra Q3: mostre a quantidade real de linhas processadas e o caminho Lua equivalente.
6. Compare 1, 4 e 16 clientes na tabela de carga HTTP, observando sucessos/s, p95 e erros.
7. Conclua usando a operação medida: a tecnologia mais rápida pode mudar conforme a consulta e a fronteira de medição.

## Arquivos e comandos diretos dos bancos isolados

O cenário de 1M usa projeto Docker iot-escala-1000000 e sub-rede 10.203.18.0/24; o de 5M usa iot-escala-5000000 e 10.203.19.0/24. As sub-redes podem precisar de ajuste em outro computador. Não há portas publicadas. Consulte o guia docs/TESTES_CARGA_1M_5M.md para entrar em cada cenário e repetir EXPLAIN ou os comandos Redis.

Cada pasta results/escala/1000000 e results/escala/5000000 contém load.json, verification.json, benchmark.json, benchmark_raw.csv, plans.json, plans.txt, concurrent_load.json e concurrent_load_raw.csv. O resumo é results/escala/comparacao.json. As tabelas do dashboard e este documento vêm dessas evidências, não de números estimados.

## Fontes técnicas

- PostgreSQL 17, Using EXPLAIN: https://www.postgresql.org/docs/17/using-explain.html
- Redis HGETALL: https://redis.io/docs/latest/commands/hgetall/
- Redis ZRANGEBYSCORE: https://redis.io/docs/latest/commands/zrangebyscore/
- Redis Lua: https://redis.io/docs/latest/develop/programmability/eval-intro/

Fontes das medições: arquivos brutos e relatórios do repositório; execução local de 17/11/2026.
