CREATE TABLE IF NOT EXISTS live_metadata(singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton), ready boolean NOT NULL);
CREATE TABLE IF NOT EXISTS live_states (
 sensor_id integer PRIMARY KEY REFERENCES sensors(id), ts bigint NOT NULL,
 temperature_centi integer NOT NULL, humidity_centi integer NOT NULL, location text NOT NULL
);
CREATE INDEX IF NOT EXISTS live_temperature_idx ON live_states(temperature_centi DESC,sensor_id DESC);
CREATE INDEX IF NOT EXISTS live_location_temperature_idx ON live_states(location,temperature_centi DESC,sensor_id DESC);
CREATE TABLE IF NOT EXISTS live_summaries (
 scope text PRIMARY KEY,count bigint NOT NULL,temperature_sum bigint NOT NULL,
 humidity_sum bigint NOT NULL,alerts bigint NOT NULL,minimum integer,maximum integer
);
CREATE OR REPLACE FUNCTION live_write(sid integer, stamp bigint, temp integer, hum integer, remove boolean)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
 old live_states%ROWTYPE;
 loc text; grp text; low integer; high integer; previous integer; incoming integer;
BEGIN
 -- O resumo global é compartilhado: serializa a manutenção na transação.
 PERFORM pg_advisory_xact_lock(761193);
 IF NOT COALESCE((SELECT ready FROM live_metadata WHERE singleton=true),false) THEN RETURN 'BUSY'; END IF;
 IF sid<=0 OR stamp<1 OR stamp>253402300799 OR temp NOT BETWEEN -5000 AND 10000 OR hum NOT BETWEEN 0 AND 10000 THEN RETURN 'INVALID'; END IF;
 SELECT location INTO loc FROM sensors WHERE id=sid;
 IF NOT FOUND THEN RETURN 'INVALID'; END IF;
 SELECT * INTO old FROM live_states WHERE sensor_id=sid;
 previous=CASE WHEN FOUND THEN 1 ELSE 0 END;
 IF previous=1 AND old.location<>loc THEN RETURN 'INVALID'; END IF;
 incoming=CASE WHEN remove THEN 0 ELSE 1 END;
 IF remove THEN DELETE FROM live_states WHERE sensor_id=sid;
 ELSE
  INSERT INTO live_states VALUES(sid,stamp,temp,hum,loc)
  ON CONFLICT(sensor_id) DO UPDATE SET ts=EXCLUDED.ts,temperature_centi=EXCLUDED.temperature_centi,humidity_centi=EXCLUDED.humidity_centi;
 END IF;
 -- Exatamente dois escopos; não percorre sensores ou leituras históricas.
 FOREACH grp IN ARRAY ARRAY['all','location:'||loc] LOOP
  IF grp='all' THEN
   SELECT temperature_centi INTO low FROM live_states ORDER BY temperature_centi,sensor_id LIMIT 1;
   SELECT temperature_centi INTO high FROM live_states ORDER BY temperature_centi DESC,sensor_id DESC LIMIT 1;
  ELSE
   SELECT temperature_centi INTO low FROM live_states WHERE location=loc ORDER BY temperature_centi,sensor_id LIMIT 1;
   SELECT temperature_centi INTO high FROM live_states WHERE location=loc ORDER BY temperature_centi DESC,sensor_id DESC LIMIT 1;
  END IF;
  INSERT INTO live_summaries VALUES(grp,incoming-previous,incoming*temp-COALESCE(old.temperature_centi,0),
    incoming*hum-COALESCE(old.humidity_centi,0),incoming*(temp>3200)::integer-COALESCE((old.temperature_centi>3200)::integer,0),low,high)
  ON CONFLICT(scope) DO UPDATE SET
    count=live_summaries.count+EXCLUDED.count,
    temperature_sum=live_summaries.temperature_sum+EXCLUDED.temperature_sum,
    humidity_sum=live_summaries.humidity_sum+EXCLUDED.humidity_sum,
    alerts=live_summaries.alerts+EXCLUDED.alerts,minimum=EXCLUDED.minimum,maximum=EXCLUDED.maximum;
 END LOOP;
 RETURN 'OK';
END $$;
