"""Testes do robô municipal. Rodar: python -m pytest -q"""
import io
import json
import sys
import threading
import zipfile
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from coletor import classificar as C  # noqa: E402
from coletor import eleitos as E  # noqa: E402
from coletor import extras, montar  # noqa: E402
from coletor import municipio as M  # noqa: E402


# ----------------------------------------------------------------- servidor falso do TCE
ORGAOS = [
    {"codigo_orgao": "01", "nome_orgao": "CÂMARA MUNICIPAL DE SOBRAL", "codigo_tipo_unidade": "02"},
    {"codigo_orgao": "02", "nome_orgao": "GABINETE DO PREFEITO", "codigo_tipo_unidade": "01"},
    {"codigo_orgao": "06", "nome_orgao": "SECRETARIA MUNICIPAL DA EDUCAÇÃO", "codigo_tipo_unidade": "03"},
    {"codigo_orgao": "16", "nome_orgao": "GABINETE DO A  VICE-PREFEITO A", "codigo_tipo_unidade": "03"},
    {"codigo_orgao": "37", "nome_orgao": "SECRETARIA DA AGRICULTURA", "codigo_tipo_unidade": "01"},
    {"codigo_orgao": "AA", "nome_orgao": "Prefeitura Municipal", "codigo_tipo_unidade": "00"},
]


def bal(org, fun, el, emp, anul, liq, pago):
    return {"codigo_orgao": org, "codigo_funcao": fun, "codigo_elemento_despesa": el,
            "valor_empenhado_ate_mes": emp, "valor_anulacoes_empenhos_ate_mes": anul,
            "valor_liquidado_ate_mes": liq, "valor_pago_ate_mes": pago, "valor_estornos_pagos_ate_mes": 0}


BALANCETE = [
    bal("01", "01", "31901100", 1000.0, 0, 1000.0, 1000.0),
    bal("01", "01", "33903900", 600.0, 100.0, 500.0, 500.0),
    bal("01", "01", "33901400", 50.0, 0, 50.0, 50.0),
    bal("02", "04", "33903900", 300.0, 0, 300.0, 300.0),
    bal("06", "12", "31901100", 5000.0, 0, 5000.0, 4800.0),
    bal("06", "12", "31911300", 700.0, 0, 700.0, 700.0),     # intraorçamentária
    bal("16", "04", "33903000", 20.0, 0, 20.0, 20.0),
]
RECEITA = [
    {"codigo_rubrica": "111250010000000", "valor_arrecadacao_ate_mes": 900.0, "valor_anulacoes_ate_mes": 0},
    {"codigo_rubrica": "171151110000000", "valor_arrecadacao_ate_mes": 4000.0, "valor_anulacoes_ate_mes": 0},
    {"codigo_rubrica": "172150010000000", "valor_arrecadacao_ate_mes": 1500.0, "valor_anulacoes_ate_mes": 0},
    {"codigo_rubrica": "175150010000000", "valor_arrecadacao_ate_mes": 800.0, "valor_anulacoes_ate_mes": 0},
    {"codigo_rubrica": "951700000000000", "valor_arrecadacao_ate_mes": -300.0, "valor_anulacoes_ate_mes": 0},
    {"codigo_rubrica": "779000000000000", "valor_arrecadacao_ate_mes": 700.0, "valor_anulacoes_ate_mes": 0},
]


def emp(org, ref, num, el, valor, nome, doc, tipo, hist):
    return {"codigo_orgao": org, "data_emissao_empenho": f"{str(ref)[:4]}-{str(ref)[4:]}-05T00:00:00",
            "numero_empenho": num, "codigo_elemento_despesa": el, "cd_subelem_desp": "99", "valor_empenhado": valor,
            "nome_negociante": nome, "numero_documento_negociante": doc, "codigo_tipo_negociante": tipo,
            "descricao_historico_empenho": hist, "codigo_funcao": "01", "endereco_negociante": "x"}


