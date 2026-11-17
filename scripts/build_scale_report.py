"""Gera o complemento Markdown e PDF exclusivamente a partir das medições reais."""
import json
from html import unescape
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, PageBreak, Preformatted

from scripts.build_documents import markdown, styles

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_DATE = ''


def number(value, digits=3):
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Noto', 7)
    canvas.drawString(48, 29, 'OBSERVATÓRIO IoT / COMPARAÇÃO DE VOLUME E CARGA / ' + DOCUMENT_DATE)
    canvas.drawRightString(A4[0] - 48, 29, str(doc.page))
    canvas.restoreState()


def main():
    global DOCUMENT_DATE
    report = json.loads((ROOT / 'results/escala/comparacao.json').read_text())
    DOCUMENT_DATE = datetime.fromisoformat(report['generated_at']).astimezone(ZoneInfo('America/Fortaleza')).strftime('%d/%m/%Y')
    one, five = report['scenarios']
    chapters = []
    introduction = f'''# Comparação real: 1 milhão e 5 milhões

Relatório gerado em 17/11/2026 a partir de ensaios locais; as datas de cada medição estão nos arquivos de evidência. Foram criadas duas bases isoladas: uma com **1.000.000** e outra com **5.000.000 de leituras em cada banco**. A base principal do dashboard continua com um milhão. Os volumes dos cenários continuam locais, separados e preservados após parar os serviços.

## O que significa cada teste

| Teste | O que varia | O que medimos |
|---|---|---|
| Carga inicial | Quantidade a inserir | Segundos para carregar e preparar os dados |
| Volume | 1 milhão ou 5 milhões armazenados | Latência das mesmas três consultas, com um cliente |
| Carga concorrente | 1, 4 e 16 clientes simultâneos | Requisições/s, mediana, p95 e erros de leituras HTTP |
| Estresse | Pressão crescente até ultrapassar a capacidade | Não foi executado; não afirmamos limite máximo |

Ter cinco vezes mais registros não significa ter cinco vezes mais usuários. O primeiro fator altera o tamanho dos dados e índices; o segundo altera a disputa por CPU, conexões e filas. O teste funcional verifica correção; a verificação integral confere todos os registros e índices.

## Carga inicial medida

| Leituras por banco | PostgreSQL (s) | Redis (s) | Geração CSV (s) |
|---|---|---|---|
'''
    for scenario in report['scenarios']:
        load = scenario['load']
        introduction += f"| {number(scenario['records'],0)} | {number(load['postgres_load_seconds'],2)} | {number(load['redis_load_seconds'],2)} | {number(load['generation_seconds'],2)} |\n"
    introduction += f'''
Com 5x mais leituras, o tempo de carga foi multiplicado por **{number(report['load_time_factor_5m_over_1m']['postgres'],2)} no PostgreSQL** e **{number(report['load_time_factor_5m_over_1m']['redis'],2)} no Redis**.

O tempo PostgreSQL inclui COPY com os índices existentes, commit e VACUUM ANALYZE. O Redis cria hashes, sorted sets e o índice de unicidade, faz pipeline em lotes e espera 1,1 s para o AOF everysec. O tempo de geração do CSV é separado. Há uma única carga medida por tamanho; estes fatores descrevem esta execução, sem prova de significância estatística e sem igualar garantias de durabilidade.

## Integridade

As duas massas foram verificadas integralmente: leituras, sensores, índices temporais e unicidade. CSV, PostgreSQL e Redis têm SHA-256 idênticos dentro de cada cenário. O hash de 1 milhão é diferente do de 5 milhões porque representam massas diferentes. São 1.000 sensores em ambos: 1.000 ou 5.000 leituras por sensor, em intervalos de cinco minutos. A massa maior prolonga o período, sem aumentar o número de sensores.
'''
    chapters.append(introduction)
    queries = '''# Consultas: efeito do volume

Cada consulta teve **30 repetições por banco**, após cinco aquecimentos, alternando a ordem das fontes. São 180 amostras por cenário, 360 no total. Cada par de respostas foi comparado integralmente. Conexões são reutilizadas; o tempo inclui driver, rede e materialização, mas não HTTP ou criação de conexão.

| Leituras | Consulta | PG mediana (ms) | Redis mediana (ms) | PG p95 (ms) | Redis p95 (ms) |
|---|---|---|---|---|---|
'''
    for scenario in report['scenarios']:
        for query in scenario['queries']:
            pg, rd = query['metrics']['postgres'], query['metrics']['redis']
            queries += f"| {number(scenario['records'],0)} | {query['query']} | {number(pg['median_ms'])} | {number(rd['median_ms'])} | {number(pg['p95_ms'])} | {number(rd['p95_ms'])} |\n"
    queries += '''
## Como interpretar

- **Q1 - ID:** retorna uma leitura, usando a chave primária no PostgreSQL e um hash no Redis. Aumentar a base não obriga ler todos os registros.
- **Q2 - histórico:** retorna sempre as primeiras 200 leituras do sensor 501. Embora o índice cresça de 1.000 para 5.000 membros por sensor no Redis, o limite de resposta permanece 200. Portanto, esta consulta não lê cinco vezes mais resultados.
- **Q3 - resumo:** agrega todo o período e os mil sensores. Processa efetivamente um ou cinco milhões de leituras. Seu custo tende a crescer mais que a consulta por ID; observe o plano e as medições reais.

| Consulta | Crescimento PG (5M / 1M) | Crescimento Redis (5M / 1M) |
|---|---|---|
'''
    for first, last in zip(one['queries'], five['queries']):
        factors = [last['metrics'][s]['median_ms']/first['metrics'][s]['median_ms'] for s in ('postgres','redis')]
        queries += f"| {first['query']} | {number(factors[0],2)}x | {number(factors[1],2)}x |\n"
    queries += '''
Um fator abaixo de 1 significa que a mediana foi menor no cenário maior nesta execução. Isso pode ocorrer por cache, variação da máquina ou plano escolhido; não prova que aumentar o volume deixa o banco mais rápido. Os testes usam cache aquecido, não limpam o cache do SO e compartilham o computador com outros processos. Não foi realizado teste estatístico de significância.

**p95** é o percentil 95 por interpolação das amostras, não o maior tempo nem garantia de latência. Trinta amostras ajudam a ilustrar a distribuição, mas são poucas para caracterizar caudas raras.
'''
    chapters.append(queries)
    concurrent = f'''# Carga: clientes simultâneos

Foram executadas **{report['protocol']['requests_per_source_per_level']} requisições por fonte e nível**, com 1, 4 e 16 clientes. Cada cliente envia a próxima requisição após receber a anterior, sem pausa artificial. As mesmas leituras, distribuídas da primeira à última ID, foram consultadas nas duas fontes.

| Leituras | Banco | Clientes | Sucessos/s | Mediana (ms) | p95 (ms) | Erros |
|---|---|---|---|---|---|---|
'''
    for scenario in report['scenarios']:
        for metric in sorted(scenario['concurrent'], key=lambda m: (m['concurrency'], m['source'])):
            concurrent += f"| {number(scenario['records'],0)} | {'PG' if metric['source']=='postgres' else 'Redis'} | {metric['concurrency']} | {number(metric['successful_requests_per_second'],1)} | {number(metric['median_ms'])} | {number(metric['p95_ms'])} | {metric['errors']} |\n"
    concurrent += '''
## O que está sendo medido

O caminho é cliente HTTP, FastAPI, abertura de conexão ao banco, leitura do registro e resposta JSON. Cada resposta teve seus cinco campos conferidos com o gerador determinístico. Uma resposta rápida com HTTP de erro ou campos incorretos é contada como falha, nunca como sucesso.

Esses números não são diretamente comparáveis aos tempos Q1 da página anterior: aqui o escopo inclui HTTP e abertura de conexão; lá é uma operação de banco com conexão reutilizada. Os dois tamanhos usam o mesmo código HTTP, verificado por hash nas evidências.

## Diferença entre volume, carga e estresse

Volume é o tamanho persistido. Carga é a frequência e simultaneidade de operações. Mais clientes podem aumentar a vazão até surgirem filas; a latência, sobretudo o p95, pode crescer mesmo quando a vazão aumenta. Estresse levaria o sistema além de sua capacidade e observaria falhas e recuperação, o que não foi feito.

Este ensaio é curto e executado uma vez por nível/fonte. Não mede escrita simultânea, Q3 concorrente, pico sustentado durante horas ou capacidade máxima. Q3 usa Lua no Redis standalone e bloqueia outras operações enquanto executa; não extrapole o teste de leitura por ID para esse resumo.
'''
    chapters.append(concurrent)
    for scenario in report['scenarios']:
        plans = f'''# Planos: {number(scenario['records'],0)} leituras

Planos reais do PostgreSQL, capturados com **EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)** fora das amostras cronometradas. A árvore começa no nó final e mostra os nós filhos indentados. Leia o caminho dos filhos até o resultado. Listas ANY extensas estão abreviadas; a versão integral está em plans.json.

'''
        for code, plan in scenario['postgres_plans'].items():
            plans += f"## {code} - PostgreSQL\n\n```text\n{plan['tree']}\nExecution Time: {plan['execution_ms']} ms\n```\n\n"
            plans += f"**Redis:** {scenario['redis_paths'][code]}\n\n"
        plans += '''## Como ler e comparar

`cost` é uma estimativa em unidades do otimizador, não milissegundos. `estimadas` são linhas previstas; `linhas reais/loop` e `tempo/loop` são médias por execução do nó. `loops` indica quantas vezes ele executou. `hit` indica blocos encontrados em shared_buffers; `read` indica blocos carregados para esse buffer e não prova acesso físico ao disco, pois o SO pode ter cache. Os tempos de nós pai incluem trabalho dos filhos: não some todos como se fossem independentes.

No Redis deste projeto não há SELECT nem plano relacional. O caminho acima é o algoritmo implementado em app/store.py. HGETALL tem custo proporcional aos campos do hash (cinco aqui); ZRANGEBYSCORE depende do índice e dos membros retornados. A agregação Lua visita todas as leituras selecionadas e não usa resultado pré-calculado. Os tempos EXPLAIN são do servidor PostgreSQL e não devem ser usados como se fossem os tempos completos do cliente Python ou do HTTP.
'''
        chapters.append(plans)
    commands = '''# Comandos e roteiro de demonstração

Execute no terminal da raiz do projeto. A execução inicial cria volumes independentes e pode levar vários minutos:

```bash
python3 -m scripts.compare_scales
```

Para repetir a verificação, consultas e carga HTTP usando os dados isolados já carregados:

```bash
python3 -m scripts.compare_scales --reuse
```

Para apenas recalcular o resumo dos arquivos existentes, sem consultar os bancos:

```bash
python3 -m scripts.compare_scales --summarize-only
```

Abra http://localhost:8000/#scalability e mostre as três tabelas e os planos expansíveis. Elas usam resultados salvos, sem disparar um teste de cinco milhões ao abrir a página.

## Mostrar ao professor

1. Explique carga inicial, volume e clientes simultâneos.
2. Mostre a confirmação de 1M e 5M em results/escala/<tamanho>/verification.json.
3. Compare os tempos de carga e as medianas Q1, Q2 e Q3.
4. Abra os planos Q1 e Q2: aponte os índices e o limite de 200 resultados.
5. Abra Q3: mostre a quantidade real de linhas processadas e o caminho Lua equivalente.
6. Compare 1, 4 e 16 clientes na tabela de carga HTTP, observando sucessos/s, p95 e erros.
7. Conclua usando a operação medida: a tecnologia mais rápida pode mudar conforme a consulta e a fronteira de medição.

## Arquivos e comandos diretos dos bancos isolados

O cenário de 1M usa projeto Docker iot-escala-1000000 e sub-rede 10.203.18.0/24; o de 5M usa iot-escala-5000000 e 10.203.19.0/24. As sub-redes podem precisar de ajuste em outro computador. Não há portas publicadas. Consulte o guia docs/TESTES_CARGA_1M_5M.md para entrar em cada cenário e repetir EXPLAIN ou os comandos Redis.

Cada pasta results/escala/1000000 e results/escala/5000000 contém load.json, verification.json, benchmark.json, benchmark_raw.csv, plans.json, plans.txt, concurrent_load.json e concurrent_load_raw.csv. O resumo é results/escala/comparacao.json. As tabelas do dashboard e este documento vêm dessas evidências, não de números estimados.

## Fontes técnicas

- PostgreSQL 17, Using EXPLAIN: https://www.postgresql.org/docs/17/using-explain.html
- Redis HGETALL: https://redis.io/docs/latest/commands/hgetall/
- Redis ZRANGEBYSCORE: https://redis.io/docs/latest/commands/zrangebyscore/
- Redis Lua: https://redis.io/docs/latest/develop/programmability/eval-intro/

Fontes das medições: arquivos brutos e relatórios do repositório; execução local de 17/11/2026.
'''
    chapters.append(commands)
    chapters = [chapter.replace('17/11/2026', DOCUMENT_DATE) for chapter in chapters]
    (ROOT / 'docs/COMPARACAO_1M_5M.md').write_text('\n\n'.join(chapters).rstrip() + '\n')
    story = []
    for index, chapter in enumerate(chapters):
        if index:
            story.append(PageBreak())
        for flowable in markdown(chapter):
            if isinstance(flowable, Preformatted):
                flowable = Preformatted(unescape('\n'.join(flowable.lines)), flowable.style)
            story.append(flowable)
    output = ROOT / 'output/pdf/Comparacao_Carga_1M_5M.pdf'
    SimpleDocTemplate(str(output), pagesize=A4, leftMargin=48, rightMargin=48,
                      topMargin=42, bottomMargin=49, title='Comparação de volume e carga: 1M e 5M',
                      author='Observatório IoT').build(story, onFirstPage=footer, onLaterPages=footer)
    print(output)


if __name__ == '__main__':
    main()
