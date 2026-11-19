"""Tempos de cliente: execução, rede e desserialização, sem conexão/serialização HTTP."""
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import statistics
import time
from datetime import datetime, timezone

from app.store import ROOT, PostgresStore, RedisStore, pg_connect, redis_connect


def percentile(values, p):
    values = sorted(values)
    index = (len(values)-1)*p
    lo, hi = math.floor(index), math.ceil(index)
    return values[lo] + (values[hi]-values[lo])*(index-lo)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=5)
    args = parser.parse_args()
    if args.repetitions < 10 or args.warmup < 1:
        parser.error("Use ao menos 10 repetições e 1 aquecimento")
    load = json.loads((ROOT / "results/load.json").read_text())
    verification = json.loads((ROOT / "results/verification.json").read_text())
    if not verification["equivalent"] or verification["sha256"]["csv"] != load["csv_sha256"]:
        raise SystemExit("Execute a verificação integral da massa atual antes do benchmark")
    # Mesmo filtro e exatamente a mesma forma de retorno para cada par.
    sid = min(501, load["sensors"])
    reading_id = min(500001, load["records"])
    selected = list(range(1, min(load["sensors"], 1000)+1))
    queries = [
        ("Q1", "Leitura por ID", lambda s: s.point(reading_id), {"reading_id": reading_id}),
        ("Q2", "Histórico de sensor", lambda s: s.history(sid, load["start"], load["end"], 200),
         {"sensor_id": sid, "start": load["start"], "end": load["end"], "limit": 200}),
        ("Q3", "Resumo de telemetria", lambda s: s.summary(selected, load["start"], load["end"]),
         {"sensor_ids": selected, "start": load["start"], "end": load["end"]}),
    ]
    raw, summaries, plans = [], [], {}
    with pg_connect() as pg, redis_connect() as rd:
        pg.autocommit = True
        # Reproduz o modelo original mesmo quando os índices adicionais estão ativos.
        stores = {"postgres": PostgresStore(pg), "redis": RedisStore(rd, optimized=False)}
        for code, name, run, filters in queries:
            for _ in range(args.warmup):
                for s in stores.values():
                    run(s)
            per_source = {src: [] for src in stores}
            digest = None
            for repetition in range(1, args.repetitions+1):
                order = ["postgres", "redis"] if repetition % 2 else ["redis", "postgres"]
                pair = {}
                for position, source in enumerate(order, 1):
                    before = time.perf_counter_ns()
                    result = run(stores[source])
                    ms = (time.perf_counter_ns()-before)/1e6
                    h = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                    raw.append(dict(query=code, name=name, repetition=repetition, position=position,
                                    source=source, elapsed_ms=ms, result_sha256=h))
                    per_source[source].append(ms)
                    pair[source] = result
                    digest = h
                assert pair["postgres"] == pair["redis"], f"Resultados divergentes: {code}"
            metrics = {src: {"median_ms": statistics.median(v), "p95_ms": percentile(v, .95),
                             "min_ms": min(v), "max_ms": max(v), "samples": len(v)}
                       for src, v in per_source.items()}
            summary = {"query": code, "name": name, "filters": filters, "metrics": metrics,
                       "postgres_over_redis": metrics["postgres"]["median_ms"]/metrics["redis"]["median_ms"],
                       "equivalent": True, "result_sha256": digest}
            summaries.append(summary)
            print(f"{code}: PostgreSQL {metrics['postgres']['median_ms']:.4f} ms / Redis {metrics['redis']['median_ms']:.4f} ms", flush=True)
        plan_queries = {
            "Q1": ("SELECT * FROM readings WHERE id=%s", (reading_id,)),
            "Q2": ("SELECT * FROM readings WHERE sensor_id=%s AND ts BETWEEN %s AND %s ORDER BY ts,id LIMIT 200",
                   (sid, load["start"], load["end"])),
            "Q3": ("SELECT count(*),count(DISTINCT sensor_id),COALESCE(sum(temperature_centi),0),COALESCE(sum(humidity_centi),0),count(*) FILTER (WHERE temperature_centi > 3200),min(temperature_centi),max(temperature_centi) FROM readings WHERE sensor_id=ANY(%s) AND ts BETWEEN %s AND %s",
                   (selected, load["start"], load["end"])),
        }
        for code, (sql, params) in plan_queries.items():
            plans[code] = pg.execute("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + sql, params).fetchone()["QUERY PLAN"]
        settings = {name: pg.execute(f"SHOW {name}").fetchone()[name] for name in
                    ("shared_buffers", "work_mem", "max_parallel_workers_per_gather", "fsync", "synchronous_commit")}
        hardware = {"platform": platform.platform(), "cpu_count": os.cpu_count(), "python": platform.python_version(),
                    "cpuinfo": next((l.split(":",1)[1].strip() for l in open('/proc/cpuinfo') if l.startswith('model name')), "não disponível"),
                    "meminfo": Path_read("/proc/meminfo"), "cgroup_memory_max": Path_read("/sys/fs/cgroup/memory.max"),
                    "cgroup_cpu_max": Path_read("/sys/fs/cgroup/cpu.max")}
        report = {"executed_at": datetime.now(timezone.utc).isoformat(), "records": load["records"],
                  "dataset_sha256": load["csv_sha256"], "repetitions": args.repetitions, "warmup": args.warmup,
                  "cache": "Aquecido, sem limpeza de cache do SO, sem cache HTTP ou de resultados na aplicação",
                  "measurement": "perf_counter_ns: cliente Python, ida/volta de rede e materialização integral da resposta; conexões reutilizadas",
                  "order": "Alternada a cada repetição", "concurrency": 1, "hardware": hardware,
                  "postgres_version": load["postgres_version"], "redis_version": load["redis_version"],
                  "postgres_settings": settings, "redis_settings": {"appendonly": "yes", "appendfsync": "everysec", "maxmemory-policy": "noeviction"},
                  "queries": summaries, "nosql_advantage_observed": any(q["postgres_over_redis"] > 1 for q in summaries)}
        with (ROOT / "results/benchmark_raw.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(raw[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(raw)
        (ROOT / "results/benchmark.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
        (ROOT / "results/plans.json").write_text(json.dumps(plans, indent=2, ensure_ascii=False)+"\n")
        print(f"{len(raw)} medições reais salvas; vantagem NoSQL: {report['nosql_advantage_observed']}")


def Path_read(path):
    from pathlib import Path
    p = Path(path)
    return p.read_text() if p.exists() else "não disponível"


if __name__ == "__main__":
    main()
