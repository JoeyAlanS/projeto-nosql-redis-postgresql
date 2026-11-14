"""Pacote local de entrega com código, documentos, evidências e massa compactada."""
import gzip
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'
CSV=ROOT/'data/readings.csv'
GZIP=ROOT/'data/readings.csv.gz'
if CSV.exists():
    with CSV.open('rb') as source, GZIP.open('wb') as dest:
        with gzip.GzipFile(filename='readings.csv',mode='wb',fileobj=dest,mtime=0) as packed:
            shutil.copyfileobj(source,packed)
    expected=json.loads((ROOT/'results/load.json').read_text())['csv_sha256']
    with gzip.open(GZIP,'rb') as f:
        h=hashlib.file_digest(f,'sha256').hexdigest()
    assert h==expected,'A massa compactada diverge do CSV verificado'
include_dirs=['app','web','sql','scripts','tests','docs','results','output/pdf','output/apresentacao']
include_files=['README.md','Makefile','Dockerfile','compose.yaml','requirements.txt','requirements.lock.txt',
               'package.json','package-lock.json','.gitattributes','.gitignore','.dockerignore','.env.example','data/readings.csv.gz']
files=[ROOT/name for name in include_files if (ROOT/name).exists()]
for name in include_dirs:
    files.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files=sorted(set(files))
manifest={'created_at':datetime.now(timezone.utc).isoformat(),'files':[
    {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    for p in files]}
(OUT/'MANIFESTO_ENTREGA.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
target=OUT/'Projeto_3_Entrega_Completa.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,Path('Projeto_3')/p.relative_to(ROOT))
    z.write(OUT/'MANIFESTO_ENTREGA.json','Projeto_3/MANIFESTO_ENTREGA.json')
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
print(f'{target}: {target.stat().st_size:,} bytes, {len(files)+1} arquivos')
