"""Agregação de mapas por blocos reais; conserva todas as referências."""
import math
import numpy as np

def agregar_mapa(trace, block=16, window=100, top=24):
    if not trace or block <= 0 or window <= 0 or top <= 0:
        raise ValueError("Rastro não vazio e parâmetros positivos são necessários")
    blocks=np.asarray(trace,dtype=np.int64)//block
    unique,counts=np.unique(blocks,return_counts=True)
    selected=unique[np.argsort(-counts,kind="stable")[:top]]
    lookup={int(b):i for i,b in enumerate(selected)}
    matrix=np.zeros((len(selected)+1,math.ceil(len(trace)/window)),dtype=int)
    for pos,b in enumerate(blocks):
        matrix[lookup.get(int(b),len(selected)),pos//window]+=1
    return matrix,[str(int(b)) for b in selected]+["Outros (soma)"]
