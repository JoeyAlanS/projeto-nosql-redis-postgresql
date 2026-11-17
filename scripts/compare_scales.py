"""Orquestra cenários independentes de 1M e 5M, sem substituir a massa principal."""
import argparse
import csv
import json
import os
import re
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/escala"
SIZES = (1_000_000, 5_000_000)


def command(records, *arguments):
    if records not in SIZES:
        raise ValueError("Cenário deve ser 1000000 ou 5000000")
    env = dict(os.environ, ESCALA_REGISTROS=str(records),
               ESCALA_UID=str(os.getuid()), ESCALA_GID=str(os.getgid()),
               ESCALA_SUBNET=f"10.203.{18 if records == 1_000_000 else 19}.0/24")
    return (["docker", "compose", "-p", f"iot-escala-{records}", "-f", "compose.escala.yaml", *arguments], env)


def run(records, *arguments):
    cmd, env = command(records, *arguments)
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def read(path):
    return json.loads(path.read_text())


def render_plan(node, depth=0):
    label = node["Node Type"]
    if node.get("Index Name"):
        label += " using " + node["Index Name"]
    if node.get("Relation Name"):
        label += " on " + node["Relation Name"]
    line = (f"{'  ' * depth}{label}: cost={node.get('Startup Cost')}..{node.get('Total Cost')}, estimadas={node.get('Plan Rows')}, "
            f"linhas reais/loop={node.get('Actual Rows')}, loops={node.get('Actual Loops')}, "
            f"tempo/loop={node.get('Actual Total Time')} ms, "
            f"blocos hit={node.get('Shared Hit Blocks', 0)}, read={node.get('Shared Read Blocks', 0)}")
    result = [line]
    for key in ("Index Cond", "Filter", "Sort Key", "Sort Method", "Heap Fetches", "Rows Removed by Filter", "Temp Read Blocks", "Temp Written Blocks"):
        if key in node:
            if key.startswith('Temp ') and node[key] == 0:
                continue
            value = str(node[key])
            def short_array(match):
                ids = match.group(1).split(',')
                if len(ids) <= 20:
                    return match.group(0)
                return "'{" + ','.join(ids[:3]) + ',...,' + ids[-1] + "}'::" + match.group(2) + " [" + str(len(ids)) + " IDs; lista abreviada]"
            value = re.sub(r"'\{([0-9,]+)\}'::((?:smallint|integer|bigint)\[\])", short_array, value)
            result.append(f"{'  ' * (depth + 1)}{key}: {value}")
    for child in node.get("Plans", []):
        result.extend(render_plan(child, depth + 1))
    return result


