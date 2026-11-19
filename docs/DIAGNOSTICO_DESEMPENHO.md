# Por que Redis ainda perde em algumas consultas?

Diagnóstico de 19/11/2026, com a base principal real de **1.000.000 de leituras**. Redis não é universalmente mais rápido: a vantagem depende da tarefa, da estrutura acessada, da quantidade de resultados e do caminho de execução. Neste projeto, ele já vence algumas consultas. O problema mais caro restante é agregar períodos sobre muitos sensores em Lua.

## Evidências medidas

O novo ensaio tem 30 repetições por variante, 3 aquecimentos, ordem rotativa, conexões reutilizadas, um cliente e igualdade exata das respostas. Os parsers Python e hiredis foram forçados no mesmo processo para compará-los. Não houve mudança nas leituras nem desativação de persistência. SQL bruto e pré-agregado são identificados separadamente.

| Consulta | PostgreSQL bruto (ms) | PostgreSQL pré-agregado (ms) | Redis com hiredis (ms) |
|---|---:|---:|---:|
| Uma leitura por ID | 0,396 | — | 0,220 |
| Histórico de 200 leituras | 1,044 | — | 1,124 |
| Resumo de 10 mil leituras, todos os sensores | 8,547 | 12,621 | 41,721 |
| Resumo de 1 milhão, todos os sensores | 252,176 | 6,855 | 37,679 |
| Resumo de um sensor, 1.000 leituras | 0,967 | 0,792 | 0,447 |

Fonte: [`results/diagnostico/depois/latency.json`](../results/diagnostico/depois/latency.json), com amostras em `samples.json`. Esses tempos incluem rede e processamento da resposta no cliente, sem HTTP. Medianas submilissegundo variam com escalonamento e carga da máquina; não demonstram superioridade universal nem significância estatística entre valores próximos.

## 1. PostgreSQL também está lendo da memória

O plano real do histórico é `Index Only Scan`, com **zero Heap Fetches**, **6 Shared Hit Blocks** e **zero Shared Read Blocks**. O índice já contém os cinco campos e a ordenação solicitada. O PostgreSQL não percorre o milhão de linhas nem precisa ler páginas de armazenamento nessa execução. Seu mecanismo nativo devolve as primeiras 200 entradas do índice.

A view do resumo contém apenas **4.000 linhas** (sensor/dia), com 576 kB incluindo índices na medição inicial. A expressão “Redis em RAM contra PostgreSQL em disco” descreve mal este ensaio com cache aquecido. `Shared Read Blocks = 0` é evidência de uso do buffer PostgreSQL nesse plano, não uma afirmação sobre todos os níveis de I/O de qualquer execução.

## 2. O resumo Redis ainda realiza milhares de operações

Usamos deltas de `INFO commandstats`, sem resetar estatísticas. Cada perfil repete a consulta cinco vezes e divide os contadores pelo número de execuções.

| Resumo Redis otimizado | ZRANGE internos | HMGET internos | Registros CSV interpretados nas bordas | Tempo interno médio do EVALSHA |
|---|---:|---:|---:|---:|
| 10 mil leituras de todos os sensores | 2.000 | 1.000 | 10.000 | 39,77 ms |
| 1 milhão de todos os sensores | 1.000 | 4.000 | 0 | 36,02 ms |
| Um sensor no período inteiro | 1 | 4 | 0 | 0,084 ms |

São **comandos internos ao Lua**, não milhares de viagens de rede. `EVALSHA` já inclui o tempo dos comandos internos; somar todas as linhas de `commandstats` contaria o mesmo trabalho duas vezes. Esses valores são médias internas, não parcelas obtidas subtraindo medianas do cliente. Tráfego concorrente contamina os deltas globais; execute o diagnóstico sozinho.

No intervalo 00:00–00:45, há dez leituras por sensor. Os agregados atuais são diários e contêm leituras posteriores a 00:45. Para respeitar o filtro, o código precisa abrir a borda parcial para **cada um dos 1.000 sensores**, interpretar CSV e somar as dez leituras. Já um período inteiro pode combinar os agregados prontos. Isso explica por que resumir 10 mil registros pode levar mais tempo que resumir o milhão inteiro.

O histórico já faz somente um `ZRANGE`. Seu tempo interno médio foi **0,026 ms**, enquanto o caminho completo do cliente levou mediana de 1,124 ms. O restante envolve transporte, espera pelo sistema e conversão de 200 strings CSV em 200 dicionários Python. Esses tempos têm definições diferentes: não se deve tratar sua diferença como uma decomposição exata. A complexidade documentada de `ZRANGE` é `O(log N + M)`; retornar mais resultados tem custo mesmo com tudo em RAM.

