"""Robô das prefeituras de outros estados pelo SICONFI (Tesouro Nacional). Começa pela Bahia.

Uso:
    python atualizar_siconfi.py --uf BA --minutos 90

Guarda, por município, a despesa por função do RREO (Anexo 02) de cada ano em
dados_brutos/siconfi/<uf>/<ibge>.json -> {"AAAA": {"periodo", "total", "funcoes", ...}}.
Ano com o 6º bimestre já entregue não é consultado de novo. Ano ainda aberto: procura bimestres mais novos.
Prefeitura que não entregou: anotada ("falta") e consultada de novo depois de 15 dias.
"""
import argparse
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path

from coletor import http, siconfi

RAIZ = Path(__file__).parent
log = logging.getLogger("siconfi")


def ler(p: Path, padrao=None):
    try:
        return json.loads(p.read_text("utf-8")) if p.exists() else padrao
    except json.JSONDecodeError:
        return padrao


def gravar(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), "utf-8")


def ultimo_bimestre_possivel(ano: int, hoje: date) -> int:
    """Último bimestre que já pode ter sido entregue (prazo: 30 dias depois do fim do bimestre)."""
    if ano < hoje.year:
        return 6
    meses_completos = hoje.month - 1 - (1 if hoje.day < 30 else 0)
    return max(0, min(6, meses_completos // 2))


def coletar(uf: str, desde: int, hoje: date, limite_s: float) -> int:
    pasta = RAIZ / "dados_brutos" / "siconfi" / uf.lower()
    lista = ler(pasta / "entes.json")
    if not lista or (lista and lista[0].get("_baixado") != hoje.isoformat()[:7]):
        try:
            novos = siconfi.entes(uf)
            if novos:
                novos[0]["_baixado"] = hoje.isoformat()[:7]
                gravar(pasta / "entes.json", novos)
                lista = novos
        except Exception as e:  # noqa: BLE001
            log.warning("lista de municípios indisponível (%s)", e)
    if not lista:
        log.error("%s: sem lista de municípios", uf)
        return 0
    t0, feitos = time.time(), 0
    for ano in range(hoje.year, desde - 1, -1):                 # do ano mais novo para o mais antigo
        maxp = ultimo_bimestre_possivel(ano, hoje)
        if not maxp:
            continue
        for e in lista:
            if time.time() - t0 > limite_s:
                log.warning("tempo esgotado; o resto fica para a próxima execução (%d consultas feitas)", feitos)
                return feitos
            arq = pasta / f"{e['ibge']}.json"
            d = ler(arq, {}) or {}
            atual = d.get(str(ano)) or {}
            if atual.get("periodo") == 6 or (atual.get("periodo") or 0) >= maxp:
                continue
            if atual.get("falta") and hoje.toordinal() - date.fromisoformat(atual["falta"]).toordinal() < 15:
                continue
            achado = None
            for p in range(maxp, (atual.get("periodo") or 0), -1):
                try:
                    achado = siconfi.rreo2(e["ibge"], ano, p)
                except http.SiteForaDoAr as x:
                    log.error("%s", x)
                    return feitos
                except Exception as x:  # noqa: BLE001
                    log.warning("%s %s %d/%d: %s", e["nome"], e["ibge"], ano, p, x)
                feitos += 1
                if achado or ano < hoje.year - 1:   # ano antigo: só o 6º bimestre interessa
                    break
            if achado:
                achado["baixado_em"] = hoje.isoformat()
                d[str(ano)] = achado
            elif not atual.get("periodo"):
                d[str(ano)] = {"falta": hoje.isoformat()}
            gravar(arq, d)
        log.info("%s %d: pronto", uf, ano)
    return feitos


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--uf", default="BA")
    ap.add_argument("--desde", type=int, default=2017)
    ap.add_argument("--minutos", type=float, default=90)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    n = coletar(a.uf.upper(), a.desde, date.today(), a.minutos * 60)
    log.info("%s: %d consultas ao SICONFI", a.uf, n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
