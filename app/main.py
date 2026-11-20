import json
import time
from fastapi.responses import JSONResponse
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.store import (Busy, Conflict, Invalid, Missing, ROOT, MAX_READING_ID, MAX_SENSOR_ID,
                       MAX_TIMESTAMP, pg_connect, redis_connect, store)

app = FastAPI(title="Observatório IoT: PostgreSQL e Redis", version="1.0.0")
Source = Literal["postgres", "redis"]
Operation = Literal["point", "history", "summary"]
RedisMode = Literal['auto', 'baseline', 'optimized']
ReadingPath = Annotated[int, Path(gt=0, le=MAX_READING_ID)]


class Reading(BaseModel):
    id: int = Field(gt=0, le=MAX_READING_ID)
    sensor_id: int = Field(gt=0, le=MAX_SENSOR_ID)
    ts: int = Field(gt=0, le=MAX_TIMESTAMP)
    temperature_centi: int = Field(ge=-5000, le=10000)
    humidity_centi: int = Field(ge=0, le=10000)


@app.get("/api/health")
def health():
    try:
        with pg_connect() as p, redis_connect() as r:
            p.execute("SELECT 1")
            r.ping()
        return {"postgres": "ok", "redis": "ok"}
    except Exception as e:
        raise HTTPException(503, "Banco indisponível. Confira docker compose logs.") from e


@app.get("/api/meta")
def meta(source: Source = "postgres"):
    try:
        with store(source) as s:
            sensors = s.sensors()
        manifest = ROOT / "results/load.json"
        load = json.loads(manifest.read_text()) if manifest.exists() else None
        return {"sensors": sensors, "load": load}
    except Exception as e:
        raise HTTPException(503, "Massa não carregada. Execute make load.") from e


def run_query(source, operation, reading_id, sensor_id, start, end, limit, location, redis_mode='auto'):
    if end < start:
        raise HTTPException(422, "Fim deve ser maior ou igual ao início")
    if operation == 'history' and not sensor_id:
        raise HTTPException(422, "Selecione um sensor para consultar o histórico")
    begin = time.perf_counter_ns()
    with store(source, redis_mode) as s:
        connected = time.perf_counter_ns()
        # Conexão e seleção de sensores fora do trecho cronometrado em ambas as fontes.
        ids = [sensor_id] if sensor_id else s.sensor_ids(location) if operation == 'summary' else []
        if sensor_id and location and sensor_id not in s.sensor_ids(location):
            raise HTTPException(422, "Sensor não pertence ao local selecionado")
        t = time.perf_counter_ns()
        if operation == "point":
            result = s.point(reading_id)
        elif operation == "history":
            result = s.history(sensor_id, start, end, limit)
        else:
            result = s.summary(ids, start, end)
        finished = time.perf_counter_ns()
        elapsed = (finished - t) / 1e6
    closed = time.perf_counter_ns()
    strategy = ('redis_optimized' if s.optimized else 'redis_baseline') if source == 'redis' else 'postgres_raw'
    return {"source": source, "operation": operation, "strategy": strategy, "elapsed_ms": elapsed,
            'timings_ms': {'connection_and_strategy': (connected-begin)/1e6,
                           'sensor_selection': (t-connected)/1e6, 'query': elapsed,
                           'connection_close': (closed-finished)/1e6,
                           'backend_total': (closed-begin)/1e6}, "data": result}


@app.get("/api/query")
def query(source: Source = "postgres", operation: Operation = "summary", reading_id: int = Query(1, gt=0, le=MAX_READING_ID),
          sensor_id: int | None = Query(None, gt=0, le=MAX_SENSOR_ID), start: int = Query(1, gt=0, le=MAX_TIMESTAMP),
          end: int = Query(4_102_444_800, gt=0, le=MAX_TIMESTAMP), limit: int = Query(200, ge=1, le=1000), location: str | None = None,
          redis_mode: RedisMode = 'auto'):
    return run_query(source, operation, reading_id, sensor_id, start, end, limit, location, redis_mode)


@app.get("/api/compare")
def compare(operation: Operation = "point", reading_id: int = Query(500001, gt=0, le=MAX_READING_ID),
            sensor_id: int | None = Query(None, gt=0, le=MAX_SENSOR_ID), start: int = Query(1, gt=0, le=MAX_TIMESTAMP),
            end: int = Query(4_102_444_800, gt=0, le=MAX_TIMESTAMP), limit: int = Query(200, ge=1, le=1000), location: str | None = None,
            redis_mode: RedisMode = 'auto'):
    outputs = [run_query(src, operation, reading_id, sensor_id, start, end, limit, location, redis_mode) for src in ("postgres", "redis")]
    return {"results": outputs, "equivalent": outputs[0]["data"] == outputs[1]["data"],
            "note": "Uma execução por fonte. Use o benchmark para medianas com aquecimento e ordem alternada."}


@app.exception_handler(Busy)
def busy_handler(request, exc):
    return JSONResponse(status_code=503, content={'detail': str(exc)})


