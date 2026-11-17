"""Gráficos Matplotlib dos ensaios reais: valida CSV/JSON e exporta PNG, SVG e PDF."""
import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.ticker import FuncFormatter, MaxNLocator
except ImportError as error:
    raise SystemExit('Instale requirements-graficos.txt no ambiente .venv-graficos; veja docs/GRAFICOS_CARGA.md.') from error

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('postgres', 'redis')
COLORS = {'postgres': '#3269A8', 'redis': '#CC5B48'}
LABELS = {'postgres': 'PostgreSQL', 'redis': 'Redis'}
INK, MUTED, GRID = '#203747', '#61727F', '#DFE5E9'
DATE_LABEL = ''


def br(value, digits=1):
    return f'{value:,.{digits}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def quantile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def same(actual, expected, message):
    if not math.isclose(float(actual), float(expected), rel_tol=1e-10, abs_tol=1e-9):
        raise ValueError(message)


def load_data():
    directory = ROOT / 'results/escala'
    path = directory / 'comparacao.json'
    report = json.loads(path.read_text())
    protocol = report['protocol']
    if (protocol['repetitions'] != 30 or protocol['clients'] != [1, 4, 16]
            or protocol['requests_per_source_per_level'] != 1200):
        raise ValueError('Estes gráficos usam o protocolo da entrega: 30 amostras e 1.200 requisições com 1, 4 e 16 clientes. Adapte os rótulos antes de usar outro protocolo.')
    scenarios = sorted(report['scenarios'], key=lambda scenario: scenario['records'])
    if [s['records'] for s in scenarios] != [1_000_000, 5_000_000]:
        raise ValueError('A comparação deve conter exatamente os cenários de 1M e 5M')
    raw_queries, raw_http, input_paths = {}, {}, [path]
    for scenario in scenarios:
        size = scenario['records']
        folder = directory / str(size)
        load = json.loads((folder / 'load.json').read_text())
        verification = json.loads((folder / 'verification.json').read_text())
        if not scenario['equivalent'] or not verification['all_temporal_and_unique_indexes_verified']:
            raise ValueError('A massa e seus índices precisam estar verificados')
        if verification['checked_readings'] != size or len(set(verification['sha256'].values())) != 1:
            raise ValueError('Contagem ou hashes da verificação divergem')
        if scenario['dataset_sha256'] != load['csv_sha256'] or load['csv_sha256'] != verification['sha256']['csv']:
            raise ValueError('As evidências não representam a mesma massa')
        for source in SOURCES:
            same(scenario['load'][source + '_load_seconds'], load[source + '_load_seconds'], 'Tempo de carga divergente')
        query_path, http_path = folder / 'benchmark_raw.csv', folder / 'concurrent_load_raw.csv'
        queries = list(csv.DictReader(query_path.open()))
        http = list(csv.DictReader(http_path.open()))
        raw_queries[size], raw_http[size] = queries, http
        if len(queries) != 6 * report['protocol']['repetitions']:
            raise ValueError('Número de amostras do benchmark incorreto')
        for query in scenario['queries']:
            code = query['query']
            for source in SOURCES:
                values = [float(row['elapsed_ms']) for row in queries if row['query'] == code and row['source'] == source]
                metric = query['metrics'][source]
                if len(values) != metric['samples'] or any(not math.isfinite(v) or v <= 0 for v in values):
                    raise ValueError('Amostras de consulta inválidas')
                same(statistics.median(values), metric['median_ms'], 'Mediana do benchmark divergente')
                same(quantile(values, .95), metric['p95_ms'], 'p95 do benchmark divergente')
            for repetition in range(1, report['protocol']['repetitions'] + 1):
                pair = [row['result_sha256'] for row in queries if row['query'] == code and int(row['repetition']) == repetition]
                if len(pair) != 2 or pair[0] != pair[1]:
                    raise ValueError('Respostas PostgreSQL/Redis divergentes no benchmark')
        if len(http) != 2 * len(report['protocol']['clients']) * report['protocol']['requests_per_source_per_level']:
            raise ValueError('Número de requisições HTTP incorreto')
        for metric in scenario['concurrent']:
            if metric['errors'] != 0:
                raise ValueError('O ensaio contém falhas HTTP; é necessário adaptar os gráficos e seus rótulos de respostas válidas antes de publicá-los.')
            group = [row for row in http if row['source'] == metric['source'] and int(row['concurrency']) == metric['concurrency']]
            if len(group) != metric['requests'] or len({row['request_index'] for row in group}) != len(group):
                raise ValueError('Grupo HTTP incompleto ou duplicado')
            successes = [float(row['elapsed_ms']) for row in group if row['valid'] == 'True' and row['status'] == '200']
            if len(successes) != metric['successes'] or len(group) - len(successes) != metric['errors']:
                raise ValueError('Contagem de sucessos/erros HTTP divergente')
            if not successes or any(not math.isfinite(v) or v <= 0 for v in successes):
                raise ValueError('Amostras HTTP inválidas')
            same(statistics.median(successes), metric['median_ms'], 'Mediana HTTP divergente')
            same(quantile(successes, .95), metric['p95_ms'], 'p95 HTTP divergente')
            same(len(successes) / metric['wall_seconds'], metric['successful_requests_per_second'], 'Vazão divergente')
        input_paths.extend([query_path, http_path, folder / 'load.json', folder / 'verification.json'])
    return report, scenarios, raw_queries, raw_http, input_paths


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 13, 'axes.titlesize': 16,
        'axes.labelsize': 13, 'xtick.labelsize': 12, 'ytick.labelsize': 12, 'text.color': INK,
        'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.edgecolor': GRID,
        'axes.spines.top': False, 'axes.spines.right': False, 'figure.facecolor': 'white',
        'axes.facecolor': 'white', 'svg.fonttype': 'none', 'pdf.fonttype': 42,
        'savefig.facecolor': 'white'})


