#!/usr/bin/env python3
"""
cruza_estrutural.py — VERSAO MONSTRO (Windows, 16 GB RAM)

Cruzamento estrutural CAT (por CNAE) x BF.
Depende dos parquets gerados por agrega_cat_cnae_monstro.py.

Uso:
    conda activate cgu
    cd D:\\_repos\\cgu
    python cruza_estrutural.py
"""
import duckdb
from pathlib import Path

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
PROJETO = Path(r'D:\_repos\cgu')
PROC = PROJETO / 'data' / 'processed'
AUX  = PROJETO / 'data' / 'bases-aux' / 'tabmun_siafi.csv'
TEMP_SPILL = PROJETO / '_tmp_duckdb'
TEMP_SPILL.mkdir(parents=True, exist_ok=True)

def p(path):
    """Converte Path para string com barras normais para SQL."""
    return path.as_posix()

con = duckdb.connect(':memory:')
con.execute("SET memory_limit = '10GB'")
con.execute("SET threads = 8")
con.execute(f"SET temp_directory = '{TEMP_SPILL.as_posix()}'")

# ------------------------------------------------------------
print('>>> carregando insumos')
con.execute(f"""
    CREATE VIEW cat_cnae_mun AS
    SELECT * FROM read_parquet('{p(PROC / "cat_cnae_mun.parquet")}')
""")
con.execute(f"""
    CREATE VIEW cat_secao_dic AS
    SELECT * FROM read_parquet('{p(PROC / "cat_cnae_secao_dic.parquet")}')
""")
con.execute(f"""
    CREATE VIEW bf_estoque AS
    SELECT * FROM read_parquet('{p(PROC / "bf_estoque.parquet")}')
""")
con.execute(f"""
    CREATE VIEW depara AS
    SELECT column0 AS cod_siafi, column3 AS uf, column2 AS nome_municipio,
           column4 AS cod_ibge7, LEFT(column4,6) AS cod_ibge6
    FROM read_csv('{p(AUX)}', header=false, delim=';', encoding='latin-1',
                  ignore_errors=true, all_varchar=true)
""")

# ------------------------------------------------------------
print('>>> agregando BF por municipio (media do estoque e variacao 202401 -> 202512)')
con.execute("""
CREATE TABLE bf_municipio AS
WITH ranked AS (
    SELECT cod_siafi, ano_mes, n_beneficiarios,
           ROW_NUMBER() OVER (PARTITION BY cod_siafi ORDER BY ano_mes ASC)  AS r_asc,
           ROW_NUMBER() OVER (PARTITION BY cod_siafi ORDER BY ano_mes DESC) AS r_desc
    FROM bf_estoque
),
inicio AS (SELECT cod_siafi, n_beneficiarios AS bf_ini FROM ranked WHERE r_asc = 1),
fim    AS (SELECT cod_siafi, n_beneficiarios AS bf_fim FROM ranked WHERE r_desc = 1),
medias AS (
    SELECT cod_siafi,
           AVG(n_beneficiarios) AS bf_media,
           MAX(n_beneficiarios) AS bf_pico,
           MIN(n_beneficiarios) AS bf_vale
    FROM bf_estoque GROUP BY cod_siafi
)
SELECT m.cod_siafi, m.bf_media, m.bf_pico, m.bf_vale,
       i.bf_ini, f.bf_fim,
       (f.bf_fim - i.bf_ini)                            AS bf_variacao_periodo,
       CASE WHEN i.bf_ini > 0
            THEN (f.bf_fim - i.bf_ini) * 1.0 / i.bf_ini
            ELSE NULL END                               AS bf_variacao_pct
FROM medias m
LEFT JOIN inicio i USING (cod_siafi)
LEFT JOIN fim    f USING (cod_siafi)
""")

# ------------------------------------------------------------
print('>>> agregando CAT por municipio (total + CNAE dominante + diversidade)')
con.execute("""
CREATE TABLE cat_municipio AS
WITH tot AS (
    SELECT cod_ibge6,
           SUM(n_cat)             AS cat_total,
           SUM(n_obito)           AS cat_obito,
           SUM(n_cid_mental)      AS cat_cid_mental,
           SUM(n_cid_lesao)       AS cat_cid_lesao,
           SUM(n_cid_musculo)     AS cat_cid_musculo,
           SUM(n_com_afastamento) AS cat_afastamento
    FROM cat_cnae_mun GROUP BY cod_ibge6
),
top_cnae AS (
    SELECT cod_ibge6, cnae_div, n_cat,
           ROW_NUMBER() OVER (PARTITION BY cod_ibge6 ORDER BY n_cat DESC) AS rn
    FROM cat_cnae_mun
),
diversidade AS (
    SELECT cod_ibge6, COUNT(DISTINCT cnae_div) AS n_cnaes_ativos
    FROM cat_cnae_mun WHERE n_cat > 0 GROUP BY cod_ibge6
)
SELECT t.*,
       tc.cnae_div         AS cnae_dominante,
       d.cnae_nome_exemplo AS cnae_dominante_nome,
       tc.n_cat            AS cat_cnae_dominante,
       CASE WHEN t.cat_total > 0
            THEN tc.n_cat * 1.0 / t.cat_total
            ELSE NULL END  AS concentracao_dominante,
       div.n_cnaes_ativos
FROM tot t
LEFT JOIN top_cnae tc ON t.cod_ibge6 = tc.cod_ibge6 AND tc.rn = 1
LEFT JOIN cat_secao_dic d ON tc.cnae_div = d.cnae_div
LEFT JOIN diversidade  div ON t.cod_ibge6 = div.cod_ibge6
""")

