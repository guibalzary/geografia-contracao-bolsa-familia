#!/usr/bin/env python3
"""
agrega_cat_cnae.py — VERSAO MONSTRO (Windows, 16 GB RAM, 8+ threads)

Agregacoes derivadas da CAT (Comunicacoes de Acidente de Trabalho / INSS)
com granularidade por CNAE secao.

Le CSVs brutos de data/raw/cat/*.csv e escreve em data/processed/:
  - cat_cnae_mun_mes.parquet
  - cat_cnae_mun.parquet
  - cat_cnpj_ranking.parquet
  - cat_cnae_secao_dic.parquet

Uso (do diretorio D:\\_repos\\cgu):
    conda activate cgu
    cd D:\\_repos\\cgu
    python agrega_cat_cnae.py
"""
import duckdb
import os
from pathlib import Path

# ------------------------------------------------------------
# CONFIG — ajuste aqui se necessario
# ------------------------------------------------------------
PROJETO = Path(r'D:\_repos\cgu')
RAW_CAT_GLOB = str(PROJETO / 'data' / 'raw' / 'cat' / '*.csv')
OUT = PROJETO / 'data' / 'processed'
TEMP_SPILL = PROJETO / '_tmp_duckdb'

OUT.mkdir(parents=True, exist_ok=True)
TEMP_SPILL.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(':memory:')
con.execute("SET memory_limit = '10GB'")
con.execute("SET threads = 8")
con.execute(f"SET temp_directory = '{TEMP_SPILL.as_posix()}'")

# usar as_posix() nos paths para evitar dor de cabeca com barras invertidas no SQL
RAW_CAT_GLOB_SQL = RAW_CAT_GLOB.replace('\\', '/')

# ------------------------------------------------------------
print('>>> lendo CAT bruta e agregando por municipio x mes x CNAE')
con.execute(f"""
CREATE TABLE cat_raw AS
SELECT
    SPLIT_PART("Munic Empr", '-', 1)                     AS cod_ibge6,
    STRFTIME("Data Acidente", '%Y%m')                    AS ano_mes,
    LEFT("CID-10", 1)                                    AS cid_capitulo,
    LEFT("CNAE2.0 Empregador", 2)                        AS cnae_div,
    "CNAE2.0 Empregador"                                 AS cnae_cod,
    "CNAE2.0 Empregador_1"                               AS cnae_nome,
    "Indica Óbito Acidente"                              AS obito,
    "CNPJ/CEI Empregador"                                AS cnpj,
    "Sexo"                                               AS sexo,
    "Data Afastamento"                                   AS data_afastamento
FROM read_csv('{RAW_CAT_GLOB_SQL}', delim=';', quote='"', encoding='latin-1',
              header=true, ignore_errors=true)
WHERE STRFTIME("Data Acidente", '%Y%m') BETWEEN '202401' AND '202512'
  AND SPLIT_PART("Munic Empr", '-', 1) IS NOT NULL
  AND LENGTH(SPLIT_PART("Munic Empr", '-', 1)) = 6
""")
n = con.execute("SELECT COUNT(*) FROM cat_raw").fetchone()[0]
print(f'    {n:,} linhas na janela 202401-202512')

# ------------------------------------------------------------
print('>>> cat_cnae_mun_mes: municipio x mes x cnae_divisao')
con.execute(f"""
CREATE TABLE cat_cnae_mun_mes AS
SELECT
    cod_ibge6, ano_mes, cnae_div,
    COUNT(*)                                              AS n_cat,
    SUM(CASE WHEN obito ILIKE 'sim%' THEN 1 ELSE 0 END)   AS n_obito,
    SUM(CASE WHEN cid_capitulo='F' THEN 1 ELSE 0 END)     AS n_cid_mental,
    SUM(CASE WHEN cid_capitulo IN ('S','T') THEN 1 ELSE 0 END) AS n_cid_lesao,
    SUM(CASE WHEN cid_capitulo='M' THEN 1 ELSE 0 END)     AS n_cid_musculo,
    SUM(CASE WHEN data_afastamento IS NOT NULL
              AND data_afastamento != ''
              AND data_afastamento != '00/00/0000'
             THEN 1 ELSE 0 END)                           AS n_com_afastamento
FROM cat_raw
GROUP BY cod_ibge6, ano_mes, cnae_div
""")
n = con.execute("SELECT COUNT(*) FROM cat_cnae_mun_mes").fetchone()[0]
print(f'    {n:,} linhas (mun x mes x cnae)')
saida = (OUT / 'cat_cnae_mun_mes.parquet').as_posix()
con.execute(f"COPY cat_cnae_mun_mes TO '{saida}' (FORMAT parquet)")

