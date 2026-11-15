"""Relatório gerado exclusivamente a partir dos CSVs da suíte completa."""
from collections import defaultdict
import csv
from datetime import datetime
import html
import json
from pathlib import Path
import re
import statistics


def integer(x): return f'{x:,}'.replace(',','.')

def fmt(x,d=2): return f'{x:.{d}f}'.replace('.',',')
def pct(x): return fmt(x*100)+'%'

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|']+['| '+' | '.join(map(str,row))+' |' for row in rows])


def markdown_html(text):
    """Renderizador pequeno para o Markdown emitido aqui (sem dependência externa)."""
    def inline(value):
        escaped=html.escape(value)
        escaped=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',escaped)
        escaped=re.sub(r'`([^`]+)`',r'<code>\1</code>',escaped)
        escaped=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',escaped)
        return escaped
    out=[]; lines=text.splitlines(); i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line: i+=1; continue
        if line.startswith('|'):
            group=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                group.append(lines[i].strip()); i+=1
            out.append('<table><thead><tr>'+''.join('<th>'+inline(x.strip())+'</th>' for x in group[0].strip('|').split('|'))+'</tr></thead><tbody>')
            for row in group[2:]: out.append('<tr>'+''.join('<td>'+inline(x.strip())+'</td>' for x in row.strip('|').split('|'))+'</tr>')
            out.append('</tbody></table>'); continue
        image=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line)
        if image:
            out.append(f'<figure><img src="{html.escape(image[2])}" alt="{html.escape(image[1])}"><figcaption>{inline(image[1])}</figcaption></figure>')
        elif line.startswith('#'):
            n=min(len(line)-len(line.lstrip('#')),6); out.append(f'<h{n}>'+inline(line[n:].strip())+f'</h{n}>')
        elif line.startswith('- '): out.append('<p class="bullet">• '+inline(line[2:])+'</p>')
        else: out.append('<p>'+inline(line)+'</p>')
        i+=1
    style="""
    @page { size: A4; margin: 17mm 15mm; }
    body { font: 11pt/1.5 Arial,sans-serif; color:#192635; max-width:1050px; margin:30px auto; }
    h1 {font-size:23pt; color:#123b57;} h2 {font-size:17pt; margin-top:28px; color:#123b57;}
    h3 {font-size:13pt; color:#175572;} h1,h2,h3 {break-after:avoid;}
    table {border-collapse:collapse; width:100%; font-size:8.5pt; margin:16px 0;}
    th,td {border:1px solid #b9c6d1; padding:5px; text-align:left; overflow-wrap:anywhere;}
    th {background:#e7eff5;} thead {display:table-header-group;} tr {break-inside:avoid;}
    figure {margin:18px 0; break-inside:avoid;} img {max-width:100%; max-height:210mm;}
    figcaption {font-size:9pt; color:#46576a;} code {font-size:9pt; overflow-wrap:anywhere;}
    a {color:#145b86;} .bullet {margin:5px 0;} @media print {body{margin:0; max-width:none;} a{color:inherit;text-decoration:none;}}
    """
    return '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Estudo completo de memória cache</title><style>'+style+'</style></head><body>'+''.join(out)+'</body></html>'


