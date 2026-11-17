"""Criar, ler, atualizar e excluir uma leitura usando um hash Redis."""
import json
from uuid import uuid4

from _conexao import conectar


def executar():
    # Um prefixo novo a cada execução evita misturar demos e dados do projeto.
    prefixo = f"demo:crud:{uuid4().hex}"
    chave = f"{prefixo}:leitura:1"
    with conectar() as banco:
        try:
            # CREATE: os mesmos cinco campos lógicos usados no projeto.
            banco.hset(chave, mapping={
                "id": 1, "sensor_id": 1, "ts": 1793491200,
                "temperature_centi": 2850, "humidity_centi": 6100,
            })
            # READ: decode_responses devolve textos; 2850 representa 28,50 °C.
            criada = banco.hgetall(chave)

            # UPDATE: altera somente o campo de temperatura.
            banco.hset(chave, "temperature_centi", 3300)
            atualizada = banco.hgetall(chave)

            # DELETE: remove a leitura e confirma sua ausência.
            banco.delete(chave)
            excluida = not banco.exists(chave)
            return {"exemplo": "CRUD com hash", "prefixo": prefixo,
                    "criada": criada, "atualizada": atualizada,
                    "excluida": excluida}
        finally:
            # Remove apenas a chave desta execução, inclusive em caso de erro.
            banco.delete(chave)


if __name__ == "__main__":
    print(json.dumps(executar(), ensure_ascii=False, indent=2))
