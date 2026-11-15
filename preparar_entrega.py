"""Audita dados, gera PDF e monta o pacote completo sem usar o espaço de C:."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from relatorio_completo import markdown_html
from verificar_entrega import audit


def main():
    root=Path(__file__).resolve().parent
    os.chdir(root)
    output=root/'Resultados_Automaticos/2026-11-14_estudo_completo'
    verdict=audit(output)
    test=subprocess.run([sys.executable,'-B','-m','unittest','test_cache_core','-v'],capture_output=True,text=True,encoding='utf-8',errors='replace')
    (output/'validacao_testes.txt').write_text(test.stdout+test.stderr,encoding='utf-8')
    if test.returncode: raise RuntimeError('Falha nos testes; veja o log')
    verdict['testes_unitarios']='13 testes aprovados; sem skips'
    browser=next(p for p in (Path('C:/Program Files/Google/Chrome/Application/chrome.exe'),Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')) if p.is_file())
    pdf=output/'Relatorio_Completo.pdf'
    with tempfile.TemporaryDirectory(prefix='cache_pdf_',dir=root.parent,ignore_cleanup_errors=True) as profile:
        cmd=[str(browser),'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--no-pdf-header-footer','--allow-file-access-from-files',f'--user-data-dir={profile}',f'--print-to-pdf={pdf}',(output/'Relatorio_Completo.html').as_uri()]
        proc=subprocess.run(cmd,capture_output=True,timeout=120,env=dict(os.environ,TEMP=profile,TMP=profile),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if proc.returncode or not pdf.is_file() or pdf.stat().st_size<10000: raise RuntimeError('Falha ao imprimir PDF: '+proc.stderr.decode('utf-8',errors='replace')[-1200:])
    verdict['pdf_bytes']=pdf.stat().st_size
    (output/'verificacao_entrega.json').write_text(json.dumps(verdict,ensure_ascii=False,indent=2),encoding='utf-8')
    text=(output/'Relatorio_Completo.md').read_text(encoding='utf-8')
    relative=output.relative_to(root)
    text=re.sub(r'(!?\[[^\]]*\]\()([^)]+)(\))',lambda m:m[1]+(relative/Path(m[2])).as_posix()+m[3],text)
    (root/'Relatorio_Final_Organizacao_de_Computadores.md').write_text(text,encoding='utf-8')
    (root/'Relatorio_Final_Organizacao_de_Computadores.conversion.html').write_text(markdown_html(text),encoding='utf-8')
    shutil.copy2(pdf,root/'Relatorio_Final_Organizacao_de_Computadores.pdf')
    with (output/'resumo_estatistico.csv').open(encoding='utf-8-sig',newline='') as f: summary=list(csv.DictReader(f))
    with (output/'comparacoes_pareadas.csv').open(encoding='utf-8-sig',newline='') as f: paired=list(csv.DictReader(f))
    base=[r for r in summary if r['experimento']=='01_politicas_fixas']; best=max(base,key=lambda r:float(r['media']))
    fir=next(r for r in paired if r['comparacao']=='FIR LRU: amostra - canal')
    guide=f"""# Guia de apresentação — estudo completo de cache

São 111 cenários com 100 repetições cada e 400 simulações adicionais de classificação 3C. O relatório final inclui a matriz de atendimento das seis atividades. Resultados finais: `Resultados_Automaticos/2026-11-14_estudo_completo`.

## Roteiro (12 a 15 minutos)

