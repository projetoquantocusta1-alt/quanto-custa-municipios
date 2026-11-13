"""Robô diário: prefeituras e câmaras do Ceará (TCE-CE) -> site.

Uso:
    python atualizar.py                 # ano atual + fila do histórico, até o limite de tempo
    python atualizar.py --anos 2024     # só estes exercícios
    python atualizar.py --municipios 162 103
    python atualizar.py --so-montar     # não consulta o TCE: só refaz os arquivos do site
    python atualizar.py --minutos 60    # limite de tempo desta execução

A primeira carga (2017 até hoje, 184 municípios) não cabe numa execução só: o robô
anda numa fila e continua de onde parou na execução seguinte. Prioridade: ano atual,
depois o ano passado, depois os anos mais antigos.
"""
import argparse
import csv
import json
import logging
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

import config
from coletor import ipca, montar
from coletor import municipio as M
from coletor.tce import ErroTCE

RAIZ = Path(__file__).parent
BRUTOS = RAIZ / "dados_brutos"
SAIDA = RAIZ / "docs" / "dados"
log = logging.getLogger("qcm")


def ler(p: Path, padrao=None):
    try:
        return json.loads(p.read_text("utf-8")) if p.exists() else padrao
    except json.JSONDecodeError:
        log.warning("arquivo corrompido, ignorado: %s", p)
        return padrao


def gravar(p: Path, obj):
    """Grava só se o conteúdo mudou (assim o git não guarda cópias iguais todo dia)."""
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    if p.exists():
        try:
            if p.read_text("utf-8") == txt:
                return
        except OSError:
            pass
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(txt, "utf-8")
    tmp.replace(p)


