"""Experimentos completos do roteiro e extensões; execução retomável por cenário."""
from __future__ import annotations
import argparse
from collections import OrderedDict
import csv
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
import time
import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from cache_core import CacheMemory, POLICIES, gerar_padrao_realista, simulacao_monte_carlo
from cache_visualizacao import agregar_mapa

RAM = 1_048_576
HOT = [64,1024,8192,32768,131072,262144,524288,786432,983040]
BASE = (.2,.2,.4)
BLOCKS = (2,4,8,16,32,64,128,256,512)
PROFILES = {"Aleatório": (0.,0.,0.), "Base": BASE, "Temporal alta": (.7,.1,.1), "Espacial alta": (.1,.7,.1), "Regiões quentes altas": (.1,.1,.7)}

@dataclass(frozen=True)
class Scenario:
    id: str
    experiment: str
    label: str
    policy: str = "LRU"
    cache: int = 8192
    block: int = 16
    ways: int = 16
    probs: tuple = BASE
    workload: str = "synthetic"
    value: float = 0
    decay: float = 1/64


def scenarios():
    result = []
    def add(experiment,label,**kwargs):
        result.append(Scenario(f"C{len(result)+1:03}",experiment,label,**kwargs))
    for policy in POLICIES:
        add("01_politicas_fixas",policy,policy=policy)
    for policy in POLICIES[:4]:
        for block in BLOCKS:
            add("01b_politicas_blocos",f"{policy}; {block} B",policy=policy,block=block,value=block)
    for name,probs in PROFILES.items():
        add("02_perfis",name,probs=probs)
    for axis in range(3):
        for value in (0,.2,.4,.6,.8):
            probs = [0.,0.,0.]; probs[axis] = value
            add(f"02_isolada_{axis}",f"{value:.1f}",probs=tuple(probs),value=value)
    for workload in ("phase","pollution","random"):
        for policy in POLICIES:
            add(f"03_robustez_{workload}",policy,policy=policy,workload=workload)
    for lines in (64,128,256,512,1024,2048):
        add("04_linhas",str(lines),cache=lines*16,value=lines)
    for ways in (1,2,4,8,16,32,64,128,256,512):
        add("04_associatividade",str(ways),ways=ways,value=ways)
    for block in BLOCKS:
        add("04_bloco_linhas_fixas",str(block),cache=512*block,block=block,value=block)
    for name,probs in (("Realista",BASE),("Aleatório",(0.,0.,0.))):
        add("06_realista_aleatorio",name,probs=probs)
    for workload in ("fir_canal","fir_amostra"):
        for policy in ("LRU","LRFU"):
            add("07_filtro_fir",f"{dict(fir_canal='Canal externo',fir_amostra='Amostra externa')[workload]}; {policy}",workload=workload,policy=policy)
    for half_life in (8,32,128,512):
        add("08_sensibilidade_lrfu",str(half_life),policy="LRFU",workload="phase",decay=1/half_life,value=half_life)
    return result


def fir_trace(rng, order, samples=128, channels=32, taps=8):
    """FIR multicanal row-major float32. Cada MAC lê x e h; cada saída escreve y.
    Acumulador em registrador; cache unificada de dados, write-allocate idealizado.
    Mesmas referências (multiconjunto) e operações, apenas ordem dos laços muda.
    121*32*(2*8+1) = 65.824 referências por rastro completo.
    """
    xbase = 4096+rng.randrange(64)*64
    hbase = 262144+rng.randrange(64)*64
    ybase = 524288+rng.randrange(64)*64
    pairs = ((n,c) for c in range(channels) for n in range(taps-1,samples)) if order == "fir_canal" else ((n,c) for n in range(taps-1,samples) for c in range(channels))
    trace = []
    for n,c in pairs:
        for k in range(taps):
            trace.extend((xbase+4*((n-k)*channels+c),hbase+4*k))
        trace.append(ybase+4*((n-taps+1)*channels+c))
    return trace


