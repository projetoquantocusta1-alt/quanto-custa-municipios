"""Monta os arquivos do site a partir dos resumos brutos (TCE, TSE, IBGE, CGU).

Medida de gasto: despesa EMPENHADA LÍQUIDA (empenhado − anulações), a "despesa
realizada" da Lei 4.320/64 (art. 35). É a única medida que o TCE informa de forma
igual em todos os municípios: conferimos que, para cada órgão, a soma das notas de
empenho menos as anulações bate com o balancete do mesmo mês.
"""
import re
from collections import defaultdict
from datetime import date

import config
from coletor import classificar as C
from coletor.extras import populacao_no_ano
from coletor.municipio import sem_acento

PALAVRAS_FRACAS = {"DE", "DA", "DO", "DAS", "DOS", "E"}


def r2(x):
    return round(float(x or 0), 2)


# ------------------------------------------------------------------ teto do vereador
def subsidio_dep_federal(ano: int, mes: int) -> float:
    v = config.SUBSIDIO_DEP_FEDERAL[0][1]
    for (a, m), valor in config.SUBSIDIO_DEP_FEDERAL:
        if (ano, mes) >= (a, m):
            v = valor
    return v


def teto_vereador_mensal(ano: int, pop: int | None) -> float | None:
    """Média mensal, no ano, do teto constitucional do subsídio do vereador."""
    if not pop:
        return None
    pct = next(p for lim, p in config.TETO_VEREADOR_FAIXAS if pop <= lim)
    media = sum(subsidio_dep_federal(ano, m) for m in range(1, 13)) / 12
    return round(media * 0.75 * pct, 2)


# ------------------------------------------------------------------ nomes
def norm_nome(s: str) -> str:
    s = re.sub(r"[^A-Z ]", " ", sem_acento(s))
    return re.sub(r"\s+", " ", s).strip()


def mandato_do_ano(ano: int) -> int | None:
    for eleicao, (ini, fim) in config.MANDATO_DA_ELEICAO.items():
        if ini <= ano <= fim:
            return eleicao
    return None


class Identificador:
    """Liga notas de empenho a prefeito, vice e vereadores do mandato.

    Dois jeitos, sempre exatos:
      1. o favorecido da nota é a própria pessoa (nome civil idêntico);
      2. o histórico da nota diz "VEREADOR(A) <nome>" e o nome que vem depois é o
         nome de urna (ou o nome civil) de exatamente um vereador daquela Câmara.
    """

    def __init__(self, eleitos: dict | None):
        self.pessoas = []       # (chave, papel, nome_civil_norm, [apelidos_norm])
        self.apelidos, self.civil = {}, {}
        if not eleitos:
            return
        for papel in ("prefeito", "vice"):
            p = eleitos.get(papel)
            if p:
                self.pessoas.append((papel, papel, norm_nome(p["nome"]), []))
        for i, v in enumerate(eleitos.get("vereadores") or []):
            apelidos = {norm_nome(v["urna"]), norm_nome(v["nome"])}
            self.pessoas.append((f"v{i}", "vereador", norm_nome(v["nome"]), [a for a in apelidos if a]))
        # apelidos que valem para mais de um vereador são descartados (ambíguos)
        cont = defaultdict(int)
        for _, papel, _, aps in self.pessoas:
            for a in aps:
                cont[a] += 1
        self.apelidos = {}
        for chave, papel, _, aps in self.pessoas:
            for a in aps:
                if cont[a] == 1 and a not in PALAVRAS_FRACAS and len(a) >= 3:
                    self.apelidos[a] = chave
        self.civil = {}
        for chave, _, civil, _ in self.pessoas:
            self.civil.setdefault(civil, []).append(chave)

    def favorecido(self, nome_negociante: str) -> str | None:
        ks = self.civil.get(norm_nome(nome_negociante))
        return ks[0] if ks and len(ks) == 1 else None

    def citado(self, historico: str) -> str | None:
        h = norm_nome(historico)
        achados = set()
        for m in re.finditer(r"\bVEREADORA? ", h):
            resto = h[m.end():m.end() + 70] + " "
            for ap, chave in self.apelidos.items():
                if resto.startswith(ap + " "):
                    achados.add(chave)
        return achados.pop() if len(achados) == 1 else None


