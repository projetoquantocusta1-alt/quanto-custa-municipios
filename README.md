# Projeto Quanto Custa — Prefeitos e vereadores do Ceará

Quanto custam as câmaras municipais, os gabinetes dos prefeitos e as prefeituras dos
184 municípios do Ceará, desde 2017. Site estático em `docs/` (GitHub Pages), atualizado
por robôs no GitHub Actions. É o primeiro repositório-satélite do Projeto Quanto Custa
(o site dos deputados federais é o outro).

## Fontes

| Dado | Fonte | Robô |
|---|---|---|
| Balancetes de despesa e receita, notas de empenho e anulações | TCE-CE — API de Dados Abertos do SIM (`api-dados-abertos.tce.ce.gov.br/sim`) | `atualizar.py` (diário) |
| Prefeitos, vices e vereadores eleitos (2016, 2020, 2024) e bens declarados | TSE — dados abertos | `semanal.py` |
| População por ano | IBGE (tabelas 6579 e 4714) | `semanal.py` |
| Emendas parlamentares por município de destino | CGU — Portal da Transparência | `semanal.py` |
| IPCA | Banco Central (SGS 433) | `atualizar.py` |

## Como medimos

- **Gasto = despesa empenhada líquida** (empenhado − anulações), a despesa realizada pela
  Lei 4.320/64. É o que todos os municípios informam ao TCE do mesmo jeito.
- Para cada órgão (câmara, gabinete do prefeito, gabinete do vice), o robô confere se as
  notas de empenho menos as anulações batem com o balancete. O resultado fica em `conferencia`.
- O total da prefeitura não inclui a modalidade 91 (intraorçamentária), para não contar duas vezes.
- Receita por origem segue o ementário de cada ano (até 2017 o antigo; de 2018 em diante o novo).
- O salário individual de prefeito e vereador **não** está nos dados abertos do TCE (a folha
  chega em lote). O site mostra o teto constitucional do vereador (art. 29, VI).
- CPF nunca é guardado (o TCE já o publica cifrado). Telefone e endereço também não.

## Primeira carga

São 184 municípios × 10 exercícios. O robô diário anda numa fila com limite de tempo
(5 h por execução) e continua de onde parou: ano atual primeiro, depois o passado, depois
os mais antigos. Em poucos dias o histórico fica completo; depois disso, cada execução só
refaz o ano corrente (os dois últimos meses enviados, que é onde os municípios corrigem).

## Rodar localmente

```bash
pip install -r requirements.txt
python -m pytest -q
python semanal.py                       # eleitos, população, emendas
python atualizar.py --municipios 162 --anos 2025 --minutos 30
python atualizar.py --so-montar         # só remonta os arquivos do site
```

## Arquivos do site (`docs/dados`)

- `meta.json` — data, anos, cobertura por ano, fatores do IPCA, mandatos.
- `resumo.json` — uma linha por município e ano (rankings).
- `m/CCC.json` — ficha completa do município (código do TCE).

`municipios_ce.csv` liga os códigos do TCE, do IBGE e do TSE.

## Versão 3 — nota a nota
- O robô agora guarda cada mês num arquivo separado (`dados_brutos/tce/AAAA/CCC/AAAAMM.json`) e só regrava um arquivo quando o conteúdo muda, para o repositório não crescer à toa.
- Câmara e gabinetes: notas de empenho com histórico completo, processo de contratação, contrato, notas de pagamento, notas fiscais (chave da NF-e, CNPJ do emitente) e itens.
- Prefeitura inteira: todas as notas de empenho de todos os órgãos, agrupadas por quem recebeu (`docs/dados/f/`).
- Arquivos da versão 1 continuam aparecendo no site até o robô refazer cada município-ano.
