"""
Figura 1 — Gradiente CNAE dominante × Variação mediana do BF por município
==========================================================================

MIN de municípios subido de 20 → 50 (17 CNAEs, cobrindo 78% dos municípios).
Truncamento inteligente: quebra em palavra inteira, limite 45 chars.

Fonte: data/processed/monstro/painel_estrutural.parquet
Saída: outputs/figuras/fig1_gradiente_cnae.png
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "monstro"
OUT_DIR = BASE_DIR / "outputs" / "figuras"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_MUNICIPIOS_POR_CNAE = 50
TOP_N_CNAES = 17          # todos os que sobrevivem ao MIN=50 (17 conforme exploração)

def trunca_palavra(s: str, limite: int = 45) -> str:
    s = str(s).strip()
    if len(s) <= limite:
        return s
    cortado = s[:limite]
    if " " in cortado:
        cortado = cortado.rsplit(" ", 1)[0]
    return cortado + "…"

painel = pd.read_parquet(DATA_DIR / "painel_estrutural.parquet")

grupo = (
    painel
    .dropna(subset=["cnae_dominante", "bf_variacao_pct"])
    .groupby(["cnae_dominante", "cnae_dominante_nome"], as_index=False)
    .agg(
        variacao_bf_mediana=("bf_variacao_pct", "median"),
        n_municipios=("cod_ibge7", "count"),
    )
)

grupo = grupo[grupo["n_municipios"] >= MIN_MUNICIPIOS_POR_CNAE].copy()
grupo = grupo.nlargest(TOP_N_CNAES, "n_municipios").copy()
grupo = grupo.sort_values("variacao_bf_mediana", ascending=False).reset_index(drop=True)

# Truncamento inteligente do nome
grupo["nome_trunc"] = grupo["cnae_dominante_nome"].apply(lambda s: trunca_palavra(s, 40))
grupo["rotulo"] = (
    grupo["cnae_dominante"] + " — "
    + grupo["nome_trunc"]
    + " (n=" + grupo["n_municipios"].astype(str) + ")"
)

magnitudes = grupo["variacao_bf_mediana"].abs()
norm = mcolors.Normalize(vmin=magnitudes.min(), vmax=magnitudes.max())
cmap = cm.get_cmap("Blues")
cores = [cmap(0.3 + 0.7 * norm(v)) for v in magnitudes]

fig, ax = plt.subplots(figsize=(12, 9))

bars = ax.barh(
    grupo["rotulo"],
    grupo["variacao_bf_mediana"] * 100,
    color=cores,
    edgecolor="#333333",
    linewidth=0.6,
)

ax.axvline(x=0, color="black", linewidth=0.8, linestyle="-")

# Ajuste do limite do eixo x para dar espaço à anotação
xmin_valor = (grupo["variacao_bf_mediana"] * 100).min()
ax.set_xlim(xmin_valor * 1.15, 1)

for bar, val in zip(bars, grupo["variacao_bf_mediana"] * 100):
    x = bar.get_width()
    y = bar.get_y() + bar.get_height() / 2
    # Anotação sempre à direita da barra (fora dela)
    ax.text(x + 0.15, y, f"{val:+.1f}%",
            va="center", ha="left", fontsize=9, color="#222222")

ax.set_xlabel("Variação mediana do estoque de beneficiários (%)", fontsize=11)
ax.set_title(
    "Geografia da contração do Bolsa Família por CNAE dominante do município\n"
    "Variação do estoque, jan/2024 → dez/2025",
    fontsize=13, pad=15, loc="left",
)

ax.grid(axis="x", alpha=0.3, linestyle="--")
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)

fig.text(
    0.02, 0.01,
    f"Fonte: elaboração própria a partir de CAT (INSS) e Bolsa Família — Pagamentos (MDS). "
    f"CNAE dominante = divisão (2 dígitos) com maior número de CATs no município. "
    f"Filtro: CNAEs dominantes em ao menos {MIN_MUNICIPIOS_POR_CNAE} municípios "
    f"(17 CNAEs, cobrindo 78% dos 5.589 municípios do painel).",
    fontsize=7, color="#555555", wrap=True,
)

plt.tight_layout(rect=[0, 0.04, 1, 1])
out_path = OUT_DIR / "fig1_gradiente_cnae.png"
plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Salvo: {out_path}")
plt.close()
