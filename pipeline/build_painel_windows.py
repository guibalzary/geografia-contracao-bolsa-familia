#!/usr/bin/env python3
"""
build_painel.py — Reúso CAT x Bolsa Família
Versão para máquina com pouca RAM (8 GB): processa incremental,
usa banco DuckDB em disco, agrega arquivo por arquivo.

Uso:
    cd /Users/guilhermecamargo/Developer/cgu/data-mapping
    python3 build_painel.py
"""
import duckdb
import glob
import os
from pathlib import Path

BASE = Path('data')
RAW_BF = BASE / 'raw' / 'bf'
RAW_CAT = BASE / 'raw' / 'cat'
AUX = BASE / 'aux' / 'tabmun_siafi.csv'
OUT = BASE / 'processed'
OUT.mkdir(parents=True, exist_ok=True)

DB_PATH = 'build.duckdb'   # banco em disco, nao em memoria
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

con = duckdb.connect(DB_PATH)

# Config conservadora para 8 GB de RAM
con.execute("SET memory_limit = '3GB'")
con.execute("SET temp_directory = '/tmp/duckdb_spill'")
con.execute("SET max_temp_directory_size = '50GiB'")
con.execute("SET threads = 2")
con.execute("SET preserve_insertion_order = false")

BF_READ = """read_csv('{path}', delim=';', quote='"', encoding='latin-1',
    header=true, ignore_errors=true)"""

def log(msg):
    print('>>> ' + msg, flush=True)

# ------------------------------------------------------------
# 1. DE-PARA
# ------------------------------------------------------------
log('1. de-para SIAFI<->IBGE')
con.execute(f"""
CREATE TABLE depara AS
SELECT column0 AS cod_siafi, column3 AS uf, column2 AS nome_municipio,
       column4 AS cod_ibge7, LEFT(column4,6) AS cod_ibge6
FROM read_csv('{AUX}', header=false, delim=';', encoding='latin-1',
              ignore_errors=true, all_varchar=true)
""")

# ------------------------------------------------------------
# 2. CAT — arquivo por arquivo, acumulando numa tabela
# ------------------------------------------------------------
log('2. CAT — agregando arquivo por arquivo')
con.execute("""
CREATE TABLE cat_mun_mes (
    cod_ibge6 VARCHAR, ano_mes VARCHAR,
    n_cat BIGINT, n_obito BIGINT, n_cid_mental BIGINT,
    n_cid_lesao BIGINT, n_cid_musculo BIGINT
)
""")
cat_files = sorted(glob.glob(str(RAW_CAT / '*.csv')))
for i, f in enumerate(cat_files, 1):
    con.execute(f"""
    INSERT INTO cat_mun_mes
    WITH raw AS (
        SELECT SPLIT_PART("Munic Empr",'-',1) AS cod_ibge6,
               STRFTIME("Data Acidente",'%Y%m') AS ano_mes,
               LEFT("CID-10",1) AS cid_cap,
               "Indica Óbito Acidente" AS obito
        FROM read_csv('{f}', delim=';', quote='"', encoding='latin-1',
                      header=true, ignore_errors=true)
        WHERE STRFTIME("Data Acidente",'%Y%m') BETWEEN '202401' AND '202512'
    )
    SELECT cod_ibge6, ano_mes,
        COUNT(*),
        SUM(CASE WHEN obito ILIKE 'sim%' THEN 1 ELSE 0 END),
        SUM(CASE WHEN cid_cap='F' THEN 1 ELSE 0 END),
        SUM(CASE WHEN cid_cap IN ('S','T') THEN 1 ELSE 0 END),
        SUM(CASE WHEN cid_cap='M' THEN 1 ELSE 0 END)
    FROM raw
    WHERE cod_ibge6 IS NOT NULL AND LENGTH(cod_ibge6)=6
    GROUP BY cod_ibge6, ano_mes
    """)
    log(f'   CAT {i}/{len(cat_files)}: {Path(f).name}')

# consolida (pode haver ano_mes repartido entre arquivos)
con.execute("""
CREATE TABLE cat_final AS
SELECT cod_ibge6, ano_mes,
    SUM(n_cat) AS n_cat, SUM(n_obito) AS n_obito,
    SUM(n_cid_mental) AS n_cid_mental, SUM(n_cid_lesao) AS n_cid_lesao,
    SUM(n_cid_musculo) AS n_cid_musculo
FROM cat_mun_mes GROUP BY cod_ibge6, ano_mes
""")

# ------------------------------------------------------------
# 3. BF ESTOQUE — arquivo por arquivo (so 202401+)
# ------------------------------------------------------------
log('3. BF estoque — arquivo por arquivo')
con.execute("""
CREATE TABLE bf_estoque (
    cod_siafi VARCHAR, ano_mes VARCHAR,
    n_beneficiarios BIGINT, valor_total DOUBLE
)
""")
bf_files = sorted(glob.glob(str(RAW_BF / '*.csv')))
for i, f in enumerate(bf_files, 1):
    mes = Path(f).name[:6]
    if mes < '202401':   # pula warm-up no estoque
        log(f'   BF estoque pula warm-up {mes}')
        continue
    con.execute(f"""
    INSERT INTO bf_estoque
    SELECT "CÓDIGO MUNICÍPIO SIAFI",
           CAST("MÊS COMPETÊNCIA" AS VARCHAR),
           COUNT(DISTINCT "NIS FAVORECIDO"),
           SUM(CAST(REPLACE("VALOR PARCELA",',','.') AS DOUBLE))
    FROM {BF_READ.format(path=f)}
    WHERE "MÊS COMPETÊNCIA" = "MÊS REFERÊNCIA"
    GROUP BY 1, 2
    """)
    log(f'   BF estoque {i}/{len(bf_files)}: {Path(f).name}')

