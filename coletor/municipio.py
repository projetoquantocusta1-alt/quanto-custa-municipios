"""Coleta de um município em um exercício, direto da API do SIM/TCE-CE.

Versão 2 (nota a nota). Arquivos em dados_brutos/tce/AAAA/:
  CCC.json         resumo do ano (pequeno): órgãos, papéis, balancete de despesa e receita,
                   meses já coletados. É o único arquivo que muda todo dia.
  CCC/AAAAMM.json  um mês, escrito de forma determinística (só muda se o TCE mudar):
     forn  [[nome, cnpj, tipo_negociante, municipio_do_negociante]]   (índice usado em emp)
     emp   notas de empenho de TODOS os órgãos da prefeitura:
           [orgao, data, numero, elemento8, sub, valor, i_forn, historico, funcao, unidade,
            especie_processo, numero_processo, numero_contrato, data_contrato, modalidade, fonte]
           (histórico inteiro nos órgãos da Câmara e dos gabinetes; nos demais, até 240
            caracteres e só em notas a partir de R$ 2.000, para o arquivo não explodir)
     anul  anulações de empenho de todos os órgãos: [orgao, data_empenho, numero_empenho, valor]
     pag   notas de pagamento (Câmara e gabinetes):
           [orgao, data_empenho, numero_empenho, sub, numero_pagamento, data, valor, estornado]
     nf    notas fiscais (Câmara e gabinetes):
           [orgao, data_empenho, numero_empenho, tipo, numero, serie, emissao, liquidacao,
            bruto, desconto, liquido, chave_nfe, cnpj_emitente, codigo_verificacao]
  CCC/itens.json   itens das notas fiscais (Câmara e gabinetes) do ano inteiro:
           [orgao, data_empenho, numero_empenho, numero_nf, seq, descricao, unidade,
            quantidade, valor_unitario, valor_total, ncm]

O CPF de pessoas físicas chega cifrado do TCE e não é guardado (nem endereço e telefone).
"""
import re
import unicodedata
from datetime import date

from coletor import tce
from coletor.privacidade import mascarar_cpf_no_texto

VERSAO = 2
VERSOES_LEGIVEIS = (1, 2)   # o site ainda monta arquivos da versão 1 enquanto o robô não refaz


def sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()


def papel_do_orgao(nome: str, tipo: str) -> str | None:
    """camara, prefeito, vice ou None. O nome manda; o tipo só desempata,
    porque há prefeituras que marcam secretarias comuns com o tipo 01."""
    n = re.sub(r"\s+", " ", sem_acento(nome)).strip()
    if "CAMARA" in n and ("MUNICIPAL" in n or "VEREADOR" in n) or (tipo == "02" and "CAMARA" in n):
        return "camara"
    if "VICE" in n and "PREFEIT" in n:
        return "vice"
    if "GABINETE" in n and "PREFEIT" in n:
        return "prefeito"
    return None


def papeis(orgaos: dict) -> dict:
    out = {"camara": [], "prefeito": [], "vice": []}
    for cod, (nome, tipo) in sorted(orgaos.items()):
        p = papel_do_orgao(nome, tipo)
        if p:
            out[p].append(cod)
    # sem órgão "Câmara" pelo nome: usa o tipo 02 (Câmara Municipal) da tabela do TCE
    if not out["camara"]:
        out["camara"] = [c for c, (_, t) in sorted(orgaos.items()) if t == "02"]
    return out


def doc_publico(doc: str, tipo_neg: str) -> str:
    """Só CNPJ válido em claro; CPF (cifrado pelo TCE) não é guardado."""
    d = re.sub(r"\D", "", doc or "")
    return d if len(d) == 14 else ""


def _mes_mais_recente(cod: str, ano: int, hoje: date) -> int | None:
    ultimo = 12 if ano < hoje.year else hoje.month
    for m in range(ultimo, 0, -1):
        ref = tce.referencia(ano, m)
        if tce.existe("balancetes_despesas_orcamentarias",
                      {"codigo_municipio": cod, "exercicio_orcamento": tce.exercicio(ano),
                       "data_referencia_doc": ref}):
            return ref
    return None


def _orgaos(cod, ano):
    lst = tce.consultar("orgaos", {"codigo_municipio": cod, "exercicio_orcamento": tce.exercicio(ano)})
    return {o["codigo_orgao"].strip(): [re.sub(r"\s+", " ", (o.get("nome_orgao") or "")).strip(),
                                         (o.get("codigo_tipo_unidade") or "").strip()] for o in lst}


