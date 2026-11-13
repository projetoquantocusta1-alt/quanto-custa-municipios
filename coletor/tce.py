"""Cliente da API de Dados Abertos do SIM/TCE-CE.

Resolve de uma vez as pegadinhas da API:
  - exercicio_orcamento no formato AAAA00 (2025 -> 202500);
  - data_referencia_doc no formato AAAAMM;
  - 1000 registros por página, com $start_index;
  - respostas com "__errors__" e HTTP 200;
  - 404 temporário em grupos inteiros de consultas (tratado como "fora do ar agora",
    não como "não existe").
"""
import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

_local = threading.local()


class ErroTCE(Exception):
    pass


def _sessao() -> requests.Session:
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        retry = Retry(total=4, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET",), respect_retry_after_header=False, backoff_max=20)
        s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=8))
        s.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/json"})
        _local.s = s
    return s


def exercicio(ano: int) -> int:
    return int(ano) * 100


def referencia(ano: int, mes: int) -> int:
    return int(ano) * 100 + int(mes)


def consultar(caminho: str, params: dict, pagina: int = None, max_paginas: int = 200,
              so_primeira: bool = False) -> list[dict]:
    """Todas as páginas de uma consulta. Levanta ErroTCE se o TCE recusar."""
    pagina = pagina or config.TCE_PAGINA
    url = f"{config.TCE_API}/{caminho.strip('/')}"
    saida: list[dict] = []
    for n in range(max_paginas):
        p = dict(params)
        p["$count"] = pagina
        if n:
            p["$start_index"] = n * pagina
        try:
            r = _sessao().get(url, params=p, timeout=(20, 180))
        except requests.RequestException as e:
            raise ErroTCE(f"{caminho}: sem resposta ({e.__class__.__name__})") from e
        time.sleep(config.PAUSA_ENTRE_REQUISICOES)
        if r.status_code == 404:
            raise ErroTCE(f"{caminho}: o TCE respondeu 404 (consulta fora do ar no momento)")
        if r.status_code == 403:
            raise ErroTCE(f"{caminho}: o TCE recusou o acesso (403) — pode ser bloqueio por IP")
        if not r.ok:
            raise ErroTCE(f"{caminho}: HTTP {r.status_code} {r.text[:200]}")
        corpo = r.json()
        if corpo.get("__errors__"):
            msg = (corpo["__errors__"][0] or {}).get("message", "consulta recusada")
            raise ErroTCE(f"{caminho}: {msg}")
        elementos = corpo.get("elements") or []
        saida.extend(elementos)
        if so_primeira or len(elementos) < pagina:
            return saida
    raise ErroTCE(f"{caminho}: passou de {max_paginas} páginas")


def existe(caminho: str, params: dict) -> bool:
    """True se a consulta tem ao menos um registro (uma página de 1)."""
    return bool(consultar(caminho, params, pagina=1, so_primeira=True))