@app.get('/api/optimization')
def optimization():
    with redis_connect() as rd:
        state = rd.get('iot:opt:v1:state') or 'not_built'
    paths = [ROOT/'results/otimizacao/benchmark.json', ROOT/'results/escala/5000000/otimizacao/benchmark.json']
    return {'state':state,'scenarios':[json.loads(p.read_text()) for p in paths if p.exists()]}


@app.get('/api/optimization/chart')
def optimization_chart():
    path = ROOT/'results/otimizacao/comparacao.png'
    if not path.exists():
        raise HTTPException(404,'Gráfico ainda não gerado')
    return FileResponse(path,media_type='image/png')


@app.get("/api/benchmark")
def benchmark():
    path = ROOT / "results/benchmark.json"
    if not path.exists():
        raise HTTPException(404, "Execute make benchmark para gerar o experimento")
    return json.loads(path.read_text())


@app.get("/api/scalability")
def scalability():
    path = ROOT / "results/escala/comparacao.json"
    if not path.exists():
        raise HTTPException(404, "A comparação de 1 e 5 milhões ainda não foi executada")
    return json.loads(path.read_text())


@app.get("/api/scalability/{records}/plans")
def scalability_plans(records: Literal["1000000", "5000000"]):
    path = ROOT / "results/escala" / str(records) / "plans.txt"
    if not path.exists():
        raise HTTPException(404, "Planos deste cenário ainda não foram gerados")
    return FileResponse(path, media_type="text/plain; charset=utf-8")


def mutate(source, operation, row=None, reading_id=None):
    try:
        with store(source) as s:
            if operation == "create":
                return s.create(row.model_dump())
            if operation == "update":
                if reading_id != row.id:
                    raise HTTPException(422, "ID do corpo deve ser igual ao ID da rota")
                return s.update(reading_id, row.model_dump())
            return s.delete(reading_id)
    except Conflict as e:
        raise HTTPException(409, str(e)) from e
    except Busy as e:
        raise HTTPException(503, str(e)) from e
    except Missing as e:
        raise HTTPException(404, str(e)) from e
    except Invalid as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/readings", status_code=201)
def create_reading(row: Reading, source: Source):
    return mutate(source, "create", row)


@app.get("/api/readings/{reading_id}")
def read_reading(reading_id: ReadingPath, source: Source):
    with store(source) as s:
        row = s.point(reading_id)
    if row is None:
        raise HTTPException(404, "Leitura não encontrada")
    return row


@app.put("/api/readings/{reading_id}")
def update_reading(reading_id: ReadingPath, row: Reading, source: Source):
    return mutate(source, "update", row, reading_id)


@app.delete("/api/readings/{reading_id}")
def delete_reading(reading_id: ReadingPath, source: Source):
    return mutate(source, "delete", reading_id=reading_id)


@app.get("/")
def index():
    return FileResponse(ROOT / "web/index.html")


app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")

# Central operacional: contratos próprios, sem filtros históricos implícitos.
from app.live import live_store

class LiveState(BaseModel):
    ts: int = Field(ge=1,le=MAX_TIMESTAMP)
    temperature_centi: int = Field(ge=-5000,le=10000)
    humidity_centi: int = Field(ge=0,le=10000)

@app.get('/api/live')
def live_query(source: Source='redis',operation: Literal['state','summary','alerts']='summary',
               sensor_id:int=Query(501,ge=1,le=MAX_SENSOR_ID),location:str|None=None,
               limit:int=Query(20,ge=1,le=100)):
    with live_store(source) as s:
        begin=time.perf_counter_ns()
        if operation=='state':value=s.latest(sensor_id)
        elif operation=='summary':value=s.summary(location)
        else:value=s.alerts(location,limit)
        elapsed=(time.perf_counter_ns()-begin)/1e6
    return {'source':source,'operation':operation,'elapsed_ms':elapsed,'data':value,
            'model':'Estado operacional atual; não é resumo do histórico'}

@app.put('/api/live/sensors/{sensor_id}')
def live_update(sensor_id:Annotated[int,Path(ge=1,le=MAX_SENSOR_ID)],row:LiveState,source:Source):
    try:
        with live_store(source) as s:return s.write(sensor_id,**row.model_dump())
    except Invalid as exc:raise HTTPException(422,str(exc)) from exc

@app.delete('/api/live/sensors/{sensor_id}')
def live_delete(sensor_id:Annotated[int,Path(ge=1,le=MAX_SENSOR_ID)],source:Source):
    try:
        with live_store(source) as s:return s.write(sensor_id,remove=True)
    except Invalid as exc:raise HTTPException(422,str(exc)) from exc

@app.get('/api/live/benchmark')
def live_benchmark():
    path=ROOT/'results/live/benchmark.json'
    if not path.exists():raise HTTPException(404,'Execute make benchmark-central')
    return json.loads(path.read_text())

@app.get('/api/live/chart')
def live_chart():
    path=ROOT/'results/live/latency.png'
    if not path.exists():raise HTTPException(404,'Execute make graficos-central')
    return FileResponse(path)
