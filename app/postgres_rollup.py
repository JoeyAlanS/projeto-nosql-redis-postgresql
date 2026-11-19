"""Controle experimental: view materializada, atualizada antes do benchmark.

Não é usada na API/CRUD: exige REFRESH após qualquer alteração nas leituras.
Compara custo de leitura pré-agregada, não a manutenção incremental do Redis.
"""
from app.store import PostgresStore

CREATE = '''CREATE MATERIALIZED VIEW IF NOT EXISTS readings_daily_experiment AS
SELECT sensor_id, (ts/86400)*86400 AS day, count(*) AS count,
sum(temperature_centi)::bigint AS temperature_sum, sum(humidity_centi)::bigint AS humidity_sum,
count(*) FILTER (WHERE temperature_centi > 3200) AS alerts,
min(temperature_centi) AS minimum, max(temperature_centi) AS maximum,
min(ts) AS first_ts, max(ts) AS last_ts
FROM readings GROUP BY sensor_id, (ts/86400)*86400 WITH NO DATA'''

SUMMARY = '''WITH selected AS MATERIALIZED (
 SELECT * FROM readings_daily_experiment
 WHERE sensor_id=ANY(%s) AND day BETWEEN (%s::bigint/86400)*86400 AND (%s::bigint/86400)*86400
), parts AS (
 SELECT sensor_id,count,temperature_sum,humidity_sum,alerts,minimum,maximum FROM selected
 WHERE first_ts >= %s AND last_ts <= %s
 UNION ALL
 SELECT r.sensor_id, count(*), sum(r.temperature_centi), sum(r.humidity_centi),
 count(*) FILTER (WHERE r.temperature_centi > 3200), min(r.temperature_centi), max(r.temperature_centi)
 FROM selected b JOIN readings r ON r.sensor_id=b.sensor_id
 AND r.ts BETWEEN greatest(b.day,%s) AND least(b.day+86399,%s)
 WHERE b.first_ts < %s OR b.last_ts > %s GROUP BY r.sensor_id
)
SELECT COALESCE(sum(count),0) AS count, count(DISTINCT sensor_id) AS sensors,
COALESCE(sum(temperature_sum),0) AS temperature_sum, COALESCE(sum(humidity_sum),0) AS humidity_sum,
COALESCE(sum(alerts),0) AS alerts, min(minimum) AS minimum, max(maximum) AS maximum FROM parts'''


def prepare(connection):
    connection.execute(CREATE)
    connection.execute('CREATE UNIQUE INDEX IF NOT EXISTS readings_daily_experiment_pk ON readings_daily_experiment(sensor_id,day)')
    connection.execute('REFRESH MATERIALIZED VIEW readings_daily_experiment')
    connection.execute('ANALYZE readings_daily_experiment')


class PostgresRollupStore(PostgresStore):
    def summary(self, sensor_ids, start, end):
        row = self.conn.execute(SUMMARY, (sensor_ids, start, end, start, end, start, end, start, end)).fetchone()
        return {k: int(v) if v is not None else None for k,v in row.items()}
