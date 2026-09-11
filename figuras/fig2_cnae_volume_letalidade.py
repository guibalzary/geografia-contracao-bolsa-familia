"""
Figura 2 v2 — Painel duplo por CNAE: onde tem muito × onde mata
================================================================

Mudança da v2 sobre v1: filtro do CNAE "00" (não classificado) que
aparecia na Fig 2B como pseudo-setor. Não é setor real — é registro
CAT sem CNAE classificado no dado bruto.

2A (esquerda): Top 15 CNAEs por CAT total, com letalidade codificada em cor.
2B (direita):  Top 15 CNAEs por letalidade (com CAT ≥ 1.000), tamanho = volume.

Fonte: data/processed/monstro/cat_cnpj_ranking.parquet
Saída: outputs/figuras/fig2_cnae_volume_letalidade.png
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

TOP_N = 15
LETALIDADE_MIN_CAT = 1000
CNAES_EXCLUIR = {"00", "0", ""}   # não classificados

def trunca_palavra(s: str, limite: int = 32) -> str:
    s = str(s).strip()
    if len(s) <= limite:
        return s
    cortado = s[:limite]
    if " " in cortado:
        cortado = cortado.rsplit(" ", 1)[0]
    return cortado + "…"

rank = pd.read_parquet(DATA_DIR / "cat_cnpj_ranking.parquet")

def nome_frequente(g):
    if len(g) == 0:
        return ""
    return g.value_counts().index[0]

por_cnae = (
    rank
    .groupby("cnae_div", as_index=False)
    .agg(
        cnae_nome=("cnae_nome", nome_frequente),
        cat_total=("n_cat", "sum"),
        obito_total=("n_obito", "sum"),
        n_cnpjs=("cnpj", "count"),
        cat_p90_cnpj=("n_cat", lambda s: s.quantile(0.9)),
    )
)

# Filtra CNAEs não classificados
por_cnae = por_cnae[~por_cnae["cnae_div"].astype(str).str.strip().isin(CNAES_EXCLUIR)].copy()

por_cnae["letalidade_pct"] = 100 * por_cnae["obito_total"] / por_cnae["cat_total"]
por_cnae["rotulo"] = por_cnae["cnae_div"] + " — " + por_cnae["cnae_nome"].apply(lambda s: trunca_palavra(s, 30))

top_vol = por_cnae.nlargest(TOP_N, "cat_total").sort_values("cat_total", ascending=True).reset_index(drop=True)

top_let = (
    por_cnae[por_cnae["cat_total"] >= LETALIDADE_MIN_CAT]
    .nlargest(TOP_N, "letalidade_pct")
    .sort_values("letalidade_pct", ascending=True)
    .reset_index(drop=True)
)

cmap_let = plt.get_cmap("Reds")
cmap_vol = plt.get_cmap("Blues")

norm_let_a = mcolors.Normalize(vmin=0, vmax=top_vol["letalidade_pct"].max())
cores_a = [cmap_let(0.25 + 0.65 * norm_let_a(v)) for v in top_vol["letalidade_pct"]]

norm_vol_b = mcolors.Normalize(vmin=top_let["cat_total"].min(), vmax=top_let["cat_total"].max())
tamanhos_b = 80 + 700 * norm_vol_b(top_let["cat_total"])
cores_b = [cmap_vol(0.35 + 0.65 * norm_vol_b(v)) for v in top_let["cat_total"]]

fig, (axA, axB) = plt.subplots(1, 2, figsize=(17, 8.5))

# 2A
barsA = axA.barh(
    top_vol["rotulo"],
    top_vol["cat_total"],
    color=cores_a,
    edgecolor="#333333",
    linewidth=0.6,
)
for bar, cat, let in zip(barsA, top_vol["cat_total"], top_vol["letalidade_pct"]):
    x = bar.get_width()
    y = bar.get_y() + bar.get_height() / 2
    axA.text(x + top_vol["cat_total"].max() * 0.01, y,
             f"{int(cat):,}".replace(",", ".") + f"  ({let:.2f}%)",
             va="center", ha="left", fontsize=8, color="#333333")

axA.set_xlabel("CATs registradas (soma no biênio)", fontsize=10)
axA.set_title("(A) Top 15 CNAEs por volume de CAT\ncor = taxa de letalidade (%)",
              fontsize=12, pad=12, loc="left")
axA.grid(axis="x", alpha=0.3, linestyle="--")
axA.set_axisbelow(True)
for spine in ["top", "right"]:
    axA.spines[spine].set_visible(False)
axA.set_xlim(0, top_vol["cat_total"].max() * 1.28)

sm_a = cm.ScalarMappable(cmap=cmap_let, norm=norm_let_a)
sm_a.set_array([])
cbar_a = fig.colorbar(sm_a, ax=axA, orientation="vertical", pad=0.02, fraction=0.03)
cbar_a.set_label("Letalidade (% óbitos/CAT)", fontsize=8)
cbar_a.ax.tick_params(labelsize=7)

# 2B
y_pos = range(len(top_let))
axB.scatter(
    top_let["letalidade_pct"],
    y_pos,
    s=tamanhos_b,
    c=cores_b,
    edgecolor="#222222",
    linewidth=0.7,
    alpha=0.9,
    zorder=3,
)
axB.set_yticks(list(y_pos))
axB.set_yticklabels(top_let["rotulo"], fontsize=9)

for i, (let, cat) in enumerate(zip(top_let["letalidade_pct"], top_let["cat_total"])):
    axB.text(let + top_let["letalidade_pct"].max() * 0.03, i,
             f"{int(cat):,}".replace(",", ".") + " CATs",
             va="center", ha="left", fontsize=8, color="#444444")

axB.set_xlabel("Taxa de letalidade (% óbitos/CAT)", fontsize=10)
axB.set_title(f"(B) Top 15 CNAEs por letalidade (mín. {LETALIDADE_MIN_CAT} CATs)\ntamanho = volume de CATs",
              fontsize=12, pad=12, loc="left")
axB.grid(axis="x", alpha=0.3, linestyle="--")
axB.set_axisbelow(True)
for spine in ["top", "right"]:
    axB.spines[spine].set_visible(False)
axB.set_xlim(0, top_let["letalidade_pct"].max() * 1.35)

fig.text(
    0.02, 0.005,
    "Fonte: elaboração própria a partir de CAT (INSS). Agregação por CNAE de divisão (2 dígitos) sobre 42.911 CNPJs distintos. "
    "A leitura por setor evita o viés do ranking por CNPJ, no qual grandes empregadores concentrados (ex.: hospitais) aparecem no topo por escala; "
    "os setores com maior letalidade (transporte, vigilância, construção, energia) só emergem quando se agrega o setor inteiro. "
    "CNAEs não classificados excluídos.",
    fontsize=7, color="#555555", wrap=True,
)

plt.suptitle(
    "Onde tem muito acidente × onde o acidente mata: dois olhares sobre o mesmo dado",
    fontsize=13.5, y=0.995, x=0.02, ha="left",
)
plt.tight_layout(rect=[0, 0.04, 1, 0.96])
out_path = OUT_DIR / "fig2_cnae_volume_letalidade.png"
plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Salvo: {out_path}")
plt.close()
