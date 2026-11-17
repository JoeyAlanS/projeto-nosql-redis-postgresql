# Roteiro de apresentação e demonstração no VS Code

Este roteiro acompanha a apresentação de **14 slides** do Observatório IoT e o repositório [projeto-nosql-redis-postgresql](https://github.com/JoeyAlanS/projeto-nosql-redis-postgresql). A demonstração usa os exemplos de sensores de temperatura e umidade deste repositório. O Projeto_Vendas recebido foi revisado separadamente e não é a base da aplicação demonstrada.

## 1. Preparar o computador antes de apresentar

Nesta instalação, os arquivos estão em:

```text
/home/joey/Documentos/GitHub/trabalho-banco-dados
```

O nome desta pasta local é diferente do nome do repositório novo. É a mesma implementação. Não é necessário clonar outra cópia neste computador para apresentar.

1. Abra o VS Code.
2. Selecione **Arquivo > Abrir Pasta** e escolha a pasta acima. Outra opção é **Arquivo > Abrir Workspace do Arquivo** e selecionar `Observatorio_IoT.code-workspace` na raiz do projeto.
3. No menu **Terminal > Novo Terminal**, abra um terminal integrado. Confira que o caminho termina em `trabalho-banco-dados` e que o arquivo `compose.yaml` aparece no Explorador.
4. Execute `docker compose up -d --build --wait` e depois `docker compose ps`.
5. Verifique que os três serviços aparecem ativos e saudáveis: `app`, `postgres` e `redis`.
6. Abra **http://localhost:8000** e mantenha a apresentação do Canva em outra aba.

Você também pode abrir o projeto pelo terminal do Linux:

```bash
cd /home/joey/Documentos/GitHub/trabalho-banco-dados
code Observatorio_IoT.code-workspace
```

A massa de um milhão de leituras já está carregada nesta instalação. Em um computador novo, clone o repositório com uma conta que tenha acesso, inicie os serviços e execute `docker compose exec -T app python -m scripts.load --records 1000000` uma vez. Depois use `make verify`. Prepare a carga antes da apresentação.

## 2. Como usar o VS Code durante a demonstração

| O que você quer fazer | Ação no VS Code |
|---|---|
| Abrir rapidamente um arquivo | Pressione `Ctrl+P`, digite o caminho, como `exemplos/redis/01_crud_hash.py`, e pressione Enter. |
| Mostrar o código | Clique no arquivo no Explorador à esquerda. |
| Ir a uma linha | Pressione `Ctrl+G`, digite o número e pressione Enter. |
| Abrir o terminal | Use **Terminal > Novo Terminal**. |
| Executar uma demonstração pronta | Use **Terminal > Executar Tarefa**, procure por `IoT:` e selecione uma tarefa. |
| Ler este roteiro formatado | Abra este arquivo e use **Abrir Visualização** no editor Markdown. |
| Ajustar o código depois de estudar | Edite, salve com `Ctrl+S` e execute novamente a tarefa. Mudanças nos scripts exigem reconstruir a imagem com a tarefa de iniciar serviços. |

Os programas rodam com Python **dentro do contêiner `app`**. O terminal do VS Code envia o comando ao Docker. Por isso, o procedimento preparado usa as tarefas e os comandos `docker compose exec`. Não é preciso instalar as bibliotecas Python no computador para esse fluxo.

As tarefas ficam em [.vscode/tasks.json](../.vscode/tasks.json) e funcionam sem o programa Make:

| Tarefa no VS Code | Quando usar |
|---|---|
| `IoT: 0 - Iniciar servicos` | Antes da apresentação e após editar código. |
| `IoT: Status dos servicos` | Para mostrar os três serviços em execução. |
| `IoT: 1 - CRUD Redis` | Primeiro exemplo: hash, criação, leitura, atualização e exclusão. |
| `IoT: 2 - Historico Redis` | Segundo exemplo: consulta por período com sorted set. |
| `IoT: 3 - Cache com TTL` | Terceiro exemplo: validade de dois segundos. |
| `IoT: 4 - CRUD nos dois bancos` | Comparação do mesmo registro em PostgreSQL e Redis. |
| `IoT: 5 - Testar exemplos Redis` | Mostrar os três testes dos exemplos. |
| `IoT: 6 - Testar aplicacao` | Mostrar os onze testes da aplicação principal. |
| `IoT: Parar servicos` | Ao encerrar, preservando os dados. |

## 3. O que falar em cada slide

Sugestão: reserve cerca de **15 a 18 minutos**, incluindo a demonstração. Se o professor pedir somente o conteúdo da entrega de 17/11, comece no slide 8 e apresente os anteriores apenas como contexto.

| Slide | Fala sugerida | O que mostrar |
|---|---|---|
| 1. Capa | “Vamos apresentar o paradigma chave-valor/cache e uma implementação comparativa com Redis e PostgreSQL.” | Tema e integrantes. |
| 2. Introdução | “O acesso chave-valor parte de uma chave que identifica um valor. Redis também oferece estruturas como hashes, sets e sorted sets.” | Conceitos do slide. |
| 3. Diferenças | “No relacional temos tabelas e relacionamentos. No Redis representamos objetos e referências com chaves e estruturas.” | Comparação entre os modelos. |
| 4. Visão geral | “Redis e Memcached fazem parte da discussão teórica. A implementação executada usa Redis e PostgreSQL.” | Identificação das tecnologias. |
| 5. Arquitetura | “Redis trabalha com estruturas em memória. No nosso Compose ativamos AOF com sincronização everysec para persistência.” | Arquitetura. Se perguntarem, abra `compose.yaml`, serviço `redis`. |
| 6. Escalabilidade | “Redis tem recursos de replicação e cluster. Nosso experimento usa uma instância, então não mede um cluster distribuído.” | Conceitos de crescimento e limite do experimento. |
| 7. Aplicações reais | “Os casos apresentados mostram usos das tecnologias no mercado. Nosso estudo usa o cenário sintético de sensores.” | Casos já descritos no slide e fontes da pesquisa. |
| 8. Vantagens e limitações | “Redis facilita o acesso por chave e o uso de estruturas em memória. A aplicação mantém índices e referências. PostgreSQL oferece SQL, relações e transações.” | Vantagens e limites. Memcached permanece como referência teórica. |
| 9. Problema | “Simulamos mil sensores em dez locais, com temperatura e umidade a cada cinco minutos. Queremos consultar IDs, histórico e alertas.” | Fluxo do problema e regra de alerta acima de 32 °C. |
| 10. Modelo relacional | “Um sensor tem várias leituras. A chave estrangeira exige um sensor existente e a restrição UNIQUE impede repetir sensor e instante.” | `sensors`, `readings`, FK e unicidade. |
| 11. Modelo Redis | “Cada objeto fica em um hash. Um sorted set ordena leituras por horário e outro hash mantém a unicidade.” | `iot:sensor:1`, `iot:reading:500001`, índice temporal e `iot:unique:1`. |
| 12. Comparação | “Os dois modelos representam o mesmo problema, mas a implementação das relações e consultas muda. O desempenho depende da operação.” | Diferenças de consultas, índices, transações e persistência. |
| 13. Redis na prática | “Vou mostrar criar, ler, atualizar e excluir uma leitura. Os valores de temperatura usam centésimos.” | Saia do slide e execute o exemplo 1 no VS Code. |
| 14. Exemplos no GitHub | “O repositório contém os três exemplos curtos e o CRUD equivalente nos dois bancos. Vou executar histórico, cache e comparação.” | URL nova, arquivos e comandos. Continue com as demonstrações abaixo. |

Depois dos exemplos, volte ao slide 14 e conclua: “Os dois bancos atendem ao problema. A escolha depende das consultas, dos requisitos de integridade e do custo de manter as estruturas.”

## 4. Demonstração 1: CRUD de uma leitura com hash

Abra [exemplos/redis/01_crud_hash.py](../exemplos/redis/01_crud_hash.py), função `executar`, linhas **8–34** na versão deste roteiro. Use os comentários `CREATE`, `READ`, `UPDATE` e `DELETE` como pontos de referência se as linhas mudarem.

Fale enquanto aponta o código:

1. “O UUID cria uma chave exclusiva desta execução.” Mostre `prefixo` e `chave`.
2. “HSET cria os cinco campos da leitura.” Mostre `banco.hset(..., mapping=...)`.
3. “HGETALL recupera o hash.” Mostre `criada`.
4. “Atualizo só a temperatura, de 2850 para 3300.” Mostre o segundo `hset`.
5. “DEL remove a chave e EXISTS confirma a ausência.” Mostre `delete` e `exists`.
6. “O finally faz a limpeza mesmo se houver erro.” Mostre o bloco final.

Execute a tarefa **`IoT: 1 - CRUD Redis`**, ou digite no terminal:

```bash
docker compose exec -T app python exemplos/redis/01_crud_hash.py
```

Mostre no JSON:

```json
"criada": {"temperature_centi": "2850"},
"atualizada": {"temperature_centi": "3300"},
"excluida": true
```

Esse é um recorte da saída. Os outros campos também aparecem. Explique: **2850 = 28,50 °C**, **3300 = 33,00 °C**, **6100 = 61,00%** de umidade. O cliente Redis retorna textos porque a conexão usa `decode_responses=True`.

### Fazer as quatro operações manualmente, uma por uma

Para mostrar os comandos no próprio Redis, entre no cliente:

```bash
docker compose exec redis redis-cli
```

O prompt muda para o Redis. A partir daí, digite **um comando por vez**:

```redis
HSET demo:manual:joey:leitura:1 id 1 sensor_id 1 ts 1793491200 temperature_centi 2850 humidity_centi 6100
HGETALL demo:manual:joey:leitura:1
HSET demo:manual:joey:leitura:1 temperature_centi 3300
HGETALL demo:manual:joey:leitura:1
DEL demo:manual:joey:leitura:1
EXISTS demo:manual:joey:leitura:1
QUIT
```

O último `EXISTS` deve retornar **0**. `QUIT` volta ao terminal normal. A chave `demo:manual:joey:leitura:1` é exclusiva desta demonstração manual, separada dos dados `iot:*`. Esses comandos mostram o hash isolado. A aplicação completa também mantém índices e valida regras com Lua.

## 5. Demonstração 2: histórico por intervalo

Abra [exemplos/redis/02_historico_sensor.py](../exemplos/redis/02_historico_sensor.py), linhas **15–26**.

Fale: “Crio três leituras, às 00:00, 00:05 e 00:10 UTC. O ID é o membro do sorted set e o horário é o score.” Mostre `zadd`. Depois: “Busco de 00:05 a 00:10 com limites inclusivos.” Mostre `zrangebyscore` e os `hgetall` seguintes.

Execute **`IoT: 2 - Historico Redis`**, ou:

```bash
docker compose exec -T app python exemplos/redis/02_historico_sensor.py
```

Mostre **`"ids": ["2", "3"]`**. As temperaturas retornadas são **2900 e 2950**, ou **29,00 °C e 29,50 °C**. Explique que o sorted set é um índice temporal, enquanto os campos completos ficam nos hashes.

## 6. Demonstração 3: cache com expiração

Abra [exemplos/redis/03_cache_ttl.py](../exemplos/redis/03_cache_ttl.py), linhas **14–25**.

Fale: “Primeiro a chave está ausente. Gravo um resumo JSON com validade de dois segundos, leio o valor e depois confirmo que expirou.” Aponte `get`, `set(..., ex=2)`, `ttl` e a verificação de expiração.

Execute **`IoT: 3 - Cache com TTL`**, ou:

```bash
docker compose exec -T app python exemplos/redis/03_cache_ttl.py
```

Mostre `ausente_antes: true`, o objeto `acerto` e `expirou: true`. O TTL observado pode variar entre 0 e 2 segundos, dependendo do momento da leitura. O resumo é um valor fixo didático, sem consulta ao PostgreSQL. A massa principal não usa TTL.

## 7. Demonstração 4: comparar PostgreSQL e Redis

Abra [scripts/crud_demo.py](../scripts/crud_demo.py), linhas **13–22**. Mostre o laço `for source in ('postgres','redis')` e as chamadas `create`, `point`, `update` e `delete`.

Fale: “Agora aplico as mesmas operações e o mesmo registro aos dois bancos. A temperatura começa em 29 °C, passa para 34 °C e depois a leitura é excluída. O programa verifica os resultados.”

Execute **`IoT: 4 - CRUD nos dois bancos`**, ou:

```bash
docker compose exec -T app python -m scripts.crud_demo
```

Mostre as duas entradas `source`, `passed: true`, a ausência após DELETE e `equivalent: true`. O programa atualiza [results/crud.json](../results/crud.json) com a evidência da execução, por isso esse arquivo pode aparecer como modificado no Git após a demonstração.

Se o professor pedir a implementação, abra [app/store.py](../app/store.py):

| Trecho | O que explicar |
|---|---|
| `PostgresStore.point`, linha 67 | SQL parametrizado: `SELECT * FROM readings WHERE id=%s`. |
| `RedisStore.point`, linha 200 | Acesso ao hash: `hgetall(f"iot:reading:{reading_id}")`. |
| `WRITE_LUA`, linha 155 | Validação do sensor, unicidade e manutenção dos índices Redis em uma execução atômica. |
| `sql/schema.sql` | FK, `UNIQUE(sensor_id, ts)` e índices PostgreSQL. |

Os números são referências da versão deste roteiro. Procure pelos nomes das funções se o arquivo mudar.

## 8. Mostrar o dashboard e os testes

No navegador em **http://localhost:8000**:

1. Mostre o indicador de conexão dos dois bancos.
2. Mostre um milhão de leituras e mil sensores no período completo.
3. Escolha um local e um sensor para mostrar os filtros e o histórico.
4. Na área **Uma leitura, dois bancos**, busque **500001** e clique em **Comparar agora**.
5. Mostre **Resultados equivalentes**, temperatura **30,59 °C**, umidade exibida **45,7%** e horário **02/11/2026 17:40 UTC**. O valor completo da umidade é 45,73%.
6. Explique que o tempo ao vivo é uma amostra. O benchmark salvo usa repetições, e o resultado varia conforme a operação.

No VS Code, execute as tarefas **`IoT: 5 - Testar exemplos Redis`** e **`IoT: 6 - Testar aplicacao`**. Espere a mensagem **OK**, com **3 testes** e **11 testes**, respectivamente. Se a apresentação tiver pouco tempo, mostre as evidências salvas e execute os testes antes do início.

## 9. Se algo não funcionar

| Situação | O que fazer |
|---|---|
| `docker` não encontrado ou sem conexão | Abra/inicie o Docker e confirme `docker version`. |
| `no configuration file provided` | Abra a pasta raiz que contém `compose.yaml`. |
| Serviço `app` não está em execução | Execute a tarefa de iniciar serviços e confira o status. |
| Alterou um arquivo, mas o resultado continua antigo | Salve o arquivo e execute a tarefa de iniciar serviços, que reconstrói a imagem. Os scripts entram por `COPY`, não por montagem de código. |
| `make` não encontrado | Use as tarefas do VS Code ou os comandos Docker deste roteiro. |
| Aplicação informa massa não carregada | Prepare a carga inicial descrita na seção 1. Os exemplos Redis curtos podem rodar sem ela. |
| Tarefas `IoT:` não aparecem | Confirme que abriu a raiz ou o workspace e que `.vscode/tasks.json` está presente. |

Depois da apresentação, execute **`IoT: Parar servicos`** ou `docker compose stop`. Os dados persistem nos volumes e podem ser retomados com a tarefa de iniciar serviços.

## Referências para operar o editor

Os menus de terminal e tarefas seguem a documentação oficial do VS Code: [Terminal Basics](https://code.visualstudio.com/docs/terminal/basics) e [Tasks](https://code.visualstudio.com/docs/debugtest/tasks). Os nomes podem aparecer em inglês como **Terminal > New Terminal** e **Terminal > Run Task**.
