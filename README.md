# Central IoT - Estado atual, alertas e histórico

Implementação comparativa com **PostgreSQL e Redis**, agora centrada no **estado atual de 1.000 sensores e seus alertas**. Cada escrita mantém os indicadores global e local; o Redis consulta hashes prontos e um ranking ordenado. Os dois bancos conservam também **1.000.000 de leituras históricas**, com CRUD, benchmark e dashboard. A fundamentação inclui Memcached como referência teórica do paradigma chave-valor/cache.

Repositório da entrega: [JoeyAlanS/projeto-nosql-redis-postgresql](https://github.com/JoeyAlanS/projeto-nosql-redis-postgresql).

O [relatório completo](output/pdf/Relatorio_Completo_Projeto_3.pdf) reúne os pontos do enunciado e os gráficos de 1M/5M. Consulte também a [análise técnica do código](docs/engenharia/ANALISE_TECNICA_COMPLETA.md) e a [conferência dos requisitos](docs/CONFORMIDADE_TRABALHO.md), revisadas com os bancos reais em 18/11/2026.

## Novo foco: central de estado e alertas

O [guia da central](docs/CENTRAL_ESTADO_ALERTAS.md) explica o modelo, os comandos, a demonstração e a comparação justa. Redis usa leitura direta de hashes e sorted sets; PostgreSQL mantém os mesmos indicadores em tabelas e índices. Não há varredura de sensores em Lua nas consultas da central.

O [resumo das melhorias e rotas em PDF](output/pdf/Resumo_Melhorias_Rotas_Redis_PostgreSQL.pdf), também [editável em Word](output/documentos/Resumo_Melhorias_Rotas_Redis_PostgreSQL.docx), mostra o fluxo HTTP → adaptador → banco → JSON, as mudanças implementadas e os resultados de cada ensaio.

Com a massa já carregada:

```bash
make up
make preparar-central
make test-central
```

Abra **http://localhost:8000/#live** para consultar, alterar e remover estados em um ou ambos os bancos, com retorno JSON. `make benchmark-central` mede os cinco contratos; `make graficos-central` gera o gráfico Python. A central existente é preservada ao preparar novamente.

A central possui 1.000 estados, não um milhão. O milhão permanece no histórico e seus testes de 1M/5M continuam disponíveis. Após a preparação, as operações da central e do histórico são independentes. O [guia](docs/CENTRAL_ESTADO_ALERTAS.md) complementa os PDFs/slides anteriores, que ainda descrevem o experimento histórico.

## Otimização Redis — 19/11/2026

O [diagnóstico de desempenho](docs/DIAGNOSTICO_DESEMPENHO.md) identifica o custo de Lua, dos filtros e do cliente Python. A aplicação usa `hiredis`, seleciona somente os IDs necessários e mostra as fases do tempo no console. Reproduza com `make diagnostico`. Esses ensaios usam a base principal de 1M; os ensaios anteriores de 1M/5M continuam identificados pela revisão medida.

O histórico agora pode usar um sorted set com registros completos; o resumo usa agregados diários mantidos pelo CRUD. Ative com `make otimizar-redis` após `make up`. A dashboard permite escolher original ou otimizado e mostra os novos ensaios em **http://localhost:8000/#optimization**.

Consulte o [guia de otimização, comandos e limites](docs/OTIMIZACAO_REDIS.md) e os [novos resultados medidos](docs/RESULTADOS_OTIMIZACAO.md). Os documentos e PDFs revisados em 18/11 descrevem a versão anterior; esta atualização é seu complemento técnico, com medições separadas. O experimento também inclui PostgreSQL pré-agregado e uma prova RedisTimeSeries de 10 mil registros.

## Laboratório histórico na dashboard

Com os dados já carregados, execute `make up` e abra **http://localhost:8000/#operations**.

- **Compare lado a lado:** uma linha PostgreSQL e um hash Redis, valores nas mesmas unidades e campos divergentes destacados.
- **Envie alterações:** clique em **Editar no PostgreSQL/Redis**, mude os valores e execute. A dashboard consulta ambos novamente e mostra **antes → depois**.
- **Demonstre em quatro passos:** crie o exemplo nos dois bancos, mude só no Redis, iguale os valores e exclua o exemplo.
- **Veja desempenho:** em **http://localhost:8000/#scalability**, alterne entre 1 e 5 milhões para visualizar as medianas reais por consulta.

Consulte o [guia da dashboard e das escritas](docs/CONSOLE_DASHBOARD.md), o [índice de documentos e entregáveis](docs/INDICE.md) e o [roteiro do VS Code](docs/ROTEIRO_VSCODE.md). As escritas são reais, por banco; “Ambos” não é uma transação distribuída.

## Executar

Requisitos: Docker com Compose v2 ou superior, aproximadamente 2 GB de RAM disponíveis para os serviços e 2 GB de disco livre. O computador usado na entrega tem 16 GB de RAM. O frontend usa HTML/CSS/JavaScript local, sem CDN ou instalação de Node.

```bash
make up
make load
make preparar-central
make verify
make test
make test-central
make benchmark
make benchmark-central
```

Abra **http://localhost:8000**. A API interativa está em **http://localhost:8000/docs**. A primeira execução baixa imagens; carga, verificação e benchmark levam alguns minutos. Se a massa já está carregada, basta `make up`. Os dados persistem em volumes Docker.

Sem `make`, execute os comandos equivalentes:

```bash
docker compose up -d --build --wait
docker compose exec -T app python -m scripts.load --records 1000000
docker compose exec -T app python -m scripts.verify
docker compose exec -T app python -m unittest discover -s tests -v
docker compose exec -T app python -m scripts.benchmark --repetitions 30 --warmup 5
```

Os serviços ficam acessíveis apenas no localhost: dashboard 8000, PostgreSQL 55432 e Redis 56379. As credenciais padrão são exclusivamente acadêmicas locais. Copie `.env.example` para `.env` se precisar alterá-las. A rede usa `10.203.17.0/24` para funcionar inclusive em ambientes com os pools automáticos do Docker esgotados. Se houver sobreposição, configure `IOT_SUBNET` com outra sub-rede privada livre.

## Organização e verificação

| Pasta | Conteúdo |
|---|---|
| `app/`, `web/`, `sql/` | API, dashboard e esquema PostgreSQL |
| `scripts/`, `tests/`, `exemplos/` | Carga, verificações, gráficos e exemplos Redis |
| `docs/` | Guias, fundamentação e requisitos fornecidos |
| `results/` | Medições e evidências reproduzíveis; o novo fluxo visual está em `results/dashboard/` |
| `output/` | Documentos, apresentação, gráficos e manifesto da entrega |

`make check` executa 31 testes (11 de integração, 12 de JavaScript, 3 dos exemplos Redis e 5 das ferramentas de carga) e a auditoria dos resultados. Requer os serviços ativos, Node 20+ para os testes do frontend e as bases equivalentes, sem uma divergência de demonstração em andamento. Node não é necessário para usar a dashboard.

`make test-otimizacao` acrescenta 10 testes históricos nos bancos reais. `make test-central` acrescenta 11 testes do novo modelo, após `make preparar-central`, totalizando 52 testes nas três baterias.

`make verify` compara integralmente os dados e índices com o CSV original. `make package` recompõe o ZIP local e seu manifesto. Dados volumosos, ambientes virtuais, caches, credenciais locais e ZIPs gerados ficam fora do Git; os resultados e arquivos finais versionados são evidências do trabalho.

## Entregas

| Prazo informado | Ponto de entrega | Arquivos |
|---|---|---|
| 10/11 | Paradigma e aplicações | `docs/01_pesquisa.md`, PDF original preservado |
| 10/11 | Visão geral do SGBD, fornecedor e licença | `docs/01_pesquisa.md`, `docs/referencias.md` |
| 10/11 | Arquitetura | `docs/01_pesquisa.md`, `docs/02_modelagem.md` |
| 10/11 | Escalabilidade | `docs/01_pesquisa.md`, limitações em `docs/04_experimentos.md` |
| 10/11 | Aplicações reais | `docs/01_pesquisa.md`, fontes primárias |
| 17/11 | Vantagens e desvantagens | `docs/02_modelagem.md` |
| 17/11 | Problema e modelagem nos dois bancos | `docs/02_modelagem.md`, `docs/modelos/`, `sql/schema.sql` |
| 19/11 | Massa volumosa, carga e documentação | `scripts/load.py`, `scripts/verify.py`, `docs/03_dados.md`, `results/` |
| 24/11 | Experimentos válidos e vantagem NoSQL | `scripts/benchmark.py`, `docs/resultados.md`, CSV bruto e planos |
| 24/11 | Dashboard, filtros e comparação de tempos | `web/`, `app/`, `results/evidencias/` |

Os requisitos atualizados também pedem código-fonte, README, CRUD, consultas/índices e slides. Estão em `app/`, `sql/`, `tests/`, `output/apresentacao/` e `docs/roteiro_apresentacao.md`. Os PDFs finais ficam em `output/pdf/`. Um pacote ZIP reúne o projeto para entrega. Os três PDFs fornecidos estão preservados em `docs/fontes/`. A preparação dos arquivos não significa que foram enviados ao sistema da disciplina.

A conferência item a item está em `docs/ENTREGAS.md`. `make package` atualiza o ZIP e o manifesto SHA-256 dos arquivos. A massa compactada é incluída no pacote; o CSV sem compressão pode ser regenerado automaticamente por `make load`.

## Usar o dashboard

1. Selecione local e sensor ou mantenha todos para o resumo geral.
2. Ajuste o intervalo UTC e clique em **Aplicar filtros**.
3. Alterne entre PostgreSQL e Redis para executar novamente as consultas.
4. Veja contagem, média, sensores e alertas e o histórico do sensor indicado no título.
5. Na consulta ao vivo, busque a leitura **500001** para comparar acesso por chave.
6. Confira as medianas do experimento na parte inferior. Uma amostra ao vivo pode oscilar.

Filtros de local/sensor atualizam as consultas imediatamente. O gráfico temporal mostra as primeiras 200 leituras do período. O quadro de benchmark usa o arquivo do experimento real, enquanto indicadores, série temporal e consulta pontual fazem novas consultas às bases.

## CRUD

Para a entrega de **17/11**, a pasta [exemplos/redis](exemplos/redis/README.md) contém três programas curtos: CRUD com hash, histórico com sorted set e cache com TTL. Execute `make up` e `make exemplos-redis`; teste com `make test-exemplos-redis`. Os programas usam chaves `demo:` exclusivas e não dependem da massa principal.

O [guia de demonstração de 17/11](docs/DEMONSTRACAO_17_11.md) explica o que mostrar na tela, quais trechos de código apresentar e como comparar PostgreSQL com Redis. A [revisão do Projeto_Vendas fornecido](docs/REVISAO_PROJETO_VENDAS.md) registra os problemas reproduzidos e as correções necessárias antes de usá-lo como evidência.

Cada operação recebe `source=postgres` ou `source=redis`. Não há transação distribuída. A demonstração abaixo aplica o mesmo CRUD nas duas fontes e limpa os dados de demonstração:

```bash
docker compose exec -T app python -m scripts.crud_demo
```

O atalho equivalente é `make crud`. O resultado esperado é `passed: true` para cada fonte e `equivalent: true` para os registros criados e lidos.

Exemplo HTTP de criação, seguido de leitura, atualização e exclusão. Repita trocando a fonte para exercitar os dois bancos:

```bash
curl -X POST 'http://localhost:8000/api/readings?source=postgres' \
  -H 'Content-Type: application/json' \
  -d '{"id":9000000003,"sensor_id":1,"ts":1794000000,"temperature_centi":2850,"humidity_centi":6100}'
curl 'http://localhost:8000/api/readings/9000000003?source=postgres'
curl -X PUT 'http://localhost:8000/api/readings/9000000003?source=postgres' \
  -H 'Content-Type: application/json' \
  -d '{"id":9000000003,"sensor_id":1,"ts":1794000000,"temperature_centi":3350,"humidity_centi":6100}'
curl -X DELETE 'http://localhost:8000/api/readings/9000000003?source=postgres'
```

Não deixe alterações em apenas uma fonte antes de comparar. `make verify` detecta mudanças em relação ao CSV canônico. Em vez de alterar registros originais, use IDs novos e remova-os depois.

## Reproduzir dados e medições

`data/readings.csv` é gerado automaticamente (sem cabeçalho, ordem em `docs/03_dados.md`). Os números da execução entregue e o SHA-256 ficam em `results/load.json`. A verificação percorre 100% das leituras e índices, em vez de comparar apenas contagens.

O carregador protege a massa existente. Se houver uma central operacional, ele também protege seus estados e recusa `--replace` sozinho. A opção adicional `--replace-live` descarta esses estados e requer `make preparar-central` depois. Para substituir uma massa sem central:

```bash
docker compose exec -T app python -m scripts.load --records 1000000 --replace
make verify
make test
make benchmark
```

A aplicação principal mantém 1 milhão de leituras. Os experimentos de **1 e 5 milhões já foram executados** em projetos Docker isolados, com resultados brutos em `results/escala/`, gráficos e [relatório comparativo](docs/COMPARACAO_1M_5M.md). `make escala` reproduz os dois cenários sem substituir a base principal; exige recursos adicionais e pode levar vários minutos. Selecionar um volume na dashboard exibe as medições salvas desse cenário; os filtros e o CRUD continuam consultando a base principal.

`results/load.json` e `iot:loaded` descrevem a carga original, incluindo tempos e espaço medidos. Não são contadores atualizados após o CRUD. `make verify` conta as leituras reais e compara todos os dados e índices com o CSV; execute sem escritas concorrentes. Novas cargas publicam o mesmo manifesto completo no arquivo e no Redis antes de sinalizar `iot:load_state=complete`.

O benchmark executa 5 aquecimentos e 30 amostras de cada uma das 3 operações por fonte, alternando a ordem. Salva 180 tempos reais, mediana, p95, filtros, hashes de resultados, hardware, versões e planos PostgreSQL. Veja `docs/04_experimentos.md` e `docs/resultados.md` para método, resultados e limitações. Os digests das imagens estão fixados no Compose e no Dockerfile; as dependências Python resolvidas ficam em `results/python-packages.txt`.

## Testes e conferência

`make test` executa 11 testes com os dois bancos reais e registra o resultado em `results/tests.log`. Abrange CRUD, índices, conflitos, campos fora dos limites, filtros vazios e exclusão Redis intercalada com atualização de outra conexão. Execute depois de `make load`; os testes criam e removem apenas um registro de demonstração reservado.

O teste de interface usa Node.js 20 ou superior e Playwright, como dependências opcionais de desenvolvimento:

```bash
npm ci
npx playwright install chromium
make browser
```

No Linux, instale as bibliotecas do navegador se forem solicitadas pelo Playwright. Para usar um Chrome já instalado, defina `CHROME_BIN` com o caminho do executável. O teste verifica as fontes, filtros, consulta por ID, erros de datas, respostas divergentes e layout móvel. Exige a massa padrão de um milhão e o benchmark salvo. Atualiza `results/browser.json` e as capturas.

`make verify` confere todas as leituras e índices após os testes. `make audit` recalcula as estatísticas do CSV e verifica as evidências e o PPTX da entrega. O teste de navegador simula uma resposta divergente para verificar a mensagem da interface; as capturas da entrega usam consultas reais.

As medições do benchmark são um registro da execução identificada em `results/benchmark.json`. Reexecutar testes funcionais não altera essas medições. Ao rodar um novo benchmark, atualize também os relatórios e slides conforme [instruções de autoria](docs/AUTORIA.md).

## Organização

```text
app/                      API, contratos e adaptadores PostgreSQL/Redis
web/                      Dashboard acessível e sem dependências externas
sql/                      Schema, restrições, índices e consultas
scripts/                  Geração, carga, verificação, CRUD e benchmark
tests/                    Testes de integração com os bancos reais
docs/                     Pesquisa, modelos, dados, método e apresentação
data/readings.csv         Massa gerada localmente, fora do controle de versão
results/                  Dados brutos, contagens, hashes, planos e capturas
output/pdf/               Entregas e relatório consolidado
output/apresentacao/      Apresentação editável
```

## Parar e retomar

`make stop` interrompe os serviços e preserva os volumes. `make up` os retoma. Não é necessário recarregar os dados. `docker compose down` remove os contêineres e a rede, mas preserva os volumes. Adicionar `-v` remove a massa persistida e exige uma nova carga.

## Identificação e apresentação

Preencha `docs/identificacao.json` com curso, professor e integrantes. O conteúdo técnico está preparado; a equipe deve personalizar a identificação, ensaiar a demonstração e realizar a apresentação/entrega. O roteiro reserva 8 minutos para conceitos, 8 para demonstração e 4 para conclusões e perguntas.

Os arquivos temporários, ambientes locais, dependências instaladas, CSV gerado e ZIP estão fora do Git. O repositório conserva código, documentação, PDFs, apresentação e evidências necessárias. Para gerar o ZIP com a massa compactada depois de clonar, execute `make load` e `make package`.
