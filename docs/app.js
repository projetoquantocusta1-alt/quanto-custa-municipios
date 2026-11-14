/* Projeto Quanto Custa — Prefeitos e vereadores do Ceará */
(() => {
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const E = { ano: null, ipca: true, pag: "inicio", sim: null, meta: null, res: null, campos: {}, det: {}, graf: {},
  limP: 20, limC: 20, limF: 20, ordP: ["gab", -1], ordC: ["porVer", -1] };

const NOMES_GRUPO = { pessoal: "Pessoal e encargos", diarias: "Diárias e passagens", servicos: "Serviços contratados",
  material: "Material de consumo", obras: "Obras e equipamentos", divida: "Dívida", repasses: "Repasses e auxílios", outros: "Outras" };
const NOMES_REC = { propria: "Arrecadação própria", uniao: "União", estado: "Estado", fundeb: "FUNDEB",
  outras_transf: "Outras transferências", credito: "Empréstimos e vendas", outras: "Outras receitas", deducoes: "Deduções p/ FUNDEB" };
const FUNCOES = { "01": "Legislativa", "02": "Judiciária", "03": "Essencial à Justiça", "04": "Administração", "06": "Segurança",
  "08": "Assistência social", "09": "Previdência", "10": "Saúde", "11": "Trabalho", "12": "Educação", "13": "Cultura",
  "14": "Direitos da cidadania", "15": "Urbanismo", "16": "Habitação", "17": "Saneamento", "18": "Meio ambiente",
  "19": "Ciência e tecnologia", "20": "Agricultura", "22": "Indústria", "23": "Comércio e serviços", "24": "Comunicações",
  "25": "Energia", "26": "Transporte", "27": "Esporte e lazer", "28": "Encargos especiais (dívida, repasses)", "99": "Reserva" };
const ELEM = { "11": "Salários", "13": "Encargos patronais", "14": "Diárias", "16": "Outras de pessoal", "30": "Material de consumo",
  "33": "Passagens", "35": "Consultoria", "36": "Serviços pessoa física", "37": "Locação de mão de obra", "39": "Serviços de empresas",
  "40": "Tecnologia", "46": "Auxílio-alimentação", "52": "Equipamentos", "93": "Indenizações", "94": "Rescisões", "04": "Contrato temporário" };

/* --------------------------------------------------------------- utilidades */
const brl = (v, c = 0) => v == null || isNaN(v) ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: c, maximumFractionDigits: c });
const curto = v => {
  if (v == null || isNaN(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return "R$ " + (v / 1e9).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " bi";
  if (a >= 1e6) return "R$ " + (v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mi";
  if (a >= 1e3) return "R$ " + (v / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 0 }) + " mil";
  return brl(v);
};
const num = v => v == null ? "—" : v.toLocaleString("pt-BR");
const pct = v => v == null || !isFinite(v) ? "—" : (v * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const semAcento = s => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const MIN = new Set(["de", "da", "do", "das", "dos", "e"]);
const titulo = s => (s || "").toLowerCase().split(" ").map((p, i) => i && MIN.has(p) ? p : p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
const fator = ano => E.ipca ? ((E.meta.ipca.fatores || {})[ano] || 1) : 1;
const v = (x, ano) => x == null ? null : x * fator(ano ?? E.ano);
async function json(url) { const r = await fetch(url, { cache: "no-cache" }); if (!r.ok) throw new Error(url + " " + r.status); return r.json(); }
const mesRef = r => r ? `${["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"][r % 100 - 1]}/${Math.floor(r / 100)}` : "";

/* linha do resumo de um município no ano escolhido */
function linha(m, ano = E.ano) {
  const l = m.anos[ano];
  if (!l) return null;
  const o = {}; E.meta._campos.forEach((c, i) => o[c] = l[i]);
  const f = fator(ano);
  for (const k of ["gasto_total", "camara", "gab_prefeito", "gab_vice", "receita_total", "transf_uniao", "transf_estado",
    "receita_propria", "emendas", "camara_pessoal", "camara_diarias"]) o[k] = o[k] == null ? null : o[k] * f;
  o.gab = (o.gab_prefeito || 0) + (o.gab_vice || 0);
  o.porVer = o.n_vereadores ? o.camara / o.n_vereadores : null;
  o.camHab = o.populacao ? o.camara / o.populacao : null;
  o.gastoHab = o.populacao ? o.gasto_total / o.populacao : null;
  o.dep = o.receita_total ? ((o.transf_uniao || 0) + (o.transf_estado || 0)) / o.receita_total : null;
  o.camRec = o.receita_total ? o.camara / o.receita_total : null;
  return o;
}
function prefeitoDoAno(m, ano = E.ano) {
  for (const [el, [i, f]] of Object.entries(E.meta.mandatos || {})) if (ano >= i && ano <= f) return (m.prefeitos || {})[el] || null;
  return null;
}

/* --------------------------------------------------------------- navegação */
function irPara(pag) {
  E.pag = pag;
  $$(".pagina").forEach(p => p.classList.toggle("ativa", p.dataset.pag === pag));
  $$(".menu nav button").forEach(b => b.dataset.pag === pag ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current"));
  fecharMenu();
  history.replaceState(null, "", `#${pag}${E.sim ? "/" + E.sim : ""}`);
  render();
  window.scrollTo(0, 0);
}
function fecharMenu() { $("#menu").classList.remove("aberto"); $("#veu").hidden = true; $("#abrir-menu").setAttribute("aria-expanded", "false"); }
function abrirMunicipio(sim) {
  E.sim = sim;
  const m = E.res.find(x => x.sim === sim);
  $("#f-mun").value = m ? titulo(m.nome) : "";
  irPara("municipio");
}

/* --------------------------------------------------------------- render */
function render() {
  if (!E.res) return;
  ({ inicio: rInicio, prefeitos: rPrefeitos, camaras: rCamaras, municipio: rMunicipio, metodo: () => {} })[E.pag]();
}

function kpis(el, itens) {
  $(el).innerHTML = itens.map(([rot, val, obs]) => `<div class="kpi"><div class="rot">${rot}</div><div class="val num">${val}</div>${obs ? `<div class="obs">${obs}</div>` : ""}</div>`).join("");
}
function top5(el, lista, fmt, sub) {
  $(el).innerHTML = lista.slice(0, 5).map(([m, val, l]) => `<li><span><button class="link-dep" data-sim="${m.sim}">${esc(titulo(m.nome))}</button><span class="s">${sub(m, l)}</span></span><span class="v">${fmt(val)}</span></li>`).join("")
    || `<li class="vazio">Sem dados para ${E.ano} ainda.</li>`;
}
function linhasDoAno() { return E.res.map(m => [m, linha(m)]).filter(([, l]) => l); }

function rInicio() {
  const L = linhasDoAno();
  const soma = k => L.reduce((s, [, l]) => s + (l[k] || 0), 0);
  const nVer = soma("n_vereadores");
  kpis("#i-kpis", [
    ["Gasto das câmaras", curto(soma("camara")), `${L.length} municípios com dados em ${E.ano}`],
    ["Custo médio por vereador", curto(nVer ? soma("camara") / nVer : null), `${num(nVer)} vereadores eleitos`],
    ["Gabinetes de prefeitos e vices", curto(soma("gab")), "soma dos dois gabinetes"],
    ["Gasto das prefeituras", curto(soma("gasto_total")), "tudo o que os municípios gastaram"],
  ]);
  const ord = k => L.filter(([, l]) => l[k] != null).map(([m, l]) => [m, l[k], l]).sort((a, b) => b[1] - a[1]);
  top5("#i-top-hab", ord("camHab"), x => brl(x, 2) + "/hab", (m, l) => `${curto(l.camara)} · ${num(l.populacao)} hab.`);
  top5("#i-top-ver", ord("porVer"), curto, (m, l) => `${l.n_vereadores} vereadores · ${curto(l.camara)}`);
  top5("#i-top-gab", ord("gab"), curto, (m) => { const p = prefeitoDoAno(m); return p ? `${esc(titulo(p[0]))} (${esc(p[1])})` : ""; });
  top5("#i-top-dep", ord("dep"), pct, (m, l) => `receita de ${curto(l.receita_total)}`);
}

function tabela(el, cols, linhas, ord, setOrd, lim, maisEl, total) {
  const [k, d] = ord;
  linhas.sort((a, b) => ((a[k] ?? -Infinity) > (b[k] ?? -Infinity) ? 1 : -1) * d);
  const head = `<thead><tr>${cols.map(c => `<th class="${c.num ? "num" : ""}" data-k="${c.k}" ${c.k === k ? `aria-sort="${d < 0 ? "descending" : "ascending"}"` : ""} style="cursor:pointer">${c.t}</th>`).join("")}</tr></thead>`;
  const body = linhas.slice(0, lim).map(l => `<tr>${cols.map(c => `<td class="${c.num ? "num" : ""}${c.q ? " quebra" : ""}">${c.f(l)}</td>`).join("")}</tr>`).join("");
  const foot = total ? `<tfoot><tr>${cols.map(c => `<td class="${c.num ? "num" : ""}">${total(c, linhas) ?? ""}</td>`).join("")}</tr></tfoot>` : "";
  $(el).innerHTML = head + `<tbody>${body || `<tr><td colspan="${cols.length}" class="vazio">Nada encontrado.</td></tr>`}</tbody>` + foot;
  $$("th", $(el)).forEach(th => th.onclick = () => { setOrd([th.dataset.k, th.dataset.k === k ? -d : -1]); });
  if (maisEl) $(maisEl).hidden = linhas.length <= lim;
}
const linkMun = l => `<button class="link-dep" data-sim="${l.m.sim}">${esc(titulo(l.m.nome))}</button>`;

function rPrefeitos() {
  const q = semAcento($("#p-busca").value);
  const L = linhasDoAno().map(([m, l]) => ({ ...l, m, nome: m.nome, pref: prefeitoDoAno(m) }))
    .filter(l => !q || semAcento(`${l.nome} ${l.pref?.join(" ")}`).includes(q));
  const soma = k => L.reduce((s, l) => s + (l[k] || 0), 0);
  kpis("#p-kpis", [["Gabinetes (prefeito + vice)", curto(soma("gab")), `${L.length} municípios`],
    ["Gasto das prefeituras", curto(soma("gasto_total"))], ["Gasto por habitante (média)", brl(soma("gasto_total") / (soma("populacao") || NaN), 0)],
    ["Emendas recebidas", curto(soma("emendas")), "empenhado no ano"]]);
  tabela("#p-tab", [
    { k: "nome", t: "Município", f: linkMun },
    { k: "pref", t: "Prefeito(a)", f: l => l.pref ? `${esc(titulo(l.pref[0]))} <span class="sub">${esc(l.pref[1])}</span>` : "—" },
    { k: "gab_prefeito", t: "Gabinete prefeito", num: 1, f: l => curto(l.gab_prefeito) },
    { k: "gab_vice", t: "Gabinete vice", num: 1, f: l => curto(l.gab_vice) },
    { k: "gasto_total", t: "Gasto da prefeitura", num: 1, f: l => curto(l.gasto_total) },
    { k: "gastoHab", t: "Por habitante", num: 1, f: l => brl(l.gastoHab) },
    { k: "dep", t: "Depende de fora", num: 1, f: l => pct(l.dep) },
  ], L, E.ordP, o => { E.ordP = o; rPrefeitos(); }, E.limP, "#p-mais",
  (c, ls) => c.k === "nome" ? "Total" : ["gab_prefeito", "gab_vice", "gasto_total"].includes(c.k) ? curto(ls.reduce((s, l) => s + (l[c.k] || 0), 0)) : "");
}


/* divergências: o que o órgão não enviou ao TCE-CE ou o que não fecha (vem pronto do robô; se não vier, calcula aqui) */
const ROT_ORG = { camara: "Câmara Municipal", prefeito: "Gabinete do Prefeito", vice: "Gabinete do Vice-Prefeito" };
function divergenciasDe(a, ano) {
  if (a.divergencias) return a.divergencias;
  const out = [], mes = a.mes_ref ? `${String(a.mes_ref).slice(4, 6)}/${String(a.mes_ref).slice(0, 4)}` : ano;
  Object.entries(a.conferencia || {}).forEach(([p, c]) => {
    const semBal = (a.orgaos?.[p]?.fonte_gasto || "balancete") !== "balancete";
    if (semBal) out.push({ orgao: p, tipo: "sem_balancete", texto: `${ROT_ORG[p]}: o balancete de despesa de ${ano} não foi enviado ao TCE-CE (dados disponíveis até ${mes}). O valor mostrado (${brl(c.notas, 2)}) é a soma das notas de empenho, menos anulações, que o próprio órgão registrou no TCE. Enviar o balancete é obrigação do órgão; quando ele chegar, o valor é conferido de novo.` });
    else if (!c.ok) out.push({ orgao: p, tipo: "diferenca", texto: `${ROT_ORG[p]}: as notas de empenho registradas no TCE-CE somam ${brl(c.notas, 2)}, mas o balancete do próprio órgão informa ${brl(c.balancete, 2)} (diferença de ${brl(c.diferenca, 2)}). Mostramos o valor do balancete, que é a despesa oficial; a diferença precisa ser explicada pelo órgão.` });
  });
  return out;
}
// situação da câmara para a lista: do resumo (robô novo) ou do arquivo do município (busca só os que não conferem)
E.sitCam = {};
function situacaoCamara(m, l) {
  if (l.situacao_camara) return { s: l.situacao_camara, d: l.diferenca_camara };
  if (l.conferido !== 0) return { s: l.conferido ? "ok" : null };
  const k = m.sim + "-" + E.ano;
  if (k in E.sitCam) return E.sitCam[k];
  E.sitCam[k] = { s: null };
  (E.det[m.sim] ? Promise.resolve(E.det[m.sim]) : jsonOuNada(`dados/m/${m.sim}.json`)).then((D) => {
    if (!D) return; E.det[m.sim] = D;
    const a = D.anos[E.ano], c = a?.conferencia?.camara;
    if (!c) return;
    E.sitCam[k] = (a.orgaos.camara.fonte_gasto || "balancete") !== "balancete" ? { s: "sem_balancete", d: c.diferenca } : c.ok ? { s: "ok" } : { s: "diferenca", d: c.diferenca };
    clearTimeout(E._rc); E._rc = setTimeout(() => { if (E.pag === "camaras") rCamaras(); }, 150);
  });
  return E.sitCam[k];
}

function rCamaras() {
  const q = semAcento($("#c-busca").value);
  const L = linhasDoAno().map(([m, l]) => ({ ...l, m, nome: m.nome })).filter(l => !q || semAcento(l.nome).includes(q));
  const soma = k => L.reduce((s, l) => s + (l[k] || 0), 0);
  const sits = linhasDoAno().map(([m, l]) => [m, situacaoCamara(m, l)]);
  const semBal = sits.filter(([, x]) => x.s === "sem_balancete").map(([m]) => titulo(m.nome));
  const difs = sits.filter(([, x]) => x.s === "diferenca").map(([m, x]) => `${titulo(m.nome)} (${brl(x.d)})`);
  $("#c-diverg").hidden = !(semBal.length || difs.length);
  $("#c-diverg").innerHTML = `<strong>Atenção: informações que as câmaras não enviaram ou que não fecham no TCE-CE (${E.ano})</strong><ul>${
    semBal.length ? `<li class="sem_balancete"><b>Sem balancete de despesa enviado ao TCE-CE:</b> ${esc(semBal.join(", "))}. Para essas câmaras, o gasto mostrado é a soma das notas de empenho que elas mesmas registraram. Enviar o balancete é obrigação de cada câmara.</li>` : ""}${
    difs.length ? `<li class="diferenca"><b>Notas de empenho e balancete não batem:</b> ${esc(difs.join(", "))}. Mostramos o valor do balancete (a despesa oficial); a diferença precisa ser explicada pela câmara.</li>` : ""}</ul>`;
  kpis("#c-kpis", [["Gasto das câmaras", curto(soma("camara")), `${L.length} câmaras`],
    ["Vereadores eleitos", num(soma("n_vereadores"))], ["Custo médio por vereador", curto(soma("camara") / (soma("n_vereadores") || NaN))],
    ["Diárias e passagens", curto(soma("camara_diarias"))]]);
  tabela("#c-tab", [
    { k: "nome", t: "Município", f: linkMun },
    { k: "camara", t: "Gasto da câmara", num: 1, f: l => curto(l.camara) },
    { k: "n_vereadores", t: "Vereadores", num: 1, f: l => num(l.n_vereadores) },
    { k: "porVer", t: "Por vereador (ano)", num: 1, f: l => curto(l.porVer) },
    { k: "camHab", t: "Por habitante", num: 1, f: l => brl(l.camHab, 2) },
    { k: "camRec", t: "% da receita", num: 1, f: l => pct(l.camRec) },
    { k: "teto_subsidio_vereador", t: "Teto do salário", num: 1, f: l => brl(l.teto_subsidio_vereador) },
    { k: "conferido", t: "Conferido", f: l => { const x = situacaoCamara(l.m, l);
        return x.s === "sem_balancete" ? '<span class="selo-conf alerta" title="A câmara não enviou o balancete do ano ao TCE-CE; valor pela soma das notas de empenho">sem balancete</span>'
          : x.s === "diferenca" ? `<span class="selo-conf nao" title="Notas de empenho e balancete não batem">diferença de ${brl(x.d)}</span>`
          : l.conferido ? '<span class="selo-conf ok">sim</span>' : l.conferido === 0 ? '<span class="selo-conf nao">diferença</span>' : "—"; } },
  ], L, E.ordC, o => { E.ordC = o; rCamaras(); }, E.limC, "#c-mais",
  (c, ls) => c.k === "nome" ? "Total" : c.k === "camara" ? curto(ls.reduce((s, l) => s + (l.camara || 0), 0)) : c.k === "n_vereadores" ? num(ls.reduce((s, l) => s + (l.n_vereadores || 0), 0)) : "");
}

/* --------------------------------------------------------------- município */
function grafico(id, cfg) { E.graf[id]?.destroy(); E.graf[id] = new Chart($("#" + id), cfg); }
const opBarra = (horiz) => ({ responsive: true, maintainAspectRatio: false, indexAxis: horiz ? "y" : "x", plugins: { legend: { display: false },
  tooltip: { callbacks: { label: c => brl(c.raw) } } }, scales: { [horiz ? "x" : "y"]: { ticks: { callback: x => curto(x) } } } });

async function rMunicipio() {
  if (!E.sim) { $("#m-vazio").hidden = false; $("#m-conteudo").hidden = true; return; }
  $("#m-vazio").hidden = true; $("#m-conteudo").hidden = false;
  const D = E.det[E.sim] || (E.det[E.sim] = await json(`dados/m/${E.sim}.json`));
  const a = D.anos[E.ano];
  $("#m-titulo").textContent = titulo(D.nome);
  if (!a) { $("#m-sub").textContent = `Sem dados de ${E.ano} no TCE ainda.`; $("#m-kpis").innerHTML = ""; E.extrasChave = null; E.N = E.PF = null; rNotas(); rPF(); return; }
  const f = fator(E.ano), x = y => y == null ? null : y * f;
  const cam = a.orgaos.camara, pre = a.orgaos.prefeito, vic = a.orgaos.vice;
  $("#m-sub").textContent = `${num(a.populacao)} habitantes · dados até ${mesRef(a.mes_ref)}${a.fechado ? "" : " (ano em andamento)"}`;
  const dv = divergenciasDe(a, E.ano);
  $("#m-diverg").hidden = !dv.length;
  $("#m-diverg").innerHTML = dv.length ? `<strong>Atenção: dados incompletos ou divergentes no TCE-CE (${E.ano})</strong><ul>${dv.map(d => `<li class="${d.tipo}">${esc(d.texto)}</li>`).join("")}</ul>
    <p class="sub">Os números deste site vêm do que cada prefeitura e câmara informa ao Tribunal de Contas. Quando a informação falta ou não fecha, avisamos aqui.</p>` : "";
  kpis("#m-kpis", [
    ["Câmara municipal", curto(x(cam.gasto)), a.n_vereadores ? `${a.n_vereadores} vereadores · ${curto(x(a.camara_por_vereador))} por vereador` : ""],
    ["Gabinete do prefeito + vice", curto(x(pre.gasto + vic.gasto))],
    ["Gasto total da prefeitura", curto(x(a.gasto_total)), a.populacao ? brl(x(a.gasto_total) / a.populacao) + " por habitante" : ""],
    ["Receita do ano", curto(x(a.receita_total)), `emendas: ${curto(x(a.emendas_total))}`],
    ["Teto do salário do vereador", brl(a.teto_subsidio_vereador), "por mês, pela Constituição"],
  ]);
  let bc = $("#m-card");
  if (!bc) { bc = document.createElement("p"); bc.className = "sub"; bc.innerHTML = '<button class="btn" id="m-card" type="button">Gerar imagem para compartilhar</button>'; $("#m-kpis").after(bc); bc = $("#m-card"); }
  bc.onclick = () => {
    const L = linhasDoAno().filter(([, l]) => l.porVer), ord = L.slice().sort((p, q) => q[1].porVer - p[1].porVer), n = ord.length;
    const pos = ord.findIndex(([m]) => m.sim === E.sim) + 1, caro = pos && pos <= Math.ceil(n / 2);
    const dvs = divergenciasDe(a, E.ano), dvC = dvs.find((d) => d.orgao === "camara");
    const destaques = [];
    if (dvC) destaques.push([dvC.tipo === "sem_balancete" ? "Atenção: a câmara não enviou o balancete ao TCE-CE" : "Atenção: notas e balancete da câmara não batem",
      dvC.tipo === "sem_balancete" ? "valor pela soma das notas de empenho que a própria câmara registrou" : `diferença de ${brl(a.conferencia.camara.diferenca)}`, "#c4161c"]);
    if (a.n_vereadores) destaques.push([`${curto(x(a.camara_por_vereador))} por vereador no ano`, `câmara inteira ÷ ${a.n_vereadores} vereadores eleitos`, "#118dff"]);
    destaques.push([`Gabinete do prefeito e do vice: ${curto(x(pre.gasto + vic.gasto))}`, "órgão inteiro da prefeitura, não é o salário do prefeito", "#107c41"]);
    const pes = x(cam.grupos?.pessoal || 0), dia = x(cam.grupos?.diarias || 0), out = Math.max(0, x(cam.gasto) - pes - dia);
    CartaoQC.abrir({
      titulo: `Câmara Municipal · ${E.ano}${a.fechado ? "" : " (até " + mesRef(a.mes_ref) + ")"}`,
      nome: titulo(D.nome), semFoto: true,
      linhas: [`${num(a.populacao)} habitantes · Ceará`, a.n_vereadores ? `${a.n_vereadores} vereadores` : ""],
      faixa: pos ? { titulo: pos === 1 ? "Câmara mais cara por vereador" : caro ? `${pos}ª mais cara por vereador` : `${n - pos + 1}ª mais econômica por vereador`, sub: `entre ${n} câmaras do Ceará · em ${E.ano}`, cor: caro ? "#c4161c" : "#107c41" } : null,
      valorRot: "A câmara custou aos cofres públicos", valor: x(cam.gasto), valorSub: a.populacao ? `${brl(x(cam.gasto) / a.populacao, 2)} por habitante` : "",
      destaques,
      composicao: pes || dia ? [["Pessoal", pes, "#14283F"], ["Diárias e passagens", dia, "#D69A32"], ["Outras despesas", out, "#2475B8"]] : [],
      fonte: `Fonte: TCE-CE (dados abertos do SIM)${$("#f-ipca").checked ? " · valores corrigidos pelo IPCA" : ""}`,
      arquivo: `camara-${semAcento(D.nome).replace(/\W+/g, "-")}-${E.ano}`,
    });
  };
  // prefeito e vice
  const md = D.mandatos[a.eleicao];
  $("#m-mandato").textContent = md ? `mandato ${md.periodo[0]}–${md.periodo[1]}` : "";
  const pessoa = (p, cargo, extra) => p ? `<div class="pessoa"><span class="ini">${esc((p.urna || p.nome)[0])}</span><div><strong>${esc(titulo(p.urna || p.nome))} <span class="sub">${esc(p.partido)}</span></strong>
    <span class="sub">${cargo} · ${esc(titulo(p.nome))}${p.bens != null ? ` · bens declarados: ${brl(p.bens)}` : ""}</span>${extra || ""}</div></div>` : "";
  const extraP = k => { const pe = a.pessoas[k]; return pe ? `<div class="det">Recebeu diretamente da prefeitura (gabinete): ${brl(x(pe.direto), 2)} em ${pe.notas} nota(s)</div>` : ""; };
  $("#m-pref").innerHTML = md ? pessoa(md.prefeito, "Prefeito(a)", extraP("prefeito")) + pessoa(md.vice, "Vice", extraP("vice")) +
    `<div class="det">Gabinete do prefeito: ${curto(x(pre.gasto))} · gabinete do vice: ${curto(x(vic.gasto))}. O TCE não publica o salário individual.</div>`
    : `<p class="sub">Eleitos ainda não carregados.</p>`;
  // câmara
  const conf = a.conferencia.camara;
  $("#m-conf-cam").className = "selo-conf " + (conf?.ok ? "ok" : "nao");
  $("#m-conf-cam").textContent = cam.fonte_gasto && cam.fonte_gasto !== "balancete" ? "soma das notas de empenho: a câmara ainda não enviou o balancete do ano ao TCE"
    : conf ? (conf.ok ? "notas conferidas com o balancete" : `diferença de ${brl(conf.diferenca)} entre notas e balancete`) : "";
  const g = Object.entries(cam.grupos).sort((p, q) => q[1] - p[1]);
  const semGrupos = !g.length && cam.gasto > 0;
  $("#g-camara").parentElement.hidden = semGrupos;
  let gsem = $("#g-camara-sem");
  if (!gsem) { gsem = document.createElement("p"); gsem.id = "g-camara-sem"; gsem.className = "sub"; $("#g-camara").parentElement.after(gsem); }
  gsem.hidden = !semGrupos;
  gsem.textContent = "A divisão do gasto por tipo de despesa vem do balancete, que esta câmara ainda não enviou ao TCE-CE. Veja abaixo cada nota de empenho.";
  grafico("g-camara", { type: "bar", data: { labels: g.map(([k]) => NOMES_GRUPO[k] || k), datasets: [{ data: g.map(([, y]) => x(y)), backgroundColor: "#118dff" }] }, options: opBarra(true) });
  // vereadores
  const vers = (md?.vereadores || []).map((p, i) => ({ p, pe: a.pessoas["v" + i] }));
  tabela("#m-ver", [
    { k: "nome", t: "Vereador(a)", f: l => `<strong>${esc(titulo(l.p.urna || l.p.nome))}</strong> <span class="sub">${esc(l.p.partido)}</span>` },
    { k: "direto", t: "Pago a ele(a)", num: 1, f: l => l.pe ? brl(x(l.pe.direto), 2) : "—" },
    { k: "citado", t: "Notas que citam o gabinete", num: 1, f: l => l.pe ? brl(x(l.pe.citado), 2) : "—" },
    { k: "bens", t: "Bens declarados", num: 1, f: l => brl(l.p.bens) },
    { k: "ex", t: "Exemplo de nota", q: 1, f: l => l.pe?.itens?.length ? `<span class="det">${esc(l.pe.itens[l.pe.itens.length - 1][4])}</span>` : "" },
  ], vers.map(l => ({ ...l, nome: l.p.urna, direto: l.pe?.direto || 0, citado: l.pe?.citado || 0, bens: l.p.bens })),
  ["citado", -1], () => {}, 999, null);
  // fornecedores
  rForn(a, f);
  // função
  const fu = Object.entries(a.por_funcao).filter(([, y]) => y > 0).slice(0, 14);
  grafico("g-funcao", { type: "bar", data: { labels: fu.map(([k]) => FUNCOES[k] || "Função " + k), datasets: [{ data: fu.map(([, y]) => x(y)), backgroundColor: "#12239e" }] }, options: opBarra(true) });
  const re = Object.entries(a.receita).filter(([k, y]) => y > 0);
  grafico("g-receita", { type: "doughnut", data: { labels: re.map(([k]) => NOMES_REC[k] || k), datasets: [{ data: re.map(([, y]) => x(y)),
    backgroundColor: ["#118dff", "#12239e", "#e66c37", "#6b007b", "#e044a7", "#744ec2", "#d9b300", "#1aab40"] }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "right" }, tooltip: { callbacks: { label: c => `${c.label}: ${brl(c.raw)}` } } } } });
  $("#m-emendas").innerHTML = `<thead><tr><th>Autor</th><th>Tipo</th><th class="num">Empenhado</th><th class="num">Pago</th></tr></thead><tbody>` +
    (a.emendas.slice(0, 15).map(e => `<tr><td>${esc(titulo(e[0]))}</td><td class="det">${esc(e[3].join(", "))}</td><td class="num">${brl(x(e[1]))}</td><td class="num">${brl(x(e[2]))}</td></tr>`).join("")
      || `<tr><td colspan="4" class="vazio">Nenhuma emenda com destino à cidade neste ano.</td></tr>`) + "</tbody>";
  // histórico da câmara
  const anos = Object.keys(D.anos).sort();
  grafico("g-hist", { type: "bar", data: { labels: anos, datasets: [
    { label: "Câmara", data: anos.map(y => D.anos[y].orgaos.camara.gasto * fator(y)), backgroundColor: "#118dff" },
    { label: "Gabinetes prefeito + vice", data: anos.map(y => (D.anos[y].orgaos.prefeito.gasto + D.anos[y].orgaos.vice.gasto) * fator(y)), backgroundColor: "#e66c37" }] },
    options: { ...opBarra(false), plugins: { legend: { display: true }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${brl(c.raw)}` } } } } });
  rExtras(D, a);
}

function rForn(a, f) {
  const o = a.orgaos[$("#m-orgao").value];
  const L = o.fornecedores.map(r => ({ nome: r[0], doc: r[1], tipo: r[2], valor: r[3] * f, notas: r[4], el: r[5] }));
  const fmtDoc = d => d ? d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5") : "";
  tabela("#m-forn", [
    { k: "nome", t: "Quem recebeu", q: 1, f: l => `${l.tipo === "FOLHA" ? `<strong>${esc(l.nome)}</strong>` : `<button class="link-forn" type="button" data-filtrar-doc="${esc(l.doc || l.nome)}">${esc(l.nome)}</button>`} <span class="sub">${fmtDoc(l.doc)}</span>` },
    { k: "tipo", t: "Tipo", f: l => ({ PJ: "Empresa", PF: "Pessoa", FOLHA: "Folha" })[l.tipo] || l.tipo },
    { k: "el", t: "Principal gasto", q: 1, f: l => esc(Object.keys(l.el).slice(0, 2).map(k => ELEM[k] || "Elemento " + k).join(", ")) },
    { k: "notas", t: "Notas", num: 1, f: l => num(l.notas) },
    { k: "valor", t: "Valor", num: 1, f: l => brl(l.valor, 2) },
  ], L, ["valor", -1], () => {}, E.limF, "#m-forn-mais",
  (c, ls) => c.k === "nome" ? `Total (${o.n_fornecedores} favorecidos; gasto do órgão: ${brl(o.gasto * f)})` : c.k === "valor" ? brl(ls.reduce((s, l) => s + l.valor, 0), 2) : "");
}

/* --------------------------------------------------------------- nota a nota e prefeitura inteira (v3) */
const ROT_PAPEL = { camara: "Câmara", prefeito: "Gab. prefeito", vice: "Gab. vice" };
const dataBR = d => d ? d.slice(8, 10) + "/" + d.slice(5, 7) + "/" + d.slice(0, 4) : "—";
const fmtCnpj = d => d ? d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5") : "";
const nomeEl = el => { const k = (el || "").slice(4, 6); return ELEM[k] || (k ? "Elemento " + k : "—"); };
const etqTipo = t => t === "PJ" ? '<span class="etq pj">empresa</span>' : t === "PF" ? '<span class="etq pf">pessoa</span>' : t === "FOLHA" ? '<span class="etq">folha</span>' : "";
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
async function jsonOuNada(url) { try { return await json(url); } catch (e) { return null; } }

async function rExtras(D, a) {
  const k = `${E.sim}/${E.ano}`;
  E.ctx = { D, a };
  if (E.extrasChave !== k) {
    E.extrasChave = k; E.N = E.PF = null; E.limN = 30; E.limPF = 30; E.abertas = new Set();
    $("#n-info").textContent = "Carregando as notas…"; $("#n-tab").innerHTML = ""; $("#pf-tab").innerHTML = "";
    const [n, f] = await Promise.all([jsonOuNada(`dados/n/${E.sim}/${E.ano}.json`), jsonOuNada(`dados/f/${E.sim}/${E.ano}.json`)]);
    if (E.extrasChave !== k) return;
    E.N = n; E.PF = f;
    if (n) {
      const meses = [...new Set(n.emp.map(e => e[20]))].sort((x, y) => x - y);
      $("#n-mes").innerHTML = `<option value="">Ano inteiro</option>` + meses.map(m => `<option value="${m}">${MESES[m - 1]}/${E.ano}</option>`).join("");
      const els = {}; n.emp.forEach(e => { const nm = nomeEl(e[3]); els[nm] = (els[nm] || 0) + e[5] - e[6]; });
      $("#n-el").innerHTML = `<option value="">Todos os tipos de gasto</option>` + Object.entries(els).sort((p, q) => q[1] - p[1]).map(([nm]) => `<option>${esc(nm)}</option>`).join("");
      n._busca = n.emp.map(e => { const f = n.forn[e[4]]; return semAcento([f[0], f[1], fmtCnpj(f[1]), e[2], e[8], e[10], e[11], ...e[17].map(x => x[0] + " " + x[7]), ...e[19].map(i => i[2])].join(" ")); });
    }
    if (f) {
      const usados = new Set(f.linhas.flatMap(l => Object.keys(l[6])));
      $("#pf-orgao").innerHTML = `<option value="">Todos os órgãos</option>` + Object.entries(f.orgaos).filter(([c]) => usados.has(c))
        .map(([c, nm]) => `<option value="${c}">${esc(titulo(nm))}</option>`).join("");
    }
  }
  rNotas(); rPF();
}

function notasFiltradas() {
  const n = E.N, q = semAcento($("#n-q").value.trim()), org = $("#n-orgao").value, mes = +$("#n-mes").value || 0,
    el = $("#n-el").value, soNf = $("#n-nf").checked;
  const L = [];
  n.emp.forEach((e, i) => {
    if (org && n.orgaos[e[0]]?.[1] !== org) return;
    if (mes && e[20] !== mes) return;
    if (el && nomeEl(e[3]) !== el) return;
    if (soNf && !e[17].length) return;
    if (q && !q.split(/\s+/).every(p => n._busca[i].includes(p))) return;
    L.push(i);
  });
  if ($("#n-ord").value === "valor") L.sort((x, y) => (n.emp[y][5] - n.emp[y][6]) - (n.emp[x][5] - n.emp[x][6]));
  else L.sort((x, y) => n.emp[y][1].localeCompare(n.emp[x][1]) || y - x);
  return L;
}

function pessoaRot(chave) {
  const { D, a } = E.ctx, md = D.mandatos[a.eleicao];
  if (!md || !chave) return "";
  const p = chave === "prefeito" ? md.prefeito : chave === "vice" ? md.vice : md.vereadores[+chave.slice(1)];
  return p ? `${chave.startsWith("v") ? "Vereador(a)" : chave === "vice" ? "Vice" : "Prefeito(a)"} ${titulo(p.urna || p.nome)}` : "";
}

function rNotas() {
  const n = E.N;
  $("#n-restos-box").hidden = true;
  if (!n) {
    $("#n-kpis").innerHTML = ""; $("#n-tab").innerHTML = ""; $("#n-mais").hidden = true; $("#n-csv").hidden = true;
    $("#n-info").innerHTML = `O detalhe nota a nota de ${E.ano} ainda está sendo coletado pelo robô para este município. Enquanto isso, a lista acima mostra quem recebeu.`;
    return;
  }
  $("#n-csv").hidden = false;
  const L = notasFiltradas();
  let emp = 0, anu = 0, pago = 0, nNf = 0, nIt = 0, vNf = 0;
  L.forEach(i => { const e = n.emp[i]; emp += e[5]; anu += e[6]; pago += e[7]; nNf += e[17].length; nIt += e[19].length; vNf += e[17].reduce((s, x) => s + x[6], 0); });
  kpis("#n-kpis", [["Notas de empenho", num(L.length), `de ${num(n.emp.length)} no ano`], ["Valor líquido", brl(emp - anu, 2), anu ? `${brl(anu, 2)} anulados` : "nada anulado"],
    ["Pago", brl(pago, 2), emp - anu ? pct(pago / (emp - anu)) + " do líquido" : ""], ["Notas fiscais", num(nNf), `${brl(vNf, 2)} · ${num(nIt)} itens`]]);
  $("#n-info").textContent = `Valores nominais, como nas notas. Dados até ${mesRef(n.mes_ref)}.`;
  const linha = i => {
    const e = n.emp[i], f = n.forn[e[4]], liq = e[5] - e[6], ab = E.abertas.has(i);
    const chips = [e[17].length ? `<span class="etq pj">${e[17].length} NF</span>` : "", e[19].length ? `<span class="etq">${e[19].length} itens</span>` : "",
      e[15] ? `<span class="etq pf">${esc(pessoaRot(e[15]))}</span>` : ""].join(" ");
    return `<tr class="clicavel" data-ni="${i}" aria-expanded="${ab}"><td>${dataBR(e[1])}</td><td>${ROT_PAPEL[n.orgaos[e[0]]?.[1]] || e[0]}</td>
      <td class="quebra"><strong>${esc(f[0])}</strong> ${etqTipo(f[2])}<span class="sub" style="display:block">${fmtCnpj(f[1])}${f[3] ? " · " + esc(titulo(f[3])) : ""}</span></td>
      <td class="quebra"><span class="trecho">${esc(e[8].slice(0, 150))}${e[8].length > 150 ? "…" : ""}</span><div>${esc(nomeEl(e[3]))} ${chips}</div></td>
      <td class="num">${brl(liq, 2)}${e[6] ? `<div class="glosa">−${brl(e[6], 2)} anulado</div>` : ""}</td><td class="num">${brl(e[7], 2)}</td></tr>` + (ab ? detalheNota(i) : "");
  };
  $("#n-tab").innerHTML = `<thead><tr><th>Data</th><th>Órgão</th><th>Quem recebeu</th><th>Para quê</th><th class="num">Valor líquido</th><th class="num">Pago</th></tr></thead><tbody>` +
    (L.slice(0, E.limN).map(linha).join("") || `<tr><td colspan="6" class="vazio">Nenhuma nota com esses filtros.</td></tr>`) +
    `</tbody><tfoot><tr><td colspan="4">Total (${num(L.length)} notas)</td><td class="num">${brl(emp - anu, 2)}</td><td class="num">${brl(pago, 2)}</td></tr></tfoot>`;
  $("#n-mais").hidden = L.length <= E.limN;
  $$("tr[data-ni]", $("#n-tab")).forEach(tr => tr.onclick = ev => {
    if (ev.target.closest("button,a")) return;
    const i = +tr.dataset.ni; E.abertas.has(i) ? E.abertas.delete(i) : E.abertas.add(i); rNotas();
  });
  if (n.restos.length) {
    $("#n-restos-box").hidden = false;
    $("#n-restos").innerHTML = `<thead><tr><th>Pago em</th><th>Órgão</th><th>Nota de empenho</th><th>Nota de pagamento</th><th class="num">Valor</th></tr></thead><tbody>` +
      n.restos.map(r => `<tr><td>${dataBR(r[4])}</td><td>${ROT_PAPEL[n.orgaos[r[0]]?.[1]] || r[0]}</td><td>nº ${esc(r[2])} de ${dataBR(r[1])}</td><td>nº ${esc(r[3])}${r[6] ? ' <span class="glosa">estornado</span>' : ""}</td><td class="num">${brl(r[5], 2)}</td></tr>`).join("") +
      `</tbody><tfoot><tr><td colspan="4">Total</td><td class="num">${brl(n.restos.filter(r => !r[6]).reduce((s, r) => s + r[5], 0), 2)}</td></tr></tfoot>`;
  }
}

function detalheNota(i) {
  const n = E.N, e = n.emp[i], f = n.forn[e[4]];
  const fatos = [["Nota de empenho", `nº ${e[2]} de ${dataBR(e[1])}`], ["Órgão", titulo(n.orgaos[e[0]]?.[0] || e[0])],
    ["Tipo de gasto", `${nomeEl(e[3])} (elemento ${e[3]})`], ["Empenhado", brl(e[5], 2)], e[6] ? ["Anulado", brl(e[6], 2)] : null,
    ["Pago", brl(e[7], 2)], e[10] || e[9] ? ["Processo de contratação", `${e[10] ? "nº " + e[10] : ""}${e[9] ? ` (espécie ${e[9]})` : ""}`] : null,
    e[11] ? ["Contrato", `nº ${e[11]}${e[12] ? " de " + dataBR(e[12]) : ""}`] : null, e[13] ? ["Modalidade do empenho", e[13]] : null,
    e[14] ? ["Fonte de recurso", e[14]] : null, e[15] ? ["Ligada a", `${pessoaRot(e[15])} (${e[16] === "direto" ? "recebeu diretamente" : "citado(a) no histórico"})`] : null]
    .filter(Boolean).map(([r, v]) => `<div><span class="sub">${r}</span><br><strong>${esc(v)}</strong></div>`).join("");
  const nfs = e[17].length ? `<table class="ranking mini-tab"><thead><tr><th>Nota fiscal</th><th>Emissão</th><th>Liquidação</th><th class="num">Bruto</th><th class="num">Desconto</th><th class="num">Líquido</th><th>Emitente</th><th>Chave NF-e / código</th></tr></thead><tbody>` +
    e[17].map(x => `<tr><td>nº ${esc(x[0])}${x[1] ? " série " + esc(x[1]) : ""}${x[10] ? ` <span class="sub">tipo ${esc(x[10])}</span>` : ""}</td><td>${dataBR(x[2])}</td><td>${dataBR(x[3])}</td><td class="num">${brl(x[4], 2)}</td><td class="num">${x[5] ? brl(x[5], 2) : "—"}</td><td class="num">${brl(x[6], 2)}</td>
      <td>${x[8] ? fmtCnpj(x[8]) + (x[8] !== f[1] && f[1] ? ' <span class="glosa">diferente do favorecido</span>' : "") : "—"}</td>
      <td class="quebra">${x[7] ? `<code style="font-size:11px">${x[7].replace(/(\d{4})/g, "$1 ").trim()}</code> <button class="btn-sec" style="padding:1px 6px;font-size:11px" data-copiar="${x[7]}" type="button">copiar</button>` : x[9] ? `código ${esc(x[9])}` : "—"}</td></tr>`).join("") + `</tbody></table>
      <p class="dica">Para ver a NF-e original, copie a chave e consulte no <a href="https://www.nfe.fazenda.gov.br/portal/principal.aspx" target="_blank" rel="noopener">Portal Nacional da NF-e</a>.</p>`
    : `<p class="sub">Nenhuma nota fiscal ligada a este empenho no TCE${e[3].slice(4, 6) === "11" || e[3].slice(0, 4) === "3190" ? " (folha de pessoal não tem nota fiscal)" : ""}.</p>`;
  const its = e[19].length ? `<table class="ranking mini-tab"><thead><tr><th>NF</th><th>Item</th><th class="num">Qtd.</th><th>Un.</th><th class="num">Preço unitário</th><th class="num">Total</th><th>NCM</th></tr></thead><tbody>` +
    e[19].map(x => `<tr><td>${esc(x[0])}</td><td class="quebra">${esc(x[2])}</td><td class="num">${num(x[4])}</td><td>${esc(x[3])}</td><td class="num">${brl(x[5], 2)}</td><td class="num">${brl(x[6], 2)}</td><td>${esc(x[7])}</td></tr>`).join("") + `</tbody></table>` : "";
  const pags = e[18].length ? `<table class="ranking mini-tab"><thead><tr><th>Nota de pagamento</th><th>Data</th><th class="num">Valor</th></tr></thead><tbody>` +
    e[18].map(x => `<tr><td>nº ${esc(x[0])}${x[3] ? ' <span class="glosa">estornado</span>' : ""}</td><td>${dataBR(x[1])}</td><td class="num">${brl(x[2], 2)}</td></tr>`).join("") + `</tbody></table>` : `<p class="sub">Nenhum pagamento registrado até ${mesRef(n.mes_ref)}.</p>`;
  const naPref = E.PF && f[1] ? E.PF.linhas.findIndex(l => l[1] === f[1]) : -1;
  return `<tr class="sub-notas"><td colspan="6">
    <div class="percentis">${fatos}</div>
    <h4 class="d-sec">Histórico completo</h4><p style="white-space:pre-wrap;margin:0">${esc(e[8]) || "—"}</p>
    <h4 class="d-sec">Notas fiscais</h4>${nfs}${its ? `<h4 class="d-sec">Itens das notas fiscais</h4>${its}` : ""}
    <h4 class="d-sec">Pagamentos</h4>${pags}
    ${naPref >= 0 ? `<p><button class="btn-sec" data-ficha="${naPref}" type="button">Ver tudo o que ${esc(f[0])} recebeu da prefeitura em ${E.ano}</button></p>` : ""}
  </td></tr>`;
}

function csv(nome, linhas) {
  const t = "﻿" + linhas.map(l => l.map(c => { const s = String(c ?? ""); return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; }).join(";")).join("\n");
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([t], { type: "text/csv;charset=utf-8" })); a.download = nome; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
const dec = v => (v ?? 0).toFixed(2).replace(".", ",");

function csvNotas() {
  const n = E.N; if (!n) return;
  csv(`notas_${E.ctx.D.nome}_${E.ano}.csv`.replace(/\s+/g, "_").toLowerCase(), [["data", "orgao", "numero_empenho", "elemento", "tipo_de_gasto", "favorecido", "cnpj", "municipio_favorecido",
    "historico", "empenhado", "anulado", "liquido", "pago", "processo", "especie_processo", "contrato", "notas_fiscais", "chaves_nfe", "valor_notas_fiscais", "itens", "ligada_a"],
  ...notasFiltradas().map(i => { const e = n.emp[i], f = n.forn[e[4]]; return [e[1], titulo(n.orgaos[e[0]]?.[0] || e[0]), e[2], e[3], nomeEl(e[3]), f[0], fmtCnpj(f[1]), f[3], e[8],
    dec(e[5]), dec(e[6]), dec(e[5] - e[6]), dec(e[7]), e[10], e[9], e[11], e[17].map(x => x[0]).join(" | "), e[17].map(x => x[7]).filter(Boolean).join(" | "),
    dec(e[17].reduce((s, x) => s + x[6], 0)), e[19].map(x => `${x[4]} ${x[3]} ${x[2]} (${dec(x[5])})`).join(" | "), pessoaRot(e[15])]; })]);
}

/* ---- prefeitura inteira */
function pfFiltrados() {
  const f = E.PF, q = semAcento($("#pf-q").value.trim()), org = $("#pf-orgao").value, tp = $("#pf-tipo").value;
  const L = [];
  f.linhas.forEach((l, i) => {
    if (tp && l[2] !== tp) return;
    if (org && !(org in l[6])) return;
    if (q && !q.split(/\s+/).every(p => semAcento(`${l[0]} ${l[1]} ${fmtCnpj(l[1])} ${l[3]}`).includes(p))) return;
    L.push([i, org ? l[6][org] : l[4]]);
  });
  return L.sort((a, b) => b[1] - a[1]);
}

function rPF() {
  const f = E.PF;
  if (!f) {
    $("#pf-kpis").innerHTML = ""; $("#pf-mais").hidden = true; $("#pf-csv").hidden = true;
    $("#pf-tab").innerHTML = `<tbody><tr><td class="vazio">A lista de quem recebeu da prefeitura inteira em ${E.ano} ainda está sendo coletada pelo robô para este município.</td></tr></tbody>`;
    return;
  }
  $("#pf-csv").hidden = false;
  const L = pfFiltrados(), tot = L.reduce((s, x) => s + x[1], 0), c = f.conferencia;
  kpis("#pf-kpis", [["Favorecidos", num(L.length), `${num(f.n_favorecidos)} no ano`], ["Valor líquido", brl(tot, 2), "valores nominais"],
    ["Notas de empenho", num(f.n_notas), "todos os órgãos"], ["Conferência", c.ok ? "bate" : brl(c.diferenca, 2), c.ok ? "notas = balancete do TCE" : "diferença entre notas e balancete"]]);
  const orgs = l => Object.keys(l[6]).slice(0, 2).map(o => titulo(f.orgaos[o] || o)).join(", ") + (Object.keys(l[6]).length > 2 ? ` e mais ${Object.keys(l[6]).length - 2}` : "");
  $("#pf-tab").innerHTML = `<thead><tr><th>Quem recebeu</th><th>De onde é</th><th>Órgãos que pagaram</th><th>Principal gasto</th><th class="num">Notas</th><th class="num">Valor líquido</th></tr></thead><tbody>` +
    (L.slice(0, E.limPF).map(([i, val]) => { const l = f.linhas[i]; return `<tr><td class="quebra"><button class="link-forn" data-ficha="${i}" type="button">${esc(l[0])}</button> ${etqTipo(l[2])}<span class="sub" style="display:block">${fmtCnpj(l[1])}</span></td>
      <td>${esc(titulo(l[3]))}</td><td class="quebra det">${esc(orgs(l))}</td><td class="det">${esc(nomeEl("00" + Object.keys(l[7])[0]?.slice(2)))}</td><td class="num">${num(l[5])}</td><td class="num">${brl(val, 2)}</td></tr>`; }).join("")
      || `<tr><td colspan="6" class="vazio">Ninguém encontrado com esses filtros.</td></tr>`) +
    `</tbody><tfoot><tr><td colspan="5">Total (${num(L.length)} favorecidos)</td><td class="num">${brl(tot, 2)}</td></tr></tfoot>`;
  $("#pf-mais").hidden = L.length <= E.limPF;
}

function csvPF() {
  const f = E.PF; if (!f) return;
  csv(`fornecedores_prefeitura_${E.ctx.D.nome}_${E.ano}.csv`.replace(/\s+/g, "_").toLowerCase(), [["favorecido", "cnpj", "tipo", "municipio", "valor_liquido", "notas", "orgaos", "tipos_de_gasto", ...MESES],
    ...pfFiltrados().map(([i]) => { const l = f.linhas[i]; return [l[0], fmtCnpj(l[1]), l[2], l[3], dec(l[4]), l[5],
      Object.entries(l[6]).map(([o, v]) => `${titulo(f.orgaos[o] || o)}: ${dec(v)}`).join(" | "),
      Object.entries(l[7]).map(([el, v]) => `${el} ${nomeEl("00" + el.slice(2))}: ${dec(v)}`).join(" | "), ...l[8].map(dec)]; })]);
}

function abrirFicha(i) {
  const f = E.PF, l = f.linhas[i];
  const naCamara = E.N && l[1] ? E.N.emp.filter(e => E.N.forn[e[4]][1] === l[1]).length : 0;
  const orgs = Object.entries(l[6]).map(([o, v]) => `<tr><td>${esc(titulo(f.orgaos[o] || o))}</td><td class="num">${brl(v, 2)}</td><td class="num">${pct(v / l[4])}</td></tr>`).join("");
  const els = Object.entries(l[7]).map(([el, v]) => `<tr><td>${esc(nomeEl("00" + el.slice(2)))} <span class="sub">${el}</span></td><td class="num">${brl(v, 2)}</td></tr>`).join("");
  const notas = l[9].map(x => `<tr><td>${dataBR(x[0])}</td><td class="det">${esc(titulo(f.orgaos[x[1]] || x[1]))}</td><td>nº ${esc(x[2])}<span class="sub" style="display:block">${esc(nomeEl(x[3]))}</span></td>
    <td class="quebra"><span class="trecho">${esc(x[5]) || '<span class="sub">histórico não guardado (nota abaixo de R$ 2.000)</span>'}</span>${x[7] || x[8] ? `<div class="sub">${x[7] ? "processo nº " + esc(x[7]) : ""}${x[8] ? " · contrato nº " + esc(x[8]) : ""}</div>` : ""}</td><td class="num">${brl(x[4], 2)}</td></tr>`).join("");
  $("#ff-corpo").innerHTML = `<p class="selo">Quem recebeu da prefeitura · ${E.ano}</p><h2 style="margin:4px 0">${esc(l[0])} ${etqTipo(l[2])}</h2>
    <p class="sub">${fmtCnpj(l[1]) || (l[2] === "PF" ? "pessoa física (CPF não é publicado)" : "")}${l[3] ? " · " + esc(titulo(l[3])) : ""}</p>
    <div class="kpis"><div class="kpi"><div class="rot">Recebeu em ${E.ano}</div><div class="val num">${brl(l[4], 2)}</div><div class="obs">líquido de anulações, valor nominal</div></div>
      <div class="kpi"><div class="rot">Notas de empenho</div><div class="val num">${num(l[5])}</div></div>
      <div class="kpi"><div class="rot">Órgãos que pagaram</div><div class="val num">${Object.keys(l[6]).length}</div></div></div>
    ${naCamara ? `<p><button class="btn-sec" data-filtrar-doc="${l[1]}" type="button">Ver as ${naCamara} notas na câmara e nos gabinetes, com notas fiscais e itens</button></p>` : ""}
    <h3 class="d-sec">Mês a mês</h3><div class="canvas-box" style="height:200px"><canvas id="ff-graf"></canvas></div>
    <div class="d-grade"><div><h3 class="d-sec">Por órgão</h3><table class="ranking mini-tab"><tbody>${orgs}</tbody></table></div>
      <div><h3 class="d-sec">Por tipo de gasto</h3><table class="ranking mini-tab"><tbody>${els}</tbody></table></div></div>
    <h3 class="d-sec">${l[9].length < l[5] ? `As ${l[9].length} maiores notas (de ${num(l[5])})` : "Todas as notas"}</h3>
    <div class="tabela-rolagem"><table class="ranking mini-tab"><thead><tr><th>Data</th><th>Órgão</th><th>Empenho</th><th>Para quê</th><th class="num">Valor</th></tr></thead><tbody>${notas || `<tr><td colspan="5" class="sub">Folha de pessoal: sem notas individuais.</td></tr>`}</tbody></table></div>`;
  $("#ficha-forn").showModal();
  E.graf.ff?.destroy();
  E.graf.ff = new Chart($("#ff-graf"), { type: "bar", data: { labels: MESES, datasets: [{ data: l[8], backgroundColor: "#118dff" }] }, options: opBarra(false) });
}

function filtrarNotasPor(texto) {
  $("#ficha-forn").open && $("#ficha-forn").close();
  $("#n-q").value = texto; $("#n-orgao").value = ""; $("#n-mes").value = ""; $("#n-el").value = ""; $("#n-nf").checked = false;
  E.limN = 30; E.abertas = new Set(); rNotas();
  $("#m-notas-box").scrollIntoView({ behavior: "smooth", block: "start" });
}

/* --------------------------------------------------------------- início */
async function iniciar() {
  try {
    [E.meta, E.res] = await Promise.all([json("dados/meta.json"), json("dados/resumo.json")]);
  } catch (e) {
    $("#aviso").hidden = false;
    $("#aviso").textContent = "Os dados ainda estão sendo coletados pelo robô. Volte em algumas horas.";
    irPara("metodo");
    return;
  }
  E.meta._campos = E.res.campos; E.res = E.res.municipios;
  const anos = E.meta.anos.slice().reverse();
  // ano padrão: o mais recente com pelo menos metade dos municípios
  E.ano = String(anos.find(a => (E.meta.cobertura[a] || 0) >= E.meta.total_municipios / 2) || anos[0]);
  $("#f-ano").innerHTML = anos.map(a => `<option value="${a}">${a}</option>`).join("");
  $("#f-ano").value = E.ano;
  $("#lista-mun").innerHTML = E.res.map(m => `<option value="${esc(titulo(m.nome))}">`).join("");
  $("#atualizado").textContent = `Atualizado em ${new Date(E.meta.gerado_em).toLocaleString("pt-BR")}`;
  if (E.meta.ipca?.referencia) $("#ipca-ref").textContent = `corrigidos pelo IPCA até ${E.meta.ipca.referencia}`;
  const cob = E.meta.cobertura[E.ano] || 0;
  if (cob < E.meta.total_municipios) { $("#aviso").hidden = false; $("#aviso").textContent = `${cob} de ${E.meta.total_municipios} municípios já têm dados de ${E.ano}. O robô completa o restante nos próximos dias.`; }
  const [pag, sim] = location.hash.slice(1).split("/");
  if (sim) E.sim = sim;
  irPara(["inicio", "prefeitos", "camaras", "municipio", "metodo"].includes(pag) ? pag : "inicio");
}

document.addEventListener("click", e => {
  const s = e.target.closest("[data-sim]"); if (s) return abrirMunicipio(s.dataset.sim);
  const p = e.target.closest("[data-pag],[data-ir]"); if (p && (p.dataset.pag || p.dataset.ir) && p.tagName === "BUTTON") irPara(p.dataset.pag || p.dataset.ir);
});
$("#f-ano").onchange = e => { E.ano = e.target.value; const c = E.meta.cobertura[E.ano] || 0; $("#aviso").hidden = c >= E.meta.total_municipios;
  $("#aviso").textContent = `${c} de ${E.meta.total_municipios} municípios já têm dados de ${E.ano}.`; render(); };
$("#f-ipca").onchange = e => { E.ipca = e.target.checked; render(); };
$("#f-mun").onchange = e => { const m = E.res.find(x => semAcento(titulo(x.nome)) === semAcento(e.target.value)); if (m) abrirMunicipio(m.sim); };
$("#p-busca").oninput = () => { E.limP = 20; rPrefeitos(); };
$("#c-busca").oninput = () => { E.limC = 20; rCamaras(); };
$("#p-mais").onclick = () => { E.limP += 30; rPrefeitos(); };
$("#c-mais").onclick = () => { E.limC += 30; rCamaras(); };
$("#m-orgao").onchange = () => { E.limF = 20; render(); };
$("#m-forn-mais").onclick = () => { E.limF += 30; render(); };
["#n-q", "#n-orgao", "#n-mes", "#n-el", "#n-nf", "#n-ord"].forEach(s => $(s)[s === "#n-q" ? "oninput" : "onchange"] = () => { E.limN = 30; E.abertas = new Set(); rNotas(); });
["#pf-q", "#pf-orgao", "#pf-tipo"].forEach(s => $(s)[s === "#pf-q" ? "oninput" : "onchange"] = () => { E.limPF = 30; rPF(); });
$("#n-mais").onclick = () => { E.limN += 50; rNotas(); };
$("#pf-mais").onclick = () => { E.limPF += 50; rPF(); };
$("#n-csv").onclick = csvNotas;
$("#pf-csv").onclick = csvPF;
$("#ff-fechar").onclick = () => $("#ficha-forn").close();
$("#ficha-forn").onclick = e => { if (e.target.id === "ficha-forn") $("#ficha-forn").close(); };
document.addEventListener("click", e => {
  const fi = e.target.closest("[data-ficha]"); if (fi) return abrirFicha(+fi.dataset.ficha);
  const fd = e.target.closest("[data-filtrar-doc]"); if (fd) return filtrarNotasPor(fd.dataset.filtrarDoc);
  const cp = e.target.closest("[data-copiar]"); if (cp) { navigator.clipboard?.writeText(cp.dataset.copiar); cp.textContent = "copiado"; }
});
$("#abrir-menu").onclick = () => { $("#menu").classList.add("aberto"); $("#veu").hidden = false; $("#abrir-menu").setAttribute("aria-expanded", "true"); };
$("#veu").onclick = fecharMenu;
iniciar();
})();
