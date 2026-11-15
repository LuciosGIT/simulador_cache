"""Verificações de comportamento e de desenho experimental, sem abrir a GUI."""
import csv
from collections import Counter
import math
from pathlib import Path
import random
import unittest
import numpy as np
from cache_core import CacheMemory, POLICIES, gerar_padrao_realista, simulacao_monte_carlo
from experimentos_completos import Scenario, scenarios, fir_trace, pattern, classify_misses


def reference(trace, size, block, ways, policy, seed=7, decay=1/64):
    """Modelo simples por listas; LRFU recalcula soma de todo histórico residente."""
    sets=[[] for _ in range(size//block//ways)]; rng=random.Random(seed); result=[]
    for time,address in enumerate(trace,1):
        b=address//block; st=sets[b%len(sets)]
        found=next((x for x in st if x['b']==b),None)
        result.append(found is not None)
        if found is not None:
            found['last']=time; found['freq']+=1; found['history'].append(time); continue
        if len(st)==ways:
            if policy=='Random': victim=rng.choice(st)
            elif policy=='FIFO': victim=min(st,key=lambda x:x['insert'])
            elif policy=='LRU': victim=min(st,key=lambda x:x['last'])
            elif policy=='LFU': victim=min(st,key=lambda x:(x['freq'],x['last']))
            else: victim=min(st,key=lambda x:(sum(2**(-decay*(time-t)) for t in x['history']),x['last'],x['insert']))
            # Mantém a ordem física das linhas para o RNG de Random.
            slot=st.index(victim)
            st[slot]=dict(b=b,insert=time,last=time,freq=1,history=[time])
        else: st.append(dict(b=b,insert=time,last=time,freq=1,history=[time]))
    return result


class CoreTests(unittest.TestCase):
    def test_against_independent_reference(self):
        for policy in POLICIES:
            for ways in (1,2,4,8):
                trace=[random.Random(100+i).randrange(128) for i in range(400)]
                cache=CacheMemory(32,4,ways,policy,rng=random.Random(7))
                actual=[cache.request_access(a) for a in trace]
                self.assertEqual(actual,reference(trace,32,4,ways,policy))
                self.assertEqual(cache.hits+cache.misses,len(trace))

    def test_address_fields(self):
        for ways in (1,4,512):
            cache=CacheMemory(8192,16,ways,'LRU')
            for address in (0,15,16,8191,8192,1048575):
                tag,index,offset=cache.calculate_address_fields(address)
                self.assertEqual(((tag*cache.num_sets+index)*16+offset),address)

    def test_fifo_and_lru_differ(self):
        self.assertEqual(reference([0,1,0,2,0],2,1,2,'FIFO'),[False,False,True,False,False])
        self.assertEqual(reference([0,1,0,2,0],2,1,2,'LRU'),[False,False,True,False,True])

    def test_invalid_configurations(self):
        for args in ((0,16,1,'LRU'),(8192,3,1,'LRU'),(32,16,4,'LRU'),(32,4,2,'typo')):
            with self.assertRaises(ValueError): CacheMemory(*args)
        with self.assertRaises(ValueError): gerar_padrao_realista(10,128,[0],(.8,.8,0))
        with self.assertRaises(ValueError): gerar_padrao_realista(10,128,[],(0,0,.5))

    def test_lrfu_lambda_zero_equals_lfu(self):
        trace=[random.Random(i).randrange(32) for i in range(300)]
        a=CacheMemory(16,1,4,'LFU'); b=CacheMemory(16,1,4,'LRFU',decay=0)
        self.assertEqual([a.request_access(x) for x in trace],[b.request_access(x) for x in trace])

    def test_cold_start_and_repeatability(self):
        kwargs=dict(n_simulacoes=4,acessos=100,memory_size=1024,cache_size=64,associatividade=2,regioes_quentes=[64],probs=(.2,.2,.4),bloco_tamanho=4,algoritmo='Random',seed_base=2026,return_details=True,verbose=False)
        a=simulacao_monte_carlo(**kwargs); b=simulacao_monte_carlo(**kwargs)
        self.assertEqual(a,b)
        for r in a: self.assertEqual(r['hits']+r['misses'],100)
        fixed=simulacao_monte_carlo(3,10,1024,64,2,[0],(0,0,0),4,'LRU',pattern_factory=lambda rng:[0]*10,return_details=True,verbose=False)
        self.assertTrue(all(r['misses']==1 and r['hits']==9 for r in fixed))

    def test_same_trace_for_all_policies(self):
        captured=[]
        def factory(rng):
            trace=[rng.randrange(1024) for _ in range(50)]; captured.append(trace); return trace
        for policy in POLICIES:
            simulacao_monte_carlo(3,50,1024,64,2,[0],(0,0,0),4,policy,seed_base=2026,pattern_factory=factory,verbose=False)
        for k in range(1,5): self.assertEqual(captured[:3],captured[k*3:k*3+3])

    def test_original_result_compatibility(self):
        path=Path('Resultados_Automaticos/2026-11-13_completo/resultados_individuais.csv')
        if not path.exists(): self.skipTest('Execução histórica ausente')
        with path.open(encoding='utf-8') as f:
            rows=[r for r in csv.DictReader(f) if r['experimento']=='politicas_substituicao' and r['tamanho_bloco_bytes']=='16' and r['repeticao']=='1']
        for row in rows:
            # Reproduz o gerador global da automação histórica, inclusive Random.
            from experimentos_completos import RAM,HOT,BASE
            random.seed(int(row['semente']))
            trace=gerar_padrao_realista(10000,RAM,HOT,BASE)
            cache=CacheMemory(8192,16,16,row['algoritmo'])
            for a in trace: cache.request_access(a)
            self.assertAlmostEqual(cache.hit_rate,float(row['taxa_acerto']),places=12)

    def test_fir_trace_same_work(self):
        a=fir_trace(random.Random(42),'fir_canal'); b=fir_trace(random.Random(42),'fir_amostra')
        self.assertEqual(len(a),65824); self.assertEqual(Counter(a),Counter(b)); self.assertNotEqual(a,b)

    def test_fir_numerical_equivalence(self):
        rng=np.random.default_rng(17); x=rng.normal(size=(32,8)).astype(np.float32); h=rng.normal(size=5).astype(np.float32)
        def filter_signal(order):
            y=np.zeros((28,8),dtype=np.float32)
            pairs=((n,c) for c in range(8) for n in range(4,32)) if order=='canal' else ((n,c) for n in range(4,32) for c in range(8))
            for n,c in pairs:
                acc=np.float32(0)
                for k in range(5): acc=np.float32(acc+x[n-k,c]*h[k])
                y[n-4,c]=acc
            return y
        a=filter_signal('canal'); b=filter_signal('amostra')
        np.testing.assert_array_equal(a,b)
        expected=np.stack([np.convolve(x[:,c],h,mode='valid') for c in range(8)],axis=1)
        np.testing.assert_allclose(a,expected,rtol=2e-6,atol=2e-6)

    def test_scenario_design(self):
        suite=scenarios(); self.assertEqual(len({s.id for s in suite}),len(suite))
        for s in suite:
            CacheMemory(s.cache,s.block,s.ways,s.policy)
            if s.experiment=='04_bloco_linhas_fixas': self.assertEqual(s.cache//s.block,512)
            if s.experiment=='04_associatividade': self.assertEqual((s.cache,s.block),(8192,16))
            if s.experiment.startswith('02_isolada'): self.assertLessEqual(sum(x>0 for x in s.probs),1)

    def test_heatmap_conserves_partial_window(self):
        from cache_visualizacao import agregar_mapa
        trace=[0,16,1024,1024,32,2048,2048]
        matrix,labels=agregar_mapa(trace,16,3,2)
        self.assertEqual(matrix.sum(axis=0).tolist(),[3,3,1])
        self.assertEqual(int(matrix.sum()),len(trace))
        self.assertIn('64',labels)
        self.assertIn('128',labels)
        self.assertEqual(labels[-1],'Outros (soma)')

    def test_3c(self):
        # 2 linhas, direta: 0 e 2 conflitam, mas cabem na FA de duas linhas.
        self.assertEqual(classify_misses([0,2,0,2],2,1,1),dict(hits=0,compulsorios=2,conflito=2,capacidade=0))
        self.assertEqual(classify_misses([0,1,2,0],2,1,2),dict(hits=0,compulsorios=3,conflito=0,capacidade=1))
        self.assertEqual(classify_misses([0,0,1,1],2,1,2),dict(hits=2,compulsorios=2,conflito=0,capacidade=0))

if __name__=='__main__': unittest.main(verbosity=2)