def build_report(output,summary,individual,args,misses):
    from experimentos_completos import scenarios
    byid={r['cenario_id']:r for r in summary}
    def group(name): return [r for r in summary if r['experimento']==name]
    def image(name,caption): return f'![{caption}](graficos/{name})'
    def stats(rows):
        return table(['Cenário','Política','Média','DP (p.p.)','Variância da fração','Mín.–máx.','Outliers'],[[r['cenario'],r['algoritmo'],pct(r['media']),fmt(r['desvio_padrao']*100,3),f"{r['variancia']:.8f}",pct(r['minimo'])+'–'+pct(r['maximo']),r['n_outliers']] for r in rows])
    base=group('01_politicas_fixas'); best=max(base,key=lambda r:r['media'])
    old=group('01b_politicas_blocos'); bestblock=max(old,key=lambda r:r['media'])
    access={r['cenario']:r for r in group('06_realista_aleatorio')}
    total_accesses=sum(r['acessos_cpu'] for r in individual)
    with (output/'comparacoes_pareadas.csv').open(encoding='utf-8-sig',newline='') as f: paired=list(csv.DictReader(f))
    def pair_table(rows): return table(['Comparação (A − B)','Diferença (p.p.)','IC bootstrap 95% (p.p.)','A > B nas repetições'],[[r['comparacao'],fmt(float(r['diferenca_media_pp']),3),f"[{fmt(float(r['ic95_inferior_pp']),3)}; {fmt(float(r['ic95_superior_pp']),3)}]",pct(float(r['fracao_a_maior']))] for r in rows])
    lines=[
    '# Universidade de Pernambuco — Escola Politécnica de Pernambuco (POLI)',
    '## Organização de Computadores',
    '### Estudo completo de memória cache: políticas, localidade, arquitetura e filtro FIR',
    '**Professor:** José Paulo Gonçalves de Oliveira',
    '**Integrantes:** Lays Leticia Alves de Souza; José Lúcio Oliveira da Silva Júnior; Gabriel Lins Alves do Nascimento; Emmanoel Barbosa; Ranie Campos Lins',
    '**Ano:** 2026',
    '## Resumo',
    f'Foram executados {len(summary)} cenários, com {args.runs} repetições cada, totalizando {integer(len(individual))} simulações principais e {integer(total_accesses)} referências. Um estudo adicional classifica misses em {len(misses)} simulações LRU. O trabalho cobre as seis atividades do roteiro: compara FIFO, LRU, LFU e Random, investiga localidade, analisa distribuições Monte Carlo, varia linhas, associatividade e bloco, implementa uma variante didática LRFU e compara acessos realistas e aleatórios. As extensões incluem mudanças de fase, poluição por varredura, sensibilidade do envelhecimento, classificação 3C por referência e reorganização dos acessos de um filtro FIR multicanal. As conclusões se restringem aos modelos simulados.',
    '**Palavras-chave:** memória cache; localidade; Monte Carlo; LRFU; filtro FIR; reprodutibilidade.',
    '## 1. Problema e hipóteses',
    'A cache mantém blocos da memória principal para reduzir buscas em níveis inferiores. Seu comportamento depende do mapeamento, da capacidade, da granularidade de transferência, da política de substituição e da sequência de referências. A taxa de acerto é hits / (hits + misses). Uma taxa maior não mede, sozinha, tempo real, energia ou custo de hardware.',
    '- H1: a classificação das políticas pode mudar conforme a carga; não há vencedora universal presumida.',
    '- H2: aumentar a probabilidade de reutilização ou de vizinhança tende a favorecer acertos no modelo, com efeitos dependentes do bloco e da organização.',
    '- H3: tamanho de bloco, quantidade de linhas e associatividade têm efeitos distintos e precisam de experimentos separados.',
    '- H4: envelhecer a frequência pode ajudar após uma mudança de fase, mas a escolha da meia-vida pode prejudicar cargas estáveis.',
    '- H5: reorganizar os laços de um FIR pode melhorar a localidade sem alterar os resultados numéricos.',
    'As hipóteses guiam a implementação e as comparações. A investigação é exploratória; não há registro prévio independente de hipóteses nem conjunto externo de validação.',
    '## 2. Metodologia e reprodutibilidade',
    table(['Parâmetro','Configuração de referência'],[['RAM','1.048.576 B (1 MiB)'],['Cache','8.192 B (8 KiB)'],['Bloco','16 B'],['Linhas','512'],['Associatividade','16 vias'],['Conjuntos','32'],['Políticas','FIFO, LRU, LFU, Random e extensão LRFU'],['Repetições por cenário',args.runs],['Referências sintéticas por repetição',args.accesses],['Referências por rastro FIR completo','65.824'],['Sementes da carga',f'{args.seed+1} a {args.seed+args.runs}'],['Semente da substituição','semente da carga + 10.000.019']]),
    'Cada repetição começa com cache vazia e usa um novo rastro. Configurações comparáveis usam a mesma semente e exatamente a mesma carga por repetição. A aleatoriedade de Random usa outro gerador, impedindo que decisões de substituição alterem o padrão de endereços. A repetição, e não cada acesso individual, é a unidade estatística. Há dependência temporal dentro de cada rastro.',
    'A função original `simulacao_monte_carlo()` foi estendida e é chamada pela nova automação. O retorno padrão continua sendo a média para preservar a interface; o modo detalhado retorna hits, misses, taxas, repetição e semente. FIFO, LRU, LFU, Random e LRFU usam o mesmo núcleo compartilhado pela GUI. Índices por dicionário aceleram buscas sem alterar a semântica; o desempate de LFU é por recência.',
    'O gerador sintético repete o último endereço, visita um vizinho com deslocamento de −16 a +16 bytes, escolhe uma das nove regiões quentes com deslocamento de 0 a 3 bytes ou sorteia um endereço uniforme. A parcela aleatória é 1 − soma das três probabilidades. O perfil base é (0,20; 0,20; 0,40). “Realista” significa apenas esse modelo sintético com localidade.',
    'Os perfis compostos reproduzem o estudo anterior. Um segundo estudo varia somente uma probabilidade, mantendo as outras duas em zero e usando o acesso aleatório como parcela complementar. Dessa forma, identifica o efeito de substituir acessos aleatórios por cada mecanismo, sem atribuir causalidade a comparações de perfis compostos.',
    'As barras de erro mostram desvio padrão amostral entre repetições, e não intervalo de confiança. A variância é calculada na escala fracionária [0,1]; o DP em tabelas usa pontos percentuais. Quartis usam interpolação linear do NumPy. Outliers seguem Q1 − 1,5×IQR e Q3 + 1,5×IQR; permanecem nos resultados, sem exclusão automática.',
    'Os intervalos de diferenças usam bootstrap pareado percentil com 5.000 reamostragens e semente registrada. Reamostram-se pares de repetições, preservando a carga comum. Os intervalos são exploratórios e não têm correção por comparações múltiplas; excluir zero descreve evidência nesse procedimento, não uma garantia geral de superioridade.',
    'O manifesto registra configurações, versões e SHA-256 do núcleo e da automação. Checkpoints atômicos por cenário permitem retomada sem misturar configurações ou versões diferentes. Contagens duplicadas de controles representam comparações planejadas, não evidências independentes adicionais.',
    '## 3. Atividade 1 — Políticas com arquitetura fixa',
    'Neste experimento somente a política muda. RAM, cache, linhas, bloco, associatividade, probabilidades e sementes permanecem fixos.',
    stats(base),image('01_politicas_fixas.png','Comparação controlada das cinco políticas, com bloco fixo de 16 B.'),
    f'A maior média nesta configuração foi {best["algoritmo"]}, com {pct(best["media"])}. Esse resultado se refere ao perfil base e não estabelece uma política universalmente melhor. A tabela pareada abaixo avalia as diferenças usando a mesma carga por repetição.',
    pair_table([r for r in paired if r['comparacao'].startswith('01_')]),
    '### 3.1 Extensão — nove blocos com capacidade fixa',
    'A comparação das quatro políticas originais foi repetida para blocos de 2 a 512 B, com capacidade de 8 KiB fixa. Em cada tamanho de bloco, só a política muda. Entre tamanhos de bloco, o número de linhas muda como consequência da capacidade fixa.',
    image('01b_blocos_capacidade_fixa.png','Políticas e tamanho de bloco com capacidade fixa.'),
    f'A maior média entre essas combinações foi {bestblock["algoritmo"]}, bloco de {bestblock["bloco_bytes"]} B, com {pct(bestblock["media"])}. Blocos maiores podem aproveitar vizinhança, mas deixam menos linhas disponíveis; o gráfico deve ser interpretado com esse compromisso.',
    '## 4. Atividade 2 — Localidade temporal, espacial e regiões quentes',
    stats(group('02_perfis')),image('02_perfis.png','Perfis compostos de acesso; mais de uma probabilidade varia entre perfis.'),
    image('02_localidade_isolada.png','Variação isolada de cada probabilidade, com as outras duas em zero.'),
    ]
    for i,label in enumerate(('temporal','espacial','regiões quentes')):
        rows=group(f'02_isolada_{i}'); first,last=rows[0],rows[-1]
        lines.append(f'No estudo isolado de {label}, a média variou de {pct(first["media"])} em p=0 para {pct(last["media"])} em p=0,8. A diferença observada foi {fmt((last["media"]-first["media"])*100)} pontos percentuais. O mecanismo complementar continua sendo o sorteio uniforme.')
    for i,name in enumerate(('Aleatório','Base','Temporal alta','Espacial alta','Regiões quentes altas')):
        lines.append(image(f'02_mapa_{i}.png',f'Mapa temporal dos blocos reais mais frequentes — {name}.'))
    lines.extend([
    'Os mapas foram gerados pela função `mapa_temporal_blocos()`, com a mesma carga da primeira repetição de cada perfil. O eixo vertical informa números reais de blocos de 16 B: não usa módulo nem mistura blocos distintos numa mesma linha identificada. São mostrados os 24 blocos mais frequentes; a última linha agrega todos os outros, portanto tem significado e escala de agregação diferentes. A última janela parcial é mantida. Cada coluna conserva o total de referências de sua janela.',
    'Repetições temporais produzem concentração em trechos do tempo; acessos espaciais favorecem endereços próximos e podem permanecer no mesmo bloco ou em blocos vizinhos; regiões quentes fazem certos blocos reaparecerem em várias janelas. No padrão uniforme, não há um pequeno conjunto fixo de blocos intencionalmente privilegiado e a linha “Outros” concentra grande parte das referências. Os mapas ilustram a carga, não o conteúdo da cache nem cada hit/miss. Como cada painel escolhe seus próprios blocos mais frequentes, posições verticais não devem ser comparadas como se fossem o mesmo endereço.',
    '## 5. Atividade 3 — Monte Carlo, distribuições e outliers',
    image('03_boxplot_politicas.png','Distribuições das taxas de acerto por política no perfil base.'),image('03_histograma.png','Histogramas das taxas por repetição, arquitetura fixa.'),
    'O boxplot mostra mediana, quartis, bigodes até as observações dentro de 1,5×IQR, média e pontos externos. Um outlier é uma repetição extrema segundo a regra, não necessariamente erro ou defeito do simulador. A robustez deve considerar simultaneamente média, dispersão, pior repetição e carga.',
    table(['Política','Mediana','Q1–Q3','Pior repetição','Melhor repetição','Outliers'],[[r['algoritmo'],pct(r['mediana']),pct(r['q1'])+'–'+pct(r['q3']),pct(r['minimo']),pct(r['maximo']),r['n_outliers']] for r in base]),
    'O arquivo `outliers.csv` identifica cenário, semente, hits, misses e taxa de cada observação marcada; `resumo_estatistico.csv` registra os limites empregados. Não foram removidas observações. Os estudos de capacidade e associatividade da próxima seção também têm 100 repetições por cenário na execução final.',
    '### 5.1 Robustez diante de mudanças de fase e varredura',
    'Na carga de fases, 80% das referências visitam oito blocos quentes, que mudam na metade da execução; 20% fazem uma varredura. Os endereços são espaçados por 512 B para competir no mesmo conjunto da arquitetura de referência. Na carga de poluição, o conjunto quente é estável e ocupa 50% das referências; a outra metade faz varredura. São testes sintéticos adversariais e declarados, não rastros representativos de todos os programas.',
    stats(group('03_robustez_phase')),image('03_boxplot_fases.png','Distribuição sob mudança de conjunto quente.'),
    stats(group('03_robustez_pollution')),image('03_boxplot_varredura.png','Distribuição sob poluição por varredura.'),
    stats(group('03_robustez_random')),image('03_boxplot_aleatorio.png','Distribuição sob carga uniforme sem localidade intencional.'),
    '## 6. Atividade 4 — Influência dos parâmetros arquiteturais',
    '### 6.1 Número de linhas',
    'Variam-se 64, 128, 256, 512, 1.024 e 2.048 linhas. Bloco de 16 B e associatividade 16 permanecem fixos; a capacidade em bytes e o número de conjuntos mudam como consequências do número de linhas.',
    stats(group('04_linhas')),image('04_linhas.png','Número de linhas com bloco e associatividade fixos.'),
    '### 6.2 Associatividade e mapeamento',
    'Mantêm-se 512 linhas de 16 B e capacidade de 8 KiB. Variam-se 1, 2, 4, 8, 16, 32, 64, 128, 256 e 512 vias. Uma via representa mapeamento direto; 512 vias, um único conjunto totalmente associativo; os valores intermediários são associativos por conjuntos. O número de conjuntos é 512 / vias.',
    stats(group('04_associatividade')),image('04_associatividade.png','Associatividade com capacidade, número de linhas e bloco fixos.'),
    'A associatividade pode aliviar conflitos de mapeamento, mas a curva depende dos endereços escolhidos e da política. O modelo não mede comparadores, área de silício, consumo ou latência de busca. Uma organização com maior taxa de acerto não é automaticamente a melhor implementação física.',
    '### 6.3 Tamanho de bloco com linhas fixas',
    'Mantêm-se 512 linhas e 16 vias; varia-se somente o tamanho de bloco como parâmetro independente. A capacidade em bytes passa de 1 KiB a 256 KiB como consequência. Esta pergunta é diferente do estudo com capacidade fixa da seção 3.1: não se pode manter simultaneamente capacidade, linhas e bloco constantes ao variar um deles.',
    stats(group('04_bloco_linhas_fixas')),image('04_bloco_linhas_fixas.png','Granularidade com número de linhas fixo; capacidade em bytes variável.'),
    '## 7. Atividade 5 — Extensão de política: LRFU didática',
    'Foi implementada uma variante didática de frequência com envelhecimento, integrada à classe `EvictionPolicy`, à GUI e ao Monte Carlo. É uma implementação nova neste projeto de uma ideia conhecida; não se reivindica a invenção científica da família LRFU.',
    'Em cada acesso residente, a pontuação é C(t) = 2^(−λ × (t − t_anterior)) × C(t_anterior) + 1. Na inserção, C=1. A política remove a menor pontuação envelhecida, com desempate por recência e inserção. λ=1/64 significa meia-vida de 64 referências globais, incluindo acessos a outros conjuntos. Na seleção, comparar log2(C) + λ×t_anterior evita subfluxo e dispensa atualizar todas as linhas a cada acesso. O termo −λ×t_atual é comum às candidatas e se cancela.',
    'A hipótese é preservar blocos frequentes sem manter indefinidamente a influência de uma fase antiga. λ=0 reduz a frequência sem envelhecimento (LFU com o mesmo desempate); meias-vidas menores privilegiam comportamento recente. A escolha da meia-vida é um parâmetro da política, não uma constante universal.',
    image('05_adaptacao_temporal.png','Uma repetição ilustrativa: taxa por janela e instante da mudança de fase.'),
    pair_table([r for r in paired if r['comparacao'].startswith('03_')]),
    stats(group('08_sensibilidade_lrfu')),image('08_sensibilidade_lrfu.png','Análise exploratória da meia-vida em 8, 32, 128 e 512 acessos.'),
    'O estudo de sensibilidade usa as mesmas sementes da carga de fases. Serve para mostrar dependência do parâmetro, sem tratar o melhor valor observado como ajuste validado em dados independentes. LFU e LRFU exigem metadados e seleção de vítima mais complexos que FIFO; os tempos Python não são custos de hardware. Na implementação, seleção LFU/LRFU percorre as vias em uma substituição; FIFO/LRU mantêm ordem explicitamente.',
    '## 8. Atividade 6 — Acesso realista versus aleatório',
    stats(group('06_realista_aleatorio')),image('06_realista_aleatorio.png','Acesso uniforme versus perfil sintético com localidade.'),
    f'Com a mesma arquitetura LRU, o realista obteve {pct(access["Realista"]["media"])} e o uniforme {pct(access["Aleatório"]["media"])}: diferença de {fmt((access["Realista"]["media"]-access["Aleatório"]["media"])*100)} pontos percentuais. A explicação é a reutilização e concentração intencionais do modelo; os mapas correspondentes são os painéis Aleatório e Base da seção 4.',
    'Como referência de ordem de grandeza, 8 KiB / 1 MiB = 0,78125% é a fração da memória que cabe na cache. Sob acesso uniforme independente, uma cache já ocupada tende a uma probabilidade de acerto dessa ordem. A partida fria e o rastro finito afetam o valor observado.',
    '## 9. Além do roteiro — Filtro FIR multicanal',
    'Foi modelado um FIR de oito coeficientes em um sinal com 128 amostras e 32 canais, armazenado em ordem amostra × canal (row-major), com elementos float32 de quatro bytes. Para cada par de saída (n,c), calcula-se y[n−7,c] = soma de h[k]×x[n−k,c], para k de 0 a 7. Há 121×32 saídas válidas.',
    'Duas versões executam exatamente os mesmos produtos e somas na mesma ordem interna: (A) canal externo e amostra interna; (B) amostra externa e canal interno. A versão B visita canais contíguos antes de avançar o tempo. Cada multiplicação-acumulação gera uma leitura de x e uma de h; cada saída gera uma escrita de y. O acumulador fica em registrador. Assim, cada rastro completo tem 121×32×17 = 65.824 referências. Não há truncamento para 10.000 referências.',
    'As 100 repetições variam os deslocamentos alinhados a 64 B das bases de entrada, coeficientes e saída, em regiões separadas da RAM. As versões e políticas compartilham o mesmo layout em cada par. As distribuições refletem variabilidade de layout e mapeamento, não 100 sinais independentes com valores influenciando os acessos. O teste numérico usa dados float32 e confere igualdade exata entre as duas ordens e concordância com convolução de referência.',
    stats(group('07_filtro_fir')),image('07_fir.png','Mesma computação FIR, ordem dos acessos diferente.'),
    pair_table([r for r in paired if r['comparacao'].startswith('FIR')]),
    'Este é um rastro derivado de um algoritmo concreto, não uma captura de endereços de uma CPU real. O modelo não inclui instruções, prefetch, vetorização, políticas reais de escrita ou otimizações do compilador. A escrita é contada como uma referência com alocação em miss, sem custo de writeback. Consequentemente, os resultados medem o efeito da ordem de referências na taxa de acerto desse modelo.',
    '## 10. Além do roteiro — Classificação de misses por referência 3C',
    'O estudo adicional usa apenas LRU e mantém uma cache sombra totalmente associativa LRU com a mesma capacidade e bloco. Se um bloco nunca foi visto, seu miss é compulsório. Para misses restantes, um hit na sombra é rotulado conflito; um miss também na sombra é rotulado capacidade. Trata-se de classificação em relação ao contrafactual FA-LRU, que pode incorporar interações entre organização e histórico; não é uma identificação física independente de cada causa.',
    ])
    buckets=defaultdict(list)
    for r in misses: buckets[r['cenario']].append(r)
    lines.append(table(['Carga e organização','Hits médios','Misses compulsórios','Conflito (referência FA-LRU)','Capacidade'],[[label]+[fmt(statistics.mean(r[k] for r in rows)) for k in ('hits','compulsorios','conflito','capacidade')] for label,rows in buckets.items()]))
    lines.extend([
    'A soma hits + compulsórios + conflito + capacidade foi verificada contra o total de referências em cada repetição. Na própria cache totalmente associativa LRU, os conflitos por essa definição são zero. A comparação da carga de fases por conjuntos com a totalmente associativa ajuda a distinguir a pressão de um conjunto específico da ocupação global.',
    '## 11. Verificação e limites',
    '- Políticas comparadas acesso a acesso com um modelo independente simples, incluindo o cálculo LRFU pela soma explícita das contribuições do histórico residente.',
    '- Endereçamento conferido por reconstrução tag/conjunto/offset; configurações inválidas rejeitadas; contadores e partida fria conferidos.',
    '- Reprodução de amostras históricas das quatro políticas originais, incluindo a sequência global original de Random.',
    '- Mesmas cargas garantidas entre políticas e RNGs separados; equivalência de multiconjunto de referências e de resultado numérico do FIR.',
    '- Testes de casos conhecidos de misses compulsórios, de conflito e de capacidade.',
    'O estudo não mede latências, ciclos de CPU, energia, hierarquia multinível ou desempenho de hardware real. A memória de dados é byte-endereçada, e não se modelam valores armazenados, exceto no teste de equivalência numérica do FIR. O aquecimento não é descartado: os resultados incluem partida fria. As sementes reproduzem os cenários neste ambiente, mas resultados de RNG e bibliotecas podem depender da versão; consulte o manifesto.',
    'Cenários com os mesmos parâmetros reaparecem como controles em atividades diferentes. Não devem ser somados como amostras independentes. No FIR, a troca de laços é controlada, porém o rastro não é extraído de um executável. A análise LRFU é exploratória em cargas escolhidas para observar frequência e adaptação; bons resultados nelas não validam superioridade universal.',
    '## 12. Conclusões',
    f'Na arquitetura fixa e perfil base, a maior média foi {best["algoritmo"]} ({pct(best["media"])}). Nos nove blocos com capacidade fixa e políticas originais, destacou-se {bestblock["algoritmo"]} com {bestblock["bloco_bytes"]} B ({pct(bestblock["media"])}). A conclusão prática deve considerar a carga, a dispersão e os compromissos de organização, e não apenas o maior número de uma tabela.',
    'A localidade e a ordem das referências são variáveis centrais do estudo. Os experimentos separados de linhas, associatividade e bloco explicitam quais quantidades são controladas e quais mudam como consequência. A política LRFU acrescenta uma forma de balancear frequência e recência, com sensibilidade mensurável ao envelhecimento. O FIR fornece um exemplo verificável de como investigar uma otimização de programa através do modelo de cache.',
    'As seis atividades foram cobertas, e as extensões acrescentam comparações pareadas, envelhecimento parametrizado, comportamento temporal após mudança de fase, classificação por cache sombra, validação por modelo de referência e um caso de processamento digital de sinais. Todos os números desta versão são gerados dos resultados efetivamente executados.',
    '## 13. Matriz de atendimento',
    table(['Item','Entrega'],[['1 — Algoritmos','Arquitetura fixa, gráfico por política, comparação pareada e discussão; seção 3'],['2 — Localidade','Perfis compostos, variação isolada, cinco mapas de blocos reais; seção 4'],['3 — Monte Carlo','100 repetições, CSV individual, quartis, variância, histogramas, boxplots e outliers; seção 5'],['4 — Arquitetura','Linhas, vias e bloco em estudos separados; direta, conjuntos e totalmente associativa; seção 6'],['5 — Nova política','LRFU integrada ao núcleo e GUI; comparação Monte Carlo e sensibilidade; seção 7'],['6 — Realista/aleatório','Comparação controlada e interpretação dos mapas; seção 8'],['Extensões','Fases, varredura, IC pareado, FIR multicanal, 3C, checkpoints e testes; seções 5, 7, 9 e 10']]),
    '## Referências',
    'OLIVEIRA, José Paulo Gonçalves de. *Simulador de Memória Cache — Projeto acadêmico*. Material fornecido na disciplina, arquivo README_Simulador_Memoria_Cache.pdf, 16 páginas. Foram usados a descrição do núcleo, a simulação Monte Carlo, as limitações e o princípio de experimentação controlada (p. 13–14).',
    'OLIVEIRA, José Paulo G. de. *Sistemas Computacionais e Sistemas Embarcados de Tempo Real — Projetos com FreeRTOS*. Seção 4.10, “Memória cache”, arquivo Memória cache - teoria.pdf fornecido na disciplina, p. 216 e seguintes. Dados editoriais completos não constam no recorte consultado.',
    'Roteiro de seis atividades práticas fornecido pelo professor e transcrito pela equipe. As expressões e implementações adicionais deste projeto são descritas nas seções correspondentes; não se atribui aos materiais a especificação dos experimentos adicionais.',
    '## Apêndice A — Todos os cenários',
    table(['ID','Experimento / cenário','Política','Cache B','Linhas','Bloco B','Vias','Média','DP p.p.'],[[r['cenario_id'],r['experimento']+' / '+r['cenario'],r['algoritmo'],r['cache_bytes'],r['cache_lines'],r['bloco_bytes'],r['associatividade'],pct(r['media']),fmt(r['desvio_padrao']*100,3)] for r in summary]),
    '## Apêndice B — Arquivos e reprodução',
    '- [Resultados individuais](resultados_individuais.csv)',
    '- [Resumo estatístico](resumo_estatistico.csv)',
    '- [Outliers identificados](outliers.csv)',
    '- [Comparações pareadas](comparacoes_pareadas.csv)',
    '- [Classificação 3C](classificacao_3c.csv)',
    '- [Configurações, versões e hashes](manifesto.json)',
    'Para reproduzir: `python -B experimentos_completos.py --runs 100 --accesses 10000 --output Resultados_Automaticos/nova_execucao`. Para retomar, repita o comando com a mesma pasta e código. Para uma verificação rápida: `python -B experimentos_completos.py --quick --output Resultados_Automaticos/teste_rapido`. A verificação rápida não substitui os resultados completos.',
    'Testes: `python -B -m unittest test_cache_core -v`. Interface: `python cache_simulator_GUI.py`. O núcleo automatizado usa Matplotlib Agg e não precisa abrir janelas. A GUI precisa de CustomTkinter; veja requirements.txt.',
    ])
    # Discussão quantitativa construída a partir dos resultados finais.
    marker='## 12. Conclusões'
    for exp,title in (('04_linhas','número de linhas'),('04_associatividade','associatividade'),('04_bloco_linhas_fixas','bloco com linhas fixas')):
        rows=group(exp); first,last=rows[0],rows[-1]; peak=max(rows,key=lambda r:r['media'])
        paragraph=f"No estudo de {title}, a média passou de {pct(first['media'])} no primeiro valor testado para {pct(last['media'])} no último; a maior média observada foi {pct(peak['media'])}, em {peak['cenario']}. Isso descreve esta carga, sem presumir crescimento estritamente monotônico nem benefício universal."
        lines.insert(lines.index(marker),paragraph)
    worst=[]
    for r in base:
        candidates=[x for x in individual if x['cenario_id']==r['cenario_id']]
        low=min(candidates,key=lambda x:x['taxa_acerto'])
        worst.append(f"{r['algoritmo']}: semente {low['semente']}, {pct(low['taxa_acerto'])}")
    paragraph='As piores repetições do perfil base foram '+ '; '.join(worst)+'. Como as cargas são pareadas, extremos compartilhados podem refletir a mesma sequência de acessos desfavorável. Não se atribui a causa de um extremo somente pela taxa agregada; o arquivo de outliers permite reproduzir a semente.'
    lines.insert(lines.index('### 5.1 Robustez diante de mudanças de fase e varredura'),paragraph)
    lrfu=next(r for r in base if r['algoritmo']=='LRFU')
    lfu=next(r for r in base if r['algoritmo']=='LFU')
    phase={r['algoritmo']:r for r in group('03_robustez_phase')}
    paragraph=f"Na carga base, LRFU obteve {pct(lrfu['media'])}, enquanto LFU obteve {pct(lfu['media'])}; a diferença descritiva LRFU menos LFU é {fmt((lrfu['media']-lfu['media'])*100)} p.p. Após introduzir a carga de fases, as médias foram {pct(phase['LRFU']['media'])} para LRFU e {pct(phase['LFU']['media'])} para LFU, diferença de {fmt((phase['LRFU']['media']-phase['LFU']['media'])*100)} p.p. Esses contrastes tornam explícitos os ganhos e perdas da política em vez de selecionar apenas um cenário favorável. Os ICs apresentados usam LRU como referência."
    lines.insert(lines.index('## 8. Atividade 6 — Acesso realista versus aleatório'),paragraph)
    frows={ (r['carga'],r['algoritmo']):r for r in group('07_filtro_fir') }
    before=frows[('fir_canal','LRU')]; after=frows[('fir_amostra','LRU')]
    miss_reduction=(after['media']-before['media'])/(1-before['media']) if before['media']<1 else 0
    paragraph=f"Na LRU, a troca de ordem levou a média de {pct(before['media'])} para {pct(after['media'])}: {fmt((after['media']-before['media'])*100)} pontos percentuais de acertos a mais e {pct(miss_reduction)} de redução relativa da taxa de misses. Isso não significa a mesma redução de tempo de execução. Avançar uma amostra do mesmo canal salta 128 B (32 canais × 4 B), ou oito blocos de 16 B; com 32 conjuntos, essa progressão visita apenas quatro índices por posição de canal. Esse padrão favorece pressão concentrada nos conjuntos. Percorrer canais contíguos aproveita os quatro elementos float32 que cabem em cada bloco e aproxima reutilizações."
    lines.insert(lines.index('## 10. Além do roteiro — Classificação de misses por referência 3C'),paragraph)
    for exp in ('03_robustez_phase','03_robustez_pollution','03_robustez_random'):
        rows=group(exp); winner=max(rows,key=lambda r:r['media']); loser=min(rows,key=lambda r:r['media'])
        # Síntese quantitativa sem escolher a narrativa antes dos resultados.
        lines.insert(lines.index('## 12. Conclusões')+1,f'Na carga {exp}, a maior média foi {winner["algoritmo"]} ({pct(winner["media"])}), e a menor, {loser["algoritmo"]} ({pct(loser["media"])}).')
    text='\n\n'.join(lines)+'\n'
    (output/'Relatorio_Completo.md').write_text(text,encoding='utf-8')
    (output/'Relatorio_Completo.html').write_text(markdown_html(text),encoding='utf-8')
    (output/'relatorio_resultados.md').write_text('# Resumo dos resultados completos\n\n[Relatório completo](Relatorio_Completo.md)\n\n'+stats(summary)+'\n',encoding='utf-8')
