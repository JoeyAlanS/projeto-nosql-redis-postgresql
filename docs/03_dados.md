# Entrega 3 - Massa volumosa e documentação dos dados

## Origem e significado

Dados sintéticos, sem informações pessoais e sem pretensão de representar medições ambientais reais. O gerador é determinístico: seed 42, 1.000 sensores, 10 locais e 1.000.000 de leituras na base principal. Há 1.000 instantes por sensor, com intervalo de 300 segundos a partir de 01/11/2026 00:00 UTC. O último instante é 04/11/2026 11:15 UTC. O complemento de escala já executou cargas isoladas de 1 e 5 milhões; com 5 milhões são 5.000 instantes por sensor, até 18/11/2026 08:35 UTC. Os resultados de cada cenário estão em `results/escala/` e `docs/COMPARACAO_1M_5M.md`.

Para a leitura de ID i, sensor_id = ((i-1) mod S)+1 e passo = floor((i-1)/S). O timestamp é início + passo*300. A temperatura em centésimos é 2300 + ((sensor_id*17 + passo*7 + seed) mod 1400). A umidade é 3000 + ((sensor_id*31 + passo*13 + seed) mod 5000). Não há sorteio dependente da plataforma. O limite de alerta é estritamente maior que 3200 centésimos (32 °C).

## Dicionário

| Campo | Unidade / tipo lógico | Regra |
|---|---|---|
| id | Inteiro positivo | Identificador único da medição |
| sensor_id | Inteiro positivo | Sensor cadastrado |
| ts | Segundos Unix UTC | Único por sensor |
| temperature_centi | 0,01 °C | De -5000 a 10000 |
| humidity_centi | 0,01 ponto percentual | De 0 a 10000 |

O arquivo `data/readings.csv` não tem cabeçalho e segue exatamente essa ordem. O CSV é a fonte canônica das duas cargas. Metadados, hashes, índices, chaves auxiliares e réplicas não contam como registros lógicos adicionais.

## Procedimento reprodutível

```bash
make up
make load
make verify
docker compose exec -T app python -m scripts.crud_demo
make test
make benchmark
```

O carregador recusa substituir uma massa já existente sem `--replace`. Para gerar novamente a base principal, execute `docker compose exec -T app python -m scripts.load --records 1000000 --replace`. Esse comando substitui as tabelas e as chaves iot:* do projeto. Para repetir a comparação de 1M e 5M em ambientes separados, use `make escala` conforme `docs/TESTES_CARGA_1M_5M.md`. Os relatórios identificam a base principal e cada cenário isolado; não misturam seus tempos de carga.

## Verificação integral e evidências

`results/load.json` registra volumes, seed, SHA-256 do CSV, versões, bytes e tempos de carga. `results/verification.json` compara contagens, metadados de sensores, cada uma das leituras e todos os índices temporais e de unicidade do Redis. Os hashes SHA-256 do CSV, PostgreSQL e Redis precisam coincidir. Não se usa apenas uma amostra.

PostgreSQL: bytes medidos com pg_total_relation_size para as duas tabelas, incluindo seus índices. Redis: used_memory mede alocação do processo, used_memory_dataset identifica a parcela dos dados e aof_current_size registra persistência. RAM Redis e disco PostgreSQL são métricas diferentes, portanto não devem ser interpretados como a mesma categoria de armazenamento. `results/storage.json` complementa as medidas com o tamanho dos diretórios persistidos e dos índices, após a carga.

O tempo de geração do CSV fica separado. O tempo PostgreSQL inclui COPY, restrições, índices existentes, commit, VACUUM e ANALYZE. O tempo Redis inclui pipelining de hashes e índices e uma espera para fsync periódico. A publicação final dos metadados ocorre após essas medidas e não compõe o intervalo cronometrado Redis. O manifesto é idêntico no disco e na chave `iot:loaded` nas cargas revisadas. Os tempos de carga descrevem esses procedimentos e não provam equivalência de durabilidade entre os bancos.

As evidências JSON e os logs têm data real de execução. As capturas em `results/evidencias/` mostram o dashboard sobre a massa carregada. Se a carga for substituída, o carregador invalida benchmark, planos e verificação antigos. As publicações em PDF e slides devem ser regeneradas após novas medições.
