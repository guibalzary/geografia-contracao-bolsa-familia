#!/usr/bin/env python3
"""
analise_correlacao.py — Correlacao within-municipio entre CAT e
crescimento do Bolsa Familia, com defasagem temporal.

Para cada municipio com >=12 meses de n_cat>0, calcula:
  - Spearman(n_cat[t], bf_crescimento[t+lag]) para lag em {0,1,2,3,6}
  - Repetido para n_obito, n_cid_mental como variaveis alternativas

Agrega a distribuicao dessas correlacoes municipais.

Uso (na pasta com painel_municipio_mes.parquet):
    python3 analise_correlacao.py
"""
import duckdb
import pandas as pd
import numpy as np
from scipy import stats
import json
from pathlib import Path

OUT = Path('.')
LAGS = [0, 1, 2, 3, 6]
MIN_MESES = 12

# ------------------------------------------------------------
print('>>> carregando painel')
con = duckdb.connect(':memory:')
con.execute("CREATE VIEW p AS SELECT * FROM read_parquet('painel_municipio_mes.parquet')")

# municipios com pelo menos MIN_MESES de n_cat > 0
elegiveis = con.execute(f"""
    SELECT cod_ibge7, nome_municipio, uf,
           COUNT(*) FILTER (WHERE n_cat > 0) AS meses_com_cat,
           SUM(n_cat) AS total_cat
    FROM p
    GROUP BY cod_ibge7, nome_municipio, uf
    HAVING COUNT(*) FILTER (WHERE n_cat > 0) >= {MIN_MESES}
""").df()
print(f'    municipios elegiveis (>={MIN_MESES} meses c/ CAT): {len(elegiveis):,}')
print(f'    somam {int(elegiveis["total_cat"].sum()):,} CATs '
      f'({100*elegiveis["total_cat"].sum()/con.execute("SELECT SUM(n_cat) FROM p").fetchone()[0]:.1f}% do total)')

# ------------------------------------------------------------
print('>>> baixando painel de elegiveis para memoria')
painel = con.execute("""
    SELECT cod_ibge7, nome_municipio, uf, ano_mes,
           n_cat, n_obito, n_cid_mental, bf_crescimento, bf_beneficiarios
    FROM p
    ORDER BY cod_ibge7, ano_mes
""").df()
painel = painel[painel['cod_ibge7'].isin(elegiveis['cod_ibge7'])].copy()
painel['ano_mes'] = painel['ano_mes'].astype(str)
print(f'    {len(painel):,} linhas em {painel["cod_ibge7"].nunique():,} municipios')

# ------------------------------------------------------------
print('>>> calculando correlacoes por municipio')

def corr_lag(g, x_col, y_col, lag):
    """Spearman(x[t], y[t+lag]) dentro do municipio."""
    g = g.sort_values('ano_mes').reset_index(drop=True)
    x = g[x_col].values
    y = g[y_col].shift(-lag).values if lag > 0 else g[y_col].values
    # remove NaN (fim da serie quando lag > 0)
    mask = ~np.isnan(x) & ~np.isnan(y)
    if mask.sum() < 8:  # minimo de pares para correlacao ter sentido
        return np.nan
    if np.std(x[mask]) == 0 or np.std(y[mask]) == 0:
        return np.nan  # sem variacao
    r, _ = stats.spearmanr(x[mask], y[mask])
    return r

resultados = []
for cod, g in painel.groupby('cod_ibge7'):
    row = {
        'cod_ibge7': cod,
        'nome_municipio': g['nome_municipio'].iloc[0].strip(),
        'uf': g['uf'].iloc[0],
        'meses_dado': len(g),
        'total_cat': int(g['n_cat'].sum()),
        'total_obito': int(g['n_obito'].sum()),
        'total_cid_mental': int(g['n_cid_mental'].sum()),
    }
    for var in ['n_cat', 'n_obito', 'n_cid_mental']:
        for lag in LAGS:
            row[f'corr_{var}_lag{lag}'] = corr_lag(g, var, 'bf_crescimento', lag)
    resultados.append(row)

res = pd.DataFrame(resultados)
res.to_parquet(OUT / 'correlacoes_municipais.parquet', index=False)
res.to_csv(OUT / 'correlacoes_municipais.csv', index=False)
print(f'    salvo em correlacoes_municipais.parquet ({len(res):,} municipios)')

# ------------------------------------------------------------
print()
print('=== DISTRIBUICAO DE CORRELACOES (n_cat -> bf_crescimento) ===')
print(f'{"lag":>4} {"n_valido":>10} {"mediana":>10} {"q25":>8} {"q75":>8} '
      f'{"%>0.2":>8} {"%<-0.2":>8}')
for lag in LAGS:
    col = f'corr_n_cat_lag{lag}'
    v = res[col].dropna()
    n_forte_pos = (v > 0.2).sum()
    n_forte_neg = (v < -0.2).sum()
    print(f'{lag:>4} {len(v):>10,} {v.median():>10.3f} {v.quantile(0.25):>8.3f} '
          f'{v.quantile(0.75):>8.3f} {100*n_forte_pos/len(v):>7.1f}% {100*n_forte_neg/len(v):>7.1f}%')

print()
print('=== IDEM PARA n_obito -> bf_crescimento ===')
for lag in LAGS:
    col = f'corr_n_obito_lag{lag}'
    v = res[col].dropna()
    if len(v) < 100:
        continue
    n_forte_pos = (v > 0.2).sum()
    print(f'lag {lag}: n={len(v):>5} | mediana={v.median():>.3f} | '
          f'q25={v.quantile(0.25):>.3f} | q75={v.quantile(0.75):>.3f} | '
          f'>0.2 em {100*n_forte_pos/len(v):.1f}%')

print()
print('=== IDEM PARA n_cid_mental -> bf_crescimento ===')
for lag in LAGS:
    col = f'corr_n_cid_mental_lag{lag}'
    v = res[col].dropna()
    if len(v) < 100:
        continue
    n_forte_pos = (v > 0.2).sum()
    print(f'lag {lag}: n={len(v):>5} | mediana={v.median():>.3f} | '
          f'q25={v.quantile(0.25):>.3f} | q75={v.quantile(0.75):>.3f} | '
          f'>0.2 em {100*n_forte_pos/len(v):.1f}%')

# ------------------------------------------------------------
print()
print('=== TESTE DE SINAL (a mediana das correlacoes eh diferente de zero?) ===')
print('Wilcoxon signed-rank test contra 0 para cada lag (n_cat).')
for lag in LAGS:
    col = f'corr_n_cat_lag{lag}'
    v = res[col].dropna()
    if len(v) < 50:
        continue
    stat, p = stats.wilcoxon(v)
    print(f'lag {lag}: mediana={v.median():>+.4f} | p-valor={p:.2e} | '
          f'{"SIGNIF." if p < 0.001 else "n.s."}')

print()
print('=== TOP 20 MUNICIPIOS POR corr_n_cat_lag1 (positivo) ===')
top = res.nlargest(20, 'corr_n_cat_lag1')[
    ['nome_municipio','uf','total_cat','corr_n_cat_lag0','corr_n_cat_lag1','corr_n_cat_lag2','corr_n_cat_lag3']
]
print(top.to_string(index=False))

print()
print('Arquivos gerados:')
print('  correlacoes_municipais.parquet')
print('  correlacoes_municipais.csv')