def canvas(title, subtitle, index, rows=1, cols=1):
    fig, axes = plt.subplots(rows, cols, figsize=(16, 9), squeeze=False)
    fig.subplots_adjust(left=.075, right=.965, bottom=.20, top=.76, wspace=.28, hspace=.56)
    fig.text(.075, .955, 'OBSERVATÓRIO IoT  /  POSTGRESQL E REDIS', fontsize=10, color=MUTED, weight='bold')
    fig.text(.965, .955, f'{index:02d} / 06', ha='right', fontsize=10, color=MUTED)
    fig.text(.075, .905, title, fontsize=24, weight='bold')
    fig.text(.075, .86, subtitle, fontsize=13, color=MUTED)
    for ax in axes.flat:
        ax.set_axisbelow(True)
        ax.grid(axis='y', color=GRID, linewidth=.8)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: br(value, 0)))
        ax.tick_params(length=0, pad=10)
        ax.spines['left'].set_visible(False)
    return fig, axes


def footer(fig, method, source='results/escala/comparacao.json e CSVs brutos'):
    fig.text(.075, .105, method, fontsize=11, color=MUTED, linespacing=1.5, va='top')
    fig.text(.075, .035, f'Fonte: {source}  |  Ensaios: {DATE_LABEL}  |  Computador compartilhado; resultados locais.', fontsize=9, color=MUTED)


def legend(fig, lines=False, markers=True):
    handles = [Line2D([0], [0], color=COLORS[s], marker=('o' if s == 'postgres' else 's') if markers else None, linewidth=2.5,
                       label=LABELS[s]) if lines else Patch(facecolor=COLORS[s], label=LABELS[s]) for s in SOURCES]
    fig.legend(handles=handles, loc='lower left', bbox_to_anchor=(.068, .81), ncol=2,
               frameon=False, fontsize=12, handlelength=1.8, columnspacing=2)


def grouped_bars(ax, scenarios, values, digits):
    positions = np.arange(2)
    maximum = max(value for source in SOURCES for value in values[source])
    for offset, source in zip((-.19, .19), SOURCES):
        bars = ax.bar(positions + offset, values[source], width=.34, color=COLORS[source], zorder=3)
        ax.bar_label(bars, labels=[br(v, digits) for v in values[source]], padding=8, fontsize=12, color=INK)
    ax.set_xticks(positions, ['1 milhão', '5 milhões'])
    ax.set_xlabel('Leituras armazenadas por banco', labelpad=12)
    ax.set_ylim(0, maximum * 1.24)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))


