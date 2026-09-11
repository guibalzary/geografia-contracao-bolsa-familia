#!/bin/bash
cd data/raw/cat
BASE="https://armazenamento-dadosabertos.s3.sa-east-1.amazonaws.com"
PASTA_ANTIGA="PDA_2023_2025/Grupos_de_dados/Comunica%C3%A7%C3%B5es+de+Acidente+de+Trabalho+%E2%80%93+CAT"
PASTA_NOVA="PDA_2025_2027/Grupos_de_dados/Comunica%C3%A7%C3%B5es+de+Acidente+de+Trabalho+%E2%80%93+CAT"

for ano in 2024 2025; do
  for mes in 01 02 03 04 05 06 07 08 09 10 11 12; do
    arquivo="D.SDA.PDA.005.CAT.${ano}${mes}.ZIP"
    if [ -f "$arquivo" ]; then
      echo "ja existe: $arquivo"
      continue
    fi
    ok=0
    for pasta in "$PASTA_NOVA" "$PASTA_ANTIGA"; do
      url="${BASE}/${pasta}/${arquivo}"
      echo "tentando ${ano}${mes}..."
      if curl -fL --retry 5 --retry-delay 10 -o "$arquivo" "$url"; then
        echo "  OK: ${ano}${mes}"
        ok=1
        break
      fi
    done
    if [ $ok -eq 0 ]; then
      echo "  FALHOU: ${ano}${mes}"
      rm -f "$arquivo"
    fi
  done
done
echo "concluido."
