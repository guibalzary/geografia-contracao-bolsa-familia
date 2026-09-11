"""
Exploração do ranking — três perguntas simultâneas
====================================================

Roda três análises exploratórias e imprime + salva um .md legível.

1. Distribuição de CAT por CNAE_div (setorial total, não por CNPJ)
   → Responde: hospitais dominam porque a exposição é maior no setor, ou
     porque estão concentrados em poucos CNPJs grandes?

2. Ausências notáveis — hospitais de porte procurados por palavra-chave
   → Responde: Einstein, HSL, Oswaldo Cruz, D'Or, A.C. Camargo, Amil,
     Sírio-Libanês, HC-SP, INCA aparecem no dataset e onde?

3. Distribuição de municípios por CNAE dominante
   → Responde: se subo MIN de 20 para 50/100 na Fig 1, quantos CNAEs sobram?

Saída:
- outputs/exploracao/ranking_exploracao.md (relatório legível)
- print no terminal com o essencial
"""

import pandas as pd
from pathlib import Path

# ============ Config ============
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "monstro"
OUT_DIR = BASE_DIR / "outputs" / "exploracao"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RANKING_PATH = DATA_DIR / "cat_cnpj_ranking.parquet"
NOMES_PATH = BASE_DIR / "outputs" / "cnpj_nomes.parquet"
PAINEL_PATH = DATA_DIR / "painel_estrutural.parquet"

# Hospitais notáveis para buscar por palavra-chave na razão social
# (ordenados por reputação/porte esperado)
HOSPITAIS_NOTAVEIS = [
    ("EINSTEIN", "Hospital Israelita Albert Einstein"),
    ("SIRIO", "Hospital Sírio-Libanês"),
    ("OSWALDO CRUZ", "Hospital Alemão Oswaldo Cruz"),
    ("BENEFICENCIA PORTUGUESA", "Beneficência Portuguesa SP"),
    ("A C CAMARGO", "A.C. Camargo Cancer Center"),
    ("AC CAMARGO", "A.C. Camargo Cancer Center"),
    ("REDE D OR", "Rede D'Or São Luiz"),
    ("REDE D'OR", "Rede D'Or São Luiz"),
    ("SAO LUIZ", "Rede D'Or São Luiz"),
    ("AMIL", "Amil / Rede Total Health"),
    ("HOSPITAL DAS CLINICAS", "HC-FMUSP"),
    ("INCA", "Instituto Nacional de Câncer"),
    ("FLEURY", "Grupo Fleury"),
    ("DASA", "DASA"),
    ("ALEMAO OSWALDO CRUZ", "Hospital Alemão Oswaldo Cruz"),
]

# ============ Carrega ============
rank = pd.read_parquet(RANKING_PATH)
nomes = pd.read_parquet(NOMES_PATH) if NOMES_PATH.exists() else pd.DataFrame(columns=["cnpj", "razao_social"])
painel = pd.read_parquet(PAINEL_PATH)

# Merge razão social no ranking
rank = rank.merge(nomes[["cnpj", "razao_social"]], on="cnpj", how="left")
rank["razao_social"] = rank["razao_social"].fillna("")

# ============ 1. Distribuição por CNAE_div ============
print("=" * 70)
print("1. DISTRIBUIÇÃO DE CAT POR CNAE_DIV (setorial)")
print("=" * 70)

por_cnae = (
    rank
    .groupby(["cnae_div", "cnae_nome"], as_index=False)
    .agg(
        cat_total=("n_cat", "sum"),
        obito_total=("n_obito", "sum"),
        n_cnpjs=("cnpj", "count"),
        cat_mediana_cnpj=("n_cat", "median"),
        cat_p90_cnpj=("n_cat", lambda s: s.quantile(0.9)),
        cat_max_cnpj=("n_cat", "max"),
    )
    .sort_values("cat_total", ascending=False)
    .reset_index(drop=True)
)
por_cnae["letalidade_pct"] = 100 * por_cnae["obito_total"] / por_cnae["cat_total"]
por_cnae["pct_total"] = 100 * por_cnae["cat_total"] / por_cnae["cat_total"].sum()

top20_cnae = por_cnae.head(20).copy()
print(top20_cnae.to_string(index=False))

# ============ 2. Hospitais notáveis — busca por palavra-chave ============
print()
print("=" * 70)
print("2. HOSPITAIS NOTÁVEIS — BUSCA NO RANKING COMPLETO")
print("=" * 70)

achados_hospitais = []
for kw, nome_ref in HOSPITAIS_NOTAVEIS:
    matches = rank[rank["razao_social"].str.upper().str.contains(kw, na=False, regex=False)]
    if len(matches) > 0:
        cat_soma = matches["n_cat"].sum()
        obito_soma = matches["n_obito"].sum()
        n_cnpjs = len(matches)
        posicao_min = rank.sort_values("n_cat", ascending=False).reset_index(drop=True).index[
            rank.sort_values("n_cat", ascending=False).reset_index(drop=True)["razao_social"]
            .str.upper().str.contains(kw, na=False, regex=False)
        ].min() + 1 if len(matches) > 0 else None
        achados_hospitais.append({
            "busca": kw,
            "referencia": nome_ref,
            "n_cnpjs_encontrados": n_cnpjs,
            "cat_soma": int(cat_soma),
            "obito_soma": int(obito_soma),
            "letalidade_pct": round(100 * obito_soma / cat_soma, 3) if cat_soma > 0 else None,
            "melhor_posicao_ranking": int(posicao_min) if posicao_min is not None else None,
        })
    else:
        achados_hospitais.append({
            "busca": kw,
            "referencia": nome_ref,
            "n_cnpjs_encontrados": 0,
            "cat_soma": 0,
            "obito_soma": 0,
            "letalidade_pct": None,
            "melhor_posicao_ranking": None,
        })

