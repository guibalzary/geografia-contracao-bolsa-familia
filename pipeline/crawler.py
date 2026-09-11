"""
Crawler do catálogo do Portal Brasileiro de Dados Abertos (dados.gov.br).

Uso:
    export CHAVE_API_DADOS_ABERTOS="sua-chave-aqui"
    python3 crawler.py

Ou:
    python3 crawler.py --chave "sua-chave-aqui"

Como obter a chave (perfil Consumidor, sem precisar ser admin de órgão):
    1. Acesse https://dados.gov.br e faça login com sua conta gov.br.
    2. No menu do canto superior direito, entre em "Minha Conta".
    3. Copie o valor da chave-api-dados-abertos.

O que este script faz:
    - Baixa todos os temas e formatos (endpoints sem paginação).
    - Pagina toda a lista de conjuntos de dados públicos.
    - Pagina toda a lista de organizações.
    - Para cada conjunto listado, baixa o detalhe completo (recursos + metadados).
    - Salva cada resposta bruta em ./catalogo_bruto/.
    - Registra falhas em ./catalogo_bruto/_falhas.log e segue adiante.

Rate-limit prudente: sleep de 0.35s entre chamadas; em caso de 429 dobra o
sleep e tenta de novo (até 5x). Não ultrapassa ~500 requests seguidas em
uma execução única sem checkpoint — grava dumps intermediários a cada
página lida, de modo que uma interrupção não perde trabalho.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import requests
except ImportError:  # stdlib fallback
    print("Instale requests: pip install requests", file=sys.stderr)
    sys.exit(2)


BASE = "https://dados.gov.br"
OUT_DIR = Path(__file__).resolve().parent / "catalogo_bruto"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = OUT_DIR / "_crawler.log"
FAIL_PATH = OUT_DIR / "_falhas.log"


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_fail(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with FAIL_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


@dataclass
class Client:
    chave: str
    session: requests.Session = field(default_factory=requests.Session)
    sleep_base: float = 0.35
    max_retries: int = 5

    def get(self, path: str, params: dict | None = None) -> Any:
        url = BASE + path
        headers = {
            "Accept": "application/json",
            "chave-api-dados-abertos": self.chave,
            "User-Agent": "cgu-reuso-2026-crawler/1.0 (guibalzary@gmail.com)",
        }
        sleep = self.sleep_base
        last_err = None
        for tent in range(1, self.max_retries + 1):
            try:
                r = self.session.get(url, headers=headers, params=params, timeout=45)
            except requests.RequestException as e:
                last_err = f"exc {type(e).__name__}: {e}"
                log(f"WARN tentativa {tent} {url} {params}: {last_err}")
                time.sleep(sleep)
                sleep *= 2
                continue

            if r.status_code == 200:
                time.sleep(self.sleep_base)
                try:
                    return r.json()
                except json.JSONDecodeError:
                    return {"_raw": r.text}

            if r.status_code == 429:
                log(f"WARN 429 rate limit em {url} params={params}; dobrando sleep para {sleep*2}s")
                time.sleep(sleep * 2)
                sleep *= 2
                continue

            if r.status_code in (401, 403):
                log_fail(f"AUTH {r.status_code} {url} params={params} body={r.text[:200]}")
                raise SystemExit(
                    f"HTTP {r.status_code} em {url} — verifique a chave-api-dados-abertos."
                )

            if r.status_code in (500, 502, 503, 504):
                last_err = f"HTTP {r.status_code}"
                log(f"WARN {last_err} em {url} params={params} (tentativa {tent})")
                time.sleep(sleep)
                sleep *= 2
                continue

            # 4xx definitivo (400, 404, 422)
            log_fail(f"HTTP {r.status_code} {url} params={params} body={r.text[:300]}")
            return None

        log_fail(f"MAX_RETRIES {url} params={params} last_err={last_err}")
        return None


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- endpoints ----------

def coletar_metadados_estaticos(cli: Client) -> None:
    """Temas, formatos, ODS, observância legal — endpoints sem paginação."""
    endpoints = {
        "temas": "/dados/api/temas",
        "formatos": "/dados/api/publico/conjuntos-dados/formatos",
        "objetivos_dev_sustentavel": "/dados/api/publico/conjuntos-dados/objetivos-desenvolvimento-sustentavel",
        "observancia_legal": "/dados/api/publico/conjuntos-dados/observancia-legal",
    }
    for nome, path in endpoints.items():
        log(f"BAIXAR {nome} <- {path}")
        data = cli.get(path)
        if data is None:
            log(f"FALHA {nome}"); continue
        save_json(OUT_DIR / f"{nome}.json", data)
        n = len(data) if isinstance(data, list) else "(objeto)"
        log(f"OK {nome} itens={n}")


def paginar(cli: Client, path: str, params_extra: dict | None = None,
            pagina_inicial: int = 1, max_paginas: int = 10_000) -> list[Any]:
    """Coleta todas as páginas de um endpoint que aceita ?pagina=N.
    Interrompe quando uma página retorna vazia."""
    resultado = []
    pag = pagina_inicial
    while pag <= max_paginas:
        params = dict(params_extra or {})
        params["pagina"] = pag
        log(f"PÁGINA {pag} em {path} params={params}")
        data = cli.get(path, params=params)
        if data is None:
            log(f"FALHA pág {pag} em {path} — interrompendo esta paginação")
            break
        itens = data if isinstance(data, list) else data.get("content") or data.get("items") or []
        if not itens:
            log(f"FIM {path} na página {pag} (vazio)")
            break
        resultado.extend(itens)
        # dump incremental por página
        save_json(OUT_DIR / f"_pag_{Path(path).name}_{pag:04d}.json", data)
        pag += 1
    return resultado


def coletar_conjuntos(cli: Client) -> list[dict]:
    log("=== LISTAR conjuntos-dados ===")
    conjuntos = paginar(
        cli,
        "/dados/api/publico/conjuntos-dados",
        params_extra={"isPrivado": "false"},
    )
    save_json(OUT_DIR / "conjuntos_lista.json", conjuntos)
    log(f"TOTAL conjuntos listados: {len(conjuntos)}")
    return conjuntos


def coletar_organizacoes(cli: Client) -> list[dict]:
    log("=== LISTAR organizacoes ===")
    orgs = paginar(cli, "/dados/api/publico/organizacao")
    save_json(OUT_DIR / "organizacoes.json", orgs)
    log(f"TOTAL organizações: {len(orgs)}")
    return orgs


def coletar_detalhes_conjuntos(cli: Client, conjuntos: list[dict], limite: int | None = None) -> None:
    """Detalha cada conjunto (recursos + metadata rica)."""
    det_dir = OUT_DIR / "detalhes_conjuntos"
    det_dir.mkdir(exist_ok=True)
    ids = [c.get("id") for c in conjuntos if c.get("id")]
    if limite:
        ids = ids[:limite]
    log(f"=== DETALHAR {len(ids)} conjuntos ===")
    for i, cid in enumerate(ids, 1):
        alvo = det_dir / f"{cid}.json"
        if alvo.exists():
            continue
        data = cli.get(f"/dados/api/publico/conjuntos-dados/{cid}")
        if data is None:
            log_fail(f"DETALHE FALHOU id={cid}"); continue
        save_json(alvo, data)
        if i % 25 == 0:
            log(f"progresso detalhes: {i}/{len(ids)}")


def coletar_reusos(cli: Client) -> None:
    """/publico/reusos não aceita pagina segundo a spec — chamada única."""
    log("=== LISTAR reusos ===")
    data = cli.get("/dados/api/publico/reusos")
    if data is None:
        log_fail("REUSOS FALHOU"); return
    save_json(OUT_DIR / "reusos.json", data)
    log(f"OK reusos itens={len(data) if isinstance(data, list) else 'obj'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Crawler do catálogo dados.gov.br")
    ap.add_argument("--chave", help="chave-api-dados-abertos (ou use env CHAVE_API_DADOS_ABERTOS)")
    ap.add_argument("--pular-detalhes", action="store_true",
                    help="não baixa detalhes por conjunto (apenas listagem)")
    ap.add_argument("--limite-detalhes", type=int, default=None,
                    help="limita quantos conjuntos detalhar (útil para teste)")
    args = ap.parse_args()

    chave = args.chave or os.environ.get("CHAVE_API_DADOS_ABERTOS", "").strip()
    if not chave:
        print("ERRO: informe --chave ou defina CHAVE_API_DADOS_ABERTOS.", file=sys.stderr)
        return 2

    cli = Client(chave=chave)
    log(f"INÍCIO em {OUT_DIR}")

    coletar_metadados_estaticos(cli)
    orgs = coletar_organizacoes(cli)
    conjuntos = coletar_conjuntos(cli)
    coletar_reusos(cli)

    if not args.pular_detalhes:
        coletar_detalhes_conjuntos(cli, conjuntos, limite=args.limite_detalhes)

    log("FIM. Resumo:")
    log(f"  organizações: {len(orgs)}")
    log(f"  conjuntos:    {len(conjuntos)}")
    log(f"  dumps em:     {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
