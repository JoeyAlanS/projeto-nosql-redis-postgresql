"""Confere artefatos e estatísticas de entrega sem alterar dados dos bancos."""
import collections
import csv
import json
import re
import statistics
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
b=json.loads((root/'results/benchmark.json').read_text())
rows=list(csv.DictReader((root/'results/benchmark_raw.csv').open()))
counts=collections.Counter((r['query'],r['source']) for r in rows)
assert len(rows)==180 and set(counts.values())=={30}
for q in b['queries']:
    for source in ('postgres','redis'):
        med=statistics.median(float(r['elapsed_ms']) for r in rows if r['query']==q['query'] and r['source']==source)
        assert med==q['metrics'][source]['median_ms']
for code in ('Q1','Q2','Q3'):
    for rep in range(1,31):
        pair=[r['result_sha256'] for r in rows if r['query']==code and int(r['repetition'])==rep]
        assert len(pair)==2 and pair[0]==pair[1]
with zipfile.ZipFile(root/'output/apresentacao/Apresentacao_Final_Projeto_3.pptx') as z:
    assert z.testzip() is None
    ns={'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
    chart_parts=[n for n in z.namelist() if '/charts/' in n and n.endswith('.xml') and '/_rels/' not in n]
    assert len(chart_parts)==1
    chart=ET.fromstring(z.read(chart_parts[0]))
    assert chart.find('.//c:valAx/c:scaling/c:min',ns).attrib['val']=='0'
    assert any(n.startswith('ppt/media/') and len(z.read(n))>10000 for n in z.namelist())
    assert len([n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')])==14
verification=json.loads((root/'results/verification.json').read_text())
browser=json.loads((root/'results/browser.json').read_text())
assert verification['equivalent'] and verification['checked_readings']==1_000_000
assert browser['passed']
tests_log=(root/'results/tests.log').read_text()
test_runs=re.findall(r'^Ran (\d+) tests? in ',tests_log,re.MULTILINE)
assert len(test_runs)==1 and int(test_runs[0])>=11 and tests_log.rstrip().endswith('\nOK')
tests_count=int(test_runs[0])
identity=json.loads((root/'docs/identificacao.json').read_text())
missing_identity=[label for key,label in [('curso','Curso'),('professor','Professor'),('integrantes','Integrantes')]
                  if not identity.get(key)]
record={'requirements_documented':True,'logical_records_per_database':1000000,
        'full_dataset_equivalent':True,'raw_measurements':len(rows),'samples_per_source_per_query':30,
        'statistics_recomputed':True,'per_pair_result_hashes_equal':True,
        'nosql_advantage_observed':b['nosql_advantage_observed'],'integration_tests_passed':tests_count,
        'browser_passed':True,'slides':14,'chart_zero_baseline_verified':True,
        'embedded_dashboard_image_verified':True,
        'missing_identity_fields':missing_identity,
        'remaining_personalization':(', '.join(missing_identity)+' em docs/identificacao.json. ' if missing_identity else '')+
                                   'Submissão e apresentação a cargo da equipe.'}
(root/'results/entrega_status.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record,ensure_ascii=False,indent=2))
