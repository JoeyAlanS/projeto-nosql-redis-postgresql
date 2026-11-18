# Conferência do documento com o Projeto 3

Revisão de 18 de novembro de 2026. O escopo acadêmico segue `docs/fontes/Projeto_3_NoSQL_Instrucoes_Atualizadas.pdf`; as datas seguem `docs/fontes/entregáveis-1.pdf`. O pedido de análise técnica detalha como explicar a implementação existente. Os requisitos acadêmicos e as perguntas de investigação são apresentados separadamente abaixo.

## Conteúdo obrigatório e localização

| Exigência do enunciado | Implementação e documentação |
|---|---|
| Paradigma, aplicações e visão geral | `docs/01_pesquisa.md`: chave-valor, Redis escolhido e Memcached como comparação teórica |
| Arquitetura, organização, consultas e escalabilidade | Pesquisa, modelos em `docs/modelos/` e capítulos 2 a 7 da análise técnica; instâncias únicas, sem ensaio de Cluster |
| Mercado, fornecedor, download e licenciamento | Pesquisa e `docs/referencias.md`, com fontes primárias e limites dos relatos do fornecedor |
| Vantagens, limitações e comparação com relacional | `docs/02_modelagem.md`: modelos, associações, SQL/comandos, transações, índices e critérios de escolha |
| Mesmo cenário e modelos dos dois bancos | Telemetria ambiental de sensores; tabelas `sensors`/`readings` e hashes/índices Redis em `app/store.py` |
| CRUD equivalente e consultas da dashboard | API `source=postgres/redis`, scripts Lua, `scripts/crud_demo.py` e testes reais de integração |
| Instalação, geração e carga automatizadas | README, Makefile, Compose, `scripts/load.py` e `scripts/verify.py` |
| Mínimo de 1 milhão de registros lógicos | Base principal com 1.000.000 de leituras em cada banco; um registro significa uma medição de um sensor em um instante |
| Volume recomendado de 5 milhões | Cenários isolados de 1M e 5M em `results/escala/`; não se somam índices ou chaves auxiliares à contagem de leituras |
| Origem, quantidade, esquema, tamanho e carga | Gerador determinístico, CSV canônico, relatórios `load.json`, verificações integrais e `docs/COMPARACAO_1M_5M.md` |
| Três consultas e ao menos dez repetições | Q1 ID, Q2 histórico e Q3 resumo; cinco aquecimentos e 30 medições por consulta e fonte |
| Cenário favorável ao NoSQL com explicação | Leitura por chave; medianas e ensaio HTTP reais, preservando PK e índices PostgreSQL |
| Ambiente, versões, cache, filtros e método | JSONs de benchmark e carga concorrente; conexões reutilizadas no teste direto, conexões por requisição no HTTP |
| Métricas lado a lado e vantagens do relacional | CSVs brutos, seis gráficos Python e comparação; PostgreSQL apresentou menor mediana em Q2 e Q3 |
| Dashboard com dados reais | Indicadores e histórico consultam a API e a fonte selecionada; o laboratório envia CRUD real |
| Ao menos três indicadores e dois filtros | Leituras, média, sensores e alertas; filtros de local, sensor e período |
| Alternância de fonte, tempos e comparação | PostgreSQL/Redis, tempos em ms, consulta pontual lado a lado e visualização dos experimentos salvos |
| Demonstração ao vivo e apresentação de 20 minutos | `docs/roteiro_apresentacao.md`, `docs/ROTEIRO_VSCODE.md`, slides e aplicação local |
| Arquivos da entrega final | Código, README, modelos, scripts, consultas/índices, CSVs de medições, evidências e documentos em `output/` |

## O que os resultados demonstram

A base usada pelas operações ao vivo contém um milhão de leituras por banco. O recorte de 10.000 leituras corresponde a dez instantes dos mil sensores, entre 01/11/2026 00:00 e 00:45 UTC. O seletor de 1M/5M da seção de escalabilidade exibe ensaios registrados; ele não muda a conexão usada pelo CRUD.

O benchmark direto usa 30 amostras por operação e fonte: 180 por volume e 360 nos dois cenários. O ensaio HTTP envia 1.200 requisições por fonte e nível de concorrência, com 1, 4 e 16 clientes: 7.200 por volume e 14.400 nos dois volumes, sem contar aquecimentos. Os resultados comparam consultas corretas, não apenas respostas HTTP 200. Não foi executado teste de estresse até a saturação.

No cenário de 1M, a leitura HTTP com 16 clientes registrou 196,20 respostas corretas/s no PostgreSQL e 522,23 no Redis. Com 5M, foram 199,58 e 479,96 respostas corretas/s. Esses números pertencem aos ensaios salvos, não à revisão documental. As agregações amplas favorecem o PostgreSQL e podem bloquear a instância Redis durante a execução Lua. Os limites de cache, durabilidade e ambiente compartilhado acompanham os resultados no relatório comparativo.

## Correspondência com o pedido de análise técnica

Os capítulos 2 a 6 da análise técnica descrevem as estratégias e seus fluxos; os capítulos 7 a 9 mapeiam as chaves e exemplos de código; os capítulos 10 a 12 explicam testes, medidas e planos; os capítulos 13 e 14 explicam a dashboard e os comandos; os capítulos 15 a 17 registram correções, limites e referências. Cinco diagramas Mermaid representam arquitetura, execução, chaves, testes e dashboard.

O planejamento Redis é a seleção de comandos e scripts pela aplicação. Não há otimizador SQL Redis, fila de buscas, prioridade de tarefas, estados persistidos de consultas ou repetição automática de trabalhos. `iot:load_state` acompanha a carga, e os estados do console pertencem ao navegador. O exemplo TTL é independente da base principal. Essas ausências respondem às perguntas da análise técnica e não são funcionalidades exigidas pelo enunciado acadêmico.

## Evidência atual e evidência histórica

`results/documentation_validation.json` registra a inspeção atual de contagens, catálogo SQL, parâmetros do driver, consultas equivalentes e manifesto. `results/verification.json` registra a comparação integral com o CSV, incluindo os índices Redis. Os ensaios de desempenho preservam suas datas e valores originais. Uma nova verificação não significa que a medição de desempenho foi repetida.

As colunas `sensors.id` e `readings.sensor_id` são `integer`. O psycopg adapta valores Python pequenos como `smallint` e listas desses valores como `smallint[]`; esses casts nos planos não demonstram uma mudança de tipo das colunas. `sql/queries.sql` usa `ANY` com a lista explícita de sensores da massa de 1M; `scripts/explain_queries.py` obtém o plano usando os parâmetros reais da carga atual.

O manifesto descreve a carga original, e não a quantidade após cada CRUD. O carregador revisado publica os mesmos metadados completos no disco e no Redis, sinalizando conclusão após a preparação do relatório. Não há transação distribuída entre PostgreSQL, Redis e arquivo.