EMPENHOS = {
    ("01", 202501): [
        emp("01", 202501, "1", "31901100", 1000.0, "FOLHA DE PAGAMENTO", "", "6", "FOLHA DE VEREADORES"),
        emp("01", 202501, "2", "33903900", 400.0, "ARTE SERVICOS LTDA", "10863187000100", "1",
            "SERVIÇOS DE COMUNICAÇÃO DO MANDATO. SOLICITADO PELO GABINETE DO VEREADOR ALAN VERAS, CONFORME LEI"),
    ],
    ("01", 202502): [
        emp("01", 202502, "3", "33903900", 200.0, "ADVOCACIA X", "53300806000161", "1",
            "SERVIÇOS JURÍDICOS AO GABINETE DA VEREADORA MICHELINE CARNEIRO IBIAPINA."),
        emp("01", 202502, "4", "33901400", 50.0, "JOSE DA SILVA", "XTbsDUnCRQW6XljPlyMQ9A==", "2",
            "DIÁRIAS PARA VIAGEM A FORTALEZA"),
    ],
    ("02", 202502): [emp("02", 202502, "9", "33903900", 300.0, "EMPRESA Y", "07995566000140", "1", "SERVIÇO")],
    ("16", 202501): [emp("16", 202501, "7", "33903000", 20.0, "PAPELARIA", "13981060000184", "1", "MATERIAL")],
    ("06", 202502): [emp("06", 202502, "50", "31901100", 5000.0, "FOLHA EDUCACAO", "", "6", "FOLHA DOS PROFESSORES"),
                     emp("06", 202502, "51", "31911300", 700.0, "INSTITUTO DE PREVIDENCIA", "07000000000100", "1", "PATRONAL")],
}
ANULACOES = {("01", 202502): [{"codigo_orgao": "01", "data_emissao_empenho": "2025-01-05T00:00:00", "numero_nota_empenho": "2",
                               "valor_anulacao": 100.0}]}
PAGAMENTOS = {("01", 202502): [
    {"data_emissao_empenho": "2025-01-05T00:00:00", "numero_empenho": "2", "numero_sub_empenho": "1",
     "numero_nota_pagamento": "77", "data_nota_pagamento": "2025-02-10T00:00:00", "valor_nota_pagamento": 300.0,
     "estado_de_estornado": "N", "cpf_responsavel_pagamento": "123"},
    {"data_emissao_empenho": "2024-12-20T00:00:00", "numero_empenho": "999", "numero_sub_empenho": "1",
     "numero_nota_pagamento": "78", "data_nota_pagamento": "2025-02-11T00:00:00", "valor_nota_pagamento": 55.0,
     "estado_de_estornado": "N"}]}
NOTAS_FISCAIS = {("01", 202502): [
    {"data_emissao_empenho": "2025-01-05T00:00:00", "numero_empenho": "2", "tipo_nota_fiscal": "1",
     "numero_nota_fiscal": "1234", "numero_serie": "1", "data_emissao": "2025-02-01T00:00:00",
     "data_liquidacao": "2025-02-02T00:00:00", "valor_bruto": 300.0, "valor_desconto": 0, "valor_liquido": 300.0,
     "numero_chave_acesso_nfe": "23250210863187000100550010000012341000012345", "cpf_cnpj_emitente": "10863187000100",
     "codigo_verifica_nfe_fpn": "ABC"}]}
ITENS = {"01": [{"data_emissao": "2025-01-05T00:00:00", "numero_nota_empenho": "2", "numero_nota_fiscal": "1234",
                 "numero_item_sequencial": 1, "descricao_item": "PANFLETOS A4", "unidade_compra": "UN",
                 "numero_quantidade_comprada": 1000, "valor_unitario_item": 0.3, "valor_total_item": 300.0,
                 "codigo_ncm": "49111090"}]}

CHAMADAS = []