## 3. Havia custo desnecessário antes da consulta

Antes, a API carregava `SMEMBERS iot:sensors` e depois os **1.000 hashes completos** para obter uma lista de IDs. A pipeline já reduzia viagens de rede, mas não eliminava comandos, bytes e desserialização.

No diagnóstico atual, a seleção antiga custa 35,79 ms com parser Python ou 16,74 ms com hiredis. A nova seleção somente dos IDs custa **1,225 ms no Redis** e **2,227 ms no PostgreSQL**, no mesmo ensaio. A API usa agora `sensor_ids()`: `SMEMBERS` no Redis e `SELECT id` no PostgreSQL. Filtros por local continuam corretos; no Redis, esse caminho busca apenas o campo `location`, e ainda pode ser melhorado com sets por local.

A rota genérica `/api/query?operation=point` enumerava sensores mesmo sem precisar deles. Essa enumeração foi removida. A rota usada pela busca por ID do laboratório, `/api/readings/<id>`, já fazia acesso direto; não atribuímos a ela esse desperdício.

## 4. O cliente Redis usava parser Python

O ambiente anterior tinha `redis==5.2.1` sem hiredis; PostgreSQL já usava `psycopg[binary]`. O ensaio atual compara explicitamente ambos os parsers Redis. No histórico de 200 leituras, a mediana caiu de **1,490 para 1,124 ms** usando hiredis. No resumo amplo, quase não mudou: o servidor Lua é o gargalo e retorna apenas sete números.

`hiredis==3.5.0` foi incluído nas dependências, e redis-py passa a usar o parser compilado automaticamente. Isso melhora o cliente e preserva as consultas. Não elimina os loops do servidor.

## Efeito no caminho HTTP real

Ensaios separados de 20 repetições por banco/caminho, 3 aquecimentos e ordem alternada, com o mesmo cliente urllib e validação da resposta:

| Caminho | PostgreSQL antes → depois (ms) | Redis antes → depois (ms) |
|---|---:|---:|
| ID pela rota do laboratório | 20,21 → 19,87 | 6,55 → 5,98 |
| ID pela rota genérica | 24,37 → 19,99 | 45,74 → 6,24 |
| Histórico de 200 leituras | 24,86 → 29,00 | 11,21 → 13,46 |
| Resumo de 10 mil leituras | 36,87 → 37,03 | 84,63 → 51,00 |

Os dados estão em `http-before.json` e `http-after.json`. São execuções sequenciais na mesma máquina compartilhada, não pares intercalados entre versões. Há variação visível no histórico; não afirmamos ganho em todos os caminhos. O resumo Redis perdeu o grande custo de preparação, mas manteve aproximadamente 42–44 ms na consulta em si. Na medição HTTP atual, Redis já vence ID e histórico; com conexões reutilizadas, o custo da consulta do histórico ainda foi ligeiramente maior no Redis. São fronteiras de medição diferentes.

O console agora mostra `timings_ms`: conexão/seleção da estratégia, seleção de sensores, consulta, fechamento da conexão e total do backend. `elapsed_ms` continua significando somente o trecho da consulta. O tempo medido pelo navegador inclui também JSON, transporte e processamento no navegador. O backend total termina antes de FastAPI serializar/enviar a resposta.

## O que mudar no modelo para favorecer Redis

### A. Resumo global pronto e resumos por local

Para a pergunta fixa “resuma toda a base”, manter um hash com os sete campos finais evita percorrer sensores/dias na leitura:

```text
Modelo atual: 1.000 índices de dias → 4.000 hashes → Lua combina os valores
Modelo proposto: HGETALL iot:summary:global → sete campos já mantidos na escrita
```

O protótipo do diagnóstico criou uma resposta global temporária no Redis e a **mesma resposta pronta em uma tabela temporária PostgreSQL**. A leitura foi 0,320 ms no Redis e 0,422 ms no PostgreSQL. O custo de leitura diminui em ambos ao reduzir o trabalho a uma resposta pronta; esse resultado não prova que o CRUD completo já foi migrado ou que há vitória garantida. As estruturas temporárias são descartadas ao terminar.

