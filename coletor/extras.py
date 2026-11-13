"""População (IBGE) e emendas parlamentares destinadas aos municípios (CGU)."""
import csv
import io
import unicodedata

import config
from coletor import http
from coletor.municipio import sem_acento


# ------------------------------------------------------------------ população
def ler_ibge(json_ibge) -> dict[str, dict[int, int]]:
    """{ibge7: {ano: pop}} a partir da resposta da API de agregados do IBGE."""
    out: dict[str, dict[int, int]] = {}
    for var in json_ibge or []:
        for res in var.get("resultados", []):
            for s in res.get("series", []):
                cod = str(s["localidade"]["id"])
                for ano, v in (s.get("serie") or {}).items():
                    try:
                        out.setdefault(cod, {})[int(ano)] = int(v)
                    except (TypeError, ValueError):
                        pass
    return out


def ler_sidra(linhas) -> dict[str, dict[int, int]]:
    """{ibge7: {ano: pop}} a partir da API do SIDRA (apisidra.ibge.gov.br/values/...).
    A 1ª linha é o cabeçalho; nas outras, o município e o ano vêm em campos D?C (a ordem varia)."""
    out: dict[str, dict[int, int]] = {}
    for r in (linhas or [])[1:]:
        if not isinstance(r, dict):
            continue
        cods = [str(v) for k, v in r.items() if k.startswith("D") and k.endswith("C")]
        mun = next((c for c in cods if len(c) == 7 and c.isdigit()), None)
        ano = next((c for c in cods if len(c) == 4 and c.isdigit() and 1990 <= int(c) <= 2100), None)
        try:
            v = int(float(str(r.get("V", "")).replace(",", ".")))
        except ValueError:
            continue
        if mun and ano:
            out.setdefault(mun, {})[int(ano)] = v
    return out


def _uma_fonte(api, sidra):
    """Tenta a API de agregados; se não responder, o SIDRA (outro servidor do IBGE)."""
    try:
        r = ler_ibge(http.get(api, timeout=(20, 120)).json())
        if r:
            return r
    except Exception:  # noqa: BLE001
        pass
    return ler_sidra(http.get(sidra, timeout=(20, 120)).json())


def baixar_populacao() -> dict[str, dict[int, int]]:
    pop = _uma_fonte(config.IBGE_ESTIMATIVA, config.SIDRA_ESTIMATIVA)
    try:
        censo = _uma_fonte(config.IBGE_CENSO_2022, config.SIDRA_CENSO_2022)
        for cod, s in censo.items():
            pop.setdefault(cod, {}).update(s)
    except Exception:  # noqa: BLE001 — o censo é complemento; sem ele vale a estimativa mais próxima
        pass
    return pop


def populacao_no_ano(serie: dict, ano: int) -> int | None:
    """Ano exato; senão, o ano disponível mais próximo (o anterior em caso de empate)."""
    if not serie:
        return None
    s = {int(k): v for k, v in serie.items()}
    if ano in s:
        return s[ano]
    melhor = min(s, key=lambda a: (abs(a - ano), a > ano))
    return s[melhor]


# ------------------------------------------------------------------ emendas
def _norm_col(c):
    return unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode().lower().strip()


def _br(v) -> float:
    s = (v or "").strip()
    if not s:
        return 0.0
    return float(s.replace(".", "").replace(",", "."))


def ler_emendas(conteudo_csv: bytes, nome_para_sim: dict[str, str], ibge_para_sim: dict[str, str]) -> list[list]:
    """Linhas [sim, ano, autor, tipo, funcao, empenhado, pago] das emendas com destino a município do CE."""
    texto = conteudo_csv.decode("latin-1")
    leitor = csv.reader(io.StringIO(texto), delimiter=";")
    cab = [_norm_col(c) for c in next(leitor)]

    def idx(*partes, exato=None):
        for i, c in enumerate(cab):
            if exato is not None and c == exato:
                return i
            if exato is None and all(p in c for p in partes):
                return i
        return None
    i_ano = idx("ano da emenda")
    i_tipo = idx("tipo de emenda")
    i_autor = idx("nome do autor")
    i_fun = idx("nome funcao")
    i_uf = idx(exato="uf")
    i_mun = idx(exato="municipio")
    i_ibge = idx("codigo municipio ibge")
    i_emp = idx("valor empenhado")
    i_pago = idx("valor pago")
    i_rp = idx("restos a pagar pagos")
    out = []
    for r in leitor:
        if not r or i_ano is None:
            continue
        uf = r[i_uf].strip().upper() if i_uf is not None else ""
        if uf not in ("CE", "CEARA", "CEARÁ"):
            continue
        sim = None
        if i_ibge is not None:
            sim = ibge_para_sim.get(r[i_ibge].strip()[:7])
        if sim is None and i_mun is not None:
            sim = nome_para_sim.get(sem_acento(r[i_mun]).strip())
        if sim is None:
            continue
        try:
            ano = int(r[i_ano])
        except ValueError:
            continue
        pago = _br(r[i_pago]) + (_br(r[i_rp]) if i_rp is not None else 0.0)
        out.append([sim, ano, r[i_autor].strip(), r[i_tipo].strip() if i_tipo is not None else "",
                    r[i_fun].strip() if i_fun is not None else "", round(_br(r[i_emp]), 2), round(pago, 2)])
    return out


def baixar_emendas(nome_para_sim, ibge_para_sim) -> list[list]:
    z = http.baixar_zip(config.EMENDAS_ZIP, timeout=900)
    nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    return ler_emendas(z.read(nome), nome_para_sim, ibge_para_sim)