# ------------------------------------------------------------------ um município-ano
def montar_ano(bruto: dict, eleitos: dict | None, pop: int | None) -> dict:
    ano = bruto["ano"]
    pap = bruto["papeis"]
    papel_de = {o: p for p, lst in pap.items() for o in lst}

    total = 0.0
    pago_total = 0.0
    por_funcao = defaultdict(float)
    por_grupo = defaultdict(float)
    orgao = {p: {"gasto": 0.0, "pago": 0.0, "grupos": defaultdict(float), "elementos": defaultdict(float)}
             for p in ("camara", "prefeito", "vice")}
    bal_por_orgao = defaultdict(float)
    for org, fun, el6, emp, anul, liq, pago, est_pag in bruto["despesa"]:
        gasto = emp - anul
        bal_por_orgao[org] += gasto
        p = papel_de.get(org)
        if p:
            o = orgao[p]
            o["gasto"] += gasto
            o["pago"] += pago
            o["grupos"][C.grupo_despesa(el6)] += gasto
            o["elementos"][el6[4:6]] += gasto
        if C.intra(el6):
            continue
        total += gasto
        pago_total += pago
        por_funcao[fun] += gasto
        por_grupo[C.grupo_despesa(el6)] += gasto

    receita = defaultdict(float)
    for rub, v in bruto["receita"]:
        g = C.grupo_receita(rub, ano)
        if g:
            receita[g] += v
    receita_total = sum(receita.values())

    # ---- notas de empenho dos órgãos da Câmara e dos gabinetes
    anul = defaultdict(float)
    for lst in bruto.get("anulacoes", {}).values():
        for org, data, num, v in lst:
            anul[(org, data, num)] += v
    ident = Identificador(eleitos)
    forn = {p: {} for p in orgao}
    pessoas = defaultdict(lambda: {"direto": 0.0, "citado": 0.0, "notas": 0, "itens": []})
    soma_notas = defaultdict(float)
    for ref, lst in sorted(bruto.get("empenhos", {}).items()):
        for org, data, num, el8, sub, valor, nome, doc, tipo, hist, fun in lst:
            liquido = valor - anul.pop((org, data, num), 0.0)
            soma_notas[org] += liquido
            p = papel_de.get(org)
            if not p:
                continue
            pessoal = el8[1:2] == "1"
            if doc:
                chave, rot, tp = doc, nome, "PJ"
            elif pessoal:
                chave, rot, tp = "_PESSOAL", "Folha, encargos e rescisões de pessoal", "FOLHA"
            else:
                chave, rot, tp = "PF:" + norm_nome(nome), nome, "PF"
            f = forn[p].setdefault(chave, {"nome": rot, "doc": doc, "tipo": tp, "valor": 0.0, "notas": 0,
                                           "elementos": defaultdict(float)})
            f["valor"] += liquido
            f["notas"] += 1
            f["elementos"][el8[4:6]] += liquido
            quem, como = ident.favorecido(nome), "direto"
            if quem is None and p == "camara":
                quem, como = ident.citado(hist), "citado"
            if quem:
                pe = pessoas[quem]
                pe[como] += liquido
                pe["notas"] += 1
                pe["itens"].append([data, r2(liquido), el8[4:6], nome[:80], hist[:200], como])

    conferencia = {}
    for p, orgs in pap.items():
        if not orgs:
            continue
        bal = sum(bal_por_orgao[o] for o in orgs)
        notas = sum(soma_notas[o] for o in orgs)
        dif = notas - bal
        conferencia[p] = {"balancete": r2(bal), "notas": r2(notas), "diferenca": r2(dif),
                          "ok": abs(dif) <= max(1.0, abs(bal) * 0.005)}

    n_ver = len((eleitos or {}).get("vereadores") or []) or None
    cam = orgao["camara"]

    def top_forn(d, n=60):
        lst = sorted(d.values(), key=lambda f: -f["valor"])
        return [[f["nome"], f["doc"], f["tipo"], r2(f["valor"]), f["notas"],
                 {k: r2(v) for k, v in sorted(f["elementos"].items(), key=lambda x: -x[1]) if abs(v) >= 0.01}]
                for f in lst[:n] if abs(f["valor"]) >= 0.01], len(lst)

    saida_orgaos = {}
    for p, o in orgao.items():
        tf, n_forn = top_forn(forn[p])
        saida_orgaos[p] = {
            "codigos": pap.get(p, []),
            "nomes": [bruto["orgaos"].get(c, ["", ""])[0] for c in pap.get(p, [])],
            "gasto": r2(o["gasto"]), "pago": r2(o["pago"]),
            "grupos": {k: r2(v) for k, v in o["grupos"].items() if abs(v) >= 0.01},
            "elementos": {k: r2(v) for k, v in sorted(o["elementos"].items(), key=lambda x: -x[1]) if abs(v) >= 0.01},
            "fornecedores": tf, "n_fornecedores": n_forn,
        }
    pessoas_saida = {}
    for k, pe in pessoas.items():
        pe["itens"].sort(key=lambda x: (x[0], x[1]))
        pessoas_saida[k] = {"direto": r2(pe["direto"]), "citado": r2(pe["citado"]), "notas": pe["notas"],
                            "itens": pe["itens"][-120:]}
    teto = teto_vereador_mensal(ano, pop)
    return {
        "ano": ano, "mes_ref": bruto["mes_ref"], "fechado": bruto["fechado"],
        "populacao": pop,
        "gasto_total": r2(total), "pago_total": r2(pago_total),
        "por_funcao": {k: r2(v) for k, v in sorted(por_funcao.items(), key=lambda x: -x[1]) if abs(v) >= 0.01},
        "por_grupo": {k: r2(v) for k, v in por_grupo.items() if abs(v) >= 0.01},
        "receita_total": r2(receita_total),
        "receita": {k: r2(v) for k, v in receita.items() if abs(v) >= 0.01},
        "orgaos": saida_orgaos,
        "n_vereadores": n_ver,
        "camara_por_vereador": r2(cam["gasto"] / n_ver) if n_ver else None,
        "teto_subsidio_vereador": teto,
        "pessoas": pessoas_saida,
        "conferencia": conferencia,
        "detalhe": bool(bruto.get("meses")),
    }


