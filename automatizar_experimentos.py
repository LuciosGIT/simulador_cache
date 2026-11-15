from __future__ import annotations

import argparse
import csv
import os
import random
import statistics
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

# Configurações do ambiente antes de importar a interface.
os.environ["CACHE_SIMULATOR_BATCH"] = "1"

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "simulador_cache_matplotlib"),
)

from cache_core import (  # noqa: E402
    CacheMemory,
    gerar_padrao_realista,
)
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


RAM_BYTES = 1_048_576
CACHE_BYTES = 8_192
ASSOCIATIVITY = 16

BLOCK_SIZES = (
    2, 4, 8, 16, 32, 64, 128, 256, 512
)

BASE_PROBABILITIES = (0.20, 0.20, 0.40)

HOT_REGIONS = [
    64,
    1024,
    8192,
    32768,
    131072,
    262144,
    524288,
    786432,
    983040,
]


def executar_uma_simulacao(
    *,
    seed: int,
    accesses: int,
    block_size: int,
    policy: str,
    probabilities: tuple[float, float, float],
) -> float:
    """Executa uma simulação e retorna a taxa de acerto."""

    random.seed(seed)

    pattern = gerar_padrao_realista(
        accesses,
        RAM_BYTES,
        HOT_REGIONS,
        probabilities,
    )

    cache = CacheMemory(
        CACHE_BYTES,
        block_size,
        ASSOCIATIVITY,
        policy,
    )

    for address in pattern:
        cache.request_access(address)

    return cache.hit_rate


def adicionar_resultados(
    rows: list[dict[str, object]],
    *,
    experiment: str,
    scenario: str,
    policy: str,
    block_size: int,
    probabilities: tuple[float, float, float],
    runs: int,
    accesses: int,
    seed_base: int,
) -> None:
    """Executa várias simulações e armazena os resultados."""

    for repetition in range(1, runs + 1):
        seed = seed_base + repetition

        hit_rate = executar_uma_simulacao(
            seed=seed,
            accesses=accesses,
            block_size=block_size,
            policy=policy,
            probabilities=probabilities,
        )

        rows.append(
            {
                "experimento": experiment,
                "cenario": scenario,
                "algoritmo": policy,
                "tamanho_bloco_bytes": block_size,
                "repeticao": repetition,
                "semente": seed,
                "acessos_cpu": accesses,
                "ram_bytes": RAM_BYTES,
                "cache_bytes": CACHE_BYTES,
                "associatividade": ASSOCIATIVITY,
                "prob_temporal": probabilities[0],
                "prob_espacial": probabilities[1],
                "prob_hot_regions": probabilities[2],
                "taxa_acerto": hit_rate,
            }
        )


def resumir(
    rows: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    """Calcula estatísticas agrupadas por experimento e cenário."""

    groups: dict[tuple[object, ...], list[float]] = defaultdict(list)

    for row in rows:
        key = (
            row["experimento"],
            row["cenario"],
            row["algoritmo"],
            row["tamanho_bloco_bytes"],
            row["acessos_cpu"],
            row["prob_temporal"],
            row["prob_espacial"],
            row["prob_hot_regions"],
        )

        groups[key].append(float(row["taxa_acerto"]))

    summary = []

    for key, values in sorted(
        groups.items(),
        key=lambda item: tuple(map(str, item[0])),
    ):
        (
            experiment,
            scenario,
            policy,
            block_size,
            accesses,
            temporal,
            spatial,
            hot,
        ) = key

        summary.append(
            {
                "experimento": experiment,
                "cenario": scenario,
                "algoritmo": policy,
                "tamanho_bloco_bytes": block_size,
                "acessos_cpu": accesses,
                "prob_temporal": temporal,
                "prob_espacial": spatial,
                "prob_hot_regions": hot,
                "n_simulacoes": len(values),
                "taxa_media": statistics.mean(values),
                "desvio_padrao": (
                    statistics.stdev(values)
                    if len(values) > 1
                    else 0.0
                ),
                "variancia": (
                    statistics.variance(values)
                    if len(values) > 1
                    else 0.0
                ),
                "taxa_minima": min(values),
                "taxa_maxima": max(values),
            }
        )

    return summary


def salvar_csv(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    """Salva os resultados em um arquivo CSV."""

    if not rows:
        return

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0]),
        )

        writer.writeheader()
        writer.writerows(rows)