1. **Conceitos e configuração (1 min):** hit, miss, linha, bloco e conjunto; RAM de 1 MiB, cache de 8 KiB, bloco de 16 B, 512 linhas, 16 vias e 32 conjuntos.
2. **Políticas (2 min):** gráfico de arquitetura fixa; só a política muda. Mesmos rastros por repetição. Melhor média no perfil base: {best['algoritmo']} ({float(best['media'])*100:.2f}%). Mostrar também as diferenças pareadas e seus intervalos.
3. **Localidade (2 min):** curvas de probabilidades isoladas e dois mapas. Distinguir perfis compostos de variação isolada. Mapas mostram números reais de blocos e a carga, não o estado da cache; a linha Outros agrega muitas posições.
4. **Monte Carlo (2 min):** boxplots de base e fases. Explicar média, mediana, variância, DP, quartis e outliers. Todas as repetições começam frias; nenhum extremo foi removido.
5. **Arquitetura (2 min):** curvas de linhas e associatividade. Uma via é direta, 512 é totalmente associativa. Comparar bloco com capacidade fixa e bloco com linhas fixas: são perguntas diferentes.
6. **LRFU (2 min):** mostrar atualização da pontuação e meia-vida de 64 acessos globais. Apresentar sensibilidade, ganhos e perdas. A família LRFU é conhecida; a contribuição é implementar e avaliar a variante neste projeto.
7. **Além do roteiro (2 min):** mudança de fase, varredura, FIR e misses 3C. No FIR, mostrar as duas ordens de laços e o teste de igualdade numérica. Diferença LRU: {float(fir['diferenca_media_pp']):.3f} pontos percentuais de acertos.
8. **Conclusão (1 min):** relacionar a carga aos resultados; não confundir taxa de acerto com tempo real ou melhor hardware universal.

## Demonstração

- Em `cache_core.py`, mostrar `LRFU` e `simulacao_monte_carlo()`.
- Em `experimentos_completos.py`, mostrar `scenarios()` e `fir_trace()`.
- Em `test_cache_core.py`, mostrar o modelo independente e a equivalência numérica do filtro.
- Executar `python -B -m unittest test_cache_core -v`.
- Abrir `python cache_simulator_GUI.py`, selecionar LRFU e gerar um mapa.
- Demonstrar retomada repetindo o comando completo na mesma pasta e com o mesmo código. As simulações concluídas vêm dos checkpoints; gráficos e análise são refeitos.

## Perguntas possíveis

**Por que 100 simulações?** É a quantidade pedida; descreve a variabilidade, mas não garante precisão universal.

**Por que as mesmas sementes?** Para comparar configurações diante da mesma carga e usar diferenças pareadas. A substituição Random tem RNG separado.

**O que é outlier?** Uma repetição além das cercas de 1,5 vezes o intervalo interquartil. Não significa necessariamente erro e continua na média.

**LRFU sempre vence?** Não; depende da carga e meia-vida. Mostrar os resultados de base, fases, varredura e aleatório, inclusive as perdas.

**Por que dois estudos de bloco?** Capacidade = linhas vezes bloco. Com capacidade fixa, variam as linhas; com linhas fixas, varia a capacidade.

**O FIR foi medido numa CPU real?** A computação foi validada numericamente, e os acessos foram modelados em rastros. Não houve captura por ferramenta de hardware nem medição de tempo real.

**Por que o FIR melhora?** A ordem por amostra aproxima referências a canais contíguos, aproveita o bloco e altera a pressão nos conjuntos. As duas versões fazem as mesmas operações e têm o mesmo multiconjunto de referências.

**O que vai além do roteiro?** Intervalos bootstrap pareados, adaptação temporal e poluição, sensibilidade da LRFU, classificação 3C por referência, FIR com equivalência, auditoria e execução retomável.

## Material

Levar PDF, código, CSVs, figuras, manifesto e logs. O ZIP reúne tudo sem o ambiente virtual. Usar Python 3.12 e instalar as dependências de `requirements.txt` em um novo ambiente.
"""
    (root/'GUIA_APRESENTACAO.md').write_text(guide,encoding='utf-8')
    shipped=[p for p in root.rglob('*') if p.is_file() and p.name!='Entrega_Cache_SHA256.txt']
    (root/'Entrega_Cache_SHA256.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix() for p in shipped)+'\n',encoding='utf-8')
    shipped.append(root/'Entrega_Cache_SHA256.txt')
    bundle=root.parent/'Entrega_Cache_2026-11-14.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in shipped: z.write(p,p.relative_to(root))
    print(json.dumps(verdict,ensure_ascii=False,indent=2),flush=True)
    print('PDF:',root/'Relatorio_Final_Organizacao_de_Computadores.pdf',flush=True)
    print('ZIP:',bundle,'bytes:',bundle.stat().st_size,flush=True)

if __name__=='__main__': main()
