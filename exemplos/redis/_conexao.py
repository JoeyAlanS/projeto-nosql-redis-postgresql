"""Conexão compartilhada pelos exemplos didáticos (mesmo Redis do Compose)."""
import os

from redis import Redis


def conectar():
    return Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:56379/0"),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
