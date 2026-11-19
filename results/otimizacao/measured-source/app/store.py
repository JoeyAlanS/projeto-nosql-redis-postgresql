"""Mesmo contrato lógico, representações físicas próprias para cada SGBD."""
import json
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
import redis
from psycopg.rows import dict_row
from app import redis_optimized as opt

FIELDS = ("id", "sensor_id", "ts", "temperature_centi", "humidity_centi")
MAX_READING_ID = 9_000_000_000_000_000
MAX_SENSOR_ID = 2_147_483_647
MAX_TIMESTAMP = 253_402_300_799  # 9999-12-31 23:59:59 UTC; exato em sorted sets.
BOUNDS = {"id": (1, MAX_READING_ID), "sensor_id": (1, MAX_SENSOR_ID),
          "ts": (1, MAX_TIMESTAMP), "temperature_centi": (-5000, 10000),
          "humidity_centi": (0, 10000)}
LOCATIONS = ["Laboratório", "Biblioteca", "Auditório", "Bloco A", "Bloco B",
             "Bloco C", "Refeitório", "Estufa", "Almoxarifado", "Oficina"]
ROOT = Path(__file__).resolve().parents[1]


def pg_connect():
    return psycopg.connect(os.getenv("DATABASE_URL", "postgresql://iot:iot_local_academico@localhost:55432/iot"), row_factory=dict_row)


def redis_connect():
    return redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:56379/0"), decode_responses=True)


def normalized(row):
    return {k: int(row[k]) for k in FIELDS} if row else None


def canonical(row):
    return ",".join(str(int(row[k])) for k in FIELDS) + "\n"


class Conflict(ValueError):
    pass


class Missing(ValueError):
    pass


class Invalid(ValueError):
    pass


class Busy(ValueError):
    pass


def validate_reading(row):
    for field, (minimum, maximum) in BOUNDS.items():
        value = row.get(field)
        if type(value) is not int or not minimum <= value <= maximum:
            raise Invalid(f"{field} deve ser inteiro entre {minimum} e {maximum}")


class PostgresStore:
    def __init__(self, connection):
        self.conn = connection

    def sensors(self, location=None):
        return self.conn.execute(
            "SELECT * FROM sensors WHERE (%s::text IS NULL OR location=%s) ORDER BY id", (location, location)
        ).fetchall()

    def point(self, reading_id):
        return self.conn.execute("SELECT * FROM readings WHERE id=%s", (reading_id,)).fetchone()

    def history(self, sensor_id, start, end, limit=200):
        # Limites inclusivos, ordem crescente e mesmo LIMIT nos dois SGBDs.
        return self.conn.execute(
            "SELECT * FROM readings WHERE sensor_id=%s AND ts BETWEEN %s AND %s ORDER BY ts,id LIMIT %s",
            (sensor_id, start, end, limit),
        ).fetchall()

    def summary(self, sensor_ids, start, end):
        row = self.conn.execute(
            """SELECT count(*) AS count, count(DISTINCT sensor_id) AS sensors,
               COALESCE(sum(temperature_centi),0) AS temperature_sum,
               COALESCE(sum(humidity_centi),0) AS humidity_sum,
               count(*) FILTER (WHERE temperature_centi > 3200) AS alerts,
               min(temperature_centi) AS minimum, max(temperature_centi) AS maximum
               FROM readings WHERE sensor_id=ANY(%s) AND ts BETWEEN %s AND %s""",
            (sensor_ids, start, end),
        ).fetchone()
        return {k: int(v) if v is not None else None for k, v in row.items()}

    def create(self, row):
        validate_reading(row)
        try:
            self.conn.execute(
                "INSERT INTO readings (id,sensor_id,ts,temperature_centi,humidity_centi) VALUES (%s,%s,%s,%s,%s)",
                tuple(row[k] for k in FIELDS),
            )
        except psycopg.errors.UniqueViolation as e:
            raise Conflict("ID ou par sensor/instante já existe") from e
        except psycopg.errors.ForeignKeyViolation as e:
            raise Invalid("Sensor não existe") from e
        return row

    def update(self, reading_id, row):
        validate_reading(dict(row, id=reading_id))
        try:
            result = self.conn.execute(
                "UPDATE readings SET sensor_id=%s,ts=%s,temperature_centi=%s,humidity_centi=%s WHERE id=%s RETURNING *",
                (row["sensor_id"], row["ts"], row["temperature_centi"], row["humidity_centi"], reading_id),
            ).fetchone()
        except psycopg.errors.UniqueViolation as e:
            raise Conflict("Par sensor/instante já existe") from e
        except psycopg.errors.ForeignKeyViolation as e:
            raise Invalid("Sensor não existe") from e
        if result is None:
            raise Missing("Leitura não encontrada")
        return result

    def delete(self, reading_id):
        row = self.conn.execute("DELETE FROM readings WHERE id=%s RETURNING *", (reading_id,)).fetchone()
        if row is None:
            raise Missing("Leitura não encontrada")
        return row


