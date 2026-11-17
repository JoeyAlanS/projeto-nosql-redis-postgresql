# Observatório IoT - Projeto 3 de Bancos de Dados NoSQL

Implementação comparativa de telemetria ambiental com **PostgreSQL e Redis**, massa sintética de **1.000.000 de leituras**, CRUD, benchmark e dashboard funcional. A fundamentação inclui Memcached como referência teórica do paradigma chave-valor/cache.

Repositório da entrega: [JoeyAlanS/projeto-nosql-redis-postgresql](https://github.com/JoeyAlanS/projeto-nosql-redis-postgresql).

## Comece pela dashboard

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
make verify
make test
make benchmark
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

`make check` executa os 30 testes atuais (11 de integração, 11 de JavaScript, 3 dos exemplos Redis e 5 das ferramentas de carga) e a auditoria dos resultados. Requer os serviços ativos, Node 20+ para os testes do frontend e as bases equivalentes, sem uma divergência de demonstração em andamento. Node não é necessário para usar a dashboard.

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

O carregador protege a massa existente. Para substituí-la deliberadamente:

```bash
docker compose exec -T app python -m scripts.load --records 1000000 --replace
make verify
make test
make benchmark
```

Para uma experiência opcional com 5 milhões, altere o valor de `--records`. Os resultados entregues usam 1 milhão. Refaça a documentação com os novos números se alterar a massa.

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