def salvar_grafico_politicas(
    summary: list[dict[str, object]],
    output: Path,
) -> None:
    """Gera gráfico comparando as políticas de substituição."""

    rows = [
        row
        for row in summary
        if row["experimento"] == "politicas_substituicao"
    ]

    figure, axis = plt.subplots(figsize=(10, 6))

    for policy in ("FIFO", "LRU", "LFU", "Random"):
        data = sorted(
            (
                row
                for row in rows
                if row["algoritmo"] == policy
            ),
            key=lambda row: int(row["tamanho_bloco_bytes"]),
        )

        axis.errorbar(
            [
                row["tamanho_bloco_bytes"]
                for row in data
            ],
            [
                float(row["taxa_media"]) * 100
                for row in data
            ],
            yerr=[
                float(row["desvio_padrao"]) * 100
                for row in data
            ],
            marker="o",
            capsize=3,
            label=policy,
        )

    axis.set_xscale("log", base=2)
    axis.set_xlabel("Tamanho do bloco (bytes)")
    axis.set_ylabel("Taxa média de acerto (%)")
    axis.set_title(
        "Políticas de substituição: média ± desvio padrão"
    )
    axis.grid(True, alpha=0.25)
    axis.legend()

    figure.tight_layout()
    figure.savefig(output, dpi=180)
    plt.close(figure)


def salvar_grafico_cenarios(
    summary: list[dict[str, object]],
    experiment: str,
    title: str,
    output: Path,
) -> None:
    """Gera gráfico comparando diferentes cenários."""

    rows = [
        row
        for row in summary
        if row["experimento"] == experiment
    ]

    figure, axis = plt.subplots(figsize=(10, 6))

    labels = [
        str(row["cenario"])
        for row in rows
    ]

    means = [
        float(row["taxa_media"]) * 100
        for row in rows
    ]

    deviations = [
        float(row["desvio_padrao"]) * 100
        for row in rows
    ]

    bars = axis.bar(
        labels,
        means,
        yerr=deviations,
        capsize=4,
        color="#0072ce",
    )

    axis.bar_label(
        bars,
        labels=[
            f"{value:.2f}%"
            for value in means
        ],
        padding=3,
        fontsize=8,
    )

    axis.set_ylim(
        0,
        min(
            105,
            max(means, default=0)
            + max(10, max(deviations, default=0) * 3),
        ),
    )

    axis.set_ylabel("Taxa média de acerto (%)")
    axis.set_title(title)
    axis.grid(axis="y", alpha=0.25)

    figure.tight_layout()
    figure.savefig(output, dpi=180)
    plt.close(figure)