HISTORY_LUA = """
local ids = redis.call('ZRANGEBYSCORE', KEYS[1], ARGV[1], ARGV[2], 'LIMIT', 0, ARGV[3])
local rows = {}
for _, id in ipairs(ids) do
  local r = redis.call('HMGET', 'iot:reading:' .. id, 'id','sensor_id','ts','temperature_centi','humidity_centi')
  rows[#rows+1] = r
end
return rows
"""

SUMMARY_LUA = """
local count, sensors, tsum, hsum, alerts, minv, maxv = 0,0,0,0,0,nil,nil
for _, key in ipairs(KEYS) do
  local ids = redis.call('ZRANGEBYSCORE', key, ARGV[1], ARGV[2])
  if #ids > 0 then sensors = sensors + 1 end
  for _, id in ipairs(ids) do
    local v = redis.call('HMGET','iot:reading:'..id,'temperature_centi','humidity_centi')
    local t, h = tonumber(v[1]), tonumber(v[2])
    count = count + 1
    tsum = tsum + t
    hsum = hsum + h
    if t > 3200 then alerts = alerts + 1 end
    if minv == nil or t < minv then minv = t end
    if maxv == nil or t > maxv then maxv = t end
  end
end
return {count,sensors,tsum,hsum,alerts,minv or false,maxv or false}
"""

# Uma execução Lua mantém hash, índice temporal e unicidade no mesmo passo.
# Projeto standalone: as chaves NÃO partilham hash slot para uso em Cluster.
WRITE_LUA = opt.WRITE_HELPERS + """
local op, id = ARGV[1], ARGV[2]
local key = 'iot:reading:'..id
local exists = redis.call('EXISTS', key) == 1
if op == 'create' and exists then return 'CONFLICT' end
if op ~= 'create' and not exists then return 'MISSING' end
if op ~= 'delete' then
  if redis.call('EXISTS','iot:sensor:'..ARGV[3]) == 0 then return 'INVALID' end
  local owner = redis.call('HGET','iot:unique:'..ARGV[3],ARGV[4])
  if owner and owner ~= id then return 'CONFLICT' end
end
if exists then
  local old = redis.call('HMGET',key,'id','sensor_id','ts','temperature_centi','humidity_centi')
  opt_change(old,-1)
  redis.call('ZREM','iot:sensor:'..old[2]..':readings',id)
  redis.call('HDEL','iot:unique:'..old[2],old[3])
end
if op == 'delete' then
  local deleted = redis.call('HMGET',key,'id','sensor_id','ts','temperature_centi','humidity_centi')
  redis.call('DEL', key)
  return deleted
end
redis.call('HSET',key,'id',id,'sensor_id',ARGV[3],'ts',ARGV[4],
           'temperature_centi',ARGV[5],'humidity_centi',ARGV[6])
redis.call('ZADD','iot:sensor:'..ARGV[3]..':readings',ARGV[4],id)
redis.call('HSET','iot:unique:'..ARGV[3],ARGV[4],id)
opt_change({id,ARGV[3],ARGV[4],ARGV[5],ARGV[6]},1)
return 'OK'
"""


