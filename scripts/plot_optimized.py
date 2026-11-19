"""Compara estratégias equivalentes nos dois bancos, usando os novos ensaios."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def main():
    paths=[ROOT/'results/otimizacao/benchmark.json',ROOT/'results/escala/5000000/otimizacao/benchmark.json']
    reports=[json.loads(p.read_text()) for p in paths if p.exists()]
    if not reports: raise SystemExit('Execute o benchmark primeiro')
    pairs=[('Q2','Histórico · índices cobrindo a resposta','postgres_raw','redis_optimized'),
           ('Q3','Resumo · modelos originais','postgres_raw','redis_baseline'),
           ('Q3','Resumo · pré-agregado nos dois','postgres_materialized','redis_optimized')]
    fig,axes=plt.subplots(3,len(reports),figsize=(6.5*len(reports),10),squeeze=False,layout='constrained')
    for col,report in enumerate(reports):
        for row,(code,title,pg,rd) in enumerate(pairs):
            ax=axes[row,col]; query=next(q for q in report['queries'] if q['query']==code)
            values=[query['metrics'][source]['median_ms'] for source in (pg,rd)]
            bars=ax.barh(['PostgreSQL','Redis'],values,color=['#3267a8','#c42537'],height=.5)
            ax.invert_yaxis(); ax.set_xlim(0,max(values)*1.38); ax.grid(axis='x',alpha=.18); ax.set_axisbelow(True)
            for bar,value in zip(bars,values):
                label=f'{value:,.3f}'.translate(str.maketrans(',.','.,'))+' ms'
                ax.text(value+max(values)*.025,bar.get_y()+bar.get_height()/2,label,va='center',fontsize=10)
            volume='1 milhão' if report['records']==1000000 else f'{report["records"]/1e6:g} milhões'
            ax.set_title(f'{volume} · {code}\n{title}',loc='left',fontsize=12,pad=12)
            ax.set_xlabel('Mediana (ms) · menor é melhor · escala própria')
            ax.spines[['top','right','left']].set_visible(False)
    fig.suptitle('Mesmos dados e resultados · comparação por estratégia',fontsize=17,fontweight='bold')
    directory=ROOT/'results/otimizacao'; directory.mkdir(exist_ok=True)
    fig.savefig(directory/'comparacao.png',dpi=160,facecolor='white'); plt.close(fig)
    print(directory/'comparacao.png')


if __name__=='__main__': main()
