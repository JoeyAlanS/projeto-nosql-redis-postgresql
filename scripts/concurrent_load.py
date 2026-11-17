"""Carga HTTP fechada: clientes simultâneos consultam leituras reais, sem gravar dados."""
import argparse
import csv
import hashlib
import json
import statistics
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.store import ROOT
from scripts.benchmark import percentile
from scripts.load import generate_row


def reading_id(index, requests, records):
    """A mesma sequência para as duas fontes, distribuída por toda a faixa de IDs."""
    return 1 + index * (records - 1) // max(requests - 1, 1)


def request_reading(base_url, source, identifier, expected):
    started = time.perf_counter_ns()
    status, valid, error = 0, False, ""
    try:
        with urllib.request.urlopen(
            f"{base_url}/api/readings/{identifier}?source={source}", timeout=30
        ) as response:
            status = response.status
            valid = status == 200 and json.load(response) == expected
            if not valid:
                error = "Resposta diferente dos cinco campos esperados"
    except urllib.error.HTTPError as exc:
        status, error = exc.code, f"HTTP {exc.code}"
    except Exception as exc:
        error = type(exc).__name__
    return {"reading_id": identifier, "status": status, "valid": valid,
            "elapsed_ms": (time.perf_counter_ns() - started) / 1e6, "error": error}


def run_group(base_url, source, concurrency, requests, load):
    barrier = threading.Barrier(concurrency + 1)

    def client(worker):
        samples = []
        barrier.wait(timeout=30)
        for index in range(worker, requests, concurrency):
            identifier = reading_id(index, requests, load["records"])
            result = request_reading(base_url, source, identifier,
                                     generate_row(identifier, load["sensors"], load["seed"]))
            samples.append(dict(source=source, concurrency=concurrency, request_index=index, **result))
        return samples

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(client, worker) for worker in range(concurrency)]
        started = time.perf_counter()
        barrier.wait(timeout=30)
        samples = [sample for future in futures for sample in future.result()]
        seconds = time.perf_counter() - started
    successes = [sample["elapsed_ms"] for sample in samples if sample["valid"]]
    metrics = {"source": source, "concurrency": concurrency, "requests": len(samples),
               "successes": len(successes), "errors": len(samples) - len(successes),
               "wall_seconds": seconds, "requests_per_second": len(samples) / seconds,
               "successful_requests_per_second": len(successes) / seconds,
               "median_ms": statistics.median(successes) if successes else None,
               "p95_ms": percentile(successes, .95) if successes else None}
    return metrics, samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=1200, help="Requisições por fonte e nível")
    parser.add_argument("--clients", type=int, nargs="+", default=[1, 4, 16])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if args.requests < 30 or not args.clients or len(set(args.clients)) != len(args.clients) or any(c < 1 or c > min(args.requests, 32) for c in args.clients):
        parser.error("Use >=30 requisições e de 1 a 32 clientes, sem exceder as requisições")
    load = json.loads((ROOT / "results/load.json").read_text())
    metrics, samples = [], []
    for source in ("postgres", "redis"):
        for index in range(10):
            identifier = reading_id(index, 10, load["records"])
            result = request_reading(args.base_url, source, identifier,
                                     generate_row(identifier, load["sensors"], load["seed"]))
            if not result["valid"]:
                raise SystemExit(f"Aquecimento falhou: {source}: {result}")
    for level, concurrency in enumerate(args.clients):
        sources = ("postgres", "redis") if level % 2 == 0 else ("redis", "postgres")
        for source in sources:
            group, raw = run_group(args.base_url, source, concurrency, args.requests, load)
            metrics.append(group)
            samples.extend(raw)
            print(f"{source}: {concurrency} clientes, {group['requests_per_second']:.1f} req/s, "
                  f"p95={group['p95_ms']} ms, erros={group['errors']}", flush=True)
    report = {"executed_at": datetime.now(timezone.utc).isoformat(), "records": load["records"],
              "dataset_sha256": load["csv_sha256"], "operation": "GET /api/readings/{id}?source=...",
              "model": "Carga fechada, sem think time; cada cliente espera a resposta antes da próxima requisição",
              "measurement": "HTTP completo: conexão HTTP, FastAPI, conexão ao banco, consulta e resposta JSON; sem reutilização intencional de conexões HTTP",
              "scope": "Consulta por ID; não mede escrita concorrente nem resumo Q3 concorrente",
              "order": "Alternada por nível: PostgreSQL/Redis no primeiro nível; Redis/PostgreSQL no seguinte",
              "ids": "Sequência determinística distribuída por toda a faixa, igual nas duas fontes",
              "warmup_requests_per_source": 10, "requests_per_source_per_level": args.requests,
              "clients": args.clients, "metrics": metrics,
              "code_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                              ("app/main.py", "app/store.py", "scripts/concurrent_load.py")},
              "all_responses_valid": all(sample["valid"] for sample in samples)}
    (ROOT / "results/concurrent_load.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    with (ROOT / "results/concurrent_load_raw.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(samples[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(samples)
    if not report["all_responses_valid"]:
        raise SystemExit("Teste registrou falhas; confira os resultados brutos")


if __name__ == "__main__":
    main()