class RedisStore:
    def __init__(self, connection, optimized=None):
        self.conn = connection
        ready = connection.get(opt.STATE) == 'ready'
        if optimized is True and not ready:
            raise Busy('Execute make otimizar-redis antes de selecionar a variante otimizada')
        self.optimized = ready if optimized is None else optimized
        self._history = connection.register_script(HISTORY_LUA)
        self._summary = connection.register_script(SUMMARY_LUA)
        self._optimized_summary = connection.register_script(opt.SUMMARY_LUA)
        self._write = connection.register_script(WRITE_LUA)

    def sensors(self, location=None):
        ids = sorted(map(int, self.conn.smembers("iot:sensors")))
        with self.conn.pipeline(transaction=False) as p:
            for sid in ids:
                p.hgetall(f"iot:sensor:{sid}")
            rows = p.execute()
        return [dict(id=int(r["id"]), name=r["name"], location=r["location"], active=r["active"] == "1")
                for r in rows if location is None or r["location"] == location]

    def point(self, reading_id):
        return normalized(self.conn.hgetall(f"iot:reading:{reading_id}"))

    def history(self, sensor_id, start, end, limit=200):
        if self.optimized:
            rows = self.conn.execute_command('ZRANGE', f'{opt.PREFIX}:sensor:{sensor_id}:full',
                                             start, end, 'BYSCORE', 'LIMIT', 0, limit)
            return [opt.unpack(row) for row in rows]
        rows = self._history(keys=[f"iot:sensor:{sensor_id}:readings"], args=[start, end, limit])
        return [dict(zip(FIELDS, map(int, row))) for row in rows]

    def summary(self, sensor_ids, start, end):
        if self.optimized:
            values = self._optimized_summary(keys=[f'{opt.PREFIX}:sensor:{sid}' for sid in sorted(set(sensor_ids))],
                                             args=[start, end])
            return dict(zip(opt.SUMMARY_FIELDS, [int(v) if v is not None else None for v in values]))
        values = self._summary(keys=[f"iot:sensor:{sid}:readings" for sid in sensor_ids], args=[start, end])
        keys = ("count", "sensors", "temperature_sum", "humidity_sum", "alerts", "minimum", "maximum")
        return dict(zip(keys, [int(v) if v is not None else None for v in values]))

    def write(self, op, row):
        validate_reading(row)
        result = self._write(args=[op] + [row[k] for k in FIELDS])
        if result == 'BUSY':
            raise Busy('Construção dos índices Redis em andamento; escrita temporariamente bloqueada')
        errors = {"CONFLICT": Conflict("ID ou par sensor/instante já existe"),
                  "MISSING": Missing("Leitura não encontrada"), "INVALID": Invalid("Sensor não existe")}
        if result in errors:
            raise errors[result]
        return row

    def create(self, row):
        return self.write("create", row)

    def update(self, reading_id, row):
        return self.write("update", dict(row, id=reading_id))

    def delete(self, reading_id):
        # Retorna a versão efetivamente excluída, na mesma execução atômica.
        result = self._write(args=["delete", reading_id])
        if result == 'BUSY':
            raise Busy('Construção dos índices Redis em andamento; escrita temporariamente bloqueada')
        if result == "MISSING":
            raise Missing("Leitura não encontrada")
        return dict(zip(FIELDS, map(int, result)))


@contextmanager
def store(source, redis_mode='auto'):
    if source == "postgres":
        with pg_connect() as c:
            yield PostgresStore(c)
    elif source == "redis":
        with redis_connect() as c:
            yield RedisStore(c, optimized={'auto': None, 'baseline': False, 'optimized': True}[redis_mode])
    else:
        raise Invalid("Fonte deve ser postgres ou redis")