class TCEFalso(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        CHAMADAS.append((u.path, q))
        caminho = u.path.rsplit("/", 1)[-1]
        assert q.get("exercicio_orcamento") == "202500", q   # formato AAAA00
        ref = int(q.get("data_referencia_doc", 0))
        org = q.get("codigo_orgao")
        if caminho == "balancetes_despesas_orcamentarias":
            dados = BALANCETE if ref == 202502 else []
        elif caminho == "balancetes_receitas_orcamentarias":
            dados = RECEITA if ref == 202502 else []
        elif caminho == "orgaos":
            dados = ORGAOS
        elif caminho == "notas_empenhos":
            dados = [x for (o, r), l in EMPENHOS.items() if r == ref and org in (None, o) for x in l]
        elif caminho == "notas_anulacoes_empenhos":
            dados = [x for (o, r), l in ANULACOES.items() if r == ref and org in (None, o) for x in l]
        elif caminho == "notas_pagamentos":
            dados = PAGAMENTOS.get((org, ref), [])
        elif caminho == "notas_fiscais":
            dados = NOTAS_FISCAIS.get((org, ref), [])
        elif caminho == "itens_notas_fiscais":
            dados = ITENS.get(org, [])
        else:
            self.send_response(404)
            self.end_headers()
            return
        ini = int(q.get("$start_index", 0))
        n = int(q.get("$count", 1000))
        corpo = json.dumps({"elements": dados[ini:ini + n]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(corpo)


@pytest.fixture()
def tce_falso(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), TCEFalso)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    monkeypatch.setattr(config, "TCE_API", f"http://127.0.0.1:{srv.server_address[1]}/sim")
    monkeypatch.setattr(config, "PAUSA_ENTRE_REQUISICOES", 0)
    from coletor import tce
    monkeypatch.setattr(tce, "_sessao", lambda: __import__("requests").Session())
    CHAMADAS.clear()
    yield
    srv.shutdown()


ELEITOS = {
    "prefeito": {"nome": "MARIA PREFEITA SOUSA", "urna": "MARIA", "partido": "AAA", "numero": "10", "genero": "Feminino",
                 "situacao": "Eleito", "sq": "1", "bens": 1000.0},
    "vice": {"nome": "JOAO VICE", "urna": "JOAO", "partido": "BBB", "numero": "10", "genero": "Masculino",
             "situacao": "Eleito", "sq": "2", "bens": None},
    "vereadores": [
        {"nome": "GEORGE ALAN FERREIRA VERAS", "urna": "ALAN VERAS", "partido": "CCC", "numero": "1", "genero": "",
         "situacao": "Eleito", "sq": "3", "bens": None},
        {"nome": "MICHELINE CARNEIRO IBIAPINA", "urna": "MICHELINE", "partido": "DDD", "numero": "2", "genero": "",
         "situacao": "Eleito", "sq": "4", "bens": None},
        {"nome": "JOSE DA SILVA", "urna": "ZE DA BODEGA", "partido": "EEE", "numero": "3", "genero": "",
         "situacao": "Eleito", "sq": "5", "bens": None},
    ],
}


# ----------------------------------------------------------------- testes
def test_papeis_pelo_nome_e_nao_pelo_tipo():
    org = {o["codigo_orgao"]: [o["nome_orgao"], o["codigo_tipo_unidade"]] for o in ORGAOS}
    p = M.papeis(org)
    assert p == {"camara": ["01"], "prefeito": ["02"], "vice": ["16"]}   # "37 Agricultura t01" fica de fora


def test_receita_por_origem_nos_dois_ementarios():
    assert C.grupo_receita("171151110000000", 2025) == "uniao"
    assert C.grupo_receita("172150010000000", 2025) == "estado"
    assert C.grupo_receita("175150010000000", 2025) == "fundeb"
    assert C.grupo_receita("172101000000000", 2017) == "uniao"     # 1.7.2.1 no ementário antigo
    assert C.grupo_receita("172200000000000", 2017) == "estado"
    assert C.grupo_receita("172400000000000", 2017) == "fundeb"
    assert C.grupo_receita("247100000000000", 2017) == "uniao"
    assert C.grupo_receita("241800000000000", 2019) == "uniao"
    assert C.grupo_receita("951700000000000", 2019) == "deducoes"
    assert C.grupo_receita("721000000000000", 2017) is None          # intraorçamentária
    assert C.grupo_receita("111250010000000", 2025) == "propria"


def test_grupos_de_despesa():
    assert C.grupo_despesa("319011") == "pessoal"
    assert C.grupo_despesa("339014") == "diarias"
    assert C.grupo_despesa("339039") == "servicos"
    assert C.grupo_despesa("449052") == "obras"
    assert C.intra("319113") and not C.intra("319011")


def test_coleta_e_montagem_ponta_a_ponta(tce_falso):
    novo = M.coletar("162", 2025, None, hoje=date(2025, 3, 10))
    assert novo["mes_ref"] == 202502                  # março ainda não chegou ao TCE
    assert novo["papeis"]["camara"] == ["01"] and novo["alvo"] == ["01", "02", "16"]
    meses, itens = novo.pop("meses_novos"), novo.pop("itens")
    assert set(meses) == {"202501", "202502"} and novo["meses_completos"] == ["202501", "202502"]
    txt = json.dumps([novo, meses, itens])
    assert "XTbsDUnCRQW6XljPlyMQ9A" not in txt and "endereco" not in txt   # CPF cifrado e endereço não são guardados
    b = M.compor(novo, meses, itens)
    assert set(b["empenhos"]) == {"202501", "202502"}
    assert all(len(x) == 11 for x in b["empenhos"]["202502"])
    pf = [x for x in b["empenhos"]["202502"] if x[6] == "JOSE DA SILVA"][0]
    assert pf[7] == ""
    a = montar.montar_ano(b, ELEITOS, 210000)
    # total do município exclui a intraorçamentária (700)
    assert a["gasto_total"] == pytest.approx(1000 + 500 + 50 + 300 + 5000 + 20)
    assert a["orgaos"]["camara"]["gasto"] == pytest.approx(1550)
    assert a["orgaos"]["prefeito"]["gasto"] == 300 and a["orgaos"]["vice"]["gasto"] == 20
    assert a["receita"] == {"propria": 900, "uniao": 4000, "estado": 1500, "fundeb": 800, "deducoes": -300}
    assert a["receita_total"] == pytest.approx(6900)
    # notas - anulações batem com o balancete em cada órgão
    assert all(c["ok"] for c in a["conferencia"].values()), a["conferencia"]
    # vereador citado no histórico e vereador que recebeu diretamente
    assert a["pessoas"]["v0"]["citado"] == pytest.approx(300)   # 400 - 100 anulados
    assert a["pessoas"]["v1"]["citado"] == pytest.approx(200)
    assert a["pessoas"]["v2"]["direto"] == pytest.approx(50)
    assert a["n_vereadores"] == 3 and a["camara_por_vereador"] == pytest.approx(1550 / 3, abs=0.01)
    # folha agregada, PJ por CNPJ
    nomes = [f[0] for f in a["orgaos"]["camara"]["fornecedores"]]
    assert "Folha, encargos e rescisões de pessoal" in nomes and "ARTE SERVICOS LTDA" in nomes
    # nota a nota: anulação, pagamento, nota fiscal e itens presos ao empenho certo
    n = montar.montar_notas(b, ELEITOS)
    arte = [e for e in n["emp"] if e[2] == "2"][0]
    assert arte[5] == 400 and arte[6] == 100 and arte[7] == 300
    assert arte[15] == "v0" and arte[16] == "citado"
    assert arte[17][0][0] == "1234" and arte[17][0][7].startswith("2325") and arte[17][0][8] == "10863187000100"
    assert arte[19][0][2] == "PANFLETOS A4" and arte[19][0][6] == 300
    assert n["restos"] == [["01", "2024-12-20", "999", "78", "2025-02-11", 55.0, 0, 0]]   # resto a pagar de 2024
    assert {e[0] for e in n["emp"]} == {"01", "02", "16"}
    # fornecedores da prefeitura inteira: inclui a Agricultura (órgão 37), sem a intraorçamentária
    fp = montar.montar_fornecedores_prefeitura(b)
    nomes = {l[0]: l for l in fp["linhas"]}
    assert "ARTE SERVICOS LTDA" in nomes and nomes["ARTE SERVICOS LTDA"][4] == 300
    assert "INSTITUTO DE PREVIDENCIA" not in nomes                      # intraorçamentária fica de fora
    assert nomes["Folha, encargos e rescisões de pessoal"][4] == pytest.approx(6000)   # 1000 câmara + 5000 educação
    assert nomes["Folha, encargos e rescisões de pessoal"][6] == {"06": 5000, "01": 1000}
    assert fp["conferencia"]["ok"], fp["conferencia"]
    # teto: 50% (100 a 300 mil hab.) de 75% do deputado federal
    assert a["teto_subsidio_vereador"] == pytest.approx(round((46366.19 * 11 + 44008.52) / 12 * .75 * .5, 2))


def test_coleta_incremental_so_refaz_os_ultimos_meses(tce_falso):
    b = M.coletar("162", 2025, None, hoje=date(2025, 3, 10))
    CHAMADAS.clear()
    M.coletar("162", 2025, b, hoje=date(2025, 3, 11))
    assert {q["data_referencia_doc"] for p, q in CHAMADAS if p.endswith("/notas_fiscais")} == {"202501", "202502"}
    meses = {q["data_referencia_doc"] for p, q in CHAMADAS if p.endswith("notas_empenhos")}
    assert meses == {"202501", "202502"}        # os dois últimos meses são sempre refeitos


def test_identificador_descarta_apelido_ambiguo():
    el = {"vereadores": [{"nome": "ANA LIMA", "urna": "ANA"}, {"nome": "ANA SOUSA", "urna": "ANA"}]}
    i = montar.Identificador(el)
    assert i.citado("GABINETE DA VEREADORA ANA") is None
    assert i.citado("GABINETE DA VEREADORA ANA LIMA") == "v0"


def _zip(nome, texto):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(nome, texto.encode("latin-1"))
    return buf.getvalue()


def test_eleitos_tse_com_segundo_turno_e_vice():
    cab = "NM_TIPO_ELEICAO;NR_TURNO;SG_UE;CD_CARGO;SQ_CANDIDATO;NR_CANDIDATO;NM_CANDIDATO;NM_URNA_CANDIDATO;SG_PARTIDO;DS_GENERO;DS_SIT_TOT_TURNO"
    linhas = [
        "ELEIÇÃO ORDINÁRIA;1;13897;11;100;10;FULANO;FULANO;AAA;MASCULINO;2º TURNO",
        "ELEIÇÃO ORDINÁRIA;2;13897;11;100;10;FULANO;FULANO;AAA;MASCULINO;ELEITO",
        "ELEIÇÃO ORDINÁRIA;2;13897;11;101;20;BELTRANO;BELTRANO;BBB;MASCULINO;NÃO ELEITO",
        "ELEIÇÃO ORDINÁRIA;2;13897;12;102;10;VICE DO FULANO;VICE;AAA;FEMININO;#NULO#",
        "ELEIÇÃO ORDINÁRIA;1;13897;13;103;12345;VEREADORA UM;UMA;CCC;FEMININO;ELEITO POR QP",
        "ELEIÇÃO ORDINÁRIA;1;13897;13;104;12346;VEREADOR DOIS;DOIS;CCC;MASCULINO;ELEITO POR MÉDIA",
        "ELEIÇÃO ORDINÁRIA;1;13897;13;105;12347;SUPLENTE;SUP;CCC;MASCULINO;SUPLENTE",
        "ELEIÇÃO SUPLEMENTAR;1;13897;11;106;30;OUTRO;OUTRO;DDD;MASCULINO;ELEITO",
    ]
    cand = E._csv_do_zip(_zip("consulta_cand_2024_CE.csv", "\n".join([cab] + linhas)), "CE")
    bens = E.bens_por_candidato(_zip("bem_candidato_2024_CE.csv",
                                     "SQ_CANDIDATO;VR_BEM_CANDIDATO\n100;1500,50\n100;1000\n103;250000,00"), "CE")
    r = E.eleitos(cand, bens, {"13897": "043"})["043"]
    assert r["prefeito"]["nome"] == "FULANO" and r["prefeito"]["bens"] == 2500.5
    assert r["vice"]["nome"] == "VICE DO FULANO"
    assert [v["urna"] for v in r["vereadores"]] == ["DOIS", "UMA"]


def test_populacao_ano_mais_proximo():
    s = {"2021": 10, "2022": 12, "2024": 15}
    assert extras.populacao_no_ano(s, 2022) == 12
    assert extras.populacao_no_ano(s, 2023) == 12      # empate: fica com o anterior
    assert extras.populacao_no_ano(s, 2017) == 10
    assert extras.populacao_no_ano(s, 2026) == 15


def test_emendas_por_municipio():
    csv_txt = ("Ano da Emenda;Tipo de Emenda;Nome do Autor da Emenda;Nome Função;Código Município IBGE;Município;UF;"
               "Valor Empenhado;Valor Pago;Valor Restos A Pagar Pagos\n"
               "2024;Emenda Individual - Transferências com Finalidade Definida;FULANO;Saúde;2312908;SOBRAL;CE;1.000,00;500,00;100,00\n"
               "2024;Emenda de Bancada;BANCADA DO CEARÁ;Educação;;MASSAPÊ;CE;2.000,00;0,00;0,00\n"
               "2024;Emenda Individual;OUTRO;Saúde;3550308;SÃO PAULO;SP;9,00;9,00;0,00\n")
    linhas = extras.ler_emendas(csv_txt.encode("latin-1"), {"MASSAPE": "103"}, {"2312908": "162"})
    assert linhas == [["162", 2024, "FULANO", "Emenda Individual - Transferências com Finalidade Definida", "Saúde", 1000.0, 600.0],
                      ["103", 2024, "BANCADA DO CEARÁ", "Emenda de Bancada", "Educação", 2000.0, 0.0]]


def test_ler_ibge():
    j = [{"resultados": [{"series": [{"localidade": {"id": "2312908"}, "serie": {"2024": "212437", "2025": "214000"}}]}]}]
    assert extras.ler_ibge(j) == {"2312908": {2024: 212437, 2025: 214000}}


def test_arquivos_por_mes_e_compatibilidade_v1(tce_falso, tmp_path, monkeypatch):
    import atualizar as A
    monkeypatch.setattr(A, "BRUTOS", tmp_path / "brutos")
    monkeypatch.setattr(A, "SAIDA", tmp_path / "site")
    A.coletar_um(2025, "162", date(2025, 3, 10))
    pasta = tmp_path / "brutos" / "tce" / "2025" / "162"
    assert sorted(p.name for p in pasta.iterdir()) == ["202501.json", "202502.json", "itens.json"]
    resumo = json.loads((tmp_path / "brutos" / "tce" / "2025" / "162.json").read_text())
    assert "meses_novos" not in resumo and "itens" not in resumo and "empenhos" not in resumo
    # gravar não reescreve arquivo igual (o git não guarda cópia nova)
    antes = (pasta / "202501.json").stat().st_mtime_ns
    A.coletar_um(2025, "162", date(2025, 3, 11))
    assert (pasta / "202501.json").stat().st_mtime_ns == antes
    b = A.carregar_bruto(2025, "162")
    assert b["empenhos"] and b["meses"] and b["itens"]
    # um arquivo v1 antigo continua sendo lido pelo site até o robô refazer
    v1 = dict(b, versao=1)
    for k in ("meses", "itens"):
        v1.pop(k)
    A.gravar(tmp_path / "brutos" / "tce" / "2024" / "162.json", v1)
    assert A.carregar_bruto(2024, "162")["versao"] == 1
    assert A.precisa(2024, "162", date(2025, 3, 11))       # v1 entra na fila para ganhar o detalhe


def test_identificador_sem_eleitos_nao_quebra():
    i = montar.Identificador(None)
    assert i.favorecido("QUALQUER") is None and i.citado("VEREADOR FULANO") is None