def municipios() -> list[dict]:
    with open(RAIZ / "municipios_ce.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def caminho_bruto(ano, sim):
    return BRUTOS / "tce" / str(ano) / f"{sim}.json"


def precisa(ano: int, sim: str, hoje: date) -> bool:
    b = ler(caminho_bruto(ano, sim))
    if not b or b.get("versao") != M.VERSAO:
        return True
    if b.get("fechado") and len(b.get("meses_completos") or []) >= 12:
        return False
    try:
        dias = (hoje - date.fromisoformat(b.get("coletado_em"))).days
    except (TypeError, ValueError):
        return True
    # ano corrente: todo dia; ano passado ainda aberto: toda semana (o município pode
    # estar atrasado na prestação de contas de dezembro)
    return dias >= (1 if ano >= hoje.year else 7)


def fila(anos, sims, hoje):
    atual = hoje.year
    ordem = sorted(anos, key=lambda a: (a != atual, a != atual - 1, -a))
    return [(a, s) for a in ordem for s in sims if precisa(a, s, hoje)]


def pasta_meses(ano, sim):
    return BRUTOS / "tce" / str(ano) / sim


def coletar_um(ano, sim, hoje):
    antigo = ler(caminho_bruto(ano, sim))
    novo = M.coletar(sim, ano, antigo, hoje)
    if novo is not None:
        pasta = pasta_meses(ano, sim)
        if (antigo or {}).get("versao") != M.VERSAO and pasta.exists():
            for velho in pasta.glob("*.json"):      # sobras de uma coleta com a lista de órgãos antiga
                velho.unlink()
        for ref, md in novo.pop("meses_novos").items():
            gravar(pasta / f"{ref}.json", md)
        gravar(pasta / "itens.json", novo.pop("itens"))
        # o resumo do ano vai por último: se a execução cair no meio, os meses são refeitos
        gravar(caminho_bruto(ano, sim), novo)
    return novo


def carregar_bruto(ano, sim):
    """Resumo do ano já com os meses (v2), ou o arquivo v1 como está."""
    b = ler(caminho_bruto(ano, sim))
    if not b or b.get("versao") not in M.VERSOES_LEGIVEIS:
        return None
    if b["versao"] == 1:
        return b
    pasta = pasta_meses(ano, sim)
    meses = {}
    for r in b.get("meses_completos") or []:
        md = ler(pasta / f"{r}.json")
        if md is None:
            log.warning("%s/%s: falta o mês %s; o ano fica para a próxima coleta", ano, sim, r)
            return None
        meses[r] = md
    return M.compor(b, meses, ler(pasta / "itens.json", []))


def coletar(tarefas, hoje, limite_s):
    inicio = time.time()
    feitos = falhas = vazios = 0
    erros_seguidos = 0
    with ThreadPoolExecutor(max_workers=config.TRABALHADORES_TCE) as ex:
        pendentes = list(tarefas)
        rodando = {}
        while pendentes or rodando:
            while pendentes and len(rodando) < config.TRABALHADORES_TCE and time.time() - inicio < limite_s:
                a, s = pendentes.pop(0)
                rodando[ex.submit(coletar_um, a, s, hoje)] = (a, s)
            if not rodando:
                break
            fut = next(as_completed(rodando))
            a, s = rodando.pop(fut)
            try:
                r = fut.result()
                if r is None:
                    vazios += 1
                else:
                    feitos += 1
                erros_seguidos = 0
            except ErroTCE as e:
                falhas += 1
                erros_seguidos += 1
                log.warning("%s/%s: %s", a, s, e)
            except Exception as e:  # noqa: BLE001
                falhas += 1
                erros_seguidos += 1
                log.error("%s/%s: %s", a, s, e)
                traceback.print_exc()
            if erros_seguidos >= 25:
                log.error("TCE falhou 25 vezes seguidas: parando a coleta nesta execução")
                pendentes.clear()
            if (feitos + falhas + vazios) % 25 == 0:
                log.info("andamento: %d ok, %d sem dados, %d falhas, %d na fila, %.0f min",
                         feitos, vazios, falhas, len(pendentes), (time.time() - inicio) / 60)
    log.info("coleta: %d ok, %d sem dados ainda, %d falhas; ficaram %d para a próxima execução",
             feitos, vazios, falhas, len(pendentes))
    return feitos, falhas, len(pendentes)


def atualizar_ipca():
    p = BRUTOS / "ipca.json"
    try:
        f = ipca.fatores_por_ano(ipca.baixar_ipca(config.ANO_INICIAL))
        gravar(p, f)
        return f
    except Exception as e:  # noqa: BLE001
        log.warning("IPCA indisponível (%s): usando o último guardado", e)
        return ler(p, {"fatores": {}, "referencia": None})


def montar_site(muns, anos):
    eleitos = {}
    for eleicao in config.ELEICOES_MUNICIPAIS:
        e = ler(BRUTOS / "tse" / f"eleitos_{eleicao}.json")
        if e:
            eleitos[eleicao] = e
    pop = ler(BRUTOS / "populacao.json", {}) or {}
    emendas = ler(BRUTOS / "emendas_ce.json", {}) or {}
    resumo = []
    for m in muns:
        brutos = {}
        for a in anos:
            b = carregar_bruto(a, m["sim"])
            if b:
                brutos[a] = b
        det, res, extras = montar.montar_municipio(m, brutos, eleitos, pop.get(m["ibge"], {}),
                                                   emendas.get("linhas_por_municipio", {}).get(m["sim"], []))
        gravar(SAIDA / "m" / f"{m['sim']}.json", det)
        # nota a nota (Câmara e gabinetes) e fornecedores da prefeitura inteira, um arquivo por ano
        for a, (notas, forn) in extras.items():
            gravar(SAIDA / "n" / m["sim"] / f"{a}.json", notas)
            gravar(SAIDA / "f" / m["sim"] / f"{a}.json", forn)
        resumo.append(res)
    ip = ler(BRUTOS / "ipca.json", {"fatores": {}, "referencia": None})
    com_dados = sorted({int(a) for r in resumo for a in r["anos"]})
    gravar(SAIDA / "resumo.json", {"campos": montar.CAMPOS_RESUMO, "municipios": resumo})
    gravar(SAIDA / "meta.json", {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "anos": com_dados, "ipca": ip,
        "eleicoes": sorted(eleitos), "mandatos": {str(k): v for k, v in config.MANDATO_DA_ELEICAO.items()},
        "emendas_atualizadas_em": emendas.get("atualizado_em"),
        "populacao_fonte": "IBGE — estimativas (tabela 6579) e Censo 2022 (tabela 4714)",
        "cobertura": {str(a): sum(1 for r in resumo if str(a) in r["anos"]) for a in com_dados},
        "total_municipios": len(muns),
    })
    log.info("site montado: %d municípios, anos %s", len(resumo), com_dados)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--anos", type=int, nargs="*")
    ap.add_argument("--municipios", nargs="*")
    ap.add_argument("--so-montar", action="store_true")
    ap.add_argument("--minutos", type=float, default=config.ORCAMENTO_MINUTOS)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    hoje = date.today()
    muns = municipios()
    if args.municipios:
        muns = [m for m in muns if m["sim"] in set(args.municipios)]
    todos_anos = list(range(config.ANO_INICIAL, hoje.year + 1))
    anos = args.anos or todos_anos
    falhas = 0
    if not args.so_montar:
        atualizar_ipca()
        tarefas = fila(anos, [m["sim"] for m in muns], hoje)
        log.info("fila: %d município-anos para consultar", len(tarefas))
        # deixa 20 min para montar e publicar
        _, falhas, _ = coletar(tarefas, hoje, max(60.0, args.minutos * 60 - 20 * 60))
    montar_site(municipios(), todos_anos)
    return 0 if falhas < 50 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