# ------------------------------------------------------------
print('>>> cat_cnae_mun: municipio x cnae (2024-2025 agregado)')
con.execute(f"""
CREATE TABLE cat_cnae_mun AS
SELECT
    cod_ibge6, cnae_div,
    SUM(n_cat)              AS n_cat,
    SUM(n_obito)            AS n_obito,
    SUM(n_cid_mental)       AS n_cid_mental,
    SUM(n_cid_lesao)        AS n_cid_lesao,
    SUM(n_cid_musculo)      AS n_cid_musculo,
    SUM(n_com_afastamento)  AS n_com_afastamento
FROM cat_cnae_mun_mes
GROUP BY cod_ibge6, cnae_div
""")
n = con.execute("SELECT COUNT(*) FROM cat_cnae_mun").fetchone()[0]
print(f'    {n:,} linhas (mun x cnae)')
saida = (OUT / 'cat_cnae_mun.parquet').as_posix()
con.execute(f"COPY cat_cnae_mun TO '{saida}' (FORMAT parquet)")

# ------------------------------------------------------------
print('>>> cat_cnpj_ranking: top empresas por CATs no periodo')
con.execute(f"""
CREATE TABLE cat_cnpj_ranking AS
SELECT
    cnpj,
    ANY_VALUE(cnae_div)                                   AS cnae_div,
    ANY_VALUE(cnae_nome)                                  AS cnae_nome,
    COUNT(*)                                              AS n_cat,
    SUM(CASE WHEN obito ILIKE 'sim%' THEN 1 ELSE 0 END)   AS n_obito,
    SUM(CASE WHEN cid_capitulo='F' THEN 1 ELSE 0 END)     AS n_cid_mental,
    COUNT(DISTINCT cod_ibge6)                             AS n_municipios
FROM cat_raw
WHERE cnpj IS NOT NULL AND cnpj != ''
GROUP BY cnpj
HAVING COUNT(*) >= 5
ORDER BY n_cat DESC
""")
n = con.execute("SELECT COUNT(*) FROM cat_cnpj_ranking").fetchone()[0]
print(f'    {n:,} empresas com >=5 CATs no periodo')
saida = (OUT / 'cat_cnpj_ranking.parquet').as_posix()
con.execute(f"COPY cat_cnpj_ranking TO '{saida}' (FORMAT parquet)")

# ------------------------------------------------------------
print('>>> cat_cnae_secao_dic: mapa codigo -> nome mais frequente')
con.execute(f"""
CREATE TABLE cat_cnae_secao_dic AS
SELECT cnae_div,
       MODE(cnae_nome) AS cnae_nome_exemplo,
       COUNT(*)        AS ocorrencias
FROM cat_raw
GROUP BY cnae_div
ORDER BY ocorrencias DESC
""")
n = con.execute("SELECT COUNT(*) FROM cat_cnae_secao_dic").fetchone()[0]
print(f'    {n:,} codigos CNAE distintos (divisao 2 digitos)')
saida = (OUT / 'cat_cnae_secao_dic.parquet').as_posix()
con.execute(f"COPY cat_cnae_secao_dic TO '{saida}' (FORMAT parquet)")

# ------------------------------------------------------------
print()
print('=== TOP 15 CNAE POR VOLUME DE CAT ===')
for row in con.execute("""
    SELECT c.cnae_div,
           d.cnae_nome_exemplo,
           SUM(c.n_cat) AS total_cat,
           SUM(c.n_obito) AS total_obito,
           SUM(c.n_cid_mental) AS total_cid_mental
    FROM cat_cnae_mun c
    LEFT JOIN cat_cnae_secao_dic d USING (cnae_div)
    GROUP BY c.cnae_div, d.cnae_nome_exemplo
    ORDER BY total_cat DESC LIMIT 15
""").fetchall():
    print(f'   {row[0]:>3} | {(row[1] or "")[:40]:<40} | CAT={row[2]:>8,} | obitos={row[3]:>4,} | CID-F={row[4]:>4,}')

print()
print('=== TOP 15 EMPRESAS POR CAT ===')
for row in con.execute("""
    SELECT cnpj, cnae_div, cnae_nome, n_cat, n_obito, n_cid_mental, n_municipios
    FROM cat_cnpj_ranking LIMIT 15
""").fetchall():
    print(f'   CNPJ={row[0]} | {row[1]} {(row[2] or "")[:30]:<30} | CAT={row[3]:>6,} | obitos={row[4]:>3} | F={row[5]:>3} | muns={row[6]:>3}')

print()
print('Arquivos gerados em', OUT)
print('  cat_cnae_mun_mes.parquet')
print('  cat_cnae_mun.parquet')
print('  cat_cnpj_ranking.parquet')
print('  cat_cnae_secao_dic.parquet')

con.close()
