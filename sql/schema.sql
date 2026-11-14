-- Recriável somente pelo carregador, após autorização explícita --replace.
CREATE TABLE IF NOT EXISTS sensors (
  id integer PRIMARY KEY CHECK (id > 0),
  name text NOT NULL,
  location text NOT NULL,
  active boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS sensors_location_idx ON sensors (location, id);
CREATE TABLE IF NOT EXISTS readings (
  id bigint PRIMARY KEY CHECK (id > 0),
  sensor_id integer NOT NULL REFERENCES sensors(id),
  ts bigint NOT NULL CHECK (ts > 0),
  temperature_centi integer NOT NULL CHECK (temperature_centi BETWEEN -5000 AND 10000),
  humidity_centi integer NOT NULL CHECK (humidity_centi BETWEEN 0 AND 10000),
  UNIQUE (sensor_id, ts)
);
-- Índice que cobre a busca por sensor/período, evita prejudicar o relacional.
CREATE INDEX IF NOT EXISTS readings_sensor_ts_idx ON readings (sensor_id, ts DESC, id DESC)
  INCLUDE (temperature_centi, humidity_centi);
CREATE INDEX IF NOT EXISTS readings_ts_idx ON readings (ts);
