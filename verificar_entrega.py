"""Auditoria independente dos resultados completos; não altera os CSVs."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics
import numpy as np
from PIL import Image


def audit(output):
    def read(name):
        with (output/name).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
    def near(a,b): assert abs(float(a)-float(b))<1e-11,(a,b)
    manifest=json.loads((output/'manifesto.json').read_text(encoding='utf-8'))
    config=manifest['config']; expected={s['id']:s for s in config['scenarios']}
    assert config['runs']==100 and config['accesses']==10000
    rows=read('resultados_individuais.csv'); summary=read('resumo_estatistico.csv'); outliers=read('outliers.csv'); pairs=read('comparacoes_pareadas.csv'); misses=read('classificacao_3c.csv')
    assert len(summary)==len(expected)==111 and len(rows)==11100 and len(misses)==400
    groups=defaultdict(list)
    for r in rows:
        n=int(r['acessos_cpu']); h=int(r['hits']); m=int(r['misses'])
        assert h+m==n and 0<=h<=n and 0<=m<=n
        near(r['taxa_acerto'],h/n)
        s=expected[r['cenario_id']]
        assert n==(65824 if s['workload'].startswith('fir_') else 10000)
        assert int(r['cache_lines'])==s['cache']//s['block']
        assert int(r['cache_bytes'])==s['cache'] and int(r['bloco_bytes'])==s['block'] and int(r['associatividade'])==s['ways']
        groups[r['cenario_id']].append(r)
    expected_outliers=set()
    for r in summary:
        g=groups[r['cenario_id']]; vals=[float(x['taxa_acerto']) for x in g]
        assert len(g)==100
        assert {int(x['repeticao']) for x in g}==set(range(1,101))
        assert {int(x['semente']) for x in g}==set(range(config['seed']+1,config['seed']+101))
        near(r['media'],statistics.mean(vals)); near(r['desvio_padrao'],statistics.stdev(vals)); near(r['variancia'],statistics.variance(vals)); near(r['minimo'],min(vals)); near(r['maximo'],max(vals))
        q1,med,q3=np.quantile(vals,[.25,.5,.75]); near(r['q1'],q1); near(r['mediana'],med); near(r['q3'],q3)
        lo=q1-1.5*(q3-q1); hi=q3+1.5*(q3-q1)
        near(r['limite_outlier_inferior'],lo); near(r['limite_outlier_superior'],hi)
        outs=[x for x in g if float(x['taxa_acerto'])<lo or float(x['taxa_acerto'])>hi]
        assert int(r['n_outliers'])==len(outs)
        expected_outliers.update((r['cenario_id'],x['repeticao']) for x in outs)
    assert {(r['cenario_id'],r['repeticao']) for r in outliers}==expected_outliers
    assert len(pairs)==18
    for i,r in enumerate(pairs):
        a={int(x['repeticao']):float(x['taxa_acerto']) for x in groups[r['cenario_a']]}; b={int(x['repeticao']):float(x['taxa_acerto']) for x in groups[r['cenario_b']]}
        delta=np.array([a[k]-b[k] for k in sorted(a)])*100
        near(r['diferenca_media_pp'],delta.mean()); near(r['fracao_a_maior'],(delta>0).mean()); near(r['fracao_empates'],(delta==0).mean())
        rng=np.random.default_rng(config['seed']+i); boot=delta[rng.integers(0,100,size=(5000,100))].mean(axis=1); lo,hi=np.quantile(boot,[.025,.975])
        near(r['ic95_inferior_pp'],lo); near(r['ic95_superior_pp'],hi)
    for r in misses:
        assert sum(int(r[k]) for k in ('hits','compulsorios','conflito','capacidade'))==int(r['acessos'])==10000
        if 'totalmente' in r['cenario']: assert int(r['conflito'])==0
    for name,digest in config['source_sha256'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
    images=list((output/'graficos').glob('*.png')); assert len(images)==21
    for p in images:
        with Image.open(p) as img: img.verify()
    md=(output/'Relatorio_Completo.md').read_text(encoding='utf-8')
    for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',md):
        assert (output/target).is_file(),target
    status=json.loads((output/'conclusao.json').read_text(encoding='utf-8'))
    assert status['status']=='concluido' and status['simulacoes']==len(rows) and status['simulacoes_3c']==len(misses)
    assert status['referencias']==sum(int(r['acessos_cpu']) for r in rows)
    return dict(status='aprovado',cenarios=111,simulacoes_principais=11100,simulacoes_3c=400,referencias_principais=status['referencias'],referencias_3c=4000000,figuras=21,comparacoes_pareadas=18,outliers=len(outliers),verificacoes='contadores, sementes, configurações, médias, DP, variâncias, quartis, extremos, outliers, bootstrap pareado, totais 3C, hashes, imagens e links')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    print(json.dumps(audit(args.output),ensure_ascii=False,indent=2))
