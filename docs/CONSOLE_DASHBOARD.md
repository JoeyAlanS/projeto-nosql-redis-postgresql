# Operações e console na dashboard

Abra **http://localhost:8000/#operations**. Se os serviços estiverem parados ou o código foi atualizado, rode `make up` na pasta do projeto e recarregue a página.

O painel faz requisições reais à API FastAPI, que acessa os bancos locais da base principal de 1 milhão de leituras. Os bancos isolados de 1 e 5 milhões usados nos testes de carga não são modificados por este painel.

## Comparação visual e mudanças pela dashboard

O laboratório aparece no início da página. Os dois cartões consultam o mesmo ID: à esquerda, a linha de `readings` no PostgreSQL; à direita, o hash `iot:reading:<id>` do Redis. Temperatura e umidade aparecem nas mesmas unidades, e uma faixa amarela destaca campos diferentes. Os valores armazenados também ficam visíveis, como `2850` para 28,50 °C.

Para **enviar uma alteração sua**, consulte o ID e clique em **Editar no PostgreSQL** ou **Editar no Redis**. O formulário abre com os valores realmente consultados. Mude temperatura, umidade, sensor ou instante, confira o destino e clique em **Executar operação**. O painel faz novas consultas aos dois bancos e exibe **antes → depois**, inclusive no banco que não recebeu escrita. O console mantém a requisição, a resposta e as capturas para exportação.

Uma leitura ausente (HTTP 404) aparece como ausente. Se a consulta falhar, o painel informa que não foi possível confirmar a leitura; não trata falha de rede como exclusão. O resultado da escrita fica separado do estado consultado depois: isso torna visível uma falha parcial mesmo quando os valores acabam iguais.

### Demonstração em quatro botões

1. **Criar nos dois:** cria a leitura #9000000010 com 28,50 °C e 55% em ambos.
2. **Mudar só Redis:** grava 33,50 °C apenas no Redis. PostgreSQL permanece em 28,50 °C; o campo de temperatura fica destacado.
3. **Igualar valores:** grava 28,50 °C e 55% nos dois bancos para demonstrar equivalência novamente.
4. **Excluir exemplo:** remove somente a leitura #9000000010 dos dois bancos. O painel confirma sua ausência com novas consultas.

Esses botões executam as operações indicadas. Já os três cartões “Comparar uma leitura”, “Experimentar o CRUD” e “Resumir 10 mil leituras” apenas preenchem o formulário e aguardam **Executar operação**.

A divergência demonstra **cópias independentes**, não um defeito do Redis ou PostgreSQL. Não existe sincronização automática neste projeto. Os bancos representam o mesmo dado lógico em estruturas distintas. As capturas antes/depois são consultas independentes e podem observar escritas de outra sessão; não são controle de concorrência ou uma transação conjunta.

### Comparar desempenho visualmente

Na seção **1 milhão × 5 milhões**, selecione a massa para ver barras das medianas salvas de Q1 (ID), Q2 (histórico) e Q3 (resumo). Cada cartão usa a mesma escala para os dois bancos, iniciando em zero; a escala muda entre consultas. Valores e unidade em milissegundos permanecem visíveis. São as 30 repetições do ensaio anterior, e trocar a seleção não gera uma nova carga.

## Uso básico

1. Escolha **PostgreSQL**, **Redis** ou **Ambos** em Banco de destino.
2. Escolha a operação: consultar por ID, criar, atualizar, excluir, histórico ou resumo.
3. Preencha os campos ou clique em um dos três exemplos. O exemplo apenas preenche; não executa sozinho.
4. Confira **Requisição e caminho no banco**, que apresenta a rota HTTP, o corpo JSON e uma explicação do SQL ou script Lua correspondente.
5. Clique em **Executar operação**. Cada banco mostra seu código HTTP, tempo e JSON retornado.

Em uma consulta por ID, **Preparar edição no PostgreSQL/Redis** carrega os cinco campos da resposta no formulário. Edite e execute para salvar. Atualizar substitui todos os campos da leitura pelos valores informados. O preenchimento por uma consulta anterior é uma fotografia daquele instante, sem controle de concorrência ou atualização automática.

Temperatura e umidade são digitadas em °C e %. O painel converte para inteiros de centésimos: 28,50 °C vira `temperature_centi: 2850`. As datas são explicitamente UTC e convertidas em segundos Unix. O sensor deve existir; a massa atual tem sensores de 1 a 1000.

Em **Ambos**, são duas requisições em sequência: primeiro PostgreSQL, depois Redis. Não há transação distribuída, sincronização contínua ou reversão automática. Se um concluir e o outro falhar, o console mostra **Resultado parcial** e preserva os dois retornos. Isso permite visualizar exatamente onde ocorreu o problema.

## Roteiro de demonstração do problema

| Passo | Ação no painel | Retorno esperado |
|---|---|---|
| 1 | Clique em **Comparar uma leitura** e execute | ID 500001, HTTP 200 nos dois bancos e resultados equivalentes |
| 2 | Clique em **Experimentar o CRUD** e execute Criar em Ambos | ID 9000000010, sensor 1, 18/11/2026 12:00 UTC, 28,50 °C e 55%; HTTP 201 nos dois |
| 3 | Repita Criar | HTTP 409: ID ou par sensor/instante já existe |
| 4 | Selecione Redis, Atualizar, temperatura 33,50 °C; execute | Redis armazena 3350; PostgreSQL continua com 2850 |
| 5 | Selecione Ambos, Consultar por ID, mantendo 9000000010 | O console destaca `$.temperature_centi: PostgreSQL 2850 → Redis 3350` |
| 6 | Selecione Ambos, Excluir; execute | Cada banco retorna a versão excluída; podem diferir devido ao passo 4 |
| 7 | Consulte o mesmo ID em Ambos | HTTP 404 nos dois bancos: registro removido |

