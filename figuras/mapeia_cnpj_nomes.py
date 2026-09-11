"""
Mapeamento CNPJ → razão social via BrasilAPI
=============================================

Consulta os top N CNPJs (por volume de CAT) na API pública da BrasilAPI
e grava um de-para em outputs/cnpj_nomes.parquet.

- BrasilAPI: https://brasilapi.com.br/api/cnpj/v1/{cnpj}
- Sem chave, gratuita, rate limit brando (~3 req/s tolerável).
- Persistência incremental: se rodar de novo, pula CNPJs já mapeados.

Uso:
    python figuras/mapeia_cnpj_nomes.py

Fonte de entrada: data/processed/monstro/cat_cnpj_ranking.parquet
Saída: outputs/cnpj_nomes.parquet
"""

import time
import json
import urllib.request
import urllib.error
import pandas as pd
from pathlib import Path

# ============ Config ============
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "monstro"
OUT_DIR = BASE_DIR / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RANKING_PATH = DATA_DIR / "cat_cnpj_ranking.parquet"
SAIDA_PATH = OUT_DIR / "cnpj_nomes.parquet"

TOP_N = 30              # mapeia os 30 com mais CAT (Fig 2 usa 20; margem de 10)
DELAY_SEG = 0.5         # pausa entre requests — gentil com a API
TIMEOUT_SEG = 15

API_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"

# ============ Carrega o que já foi mapeado (idempotência) ============
if SAIDA_PATH.exists():
    ja_mapeado = pd.read_parquet(SAIDA_PATH)
    cnpjs_ja_ok = set(ja_mapeado["cnpj"].tolist())
    print(f"[info] {len(cnpjs_ja_ok)} CNPJs já mapeados em {SAIDA_PATH.name}, pulando esses.")
else:
    ja_mapeado = pd.DataFrame(columns=["cnpj", "razao_social", "nome_fantasia", "erro"])
    cnpjs_ja_ok = set()

# ============ Seleciona top N para consultar ============
rank = pd.read_parquet(RANKING_PATH)
top = rank.nlargest(TOP_N, "n_cat").copy()
cnpjs_a_consultar = [c for c in top["cnpj"].tolist() if c not in cnpjs_ja_ok]

print(f"[info] Total no ranking: {len(rank)}; top-{TOP_N} selecionado; "
      f"{len(cnpjs_a_consultar)} pendentes de consulta.")

# ============ Consulta ============
resultados = []
for i, cnpj in enumerate(cnpjs_a_consultar, start=1):
    url = API_URL.format(cnpj=cnpj)
    linha = {"cnpj": cnpj, "razao_social": None, "nome_fantasia": None, "erro": None}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cgu-reuso-mapper/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEG) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            linha["razao_social"] = payload.get("razao_social")
            linha["nome_fantasia"] = payload.get("nome_fantasia") or None
        print(f"  [{i:>2}/{len(cnpjs_a_consultar)}] {cnpj} → {linha['razao_social']}")
    except urllib.error.HTTPError as e:
        linha["erro"] = f"HTTP {e.code}"
        print(f"  [{i:>2}/{len(cnpjs_a_consultar)}] {cnpj} → ERRO HTTP {e.code}")
    except urllib.error.URLError as e:
        linha["erro"] = f"URLError: {e.reason}"
        print(f"  [{i:>2}/{len(cnpjs_a_consultar)}] {cnpj} → ERRO URL {e.reason}")
    except Exception as e:
        linha["erro"] = f"{type(e).__name__}: {e}"
        print(f"  [{i:>2}/{len(cnpjs_a_consultar)}] {cnpj} → ERRO {e}")

    resultados.append(linha)
    time.sleep(DELAY_SEG)

# ============ Persiste (append) ============
if resultados:
    novo = pd.DataFrame(resultados)
    final = pd.concat([ja_mapeado, novo], ignore_index=True)
    final = final.drop_duplicates(subset=["cnpj"], keep="last").reset_index(drop=True)
    final.to_parquet(SAIDA_PATH, index=False)
    print(f"[ok] {SAIDA_PATH} atualizado. Total de CNPJs: {len(final)}")
else:
    print("[info] Nada a fazer — todos os CNPJs do top já estavam mapeados.")
