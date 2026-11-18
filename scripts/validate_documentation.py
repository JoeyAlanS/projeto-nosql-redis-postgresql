"""Captura evidências reais para confrontar documento, esquema e consultas.

Execute sem escritas concorrentes, depois de scripts.verify. Não recarrega a
massa nem repete o benchmark. Os tempos de desempenho históricos são preservados.
"""
import hashlib
import json
from datetime import datetime, timezone

from app.store import ROOT, PostgresStore, RedisStore, pg_connect, redis_connect


def main():
    load = json.loads((ROOT / "results/load.json").read_text())
    verification = json.loads((ROOT / "results/verification.json").read_text())
    assert verification["equivalent"]
    assert verification["sha256"]["csv"] == load["csv_sha256"]
    with pg_connect() as pg, redis_connect() as rd:
        pg.autocommit = True
        columns = pg.execute("""
            SELECT table_name,column_name,data_type FROM information_schema.columns
            WHERE table_schema='public' AND table_name IN ('sensors','readings')
            ORDER BY table_name,ordinal_position
        """).fetchall()
        types = {(r["table_name"], r["column_name"]): r["data_type"] for r in columns}
        assert types["sensors", "id"] == types["readings", "sensor_id"] == "integer"
        adapted = pg.execute("SELECT pg_typeof(%s)::text AS scalar, pg_typeof(%s)::text AS array",
                             (501, list(range(1, 1001)))).fetchone()
        counts = {"postgres": pg.execute("SELECT count(*) AS n FROM readings").fetchone()["n"],
                  "redis": sum(1 for _ in rd.scan_iter("iot:reading:*", count=10000))}
        assert counts["postgres"] == counts["redis"] == load["records"]
        stores = [PostgresStore(pg), RedisStore(rd)]
        identifier = min(500001, load["records"])
        points = [s.point(identifier) for s in stores]
        histories = [s.history(1, load["start"], load["end"], 3) for s in stores]
        # Dez instantes por sensor quando disponíveis, sem executar Q3 de 5M.
        selected = list(range(1, load["sensors"] + 1))
        end = min(load["end"], load["start"] + 2700)
        summaries = [s.summary(selected, load["start"], end) for s in stores]
        assert points[0] == points[1] and points[0] is not None
        assert histories[0] == histories[1] and summaries[0] == summaries[1]
        manifest_equal = json.loads(rd.get("iot:loaded")) == load
        state = rd.get("iot:load_state")
        assert manifest_equal and state == "complete", "Manifesto de carga incompleto ou divergente"
        report = {"validated_at": datetime.now(timezone.utc).isoformat(),
                  "logical_records_per_database": counts, "columns": columns,
                  "psycopg_parameter_types": adapted, "manifest_equal": manifest_equal,
                  "load_state": state, "point": points[0], "history_limit_3": histories[0],
                  "summary_range": {"start": load["start"], "end": end, "data": summaries[0]},
                  "full_verification_at": verification["verified_at"],
                  "full_verification_sha256": verification["sha256"],
                  "historical_benchmark_reexecuted": False,
                  "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                                    for p in ("app/store.py", "sql/schema.sql", "sql/queries.sql", "scripts/load.py")}}
    (ROOT / "results/documentation_validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
