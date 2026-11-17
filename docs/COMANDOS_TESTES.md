# Comandos para testar PostgreSQL e Redis

Execute no **Terminal > Novo Terminal do VS Code**, na pasta do projeto. Os blocos `bash` abaixo são comandos do terminal Linux; não os cole dentro de `psql` ou `redis-cli`. Copie um bloco completo por vez e aguarde terminar.

**A base carregada possui 1.000.000 de leituras em cada banco, de 1.000 sensores.** Os testes com **10.000 leituras** usam um recorte dessa base existente, sem recarregar os dados. PostgreSQL e Redis representam as mesmas medições.

Consultas, CRUD e testes deste roteiro foram conferidos em **17/11/2026**. Veja a [evidência da consulta das 10.000 leituras](../results/consulta_10000.json) e a [verificação integral do milhão](../results/verification.json). A nova execução do benchmark e o encerramento dos serviços são passos opcionais; os serviços foram mantidos em execução.

## 1. Abrir a pasta e iniciar os serviços

```bash
cd /home/joey/Documentos/GitHub/trabalho-banco-dados
docker compose up -d --build --wait
```

Conferir os três serviços:

```bash
docker compose ps
```

Testar as conexões reais da aplicação:

```bash
curl --fail-with-body -sS http://localhost:8000/api/health | python3 -m json.tool
```

Esperado: `postgres: ok` e `redis: ok`. Dashboard: **http://localhost:8000/**. API interativa: **http://localhost:8000/docs**.

Nesta instalação os dados já existem nos volumes. Não é necessário executar a carga novamente para testar.

## 2. Comprovar a quantidade que realmente existe

PostgreSQL — conta as linhas da tabela:

```bash
docker compose exec -T postgres psql -U iot -d iot -c "SELECT count(*) AS leituras, min(id) AS primeiro_id, max(id) AS ultimo_id FROM readings;"
```

Esperado: `1000000`, primeiro ID `1`, último ID `1000000`.

Redis — percorre as chaves das leituras e conta:

```bash
docker compose exec -T redis redis-cli --scan --pattern 'iot:reading:*' | wc -l
```

Esperado: `1000000`. A varredura pode levar alguns segundos. Execute sem outros testes gravando dados simultaneamente.

Sensores PostgreSQL:

```bash
docker compose exec -T postgres psql -U iot -d iot -c "SELECT count(*) AS sensores FROM sensors;"
```

Sensores Redis:

```bash
docker compose exec -T redis redis-cli SCARD iot:sensors
```

Ambos: `1000`. O comando Redis `DBSIZE` conta também índices e metadados, portanto não equivale à quantidade de leituras.

## 3. Ver a estrutura física

Tabelas e restrições PostgreSQL:

```bash
docker compose exec -T postgres psql -U iot -d iot -c '\dt'
docker compose exec -T postgres psql -U iot -d iot -c '\d readings'
```

Tipos das estruturas Redis e quantidade de leituras do sensor 1:

```bash
docker compose exec -T redis redis-cli TYPE iot:reading:500001
docker compose exec -T redis redis-cli TYPE iot:sensors
docker compose exec -T redis redis-cli TYPE iot:sensor:1:readings
docker compose exec -T redis redis-cli TYPE iot:unique:1
docker compose exec -T redis redis-cli ZCARD iot:sensor:1:readings
```

Esperado, na ordem: `hash`, `set`, `zset`, `hash`, `1000`.

## 4. Ler o mesmo registro nos dois bancos

PostgreSQL:

```bash
docker compose exec -T postgres psql -U iot -d iot -c "SELECT * FROM readings WHERE id = 500001;"
```

Redis:

```bash
docker compose exec -T redis redis-cli HGETALL iot:reading:500001
```

Comparar pela API, que consulta os dois bancos:

```bash
curl --fail-with-body -sS 'http://localhost:8000/api/compare?operation=point&reading_id=500001' | python3 -m json.tool
```

Esperado: `equivalent: true`, sensor `1`, timestamp `1793641200`, temperatura `3059` e umidade `4573`. As unidades estão em centésimos: **30,59 °C** e **45,73%**.

## 5. Principal teste: operar sobre 10.000 leituras existentes

O intervalo de **01/11/2026, 00:00 a 00:45 UTC**, inclusive, possui dez medições de cada um dos mil sensores: **10 × 1.000 = 10.000**. Na carga padrão, corresponde aos IDs `1` a `10000`. Não é uma base nova nem uma estimativa da contagem.

### 5.1. Contar, filtrar e agregar no PostgreSQL

```bash
docker compose exec -T postgres psql -U iot -d iot -c "SELECT count(*) AS leituras, count(DISTINCT sensor_id) AS sensores, round(avg(temperature_centi) / 100, 5) AS media_celsius, count(*) FILTER (WHERE temperature_centi > 3200) AS alertas, min(temperature_centi) / 100.0 AS minima_celsius, max(temperature_centi) / 100.0 AS maxima_celsius FROM readings WHERE ts BETWEEN 1793491200 AND 1793493900;"
```