def pattern(s, rng, accesses):
    if s.workload.startswith("fir_"):
        return fir_trace(rng,s.workload)
    if s.workload in ("synthetic","random"):
        probs = s.probs if s.workload == "synthetic" else (0.,0.,0.)
        return gerar_padrao_realista(accesses,RAM,HOT,probs,rng=rng)
    # 32 regiões espaçadas por 512 B => todas competem no mesmo conjunto
    # na configuração 8 KiB, bloco 16 B, 16 vias. Mudam após a metade.
    if s.workload == "phase":
        old = [65536+i*512 for i in range(8)]
        new = [131072+i*512 for i in range(8)]
        trace = []
        for i in range(accesses):
            hot = old if i < accesses//2 else new
            # 80% quentes e 20% varredura no mesmo conjunto: pressão de substituição.
            trace.append(rng.choice(hot) if rng.random()<.8 else 262144+(i%1024)*512)
        return trace
    if s.workload == "pollution":
        hot = [65536+i*512 for i in range(8)]
        return [rng.choice(hot) if rng.random()<.5 else 262144+(i%1024)*512 for i in range(accesses)]
    raise ValueError(s.workload)


def write_csv(path, rows):
    if not rows:
        path.write_text("",encoding="utf-8"); return
    temporary = path.with_suffix(path.suffix+".tmp")
    with temporary.open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    temporary.replace(path)


