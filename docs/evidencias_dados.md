# Evidências da massa carregada

## Volume e equivalência

| Medida | Resultado observado |
|---|---|
| Leituras PostgreSQL | 1.000.000 |
| Leituras Redis | 1.000.000 |
| Sensores e seus índices verificados | 1.000 |
| Leituras comparadas individualmente | 1.000.000 |
| Verificação integral | 47,11 segundos |
| Redis evicted_keys | 0 |

SHA-256 idêntico no CSV, no fluxo ordenado PostgreSQL e nos hashes Redis:

519f2a3fceac765890289c51876e3be1980ff8c03d9f74d9768beb84a264369f

A verificação também conferiu todos os sorted sets e índices de unicidade por sensor. O relatório completo está em results/verification.json. Não há redução do mínimo de um milhão nem contagem de índices como registros de negócio.

## Carga e espaço ocupado

| Medida | Resultado |
|---|---|
| Geração do CSV | 4,45 segundos |
| Carga PostgreSQL com manutenção descrita | 15,15 segundos |
| Carga Redis com índices e espera de fsync | 50,44 segundos |
| CSV canônico | 30,31 MiB |
| PostgreSQL tabelas e índices | 207,59 MiB |
| Redis used_memory | 238,37 MiB |
| Redis used_memory_dataset | 198,35 MiB |
| Redis AOF após carga | 166,63 MiB |
| Diretório PostgreSQL, incluindo WAL e catálogo | 621,81 MiB |
| Diretório Redis persistido | 166,63 MiB |

RAM de processo, tabelas/índices e diretórios em disco medem categorias distintas. Os valores não são uma comparação direta de custo total. Os diretórios podem crescer após operações de teste. A carga Redis usa AOF everysec e PostgreSQL usa WAL com sincronização ativa, portanto diferenças de tempo não indicam a mesma durabilidade de escrita.

## Reproduzir e auditar

Use make up, make load e make verify. O CSV é determinístico para a seed e o volume registrados em results/load.json. O script de CRUD remove os dados temporários, preservando a massa original. As imagens executadas e os índices/bytes foram preservados em results/docker-images.json e results/storage.json. As instruções completas estão no README e em docs/03_dados.md.