Esperado: **10.000 leituras**, **1.000 sensores**, média **29,93280 °C**, **3.522 alertas**, mínima **23,00 °C**, máxima **36,99 °C**.

Mostrar dez dos registros desse recorte, com os valores convertidos:

```bash
docker compose exec -T postgres psql -U iot -d iot -c "SELECT id, sensor_id, to_timestamp(ts) AT TIME ZONE 'UTC' AS horario_utc, temperature_centi / 100.0 AS temperatura_celsius, humidity_centi / 100.0 AS umidade_pct FROM readings WHERE ts BETWEEN 1793491200 AND 1793493900 ORDER BY id LIMIT 10;"
```

### 5.2. Consultar o índice temporal Redis

```bash
docker compose exec -T redis redis-cli ZCOUNT iot:sensor:1:readings 1793491200 1793493900
docker compose exec -T redis redis-cli ZRANGEBYSCORE iot:sensor:1:readings 1793491200 1793493900
```

O primeiro retorna **10** leituras do sensor 1. O segundo retorna os IDs `1, 1001, 2001, ..., 9001`. O índice deste sensor é apenas uma das mil partes do recorte.

### 5.3. Executar a agregação das 10.000 nos dois bancos e comparar

```bash
curl --fail-with-body -sS 'http://localhost:8000/api/compare?operation=summary&start=1793491200&end=1793493900' | python3 -m json.tool
```

Em **cada** entrada de `results`, confira:

```json
{
  "count": 10000,
  "sensors": 1000,
  "temperature_sum": 29932800,
  "humidity_sum": 54385000,
  "alerts": 3522,
  "minimum": 2300,
  "maximum": 3699
}
```

O resultado final deve ter **`equivalent: true`**. A média em graus é `temperature_sum / count / 100`. `elapsed_ms` muda a cada execução; uma amostra não substitui o benchmark.

### 5.4. Ler todos os cinco campos dos 10.000 registros e conferir um por um

O bloco inteiro abaixo roda Python dentro do contêiner. Ele usa `SELECT` no PostgreSQL e `HGETALL` em lotes no Redis; não lê o CSV e não grava nos bancos. Não imprime dez mil linhas no terminal: mostra a contagem e confirma a igualdade de **todos os campos**.

```bash
docker compose exec -T app python - <<'PY'
import json
from app.store import pg_connect, redis_connect, normalized

with pg_connect() as pg, redis_connect() as rd:
    postgres = pg.execute(
        "SELECT * FROM readings WHERE id BETWEEN %s AND %s ORDER BY id",
        (1, 10000),
    ).fetchall()
    redis_rows = []
    for inicio in range(1, 10001, 1000):
        with rd.pipeline(transaction=False) as lote:
            for identificador in range(inicio, inicio + 1000):
                lote.hgetall(f"iot:reading:{identificador}")
            redis_rows.extend(normalized(row) for row in lote.execute())

assert len(postgres) == 10000, "Quantidade PostgreSQL diferente de 10000"
assert all(row is not None for row in redis_rows), "Faltam leituras Redis"
assert postgres == redis_rows, "Os campos das leituras divergem"
print(json.dumps({
    "leituras_postgres": len(postgres),
    "leituras_redis": sum(row is not None for row in redis_rows),
    "todos_os_campos_iguais": postgres == redis_rows,
    "primeiro_id": postgres[0]["id"],
    "ultimo_id": postgres[-1]["id"],
}, indent=2))
PY
```

Esperado: duas contagens `10000`, `todos_os_campos_iguais: true`, primeiro ID `1`, último ID `10000`.

## 6. Consultar histórico e o milhão completo

Histórico do sensor 1 entre 00:05 e 00:10 UTC, inclusive:

```bash
curl --fail-with-body -sS 'http://localhost:8000/api/compare?operation=history&sensor_id=1&start=1793491500&end=1793491800&limit=10' | python3 -m json.tool
```

Esperado: IDs **1001 e 2001**, iguais nas duas fontes. Na API, o histórico aceita no máximo `limit=1000` por requisição. Para as 10.000 leituras de vários sensores, use a agregação ou a leitura em lotes da seção 5.

Resumo de **todas as 1.000.000 de leituras**:

```bash
curl --fail-with-body -sS 'http://localhost:8000/api/compare?operation=summary&start=1793491200&end=1793790900' | python3 -m json.tool
```

Esperado: `count: 1000000`, `sensors: 1000`, `alerts: 356430` nas duas fontes e `equivalent: true`. Esta operação processa muito mais leituras que uma busca por ID e pode levar alguns segundos.

## 7. Criar, ler, atualizar e excluir manualmente

Os comandos abaixo fazem CRUD em **um registro temporário adicional**, em cada banco. Os 10.000 da seção 5 são registros originais usados nas consultas; não serão atualizados nem excluídos. Execute os quatro passos em ordem. A API recebe uma fonte por chamada e não sincroniza os bancos automaticamente; os laços aplicam explicitamente a operação nas duas fontes.

### 7.1. CREATE — criar com temperatura de 28,50 °C