def summarize(s, records):
    vals = np.array([r["taxa_acerto"] for r in records])
    q1,median,q3 = np.quantile(vals,[.25,.5,.75]); iqr=q3-q1
    low,high=q1-1.5*iqr,q3+1.5*iqr
    std=statistics.stdev(vals) if len(vals)>1 else 0
    row = dict(cenario_id=s.id,experimento=s.experiment,cenario=s.label,algoritmo=s.policy,cache_bytes=s.cache,cache_lines=s.cache//s.block,bloco_bytes=s.block,associatividade=s.ways,conjuntos=s.cache//s.block//s.ways,carga=s.workload,prob_temporal=s.probs[0],prob_espacial=s.probs[1],prob_quente=s.probs[2],lambda_lrfu=s.decay if s.policy=="LRFU" else "",valor=s.value,n=len(vals),acessos=records[0]['acessos_cpu'],media=float(vals.mean()),desvio_padrao=float(std),variancia=float(std**2),mediana=float(median),q1=float(q1),q3=float(q3),minimo=float(vals.min()),maximo=float(vals.max()),limite_outlier_inferior=float(low),limite_outlier_superior=float(high),n_outliers=int(sum((vals<low)|(vals>high))))
    return row, [dict(cenario_id=s.id,experimento=s.experiment,cenario=s.label,**r) for r in records if r['taxa_acerto']<low or r['taxa_acerto']>high]


def paired_comparisons(suite, data, runs, seed):
    """IC bootstrap pareado, bilateral 95%, 5.000 reamostragens; exploratório."""
    comparisons=[]
    def pair(a,b,label):
        av={r['repeticao']:r['taxa_acerto'] for r in data[a.id]}
        bv={r['repeticao']:r['taxa_acerto'] for r in data[b.id]}
        assert av.keys()==bv.keys()
        delta=np.array([av[k]-bv[k] for k in sorted(av)])*100
        rng=np.random.default_rng(seed+len(comparisons))
        boot=delta[rng.integers(0,len(delta),size=(5000,len(delta)))].mean(axis=1)
        lo,hi=np.quantile(boot,[.025,.975])
        comparisons.append(dict(comparacao=label,cenario_a=a.id,cenario_b=b.id,n=len(delta),diferenca_media_pp=float(delta.mean()),ic95_inferior_pp=float(lo),ic95_superior_pp=float(hi),fracao_a_maior=float((delta>0).mean()),fracao_empates=float((delta==0).mean()),metodo="bootstrap pareado percentil 5000; exploratorio sem correcao multipla"))
    for experiment in ("01_politicas_fixas","03_robustez_phase","03_robustez_pollution","03_robustez_random"):
        group=[s for s in suite if s.experiment==experiment]
        ref=next(s for s in group if s.policy=="LRU")
        for s in group:
            if s!=ref: pair(s,ref,f"{experiment}: {s.policy} - LRU")
    for policy in ("LRU","LRFU"):
        a=next(s for s in suite if s.experiment=="07_filtro_fir" and s.workload=="fir_amostra" and s.policy==policy)
        b=next(s for s in suite if s.experiment=="07_filtro_fir" and s.workload=="fir_canal" and s.policy==policy)
        pair(a,b,f"FIR {policy}: amostra - canal")
    return comparisons


def classify_misses(trace, cache_bytes=8192, block=16, ways=16):
    """3C com referência totalmente associativa LRU de igual capacidade.
    Em LRU por conjuntos, rótulo conflito significa miss não compulsório que
    seria hit no contrafactual FA-LRU; capacidade se ambos são miss.
    É uma classificação por referência, não prova de causa física isolada.
    """
    cache=CacheMemory(cache_bytes,block,ways,"LRU")
    seen=set(); shadow=OrderedDict(); counts=dict(hits=0,compulsorios=0,conflito=0,capacidade=0)
    for address in trace:
        b=address//block; shadow_hit=b in shadow
        hit=cache.request_access(address)
        if hit: counts['hits']+=1
        elif b not in seen: counts['compulsorios']+=1
        elif shadow_hit: counts['conflito']+=1
        else: counts['capacidade']+=1
        seen.add(b)
        if shadow_hit: shadow.move_to_end(b)
        else:
            shadow[b]=None
            if len(shadow)>cache_bytes//block: shadow.popitem(last=False)
    assert sum(counts.values())==len(trace)
    return counts


def plot_results(output,suite,data,summary,seed,accesses):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    byid={r['cenario_id']:r for r in summary}
    figures=output/'graficos'; figures.mkdir(exist_ok=True)
    def save(fig,name):
        fig.tight_layout(); fig.savefig(figures/name,dpi=160); plt.close(fig)
    def groups(experiment): return [s for s in suite if s.experiment==experiment]
    for exp,name in (("01_politicas_fixas","01_politicas_fixas.png"),("02_perfis","02_perfis.png"),("06_realista_aleatorio","06_realista_aleatorio.png"),("07_filtro_fir","07_fir.png")):
        ss=groups(exp); fig,ax=plt.subplots(figsize=(10,5)); means=[byid[s.id]['media']*100 for s in ss]
        bars=ax.bar([s.label for s in ss],means,yerr=[byid[s.id]['desvio_padrao']*100 for s in ss],capsize=4)
        ax.bar_label(bars,fmt='%.2f%%',padding=4); ax.set_ylim(0,105); ax.set_ylabel('Taxa de acerto (%) — média ± DP amostral'); ax.tick_params(axis='x',labelrotation=15); ax.set_title(exp)
        save(fig,name)
    fig,ax=plt.subplots(figsize=(10,5))
    for policy in POLICIES[:4]:
        ss=[s for s in groups('01b_politicas_blocos') if s.policy==policy]
        ax.errorbar([s.block for s in ss],[byid[s.id]['media']*100 for s in ss],yerr=[byid[s.id]['desvio_padrao']*100 for s in ss],marker='o',label=policy,capsize=2)
    ax.set_xscale('log',base=2); ax.set_xlabel('Bloco (B); capacidade fixa 8 KiB'); ax.set_ylabel('Acertos (%)'); ax.legend(); save(fig,'01b_blocos_capacidade_fixa.png')
    fig,axes=plt.subplots(1,3,figsize=(14,4))
    for i,ax in enumerate(axes):
        ss=groups(f'02_isolada_{i}')
        ax.errorbar([s.value for s in ss],[byid[s.id]['media']*100 for s in ss],yerr=[byid[s.id]['desvio_padrao']*100 for s in ss],marker='o',capsize=3)
        ax.set_title(('Temporal','Espacial','Regiões quentes')[i]); ax.set_xlabel('Probabilidade (demais = 0)'); ax.set_ylabel('Acertos (%)'); ax.set_ylim(0,100)
    save(fig,'02_localidade_isolada.png')
    for exp,name in (("01_politicas_fixas","03_boxplot_politicas.png"),("03_robustez_phase","03_boxplot_fases.png"),("03_robustez_pollution","03_boxplot_varredura.png"),("03_robustez_random","03_boxplot_aleatorio.png")):
        ss=groups(exp); fig,ax=plt.subplots(figsize=(9,5))
        ax.boxplot([[r['taxa_acerto']*100 for r in data[s.id]] for s in ss],tick_labels=[s.policy for s in ss],showmeans=True,whis=1.5)
        ax.set_ylabel('Taxa de acerto (%)'); ax.set_title(exp+'; pontos externos: regra 1,5×IQR'); save(fig,name)
    fig,ax=plt.subplots(figsize=(9,5))
    for s in groups('01_politicas_fixas'):
        ax.hist([r['taxa_acerto']*100 for r in data[s.id]],bins=14,histtype='step',linewidth=1.6,label=s.policy)
    ax.set_xlabel('Taxa de acerto (%)'); ax.set_ylabel('Repetições'); ax.legend(); save(fig,'03_histograma.png')
    for exp,name,xlabel in (("04_linhas","04_linhas.png","Número de linhas; bloco fixo 16 B"),("04_associatividade","04_associatividade.png","Vias por conjunto; 512 linhas fixas"),("04_bloco_linhas_fixas","04_bloco_linhas_fixas.png","Bloco (B); 512 linhas fixas"),("08_sensibilidade_lrfu","08_sensibilidade_lrfu.png","Meia-vida da LRFU (acessos globais)")):
        ss=groups(exp); fig,ax=plt.subplots(figsize=(9,5)); ax.errorbar([s.value for s in ss],[byid[s.id]['media']*100 for s in ss],yerr=[byid[s.id]['desvio_padrao']*100 for s in ss],marker='o',capsize=3)
        ax.set_xscale('log',base=2); ax.set_xlabel(xlabel); ax.set_ylabel('Acertos (%) — média ± DP'); save(fig,name)
    # Exibe blocos reais mais frequentes e agrega o restante, sem módulo.
    for index,s in enumerate(groups('02_perfis')):
        trace=pattern(s,random.Random(seed+1),accesses)
        mapa_temporal_blocos(trace,s.block,figures/f'02_mapa_{index}.png',s.label)
    # Mesma carga de mudança de fase para todas as políticas; exemplo, não inferência.
    fig,ax=plt.subplots(figsize=(10,5)); window=250
    template=next(s for s in suite if s.experiment=='03_robustez_phase')
    trace=pattern(template,random.Random(seed+1),accesses)
    for policy in POLICIES:
        cache=CacheMemory(8192,16,16,policy,rng=random.Random(seed+1+10_000_019)); hits=[]
        for a in trace: hits.append(cache.request_access(a))
        ax.plot([i for i in range(window,len(trace)+1,window)],[np.mean(hits[i-window:i])*100 for i in range(window,len(trace)+1,window)],label=policy)
    ax.axvline(accesses//2,color='black',linestyle='--',label='Mudança de fase'); ax.set_xlabel('Referências acumuladas'); ax.set_ylabel(f'Acertos por janela de {window} (%)'); ax.legend(); save(fig,'05_adaptacao_temporal.png')


def mapa_temporal_blocos(trace,block,output,title,window=100,top=24):
    matrix,labels=agregar_mapa(trace,block,window,top)
    fig,ax=plt.subplots(figsize=(12,7)); im=ax.imshow(matrix,origin='upper',aspect='auto',cmap='magma')
    ax.set_yticks(range(len(labels)),labels); ax.set_ylabel(f'Número real do bloco de {block} B'); ax.set_xlabel(f'Janela temporal ({window} referências; última pode ser parcial)'); ax.set_title(title+' — repetição 1; blocos mais frequentes'); fig.colorbar(im,ax=ax,label='Referências por janela')
    fig.tight_layout(); fig.savefig(output,dpi=160); plt.close(fig)


def run(args):
    output=args.output; output.mkdir(parents=True,exist_ok=True)
    suite=scenarios(); manifest_path=output/'manifesto.json'
    hashes={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('cache_core.py','cache_visualizacao.py','experimentos_completos.py')}
    config=dict(runs=args.runs,accesses=args.accesses,seed=args.seed,scenarios=[asdict(s) for s in suite],source_sha256=hashes)
    # JSON normaliza tuplas para listas antes da comparação de retomada.
    config=json.loads(json.dumps(config))
    if manifest_path.exists():
        previous=json.loads(manifest_path.read_text(encoding='utf-8'))
        if previous['config']!=config: raise ValueError('Pasta contém configuração ou código diferente; escolha outra pasta para preservar os dados')
    else:
        manifest_path.write_text(json.dumps(dict(created_at=datetime.now().astimezone().isoformat(),python=sys.version,numpy=np.__version__,matplotlib=matplotlib.__version__,config=config),ensure_ascii=False,indent=2),encoding='utf-8')
    checkpoint_dir=output/'checkpoints'; checkpoint_dir.mkdir(exist_ok=True)
    data={}; allrows=[]; summary=[]; outliers=[]
    start=time.perf_counter()
    for index,s in enumerate(suite,1):
        cp=checkpoint_dir/f'{s.id}.json'
        if cp.exists():
            records=json.loads(cp.read_text(encoding='utf-8'))
        else:
            print(f'[{index}/{len(suite)}] {s.experiment} | {s.label}',flush=True)
            records=simulacao_monte_carlo(args.runs,args.accesses,RAM,s.cache,s.ways,HOT,s.probs,s.block,s.policy,seed_base=args.seed,pattern_factory=lambda rng:pattern(s,rng,args.accesses),return_details=True,verbose=False,decay=s.decay)
            tmp=cp.with_suffix('.tmp'); tmp.write_text(json.dumps(records),encoding='utf-8'); tmp.replace(cp)
        if len(records)!=args.runs or [r['semente'] for r in records]!=list(range(args.seed+1,args.seed+args.runs+1)):
            raise ValueError(f'Checkpoint inválido: {s.id}')
        data[s.id]=records
        allrows.extend(dict(cenario_id=s.id,experimento=s.experiment,cenario=s.label,algoritmo=s.policy,cache_bytes=s.cache,cache_lines=s.cache//s.block,bloco_bytes=s.block,associatividade=s.ways,**r) for r in records)
        row,outs=summarize(s,records); summary.append(row); outliers.extend(outs)
    write_csv(output/'resultados_individuais.csv',allrows)
    write_csv(output/'resumo_estatistico.csv',summary)
    write_csv(output/'outliers.csv',outliers)
    write_csv(output/'comparacoes_pareadas.csv',paired_comparisons(suite,data,args.runs,args.seed))
    print('Calculando classificação 3C adicional (LRU)...',flush=True)
    misses=[]
    for label,workload,ways in (("Realista por conjuntos","synthetic",16),("Aleatório por conjuntos","random",16),("Fases por conjuntos","phase",16),("Fases totalmente associativa","phase",512)):
        s=Scenario('3C','09_3c',label,ways=ways,workload=workload)
        for repetition in range(1,args.runs+1):
            trace=pattern(s,random.Random(args.seed+repetition),args.accesses)
            counts=classify_misses(trace,ways=ways)
            misses.append(dict(cenario=label,repeticao=repetition,semente=args.seed+repetition,acessos=len(trace),**counts))
    write_csv(output/'classificacao_3c.csv',misses)
    plot_results(output,suite,data,summary,args.seed,args.accesses)
    from relatorio_completo import build_report
    build_report(output,summary,allrows,args,misses)
    status=dict(status='concluido',completed_at=datetime.now().astimezone().isoformat(),cenarios=len(suite),simulacoes=len(allrows),simulacoes_3c=len(misses),referencias=sum(r['acessos_cpu'] for r in allrows),referencias_3c=sum(r['acessos'] for r in misses),segundos_esta_execucao=time.perf_counter()-start)
    (output/'conclusao.json').write_text(json.dumps(status,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False),flush=True)
    print('Resultados em:',output.resolve(),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs',type=int,default=100)
    parser.add_argument('--accesses',type=int,default=10000)
    parser.add_argument('--seed',type=int,default=2026)
    parser.add_argument('--output',type=Path,default=Path('Resultados_Automaticos/2026-11-14_estudo_completo'))
    parser.add_argument('--quick',action='store_true')
    args=parser.parse_args()
    if args.quick: args.runs=3; args.accesses=1000
    if args.runs<2 or args.accesses<500: parser.error('Use ao menos 2 repetições e 500 acessos')
    run(args)

if __name__=='__main__': main()
