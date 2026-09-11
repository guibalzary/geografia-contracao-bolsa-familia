# Metodologia

Documento técnico detalhando decisões metodológicas, escolhas de escopo, limitações reconhecidas e próximos passos deste reúso.

## 1. Perguntas de partida e pivô

O reúso começou com uma hipótese temporal específica: se a Comunicação de Acidente de Trabalho (CAT) é o registro formal do evento que retira ou compromete a capacidade laborativa da pessoa, então em algum horizonte razoável (semanas a meses) parte dessas famílias deveria aparecer no Bolsa Família — sinal de que a proteção previdenciária stricto sensu não bastou e a assistência social absorveu o choque.

Essa hipótese foi testada. Não sustentou (Seção 5 abaixo). O resultado é preservado neste reúso como a Figura 3 e é insumo direto da Seção 5 da metodologia. O pivô para a análise estrutural (perfil setorial × variação BF, Figura 1) e para o desmembramento volume × letalidade (Figura 2) aconteceu na noite de 10 para 11 de setembro de 2026, com base nos dados já processados.

Registrar o resultado nulo é escolha editorial deliberada, que visa manter transparência sobre o estudo, e honestidade com o que os dados apresentam.

## 2. Fontes e cobertura

**Bolsa Família — Pagamentos (MDS)**. Fornecido pelo Portal da Transparência da CGU, arquivado mensalmente. Cada arquivo mensal contém uma linha por pagamento efetuado — NIS do beneficiário, município, valor, data. Volume: dezenas de milhões de linhas por mês. Cobertura utilizada: 25 arquivos, de dezembro de 2023 (warm-up para detectar entradas em janeiro de 2024) a dezembro de 2025.

**Comunicação de Acidente de Trabalho — CAT (INSS)**. Disponibilizada no dados.gov.br com granularidade de uma linha por CAT emitida. Campos utilizados: CNPJ do empregador, CNAE de divisão (2 dígitos) do vínculo, município do acidente (código IBGE de 6 dígitos), tipo de CAT (típica, trajeto, doença), agrupador de CID (mental, lesão, musculoesquelética), indicador de óbito. Volume: mais de 1 milhão de registros por ano.

**Tabela auxiliar SIAFI × IBGE7**. Dicionário para conversão entre os códigos de município utilizados pelas duas bases (o BF trafega em IBGE6 truncado; a CAT em IBGE7; alguns cruzamentos com SIAFI foram necessários).

Bases descartadas por escopo neste primeiro corte: RAIS (para taxa CAT/empregado por CNPJ), CadÚnico (para causa da saída do BF), Novo CAGED (para dinâmica de vínculos formais). Cada uma delas volta como próximo passo natural em iteração futura.

## 3. Pipeline de processamento

Executado em duas máquinas por decisão de custo/RAM:

- **MacBook Pro 2017 (8 GB RAM, dual-core i5)** — usado para coleta, primeira agregação BF (que estourou memória e forçou reescrita) e todas as figuras.
- **Desktop AMD Ryzen 7 1700 (16 GB RAM, SSD, Windows 10)** — usado para o painel mensal completo e para as agregações CAT × CNAE × município, onde o número de chaves distintas (~25 milhões de NIS na base BF) inviabilizou o Mac.

O pipeline canônico (ordem de execução):

1. `pipeline/download_bf.sh` e `pipeline/download_cat.sh` — coleta em lote, com retentativa em falhas HTTP.
2. `pipeline/build_painel.py` — constrói o painel município × mês (estoque BF, entradas BF, vale, pico), com warm-up em dezembro/2023.
3. `pipeline/agrega_cat_cnae.py` — agrega CAT por CNAE de divisão × município × mês; produz `cat_cnae_mun.parquet` e `cat_cnpj_ranking.parquet`.
4. `pipeline/cruza_estrutural.py` — cruza o painel BF com o CNAE dominante de cada município (definido como divisão CNAE de 2 dígitos com o maior número de CATs no período); produz `painel_estrutural.parquet`.
5. `pipeline/analise_correlacao.py` — calcula Spearman por município entre séries CAT e entradas BF, para cinco defasagens; produz `correlacoes_municipais.parquet`.
6. `figuras/fig1_gradiente_cnae.py`, `figuras/fig2_cnae_volume_letalidade.py`, `figuras/fig3_correlacoes_temporais.py` — geração das figuras a partir dos artefatos processados.

