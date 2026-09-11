#!/usr/bin/env python3
"""
refaz_painel_macbook.py

Versao para rodar no MacBook a partir dos parquet ja materializados
no Monstro. Recalcula bf_variacao/bf_crescimento e monta o painel v4
com a metrica robusta (variacao liquida do estoque em vez de
primeira aparicao).

Assume os arquivos no mesmo diretorio do script:
  - bf_estoque.parquet
  - cat_final.parquet
  - tabmun_siafi.csv  (o de-para; se estiver em outro lugar, ajuste o path)

Uso:
    cd /pasta/onde/estao/os/arquivos
    python3 refaz_painel_macbook.py
"""
import duckdb
import os
from pathlib import Path

# ajuste o caminho do de-para se necessario
DEPARA = 'tabmun_siafi.csv'

# saidas ao lado do script
OUT_PARQUET = 'painel_municipio_mes.parquet'
OUT_CSV = 'painel_municipio_mes.csv'

# checagem de presenca
for f in ['bf_estoque.parquet', 'cat_final.parquet']:
    if not os.path.exists(f):
        raise SystemExit(f'ERRO: {f} nao encontrado no diretorio atual.')

con = duckdb.connect(':memory:')
con.execute("SET memory_limit = '2GB'")
con.execute("SET threads = 2")

# view sobre parquet — nao carrega em memoria, so aponta
con.execute("CREATE VIEW bf_estoque AS SELECT * FROM read_parquet('bf_estoque.parquet')")
con.execute("CREATE VIEW cat_final AS SELECT * FROM read_parquet('cat_final.parquet')")

# de-para — se o arquivo estiver disponivel; senao pula o join geografico
if os.path.exists(DEPARA):
    con.execute(f"""
        CREATE VIEW depara AS
        SELECT column0 AS cod_siafi, column3 AS uf, column2 AS nome_municipio,
               column4 AS cod_ibge7, LEFT(column4,6) AS cod_ibge6
        FROM read_csv('{DEPARA}', header=false, delim=';',
                      encoding='latin-1', ignore_errors=true, all_varchar=true)
    """)
    has_depara = True
else:
    print(f'AVISO: {DEPARA} nao encontrado. Painel sairah sem UF/nome_municipio/cod_ibge7.')
    has_depara = False

# ------------------------------------------------------------
print('>>> calculando variacao liquida do estoque')
con.execute("""
CREATE TABLE bf_variacao AS
WITH com_anterior AS (
    SELECT
        cod_siafi,
        ano_mes,
        n_beneficiarios,
        LAG(n_beneficiarios) OVER (
            PARTITION BY cod_siafi ORDER BY ano_mes
        ) AS n_beneficiarios_ant
    FROM bf_estoque
)
SELECT
    cod_siafi,
    ano_mes,
    n_beneficiarios,
    COALESCE(n_beneficiarios - n_beneficiarios_ant, 0) AS variacao_liquida,
    GREATEST(COALESCE(n_beneficiarios - n_beneficiarios_ant, 0), 0) AS crescimento_liquido
FROM com_anterior
""")

# ------------------------------------------------------------
print('>>> montando painel v4')
if has_depara:
    con.execute("""
    CREATE TABLE painel_v4 AS
    WITH bf_join AS (
        SELECT
            e.cod_siafi, e.ano_mes, e.n_beneficiarios, e.valor_total,
            COALESCE(v.variacao_liquida, 0)     AS bf_variacao,
            COALESCE(v.crescimento_liquido, 0)  AS bf_crescimento
        FROM bf_estoque e
        LEFT JOIN bf_variacao v
          ON e.cod_siafi=v.cod_siafi AND e.ano_mes=v.ano_mes
    )
    SELECT
        d.cod_ibge7, d.cod_ibge6, d.cod_siafi, d.uf, d.nome_municipio,
        COALESCE(bf.ano_mes, cat.ano_mes) AS ano_mes,
        COALESCE(cat.n_cat, 0)         AS n_cat,
        COALESCE(cat.n_obito, 0)       AS n_obito,
        COALESCE(cat.n_cid_mental, 0)  AS n_cid_mental,
        COALESCE(cat.n_cid_lesao, 0)   AS n_cid_lesao,
        COALESCE(cat.n_cid_musculo, 0) AS n_cid_musculo,
        COALESCE(bf.n_beneficiarios, 0)AS bf_beneficiarios,
        COALESCE(bf.bf_variacao, 0)    AS bf_variacao,
        COALESCE(bf.bf_crescimento, 0) AS bf_crescimento,
        COALESCE(bf.valor_total, 0)    AS bf_valor_total
    FROM depara d
    LEFT JOIN bf_join bf ON d.cod_siafi=bf.cod_siafi
    LEFT JOIN cat_final cat ON d.cod_ibge6=cat.cod_ibge6 AND cat.ano_mes=bf.ano_mes
    WHERE COALESCE(bf.ano_mes, cat.ano_mes) IS NOT NULL
    """)
else:
    # sem de-para, saida menor mas ainda util
    con.execute("""
    CREATE TABLE painel_v4 AS
    SELECT
        e.cod_siafi, e.ano_mes, e.n_beneficiarios,
        COALESCE(v.variacao_liquida, 0)     AS bf_variacao,
        COALESCE(v.crescimento_liquido, 0)  AS bf_crescimento
    FROM bf_estoque e
    LEFT JOIN bf_variacao v
      ON e.cod_siafi=v.cod_siafi AND e.ano_mes=v.ano_mes
    """)

# ------------------------------------------------------------
print('>>> exportando')
con.execute(f"COPY painel_v4 TO '{OUT_PARQUET}' (FORMAT parquet)")
con.execute(f"COPY painel_v4 TO '{OUT_CSV}' (FORMAT csv, HEADER true)")

# ------------------------------------------------------------
print()
print('=== LINHAS NO PAINEL ===')
print(con.execute("SELECT COUNT(*) FROM painel_v4").fetchone())

print()
print('=== VARIACAO POR MES (nacional) ===')
for row in con.execute("""
    SELECT ano_mes,
           SUM(bf_variacao)     AS variacao_total,
           SUM(bf_crescimento)  AS crescimento_total,
           SUM(n_beneficiarios) AS estoque_total
    FROM painel_v4 GROUP BY ano_mes ORDER BY ano_mes
""").fetchall():
    print(' ', row[0], '| variacao:', f'{row[1]:>+12}', '| crescimento:', f'{row[2]:>11}', '| estoque:', f'{row[3]:>11}')

if has_depara:
    print()
    print('=== AMOSTRA (top 10 municipios por n_cat, com bf_crescimento) ===')
    for row in con.execute("""
        SELECT nome_municipio, uf, ano_mes, n_cat, n_obito, n_cid_mental,
               bf_variacao, bf_crescimento
        FROM painel_v4
        WHERE n_cat > 0 AND bf_beneficiarios > 0
        ORDER BY n_cat DESC LIMIT 10
    """).fetchall():
        print(' ', row)

con.close()
print()
print('Painel v4 salvo em', OUT_PARQUET, 'e', OUT_CSV)