def salvar_mapa_calor(
    *,
    probabilities: tuple[float, float, float],
    accesses: int,
    seed: int,
    title: str,
    output: Path,
) -> None:
    """Gera mapa de calor dos acessos à memória."""

    random.seed(seed)

    pattern = gerar_padrao_realista(
        accesses,
        RAM_BYTES,
        HOT_REGIONS,
        probabilities,
    )

    block_size = 16
    window = 50
    block_count = 64

    window_count = max(
        1,
        len(pattern) // window,
    )

    heatmap = [
        [0 for _ in range(window_count)]
        for _ in range(block_count)
    ]

    for position, address in enumerate(
        pattern[: window_count * window]
    ):
        block_index = (
            (address // block_size) % block_count
        )

        time_window = position // window

        heatmap[block_index][time_window] += 1

    figure, axis = plt.subplots(figsize=(11, 5))

    image = axis.imshow(
        heatmap,
        cmap="magma",
        aspect="auto",
        origin="lower",
    )

    figure.colorbar(
        image,
        ax=axis,
        label="Acessos por bloco",
    )

    axis.set_title(title)
    axis.set_xlabel(
        f"Janelas temporais ({window} acessos/janela)"
    )
    axis.set_ylabel("Classe do bloco (número do bloco módulo 64)")

    figure.tight_layout()
    figure.savefig(output, dpi=180)
    plt.close(figure)


def salvar_relatorio(
    path: Path,
    summary: list[dict[str, object]],
    runs: int,
    accesses: int,
) -> None:
    """Gera relatório em Markdown com os resultados."""

    lines = [
        "# Resultados automáticos — Simulador de Memória Cache",
        "",
        "## Configuração fixa",
        "",
        (
            f"- RAM: {RAM_BYTES} bytes; "
            f"cache: {CACHE_BYTES} bytes; "
            f"associatividade: {ASSOCIATIVITY}."
        ),
        (
            f"- {runs} simulações Monte Carlo por cenário; "
            f"{accesses} acessos por simulação."
        ),
        (
            "- Cada repetição utiliza uma sequência de acessos "
            "reproduzível para comparar os algoritmos."
        ),
        "",
        "## Resumo estatístico",
        "",
        (
            "| Experimento | Cenário | Algoritmo | Bloco (B) "
            "| Média | Desvio padrão | Variância | Mín. | Máx. |"
        ),
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in summary:
        lines.append(
            "| {experimento} | {cenario} | {algoritmo} | "
            "{tamanho_bloco_bytes} | {media:.2f}% | "
            "{std:.2f}% | {variancia:.6f} | "
            "{minimum:.2f}% | {maximum:.2f}% |".format(
                experimento=row["experimento"],
                cenario=row["cenario"],
                algoritmo=row["algoritmo"],
                tamanho_bloco_bytes=row["tamanho_bloco_bytes"],
                media=float(row["taxa_media"]) * 100,
                std=float(row["desvio_padrao"]) * 100,
                variancia=float(row["variancia"]),
                minimum=float(row["taxa_minima"]) * 100,
                maximum=float(row["taxa_maxima"]) * 100,
            )
        )

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    """Lê os argumentos informados no terminal."""

    parser = argparse.ArgumentParser(
        description=(
            "Executa os experimentos propostos "
            "para o simulador de cache."
        )
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=100,
        help="Simulações Monte Carlo por cenário (padrão: 100).",
    )

    parser.add_argument(
        "--accesses",
        type=int,
        default=10_000,
        help="Acessos por simulação (padrão: 10000).",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="Semente inicial para resultados reproduzíveis.",
    )

    parser.add_argument(
        "--only",
        choices=("all", "policies", "locality", "access"),
        default="all",
        help="Executa somente um grupo de experimentos.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Diretório de saída. "
            "Por padrão, cria uma pasta com data e hora."
        ),
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Teste rápido: 10 simulações e 2000 acessos.",
    )

    args = parser.parse_args()

    if args.quick:
        args.runs = 10
        args.accesses = 2_000

    if args.runs <= 0 or args.accesses <= 0:
        parser.error(
            "--runs e --accesses devem ser maiores que zero."
        )

    return args


def main() -> None:
    """Função principal que executa os experimentos."""

    args = parse_args()

    output = (
        args.output
        or Path("Resultados_Automaticos")
        / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    )

    output.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows: list[dict[str, object]] = []

    if args.only in ("all", "policies"):
        print(
            "[1/3] Comparando as políticas de substituição..."
        )

        for policy in ("FIFO", "LRU", "LFU", "Random"):
            for block_size in BLOCK_SIZES:
                adicionar_resultados(
                    rows,
                    experiment="politicas_substituicao",
                    scenario="base",
                    policy=policy,
                    block_size=block_size,
                    probabilities=BASE_PROBABILITIES,
                    runs=args.runs,
                    accesses=args.accesses,
                    seed_base=args.seed,
                )

    if args.only in ("all", "locality"):
        print("[2/3] Medindo o efeito da localidade...")

        scenarios = {
            "Aleatorio": (0.00, 0.00, 0.00),
            "Base": BASE_PROBABILITIES,
            "Temporal alta": (0.70, 0.10, 0.10),
            "Espacial alta": (0.10, 0.70, 0.10),
            "Hot regions altas": (0.10, 0.10, 0.70),
        }

        for scenario, probabilities in scenarios.items():
            adicionar_resultados(
                rows,
                experiment="efeito_localidade",
                scenario=scenario,
                policy="LRU",
                block_size=16,
                probabilities=probabilities,
                runs=args.runs,
                accesses=args.accesses,
                seed_base=args.seed,
            )

    if args.only in ("all", "access"):
        print(
            "[3/3] Comparando acesso realista e aleatório..."
        )

        scenarios = (
            ("Realista", BASE_PROBABILITIES),
            ("Aleatorio", (0.00, 0.00, 0.00)),
        )

        for scenario, probabilities in scenarios:
            adicionar_resultados(
                rows,
                experiment="realista_vs_aleatorio",
                scenario=scenario,
                policy="LRU",
                block_size=16,
                probabilities=probabilities,
                runs=args.runs,
                accesses=args.accesses,
                seed_base=args.seed,
            )

    summary = resumir(rows)

    salvar_csv(
        output / "resultados_individuais.csv",
        rows,
    )

    salvar_csv(
        output / "resumo_estatistico.csv",
        summary,
    )

    salvar_relatorio(
        output / "relatorio_resultados.md",
        summary,
        args.runs,
        args.accesses,
    )

    if args.only in ("all", "policies"):
        salvar_grafico_politicas(
            summary,
            output / "grafico_politicas.png",
        )

    if args.only in ("all", "locality"):
        salvar_grafico_cenarios(
            summary,
            "efeito_localidade",
            "Efeito da localidade (LRU, bloco de 16 B)",
            output / "grafico_localidade.png",
        )

    if args.only in ("all", "access"):
        salvar_grafico_cenarios(
            summary,
            "realista_vs_aleatorio",
            "Acesso realista versus aleatório (LRU, bloco de 16 B)",
            output / "grafico_realista_vs_aleatorio.png",
        )

        salvar_mapa_calor(
            probabilities=BASE_PROBABILITIES,
            accesses=args.accesses,
            seed=args.seed + 1,
            title="Mapa de calor — padrão realista",
            output=output / "mapa_calor_realista.png",
        )

        salvar_mapa_calor(
            probabilities=(0.00, 0.00, 0.00),
            accesses=args.accesses,
            seed=args.seed + 1,
            title="Mapa de calor — padrão aleatório",
            output=output / "mapa_calor_aleatorio.png",
        )

    print(
        f"Concluído. Arquivos gerados em: {output.resolve()}"
    )


if __name__ == "__main__":
    main()
