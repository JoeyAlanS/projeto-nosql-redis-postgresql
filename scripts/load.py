"""Geração determinística e carga independente do mesmo CSV nos dois bancos."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone

from app.store import FIELDS, LOCATIONS, ROOT, canonical, pg_connect, redis_connect

START = 1_793_491_200  # 2026-11-01 00:00:00 UTC


def generate_row(i, sensors, seed):
    sid = (i - 1) % sensors + 1
    step = (i - 1) // sensors
    return dict(id=i, sensor_id=sid, ts=START + step * 300,
                temperature_centi=2300 + (sid * 17 + step * 7 + seed) % 1400,
                humidity_centi=3000 + (sid * 31 + step * 13 + seed) % 5000)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, default=1_000_000)
    parser.add_argument("--sensors", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--replace", action="store_true", help="Substitui apenas a massa do projeto")
    args = parser.parse_args()
    if args.records < 1 or not 1 <= args.sensors <= args.records:
        parser.error("Quantidades devem ser positivas e sensores <= registros")
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "results").mkdir(exist_ok=True)
    csv_path = ROOT / "data/readings.csv"
    with pg_connect() as pg, redis_connect() as rd:
        pg.execute((ROOT / "sql/schema.sql").read_text())
        pg.commit()
        existing = pg.execute("SELECT count(*) AS n FROM readings").fetchone()["n"]
        if (existing or rd.exists("iot:loaded") or rd.scard("iot:sensors")) and not args.replace:
            raise SystemExit("Massa já existe. Para substituir conscientemente use --replace.")
        if args.replace:
            pg.execute("TRUNCATE readings,sensors")
            pg.commit()
            keys = []
            for key in rd.scan_iter("iot:*"):
                keys.append(key)
                if len(keys) == 2000:
                    rd.unlink(*keys)
                    keys.clear()
            if keys:
                rd.unlink(*keys)
        # Invalida resultados antigos para evitar associação a outra carga.
        for name in ("benchmark.json", "benchmark_raw.csv", "verification.json", "load.json", "plans.json"):
            (ROOT / "results" / name).unlink(missing_ok=True)
        rd.set("iot:load_state", "loading")
        report = {"generated_at": datetime.now(timezone.utc).isoformat(), "records": args.records,
                  "sensors": args.sensors, "seed": args.seed, "logical_record": "Uma medição de um sensor em um instante",
                  "fields": list(FIELDS), "start": START,
                  "end": generate_row(args.records, args.sensors, args.seed)["ts"],
                  "interval_seconds": 300, "alert_rule": "temperature_centi > 3200"}
        t = time.perf_counter()
        digest = hashlib.sha256()
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            for i in range(1, args.records + 1):
                line = canonical(generate_row(i, args.sensors, args.seed))
                digest.update(line.encode())
                f.write(line)
        report.update(csv_sha256=digest.hexdigest(), csv_bytes=csv_path.stat().st_size,
                      generation_seconds=time.perf_counter() - t)
        sensors = [dict(id=sid, name=f"Sensor {sid:04}", location=LOCATIONS[(sid-1) % len(LOCATIONS)], active=True)
                   for sid in range(1, args.sensors + 1)]
        t = time.perf_counter()
        with pg.cursor().copy("COPY sensors (id,name,location,active) FROM STDIN") as copy:
            for s in sensors:
                copy.write_row(tuple(s.values()))
        with pg.cursor().copy("COPY readings (id,sensor_id,ts,temperature_centi,humidity_centi) FROM STDIN WITH (FORMAT CSV)") as copy:
            with csv_path.open("rb") as f:
                while chunk := f.read(1024 * 1024):
                    copy.write(chunk)
        pg.commit()
        # VACUUM prepara visibilidade para index-only scan. Fora de transação.
        pg.autocommit = True
        pg.execute("VACUUM (ANALYZE) readings")
        pg.execute("ANALYZE sensors")
        report["postgres_load_seconds"] = time.perf_counter() - t
        print(f"PostgreSQL: {args.records:,} leituras em {report['postgres_load_seconds']:.2f}s", flush=True)
        t = time.perf_counter()
        with rd.pipeline(transaction=False) as pipe:
            for s in sensors:
                pipe.hset(f"iot:sensor:{s['id']}", mapping={**s, "active": "1"})
                pipe.sadd("iot:sensors", s["id"])
            pipe.execute()
            with csv_path.open() as f:
                for i, line in enumerate(f, 1):
                    row = dict(zip(FIELDS, map(int, line.strip().split(","))))
                    pipe.hset(f"iot:reading:{row['id']}", mapping=row)
                    pipe.zadd(f"iot:sensor:{row['sensor_id']}:readings", {row["id"]: row["ts"]})
                    pipe.hset(f"iot:unique:{row['sensor_id']}", row["ts"], row["id"])
                    if i % 2000 == 0:
                        pipe.execute()
                    if i % 200000 == 0:
                        print(f"Redis: {i:,}/{args.records:,}", flush=True)
                pipe.execute()
        # Aguarda fsync periódico sem alterar a configuração de durabilidade.
        time.sleep(1.1)
        report["redis_load_seconds"] = time.perf_counter() - t
        report["postgres_bytes"] = pg.execute(
            "SELECT sum(pg_total_relation_size(x)) AS n FROM unnest(ARRAY['sensors','readings']) AS x"
        ).fetchone()["n"]
        report["postgres_bytes"] = int(report["postgres_bytes"])
        report["postgres_version"] = pg.execute("SHOW server_version").fetchone()["server_version"]
        info = rd.info()
        report.update(redis_version=info["redis_version"], redis_used_memory_bytes=info["used_memory"],
                      redis_dataset_bytes=info["used_memory_dataset"], redis_aof_bytes=info["aof_current_size"],
                      redis_maxmemory_policy=rd.config_get("maxmemory-policy")["maxmemory-policy"],
                      redis_appendfsync=rd.config_get("appendfsync")["appendfsync"],
                      redis_evicted_keys=info["evicted_keys"])
        publish_report(rd, report)
        print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)


def publish_report(rd, report):
    """Publica o manifesto completo; complete só é visível após os metadados.

    O arquivo é substituído atomicamente e as duas chaves são publicadas em
    uma transação Redis. Isso não constitui uma transação entre disco e Redis:
    falhas de publicação não são ocultadas e exigem conferência do estado.
    As medidas de espaço descrevem o instante anterior à publicação final.
    """
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    manifest = ROOT / "results/load.json"
    temporary = manifest.with_suffix(".json.tmp")
    temporary.write_text(payload)
    temporary.replace(manifest)
    with rd.pipeline(transaction=True) as pipe:
        pipe.set("iot:loaded", payload)
        pipe.set("iot:load_state", "complete")
        pipe.execute()


if __name__ == "__main__":
    main()