# ------------------------------------------------------------------ nota a nota (v2)
ESTORNADO = {"S", "SIM", "1", "T", "TRUE", "E", "ESTORNADO", "ESTORNADA"}


def _k(org, data, num):
    return (org, data, (num or "").lstrip("0"))


def montar_notas(bruto: dict, eleitos: dict | None) -> dict:
    """Todas as notas de empenho da Câmara e dos gabinetes, cada uma com anulações,
    pagamentos, notas fiscais e itens. Um arquivo por município-ano."""
    pap = bruto["papeis"]
    papel_de = {o: p for p, lst in pap.items() for o in lst}
    alvo = set(bruto.get("alvo") or [])
    ident = Identificador(eleitos)
    anul, pags, nfs, itens = defaultdict(float), defaultdict(list), defaultdict(list), defaultdict(list)
    for r, md in bruto["meses"].items():
        for org, data, num, v in md["anul"]:
            if org in alvo:
                anul[_k(org, data, num)] += v
        for org, data, num, sub, np_, dpag, v, est in md["pag"]:
            pags[_k(org, data, num)].append([np_, dpag, r2(v), 1 if est.upper() in ESTORNADO else 0, sub])
        for org, data, num, tipo, nnf, serie, emi, liq, bruto_v, desc, liqv, chave, emit, verif in md["nf"]:
            nfs[_k(org, data, num)].append([nnf, serie, emi, liq, r2(bruto_v), r2(desc), r2(liqv), chave, emit, verif, tipo])
    for org, data, num, nnf, seq, desc, un, qtd, unit, tot, ncm in bruto.get("itens") or []:
        itens[_k(org, data, num)].append([nnf, seq, desc, un, qtd, unit, tot, ncm])

    forn, fidx, linhas, usados = [], {}, [], set()
    for r, md in sorted(bruto["meses"].items()):
        fz = md["forn"]
        for e in md["emp"]:
            org = e[0]
            if org not in alvo:
                continue
            nome, doc, tipo_neg, mun_neg = fz[e[6]]
            fk = (nome, doc)
            if fk not in fidx:
                fidx[fk] = len(forn)
                forn.append([nome, doc, "PJ" if doc else "PF", mun_neg])
            k = _k(org, e[1], e[2])
            usados.add(k)
            ps = pags.get(k, [])
            pago = sum(p[2] for p in ps if not p[3])
            quem, como = ident.favorecido(nome), "direto"
            if quem is None and papel_de.get(org) == "camara":
                quem, como = ident.citado(e[7]), "citado"
            linhas.append([org, e[1], e[2], e[3], fidx[fk], r2(e[5]), r2(anul.get(k, 0.0)), r2(pago), e[7],
                           e[10], e[11], e[12], e[13], e[14], e[15], quem or "", como if quem else "",
                           sorted(nfs.get(k, [])), sorted(ps, key=lambda p: (p[1], p[0])), sorted(itens.get(k, []), key=lambda i: (i[0], i[1])),
                           int(r[4:])])
    linhas.sort(key=lambda x: (x[1], x[0], x[2]))
    # pagamentos e notas fiscais de empenhos de anos anteriores (restos a pagar)
    restos = []
    for k, ps in pags.items():
        if k not in usados:
            for p in ps:
                restos.append([k[0], k[1], k[2], p[0], p[1], p[2], p[3], len(nfs.get(k, []))])
    restos.sort(key=lambda x: (x[4], x[0], x[2]))
    return {
        "ano": bruto["ano"], "mes_ref": bruto["mes_ref"],
        "orgaos": {o: [bruto["orgaos"].get(o, [""])[0], papel_de.get(o, "")] for o in sorted(alvo)},
        "forn": forn,
        "colunas": ["orgao", "data", "numero", "elemento", "i_favorecido", "empenhado", "anulado", "pago", "historico",
                    "especie_processo", "numero_processo", "contrato", "data_contrato", "modalidade", "fonte", "pessoa",
                    "como", "notas_fiscais", "pagamentos", "itens", "mes"],
        "notas_fiscais_colunas": ["numero", "serie", "emissao", "liquidacao", "bruto", "desconto", "liquido", "chave_nfe",
                                  "cnpj_emitente", "codigo_verificacao", "tipo"],
        "pagamentos_colunas": ["numero", "data", "valor", "estornado", "sub_empenho"],
        "itens_colunas": ["nota_fiscal", "seq", "descricao", "unidade", "quantidade", "valor_unitario", "valor_total", "ncm"],
        "emp": linhas,
        "restos": restos,
    }