**DuckDB** foi o motor SQL de todas as agregações — leitura direta de parquet, agregação em disco quando necessário, sem carregar tudo em memória. Onde havia risco de OOM em máquina de 16 GB, adotou-se estratégia de ordenação (`ROW_NUMBER OVER ORDER BY`) em vez de hash agregação.

**Idempotência.** Todos os scripts do pipeline são idempotentes: podem ser reexecutados sem duplicar dado ou corromper artefato. Coleta pula arquivos já baixados; agregações sobrescrevem parquet inteiro.

## 4. Escolha da unidade de análise

Duas escolhas críticas moldaram todas as figuras:

**Escolha 1 — Município como unidade da análise BF.** O BF é pago por família, identificado por NIS. A agregação para município preserva a geografia mas perde a capacidade de rastrear a família individual entre programas. A alternativa (análise por NIS) exigiria linkage entre CAT e BF que a proteção do dado individual não permite. A unidade municipal é o ponto máximo de granularidade geográfica publicamente disponível.

**Escolha 2 — Divisão CNAE (2 dígitos) como unidade da análise setorial.** O CNAE tem cinco níveis: seção (1 letra), divisão (2 dígitos), grupo (3), classe (4), subclasse (7). Divisão é o nível em que setores comparáveis se distinguem sem fragmentar excessivamente. Exemplos: divisão 86 é "Atividades de atendimento à saúde humana" (hospitais + clínicas + laboratórios + odonto); divisão 49 é "Transporte terrestre" (rodoviário de carga + rodoviário de passageiro + ferroviário). Fragmentar mais expõe a ruído; agregar mais perde diferenciação útil.

**Escolha 3 — CNAE dominante do município.** Cada município recebeu como perfil o CNAE de divisão com maior número de CATs emitidas no biênio. É um proxy da vitalidade econômica local — municípios cuja economia efetivamente movimenta trabalho formal aparecem com esse trabalho representado. Municípios de perfil rural com pouca formalização podem ter CNAE dominante que subrepresenta a atividade real (safra sazonal, informalidade agrícola).

## 5. Teste temporal e resultado nulo

A hipótese testada foi: para cada município com série mensal suficientemente longa, a Comunicação de Acidente de Trabalho precede — em algum horizonte de meses — a entrada de nova família no Bolsa Família (NIS aparecendo pela primeira vez no cadastro de pagamentos).

Método: correlação de Spearman entre a série mensal de CATs e a série mensal de entradas no BF, calculada município a município, para cinco defasagens (0, 1, 2, 3 e 6 meses). Municípios com menos de 12 meses de série foram excluídos (aproximadamente 3.500 dos 5.589; a maioria são municípios pequenos com meses zerados). A base final da análise temporal é de aproximadamente 2.000 municípios por defasagem.

Resultado: a distribuição das correlações é ampla e centrada em torno do zero. Medianas por defasagem:

- Lag 0: −0,099
- Lag 1: −0,128
- Lag 2: +0,042
- Lag 3: +0,029
- Lag 6: +0,194

A dispersão é grande (IQR aproximadamente [−0,25, +0,20] em cada defasagem), com whiskers cobrindo praticamente todo o intervalo [−0,7, +0,7]. O sinal fraco no lag 6 (+0,194) é notável mas insuficiente para sustentar hipótese direcional. Investigação futura poderia testar granularidade trimestral ou anual, ou restringir a municípios com perfil de emprego formal denso — está fora do escopo desta iteração.

A decisão de abandonar a hipótese temporal e pivotar para a análise estrutural (Figuras 1 e 2) é fundamentada nesses números. Todos os cálculos são reproduzíveis a partir de `pipeline/analise_correlacao.py` sobre os artefatos de `data/processed/`.

## 6. O gradiente estrutural — o que ele mede, o que ele não mede

A Figura 1 mostra que municípios de perfil setorial X tiveram variação mediana Y no estoque BF. Isso é factual.

O que a Figura 1 **não permite dizer**, e que este reúso deliberadamente não afirma:

