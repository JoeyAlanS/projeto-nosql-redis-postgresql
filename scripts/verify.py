"""Compara 100% das leituras e índices Redis com o CSV canônico e PostgreSQL."""
import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime, timezone

from app.store import ROOT, PostgresStore, RedisStore, canonical, pg_connect, redis_connect


def main():
    load = json.loads((ROOT / "results/load.json").read_text())
    t = time.perf_counter()
    digests = {name: hashlib.sha256() for name in ("csv", "postgres", "redis")}
    expected_indexes = defaultdict(dict)
    checked = 0
    with pg_connect() as pg, redis_connect() as rd:
        assert PostgresStore(pg).sensors() == RedisStore(rd).sensors(), "Metadados de sensores divergem"
        count_pg = pg.execute("SELECT count(*) AS n FROM readings").fetchone()["n"]
        count_rd = sum(1 for _ in rd.scan_iter("iot:reading:*", count=10000))
        assert count_pg == count_rd == load["records"], "Contagens divergem"
        with pg.cursor(name="full_verification") as cursor, (ROOT / "data/readings.csv").open() as csv:
            cursor.execute("SELECT * FROM readings ORDER BY id")
            while batch := cursor.fetchmany(5000):
                with rd.pipeline(transaction=False) as pipe:
                    for row in batch:
                        pipe.hgetall(f"iot:reading:{row['id']}")
                    redis_rows = pipe.execute()
                for row, rr in zip(batch, redis_rows):
                    actual_pg = canonical(row)
                    actual_rd = canonical(rr)
                    original = csv.readline()
                    assert actual_pg == actual_rd == original, f"Divergência na leitura {row['id']}"
                    for name, value in (("csv", original), ("postgres", actual_pg), ("redis", actual_rd)):
                        digests[name].update(value.encode())
                    expected_indexes[row["sensor_id"]][str(row["id"])] = row["ts"]
                    checked += 1
                if checked % 200000 == 0:
                    print(f"Verificação integral: {checked:,} leituras", flush=True)
            assert not csv.readline(), "CSV contém registros extras"
        for sid, mapping in expected_indexes.items():
            indexed = {rid: int(ts) for rid, ts in rd.zrange(f"iot:sensor:{sid}:readings", 0, -1, withscores=True)}
            unique = rd.hgetall(f"iot:unique:{sid}")
            assert indexed == mapping, f"Índice temporal divergente, sensor {sid}"
            assert unique == {str(ts): rid for rid, ts in mapping.items()}, f"Unicidade divergente, sensor {sid}"
        hashes = {k: v.hexdigest() for k, v in digests.items()}
        assert len(set(hashes.values())) == 1 and hashes["csv"] == load["csv_sha256"]
        report = {"verified_at": datetime.now(timezone.utc).isoformat(), "checked_readings": checked,
                  "postgres_count": count_pg, "redis_count": count_rd, "sha256": hashes,
                  "sensors_verified": len(expected_indexes), "all_temporal_and_unique_indexes_verified": True,
                  "redis_evicted_keys": rd.info()["evicted_keys"],
                  "seconds": time.perf_counter()-t, "equivalent": True}
        (ROOT / "results/verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
