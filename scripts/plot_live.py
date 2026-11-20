"""Gráfico reproduzível das medições do modelo operacional, sem novos ensaios."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def main():
    report=json.loads((ROOT/'results/live/benchmark.json').read_text())
    labels=['Estado do sensor','Resumo global','Resumo do local','Top 20 alertas','Atualizar estado\ne indicadores']
    metrics=list(report['results'].values())
    fig,axes=plt.subplots(1,2,figsize=(12,5),gridspec_kw={'width_ratios':[2,1]},layout='constrained')
    for ax,indices in zip(axes,[range(4),range(4,5)]):
        y=np.arange(len(indices))
        for offset,source,color in [(-.18,'postgres','#2563eb'),(.18,'redis','#d44a42')]:
            values=[metrics[i][source]['median_ms'] for i in indices]
            p95=[metrics[i][source]['p95_ms'] for i in indices]
            bars=ax.barh(y+offset,values,height=.32,color=color,label='PostgreSQL' if source=='postgres' else 'Redis')
            ax.plot(p95,y+offset,'|',color=color,markersize=13)
            ax.bar_label(bars,fmt='%.3f',label_type='center',color='white',fontsize=9)
        ax.set_yticks(y,[labels[i] for i in indices]);ax.invert_yaxis()
        ax.set_xlabel('Milissegundos · menor é melhor');ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
        ax.set_xlim(0,max(metrics[i][s]['p95_ms'] for i in indices for s in ['redis','postgres'])*1.18)
        ax.spines[['top','right']].set_visible(False)
    axes[0].set_title('Consultas diretas');axes[1].set_title('Escrita com manutenção')
    axes[0].legend(loc='lower right')
    fig.suptitle(f"Central IoT · {report['operational_states']:,} estados atuais".replace(',','.'),fontsize=17)
    fig.supxlabel('Barras: mediana · traços: p95 · 30 amostras, 3 aquecimentos, 1 cliente\nConexões reutilizadas. SQL inclui COMMIT; Redis AOF everysec. Garantias de durabilidade diferentes.',fontsize=10)
    fig.savefig(ROOT/'results/live/latency.png',dpi=180)
    plt.close(fig)

if __name__=='__main__':main()
