"""
Figura 3 — Correlações temporais CAT × entradas BF
====================================================

Ajuste editorial: em vez de afirmar "ausência", reconhecer sinal fraco e
não-monotônico (medianas entre -0.13 e +0.19), dispersão amplamente sobreposta
ao zero. Insuficiente para sustentar hipótese direcional; suficiente para
merecer investigação futura, não usado neste reúso.

Fonte: data/processed/monstro/correlacoes_municipais.parquet
Saída: outputs/figuras/fig3_correlacoes_temporais.png
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "monstro"
OUT_DIR = BASE_DIR / "outputs" / "figuras"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LAGS = [0, 1, 2, 3, 6]

corr = pd.read_parquet(DATA_DIR / "correlacoes_municipais.parquet")

dados_por_lag = []
labels = []
for lag in LAGS:
    col = f"corr_n_cat_lag{lag}"
    if col not in corr.columns:
        continue
    valores = corr[col].dropna().values
    dados_por_lag.append(valores)
    labels.append(f"Lag {lag}\n(n={len(valores):,})".replace(",", "."))

fig, ax = plt.subplots(figsize=(11, 7))

bp = ax.boxplot(
    dados_por_lag,
    vert=False,
    labels=labels,
    widths=0.55,
    patch_artist=True,
    showfliers=False,
    medianprops=dict(color="#222222", linewidth=1.6),
    boxprops=dict(facecolor="#c6dbef", edgecolor="#2b5f8a", linewidth=0.8),
    whiskerprops=dict(color="#2b5f8a", linewidth=0.8),
    capprops=dict(color="#2b5f8a", linewidth=0.8),
)

ax.axvline(x=0, color="#c0392b", linewidth=1.2, linestyle="--", alpha=0.8, zorder=2)
ax.text(0, len(dados_por_lag) + 0.55, "  ρ = 0",
        fontsize=9, color="#c0392b", va="bottom", ha="left")

for i, valores in enumerate(dados_por_lag):
    mediana = np.median(valores)
    ax.text(mediana, i + 1 + 0.28, f"mediana {mediana:+.3f}",
            fontsize=8, color="#222222", ha="center")

ax.set_xlabel("Correlação de Spearman (CAT × entradas BF) por município", fontsize=11)
ax.set_title(
    "Sinal temporal fraco e não-monotônico entre CAT e entradas no BF\n"
    "Medianas entre −0,13 e +0,19; dispersão amplamente sobreposta ao zero",
    fontsize=13, pad=15, loc="left",
)

ax.set_xlim(-1, 1)
ax.grid(axis="x", alpha=0.3, linestyle="--")
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)

fig.text(
    0.02, 0.01,
    "Fonte: elaboração própria. Correlação de Spearman calculada município a município, "
    "entre a série mensal de CATs e a série mensal de entradas no BF (NIS aparecendo pela primeira vez). "
    "A distribuição centrada em torno do zero, com medianas entre −0,13 e +0,19 e dispersão ampla, "
    "indica ausência de sinal direcional consistente na frequência mensal — o que motivou o pivô para "
    "a análise estrutural (Figura 1). O sinal fraco no lag 6 (+0,194) merece investigação futura, "
    "possivelmente com granularidade trimestral ou anual, fora do escopo deste reúso. "
    "Outliers ocultos: municípios com série muito curta produzem correlações espúrias por baixo N.",
    fontsize=7, color="#555555", wrap=True,
)

plt.tight_layout(rect=[0, 0.07, 1, 1])
out_path = OUT_DIR / "fig3_correlacoes_temporais.png"
plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Salvo: {out_path}")
plt.close()