- Que o setor econômico dominante *causou* a variação. É correlação ecológica municipal. Individualmente, cada família que saiu ou entrou no BF tem uma história — corte administrativo por inconsistência cadastral, melhora ou piora de renda, mudança de composição familiar, óbito, migração. O dado agregado por município não distingue.
- Que "menos contração é melhor" ou "mais contração é melhor". A revisão do CadÚnico de 2024-2025 produziu três tipos de saída em proporções que ninguém sabe: (a) saída por melhora efetiva de renda, (b) corte administrativo por inconsistência cadastral, (c) exclusão indevida por falha operacional (não atualização, mudança de endereço, perda de prazo). Cada tipo tem valor moral e político diferente; o dado bruto não separa.
- Que o dinamismo econômico do setor local seja a única — ou mesmo a principal — explicação do gradiente. Ao menos quatro hipóteses são compatíveis:
    1. Capacidade operacional local do CRAS (municípios com CRAS mais estruturado convocam, atualizam e cortam mais eficientemente).
    2. Perfil demográfico predominante (composição familiar, escolaridade, idade média — determinantes fortes da elegibilidade formal).
    3. Regularidade cadastral prévia (municípios com histórico de cadastro atualizado sofrem menos revisão).
    4. Vitalidade econômica setorial (a hipótese que subjaz à leitura ingênua do gradiente).

Distinguir uma dessas hipóteses da outra exige cruzamento com dados operacionais do CadÚnico e com RAIS. Nenhum desses cruzamentos está no escopo desta iteração.

O que sobra afirmar honestamente: **o mapa da contração é desigual, e essa desigualdade correlaciona com o perfil setorial dominante do município de forma que merece investigação**. A intenção deste reúso é de adicionar camadas de informação à retração já bem noticiada do Bolsa Família, trazendo mais fatos para a luz, e desejavelmente, que as constatações abram portas para ainda mais inteligência.

## 7. Volume × Letalidade — por que o ranking por CNPJ foi rejeitado como figura principal

Uma versão anterior da Figura 2 apresentava o ranking dos 20 CNPJs com maior número absoluto de CATs no biênio. O ranking é dominado por hospitais grandes (Santa Casa de SP, Grupo Hospitalar Conceição, Fundação do ABC, Hospital de Clínicas de Porto Alegre) e por bancos, com uma indústria isolada no topo (TUPY S/A, fundição de ferro em Joinville). A leitura ingênua é: "hospitais são os maiores empregadores acidentados do Brasil."

Essa leitura é errada por dois motivos, expostos textualmente na Fig 2 como parte do valor do reúso:

**Viés de escala.** Volume absoluto de CAT é função direta do tamanho da folha de pagamento. Grandes empregadores concentrados aparecem no topo por escala; setores fragmentados em milhares de CNPJs pequenos (transporte rodoviário de carga, construção civil terceirizada, comércio varejista) desaparecem apesar de agregarem mais CAT total quando somados. A leitura correta exige normalização por número de vínculos (RAIS), fora do escopo desta iteração.

**Viés de gravidade.** O número absoluto de CAT não diferencia entre "arranhão que virou CAT porque o SESMT do hospital é bem estruturado" e "óbito em canteiro de obras". A separação em volume × letalidade é o que revela onde o trabalho é efetivamente perigoso: transporte rodoviário (letalidade 0,80% — 20 vezes a de hospitais), obras para geração de energia (0,62%), construção de edifícios (0,51%), vigilância patrimonial (aproximadamente 0,9%).

O achado sobre **vigilância patrimonial (CNAE 80)** — 7.390 CATs no biênio com letalidade próxima de 0,9% — é substrato de dado público que raramente aparece traduzido no debate. Merece atenção específica em iteração futura, possivelmente com desdobramento por região (o risco em vigilância pode variar substancialmente entre áreas metropolitanas de alta violência e áreas de menor exposição).

