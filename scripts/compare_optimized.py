"""Reutiliza as massas isoladas existentes; não recarrega nem apaga volumes."""
import argparse
from scripts.compare_scales import ROOT, run


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--records',type=int,choices=(1000000,5000000),default=5000000)
    parser.add_argument('--repetitions',type=int,default=10)
    parser.add_argument('--warmup',type=int,default=2)
    args=parser.parse_args()
    if not (ROOT/f'results/escala/{args.records}/load.json').exists():
        parser.error('Cenário ainda não existe. Prepare as massas com make escala primeiro.')
    try:
        run(args.records,'up','-d','--build','--wait')
        run(args.records,'exec','-T','app','python','-m','scripts.optimize_redis')
        run(args.records,'exec','-T','app','python','-m','scripts.benchmark_optimized',
            '--repetitions',str(args.repetitions),'--warmup',str(args.warmup))
    finally:
        run(args.records,'stop')


if __name__=='__main__': main()