# ------------------------------------------------------------
print('>>> montando painel_estrutural')
con.execute("""
CREATE TABLE painel_estrutural AS
SELECT
    d.cod_ibge7, d.cod_ibge6, d.cod_siafi, d.uf, d.nome_municipio,
    COALESCE(c.cat_total, 0)              AS cat_total,
    COALESCE(c.cat_obito, 0)              AS cat_obito,
    COALESCE(c.cat_cid_mental, 0)         AS cat_cid_mental,
    COALESCE(c.cat_cid_lesao, 0)          AS cat_cid_lesao,
    COALESCE(c.cat_cid_musculo, 0)        AS cat_cid_musculo,
    COALESCE(c.cat_afastamento, 0)        AS cat_afastamento,
    c.cnae_dominante,
    c.cnae_dominante_nome,
    c.cat_cnae_dominante,
    c.concentracao_dominante,
    c.n_cnaes_ativos,
    b.bf_media, b.bf_pico, b.bf_vale, b.bf_ini, b.bf_fim,
    b.bf_variacao_periodo,
    b.bf_variacao_pct
FROM depara d
LEFT JOIN cat_municipio c ON d.cod_ibge6 = c.cod_ibge6
LEFT JOIN bf_municipio  b ON d.cod_siafi = b.cod_siafi
""")

# ------------------------------------------------------------
print('>>> montando matriz_cnae_municipio (long format)')
con.execute("""
CREATE TABLE matriz_cnae_municipio AS
SELECT
    d.cod_ibge7, d.uf, d.nome_municipio,
    c.cnae_div,
    dic.cnae_nome_exemplo AS cnae_nome,
    c.n_cat, c.n_obito, c.n_cid_mental, c.n_cid_lesao,
    c.n_cid_musculo, c.n_com_afastamento
FROM depara d
JOIN cat_cnae_mun c    ON d.cod_ibge6 = c.cod_ibge6
LEFT JOIN cat_secao_dic dic ON c.cnae_div = dic.cnae_div
""")

# ------------------------------------------------------------
print('>>> exportando')
con.execute(f"COPY painel_estrutural TO '{p(PROC / 'painel_estrutural.parquet')}' (FORMAT parquet)")
con.execute(f"COPY painel_estrutural TO '{p(PROC / 'painel_estrutural.csv')}' (FORMAT csv, HEADER true)")
con.execute(f"COPY matriz_cnae_municipio TO '{p(PROC / 'matriz_cnae_municipio.parquet')}' (FORMAT parquet)")

# ------------------------------------------------------------
print()
print('=== LINHAS ===')
print('  painel_estrutural:', con.execute("SELECT COUNT(*) FROM painel_estrutural").fetchone()[0])
print('  matriz_cnae_municipio:', con.execute("SELECT COUNT(*) FROM matriz_cnae_municipio").fetchone()[0])

print()
print('=== TOP 15 CNAE POR VOLUME NACIONAL DE CAT ===')
for row in con.execute("""
    SELECT cnae_div, MAX(cnae_nome) AS cnae_nome,
           SUM(n_cat) AS total_cat,
           SUM(n_obito) AS total_obito,
           SUM(n_cid_mental) AS total_f
    FROM matriz_cnae_municipio
    GROUP BY cnae_div ORDER BY total_cat DESC LIMIT 15
""").fetchall():
    print(f'  {row[0]:>3} | {(row[1] or "")[:35]:<35} | CAT={row[2]:>8,} | obito={row[3]:>4} | F={row[4]:>4}')

print()
print('=== VARIACAO BF por CNAE DOMINANTE (municipios com >=50) ===')
print('    (municipios agrupados pelo CNAE onde mais tem CAT)')
for row in con.execute("""
    SELECT cnae_dominante,
           MAX(cnae_dominante_nome) AS cnae_nome,
           COUNT(*) AS n_mun,
           AVG(bf_variacao_pct) AS var_pct_media,
           MEDIAN(bf_variacao_pct) AS var_pct_mediana,
           AVG(cat_total) AS cat_medio
    FROM painel_estrutural
    WHERE cnae_dominante IS NOT NULL AND bf_variacao_pct IS NOT NULL
    GROUP BY cnae_dominante
    HAVING COUNT(*) >= 50
    ORDER BY MEDIAN(bf_variacao_pct)
    LIMIT 20
""").fetchall():
    print(f'  {row[0]:>3} | {(row[1] or "")[:30]:<30} | n_mun={row[2]:>4} | '
          f'var_media={row[3]*100:>+6.1f}% | var_med={row[4]*100:>+6.1f}% | cat_med={row[5]:>7.1f}')

print()
print('Arquivos gerados em', PROC)
print('  painel_estrutural.parquet / .csv')
print('  matriz_cnae_municipio.parquet')

con.close()
