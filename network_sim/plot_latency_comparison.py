"""
Genereaza un grafic comparativ al distributiei latentelor intre scenariul
de retea rapida ("5G-like") si cel congestionat (cu jitter real), pornind
de la CSV-urile produse de xml_to_csv.py.

Rulare:
    python3 plot_latency_comparison.py

Scrie network_sim/latency_comparison.png (300 DPI, gata de pus intr-un
document Word/LaTeX).
"""

import csv
import os
import statistics

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

HERE = os.path.dirname(os.path.abspath(__file__))

# paleta validata (categorical, slot 1 si 2) din skill-ul de dataviz
COLOR_FAST = "#2a78d6"       # albastru - retea rapida
COLOR_CONGESTED = "#eb6834"  # portocaliu - retea congestionata
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
SURFACE = "#fcfcfb"
GRID = "#e4e2dd"


def load_latencies(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [float(row["latency_ms"]) for row in csv.DictReader(f)]


def main():
    fast = load_latencies(os.path.join(HERE, "latency_output.csv"))
    congested = load_latencies(os.path.join(HERE, "latency_congestionat.csv"))

    fast_mean, fast_std = statistics.mean(fast), statistics.stdev(fast)
    cong_mean, cong_std = statistics.mean(congested), statistics.stdev(congested)

    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    bin_width = 1.0  # ms, acelasi bin-width folosit in FlowMonitor
    all_vals = fast + congested
    bins = [i * bin_width for i in range(int(min(all_vals)), int(max(all_vals)) + 2)]

    ax.hist(
        fast,
        bins=bins,
        color=COLOR_FAST,
        alpha=0.9,
        label=f"Rețea rapidă (“5G-like”)  —  medie {fast_mean:.1f} ms, deviație {fast_std:.2f} ms",
        edgecolor=SURFACE,
        linewidth=0.3,
    )
    ax.hist(
        congested,
        bins=bins,
        color=COLOR_CONGESTED,
        alpha=0.9,
        label=f"Rețea congestionată (jitter)  —  medie {cong_mean:.1f} ms, deviație {cong_std:.2f} ms",
        edgecolor=SURFACE,
        linewidth=0.3,
    )

    # linii verticale la medie, cu eticheta directa
    ax.axvline(fast_mean, color=COLOR_FAST, linestyle="--", linewidth=1.2, alpha=0.85)
    ax.axvline(cong_mean, color=COLOR_CONGESTED, linestyle="--", linewidth=1.2, alpha=0.85)

    ax.set_xlabel("Latență (ms)", color=TEXT_PRIMARY, fontsize=11)
    ax.set_ylabel("Număr de pachete", color=TEXT_PRIMARY, fontsize=11)
    ax.set_title(
        "Distribuția latenței de livrare a datelor — simulare ns-3\n"
        "rețea rapidă vs. rețea congestionată (trafic de fond în rafale)",
        color=TEXT_PRIMARY,
        fontsize=12.5,
        pad=14,
        loc="left",
    )

    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(GRID)

    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9.5)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5))

    legend = ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        frameon=False,
        fontsize=9.5,
        labelcolor=TEXT_SECONDARY,
        ncol=1,
    )

    fig.tight_layout()

    out_path = os.path.join(HERE, "latency_comparison.png")
    fig.savefig(out_path, facecolor=SURFACE, bbox_inches="tight")
    print(f"[*] Grafic salvat: {out_path}")
    print(f"    5G rapid:      n={len(fast)}, medie={fast_mean:.2f}ms, stdev={fast_std:.2f}ms")
    print(f"    Congestionat:  n={len(congested)}, medie={cong_mean:.2f}ms, stdev={cong_std:.2f}ms")


if __name__ == "__main__":
    main()