def load_figure(scenarios):
    fig, axes = canvas('Tempo de carga inicial', 'Inserção dos dados e preparação dos índices  |  Menor é melhor', 1)
    values = {source: [s['load'][source + '_load_seconds'] for s in scenarios] for source in SOURCES}
    grouped_bars(axes[0, 0], scenarios, values, 2)
    axes[0, 0].set_ylabel('Tempo de carga (segundos)', labelpad=14)
    legend(fig)
    footer(fig, 'Uma carga por banco e volume. PostgreSQL inclui COPY, commit e VACUUM ANALYZE.\nRedis inclui hashes, índices e espera do AOF everysec. Geração do CSV medida separadamente.')
    return fig


def query_figure(scenarios):
    fig, axes = canvas('Tempo das consultas com 1 e 5 milhões', 'Medianas de 30 amostras por fonte  |  Escalas próprias por consulta  |  Menor é melhor', 2, cols=3)
    for index, (code, title, divisor, unit) in enumerate((('Q1', 'Q1 · Leitura por ID', 1, 'ms'),
            ('Q2', 'Q2 · Histórico: 200 leituras', 1, 'ms'), ('Q3', 'Q3 · Resumo completo', 1000, 's'))):
        ax = axes[0, index]
        values = {source: [next(q for q in s['queries'] if q['query'] == code)['metrics'][source]['median_ms'] / divisor
                           for s in scenarios] for source in SOURCES}
        grouped_bars(ax, scenarios, values, 3)
        ax.set_title(title, loc='left', pad=18)
        ax.set_ylabel(f'Mediana ({unit})', labelpad=10)
        if code == 'Q1':
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: br(v, 2)))
    legend(fig)
    footer(fig, 'Conexões reutilizadas; inclui driver, rede e leitura da resposta. Exclui HTTP e criação de conexão.\nQ1 retorna uma leitura; Q2 limita a 200; Q3 processa o volume completo. Não compare alturas entre painéis.')
    return fig


def concurrent_series(scenario, source, metric):
    rows = sorted((m for m in scenario['concurrent'] if m['source'] == source), key=lambda m: m['concurrency'])
    return [m['concurrency'] for m in rows], [m[metric] for m in rows]


def line(ax, scenario, source, metric, digits):
    x, y = concurrent_series(scenario, source, metric)
    ax.plot(x, y, color=COLORS[source], marker='o' if source == 'postgres' else 's',
            linewidth=2.5, markersize=8, markeredgecolor='white', markeredgewidth=1, zorder=3)
    for xx, yy in zip(x, y):
        offset, alignment = (0, 9), 'center'
        if metric.endswith('_ms'):
            offset, alignment = ((-7, 10), 'right') if source == 'postgres' else ((7, -12), 'left')
        ax.annotate(br(yy, digits), (xx, yy), xytext=offset, textcoords='offset points',
                    ha=alignment, fontsize=11, color=COLORS[source], weight='bold')
    ax.set_xticks([1, 4, 16])
    ax.set_xlim(-.5, 18)
    ax.set_xlabel('Clientes simultâneos', labelpad=10)


def throughput_figure(scenarios):
    fig, axes = canvas('Vazão da aplicação sob carga', 'Leitura por ID via HTTP  |  Mais respostas corretas por segundo é melhor', 3, cols=2)
    maximum = max(m['successful_requests_per_second'] for s in scenarios for m in s['concurrent'])
    for scenario, ax in zip(scenarios, axes.flat):
        for source in SOURCES:
            line(ax, scenario, source, 'successful_requests_per_second', 1)
        ax.set_title(f"{scenario['records'] // 1_000_000} {'milhão' if scenario['records'] == 1_000_000 else 'milhões'} de leituras", loc='left', pad=18)
        ax.set_ylim(0, math.ceil(maximum * 1.2 / 100) * 100)
        ax.set_ylabel('Respostas corretas por segundo', labelpad=14)
    legend(fig, lines=True)
    footer(fig, '1.200 requisições por fonte e nível; cada cliente espera a resposta antes da próxima requisição.\nInclui HTTP, API e conexão ao banco. 14.400 respostas válidas e zero erros nos dois tamanhos; ensaio curto.')
    return fig


