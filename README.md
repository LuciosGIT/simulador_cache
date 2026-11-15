# Simulador de memória cache — estudo completo

Projeto de Organização de Computadores (POLI/UPE). Cobre as seis atividades do professor e acrescenta experimentos de adaptação, análise pareada, classificação de misses e localidade em filtro FIR multicanal.

## Entrega principal

- [Relatório final](Relatorio_Final_Organizacao_de_Computadores.md) e versão PDF com o mesmo nome.
- [Resultados completos de 14/11/2026](Resultados_Automaticos/2026-11-14_estudo_completo/Relatorio_Completo.md).
- [Guia para apresentação](GUIA_APRESENTACAO.md).
- Dados individuais, estatísticas, outliers, comparações pareadas, classificação 3C, manifesto e figuras na pasta da execução completa.

A pasta `2026-11-14_validacao_rapida` contém somente uma verificação dßo fluxo com três repetições. Use a pasta `2026-11-14_estudo_completo` para os resultados finais com 100 repetições. As pastas de 10 e 13/11 preservam o estudo anterior.

## Instalação e uso

Use Python 3.12 (versão validada nesta entrega). Em PowerShell, na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe cache_simulator_GUI.py
```

A interface usa CustomTkinter. A versão atual não depende de Dear PyGui. O Python precisa incluir Tkinter para a GUI; a automação usa backend Agg, sem abrir janelas.

Execução completa:

```powershell
.\.venv\Scripts\python.exe -B experimentos_completos.py --runs 100 --accesses 10000 --output Resultados_Automaticos/nova_execucao
```

A execução padrão tem 111 cenários × 100 repetições, mais 400 simulações LRU para classificação de misses. Os rastros sintéticos têm 10.000 referências; cada rastro FIR completo tem 65.824. Repita o mesmo comando para retomar os cenários concluídos. Configuração ou código diferente exige outra pasta. Cada cenário é salvo atomicamente após suas 100 repetições; uma interrupção no meio dele refaz somente esse cenário. Um marcador `conclusao.json` indica que gráficos e relatório foram concluídos.

Validação rápida e testes:

```powershell
.\.venv\Scripts\python.exe -B -m unittest test_cache_core -v
.\.venv\Scripts\python.exe -B experimentos_completos.py --quick --output Resultados_Automaticos/teste_rapido
.\.venv\Scripts\python.exe -B verificar_entrega.py --output Resultados_Automaticos/2026-11-14_estudo_completo
```

## Arquivos do código

| Arquivo | Responsabilidade |
|---|---|
| `cache_core.py` | Cache, políticas e função compartilhada `simulacao_monte_carlo()` |
| `cache_simulator_GUI.py` | Interface e diagramas; inclui LRFU |
| `cache_visualizacao.py` | Agregação de mapas sem colisão por módulo e sem perder a janela parcial |
| `experimentos_completos.py` | 111 cenários, rastros FIR, checkpoints, gráficos e estatística |
| `relatorio_completo.py` | Relatório Markdown e HTML gerado dos dados reais |
| `test_cache_core.py` | Modelo independente, endereçamento, RNG, FIR e classificação 3C |
| `verificar_entrega.py` | Auditoria independente dos arquivos e estatísticas exportadas |
| `automatizar_experimentos.py` | Automação histórica de três grupos, preservada |

## Desenho experimental

O estudo separa três perguntas: variar linhas com bloco fixo; variar vias com linhas e capacidade fixas; variar bloco com linhas fixas. Também mantém o estudo de blocos com capacidade fixa, explicitando que o número de linhas muda nesse caso. Comparações de políticas compartilham a mesma sequência de referências por repetição. Carga e substituição aleatória usam geradores distintos.

A extensão LRFU usa frequência com envelhecimento exponencial, meia-vida padrão de 64 acessos globais. O trabalho não reivindica a invenção da família LRFU e mede também suas limitações. Os intervalos bootstrap pareados são exploratórios, sem correção por múltiplas comparações.

No FIR, as duas versões calculam a mesma saída; muda apenas a ordem dos laços de amostra e canal. Leituras e escritas são referências de dados idealizadas. A classificação 3C usa cache sombra totalmente associativa LRU e deve ser entendida em relação a essa referência. O simulador mede taxa de acerto, não tempo de CPU ou desempenho real de hardware.

