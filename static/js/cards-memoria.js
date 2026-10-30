// Cards da "memoria da IA" (Laboratorio v4, Grupo D, 2026-10-30; docs/briefings/2026-10-30-lab-v4-memoria.md):
//   guardados    - "Onde guardei": pino que cai, lugar em destaque e a lista do que ele ja guardou;
//   o_que_falei  - "O que eu falei sobre...": as frases dele, datadas, do mais novo pro mais velho;
//   neste_dia    - "Neste dia": o que aconteceu nesta data em meses/anos atras (so progresso);
//   coincidencia - cruzamento sono/treino x tarefas/delivery, sempre "coincidencia, nao causa".
//
// Mesmo contrato do resto: renderizador PURO (estado final; historico abre parado; testes em Node),
// entrada animada so em .card-novo (CSS), cliques via Cards.registrarAcao. Texto vindo do servidor
// sempre por `esc`. prefers-reduced-motion: nada anima (CSS).
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const { esc, numeroValido } = Cards;
  const lista = (v) => (Array.isArray(v) ? v : []);

  const svg = (corpo) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${corpo}</svg>`;
  const I = {
    pino: svg('<path d="M12 21s-6.5-6.2-6.5-11a6.5 6.5 0 0 1 13 0c0 4.8-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.4"/>'),
    caixa: svg('<path d="M4 8h16v11a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19V8Z"/><path d="M3 4.5h18V8H3zM10 12h4"/>'),
    lupa: svg('<circle cx="11" cy="11" r="6.5"/><path d="m20 20-3.9-3.9"/>'),
    calendario: svg('<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>'),
    grafico: svg('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'),
    aviao: svg('<path d="M21 15.5v-1.8l-7.5-4.6V4a1.5 1.5 0 0 0-3 0v5.1L3 13.7v1.8l7.5-2.3v4.9L8.6 19.5V21l3.4-1 3.4 1v-1.5l-1.9-1.4v-4.9z"/>'),
    haltere: svg('<path d="M6.5 6.5v11M17.5 6.5v11M3.5 9v6M20.5 9v6M6.5 12h11"/>'),
    x: svg('<path d="M6 6l12 12M18 6 6 18"/>'),
    ok: svg('<circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.3 2.4 2.3 4.6-4.9"/>'),
  };
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const dd = (n) => String(n).padStart(2, "0");
  // "21/10" no ano corrente, "21/10/2025" nos outros
  function dataCurta(iso, agora) {
    const d = Cards.parseDia(iso);
    if (!d) return "";
    const ref = agora instanceof Date ? agora : new Date();
    return d.getFullYear() === ref.getFullYear() ? `${dd(d.getDate())}/${dd(d.getMonth() + 1)}` : `${dd(d.getDate())}/${dd(d.getMonth() + 1)}/${d.getFullYear()}`;
  }
  const olho = (icone, texto, quando) =>
    `<div class="card-resultado-eyebrow">${icone}<span>${esc(texto)}</span>${quando ? `<span class="sd-quando">${esc(quando)}</span>` : ""}</div>`;
  const n1 = (v) => String(Math.round(Number(v) * 10) / 10).replace(".", ",");
  const oculto = (icone, titulo) =>
    `<div class="sd mm">${olho(icone, titulo, "")}<p class="mm-meta">Escondido no modo visitante.</p></div>`;

  // ======================================================================= guardados
  function itemGuardado(it, destaqueId) {
    const marca = it.id === destaqueId ? " destaque" : "";
    return (
      `<li class="gd-it${marca}" data-gd-id="${esc(it.id)}">` +
      `<span class="gd-ic">${I.caixa}</span>` +
      `<span class="gd-txt"><b>${esc(it.objeto)}</b><small>${esc(it.lugar)}</small></span>` +
      `<span class="gd-quando">${esc(it.quando || "")}</span>` +
      `<button type="button" class="gd-tirar" data-acao="gd_tirar" data-id="${esc(it.id)}" aria-label="Tirar ${esc(it.objeto)} da lista">${I.x}</button>` +
      `</li>`
    );
  }
  function raizGuardados(data) {
    const d = data || {};
    if (d.oculto) return oculto(I.pino, "Guardados");
    const dest = d.destaque && typeof d.destaque === "object" ? d.destaque : null;
    const modo = d.modo || "lista";
    let miolo = "";
    if (modo === "achei" && dest) {
      miolo =
        `<div class="gd-resp" data-modo="achei"><span class="gd-pin">${I.pino}</span><div class="gd-resp-txt">` +
        `<p class="gd-obj">${esc(dest.objeto)}</p><p class="sd-hero">${esc(dest.lugar)}</p>` +
        `<p class="mm-meta">Tu guardou ${esc(dest.quando || "")}</p></div></div>`;
    } else if (modo === "guardado" && dest) {
      miolo =
        `<div class="gd-resp" data-modo="guardado"><span class="gd-pin">${I.pino}</span><div class="gd-resp-txt">` +
        `<p class="gd-obj">Guardado: ${esc(dest.objeto)}</p><p class="sd-hero">${esc(dest.lugar)}</p>` +
        `<p class="mm-meta">${dest.anterior ? `Antes estava em ${esc(dest.anterior)}. ` : ""}Te lembro onde tá quando tu perguntar.</p></div></div>`;
    } else if (modo === "nao_achei") {
      miolo =
        `<div class="gd-resp vazio" data-modo="nao_achei"><div class="gd-resp-txt">` +
        `<p class="sd-hero">Não tenho nada guardado${d.busca ? ` sobre “${esc(d.busca)}”` : ""}.</p>` +
        `<p class="mm-meta">Me diz onde tá que eu anoto.</p></div></div>`;
    }
    const outros = lista(d.itens).filter((i) => i && !(dest && i.id === dest.id));
    const todos = modo === "lista" ? lista(d.itens) : outros;
    const rot = modo === "lista" ? "" : todos.length ? `<p class="sd-rotulo">${modo === "nao_achei" ? "O que eu tenho guardado" : "Outros guardados"}</p>` : "";
    const ul = todos.length ? `<ul class="gd-lista">${todos.map((i) => itemGuardado(i, dest && dest.id)).join("")}</ul>` : "";
    const quando = modo === "lista" && numeroValido(d.total) ? `${d.total} ${d.total === 1 ? "item" : "itens"}` : "";
    return `<div class="sd gd" data-modo="${esc(modo)}">${olho(I.pino, "Guardados", quando)}${miolo}${rot}${ul}</div>`;
  }
  Cards.registrar("guardados", (data) => raizGuardados(data));

  // ===================================================================== o_que_falei
  function raizFalas(data, agora) {
    const d = data || {};
    if (d.oculto) return oculto(I.lupa, "O que tu disse");
    const itens = lista(d.itens).filter((i) => i && i.texto);
    const total = numeroValido(d.total) ? d.total : itens.length;
    const rodape = total > itens.length ? `<p class="mm-meta">Mostrando as ${itens.length} mais recentes de ${total}.</p>` : "";
    const corpo = itens.length
      ? itens
          .map(
            (i, n) =>
              `<div class="oq-it" style="--n:${n}"><span class="oq-dia">${esc(dataCurta(i.dia, agora))}</span><span class="oq-q">${esc(i.texto)}</span></div>`
          )
          .join("")
      : `<p class="mm-meta">Nada que tu tenha dito sobre isso.</p>`;
    return (
      `<div class="sd oq">${olho(I.lupa, "O que tu disse", total ? `${total} ${total === 1 ? "vez" : "vezes"}` : "")}` +
      `<p class="sd-hero">sobre “${esc(d.assunto || "")}”</p><div class="oq-lista">${corpo}</div>${rodape}</div>`
    );
  }
  Cards.registrar("o_que_falei", (data, _card, ctx) => raizFalas(data, ctx && ctx.agora));

  // ======================================================================== neste_dia
  function raizNesteDia(data, agora) {
    const d = data || {};
    if (d.oculto) return oculto(I.calendario, "Neste dia");
    const itens = lista(d.itens).filter((i) => i && i.texto);
    const corpo = itens
      .map((i, n) => {
        const ic = i.icone === "saude" ? I.haltere : I.aviao;
        return (
          `<div class="nd-it" style="--n:${n}"><span class="nd-ico">${ic}</span><div class="nd-txt">` +
          `<small>${esc(i.rotulo)}${i.quando ? ` · ${esc(i.quando)}` : ""}</small><p>${esc(i.texto)}</p></div></div>`
        );
      })
      .join("");
    return (
      `<div class="sd nd">${olho(I.calendario, "Neste dia", d.rotulo || "")}` +
      `<div class="nd-pilha">${corpo}</div>` +
      `<p class="mm-meta">Só aparece quando a data tem algo bom. Dia comum, não aparece nada.</p></div>`
    );
  }
  Cards.registrar("neste_dia", (data, _card, ctx) => raizNesteDia(data, ctx && ctx.agora));

  // ===================================================================== coincidencia
  const unidade = (u, v) => (u ? `${u}${Math.round(Number(v))}` : n1(v));
  function linhaCoincidencia(l, rotBom, rotRuim) {
    const mx = Math.max(Number(l.bom) || 0, Number(l.ruim) || 0, 0.0001);
    const f = (v) => Math.max(0.04, Math.min(1, (Number(v) || 0) / mx)).toFixed(3);
    return (
      `<div class="co-linha"><span class="mm-meta">${esc(l.rotulo)}</span>` +
      `<div class="co-b"><i class="bom" style="--w:${f(l.bom)}"></i><em>${esc(rotBom)}: ${esc(unidade(l.unidade, l.bom))}</em></div>` +
      `<div class="co-b"><i class="ruim" style="--w:${f(l.ruim)}"></i><em>${esc(rotRuim)}: ${esc(unidade(l.unidade, l.ruim))}</em></div></div>`
    );
  }
  function detalheCoincidencia(d, agora) {
    const linhas = lista(d.detalhe)
      .map((x) => {
        const sono = numeroValido(x.sono) ? `${n1(x.sono)} h` : "—";
        const dinheiro = Number(x.delivery) > 0 ? `R$ ${Math.round(Number(x.delivery))}` : "—";
        return (
          `<tr class="${x.lado === "ruim" ? "ruim" : "bom"}"><td>${esc(dataCurta(x.dia, agora))}</td>` +
          `<td>${esc(sono)}</td><td>${esc(x.tarefas)}</td><td>${esc(dinheiro)}</td></tr>`
        );
      })
      .join("");
    return (
      `<div class="co-detalhe" hidden><table><thead><tr><th>Dia</th><th>Sono</th><th>Tarefas</th><th>Delivery</th></tr></thead>` +
      `<tbody>${linhas}</tbody></table></div>`
    );
  }
  function raizCoincidencia(data, agora) {
    const d = data || {};
    if (d.oculto) return oculto(I.grafico, "Coincidência da semana");
    const linhas = lista(d.linhas).filter((l) => l && numeroValido(Number(l.bom)));
    if (!linhas.length) return null;
    return (
      `<div class="sd co" data-tipo="${esc(d.tipo)}">${olho(I.grafico, "Coincidência da semana", d.periodo || "")}` +
      `<p class="sd-hero">${esc(d.titulo)}</p>` +
      linhas.map((l) => linhaCoincidencia(l, d.rot_bom, d.rot_ruim)).join("") +
      `<p class="mm-meta">${esc(d.aviso)}</p>` +
      detalheCoincidencia(d, agora) +
      `<div class="co-pe"><button type="button" class="ca-botao ca-leve" data-acao="co_ocultar" data-tipo="${esc(d.tipo)}">Não ligo pra isso</button>` +
      (lista(d.detalhe).length ? `<button type="button" class="ca-botao" data-acao="co_detalhe" aria-expanded="false">Quero ver mais</button>` : "") +
      `</div></div>`
    );
  }
  Cards.registrar("coincidencia", (data, _card, ctx) => raizCoincidencia(data, ctx && ctx.agora));

  // ========================================================================== acoes
  const reduz = () => !!(raiz.matchMedia && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches);
  async function enviar(deps, url, metodo, corpo) {
    if (typeof deps.apiFetch !== "function") return null;
    try {
      const opcoes = { method: metodo };
      if (corpo) {
        opcoes.headers = { "Content-Type": "application/json" };
        opcoes.body = JSON.stringify(corpo);
      }
      return await deps.apiFetch(url, opcoes);
    } catch (_) {
      return null;
    }
  }
  // dois toques pra tirar (o primeiro so pergunta), sem confirm() do navegador
  Cards.registrarAcao("gd_tirar", async (btn, cardEl, deps) => {
    if (btn.disabled) return;
    if (!btn.classList.contains("confirma")) {
      btn.classList.add("confirma");
      btn.setAttribute("aria-label", "Toque de novo para tirar");
      raiz.setTimeout(() => {
        btn.classList.remove("confirma");
        btn.setAttribute("aria-label", "Tirar da lista");
      }, 3000);
      return;
    }
    btn.disabled = true;
    const r = await enviar(deps || {}, `/api/guardados/${encodeURIComponent(btn.dataset.id)}`, "DELETE");
    const li = btn.closest(".gd-it");
    if (!r || r.error || r.ok === false) {
      btn.disabled = false;
      btn.classList.remove("confirma");
      return;
    }
    if (li) {
      li.classList.add("saindo");
      raiz.setTimeout(() => li.remove(), reduz() ? 0 : 380);
    }
    if (typeof deps.aoMudar === "function") deps.aoMudar();
  });
  Cards.registrarAcao("co_detalhe", (btn, cardEl) => {
    const det = cardEl.querySelector(".co-detalhe");
    if (!det) return;
    const abre = det.hidden;
    det.hidden = !abre;
    btn.setAttribute("aria-expanded", String(abre));
    btn.textContent = abre ? "Esconder" : "Quero ver mais";
  });
  Cards.registrarAcao("co_ocultar", async (btn, cardEl, deps) => {
    if (btn.disabled) return;
    btn.disabled = true;
    const r = await enviar(deps || {}, "/api/coincidencias/ocultar", "POST", { tipo: btn.dataset.tipo });
    if (!r || r.error || r.ok === false) {
      btn.disabled = false;
      return;
    }
    const raizEl = cardEl.querySelector(".co");
    if (raizEl) {
      raizEl.classList.add("some");
      raiz.setTimeout(() => {
        raizEl.innerHTML = `<p class="mm-meta">Não mostro mais esse tipo de coincidência.</p>`;
        raizEl.classList.remove("some");
      }, reduz() ? 0 : 420);
    }
  });

  const api = { raizGuardados, raizFalas, raizNesteDia, raizCoincidencia, dataCurta };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  raiz.CardsMemoria = api;
})(typeof window !== "undefined" ? window : globalThis);