def latency_figure(scenarios):
    fig, axes = canvas('Latência da aplicação sob carga', 'Mediana e percentil 95 das respostas HTTP  |  Menor é melhor', 4, rows=2, cols=2)
    fig.subplots_adjust(bottom=.20, top=.74, hspace=.66)
    for row, (metric, label) in enumerate((('median_ms', 'Mediana'), ('p95_ms', 'p95'))):
        maximum = max(m[metric] for s in scenarios for m in s['concurrent'])
        for col, scenario in enumerate(scenarios):
            ax = axes[row, col]
            for source in SOURCES:
                line(ax, scenario, source, metric, 1)
            ax.set_title(f"{label} · {scenario['records'] // 1_000_000}M leituras", loc='left', pad=13, fontsize=14)
            ax.set_ylabel('Tempo de resposta (ms)', labelpad=12)
            ax.set_ylim(0, math.ceil(maximum * 1.3 / 20) * 20)
    legend(fig, lines=True)
    footer(fig, 'Mesmos níveis de clientes e escalas iguais entre os dois volumes em cada linha.\nO p95 é um percentil das respostas corretas, não um intervalo de confiança nem uma garantia de capacidade.')
    return fig


def distribution_figure(scenarios, raw_queries):
    fig, axes = canvas('Dispersão das consultas de banco', 'Cada ponto representa uma das 30 amostras reais  |  Todas as amostras incluídas', 5, cols=3)
    rng = np.random.default_rng(42)
    for ax, code, title, divisor, unit in zip(axes.flat, ('Q1', 'Q2', 'Q3'),
            ('Q1 · Leitura por ID', 'Q2 · Histórico: 200 leituras', 'Q3 · Resumo completo'), (1, 1, 1000), ('ms', 'ms', 's')):
        groups, source_order = [], []
        for scenario in scenarios:
            for source in SOURCES:
                groups.append([float(r['elapsed_ms']) / divisor for r in raw_queries[scenario['records']]
                               if r['source'] == source and r['query'] == code])
                source_order.append(source)
        box = ax.boxplot(groups, positions=range(4), widths=.55, patch_artist=True, showfliers=False,
                         medianprops={'color': INK, 'linewidth': 1.8},
                         whiskerprops={'color': MUTED}, capprops={'color': MUTED})
        for index, (patch, source, values) in enumerate(zip(box['boxes'], source_order, groups)):
            patch.set_facecolor(COLORS[source]); patch.set_alpha(.30); patch.set_edgecolor(COLORS[source])
            ax.scatter(index + rng.uniform(-.12, .12, len(values)), values, color=COLORS[source], s=17, alpha=.65, zorder=3)
        ax.set_xticks(range(4), ['PG\n1M', 'Redis\n1M', 'PG\n5M', 'Redis\n5M'])
        ax.set_title(title, loc='left', pad=18)
        ax.set_ylabel(f'Tempo de consulta ({unit})', labelpad=10)
        ax.set_ylim(0, max(max(g) for g in groups) * 1.15)
        if code == 'Q1':
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: br(v, 2)))
    legend(fig)
    footer(fig, 'Caixa: percentis 25 e 75; linha: mediana; bigodes: até 1,5 vez o intervalo interquartil.\nOs pontos incluem os extremos; o deslocamento horizontal apenas evita sobreposição. Escalas próprias por consulta.')
    return fig


def ecdf_figure(scenarios, raw_http):
    fig, axes = canvas('Distribuição da latência com 16 clientes', 'Curva acumulada empírica  |  Mais à esquerda significa menor latência', 6, cols=2)
    limit = math.ceil(max(float(r['elapsed_ms']) for rows in raw_http.values() for r in rows if int(r['concurrency']) == 16) / 20) * 20
    for scenario, ax in zip(scenarios, axes.flat):
        for source in SOURCES:
            values = np.sort([float(r['elapsed_ms']) for r in raw_http[scenario['records']]
                              if r['source'] == source and int(r['concurrency']) == 16 and r['valid'] == 'True'])
            cumulative = np.arange(1, len(values) + 1) / len(values) * 100
            ax.step(np.r_[0, values, limit], np.r_[0, cumulative, 100], where='post', color=COLORS[source], linewidth=2.4)
        ax.axhline(95, color=MUTED, linestyle='--', linewidth=.9, alpha=.65)
        ax.text(4, 96.8, '95% das respostas', fontsize=10, color=MUTED)
        ax.set_title(f"{scenario['records'] // 1_000_000}M leituras", loc='left', pad=18)
        ax.set_xlim(0, limit); ax.set_ylim(0, 104)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_xlabel('Tempo de resposta HTTP (ms)', labelpad=12)
        ax.set_ylabel('Respostas acumuladas (%)', labelpad=12)
    legend(fig, lines=True, markers=False)
    footer(fig, '1.200 respostas corretas por curva, sem remover amostras ou cortar a cauda.\nA interseção com 95% aproxima o p95; o valor informado nos relatórios usa interpolação linear.')
    return fig


