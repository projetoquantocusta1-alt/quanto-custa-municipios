"""Configuração do Projeto Quanto Custa — Municípios do Ceará (prefeitos e vereadores)."""

ANO_INICIAL = 2017            # primeiro exercício coletado
UF = "CE"

USER_AGENT = "ProjetoQuantoCusta/1.0 (painel de transparencia com dados abertos)"
PAUSA_ENTRE_REQUISICOES = 0.15   # segundos entre chamadas ao mesmo site
TRABALHADORES_TCE = 4            # consultas simultâneas ao TCE (educado: poucas)

# --- TCE-CE: API de Dados Abertos do SIM (Sistema de Informações Municipais) ---
# Pegadinhas da API (todas tratadas em coletor/tce.py):
#  - exercicio_orcamento é AAAA00 (2025 -> 202500); mandar 2025 devolve lista vazia sem erro;
#  - data_referencia_doc é AAAAMM;
#  - no máximo 1000 registros por página ($count / $start_index);
#  - os códigos de município são os do TCE, não os do IBGE (tabela em municipios_ce.csv).
TCE_API = "https://api-dados-abertos.tce.ce.gov.br/sim"
TCE_PAGINA = 1000

# Tempo máximo de uma execução do robô (o GitHub Actions corta em 6 h).
ORCAMENTO_MINUTOS = 300

# --- TSE: candidatos e bens (eleições municipais) ---
ELEICOES_MUNICIPAIS = [2016, 2020, 2024]
MANDATO_DA_ELEICAO = {2016: (2017, 2020), 2020: (2021, 2024), 2024: (2025, 2028), 2028: (2029, 2032)}
TSE_CAND_ZIP = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip"
TSE_BENS_ZIP = "https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_{ano}.zip"

# --- Emendas parlamentares (CGU / Portal da Transparência) ---
EMENDAS_ZIP = "https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares/UNICO"

# --- IBGE: população estimada (tabela 6579) e Censo 2022 (tabela 4714) ---
IBGE_ESTIMATIVA = ("https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/all/"
                   "variaveis/9324?localidades=N6[N3[23]]")
IBGE_CENSO_2022 = ("https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/"
                   "variaveis/93?localidades=N6[N3[23]]")
# Plano B (outro servidor do IBGE), mesmas tabelas: municípios do CE (n3/23)
SIDRA_ESTIMATIVA = "https://apisidra.ibge.gov.br/values/t/6579/n6/in%20n3%2023/v/9324/p/all"
SIDRA_CENSO_2022 = "https://apisidra.ibge.gov.br/values/t/4714/n6/in%20n3%2023/v/93/p/2022"

# --- IPCA (Banco Central, série 433) ---
IPCA_SGS = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados"
            "?formato=json&dataInicial=01/01/{ano}")

# --- Teto do subsídio do vereador (Constituição, art. 29, VI) ---
# Percentual do subsídio do deputado estadual, conforme a população do município.
TETO_VEREADOR_FAIXAS = [(10_000, 0.20), (50_000, 0.30), (100_000, 0.40),
                        (300_000, 0.50), (500_000, 0.60), (float("inf"), 0.75)]
# Subsídio do deputado estadual = 75% do deputado federal (art. 27, §2º).
# Deputado federal: Decreto Legislativo 172/2022 — ((ano, mês em que passa a valer), valor).
SUBSIDIO_DEP_FEDERAL = [((2015, 2), 33763.00), ((2023, 1), 39293.32), ((2023, 4), 41650.92),
                        ((2024, 2), 44008.52), ((2025, 2), 46366.19)]
