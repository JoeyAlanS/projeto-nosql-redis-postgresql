"""Demonstra CRUD equivalente sem modificar permanentemente a massa original."""
import json
from datetime import datetime, timezone
from app.store import ROOT, store


def main():
    load=json.loads((ROOT/'results/load.json').read_text())
    row=dict(id=9_000_000_002,sensor_id=1,ts=load['end']+172800,
             temperature_centi=2900,humidity_centi=6000)
    trace={"executed_at":datetime.now(timezone.utc).isoformat(),"operations":[]}
    try:
        for source in ('postgres','redis'):
            with store(source) as s:
                s.create(row)
                before=s.point(row['id'])
                updated=dict(row,temperature_centi=3400)
                s.update(row['id'],updated)
                after=s.point(row['id'])
                s.delete(row['id'])
                deleted=s.point(row['id'])
                assert before == row and after == updated and deleted is None
                trace['operations'].append(dict(source=source,created_and_read=before,updated_and_read=after,
                                                after_delete=deleted,passed=True))
    finally:
        for source in ('postgres','redis'):
            with store(source) as s:
                if s.point(row['id']): s.delete(row['id'])
    trace['equivalent']=trace['operations'][0]['created_and_read']==trace['operations'][1]['created_and_read']
    (ROOT/'results/crud.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(trace,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
