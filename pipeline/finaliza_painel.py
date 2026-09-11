#!/usr/bin/env python3
"""
finaliza_painel.py — continua de onde build_painel.py parou.
Conecta no build.duckdb existente (que ja tem nis_tmp, cat_final,
bf_estoque, depara) e faz so o passo final: entradas + painel.

Estrategia anti-OOM: agrupa nis_tmp via SORT (derrama em disco)
em vez de HASH (estourava). memory_limit baixo, 1 thread.

Uso:
    cd /Users/guilhermecamargo/Developer/cgu/data-mapping
    python3 finaliza_painel.py
"""
import duckdb
import os
from pathlib import Path

OUT = Path('data/processed')
con = duckdb.connect('build.duckdb')

# Config ultra-conservadora para o passo pesado
con.execute("SET memory_limit = '2GB'")
con.execute("SET temp_directory = '/tmp/duckdb_spill'")
con.execute("SET max_temp_directory_size = '50GiB'")
con.execute("SET threads = 1")
con.execute("SET preserve_insertion_order = false")

def log(msg):
    print('>>> ' + msg, flush=True)

# confere o que ja existe no banco
tabelas = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
log('tabelas no banco: ' + ', '.join(tabelas))

# ------------------------------------------------------------
# 4b. ENTRADAS — via sort, nao hash.
#     Primeiro materializa a primeira aparicao ordenando por nis.
#     ROW_NUMBER sobre particao ordenada derrama para disco.
# ------------------------------------------------------------
log('4b. calculando primeira aparicao (via sort)')

# passo 1: para cada NIS, a linha de menor ano_mes.
# usamos QUALIFY com ROW_NUMBER, que o DuckDB resolve por sort.
con.execute("DROP TABLE IF EXISTS primeira_aparicao")
con.execute("""
CREATE TABLE primeira_aparicao AS
SELECT nis, cod_siafi, ano_mes AS primeiro_mes
FROM (
    SELECT nis, cod_siafi, ano_mes,
           ROW_NUMBER() OVER (PARTITION BY nis ORDER BY ano_mes) AS rn
    FROM nis_tmp
)
WHERE rn = 1
""")
log('   primeira_aparicao criada')

# passo 2: conta entradas por municipio x mes (so 202401+)
con.execute("DROP TABLE IF EXISTS bf_entradas")
con.execute("""
CREATE TABLE bf_entradas AS
SELECT cod_siafi, primeiro_mes AS ano_mes, COUNT(*) AS n_entradas
FROM primeira_aparicao
WHERE primeiro_mes >= '202401'
GROUP BY cod_siafi, primeiro_mes
""")
log('   bf_entradas criada')

# ------------------------------------------------------------
# 5. PAINEL
# ------------------------------------------------------------
log('5. montando painel')
con.execute("DROP TABLE IF EXISTS painel")
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
log('   painel criado')

# ------------------------------------------------------------
# 6. EXPORTA
# ------------------------------------------------------------
log('6. exportando')
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
print('=== ENTRADAS BF POR MES (jan/2024 deve estar normalizado) ===')
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
print()
print('Concluido. Painel em', OUT / 'painel_municipio_mes.parquet')
print('Se os numeros baterem, pode apagar build.duckdb (3.3 GB) com:')
print('  rm build.duckdb')