def _despesa(cod, ano, ref):
    lst = tce.consultar("balancetes_despesas_orcamentarias",
                        {"codigo_municipio": cod, "exercicio_orcamento": tce.exercicio(ano),
                         "data_referencia_doc": ref})
    agg: dict[tuple, list] = {}
    for x in lst:
        k = ((x.get("codigo_orgao") or "").strip(), (x.get("codigo_funcao") or "").strip(),
             (x.get("codigo_elemento_despesa") or "")[:6])
        v = agg.setdefault(k, [0.0] * 5)
        v[0] += x.get("valor_empenhado_ate_mes") or 0
        v[1] += x.get("valor_anulacoes_empenhos_ate_mes") or 0
        v[2] += x.get("valor_liquidado_ate_mes") or 0
        v[3] += x.get("valor_pago_ate_mes") or 0
        v[4] += x.get("valor_estornos_pagos_ate_mes") or 0
    return [[*k, *[round(a, 2) for a in v]] for k, v in sorted(agg.items()) if any(v)]


def _receita(cod, ano, ref):
    lst = tce.consultar("balancetes_receitas_orcamentarias",
                        {"codigo_municipio": cod, "exercicio_orcamento": tce.exercicio(ano),
                         "data_referencia_doc": ref})
    agg: dict[str, float] = {}
    for x in lst:
        r = (x.get("codigo_rubrica") or "").strip()
        agg[r] = agg.get(r, 0.0) + (x.get("valor_arrecadacao_ate_mes") or 0) - (x.get("valor_anulacoes_ate_mes") or 0)
    return [[r, round(v, 2)] for r, v in sorted(agg.items()) if abs(v) >= 0.005]


def _limpo(s, n=None) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:n] if n else s


def _d(s) -> str:
    return (s or "")[:10]


