# Entrega 4 - Experimentos e dashboard

## Perguntas do experimento

1. Qual a latência de recuperar uma leitura pelo seu ID?
2. Quanto custa buscar as primeiras 200 leituras de um sensor no período completo?
3. Quanto custa produzir um resumo exato do período para 1.000 sensores?

## Consultas comparáveis

| Consulta | PostgreSQL | Redis | Resultado |
|---|---|---|---|
| Q1 leitura por ID | SELECT pela PK | HGETALL | Os mesmos cinco campos de uma leitura |
| Q2 histórico | WHERE sensor/período, ORDER BY ts,id, LIMIT 200 | ZRANGEBYSCORE LIMIT e HMGET em Lua | Lista dos mesmos registros em ordem crescente |
| Q3 resumo | COUNT, COUNT DISTINCT, SUM, FILTER, MIN, MAX | Lua percorre sorted sets e hashes selecionados | Contagem, sensores, somas, alertas, mínimo e máximo |

Não há resposta pré-calculada para nenhum dos bancos. O resumo retorna somas inteiras e a UI calcula médias. Q1 usa ID 500001, Q2 usa sensor 501 e Q3 usa todos os 1.000 sensores. Os limites UTC exatos e a lista de sensores estão no JSON. O SQL está em `sql/queries.sql`; os comandos e scripts Redis em `app/store.py`.

## Protocolo

Usar `make benchmark` após a carga e a verificação. Cada consulta tem 5 aquecimentos por fonte e 30 repetições cronometradas por fonte, totalizando 180 medições válidas. O comando exige no mínimo 10 repetições. A ordem alterna PostgreSQL/Redis e Redis/PostgreSQL a cada repetição. Há um cliente e uma operação por vez.

A medição usa perf_counter_ns no cliente Python, do envio da operação até a materialização completa do resultado, incluindo rede, driver e conversão necessária para o contrato. Exclui criação de conexão, escolha dos sensores e serialização HTTP, igualmente nas duas fontes. Os scripts Lua aquecem o cache de scripts antes das amostras. Cada par de resultados precisa ser exatamente igual; o hash do resultado fica no CSV bruto.

O experimento usa cache aquecido. Não limpa caches de disco ou do SO. Redis usa RAM como arquitetura nativa e PostgreSQL pode usar shared_buffers e cache do SO. Ambos usam a mesma rede Docker e o mesmo cliente. Não existe cache de respostas na API. Há outros serviços no computador, portanto o ensaio não isola completamente ruído de carga. Medianas reduzem sensibilidade a extremos, mas não eliminam esse limite.

`results/benchmark_raw.csv` preserva cada amostra, ordem, fonte e hash de resultado. `results/benchmark.json` contém mediana, p95 por interpolação linear, mínimo, máximo, versões, hardware e configuração. `results/plans.json` inclui planos medidos fora das amostras de latência, pois EXPLAIN ANALYZE tem custo próprio. [15]

## Interpretação e limites

Um fator PostgreSQL/Redis maior que 1 indica menor mediana Redis. Um fator menor que 1 favorece PostgreSQL. A explicação da busca por ID considera o acesso direto a hash versus um índice B-tree e a execução SQL. Q2 inclui reconstrução de objetos nas duas fontes. Q3 evidencia a capacidade de agregação do SQL frente ao loop Lua sobre hashes. A análise final usa os números efetivamente obtidos, inclusive resultados desfavoráveis ao Redis.

O ensaio original de um cliente não mede throughput concorrente, cache frio, failover, replicação, recuperação após falha, custo de nuvem ou escalabilidade horizontal. A diferença de durabilidade (AOF everysec versus confirmação WAL) precisa acompanhar a interpretação. Não há medição empírica de Cluster ou Memcached. Q3 em Lua bloqueia o Redis da instância única durante a execução; isso restringe seu uso para painéis concorrentes.

## Complemento: volume e carga concorrente

A [comparação de 1M e 5M](COMPARACAO_1M_5M.md) usa duas bases isoladas, verificação integral, o mesmo protocolo de consultas e um ensaio HTTP de leitura por ID com 1, 4 e 16 clientes. Os tempos de carga inicial, latências de consultas e métricas de concorrência são apresentados separadamente. As instruções e os planos demonstráveis estão em [TESTES_CARGA_1M_5M.md](TESTES_CARGA_1M_5M.md). Os resultados originais de `results/benchmark.json` permanecem preservados; as novas medições ficam em `results/escala/`.

## Dashboard funcional

Disponível em http://localhost:8000 após `make up` e `make load`. O frontend faz chamadas à API, que consulta efetivamente a fonte selecionada. Os dados do gráfico e dos indicadores não vêm de imagens ou constantes.

- Indicadores: leituras no período, temperatura média, sensores com leituras e quantidade/proporção de alertas.
- Visualização temporal das primeiras 200 leituras do sensor escolhido; sem sensor específico, usa o primeiro sensor do local e informa isso no título.
- Filtros de local, sensor e intervalo UTC; local/sensor disparam nova consulta e datas são aplicadas pelo botão.
- Alternância PostgreSQL/Redis com os mesmos filtros e resultados equivalentes.
- Tempos reais do resumo e histórico em milissegundos.
- Consulta pontual ao vivo, lado a lado, com indicação de equivalência.
- Gráfico do benchmark de 30 repetições, com fonte e mediana identificadas. Esse painel usa o experimento salvo; o painel de consulta ao vivo mede uma nova chamada a cada clique.

A comparação ao vivo faz uma única execução por fonte, em ordem PostgreSQL e Redis. É ilustrativa e pode oscilar. A afirmação experimental deve se apoiar nas medianas de `results/benchmark.json`. O dashboard usa escala própria por operação no gráfico e explicita essa escolha.

## Demonstração de 20 minutos

O roteiro detalhado, divisão de tempo e perguntas esperadas estão em `docs/roteiro_apresentacao.md`. Uma execução ao vivo pode variar; se a amostra pontual oscilar, apresentar o experimento repetido e explicar a diferença entre amostra individual e mediana. A equipe precisa ensaiar a apresentação e realizar a entrega no sistema da disciplina.