df_hosp = pd.DataFrame(achados_hospitais)
# Consolida por referência (varias palavras-chave apontam para mesmo hospital)
df_hosp_agg = (
    df_hosp
    .groupby("referencia", as_index=False)
    .agg(
        n_cnpjs_encontrados=("n_cnpjs_encontrados", "max"),
        cat_soma=("cat_soma", "max"),
        obito_soma=("obito_soma", "max"),
        letalidade_pct=("letalidade_pct", "max"),
        melhor_posicao_ranking=("melhor_posicao_ranking", "min"),
    )
    .sort_values("cat_soma", ascending=False)
    .reset_index(drop=True)
)
print(df_hosp_agg.to_string(index=False))

# Mostra também os matches individuais para inspeção
print()
print("--- Detalhes dos matches individuais (top 15 por CAT) ---")
matches_detalhe = []
for kw, nome_ref in HOSPITAIS_NOTAVEIS:
    ms = rank[rank["razao_social"].str.upper().str.contains(kw, na=False, regex=False)]
    for _, m in ms.iterrows():
        matches_detalhe.append({
            "busca": kw,
            "razao_social": m["razao_social"][:60],
            "cnpj_raiz": m["cnpj"][:8],
            "cnae_div": m["cnae_div"],
            "n_cat": int(m["n_cat"]),
            "n_obito": int(m["n_obito"]),
        })
if matches_detalhe:
    df_det = pd.DataFrame(matches_detalhe).drop_duplicates(subset=["cnpj_raiz"]).sort_values("n_cat", ascending=False).head(15)
    print(df_det.to_string(index=False))
else:
    print("Nenhum match encontrado.")

# ============ 3. Distribuição de municípios por CNAE dominante ============
print()
print("=" * 70)
print("3. DISTRIBUIÇÃO DE MUNICÍPIOS POR CNAE DOMINANTE (para Fig 1)")
print("=" * 70)

dist_cnae_dom = (
    painel
    .dropna(subset=["cnae_dominante"])
    .groupby(["cnae_dominante", "cnae_dominante_nome"], as_index=False)
    .agg(n_municipios=("cod_ibge7", "count"))
    .sort_values("n_municipios", ascending=False)
    .reset_index(drop=True)
)

# Quantos CNAEs sobrariam com cada MIN candidato
for min_n in [20, 30, 50, 75, 100, 150, 200]:
    n_cnaes = (dist_cnae_dom["n_municipios"] >= min_n).sum()
    n_mun = dist_cnae_dom[dist_cnae_dom["n_municipios"] >= min_n]["n_municipios"].sum()
    pct_mun = 100 * n_mun / dist_cnae_dom["n_municipios"].sum()
    print(f"MIN={min_n:>3} → {n_cnaes:>2} CNAEs sobrevivem, cobrindo {n_mun:>4} municípios ({pct_mun:.1f}% do total)")

print()
print("--- Top 20 CNAEs por n_municipios (para escolher MIN) ---")
print(dist_cnae_dom.head(20).to_string(index=False))

# ============ Salva relatório .md ============
md_path = OUT_DIR / "ranking_exploracao.md"
with open(md_path, "w", encoding="utf-8") as f:
    f.write("# Exploração do ranking — 11/09/2026\n\n")

    f.write("## 1. Distribuição de CAT por CNAE_div\n\n")
    f.write("Top 20 divisões CNAE por volume total de CATs (soma de todos os CNPJs do setor).\n\n")
    f.write(top20_cnae.to_markdown(index=False))
    f.write("\n\n")

    f.write("## 2. Hospitais notáveis — presença no dataset\n\n")
    f.write("Busca por palavra-chave na razão social (BrasilAPI), no ranking completo (42.911 CNPJs).\n\n")
    f.write(df_hosp_agg.to_markdown(index=False))
    f.write("\n\n### Matches individuais (top por CAT)\n\n")
    if matches_detalhe:
        df_det = pd.DataFrame(matches_detalhe).drop_duplicates(subset=["cnpj_raiz"]).sort_values("n_cat", ascending=False).head(20)
        f.write(df_det.to_markdown(index=False))
    else:
        f.write("_Nenhum match encontrado._\n")
    f.write("\n\n")

    f.write("## 3. MIN para Fig 1\n\n")
    f.write("Quantos CNAEs sobrevivem a cada corte de mínimo de municípios:\n\n")
    for min_n in [20, 30, 50, 75, 100, 150, 200]:
        n_cnaes = (dist_cnae_dom["n_municipios"] >= min_n).sum()
        n_mun = dist_cnae_dom[dist_cnae_dom["n_municipios"] >= min_n]["n_municipios"].sum()
        pct_mun = 100 * n_mun / dist_cnae_dom["n_municipios"].sum()
        f.write(f"- MIN={min_n}: {n_cnaes} CNAEs, {n_mun} municípios ({pct_mun:.1f}% do total)\n")
    f.write("\n### Top 20 CNAEs por número de municípios dominados\n\n")
    f.write(dist_cnae_dom.head(20).to_markdown(index=False))
    f.write("\n")

print()
print(f"[ok] Relatório salvo: {md_path}")
