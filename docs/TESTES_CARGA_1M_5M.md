# Testes de volume, carga inicial e clientes simultâneos

Este guia complementa [os comandos básicos](COMANDOS_TESTES.md). Os resultados estão na [comparação explicada](COMPARACAO_1M_5M.md), no [PDF](../output/pdf/Comparacao_Carga_1M_5M.pdf) e em `results/escala/`. No dashboard, abra **http://localhost:8000/#scalability**.

## 1. Entender a diferença

| Nome | Pergunta | Variável |
|---|---|---|
| Carga inicial | Quanto demora inserir os registros e preparar índices? | 1 milhão ou 5 milhões inseridos |
| Teste de volume | Como o tamanho da base afeta a mesma consulta? | Registros armazenados; um cliente |
| Teste de carga concorrente | Como o serviço responde com mais clientes? | 1, 4 ou 16 clientes simultâneos |
| Teste funcional | O resultado e as regras estão corretos? | CRUD, filtros, conflitos e validações |
| Teste de estresse | Qual o limite e como o sistema falha e se recupera? | Pressão até ultrapassar a capacidade; não executado |

O milhão da aplicação principal é preservado. Os experimentos usam projetos Docker e volumes próprios, sem portas publicadas. Os arquivos de dados ficam em `data/escala/1000000` e `data/escala/5000000`, ignorados pelo Git. Os resultados ficam em pastas correspondentes em `results/escala/`.

## 2. Executar tudo em uma instalação nova

No terminal do VS Code:

```bash
cd /home/joey/Documentos/GitHub/trabalho-banco-dados
python3 -m scripts.compare_scales
```

O comando carrega, verifica integralmente, mede Q1/Q2/Q3 e executa carga HTTP em cada tamanho, em sequência. Ao terminar cada cenário, para seus contêineres e preserva volumes. Pode levar vários minutos e precisa de RAM/disco para as duas massas, além dos serviços já presentes na máquina. Nesta instalação a execução já foi feita; use os resultados ou a opção `--reuse` abaixo.

O carregador recusa substituir uma massa existente. Se a execução foi interrompida durante a carga, inspecione o cenário antes de repetir; `--reuse` exige o manifesto correspondente e a verificação integral subsequente detecta massa incompleta ou alterada. A execução não usa `--replace` nem modifica os volumes da aplicação principal.

## 3. Repetir consultas e carga HTTP com os bancos já preenchidos

```bash
python3 -m scripts.compare_scales --reuse
```

Isso repete a verificação, benchmark e carga concorrente; não mede novamente a inserção inicial. Substitui os resultados dos ensaios isolados. Para repetir somente um tamanho:

```bash
python3 -m scripts.compare_scales --reuse --records 5000000
```

Para repetir somente os clientes simultâneos nos dois tamanhos já verificados:

```bash
python3 -m scripts.compare_scales --http-only
```

Para apenas reconstruir a comparação dos arquivos salvos, sem executar consultas:

```bash
python3 -m scripts.compare_scales --summarize-only
```

O dashboard lê esse resumo. Para atualizar o PDF e o Markdown com resultados novos, use o gerador `scripts/build_scale_report.py` no ambiente de autoria descrito em `docs/AUTORIA.md` e confira a renderização. As bibliotecas de autoria não fazem parte da imagem da aplicação.

## 4. Selecionar o banco isolado que deseja demonstrar

Escolha **um** dos dois blocos. As variáveis permanecem no terminal e serão usadas nos próximos comandos.

Para **1 milhão**:

```bash
export ESCALA_REGISTROS=1000000
export ESCALA_SUBNET=10.203.18.0/24
projeto_escala=iot-escala-1000000
docker compose -p "$projeto_escala" -f compose.escala.yaml up -d --build --wait
```

Para **5 milhões**:

```bash
export ESCALA_REGISTROS=5000000
export ESCALA_SUBNET=10.203.19.0/24
projeto_escala=iot-escala-5000000
docker compose -p "$projeto_escala" -f compose.escala.yaml up -d --build --wait
```

As sub-redes precisam estar livres; em outro computador, adapte as configurações se houver conflito. Para conferir o cenário selecionado:

```bash
docker compose -p "$projeto_escala" -f compose.escala.yaml ps
```

## 5. Contar os dados reais em cada banco

PostgreSQL:

```bash
docker compose -p "$projeto_escala" -f compose.escala.yaml exec -T postgres psql -U iot -d iot -c "SELECT count(*) AS leituras FROM readings;"
```

Redis:

```bash
docker compose -p "$projeto_escala" -f compose.escala.yaml exec -T redis redis-cli --scan --pattern 'iot:reading:*' | wc -l
```

Esperado: **1000000** ou **5000000**, conforme o cenário escolhido. Uma varredura Redis é mais demorada que consultar apenas uma chave. Não conte durante a carga ou durante testes que gravem dados.

## 6. Demonstrar os três planos de execução