O ID do exemplo fica fora da massa original. As escritas são persistidas no banco selecionado; ao terminar, exclua esse ID em ambos. A demonstração não é uma operação de cache: os bancos têm representações independentes dos dados.

Para demonstrar uma **falha parcial**, com a leitura criada apenas no PostgreSQL, execute Criar em Ambos: PostgreSQL retorna 409 e Redis retorna 201. Isso mostra por que não se pode presumir que as duas escritas confirmam ou falham juntas. Consulte ambos e exclua a leitura de teste ao terminar.

## Trabalhar com as 10 mil leituras

Clique em **Resumir 10 mil leituras** e execute. O formulário usa:

- Início: **01/11/2026 00:00:00 UTC** (`1793491200`).
- Fim: **01/11/2026 00:45:00 UTC** (`1793493900`), inclusivo.
- Sensor vazio: todos os sensores.

Na massa original, as duas respostas contêm `count: 10000`, `sensors: 1000`, `alerts: 3522`, `temperature_sum: 29932800` e `humidity_sum: 54385000`. O resultado é calculado no banco ao clicar, não é preenchido com valores salvos.

Para ver as linhas, escolha **Histórico do sensor**, sensor **1**, mesmo intervalo e limite **20**: são 10 leituras, IDs `1, 1001, 2001, …, 9001`. Cada sensor tem uma medição a cada cinco minutos. O limite máximo por consulta de histórico é 1000; o resumo pode agregar todas as leituras do período sem retornar cada linha individualmente.

## Como interpretar o console

| Informação | Significado |
|---|---|
| HTTP 200 | Consulta, atualização ou exclusão concluída |
| HTTP 201 | Leitura criada |
| HTTP 404 | Leitura não encontrada naquele banco |
| HTTP 409 | ID ou par sensor/instante duplicado |
| HTTP 422 | Campo inválido ou sensor inexistente |
| HTTP 500/503 | Falha da API ou indisponibilidade; confira `make logs` e `docker compose ps` |
| Sem resposta HTTP | Não houve confirmação. Consulte o registro antes de repetir uma escrita |
| Resultados equivalentes | Os dados retornados são iguais; tempos e ordem das propriedades JSON são desconsiderados |
| Resultados diferentes | O console lista até 20 caminhos divergentes e mantém os dois retornos completos |
| Validação local | A entrada foi rejeitada antes do envio; nenhuma operação foi executada |

**Ponta a ponta** mede uma requisição no navegador, incluindo HTTP, API, abertura da conexão e leitura do corpo de resposta. Histórico e resumo também mostram o tempo do trecho de consulta medido no backend, que exclui abertura da conexão e seleção dos sensores. Estes tempos de uma única execução não substituem as medianas/p95 do benchmark e não constituem teste de carga concorrente.

A prévia SQL/Lua é explicativa e não um editor de comandos arbitrários. Ela segue `app/store.py`: PostgreSQL usa SQL parametrizado; Redis usa `HGETALL` para busca pontual e scripts Lua para manter hashes, índice temporal e unicidade nas escritas. O resumo Redis percorre as leituras e bloqueia outras operações durante seu script; ampliar o intervalo pode aumentar bastante o tempo.

As últimas **30 execuções** ficam na memória da aba. **Baixar JSON** exporta as requisições, respostas, horários, tempos e comparações. **Limpar console** limpa apenas esse histórico visual. Recarregar a página também apaga o histórico, mas mantém os dados dos bancos.

## Código e verificação

- `web/index.html`: campos, exemplos e roteiro visível.
- `web/operations.css`: formulário responsivo e console.
- `web/operations-core.mjs`: validação, conversão de unidades, requisições e comparação estrutural.
- `web/operations.js`: envio real via fetch, demonstração guiada, erros, edição e exportação.
- `web/reading-comparison.mjs`: distingue ausência de erro, compara campos e captura antes/depois.
- `web/reading-view.js` e `web/reading-comparison.css`: cartões visuais, estruturas e transições de valores.
- `app/main.py` e `app/store.py`: API e operações existentes, reaproveitadas sem mudar seu contrato.
- `tests/frontend/*.test.mjs`: 11 testes das rotas/payloads, limites, filtros, comparação, estados desconhecidos, capturas e falhas parciais. Rode `make test-console` com Node 20 ou superior.
- `make test`: testes de integração com PostgreSQL e Redis. Execute com as bases equivalentes, depois de remover a leitura de demonstração; diferenças criadas intencionalmente no roteiro fazem os testes de equivalência falharem.
- `results/console_operacoes.json`: histórico real exportado da interface, com 13 operações cobrindo CRUD, divergência, falha parcial, 404/409/422, histórico e resumo de 10 mil.
- `results/console_validacao.json`: evidências da interface e da limpeza dos dados de demonstração.

Não é necessário instalar Node para usar a dashboard; ele é usado apenas no teste isolado do JavaScript. Os testes de carga e gráficos anteriores permanecem em `results/escala/` e `output/graficos/`.

A verificação desta versão e as operações reais exportadas estão em `results/dashboard/`. Execute `make check` para rodar os 30 testes e a auditoria; finalize a demonstração antes para manter as bases equivalentes.
