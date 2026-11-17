# Exemplos simples de Redis — entrega de 17/11

Três programas curtos para demonstrar os conceitos do Observatório IoT. Usam o Redis real do projeto e as mesmas unidades dos dados principais: `2850` representa `28,50 °C` e `6100` representa `61,00%` de umidade.

## Executar com Docker

Na raiz do repositório:

```bash
make up
make exemplos-redis
```

Os exemplos não dependem da carga de um milhão de leituras. `make up` também reconstrói a imagem para incluir os novos arquivos. Para executar um de cada vez:

```bash
docker compose exec -T app python exemplos/redis/01_crud_hash.py
docker compose exec -T app python exemplos/redis/02_historico_sensor.py
docker compose exec -T app python exemplos/redis/03_cache_ttl.py
```

Também é possível executá-los diretamente com Python 3.12 e `redis==5.2.1` instalado:

```bash
python exemplos/redis/01_crud_hash.py
```

Fora do contêiner, o endereço padrão é `redis://localhost:56379/0`. Dentro do Compose, a variável `REDIS_URL` já aponta para `redis://redis:6379/0`. Para outro servidor, configure essa variável antes da execução. A única biblioteca Python usada pelos exemplos é `redis`; eles não importam a API nem o adaptador PostgreSQL.

## 1. CRUD com hash

Arquivo: [01_crud_hash.py](01_crud_hash.py).

| Etapa | Comando | Resultado esperado |
|---|---|---|
| Criar | `HSET` com os cinco campos da leitura | Hash com temperatura `2850` e umidade `6100` |
| Ler | `HGETALL` | Dicionário com os campos e valores em texto |
| Atualizar | `HSET` do campo `temperature_centi` | Temperatura passa a `3300`, isto é, 33 °C |
| Excluir | `DEL`, seguido de `EXISTS` | `excluida: true` |

Mostre a função `executar`, principalmente as chamadas `hset`, `hgetall` e `delete`. O nome real da chave contém um UUID, por exemplo `demo:crud:<uuid>:leitura:1`.

## 2. Histórico com sorted set

Arquivo: [02_historico_sensor.py](02_historico_sensor.py).

Três hashes guardam as leituras de um sensor às **00:00, 00:05 e 00:10 UTC de 01/11/2026**. Um sorted set guarda os IDs como membros e os timestamps como scores. `ZRANGEBYSCORE` entre 00:05 e 00:10 devolve **IDs 2 e 3**, nessa ordem, incluindo os extremos. Depois, `HGETALL` recupera os valores de cada leitura.

O sorted set é um índice temporal, não uma cópia dos campos de temperatura e umidade. Na apresentação, explique primeiro o `zadd` e depois o `zrangebyscore`.

## 3. Cache com TTL

Arquivo: [03_cache_ttl.py](03_cache_ttl.py).

O programa demonstra uma ausência no cache, grava um resumo JSON com validade de dois segundos, recupera esse resumo e verifica sua expiração. A saída deve conter `ausente_antes: true`, o conteúdo de `acerto` e `expirou: true`. O TTL observado depende do tempo transcorrido e normalmente aparece como 2 ou 1 segundo.

O resumo é um valor fixo didático, sem consulta ao PostgreSQL. A massa principal `iot:*` não usa TTL, pois precisa preservar o histórico. O cache com expiração é um exemplo complementar do paradigma.

## Isolamento e limites

Cada execução cria um prefixo exclusivo `demo:<exemplo>:<uuid>`. O bloco `finally` remove apenas as chaves dessa execução. Não há `FLUSHDB`, `FLUSHALL`, substituição de carga ou escrita em `iot:*`. Os programas podem ser repetidos e demonstrados sem apagar os dados principais.

Os exemplos mostram os comandos básicos. Eles não implementam todas as regras da API, nem tornam a sequência inteira atômica. A implementação completa em [app/store.py](../../app/store.py) também valida sensores, mantém o índice de unicidade e usa Lua para alterações coerentes dos hashes e índices. Para demonstrar o mesmo CRUD nos **dois** bancos, use `python -m scripts.crud_demo` dentro do serviço `app`.

## Testar

```bash
make test-exemplos-redis
```

São três testes de integração com Redis real: valores do CRUD, limites inclusivos/ordem do histórico, acerto/expiração do cache e ausência de chaves remanescentes. `make test` continua executando os 11 testes da aplicação principal.

## Conexão com a entrega de 17/11

- **Vantagens e desvantagens:** os exemplos mostram acesso direto por chave e índice por período; a manutenção manual das estruturas e a expiração tornam visíveis responsabilidades da aplicação.
- **Problema e modelagem:** uma leitura de temperatura/umidade de um sensor em um instante. O mesmo significado aparece nas tabelas PostgreSQL e nos hashes/índices Redis.
- **Material completo:** [comparação e modelos](../../docs/02_modelagem.md), [DDL PostgreSQL](../../sql/schema.sql), [modelo Redis](../../docs/modelos/redis.svg) e [modelo relacional](../../docs/modelos/relacional.svg).

Referências oficiais: [Hashes](https://redis.io/docs/latest/develop/data-types/hashes/), [Sorted sets](https://redis.io/docs/latest/develop/data-types/sorted-sets/) e [SET com expiração](https://redis.io/docs/latest/commands/set/).
