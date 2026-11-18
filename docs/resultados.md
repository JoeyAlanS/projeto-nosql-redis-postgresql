# Resultados medidos e análise

Execução em 14/11/2026, sobre 1.000.000 leituras em cada base. Foram realizadas 30 repetições de cada consulta por fonte, após 5 aquecimentos. O arquivo bruto contém 180 amostras e os resultados de cada par coincidem. Tempos em milissegundos, medidos no cliente. Este é o ensaio original; as medições posteriores de 1M/5M estão em docs/COMPARACAO_1M_5M.md.

## Medianas e p95

| Operação | Mediana PostgreSQL | Mediana Redis | p95 PostgreSQL | p95 Redis |
|---|---|---|---|---|
| Q1 - Leitura por ID | 0,355 | 0,298 | 0,487 | 0,405 |
| Q2 - Histórico de sensor | 0,853 | 3,947 | 1,287 | 4,941 |
| Q3 - Resumo de telemetria | 188,166 | 3.124,577 | 267,294 | 3.350,199 |

O p95 usa interpolação linear sobre as 30 amostras. Os tempos mínimos e máximos e o hash de cada resposta estão nos arquivos de evidência. Não se arredondam as amostras antes de calcular as estatísticas.

## Vantagem observada do NoSQL

Na Q1, a mediana Redis foi 15,97% menor que a mediana PostgreSQL. A razão PostgreSQL/Redis foi 1,19. O cenário é a recuperação operacional de uma leitura conhecida pelo identificador, sem agregado ou junção. Redis resolve o acesso diretamente no hash e PostgreSQL usa a chave primária, com Index Scan confirmado no plano.

A diferença absoluta foi 0,0566 ms. Trata-se de uma vantagem modesta no ambiente testado, com distribuições sobrepostas e sem teste formal de significância. Uma consulta ao vivo pode inverter a ordem. Não se deve extrapolar esse ganho para throughput concorrente ou outros ambientes. O resultado atende ao cenário de menor mediana observado, sem retirar índices do relacional.

## Vantagens observadas do relacional

Na Q2, a mediana PostgreSQL foi 4,63 vezes menor. O plano usa Index Only Scan em readings_sensor_ts_idx, em ordem reversa para produzir os resultados crescentes. O índice cobre os campos necessários. Redis localiza os IDs pelo sorted set e reconstrói as 200 leituras por HMGET no script Lua, o que adiciona trabalho por objeto.

Na Q3, a mediana PostgreSQL foi 16,61 vezes menor. SQL agrega os dados pelo plano do SGBD, enquanto o script Lua percorre até um milhão de hashes. Essa operação ocupa a instância Redis durante cerca de 3,12 segundos neste ensaio. O resultado mostra por que consultas amplas não devem ser escolhidas apenas pela reputação de baixa latência do NoSQL.

## Ambiente e configurações

| Item | Valor registrado |
|---|---|
| CPU | 12th Gen Intel(R) Core(TM) i5-12450H |
| CPUs lógicas visíveis | 12 |
| RAM total do host | 15.773,81 MiB |
| Plataforma | Linux-7.2.11-arch1-1-x86_64-with-glibc2.41 |
| Python | 3.12.16 |
| PostgreSQL | 17.12 (Debian 17.12-1.pgdg13+1) |
| Redis | 8.10.3 |
| shared_buffers / work_mem | 128MB / 4MB |
| fsync / synchronous_commit | on / on |
| Redis persistência / memória | AOF everysec / noeviction / sem TTL |
| Concorrência | Um cliente e uma consulta por vez |
| Cache | Aquecido, sem cache de respostas da aplicação |

Os contêineres não têm limite adicional de CPU/RAM via cgroup. Outros serviços estavam ativos no computador. As imagens estão identificadas por digest no Compose e as dependências resolvidas em requirements.lock.txt. Não se afirma que as configurações de durabilidade são equivalentes.

## Validação do produto

Os 11 testes de integração passaram com bancos reais, incluindo CRUD, conflitos de unicidade, sensor inexistente, limites numéricos, validação HTTP, manutenção de índices, exclusão com atualização intercalada e equivalência de consultas. O log atual está em results/tests.log. A inspeção automatizada de navegador preservada em results/browser.json confirmou 14 chamadas de consulta, alternância de fonte equivalente, filtro de local com 100.000 leituras, filtro de sensor com 1.000 leituras e recorte temporal com 145 leituras. Também verificou ID inexistente, respostas divergentes e recuperação após datas inválidas. Essa inspeção de navegador não foi repetida na revisão documental. A consulta pontual real retornou resultados iguais.

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