```bash
for fonte in postgres redis; do
  curl --fail-with-body -sS -X POST "http://localhost:8000/api/readings?source=$fonte" \
    -H 'Content-Type: application/json' \
    -d '{"id":9000000003,"sensor_id":1,"ts":1794000000,"temperature_centi":2850,"humidity_centi":6100}' | python3 -m json.tool
done
```

### 7.2. READ — ler e comparar o que acabou de criar

```bash
curl --fail-with-body -sS 'http://localhost:8000/api/compare?operation=point&reading_id=9000000003' | python3 -m json.tool
```

### 7.3. UPDATE — mudar a temperatura para 33,50 °C

```bash
for fonte in postgres redis; do
  curl --fail-with-body -sS -X PUT "http://localhost:8000/api/readings/9000000003?source=$fonte" \
    -H 'Content-Type: application/json' \
    -d '{"id":9000000003,"sensor_id":1,"ts":1794000000,"temperature_centi":3350,"humidity_centi":6100}' | python3 -m json.tool
done
```

Repita o READ do passo anterior: deve mostrar `temperature_centi: 3350` e `equivalent: true`.

### 7.4. DELETE — remover apenas o registro temporário

```bash
for fonte in postgres redis; do
  curl --fail-with-body -sS -X DELETE "http://localhost:8000/api/readings/9000000003?source=$fonte" | python3 -m json.tool
done
```

Repita o READ: ambas as respostas `data` devem ser `null`. Refaça as contagens da seção 2: devem voltar a **1.000.000** em cada banco. Se repetir CREATE antes de DELETE, o retorno esperado é conflito HTTP **409**, pois o ID já existe.

Para executar automaticamente um ciclo completo, com verificações e limpeza ao final:

```bash
docker compose exec -T app python -m scripts.crud_demo
```

Esse programa usa outro ID reservado, mostra `passed: true` para ambas as fontes e grava `results/crud.json`.

## 8. Executar os três exemplos curtos Redis

CRUD com hash — criar, ler, mudar 28,50 para 33,00 °C e excluir:

```bash
docker compose exec -T app python exemplos/redis/01_crud_hash.py
```

Histórico com sorted set — retornar IDs `2` e `3` do exemplo didático:

```bash
docker compose exec -T app python exemplos/redis/02_historico_sensor.py
```

Cache com TTL — gravar JSON com validade de dois segundos e confirmar expiração:

```bash
docker compose exec -T app python exemplos/redis/03_cache_ttl.py
```

Esses três programas criam dados pequenos em chaves `demo:` exclusivas e fazem a limpeza. Eles demonstram conceitos; as consultas da seção 5 usam as 10.000 leituras reais da massa sintética carregada em `iot:*`.

## 9. Rodar os testes automáticos e verificar a massa inteira

Testes da aplicação — esperado **11 testes, OK**:

```bash
docker compose exec -T app python -m unittest discover -s tests -v
```

Testes dos exemplos — esperado **3 testes, OK**:

```bash
docker compose exec -T app python -m unittest discover -s exemplos/redis -p 'test_*.py' -v
```

Verificação integral — percorre o milhão e confere campos, índices e hash canônico:

```bash
docker compose exec -T app python -m scripts.verify
```

Esta última é mais demorada que uma contagem. Atualiza `results/verification.json`. Os testes e o CRUD devem terminar antes de executá-la.

## 10. Entender a velocidade e repetir o benchmark

Ver o plano da consulta pontual PostgreSQL, incluindo execução real:

```bash
docker compose exec -T postgres psql -U iot -d iot -c "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM readings WHERE id = 500001;"
```

O plano pode usar `readings_pkey`: a busca por ID usa um índice. Ela não precisa devolver nem percorrer linearmente o milhão de registros.

Consultar o benchmark **já salvo**, sem executar novas medições:

```bash
curl --fail-with-body -sS http://localhost:8000/api/benchmark | python3 -m json.tool
```

Opcional — executar **novas medições**, com 30 repetições e cinco aquecimentos por consulta/fonte:

```bash
docker compose exec -T app python -m scripts.benchmark --repetitions 30 --warmup 5
```

O benchmark atualiza os arquivos de medições e planos em `results/`, pode levar alguns minutos e deve rodar sem outros testes concorrentes. Relatórios e slides com números antigos precisam ser atualizados se você trocar as medições apresentadas.

## 11. Encerrar preservando os dados

```bash
docker compose stop
```

Para retomar, use o comando da seção 1. Os volumes preservam PostgreSQL e Redis. Durante a demonstração, use as operações temporárias da seção 7 para manter a massa original e as comparações consistentes.

## Ordem curta para apresentar

1. Iniciar e mostrar `docker compose ps`.
2. Contar o milhão nos dois bancos (seção 2).
3. Consultar o ID `500001` (seção 4).
4. Comparar a agregação das **10.000** (seção 5.3).
5. Confirmar os cinco campos das **10.000** (seção 5.4).
6. Fazer o CRUD temporário (seção 7).
7. Mostrar os 11 + 3 testes (seção 9).
8. Se houver tempo, consultar o resumo do milhão e o plano PostgreSQL.
