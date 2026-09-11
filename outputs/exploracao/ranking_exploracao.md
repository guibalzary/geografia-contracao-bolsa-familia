# Exploração do ranking — 11/09/2026

## 1. Distribuição de CAT por CNAE_div

Top 20 divisões CNAE por volume total de CATs (soma de todos os CNPJs do setor).

|   cnae_div | cnae_nome            |   cat_total |   obito_total |   n_cnpjs |   cat_mediana_cnpj |   cat_p90_cnpj |   cat_max_cnpj |   letalidade_pct |   pct_total |
|-----------:|:---------------------|------------:|--------------:|----------:|-------------------:|---------------:|---------------:|-----------------:|------------:|
|         86 | Atividades de Atendi |       98233 |            35 |      2266 |               23   |           99   |           1375 |        0.0356296 |    14.1807  |
|         47 | Comercio Varejista d |       42852 |            94 |      4645 |                7   |           15   |            109 |        0.21936   |     6.18603 |
|         84 | Administracao Public |       25794 |            62 |      1033 |               12   |           53   |            572 |        0.240366  |     3.72357 |
|         46 | Comercio Atacadista  |       23708 |            70 |      2420 |                7   |           17   |            131 |        0.295259  |     3.42244 |
|         49 | Transporte Rodoviari |       23070 |           197 |      1945 |                8   |           21   |            208 |        0.853923  |     3.33034 |
|         10 | Abate de Suinos, Ave |       20513 |            47 |       282 |               44   |          174.4 |            521 |        0.229123  |     2.96122 |
|         78 | Locacao de Mao-De-Ob |       14453 |            38 |       513 |               13   |           57   |            568 |        0.262921  |     2.08641 |
|         86 | Atividades de Apoio  |       14451 |             6 |       243 |               18   |           95   |           1882 |        0.0415196 |     2.08612 |
|         38 | Coleta de Residuos N |       13222 |            36 |       280 |               19   |          124.1 |            545 |        0.272273  |     1.9087  |
|         10 | Abate de Reses, Exce |       12827 |            27 |       317 |               18   |          104   |            271 |        0.210493  |     1.85168 |
|         28 | Fabricacao de Maquin |       10962 |            12 |       762 |                8   |           29   |            244 |        0.109469  |     1.58245 |
|         10 | Fabricacao de Produt |       10513 |            14 |       645 |               10   |           30.6 |            305 |        0.133168  |     1.51764 |
|         41 | Construcao de Edific |       10381 |            53 |       850 |                8   |           22   |            585 |        0.510548  |     1.49858 |
|         86 | Atividades de Atenca |       10005 |             3 |       369 |                8   |           61.8 |            457 |        0.029985  |     1.4443  |
|         81 | Limpeza em Predios e |        9943 |            14 |       420 |                9.5 |           46.2 |            553 |        0.140803  |     1.43535 |
|         29 | Fabricacao de Pecas  |        8496 |            10 |       431 |               11   |           42   |            292 |        0.117702  |     1.22647 |
|         10 | Fabricacao de Acucar |        7974 |            48 |       172 |               32   |          102.7 |            323 |        0.601956  |     1.15111 |
|         56 | Servicos de Catering |        7831 |            11 |       517 |                8   |           29   |            430 |        0.140467  |     1.13047 |
|         86 | Atividades de Servic |        7100 |             4 |       703 |                7   |           16   |            150 |        0.056338  |     1.02494 |
|         22 | Fabricacao de Artefa |        6730 |            16 |       543 |                8   |           23   |            144 |        0.237741  |     0.97153 |

## 2. Hospitais notáveis — presença no dataset

Busca por palavra-chave na razão social (BrasilAPI), no ranking completo (42.911 CNPJs).

| referencia                         |   n_cnpjs_encontrados |   cat_soma |   obito_soma |   letalidade_pct |   melhor_posicao_ranking |
|:-----------------------------------|----------------------:|-----------:|-------------:|-----------------:|-------------------------:|
| Amil / Rede Total Health           |                     2 |       1429 |            0 |                0 |                        7 |
| A.C. Camargo Cancer Center         |                     0 |          0 |            0 |              nan |                      nan |
| Beneficência Portuguesa SP         |                     0 |          0 |            0 |              nan |                      nan |
| DASA                               |                     0 |          0 |            0 |              nan |                      nan |
| Grupo Fleury                       |                     0 |          0 |            0 |              nan |                      nan |
| HC-FMUSP                           |                     0 |          0 |            0 |              nan |                      nan |
| Hospital Alemão Oswaldo Cruz       |                     0 |          0 |            0 |              nan |                      nan |
| Hospital Israelita Albert Einstein |                     0 |          0 |            0 |              nan |                      nan |
| Hospital Sírio-Libanês             |                     0 |          0 |            0 |              nan |                      nan |
| Instituto Nacional de Câncer       |                     0 |          0 |            0 |              nan |                      nan |
| Rede D'Or São Luiz                 |                     0 |          0 |            0 |              nan |                      nan |

### Matches individuais (top por CAT)

| busca   | razao_social                |   cnpj_raiz |   cnae_div |   n_cat |   n_obito |
|:--------|:----------------------------|------------:|-----------:|--------:|----------:|
| AMIL    | ASSOCIACAO SAUDE DA FAMILIA |    68311216 |         86 |     875 |         0 |

## 3. MIN para Fig 1

Quantos CNAEs sobrevivem a cada corte de mínimo de municípios:

- MIN=20: 40 CNAEs, 4291 municípios (95.2% do total)
- MIN=30: 31 CNAEs, 4072 municípios (90.3% do total)
- MIN=50: 17 CNAEs, 3524 municípios (78.2% do total)
- MIN=75: 12 CNAEs, 3202 municípios (71.0% do total)
- MIN=100: 10 CNAEs, 3045 municípios (67.5% do total)
- MIN=150: 6 CNAEs, 2608 municípios (57.8% do total)
- MIN=200: 5 CNAEs, 2413 municípios (53.5% do total)

### Top 20 CNAEs por número de municípios dominados

|   cnae_dominante | cnae_dominante_nome   |   n_municipios |
|-----------------:|:----------------------|---------------:|
|               10 | Abate de Suinos, Ave  |            683 |
|               47 | Comercio Varejista d  |            635 |
|               84 | Administracao Public  |            401 |
|               01 | Criacao de Aves       |            361 |
|               86 | Atividades de Atendi  |            333 |
|               46 | Comercio Atacadista   |            195 |
|               23 | Fabricacao de Artefa  |            114 |
|               49 | Transporte Rodoviari  |            110 |
|               16 | Desdobramento de Mad  |            109 |
|               08 | Extracao de Pedra, A  |            104 |
|               15 | Fabricacao de Calcad  |             80 |
|               82 | Servicos Combinados   |             77 |
|               19 | Fabricacao de Alcool  |             70 |
|               02 | Producao Florestal -  |             65 |
|               25 | Fabricacao de Produt  |             64 |
|               31 | Fabricacao de Moveis  |             62 |
|               42 | Obras para Geracao e  |             61 |
|               64 | Bancos Multiplos, co  |             47 |
|               41 | Construcao de Edific  |             47 |
|               55 | Hoteis e Similares    |             46 |