def montar_fornecedores_prefeitura(bruto: dict) -> dict:
    """Todos os favorecidos da prefeitura inteira (todos os órgãos), com as maiores notas."""
    anul = defaultdict(float)
    for md in bruto["meses"].values():
        for org, data, num, v in md["anul"]:
            anul[_k(org, data, num)] += v
    fz = {}
    soma_por_orgao = defaultdict(float)
    n_emp = 0
    for r, md in sorted(bruto["meses"].items()):
        mes = int(r[4:])
        for e in md["emp"]:
            org, data, num, el8, valor = e[0], e[1], e[2], e[3], e[5]
            liq = valor - anul.pop(_k(org, data, num), 0.0)
            soma_por_orgao[org] += liq
            if C.intra(el8[:6]):
                continue
            n_emp += 1
            nome, doc, _tipo, mun_neg = md["forn"][e[6]]
            if doc:
                chave, rot, tp = doc, nome, "PJ"
            elif el8[1:2] == "1":
                chave, rot, tp = "_PESSOAL", "Folha, encargos e rescisões de pessoal", "FOLHA"
            else:
                chave, rot, tp = "PF:" + norm_nome(nome), nome, "PF"
            f = fz.setdefault(chave, {"nome": rot, "doc": doc, "tipo": tp, "mun": mun_neg if tp != "FOLHA" else "",
                                      "valor": 0.0, "n": 0, "orgaos": defaultdict(float), "el": defaultdict(float),
                                      "mensal": [0.0] * 12, "notas": []})
            f["valor"] += liq
            f["n"] += 1
            f["orgaos"][org] += liq
            f["el"][el8[:6]] += liq
            f["mensal"][mes - 1] += liq
            if tp != "FOLHA":
                f["notas"].append([data, org, num, el8, r2(liq), (e[7] or "")[:240], e[10], e[11], e[12]])
    # anulações sem empenho no ano (empenho de outro exercício): entram só na conferência
    for (org, _, _), v in anul.items():
        soma_por_orgao[org] -= v
    lst = sorted(fz.values(), key=lambda f: -f["valor"])
    linhas = []
    for i, f in enumerate(lst):
        if abs(f["valor"]) < 0.01 and f["n"] == 0:
            continue
        lim = 60 if i < 150 else 10
        notas = sorted(f["notas"], key=lambda x: -x[4])
        linhas.append([f["nome"], f["doc"], f["tipo"], f["mun"], r2(f["valor"]), f["n"],
                       {k: r2(v) for k, v in sorted(f["orgaos"].items(), key=lambda x: -x[1]) if abs(v) >= 0.01},
                       {k: r2(v) for k, v in sorted(f["el"].items(), key=lambda x: -x[1]) if abs(v) >= 0.01},
                       [r2(x) for x in f["mensal"]], notas[:lim]])
    bal = defaultdict(float)
    for org, fun, el6, emp, an, liq, pago, est in bruto["despesa"]:
        bal[org] += emp - an
    dif = sum(soma_por_orgao.values()) - sum(bal.values())
    tot_bal = sum(bal.values())
    return {
        "ano": bruto["ano"], "mes_ref": bruto["mes_ref"],
        "orgaos": {o: v[0] for o, v in sorted(bruto["orgaos"].items())},
        "colunas": ["nome", "cnpj", "tipo", "municipio", "valor", "notas", "por_orgao", "por_elemento", "mensal", "maiores_notas"],
        "notas_colunas": ["data", "orgao", "numero", "elemento", "valor_liquido", "historico", "especie_processo",
                          "numero_processo", "contrato"],
        "total": r2(sum(f["valor"] for f in lst)), "n_notas": n_emp, "n_favorecidos": len(linhas),
        "conferencia": {"balancete": r2(tot_bal), "notas": r2(sum(soma_por_orgao.values())), "diferenca": r2(dif),
                        "ok": abs(dif) <= max(1.0, abs(tot_bal) * 0.005)},
        "linhas": linhas,
    }


