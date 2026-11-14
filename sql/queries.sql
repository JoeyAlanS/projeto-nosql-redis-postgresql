-- Parâmetros exemplificativos. As execuções reais usam bind parameters do psycopg.
-- Q1: readings_pkey. Os cinco campos precisam ser retornados.
SELECT * FROM readings WHERE id = 500001;

-- Q2: mesmas datas e limite usados pelo Redis. Limites inclusivos.
SELECT * FROM readings
WHERE sensor_id = 501 AND ts BETWEEN 1793491200 AND 1793790900
ORDER BY ts, id LIMIT 200;

-- Q3: o filtro real usa sensor_id=ANY(array), definido no benchmark.json.
SELECT count(*) AS count, count(DISTINCT sensor_id) AS sensors,
       COALESCE(sum(temperature_centi),0) AS temperature_sum,
       COALESCE(sum(humidity_centi),0) AS humidity_sum,
       count(*) FILTER (WHERE temperature_centi > 3200) AS alerts,
       min(temperature_centi) AS minimum, max(temperature_centi) AS maximum
FROM readings WHERE sensor_id BETWEEN 1 AND 1000
AND ts BETWEEN 1793491200 AND 1793790900;

-- Rode EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) antes de cada SELECT
-- para inspecionar planos, sem misturar esse custo às amostras de latência.
