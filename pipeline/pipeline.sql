-- ============================================================
-- pipeline.sql — Reúso CAT x Bolsa Família  (v3 com warm-up)
-- Painel ecológico município x mês (jan/2024 a dez/2025)
--
-- Warm-up: 202312 entra APENAS no cálculo de entradas (base de
-- comparação para janeiro/2024), mas NÃO entra no painel final.
-- Resultado: 24 meses limpos e simétricos, 202401-202512.
--
-- Uso:
--   cd /Users/guilhermecamargo/Developer/cgu/data-mapping
--   duckdb < pipeline.sql
-- ============================================================

SET memory_limit = '5GB';
SET threads = 2;
SET temp_directory = '/tmp/duckdb_spill';
SET max_temp_directory_size = '40GiB';
SET preserve_insertion_order = false;

-- ------------------------------------------------------------
-- 1. DE-PARA SIAFI <-> IBGE
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE depara AS
SELECT
    column0                       AS cod_siafi,
    column3                       AS uf,
    column2                       AS nome_municipio,
    column4                       AS cod_ibge7,
    LEFT(column4, 6)              AS cod_ibge6
FROM read_csv(
    'data/aux/tabmun_siafi.csv',
    header = false, delim = ';', encoding = 'latin-1',
    ignore_errors = true, all_varchar = true
);

-- ------------------------------------------------------------
-- 2. CAT — agregação município x mês
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE cat_mun_mes AS
WITH cat_raw AS (
    SELECT
        SPLIT_PART("Munic Empr", '-', 1)              AS cod_ibge6,
        STRFTIME("Data Acidente", '%Y%m')             AS ano_mes,
        LEFT("CID-10", 1)                              AS cid_capitulo,
        LEFT("CNAE2.0 Empregador", 2)                  AS cnae_secao,
        "Indica Óbito Acidente"                        AS obito
    FROM read_csv(
        'data/raw/cat/*.csv',
        delim = ';', quote = '"', encoding = 'latin-1',
        header = true, ignore_errors = true
    )
    WHERE STRFTIME("Data Acidente", '%Y%m') BETWEEN '202401' AND '202512'
)
SELECT
    cod_ibge6,
    ano_mes,
    COUNT(*)                                                  AS n_cat,
    SUM(CASE WHEN obito ILIKE 'sim%' THEN 1 ELSE 0 END)       AS n_obito,
    SUM(CASE WHEN cid_capitulo = 'F' THEN 1 ELSE 0 END)       AS n_cid_mental,
    SUM(CASE WHEN cid_capitulo IN ('S','T') THEN 1 ELSE 0 END) AS n_cid_lesao,
    SUM(CASE WHEN cid_capitulo = 'M' THEN 1 ELSE 0 END)       AS n_cid_musculo
FROM cat_raw
WHERE cod_ibge6 IS NOT NULL AND LENGTH(cod_ibge6) = 6
GROUP BY cod_ibge6, ano_mes;

-- ------------------------------------------------------------
-- 3b. BF — estoque. Só janela final (202401+), SEM warm-up.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE bf_estoque AS
SELECT
    "CÓDIGO MUNICÍPIO SIAFI"                    AS cod_siafi,
    CAST("MÊS COMPETÊNCIA" AS VARCHAR)          AS ano_mes,
    COUNT(DISTINCT "NIS FAVORECIDO")            AS n_beneficiarios,
    SUM(CAST(REPLACE("VALOR PARCELA", ',', '.') AS DOUBLE)) AS valor_total
FROM read_csv(
    'data/raw/bf/*.csv',
    delim = ';', quote = '"', encoding = 'latin-1',
    header = true, ignore_errors = true
)
WHERE "MÊS COMPETÊNCIA" = "MÊS REFERÊNCIA"
  AND CAST("MÊS COMPETÊNCIA" AS VARCHAR) >= '202401'
GROUP BY 1, 2;