def resumo_linha(a: dict, emendas_ano: float) -> list:
    """Linha compacta para os rankings (mesma ordem de CAMPOS_RESUMO)."""
    o = a["orgaos"]
    rc = a["receita"]
    return [a["mes_ref"], a["populacao"], a["gasto_total"], o["camara"]["gasto"], o["prefeito"]["gasto"],
            o["vice"]["gasto"], a["n_vereadores"], a["receita_total"], rc.get("uniao", 0.0), rc.get("estado", 0.0),
            rc.get("propria", 0.0), r2(emendas_ano), a["teto_subsidio_vereador"],
            o["camara"]["grupos"].get("pessoal", 0.0), o["camara"]["grupos"].get("diarias", 0.0),
            int(all(c["ok"] for c in a["conferencia"].values())) if a["conferencia"] else None]


CAMPOS_RESUMO = ["mes_ref", "populacao", "gasto_total", "camara", "gab_prefeito", "gab_vice", "n_vereadores",
                 "receita_total", "transf_uniao", "transf_estado", "receita_propria", "emendas",
                 "teto_subsidio_vereador", "camara_pessoal", "camara_diarias", "conferido"]


def pessoa_publica(p: dict | None) -> dict | None:
    if not p:
        return None
    return {k: p.get(k) for k in ("nome", "urna", "partido", "numero", "genero", "situacao", "bens")}


