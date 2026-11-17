"""Sorted set por sensor: timestamp no score, ID da leitura como membro."""
import json
from uuid import uuid4

from _conexao import conectar


def executar():
    prefixo = f"demo:historico:{uuid4().hex}"
    indice = f"{prefixo}:sensor:1:leituras"
    chaves = [f"{prefixo}:leitura:{i}" for i in (1, 2, 3)]
    inicio = 1793491200  # 01/11/2026 00:00 UTC
    with conectar() as banco:
        try:
            for numero, chave in enumerate(chaves, start=1):
                instante = inicio + (numero - 1) * 300
                banco.hset(chave, mapping={
                    "id": numero, "sensor_id": 1, "ts": instante,
                    "temperature_centi": 2800 + numero * 50,
                    "humidity_centi": 6100,
                })
                banco.zadd(indice, {str(numero): instante})

            # Limites inclusivos: recupera as leituras de 00:05 e 00:10 UTC.
            ids = banco.zrangebyscore(indice, inicio + 300, inicio + 600)
            leituras = [banco.hgetall(f"{prefixo}:leitura:{i}") for i in ids]
            return {"exemplo": "Histórico por sensor e período", "prefixo": prefixo,
                    "inicio_utc": "2026-11-01 00:05", "fim_utc": "2026-11-01 00:10",
                    "ids": ids, "leituras": leituras}
        finally:
            banco.delete(indice, *chaves)


if __name__ == "__main__":
    print(json.dumps(executar(), ensure_ascii=False, indent=2))
