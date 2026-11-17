# Demonstração — entrega de 17/11

O problema é a consulta de temperatura e umidade de sensores de um campus simulado. PostgreSQL e Redis representam o mesmo conjunto de leituras. Os dados são sintéticos, não medições de sensores físicos conectados ao computador.

## Iniciar e mostrar a aplicação

Na raiz do projeto:

```bash
make up
```

Abra **http://localhost:8000**. Nesta instalação a massa de um milhão de leituras já está carregada e persiste nos volumes Docker. Em uma instalação nova, execute `make load` uma vez antes da demonstração da aplicação.

1. Mostre o indicador **PostgreSQL e Redis conectados** e os indicadores do período.
2. Selecione um local e um sensor. Explique que o histórico mostra até 200 pontos e que os horários são UTC.
3. Alterne entre as fontes para executar a consulta em cada banco.
4. Vá a **Uma leitura, dois bancos**. Digite **500001** e clique em **Comparar agora**.
5. Confira **Resultados equivalentes**. A leitura tem sensor 1, temperatura **30,59 °C**, umidade **45,73%** (exibida como 45,7% na tela) e instante **02/11/2026 17:40 UTC**.
6. Explique que os dois tempos exibidos são amostras ao vivo. As medianas do experimento repetido ficam na seção seguinte; não se conclui que um banco é sempre mais rápido a partir de uma única chamada.

Na massa padrão e no período completo, os indicadores são: **1.000.000 leituras**, **1.000 sensores**, temperatura média **30,00 °C** e **356.430 leituras acima de 32 °C**. Filtros alteram esses valores.

Captura da comparação executada para a entrega: [tela da demonstração](../results/evidencias/comparacao_17_11.png).

## Exemplos Redis em cerca de dois minutos

```bash
make exemplos-redis
```

| Arquivo | Parte a mostrar | Explicação e resultado |
|---|---|---|
| [01_crud_hash.py](../exemplos/redis/01_crud_hash.py) | `executar`: `hset`, `hgetall`, `delete` | Uma leitura é um hash. Temperatura passa de 2850 para 3300: 28,50 °C para 33,00 °C. Ao final, `excluida` é `true`. |
| [02_historico_sensor.py](../exemplos/redis/02_historico_sensor.py) | `zadd` e `zrangebyscore` | Um sorted set indexa IDs por timestamp. O intervalo inclusivo de 00:05 a 00:10 retorna IDs 2 e 3. |
| [03_cache_ttl.py](../exemplos/redis/03_cache_ttl.py) | `set(..., ex=2)`, `get` e `ttl` | Resumo JSON didático: ausência, acerto e expiração em aproximadamente dois segundos. A massa principal não expira. |

Os três programas funcionam mesmo sem a massa principal. Cada execução usa um UUID nas chaves `demo:` e remove apenas as suas chaves. A sequência didática de comandos não implementa todas as regras e garantias da API completa.

## O mesmo CRUD em PostgreSQL e Redis

```bash
make crud
```

O programa [scripts/crud_demo.py](../scripts/crud_demo.py) cria uma leitura temporária, lê, atualiza de **29 para 34 °C**, lê novamente e exclui. Faz isso nas duas fontes e confere os resultados. A saída inclui `passed: true` nas duas operações e `equivalent: true`. Também grava [results/crud.json](../results/crud.json).

| Operação | PostgreSQL | Redis |
|---|---|---|
| Criar | `INSERT INTO readings (...) VALUES (...)` | `HSET iot:reading:<id> ...`, com manutenção dos índices |
| Ler por ID | `SELECT * FROM readings WHERE id=%s` | `HGETALL iot:reading:<id>` |
| Atualizar | `UPDATE readings SET ... WHERE id=%s RETURNING *` | Script Lua atualiza hash, sorted set e índice de unicidade |
| Excluir | `DELETE FROM readings WHERE id=%s RETURNING *` | Script Lua remove o hash e as referências nos índices |

Mostre [PostgresStore](../app/store.py) para o SQL e, no mesmo arquivo, `RedisStore.point` e `WRITE_LUA` para a implementação Redis. O PostgreSQL usa FK e `UNIQUE(sensor_id, ts)`; no Redis a aplicação verifica o sensor e mantém `iot:unique:<sensor_id>`. A API não oferece uma transação distribuída entre os dois bancos.

## Texto de apoio aos slides

1. **Vantagens e limitações:** Redis oferece estruturas em memória e acesso por chave; exige cuidado com RAM e índices manuais. PostgreSQL oferece SQL, relações e transações. Memcached é a referência teórica de cache temporário.
2. **Definição do problema:** campus simulado com mil sensores em dez locais, amostragem a cada cinco minutos, busca por ID, histórico por período e alertas acima de 32 °C.
3. **Modelo relacional:** `sensors` se relaciona 1:N com `readings`. Identificadores, FK, unicidade e índices sustentam as consultas. `ts` é um inteiro com segundos UTC, e temperatura/umidade usam centésimos.
4. **Modelo Redis:** hashes guardam objetos; `iot:sensors` lista IDs; sorted sets ordenam leituras por instante; o hash de unicidade evita repetir sensor e horário. As setas do diagrama representam referências lógicas.
5. **Comparação:** o SQL expressa relações e agregações; Redis exige comandos e manutenção explícita das estruturas. Scripts Lua são atômicos, mas não oferecem rollback geral como uma transação SQL. Nesta implementação há uma instância de cada banco.
6. **Redis na prática:** explique HSET, HGETALL e DEL. A chave abreviada no slide é didática; os scripts executáveis usam prefixos exclusivos.
7. **Exemplos no GitHub:** abra a pasta `exemplos/redis`, execute os programas e mostre os resultados. Para comparar o CRUD completo dos dois bancos, execute `make crud`.

## Conferir os exemplos

```bash
make test-exemplos-redis
make test
```

São três testes dos exemplos e onze testes da aplicação, todos com bancos reais. Verificam valores, ordenação/limites do histórico, expiração, limpeza e os contratos principais da aplicação.