def montar_municipio(mun: dict, brutos: dict[int, dict], eleitos_por_eleicao: dict[int, dict],
                     pop_serie: dict, emendas: list[list]) -> tuple[dict, dict]:
    """(arquivo detalhado do município, entrada do resumo, {ano: (nota a nota, fornecedores da prefeitura)})."""
    anos = {}
    linhas = {}
    em_por_ano = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, set(), set()]))
    for _sim, ano, autor, tipo, fun, emp, pago in emendas:
        e = em_por_ano[ano][autor or "Não informado"]
        e[0] += emp
        e[1] += pago
        if tipo:
            e[2].add(tipo)
        if fun:
            e[3].add(fun)
    extras = {}
    for ano in sorted(brutos):
        eleicao = mandato_do_ano(ano)
        el = (eleitos_por_eleicao.get(eleicao) or {}).get(mun["sim"])
        a = montar_ano(brutos[ano], el, populacao_no_ano(pop_serie, ano))
        if brutos[ano].get("meses"):
            fp = montar_fornecedores_prefeitura(brutos[ano])
            extras[str(ano)] = (montar_notas(brutos[ano], el), fp)
            a["prefeitura_conferencia"] = fp["conferencia"]
            a["prefeitura_favorecidos"] = fp["n_favorecidos"]
        em = em_por_ano.get(ano, {})
        a["emendas"] = sorted([[k, r2(v[0]), r2(v[1]), sorted(v[2]), sorted(v[3])] for k, v in em.items()],
                              key=lambda x: -x[1])
        a["emendas_total"] = r2(sum(v[0] for v in em.values()))
        a["eleicao"] = eleicao
        anos[str(ano)] = a
        linhas[str(ano)] = resumo_linha(a, a["emendas_total"])
    mandatos = {}
    for eleicao, por_mun in sorted(eleitos_por_eleicao.items()):
        el = por_mun.get(mun["sim"])
        if not el:
            continue
        mandatos[str(eleicao)] = {
            "periodo": list(config.MANDATO_DA_ELEICAO.get(eleicao, (eleicao + 1, eleicao + 4))),
            "prefeito": pessoa_publica(el.get("prefeito")),
            "vice": pessoa_publica(el.get("vice")),
            "vereadores": [pessoa_publica(v) for v in el.get("vereadores") or []],
        }
    detalhe = {"sim": mun["sim"], "ibge": mun["ibge"], "nome": mun["nome"], "mandatos": mandatos, "anos": anos}
    prefeitos = {e: [m["prefeito"]["urna"] or m["prefeito"]["nome"], m["prefeito"]["partido"]]
                 for e, m in mandatos.items() if m["prefeito"]}
    resumo = {"sim": mun["sim"], "ibge": mun["ibge"], "nome": mun["nome"], "prefeitos": prefeitos, "anos": linhas}
    return detalhe, resumo, extras


def hoje_iso():
    return date.today().isoformat()
