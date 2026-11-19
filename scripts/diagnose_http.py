"""Mede os caminhos HTTP reais, com a mesma carga e ordem alternada."""
import argparse
import json
import statistics
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--repetitions',type=int,default=20)
    args=parser.parse_args()
    cases={
        'ID_dashboard':'/api/readings/500001?source={source}',
        'ID_query':'/api/query?source={source}&operation=point&reading_id=500001',
        'historico_200':'/api/query?source={source}&operation=history&sensor_id=501&limit=200&redis_mode=optimized',
        'resumo_10000':'/api/query?source={source}&operation=summary&start=1793491200&end=1793493900&redis_mode=optimized',
    }
    samples=[]
    for name,path in cases.items():
        expected=None
        for repetition in range(args.repetitions+3):
            order=['postgres','redis'] if repetition%2==0 else ['redis','postgres']
            for source in order:
                begin=time.perf_counter_ns()
                with urllib.request.urlopen('http://localhost:8000'+path.format(source=source)) as response:
                    value=json.load(response)
                elapsed=(time.perf_counter_ns()-begin)/1e6
                data=value.get('data',value)
                if expected is None: expected=data
                assert data==expected,(name,source)
                if repetition>=3:
                    samples.append(dict(case=name,source=source,repetition=repetition-2,
                        http_ms=elapsed,backend_query_ms=value.get('elapsed_ms')))
    results={name:{source:{
        'http_median_ms':statistics.median(r['http_ms'] for r in samples if r['case']==name and r['source']==source),
        'backend_query_median_ms':statistics.median(r['backend_query_ms'] for r in samples if r['case']==name and r['source']==source)
          if name!='ID_dashboard' else None,
    } for source in ['postgres','redis']} for name in cases}
    result=dict(executed_at=datetime.now(timezone.utc).isoformat(),repetitions=args.repetitions,warmup=3,
                client='urllib, HTTP local, uma requisição de cada vez, ordem alternada',results=results,samples=samples)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