-- ------------------------------------------------------------
-- 3a+3c. BF — entradas. INCLUI warm-up 202312 na base de
--   comparação. A primeira aparição de cada NIS é calculada
--   sobre 202312+, mas depois filtramos para manter só
--   entradas em 202401+ (as de 202312 eram só referência).
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE bf_entradas AS
WITH primeira_aparicao AS (
    SELECT
        "NIS FAVORECIDO"                              AS nis,
        MIN("CÓDIGO MUNICÍPIO SIAFI")                 AS cod_siafi,
        MIN(CAST("MÊS COMPETÊNCIA" AS VARCHAR))       AS primeiro_mes
    FROM read_csv(
        'data/raw/bf/*.csv',
        delim = ';', quote = '"', encoding = 'latin-1',
        header = true, ignore_errors = true
    )
    WHERE "MÊS COMPETÊNCIA" = "MÊS REFERÊNCIA"
      AND CAST("MÊS COMPETÊNCIA" AS VARCHAR) >= '202312'
    GROUP BY "NIS FAVORECIDO"
)
SELECT
    cod_siafi,
    primeiro_mes    AS ano_mes,
    COUNT(*)        AS n_entradas
FROM primeira_aparicao
WHERE primeiro_mes >= '202401'    -- descarta os que já estavam em 202312
GROUP BY cod_siafi, primeiro_mes;

-- ------------------------------------------------------------
-- 4. PAINEL
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE painel AS
WITH bf_join AS (
    SELECT
        e.cod_siafi, e.ano_mes, e.n_beneficiarios, e.valor_total,
        COALESCE(ent.n_entradas, 0) AS n_entradas
    FROM bf_estoque e
    LEFT JOIN bf_entradas ent
        ON e.cod_siafi = ent.cod_siafi AND e.ano_mes = ent.ano_mes
)
SELECT
    d.cod_ibge7, d.cod_ibge6, d.cod_siafi, d.uf, d.nome_municipio,
    COALESCE(bf.ano_mes, cat.ano_mes)          AS ano_mes,
    COALESCE(cat.n_cat, 0)                      AS n_cat,
    COALESCE(cat.n_obito, 0)                    AS n_obito,
    COALESCE(cat.n_cid_mental, 0)              AS n_cid_mental,
    COALESCE(cat.n_cid_lesao, 0)               AS n_cid_lesao,
    COALESCE(cat.n_cid_musculo, 0)             AS n_cid_musculo,
    COALESCE(bf.n_beneficiarios, 0)            AS bf_beneficiarios,
    COALESCE(bf.n_entradas, 0)                 AS bf_entradas,
    COALESCE(bf.valor_total, 0)                AS bf_valor_total
FROM depara d
LEFT JOIN bf_join bf
    ON d.cod_siafi = bf.cod_siafi
LEFT JOIN cat_mun_mes cat
    ON d.cod_ibge6 = cat.cod_ibge6 AND cat.ano_mes = bf.ano_mes
WHERE COALESCE(bf.ano_mes, cat.ano_mes) IS NOT NULL;

-- ------------------------------------------------------------
-- 5. EXPORTA
-- ------------------------------------------------------------
COPY painel TO 'data/processed/painel_municipio_mes.parquet' (FORMAT parquet);
COPY painel TO 'data/processed/painel_municipio_mes.csv' (FORMAT csv, HEADER true);

-- ------------------------------------------------------------
-- 6. SANIDADE
-- ------------------------------------------------------------
.print '=== LINHAS NO PAINEL ==='
SELECT COUNT(*) AS linhas_painel FROM painel;

.print '=== COBERTURA TEMPORAL ==='
SELECT MIN(ano_mes) AS primeiro, MAX(ano_mes) AS ultimo,
       COUNT(DISTINCT ano_mes) AS meses FROM painel;

.print '=== ENTRADAS BF POR MES (conferir se jan/2024 normalizou) ==='
SELECT ano_mes, SUM(bf_entradas) AS entradas_totais
FROM painel GROUP BY ano_mes ORDER BY ano_mes;

.print '=== TOTAIS DE CONTROLE ==='
SELECT SUM(n_cat) AS total_cat, SUM(n_obito) AS total_obitos,
       SUM(n_cid_mental) AS total_cid_mental, SUM(bf_entradas) AS total_entradas_bf
FROM painel;

.print '=== CASAMENTO CAT<->BF ==='
SELECT
    COUNT(*) FILTER (WHERE n_cat > 0 AND bf_beneficiarios > 0) AS ambos,
    COUNT(*) FILTER (WHERE n_cat > 0 AND bf_beneficiarios = 0) AS so_cat,
    COUNT(*) FILTER (WHERE n_cat = 0 AND bf_beneficiarios > 0) AS so_bf
FROM painel;
