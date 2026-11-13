"""Robô semanal: eleitos (TSE), população (IBGE) e emendas destinadas aos municípios (CGU).

Uso:
    python semanal.py                # tudo
    python semanal.py --so tse       # tse | ibge | emendas
    python semanal.py --refazer-tse  # baixa de novo as eleições já guardadas
"""
import argparse
import csv
import logging
import sys
import traceback
from collections import defaultdict
from datetime import date
from pathlib import Path

import config
from coletor import eleitos as E
from coletor import extras, http
from coletor.municipio import sem_acento

RAIZ = Path(__file__).parent
BRUTOS = RAIZ / "dados_brutos"
log = logging.getLogger("qcm")

from atualizar import gravar, ler  # noqa: E402


def municipios():
    with open(RAIZ / "municipios_ce.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tse(refazer=False):
    muns = municipios()
    tse_para_sim = {m["tse"]: m["sim"] for m in muns}
    ok = 0
    for ano in config.ELEICOES_MUNICIPAIS:
        p = BRUTOS / "tse" / f"eleitos_{ano}.json"
        if p.exists() and not refazer:
            log.info("TSE %s: já guardado", ano)
            ok += 1
            continue
        try:
            cand = E._csv_do_zip(http.get(config.TSE_CAND_ZIP.format(ano=ano), timeout=600).content, config.UF)
            try:
                bens = E.bens_por_candidato(http.get(config.TSE_BENS_ZIP.format(ano=ano), timeout=600).content, config.UF)
            except Exception as e:  # noqa: BLE001
                log.warning("TSE %s: bens indisponíveis (%s)", ano, e)
                bens = {}
            res = E.eleitos(cand, bens, tse_para_sim)
            sem_pref = [m["nome"] for m in muns if not (res.get(m["sim"]) or {}).get("prefeito")]
            n_ver = sum(len(v["vereadores"]) for v in res.values())
            log.info("TSE %s: %d municípios, %d vereadores; sem prefeito eleito na ordinária: %s",
                     ano, len(res), n_ver, sem_pref[:10])
            gravar(p, res)
            ok += 1
        except Exception as e:  # noqa: BLE001
            log.error("TSE %s falhou: %s", ano, e)
    return ok


def ibge():
    try:
        pop = extras.baixar_populacao()
        ce = {k: v for k, v in pop.items() if k.startswith("23")}
        if len(ce) < 180:
            raise ValueError(f"só {len(ce)} municípios na resposta do IBGE")
        gravar(BRUTOS / "populacao.json", ce)
        log.info("IBGE: população de %d municípios", len(ce))
        return True
    except Exception as e:  # noqa: BLE001
        log.error("IBGE falhou: %s", e)
        return False


def emendas():
    muns = municipios()
    nome_para_sim = {sem_acento(m["nome"]): m["sim"] for m in muns}
    ibge_para_sim = {m["ibge"]: m["sim"] for m in muns}
    try:
        linhas = extras.baixar_emendas(nome_para_sim, ibge_para_sim)
    except Exception as e:  # noqa: BLE001
        log.error("emendas falharam: %s", e)
        return False
    por_mun = defaultdict(list)
    for ln in linhas:
        if ln[1] >= config.ANO_INICIAL:
            por_mun[ln[0]].append(ln)
    gravar(BRUTOS / "emendas_ce.json", {"atualizado_em": date.today().isoformat(),
                                        "linhas_por_municipio": dict(por_mun)})
    log.info("emendas: %d linhas para %d municípios do CE", sum(map(len, por_mun.values())), len(por_mun))
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", choices=["tse", "ibge", "emendas"])
    ap.add_argument("--refazer-tse", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    res = []
    if args.so in (None, "tse"):
        res.append(tse(args.refazer_tse) > 0)
    if args.so in (None, "ibge"):
        res.append(ibge())
    if args.so in (None, "emendas"):
        res.append(emendas())
    # remonta o site com o que chegou (sem consultar o TCE)
    import atualizar
    atualizar.main(["--so-montar"])
    return 0 if any(res) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