O script abaixo usa a mesma forma SQL das três consultas do benchmark e lê os filtros do manifesto do cenário. `EXPLAIN ANALYZE` executa SELECTs reais. Ele também explica o algoritmo Redis e consulta a quantidade de membros de seus índices.

Q1, leitura por ID:

```bash
docker compose -p "$projeto_escala" -f compose.escala.yaml exec -T app python -m scripts.explain_queries --query Q1
```

Q2, histórico com limite de 200 leituras:

```bash
docker compose -p "$projeto_escala" -f compose.escala.yaml exec -T app python -m scripts.explain_queries --query Q2
```

Q3, resumo do período inteiro:

```bash
docker compose -p "$projeto_escala" -f compose.escala.yaml exec -T app python -m scripts.explain_queries --query Q3
```

Para mostrar os três de uma vez, omita `--query Q1`.

### Como ler o PostgreSQL

- `Index Scan`: usa índice e pode buscar dados da tabela. Q1 normalmente usa `readings_pkey`.
- `Index Only Scan`: o índice cobre os campos; confira `Heap Fetches` para saber se houve acessos à tabela.
- `Seq Scan`: percorre linhas da tabela; pode ser uma escolha apropriada quando a consulta precisa de grande parte dos dados.
- `Sort`, `Aggregate` e nós paralelos: indicam ordenação, agregação e distribuição de trabalho, se aparecerem no plano real.
- `cost`: estimativa do otimizador, não tempo em milissegundos.
- `actual rows` e `loops`: linhas por execução do nó e quantidade de execuções. Tempos e linhas podem ser médias por loop.
- `Buffers: shared hit/read`: blocos encontrados no buffer ou carregados nele. `read` não prova leitura física do disco, pois o SO também tem cache.
- `Execution Time`: tempo de execução no servidor. Não inclui toda a viagem HTTP até o usuário.

Os nós exatos dependem das estatísticas e do cenário. Mostre os planos capturados em `results/escala/<tamanho>/plans.txt`, sem prometer que toda execução terá a mesma árvore. Não some tempos de pais e filhos.

### Como explicar o Redis

Aqui usamos hashes, sorted sets e Lua, sem SELECT ou plano relacional:

| Operação | Caminho Redis |
|---|---|
| Q1 | HGETALL de uma chave; cinco campos |
| Q2 | Lua faz ZRANGEBYSCORE com LIMIT 200 e HMGET dos hashes retornados |
| Q3 | Lua percorre os mil índices e consulta temperatura/umidade de 1M ou 5M hashes |

O custo HGETALL depende dos campos do hash, não de ler toda a base. O histórico depende dos membros do índice e do limite retornado. O resumo cresce com as leituras processadas e bloqueia outras operações da instância durante o script Lua. A carga concorrente demonstrada mede Q1 HTTP, não Q3 concorrente.

## 7. Executar somente o teste de carga concorrente

```bash
docker compose -p "$projeto_escala" -f compose.escala.yaml exec -T app python -m scripts.concurrent_load --requests 1200 --clients 1 4 16
```

São **1.200 requisições por banco e por nível**: 7.200 no cenário escolhido, 14.400 nos dois tamanhos. Cada resposta deve ter HTTP 200 e os mesmos cinco campos esperados. O gerador calcula os valores esperados; os dados retornados são consultados efetivamente nos bancos, não gerados no lugar da consulta.

O laço é fechado: cada cliente espera a resposta antes de enviar a próxima. Os tempos incluem HTTP, API e a conexão ao banco. O benchmark Q1 reutiliza conexão e mede outra fronteira; por isso suas latências não devem ser equiparadas diretamente.

- **Sucessos/s:** respostas corretas divididas pelo tempo total.
- **Mediana:** valor central dos tempos de respostas corretas.
- **p95:** percentil 95 interpolado das amostras corretas.
- **Erros:** HTTP de erro, timeout ou dados divergentes.

É um ensaio curto, com uma execução por nível. Não determina capacidade máxima nem substitui um teste prolongado de produção. Execute sem outros ensaios de banco concorrendo, para reduzir interferência.

## 8. Conferir integridade e parar o cenário

```bash
docker compose -p "$projeto_escala" -f compose.escala.yaml exec -T app python -m scripts.verify
```

Depois:

```bash
docker compose -p "$projeto_escala" -f compose.escala.yaml stop
```

Os dados persistem nos volumes Docker. A aplicação principal é iniciada separadamente com `docker compose up -d --build --wait` na raiz, usando `compose.yaml`.

## Fontes

[PostgreSQL EXPLAIN](https://www.postgresql.org/docs/17/using-explain.html), [Redis HGETALL](https://redis.io/docs/latest/commands/hgetall/), [Redis ZRANGEBYSCORE](https://redis.io/docs/latest/commands/zrangebyscore/) e [Lua no Redis](https://redis.io/docs/latest/develop/programmability/eval-intro/).
