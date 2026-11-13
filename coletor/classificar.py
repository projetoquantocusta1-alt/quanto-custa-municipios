"""Tradução dos códigos do orçamento público para linguagem de cidadão."""

FUNCOES = {
    "01": "Legislativa", "02": "Judiciária", "03": "Essencial à Justiça", "04": "Administração",
    "05": "Defesa Nacional", "06": "Segurança Pública", "07": "Relações Exteriores",
    "08": "Assistência Social", "09": "Previdência Social", "10": "Saúde", "11": "Trabalho",
    "12": "Educação", "13": "Cultura", "14": "Direitos da Cidadania", "15": "Urbanismo",
    "16": "Habitação", "17": "Saneamento", "18": "Gestão Ambiental", "19": "Ciência e Tecnologia",
    "20": "Agricultura", "21": "Organização Agrária", "22": "Indústria", "23": "Comércio e Serviços",
    "24": "Comunicações", "25": "Energia", "26": "Transporte", "27": "Desporto e Lazer",
    "28": "Encargos Especiais", "99": "Reserva de Contingência",
}

# Elemento de despesa (posições 5-6 do código de natureza da despesa).
ELEMENTOS = {
    "01": "Aposentadorias", "03": "Pensões", "04": "Contratação por tempo determinado",
    "05": "Outros benefícios previdenciários", "07": "Previdência complementar",
    "08": "Outros benefícios assistenciais", "11": "Salários e vantagens (vencimentos)",
    "12": "Vencimentos de militares", "13": "Encargos patronais (INSS, previdência)",
    "14": "Diárias", "16": "Outras despesas variáveis de pessoal", "18": "Auxílio a estudantes",
    "20": "Auxílio a pesquisadores", "21": "Juros da dívida", "22": "Outros encargos da dívida",
    "30": "Material de consumo", "31": "Premiações", "32": "Material de distribuição gratuita",
    "33": "Passagens e locomoção", "34": "Pessoal terceirizado", "35": "Consultorias",
    "36": "Serviços de pessoa física", "37": "Locação de mão de obra", "38": "Arrendamento mercantil",
    "39": "Serviços de empresas (pessoa jurídica)", "40": "Tecnologia da informação",
    "41": "Contribuições", "42": "Auxílios", "43": "Subvenções sociais", "45": "Subvenções econômicas",
    "46": "Auxílio-alimentação", "47": "Tributos e contribuições", "48": "Auxílio financeiro a pessoas",
    "49": "Auxílio-transporte", "51": "Obras e instalações", "52": "Equipamentos e material permanente",
    "61": "Compra de imóveis", "65": "Participação em empresas", "66": "Empréstimos concedidos",
    "67": "Depósitos compulsórios", "70": "Rateio de consórcios públicos", "71": "Amortização da dívida",
    "81": "Distribuição constitucional", "91": "Sentenças judiciais", "92": "Despesas de anos anteriores",
    "93": "Indenizações e restituições", "94": "Indenizações trabalhistas (rescisões)",
    "95": "Indenização por demissão voluntária", "96": "Ressarcimento de pessoal requisitado",
    "99": "A classificar",
}

# Grandes grupos que o cidadão entende.
GRUPOS_DESPESA = [
    ("pessoal", "Pessoal e encargos"),
    ("diarias", "Diárias e passagens"),
    ("servicos", "Serviços contratados"),
    ("material", "Material de consumo"),
    ("obras", "Obras e equipamentos"),
    ("divida", "Dívida"),
    ("repasses", "Repasses, auxílios e subvenções"),
    ("outros", "Outras despesas"),
]


def nome_elemento(el6: str) -> str:
    return ELEMENTOS.get(el6[4:6], f"Elemento {el6[4:6]}")


def intra(el6: str) -> bool:
    """Modalidade 91: o município pagando a si mesmo (ex.: contribuição ao próprio
    instituto de previdência). Fica fora do total do município para não contar duas vezes."""
    return el6[2:4] == "91"


def grupo_despesa(el6: str) -> str:
    cat, grp, el = el6[:1], el6[1:2], el6[4:6]
    if grp == "1":
        return "pessoal"
    if el in ("14", "33"):
        return "diarias"
    if grp in ("2",) or el in ("21", "22", "71"):
        return "divida"
    if el in ("34", "35", "36", "37", "39", "40"):
        return "servicos"
    if el in ("30", "32"):
        return "material"
    if cat == "4" or el in ("51", "52", "61"):
        return "obras"
    if el in ("41", "42", "43", "45", "48", "70", "81", "18", "20", "31"):
        return "repasses"
    return "outros"


# ----------------------------------------------------------------------- receitas
GRUPOS_RECEITA = [
    ("propria", "Arrecadação própria (impostos, taxas e contribuições)"),
    ("uniao", "Transferências da União"),
    ("estado", "Transferências do Estado"),
    ("fundeb", "FUNDEB"),
    ("outras_transf", "Outras transferências e convênios"),
    ("credito", "Empréstimos e venda de bens"),
    ("outras", "Outras receitas"),
    ("deducoes", "Deduções (parcela retida para o FUNDEB)"),
]


def grupo_receita(rubrica: str, ano: int) -> str | None:
    """Classifica a rubrica pela origem do dinheiro. None = intraorçamentária (fica de fora).

    Até 2017 vale o ementário antigo (1.7.2.1 União, 1.7.2.2 Estado, 1.7.2.4 FUNDEB);
    de 2018 em diante, o novo (1.7.1 União, 1.7.2 Estado, 1.7.5 FUNDEB).
    """
    r = (rubrica or "").strip()
    if not r:
        return "outras"
    if r[0] == "9":
        return "deducoes"
    if r[0] in ("7", "8"):
        return None
    if r[0] == "1":
        if r[1] in ("1", "2"):
            return "propria"
        if r[1] == "7":
            if ano <= 2017:
                if r[2] == "2":
                    return {"1": "uniao", "2": "estado", "4": "fundeb"}.get(r[3], "outras_transf")
                if r[2] == "6":   # convênios (1.7.6.1 União, 1.7.6.2 Estado)
                    return {"1": "uniao", "2": "estado"}.get(r[3], "outras_transf")
                return "outras_transf"
            return {"1": "uniao", "2": "estado", "5": "fundeb"}.get(r[2], "outras_transf")
        return "outras"
    if r[0] == "2":
        if r[1] == "4":
            if ano <= 2017:
                if r[2] == "2":
                    return {"1": "uniao", "2": "estado"}.get(r[3], "outras_transf")
                if r[2] == "7":
                    return {"1": "uniao", "2": "estado"}.get(r[3], "outras_transf")
                return "outras_transf"
            return {"1": "uniao", "2": "estado"}.get(r[2], "outras_transf")
        if r[1] in ("1", "2"):
            return "credito"
        return "outras"
    return "outras"
