"""
Busca hospitais notáveis na razão social BRUTA do cat_final
============================================================

Diferente de explora_ranking.py (que buscava via BrasilAPI, mapeada só
para os top 30 CNPJs), este script busca diretamente no cat_final.parquet,
que deve trazer a razão social original do SIACAT/RAIS.

Objetivo: responder honestamente no README se Einstein, HSL, Oswaldo Cruz,
D'Or, A.C. Camargo etc. estão ou não presentes no dataset, e em que ordem
de grandeza — sem afirmar "prevenção" onde na verdade é sub-mapeamento
da nossa consulta anterior.

Saída: outputs/exploracao/hospitais_notaveis_razaosocial_bruta.md
"""

import pandas as pd
import duckdb
from pathlib import Path

# ============ Config ============
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "monstro"
OUT_DIR = BASE_DIR / "outputs" / "exploracao"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CAT_FINAL = DATA_DIR / "cat_final.parquet"

HOSPITAIS_KEYWORDS = [
    ("EINSTEIN", "Einstein"),
    ("ISRAELITA", "Einstein (fallback via 'Israelita')"),
    ("SIRIO", "Sírio-Libanês"),
    ("SIRIO-LIBANES", "Sírio-Libanês (variante)"),
    ("SIRIO LIBANES", "Sírio-Libanês (variante 2)"),
    ("OSWALDO CRUZ", "Alemão Oswaldo Cruz"),
    ("BENEFICENCIA PORTUGUESA", "Beneficência Portuguesa"),
    ("A C CAMARGO", "A.C. Camargo"),
    ("AC CAMARGO", "A.C. Camargo (variante)"),
    ("REDE D OR", "Rede D'Or"),
    ("REDE D'OR", "Rede D'Or (variante)"),
    ("SAO LUIZ", "Rede D'Or / São Luiz"),
    ("AMIL", "Amil"),
    ("HOSPITAL DAS CLINICAS", "HC-FMUSP"),
    ("INCA", "INCA"),
    ("FLEURY", "Fleury"),
    ("DASA", "DASA"),
    ("HAPVIDA", "Hapvida"),
    ("NOTRE DAME", "Notre Dame Intermédica"),
    ("PREVENT SENIOR", "Prevent Senior"),
    ("SANTA CASA", "Santa Casas (para contraste)"),
    ("MISERICORDIA", "Misericórdias (para contraste)"),
]

# ============ Descobre colunas ============
con = duckdb.connect()
schema = con.execute(f"DESCRIBE SELECT * FROM '{CAT_FINAL.as_posix()}'").fetchdf()
print("Colunas de cat_final.parquet:")
print(schema.to_string(index=False))
print()

# Tenta identificar coluna de razão social
candidatos_razao = [c for c in schema["column_name"].tolist()
                    if any(k in c.lower() for k in ["razao", "nome_emp", "nome_fantasia", "empregador", "empregadora"])]
print(f"Candidatos a coluna de razão social: {candidatos_razao}")

if not candidatos_razao:
    # Mostra amostra pra descobrir
    print("\nAmostra do cat_final (2 linhas):")
    amostra = con.execute(f"SELECT * FROM '{CAT_FINAL.as_posix()}' LIMIT 2").fetchdf()
    print(amostra.T.to_string())
    print("\n[!] Nenhuma coluna óbvia de razão social encontrada. Ajuste o script.")
    con.close()
    raise SystemExit(1)

COL_RAZAO = candidatos_razao[0]
print(f"Usando coluna: {COL_RAZAO}\n")

# Também tenta descobrir coluna de CNPJ
candidatos_cnpj = [c for c in schema["column_name"].tolist() if "cnpj" in c.lower()]
COL_CNPJ = candidatos_cnpj[0] if candidatos_cnpj else None
print(f"Coluna CNPJ: {COL_CNPJ}\n")

# ============ Busca ============
print("=" * 70)
print("HOSPITAIS NOTÁVEIS NA RAZÃO SOCIAL BRUTA DO cat_final")
print("=" * 70)

resultados = []
for kw, ref in HOSPITAIS_KEYWORDS:
    # Conta CATs onde a razão social contém a palavra-chave
    q = f"""
    SELECT
        COUNT(*) AS n_cat,
        COUNT(DISTINCT {COL_CNPJ}) AS n_cnpjs
    FROM '{CAT_FINAL.as_posix()}'
    WHERE UPPER({COL_RAZAO}) LIKE '%{kw}%'
    """ if COL_CNPJ else f"""
    SELECT
        COUNT(*) AS n_cat,
        NULL AS n_cnpjs
    FROM '{CAT_FINAL.as_posix()}'
    WHERE UPPER({COL_RAZAO}) LIKE '%{kw}%'
    """
    r = con.execute(q).fetchone()
    n_cat, n_cnpjs = r[0], r[1]

    resultados.append({
        "keyword": kw,
        "referencia": ref,
        "n_cat": int(n_cat),
        "n_cnpjs_distintos": int(n_cnpjs) if n_cnpjs else 0,
    })

df = pd.DataFrame(resultados).sort_values("n_cat", ascending=False).reset_index(drop=True)
print(df.to_string(index=False))

# ============ Amostra de razões sociais reais para hospitais notáveis ============
print()
print("=" * 70)
print("AMOSTRA DE RAZÕES SOCIAIS ÚNICAS PARA CADA PALAVRA-CHAVE")
print("=" * 70)

amostras_texto = []
for kw, ref in HOSPITAIS_KEYWORDS:
    q = f"""
    SELECT DISTINCT {COL_RAZAO} AS razao, COUNT(*) AS n_cat
    FROM '{CAT_FINAL.as_posix()}'
    WHERE UPPER({COL_RAZAO}) LIKE '%{kw}%'
    GROUP BY {COL_RAZAO}
    ORDER BY n_cat DESC
    LIMIT 5
    """
    ams = con.execute(q).fetchdf()
    if len(ams) > 0:
        print(f"\n[{kw}] — {ref}")
        print(ams.to_string(index=False))
        amostras_texto.append((kw, ref, ams))

con.close()

# ============ Salva md ============
md_path = OUT_DIR / "hospitais_notaveis_razaosocial_bruta.md"
with open(md_path, "w", encoding="utf-8") as f:
    f.write("# Hospitais notáveis — busca na razão social bruta (cat_final)\n\n")
    f.write(f"Coluna utilizada: `{COL_RAZAO}`\n\n")
    f.write("## Contagem de CATs por palavra-chave\n\n")
    f.write(df.to_markdown(index=False))
    f.write("\n\n## Amostras de razões sociais encontradas\n\n")
    for kw, ref, ams in amostras_texto:
        f.write(f"### {kw} — {ref}\n\n")
        f.write(ams.to_markdown(index=False))
        f.write("\n\n")

print(f"\n[ok] Relatório salvo: {md_path}")
