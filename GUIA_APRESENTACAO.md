# Guia de apresentação — estudo completo de cache

São 111 cenários com 100 repetições cada e 400 simulações adicionais de classificação 3C. O relatório final inclui a matriz de atendimento das seis atividades. Resultados finais: `Resultados_Automaticos/2026-11-14_estudo_completo`.

## Roteiro (12 a 15 minutos)

1. **Conceitos e configuração (1 min):** hit, miss, linha, bloco e conjunto; RAM de 1 MiB, cache de 8 KiB, bloco de 16 B, 512 linhas, 16 vias e 32 conjuntos.
2. **Políticas (2 min):** gráfico de arquitetura fixa; só a política muda. Mesmos rastros por repetição. Melhor média no perfil base: LFU (76.59%). Mostrar também as diferenças pareadas e seus intervalos.
3. **Localidade (2 min):** curvas de probabilidades isoladas e dois mapas. Distinguir perfis compostos de variação isolada. Mapas mostram números reais de blocos e a carga, não o estado da cache; a linha Outros agrega muitas posições.
4. **Monte Carlo (2 min):** boxplots de base e fases. Explicar média, mediana, variância, DP, quartis e outliers. Todas as repetições começam frias; nenhum extremo foi removido.
5. **Arquitetura (2 min):** curvas de linhas e associatividade. Uma via é direta, 512 é totalmente associativa. Comparar bloco com capacidade fixa e bloco com linhas fixas: são perguntas diferentes.
6. **LRFU (2 min):** mostrar atualização da pontuação e meia-vida de 64 acessos globais. Apresentar sensibilidade, ganhos e perdas. A família LRFU é conhecida; a contribuição é implementar e avaliar a variante neste projeto.
7. **Além do roteiro (2 min):** mudança de fase, varredura, FIR e misses 3C. No FIR, mostrar as duas ordens de laços e o teste de igualdade numérica. Diferença LRU: 9.079 pontos percentuais de acertos.
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