**Uma questão em aberto que este reúso não pôde resolver:** hospitais notáveis do setor privado premium (Einstein, Sírio-Libanês, Alemão Oswaldo Cruz, A.C. Camargo, Rede D'Or) não aparecem entre os 30 CNPJs mapeados por razão social via BrasilAPI. Duas explicações são possíveis: (a) sub-registro sofisticado nesses hospitais (SESMT robusto que trata acidentes internamente sem virar CAT no INSS), (b) razão social oficial diferente do nome fantasia, fazendo com que apareçam no dataset com nomes não pesquisados. O `cat_final.parquet` foi agregado por município × mês antes de preservar razão social, o que impede busca direta na base bruta com os artefatos disponíveis. Iteração futura com mapeamento CNPJ completo do dataset (via base pública da Receita Federal) pode responder honestamente.

## 8. Limitações reconhecidas

**Análise ecológica.** Todas as correlações são municipais, não individuais. Correlação municipal não é evidência de relação individual (falácia ecológica). Este reúso trata o município como unidade de análise sem afirmar propriedades causais no nível da família.

**Sub-registro estrutural na CAT.** A CAT é obrigatória por lei, mas o cumprimento não é uniforme. Setores com sindicalização forte, empresas grandes com SESMT bem estruturado e vínculos formais tendem a reportar mais. Trabalho informal, terceirização em cascata e pequena empresa reportam menos. Isso enviesa o ranking setorial em direção a empresas grandes formais, e o gradiente municipal em direção a municípios de tecido produtivo formal.

**Cobertura BF durante revisão do CadÚnico.** O biênio analisado corresponde a período de revisão ativa do cadastro. Saídas por corte administrativo, saídas por melhora de renda e exclusões indevidas coexistem no dado bruto sem distinção. Qualquer leitura do gradiente que atribua causa a um desses três mecanismos é especulativa.

**Definição de "entrada no BF".** Neste reúso, entrada foi definida operacionalmente como aparecimento pela primeira vez de um NIS na base de pagamentos, no horizonte de 25 meses. NIS já beneficiários em dezembro/2023 (mês de warm-up) foram excluídos das entradas. Essa definição é próxima da real, mas não idêntica — famílias podem ter cadastro anterior e ter passado por período sem pagamento antes do warm-up.

**Codificação de CNAE nos registros CAT.** Alguns registros vieram sem CNAE ("00" ou vazio); foram excluídos da análise setorial da Fig 2. O número exato é pequeno em relação ao total, mas o viés introduzido não é aleatório — registros mal codificados tendem a se concentrar em setores específicos (vínculos informais, primeiras versões da CAT antes de correção retroativa).

## 9. Próximos passos

Cada próximo passo corresponde a um cruzamento adicional com base pública que abriria uma pergunta específica:

**Com RAIS.** Taxa CAT/empregado por CNPJ, resolvendo o viés de escala do ranking por CNPJ. Remuneração média por CNAE por município, discriminando se municípios de perfil agrícola mantiveram beneficiários por baixa remuneração formal (elegibilidade real preservada) ou por outros fatores.

**Com dados operacionais do CadÚnico.** Volume de recadastramento por município no biênio, número de convocações, taxa de resposta. Distingue a hipótese "CRAS operacional forte cortou mais" da hipótese "vitalidade econômica retirou beneficiários por melhora de renda".

**Com Novo CAGED.** Fluxo mensal de admissões e desligamentos formais por município e CNAE. Testa em maior detalhe a relação entre dinâmica do emprego formal local e variação BF.

**Com mapeamento CNPJ→razão social completo.** Consulta em lote à base pública da Receita Federal para todos os 42.911 CNPJs do ranking, resolvendo a limitação da BrasilAPI (limitada a 30 CNPJs neste reúso).

**Com granularidade temporal alternativa.** Repetir o teste de correlação temporal em janela trimestral e anual, para verificar se o sinal fraco no lag 6 (+0,194) se estabiliza ou desaparece.

**Com desdobramento regional.** Repetir Fig 1 e Fig 2 por macrorregião (Norte, Nordeste, Centro-Oeste, Sudeste, Sul) e por dominância urbana/rural, para verificar se o gradiente estrutural é uniforme ou se esconde padrões regionais distintos.

## 10. Considerações de reprodutibilidade

Todos os artefatos intermediários estão em `data/processed/` como parquet. Todos os scripts do pipeline são versionados em Python (nenhum notebook Jupyter — decisão editorial de manter tudo reproduzível por linha de comando). DuckDB é a única dependência não-óbvia; instalado via `pip install duckdb`.

Máquinas mínimas para reprodução:

- Etapa de coleta: qualquer máquina com conexão estável; total baixado ~15 GB.
- Etapa de agregação BF (produção do painel mensal): ≥ 16 GB de RAM recomendado. Máquinas de 8 GB conseguem mediante `PRAGMA memory_limit` no DuckDB e paciência.
- Etapa de agregação CAT e figuras: qualquer máquina com Python funcional.

O tempo total de reprodução, em máquina de 16 GB RAM com SSD, é de aproximadamente 3 horas (predominantemente na etapa de coleta e primeira agregação BF; agregações CAT e figuras rodam em minutos).

---

*Documento vivo. Versão atual: 11 de setembro de 2026.*