A aplicação ainda não usa esse hash global. Para integrá-lo corretamente, inserções, alterações e exclusões devem manter contagens, somas, alertas, extremos e sensores distintos no mesmo script de escrita. Uma exclusão do único mínimo/máximo exige uma estrutura auxiliar, como frequência ordenada das temperaturas. Sensores distintos precisam de contadores por sensor; não basta somar a quantidade de sensores de vários dias.

### B. Intervalos de cinco minutos, agrupados globalmente e por local

Este é o próximo experimento indicado para o resumo 00:00–00:45. Com a massa atual alinhada a cinco minutos, a consulta combinaria **dez resumos globais de cinco minutos**, em vez de abrir os dados de mil sensores. Consultas por um sensor usariam os agregados desse sensor; consultas por local usariam agregados do local.

```text
Proposta: iot:summary:global:5m:<inicio_epoch>
Proposta: iot:summary:location:<local>:5m:<inicio_epoch>
Proposta: iot:summary:sensor:<id>:5m:<inicio_epoch>
```

É uma proposta, ainda sem integração ou benchmark em 1M/5M. Filtros que cortem um bucket devem ler exatamente suas bordas. A contagem distinta exige união exata de sensores presentes, por exemplo bitmaps com contadores para excluir corretamente, e não soma de contagens. Essa granularidade amplia memória e custo de escrita; deve ser escolhida pelas consultas mais frequentes. O controle SQL deve receber agregados com a mesma granularidade e estar igualmente atualizado.

### C. Conexões reutilizadas nos dois bancos

A API ainda cria conexões por requisição. Reutilizar um pool no Redis **e** um pool PostgreSQL reduz o custo de preparação para ambos. Isso deve ser testado com concorrência real e fechamento/limites corretos. A alteração desta revisão ativou hiredis e reduziu a seleção de sensores; não implantou os pools. A documentação Redis recomenda conexões duradouras e redução de viagens de rede.

### D. Redis como camada de consultas frequentes

Uma arquitetura apropriada a este problema é PostgreSQL para histórico completo e consultas flexíveis, com Redis para últimas leituras, indicadores prontos, contadores e consultas repetidas. Cache por filtros pode ajudar quando há repetição, desde que a expiração/invalidação seja explícita. Compare cache Redis com uma estratégia equivalente de resposta pronta quando o objetivo for avaliar o custo dessa estratégia; leitura de resposta pronta e cálculo analítico fazem trabalhos diferentes.

Mais memória, desligar AOF ou acrescentar threads de I/O não remove os loops de agregação Lua. O estado medido tinha zero evictions. Não reduzimos garantias de persistência para obter vantagem.

## Reproduzir e demonstrar

```bash
cd /home/joey/Documentos/GitHub/trabalho-banco-dados
make up
make test-otimizacao
make diagnostico
python3 -m scripts.diagnose_http --output results/diagnostico/http-reproducao.json
```

`make diagnostico` grava em `results/diagnostico/reproducao/`, preservando as evidências anteriores. Execute sem testes, operações manuais ou outros benchmarks simultâneos. O comando atualiza a view materializada experimental fora do tempo medido, usa namespace temporário com TTL e remove sua chave ao terminar. As leituras originais são preservadas. Dependências do container já incluem hiredis.

Na dashboard, clique em **03 · Resumir 10 mil leituras → Executar operação** e leia as fases no console. Depois selecione sensor 501 para observar o efeito de reduzir o número de sensores. Os gráficos de 1M/5M da revisão anterior continuam históricos. Esta investigação não repetiu os ensaios de 5 milhões nem testes de saturação.

Foram aprovados **41 testes**: 11 de integração, 12 de frontend, 3 dos exemplos, 5 das ferramentas de escala e 10 da otimização. As novas regressões conferem seleção por local, ausência de enumeração em ponto e coerência dos tempos. As amostras do diagnóstico também comparam todas as respostas exatamente.

## Fontes primárias

- [Redis: parser hiredis no redis-py](https://redis.io/docs/latest/develop/clients/redis-py/).
- [Redis: diagnóstico de latência, comandos e conexões](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency/).
- [Redis: ZRANGE e sua complexidade](https://redis.io/docs/latest/commands/zrange/).
- [Redis: INFO e commandstats](https://redis.io/docs/latest/commands/info/).
- [Redis: execução de scripts Lua](https://redis.io/docs/latest/develop/programmability/eval-intro/).
- [PostgreSQL 17: index-only scans e índices com INCLUDE](https://www.postgresql.org/docs/17/indexes-index-only-scans.html).