# ------------------------------------------------------------
# 4. BF ENTRADAS — etapa 1: extrai (NIS, mun, mes) para Parquet enxuto
#    inclui warm-up 202312. Grava incremental.
# ------------------------------------------------------------
log('4a. BF entradas — extraindo NIS para parquet enxuto')
nis_parquet = str(OUT / '_nis_tmp.parquet')
# processa cada arquivo e faz COPY append via UNION nao da; entao
# criamos tabela em disco e inserimos incremental, depois exportamos
con.execute("CREATE TABLE nis_tmp (nis BIGINT, cod_siafi VARCHAR, ano_mes VARCHAR)")
for i, f in enumerate(bf_files, 1):
    mes = Path(f).name[:6]
    if mes < '202312':
        continue
    con.execute(f"""
    INSERT INTO nis_tmp
    SELECT DISTINCT "NIS FAVORECIDO",
           "CÓDIGO MUNICÍPIO SIAFI",
           CAST("MÊS COMPETÊNCIA" AS VARCHAR)
    FROM {BF_READ.format(path=f)}
    WHERE "MÊS COMPETÊNCIA" = "MÊS REFERÊNCIA"
    """)
    log(f'   NIS extract {i}/{len(bf_files)}: {Path(f).name}')

# etapa 2: primeira aparicao por NIS, depois conta entradas por mun x mes
log('4b. BF entradas — calculando primeira aparicao')
con.execute("""
CREATE TABLE bf_entradas AS
WITH primeira AS (
    SELECT nis, MIN(cod_siafi) AS cod_siafi, MIN(ano_mes) AS primeiro_mes
    FROM nis_tmp GROUP BY nis
)
SELECT cod_siafi, primeiro_mes AS ano_mes, COUNT(*) AS n_entradas
FROM primeira
WHERE primeiro_mes >= '202401'
GROUP BY cod_siafi, primeiro_mes
""")
con.execute("DROP TABLE nis_tmp")

# ------------------------------------------------------------
# 5. PAINEL
# ------------------------------------------------------------
log('5. montando painel')
con.execute("""
CREATE TABLE painel AS
WITH bf_join AS (
    SELECT e.cod_siafi, e.ano_mes, e.n_beneficiarios, e.valor_total,
           COALESCE(ent.n_entradas,0) AS n_entradas
    FROM bf_estoque e
    LEFT JOIN bf_entradas ent
      ON e.cod_siafi=ent.cod_siafi AND e.ano_mes=ent.ano_mes
)
SELECT d.cod_ibge7, d.cod_ibge6, d.cod_siafi, d.uf, d.nome_municipio,
    COALESCE(bf.ano_mes, cat.ano_mes) AS ano_mes,
    COALESCE(cat.n_cat,0) AS n_cat,
    COALESCE(cat.n_obito,0) AS n_obito,
    COALESCE(cat.n_cid_mental,0) AS n_cid_mental,
    COALESCE(cat.n_cid_lesao,0) AS n_cid_lesao,
    COALESCE(cat.n_cid_musculo,0) AS n_cid_musculo,
    COALESCE(bf.n_beneficiarios,0) AS bf_beneficiarios,
    COALESCE(bf.n_entradas,0) AS bf_entradas,
    COALESCE(bf.valor_total,0) AS bf_valor_total
FROM depara d
LEFT JOIN bf_join bf ON d.cod_siafi=bf.cod_siafi
LEFT JOIN cat_final cat ON d.cod_ibge6=cat.cod_ibge6 AND cat.ano_mes=bf.ano_mes
WHERE COALESCE(bf.ano_mes, cat.ano_mes) IS NOT NULL
""")

# ------------------------------------------------------------
# 6. EXPORTA
# ------------------------------------------------------------
log('6. exportando painel')
con.execute(f"COPY painel TO '{OUT}/painel_municipio_mes.parquet' (FORMAT parquet)")
con.execute(f"COPY painel TO '{OUT}/painel_municipio_mes.csv' (FORMAT csv, HEADER true)")

# ------------------------------------------------------------
# 7. SANIDADE
# ------------------------------------------------------------
print()
print('=== LINHAS NO PAINEL ===')
print(con.execute("SELECT COUNT(*) FROM painel").fetchall())
print('=== COBERTURA TEMPORAL ===')
print(con.execute("SELECT MIN(ano_mes), MAX(ano_mes), COUNT(DISTINCT ano_mes) FROM painel").fetchall())
print('=== ENTRADAS BF POR MES ===')
for row in con.execute("SELECT ano_mes, SUM(bf_entradas) FROM painel GROUP BY ano_mes ORDER BY ano_mes").fetchall():
    print('  ', row[0], '->', row[1])
print('=== TOTAIS DE CONTROLE ===')
print(con.execute("SELECT SUM(n_cat), SUM(n_obito), SUM(n_cid_mental), SUM(bf_entradas) FROM painel").fetchall())
print('=== CASAMENTO CAT<->BF ===')
print(con.execute("""SELECT
    COUNT(*) FILTER (WHERE n_cat>0 AND bf_beneficiarios>0),
    COUNT(*) FILTER (WHERE n_cat>0 AND bf_beneficiarios=0),
    COUNT(*) FILTER (WHERE n_cat=0 AND bf_beneficiarios>0)
FROM painel""").fetchall())

con.close()
os.remove(DB_PATH)   # limpa o banco de trabalho
print()
print('Concluido. Painel em', OUT / 'painel_municipio_mes.parquet')
