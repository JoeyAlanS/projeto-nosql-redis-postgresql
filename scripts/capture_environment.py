"""Detalhes de armazenamento e índices após a execução."""
import json
from app.store import ROOT, pg_connect

with pg_connect() as p:
    tables=p.execute("SELECT sum(pg_total_relation_size(x)) AS bytes FROM unnest(ARRAY['sensors','readings']) AS x").fetchone()
    indexes=p.execute("SELECT indexname,indexdef,pg_relation_size(indexname::regclass) AS bytes FROM pg_indexes WHERE schemaname='public'").fetchall()
    (ROOT/'results/storage.json').write_text(json.dumps({
        'postgres_table_and_index_bytes':int(tables['bytes']), 'indexes':indexes,
        'note':'Diretórios persistidos incluem WAL/configuração. Métricas complementares em load.json.'
    },indent=2)+'\n')
