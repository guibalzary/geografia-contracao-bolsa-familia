#!/bin/bash
# download_bf.sh — Bolsa Família Pagamentos jan/2024 a dez/2025
mkdir -p data/raw/bf
cd data/raw/bf
for ano in 2024 2025; do
  for mes in 01 02 03 04 05 06 07 08 09 10 11 12; do
    arquivo="${ano}${mes}_bf.zip"
    if [ -f "$arquivo" ]; then
      echo "já existe: $arquivo — pulando"
      continue
    fi
    url="https://portaldatransparencia.gov.br/download-de-dados/novo-bolsa-familia/${ano}${mes}"
    echo "baixando ${ano}${mes}..."
    curl -fL --retry 5 --retry-delay 10 -o "$arquivo" "$url"
  done
done
echo "concluído."