def main():
    global DATE_LABEL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dpi', type=int, default=240)
    args = parser.parse_args()
    if not 72 <= args.dpi <= 600:
        parser.error('Use DPI entre 72 e 600')
    report, scenarios, raw_queries, raw_http, inputs = load_data()
    DATE_LABEL = datetime.fromisoformat(report['generated_at']).astimezone(ZoneInfo('America/Fortaleza')).strftime('%d/%m/%Y')
    style()
    output = ROOT / 'output/graficos'; output.mkdir(parents=True, exist_ok=True)
    evidence = ROOT / 'results/graficos'; evidence.mkdir(parents=True, exist_ok=True)
    pdf_path = ROOT / 'output/pdf/Graficos_Carga_1M_5M.pdf'
    specifications = [
        ('01_tempo_carga', lambda: load_figure(scenarios)),
        ('02_mediana_consultas', lambda: query_figure(scenarios)),
        ('03_vazao_concorrencia', lambda: throughput_figure(scenarios)),
        ('04_latencia_concorrencia', lambda: latency_figure(scenarios)),
        ('05_distribuicao_consultas', lambda: distribution_figure(scenarios, raw_queries)),
        ('06_distribuicao_http', lambda: ecdf_figure(scenarios, raw_http)),
    ]
    files = []
    with PdfPages(pdf_path, metadata={'Title': 'Gráficos dos testes de carga e volume - Observatório IoT',
                                    'Author': 'Observatório IoT', 'Subject': 'Ensaios locais medidos: 1M e 5M'}) as pdf:
        for name, build in specifications:
            fig = build()
            for extension in ('png', 'svg'):
                path = output / f'{name}.{extension}'
                fig.savefig(path, dpi=args.dpi)
                if extension == 'svg':
                    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')
                files.append(path)
            pdf.savefig(fig)
            plt.close(fig)
            print(f'{name}: PNG e SVG gerados', flush=True)
    files.append(pdf_path)
    archive = ROOT / 'output/Graficos_Carga_1M_5M.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, path.name)
        bundle.writestr('LEIA-ME.txt',
            'Seis gráficos dos ensaios locais de 1 milhão e 5 milhões de leituras.\n'
            'PNG: imagens 16:9 para slides. SVG e PDF: formatos vetoriais.\n'
            'Fonte: 360 medições de consultas e 14.400 requisições HTTP.\n'
            'Código e instruções para gerar novamente:\n'
            'https://github.com/JoeyAlanS/projeto-nosql-redis-postgresql/blob/main/docs/GRAFICOS_CARGA.md\n')
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError('Falha na verificação do ZIP dos gráficos')
    files.append(archive)
    manifest = {'generated_at': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
        'matplotlib': matplotlib.__version__, 'numpy': np.__version__, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'records': [s['records'] for s in scenarios], 'figures': len(specifications), 'png_dpi': args.dpi,
        'benchmark_samples_rechecked': sum(map(len, raw_queries.values())),
        'http_samples_rechecked': sum(map(len, raw_http.values())),
        'raw_medians_p95_and_throughput_match': True,
        'load_trials_per_source_per_size': report['protocol']['load_trials_per_size'],
        'http_errors': sum(m['errors'] for s in scenarios for m in s['concurrent']),
        'inputs': [{'path': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in inputs],
        'outputs': [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
    (evidence / 'manifesto_graficos.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(pdf_path)


if __name__ == '__main__':
    main()
