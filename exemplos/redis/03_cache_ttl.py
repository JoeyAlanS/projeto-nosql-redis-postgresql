"""Cache de resumo: ausência, acerto e expiração automática após dois segundos."""
import json
import time
from uuid import uuid4

from _conexao import conectar


def executar():
    prefixo = f"demo:cache:{uuid4().hex}"
    chave = f"{prefixo}:resumo:sensor:1"
    with conectar() as banco:
        try:
            ausente_antes = banco.get(chave) is None  # cache miss
            # Resumo didático fixo; não é uma medição nem consulta ao PostgreSQL.
            resumo = {"sensor_id": 1, "leituras": 3, "temperatura_media": 29.0}
            banco.set(chave, json.dumps(resumo), ex=2)
            acerto = json.loads(banco.get(chave))  # cache hit
            ttl = banco.ttl(chave)

            # Espera curta e limitada; EXISTS/GET observam a expiração no servidor.
            limite = time.monotonic() + 5
            while banco.exists(chave) and time.monotonic() < limite:
                time.sleep(0.1)
            expirou = banco.get(chave) is None
            if not expirou:
                raise RuntimeError("A chave não expirou no prazo esperado")
            return {"exemplo": "Cache com TTL", "prefixo": prefixo,
                    "ausente_antes": ausente_antes, "acerto": acerto,
                    "ttl_segundos_observado": ttl, "expirou": expirou}
        finally:
            banco.delete(chave)


if __name__ == "__main__":
    print(json.dumps(executar(), ensure_ascii=False, indent=2))