def summarize():
    scenarios = []
    code_hashes = None
    for records in SIZES:
        directory = RESULTS / str(records)
        load, verification, benchmark, plans, concurrent = [read(directory / name) for name in
            ("load.json", "verification.json", "benchmark.json", "plans.json", "concurrent_load.json")]
        assert load["records"] == verification["checked_readings"] == benchmark["records"] == concurrent["records"] == records
        assert verification["equivalent"] and verification["all_temporal_and_unique_indexes_verified"]
        assert len(set(verification["sha256"].values())) == 1
        assert load["csv_sha256"] == verification["sha256"]["csv"] == benchmark["dataset_sha256"] == concurrent["dataset_sha256"]
        assert concurrent["all_responses_valid"] and all(metric["errors"] == 0 for metric in concurrent["metrics"])
        if not concurrent.get("code_sha256"):
            raise ValueError("Repita o teste concorrente com a versão atual para registrar o código executado")
        if code_hashes is None:
            code_hashes = concurrent["code_sha256"]
        assert code_hashes == concurrent["code_sha256"], "Código HTTP difere entre cenários"
        http_raw = list(csv.DictReader((directory / "concurrent_load_raw.csv").open()))
        assert len(http_raw) == len(concurrent["clients"]) * 2 * concurrent["requests_per_source_per_level"]
        for metric in concurrent["metrics"]:
            group = [r for r in http_raw if r["source"] == metric["source"] and int(r["concurrency"]) == metric["concurrency"]]
            assert len(group) == metric["requests"] == concurrent["requests_per_source_per_level"]
            assert all(r["valid"] == "True" and r["status"] == "200" for r in group)
            assert len({r["request_index"] for r in group}) == len(group)
            assert statistics.median(float(r["elapsed_ms"]) for r in group) == metric["median_ms"]
        raw = list(csv.DictReader((directory / "benchmark_raw.csv").open()))
        assert len(raw) == 6 * benchmark["repetitions"]
        for query in benchmark["queries"]:
            assert query["equivalent"]
            for source in ("postgres", "redis"):
                values = [float(row["elapsed_ms"]) for row in raw if row["query"] == query["query"] and row["source"] == source]
                assert len(values) == benchmark["repetitions"]
                assert statistics.median(values) == query["metrics"][source]["median_ms"]
            for repetition in range(1, benchmark["repetitions"] + 1):
                hashes = [row["result_sha256"] for row in raw if row["query"] == query["query"] and int(row["repetition"]) == repetition]
                assert len(hashes) == 2 and hashes[0] == hashes[1]
        plan_text = [f"POSTGRESQL: {records:,} LEITURAS", "Extraído do EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON).",
                     "Linhas e tempos de cada nó são médias por loop; não some tempos de pais e filhos.",
                     "Listas ANY extensas estão abreviadas; o plano integral está em plans.json.", ""]
        compact_plans = {}
        for code, plan in plans.items():
            actual = plan[0]
            lines = render_plan(actual["Plan"])
            compact_plans[code] = {"execution_ms": actual["Execution Time"], "tree": "\n".join(lines)}
            plan_text.extend([code, *lines, f"Planning Time: {actual['Planning Time']} ms", f"Execution Time: {actual['Execution Time']} ms", ""])
        redis_paths = {
            "Q1": "HGETALL iot:reading:500001 -> cinco campos de um único hash.",
            "Q2": f"EVALSHA HISTORY_LUA -> ZRANGEBYSCORE de 1 sorted set ({records // load['sensors']} membros), LIMIT 200 -> 200 HMGET -> 200 leituras.",
            "Q3": f"EVALSHA SUMMARY_LUA -> {load['sensors']} ZRANGEBYSCORE -> {records:,} HMGET de temperatura/umidade -> agregação em Lua; bloqueia outras operações Redis durante o script."
        }
        plan_text.extend(["REDIS: CAMINHO DOS COMANDOS", "Rastreamento do código, não plano de otimizador SQL.", *[f"{code}: {path}" for code, path in redis_paths.items()]])
        (directory / "plans.txt").write_text("\n".join(plan_text) + "\n")
        scenarios.append({"records": records, "sensors": load["sensors"], "start": load["start"], "end": load["end"],
            "dataset_sha256": load["csv_sha256"], "verified_readings": verification["checked_readings"],
            "versions": {"postgres": load["postgres_version"], "redis": load["redis_version"]},
            "equivalent": verification["equivalent"], "load": {key: load[key] for key in
                ("generation_seconds", "postgres_load_seconds", "redis_load_seconds", "csv_bytes", "postgres_bytes", "redis_used_memory_bytes", "redis_aof_bytes")},
            "queries": [{key: query[key] for key in ("query", "name", "metrics", "equivalent")} for query in benchmark["queries"]],
            "postgres_plans": compact_plans, "redis_paths": redis_paths, "concurrent": concurrent["metrics"]})
    ratios = {source: scenarios[1]["load"][source + "_load_seconds"] / scenarios[0]["load"][source + "_load_seconds"] for source in ("postgres", "redis")}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "scenarios": scenarios, "http_code_sha256": code_hashes,
              "volume_factor": 5, "load_time_factor_5m_over_1m": ratios,
              "protocol": {"repetitions": benchmark["repetitions"], "warmup": benchmark["warmup"],
                           "clients": concurrent["clients"], "requests_per_source_per_level": concurrent["requests_per_source_per_level"],
                           "cache": "Aquecido; sem limpar cache do SO", "isolated_database_projects": True,
                           "load_trials_per_size": 1, "http_load_trials_per_source_per_level": 1},
              "limits": ["Um computador compartilhado; sem isolamento de CPU ou cache do SO.",
                         "Carga inicial medida uma vez por tamanho; não demonstra significância estatística.",
                         "Carga PostgreSQL inclui COPY, índices existentes e VACUUM ANALYZE; Redis inclui criação dos índices e espera de 1,1 s para AOF everysec.",
                         "Tamanho PostgreSQL em disco e memória Redis são métricas diferentes.",
                         "Concorrência mede leitura pontual HTTP, não escrita, resumo concorrente nem teste de estresse até falhar.",
                         "Banco maior não significa mais usuários simultâneos; os dois fatores foram variados separadamente."]}
    RESULTS.mkdir(exist_ok=True, parents=True)
    (RESULTS / "comparacao.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summarize-only", action="store_true")
    parser.add_argument("--reuse", action="store_true", help="Reutiliza a massa isolada após conferir o manifesto; a verificação integral é repetida")
    parser.add_argument("--http-only", action="store_true", help="Repete apenas a carga HTTP das massas já verificadas")
    parser.add_argument("--records", type=int, nargs="+", choices=SIZES, default=list(SIZES))
    args = parser.parse_args()
    if not args.summarize_only:
        # Sem --replace: uma execução anterior precisa ser removida conscientemente para refazer a carga.
        for records in args.records:
            (RESULTS / str(records)).mkdir(parents=True, exist_ok=True)
            (ROOT / 'data/escala' / str(records)).mkdir(parents=True, exist_ok=True)
            print(f"\nCENÁRIO {records:,} — bancos independentes", flush=True)
            try:
                run(records, "up", "-d", "--build", "--wait")
                existing = RESULTS / str(records) / "load.json"
                if args.reuse or args.http_only:
                    if not existing.exists() or read(existing)["records"] != records:
                        raise SystemExit("--reuse exige um manifesto da massa isolada correspondente")
                else:
                    run(records, "exec", "-T", "app", "python", "-m", "scripts.load", "--records", str(records))
                if args.http_only:
                    verification = read(RESULTS / str(records) / "verification.json")
                    assert verification["equivalent"] and verification["checked_readings"] == records
                    assert verification["sha256"]["csv"] == read(existing)["csv_sha256"]
                modules = [] if args.http_only else [("scripts.verify", []), ("scripts.benchmark", ["--repetitions", "30", "--warmup", "5"])]
                modules.append(("scripts.concurrent_load", ["--requests", "1200", "--clients", "1", "4", "16"]))
                for module, flags in modules:
                    run(records, "exec", "-T", "app", "python", "-m", module, *flags)
            finally:
                run(records, "stop")
    if all((RESULTS / str(records) / "concurrent_load.json").exists() for records in SIZES):
        report = summarize()
        print(json.dumps({"records": [s["records"] for s in report["scenarios"]], "report": str(RESULTS / "comparacao.json")}, indent=2))


if __name__ == "__main__":
    main()