def _v(x) -> float:
    try:
        return round(float(x or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _mes_empenhos(cod, ano, ref, alvo):
    """Todas as notas de empenho do mês, de todos os órgãos (uma consulta só)."""
    lst = tce.consultar("notas_empenhos", {"codigo_municipio": cod, "exercicio_orcamento": tce.exercicio(ano),
                                           "data_referencia_doc": ref})
    forn, idx, emp = [], {}, []
    for e in lst:
        org = _limpo(e.get("codigo_orgao"))
        tipo = _limpo(e.get("codigo_tipo_negociante"))
        f = (mascarar_cpf_no_texto(_limpo(e.get("nome_negociante"))), doc_publico(e.get("numero_documento_negociante"), tipo), tipo,
             _limpo(e.get("municipio_negociante"), 60))
        if f not in idx:
            idx[f] = len(forn)
            forn.append(list(f))
        valor = _v(e.get("valor_empenhado"))
        hist = mascarar_cpf_no_texto(_limpo(e.get("descricao_historico_empenho")))
        if org in alvo:
            hist = hist[:1500]
        else:
            hist = hist[:240] if abs(valor) >= 2000 else ""
        emp.append([org, _d(e.get("data_emissao_empenho")), _limpo(e.get("numero_empenho")),
                    _limpo(e.get("codigo_elemento_despesa")), _limpo(e.get("cd_subelem_desp")), valor, idx[f], hist,
                    _limpo(e.get("codigo_funcao")), _limpo(e.get("codigo_unidade_orcamentaria")),
                    _limpo(e.get("tipo_processo_licitatorio")), _limpo(e.get("numero_licitacao"), 40),
                    _limpo(e.get("numero_contrato"), 40), _d(e.get("data_contrato")),
                    _limpo(e.get("modalidade_nota_empenho")), _limpo(e.get("codigo_fonte"))])
    emp.sort(key=lambda x: (x[0], x[1], x[2], x[5]))
    return forn, emp


def _mes_anulacoes(cod, ano, ref):
    lst = tce.consultar("notas_anulacoes_empenhos", {"codigo_municipio": cod, "exercicio_orcamento": tce.exercicio(ano),
                                                     "data_referencia_doc": ref})
    out = [[_limpo(a.get("codigo_orgao")), _d(a.get("data_emissao_empenho")), _limpo(a.get("numero_nota_empenho")),
            _v(a.get("valor_anulacao"))] for a in lst]
    return sorted(out)


def _mes_pagamentos(cod, ano, ref, orgao):
    lst = tce.consultar("notas_pagamentos", {"codigo_municipio": cod, "exercicio_orcamento": tce.exercicio(ano),
                                             "codigo_orgao": orgao, "data_referencia_doc": ref})
    return [[orgao, _d(p.get("data_emissao_empenho")), _limpo(p.get("numero_empenho")), _limpo(p.get("numero_sub_empenho")),
             _limpo(p.get("numero_nota_pagamento")), _d(p.get("data_nota_pagamento")), _v(p.get("valor_nota_pagamento")),
             _limpo(p.get("estado_de_estornado"))] for p in lst]


def _mes_notas_fiscais(cod, ano, ref, orgao):
    lst = tce.consultar("notas_fiscais", {"codigo_municipio": cod, "exercicio_orcamento": tce.exercicio(ano),
                                          "codigo_orgao": orgao, "data_referencia_doc": ref})
    out = []
    for n in lst:
        emit = re.sub(r"\D", "", n.get("cpf_cnpj_emitente") or "")
        out.append([orgao, _d(n.get("data_emissao_empenho")), _limpo(n.get("numero_empenho")),
                    _limpo(n.get("tipo_nota_fiscal")), _limpo(n.get("numero_nota_fiscal"), 30), _limpo(n.get("numero_serie"), 10),
                    _d(n.get("data_emissao")), _d(n.get("data_liquidacao")), _v(n.get("valor_bruto")),
                    _v(n.get("valor_desconto")), _v(n.get("valor_liquido")),
                    re.sub(r"\D", "", n.get("numero_chave_acesso_nfe") or "")[:44],
                    emit if len(emit) == 14 else "", _limpo(n.get("codigo_verifica_nfe_fpn"), 40)])
    return out


def _itens(cod, ano, orgao):
    lst = tce.consultar("itens_notas_fiscais", {"codigo_municipio": cod, "exercicio_orcamento": tce.exercicio(ano),
                                                "codigo_orgao": orgao})
    out = [[orgao, _d(i.get("data_emissao")), _limpo(i.get("numero_nota_empenho")), _limpo(i.get("numero_nota_fiscal"), 30),
            int(_v(i.get("numero_item_sequencial"))), mascarar_cpf_no_texto(_limpo(i.get("descricao_item"), 300)), _limpo(i.get("unidade_compra"), 20),
            _v(i.get("numero_quantidade_comprada")), _v(i.get("valor_unitario_item")), _v(i.get("valor_total_item")),
            _limpo(i.get("codigo_ncm"), 12)] for i in lst]
    return sorted(out, key=lambda x: (x[1], x[2], x[3], x[4]))


def coletar_mes(cod, ano, ref, alvo) -> dict:
    forn, emp = _mes_empenhos(cod, ano, ref, set(alvo))
    pag, nf = [], []
    for o in alvo:
        pag += _mes_pagamentos(cod, ano, ref, o)
        nf += _mes_notas_fiscais(cod, ano, ref, o)
    return {"forn": forn, "emp": emp, "anul": _mes_anulacoes(cod, ano, ref), "pag": sorted(pag), "nf": sorted(nf)}


def coletar(cod: str, ano: int, antigo: dict | None, hoje: date | None = None) -> dict | None:
    """Atualiza um município-ano. Devolve None se o TCE ainda não tem dados.

    Devolve o resumo do ano com duas chaves a mais, que quem chama grava em arquivos
    separados: "meses_novos" {AAAAMM: dados do mês} e "itens" (itens das notas fiscais)."""
    hoje = hoje or date.today()
    antigo = antigo if (antigo or {}).get("versao") == VERSAO else None
    ref = _mes_mais_recente(cod, ano, hoje)
    if ref is None:
        return None
    orgaos = _orgaos(cod, ano)
    pap = papeis(orgaos)
    alvo = sorted(set(pap["camara"] + pap["prefeito"] + pap["vice"]))

    ja = set((antigo or {}).get("meses_completos") or [])
    if (antigo or {}).get("alvo") != alvo:      # mudou a lista de órgãos: refaz os meses
        ja = set()
    ultimo_mes = ref % 100
    # Os dois últimos meses sempre são refeitos: é onde o município ainda corrige o que mandou.
    refazer = {str(tce.referencia(ano, m)) for m in range(max(1, ultimo_mes - 1), ultimo_mes + 1)}
    novos = {}
    for m in range(1, ultimo_mes + 1):
        r = str(tce.referencia(ano, m))
        if r in ja and r not in refazer:
            continue
        novos[r] = coletar_mes(cod, ano, int(r), alvo)
    itens = []
    for o in alvo:
        itens += _itens(cod, ano, o)
    completos = sorted((ja | set(novos)) & {str(tce.referencia(ano, m)) for m in range(1, ultimo_mes + 1)})
    return {
        "versao": VERSAO, "municipio": cod, "ano": ano, "mes_ref": ref,
        "fechado": ref == tce.referencia(ano, 12) and ano < hoje.year,
        "coletado_em": hoje.isoformat(),
        "orgaos": orgaos, "papeis": pap, "alvo": alvo,
        "despesa": _despesa(cod, ano, ref),
        "receita": _receita(cod, ano, ref),
        "meses_completos": completos,
        "meses_novos": novos, "itens": sorted(itens),
    }


def compor(ano_v2: dict, meses: dict, itens: list | None) -> dict:
    """Junta o resumo do ano (v2) com os meses gravados à parte, no formato que montar.py lê.
    Também devolve "empenhos"/"anulacoes" dos órgãos-alvo no formato antigo (v1)."""
    alvo = set(ano_v2.get("alvo") or [])
    b = dict(ano_v2)
    b["meses"] = meses
    b["itens"] = itens or []
    b["empenhos"], b["anulacoes"] = {}, {}
    for r, md in sorted(meses.items()):
        fz = md["forn"]
        b["empenhos"][r] = [[e[0], e[1], e[2], e[3], e[4], e[5], fz[e[6]][0], fz[e[6]][1], fz[e[6]][2], e[7], e[8]]
                            for e in md["emp"] if e[0] in alvo]
        b["anulacoes"][r] = [a for a in md["anul"] if a[0] in alvo]
    return b
