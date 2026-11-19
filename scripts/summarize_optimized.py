"""Valida as amostras e escreve uma síntese dos novos ensaios."""
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MEASURED_REVISION='0d7a74adea48f06aecbac78a09dc880677ddd89c'


def main():
    paths=[ROOT/'results/otimizacao/benchmark.json',ROOT/'results/escala/5000000/otimizacao/benchmark.json']
    lines=['# Novos resultados — otimização Redis (19/11/2026)','',
           'Medições da revisão `0d7a74a`, anteriores ao parser compilado e à redução da seleção de sensores. '
           '[Diagnóstico e medições da revisão seguinte](DIAGNOSTICO_DESEMPENHO.md).','',
           'Medições com um cliente, cache aquecido, 10 repetições e 2 aquecimentos por variante/operação. '
           'Tempos de cliente, incluindo execução, rede e desserialização, sem abertura da conexão e sem HTTP. '
           'A ordem das variantes foi rotacionada. Todos os resultados foram comparados campo a campo.','',
           '| Massa | Consulta | PostgreSQL bruto (ms) | Redis original (ms) | Redis otimizado (ms) | PostgreSQL pré-agregado (ms) |',
           '|---|---|---:|---:|---:|---:|']
    audited=[]
    for path in paths:
        report=json.loads(path.read_text()); raw=list(csv.DictReader(path.with_name('benchmark_raw.csv').open()))
        assert report['equivalent'] and report['redis_build']['all_full_indexes_and_buckets_verified']
        for query in report['queries']:
            pairs={}
            for source,metrics in query['metrics'].items():
                records=[r for r in raw if r['query']==query['query'] and r['source']==source]
                values=[float(r['elapsed_ms']) for r in records]
                assert len(values)==report['repetitions']==metrics['samples']
                assert statistics.median(values)==metrics['median_ms']
                assert math.isclose(statistics.quantiles(values,n=100,method='inclusive')[94],metrics['p95_ms'],rel_tol=1e-12)
                for r in records: pairs.setdefault(r['repetition'],set()).add(r['result_sha256'])
            assert all(len(hashes)==1 for hashes in pairs.values())
            values=[f'{query["metrics"][s]["median_ms"]:.3f}' if s in query['metrics'] else '—' for s in
                    ('postgres_raw','redis_baseline','redis_optimized','postgres_materialized')]
            lines.append(f'| {report["records"]:,} | {query["query"]} | '+ ' | '.join(values)+' |')
        audited.append({'records':report['records'],'samples':len(raw),'medians_and_p95_recomputed':True,'response_hashes_equal':True})
    lines.extend(['','Q1 mantém o mesmo `HGETALL`; a diferença entre variantes é variação de medição. '
        'Q2 retorna as primeiras 200 leituras de um sensor. Q3 resume todos os registros do cenário.','',
        '## Como interpretar',''])
    for path in paths:
        r=json.loads(path.read_text()); q2,q3=r['queries'][1:]
        m2,m3=q2['metrics'],q3['metrics']; b=r['redis_build']
        lines.append(f'- **{r["records"]:,} leituras:** Q2 Redis melhorou {m2["redis_baseline"]["median_ms"]/m2["redis_optimized"]["median_ms"]:.2f}×; '
                     f'Q3 melhorou {m3["redis_baseline"]["median_ms"]/m3["redis_optimized"]["median_ms"]:.2f}× frente ao Redis original. '
                     f'A construção conferiu todos os registros e {b["daily_buckets"]:,} resumos; levou {b["seconds"]:.2f} s. '
                     f'Aumento observado de `used_memory`: {(b["memory_after_bytes"]-b["memory_before_bytes"])/2**20:.2f} MiB. '
                     f'Preparação da view SQL: {r["postgres_materialization_seconds"]:.2f} s.')
    lines.extend(['','O PostgreSQL bruto venceu Q2 neste ensaio; o Redis otimizado reduziu seu custo, sem garantia de ultrapassar SQL. '
        'Em Q3, Redis otimizado venceu o SQL bruto, mas PostgreSQL pré-agregado foi mais rápido. '
        'A comparação pré-agregada é de leitura: Redis mantém seus resumos a cada CRUD; a view SQL usa atualização prévia. '
        'Não são garantias gerais de superioridade, capacidade máxima ou mesma durabilidade.','',
        '## Experimento TimeSeries',''])
    ts=json.loads((ROOT/'results/otimizacao/timeseries.json').read_text())
    lines.append('Prova separada com **10.000 leituras**: '+', '.join(f'{s}: {v:.3f} ms' for s,v in ts['median_ms'].items())+'. '
                 'Agregação, alteração, exclusão e compactação conferidas; todas as chaves temporárias removidas. '
                 'TimeSeries não superou as outras estratégias neste protótipo. Não foi integrado à API nem testado com 1M/5M.')
    lines.extend(['','![Gráfico das novas medianas](../results/otimizacao/comparacao.png)','',
                  'Estrutura, scripts, comandos e limites: [guia da otimização](OTIMIZACAO_REDIS.md).',''])
    (ROOT/'docs/RESULTADOS_OTIMIZACAO.md').write_text('\n'.join(lines))
    receipt={'scenarios':audited,'samples_total':sum(r['samples'] for r in audited),
             'source_revision':MEASURED_REVISION,
             'source_files_match_measured_revision':all(all(hashlib.sha256(
                 (ROOT/'results/otimizacao/measured-source'/name).read_bytes()).hexdigest()==digest
                for name,digest in json.loads(p.read_text())['code_sha256'].items()) for p in paths),
             'working_tree_matches_measured':all(all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
                for name,digest in json.loads(p.read_text())['code_sha256'].items()) for p in paths)}
    assert receipt['source_files_match_measured_revision']
    (ROOT/'results/otimizacao/audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__': main()
