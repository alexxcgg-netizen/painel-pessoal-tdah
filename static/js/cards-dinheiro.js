// Cards do Grupo E (Dinheiro) do Laboratorio v4, 30/10/2026 (docs/briefings/2026-10-30-lab-v4-dinheiro.md):
//   cupom_itens  - "Cupom vira itens": QR (animacao de leitura so em .card-novo), barra por categoria,
//                  uma linha por categoria e "Registrar como gasto" (POST /api/cupons/<id>/registrar);
//   contas_email - "Cacador de contas no e-mail": faixa da varredura + uma linha por conta (boleto, PIX,
//                  fatura ou rastreio) com "Copiar codigo" e "Ja paguei" (POST /api/contas-email/<id>/status).
// Dinheiro PESSOAL do Alex. Valores somem no modo visitante (cards.CAMPOS_SENSIVEIS: data.oculto).
// Mesmo contrato do resto: renderizador PURO (estado final; historico abre parado), cliques via
// Cards.registrarAcao, animacao so em .card-novo (CSS) e prefers-reduced-motion desliga tudo.
(function (raiz) {
  "use strict";
  const Cards = raiz.Cards || (typeof require === "function" ? require("./cards.js") : null);
  if (!Cards) return;
  const { esc, numeroValido } = Cards;
  const lista = (v) => (Array.isArray(v) ? v : []);

  const svg = (corpo) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${corpo}</svg>`;
  const I = {
    cupom: svg('<path d="M6 3h12v18l-2.4-1.6L13.2 21 12 19.8 10.8 21l-2.4-1.6L6 21V3Z"/><path d="M9 8h6M9 12h6M9 16h3"/>'),
    email: svg('<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m4 7.5 8 6 8-6"/>'),
    ok: svg('<circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.3 2.4 2.3 4.6-4.9"/>'),
    alerta: svg('<path d="M12 4 2.8 19.5h18.4L12 4Z"/><path d="M12 10v4M12 17h.01"/>'),
    copiar: svg('<rect x="8.5" y="8.5" width="11" height="11" rx="2.5"/><path d="M15.5 8.5V6.2a1.7 1.7 0 0 0-1.7-1.7H6.2a1.7 1.7 0 0 0-1.7 1.7v7.6a1.7 1.7 0 0 0 1.7 1.7h2.3"/>'),
  };
  const olho = (icone, texto, quando) =>
    `<div class="card-resultado-eyebrow">${icone}<span>${esc(texto)}</span>${quando ? `<span class="sd-quando cd-quando">${esc(quando)}</span>` : ""}</div>`;
  // "R$ 312,58" com espaco que nao quebra (valor nunca racha em duas linhas)
  const reais = (v) => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }).replace(/\s/g, " ");
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const diaMes = (iso) => {
    const d = Cards.parseDia(iso);
    return d ? `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}` : "";
  };

  // ===================================================== cupom_itens
  // QR 9x9 decorativo (o do protótipo): a "leitura" e so teatro de entrada, o dado vem do servidor
  const QR_PIXELS = Array.from({ length: 81 }, (_, i) => ((i * 7 + (i % 5) * 3) % 3 !== 0 ? '<i class="p"></i>' : "<i></i>")).join("");

  Cards.registrar("cupom_itens", (data) => {
    if (!data || !data.cupom_id) return null;
    const oculto = !!data.oculto || !numeroValido(data.total);
    if (oculto) {
      return (
        `<div class="sd cu">` + olho(I.cupom, "Cupom fiscal", data.estabelecimento || "") +
        `<p class="cu-nota">${esc(Cards.MOEDA_OCULTA)} · valores ocultos no modo visitante</p></div>`
      );
    }
    const cats = lista(data.categorias).filter((c) => c && c.nome && numeroValido(c.valor) && c.valor > 0);
    const barra = cats
      .map((c, k) => `<i style="flex:${c.valor};background:${esc(c.cor || "#8a94a3")};--k:${k}"></i>`)
      .join("");
    const linhas = cats
      .map(
        (c, k) =>
          `<div class="cu-l" style="--k:${k}"><span class="cu-dot" style="background:${esc(c.cor || "#8a94a3")}"></span>` +
          `<span class="cu-n">${esc(c.nome)}</span><span class="cu-v">${esc(reais(c.valor))}</span></div>`,
      )
      .join("");
    const n = Number(data.qtd_itens) || 0;
    const ex = lista(data.exemplos).filter((e) => typeof e === "string" && e);
    const nota = `${n} ${n === 1 ? "item separado" : "itens separados"}.${ex.length ? ` Ex.: ${ex.map((e) => esc(e)).join(", ")}.` : ""}`;
    const quando = reais(data.total);
    const dia = diaMes(typeof data.emitido_em === "string" ? data.emitido_em.slice(0, 10) : "");
    return (
      `<div class="sd cu" data-cupom="${esc(data.cupom_id)}" data-feito-chave="${esc(`cupom:${data.cupom_id}`)}">` +
      olho(I.cupom, "Cupom fiscal", quando) +
      `<div class="cu-qr" aria-hidden="true"><div class="cu-cod">${QR_PIXELS}</div><i class="cu-luz"></i></div>` +
      `<p class="cu-dia">${esc([data.estabelecimento, dia ? `emitido em ${dia}` : ""].filter(Boolean).join(" · "))}</p>` +
      `<div class="cu-res"><div class="cu-barra" role="img" aria-label="Divisão do cupom por categoria">${barra}</div>${linhas}` +
      `<p class="cu-nota">${nota}</p></div>` +
      (data.registrado
        ? `<p class="sd-status ok">${I.ok}<span>Já tá no teu extrato.</span></p>`
        : `<button type="button" class="ca-botao cu-registrar" data-acao="cupom_registrar" data-cupom="${esc(data.cupom_id)}"><span>Registrar como gasto</span></button>` +
          `<p class="sd-status" aria-live="polite"></p>`) +
      `</div>`
    );
  });

  // ===================================================== contas_email
  const ROTULO_COPIA = { boleto: "Copiar boleto", pix: "Copiar PIX copia-e-cola" };
  const URL_CORREIOS = "https://rastreamento.correios.com.br/app/index.php";

  function quandoVence(c) {
    if (!c.vence) return c.tipo === "rastreio" ? "código de rastreio" : "sem vencimento no e-mail";
    const d = diaMes(c.vence);
    if (!numeroValido(c.dias)) return `vence ${d}`;
    if (c.dias < 0) return `venceu ${d} (há ${-c.dias} ${c.dias === -1 ? "dia" : "dias"})`;
    if (c.dias === 0) return `vence hoje (${d})`;
    if (c.dias === 1) return `vence amanhã (${d})`;
    return `vence ${d} (em ${c.dias} dias)`;
  }

  // ---- linguagem D (04/11, docs/CARDS.md cena 8): uma conta só vira pílula com "deslize se já
  // pagou" (POST /api/contas-email/<id>/status, a rota que já existia). Várias contas e rastreio
  // continuam na lista com botões.
  const D = () => raiz.CardsD || (typeof require === "function" ? require("./cards-d.js") : null);
  const COR_CONTA = "#ffd36e";
  const ICONE_CONTA =
    '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6 2.5h9l4 4V20a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 015 20V4A1.5 1.5 0 016.5 2.5zM8.5 11h7v1.6h-7zm0 3.5h7v1.6h-7zm0-7h4v1.6h-4z"/></svg>';
  function contaD(c, card) {
    const cd = D();
    const paga = c.status === "paga";
    const luz = /\b(luz|energia|celesc|copel|cemig|enel)\b/i.test(c.nome);
    const copia =
      c.codigo && ROTULO_COPIA[c.tipo]
        ? `<button type="button" data-acao="conta_copiar" data-codigo="${esc(c.codigo)}" data-tipo="${esc(c.tipo)}">${esc(ROTULO_COPIA[c.tipo])}</button>`
        : "";
    const linhas = [c.vence ? ["Vencimento", diaMes(c.vence)] : null].filter(Boolean);
    return cd.pilula({
      v: "conta",
      cor: COR_CONTA,
      icone: luz ? cd.IC.raio : ICONE_CONTA,
      titulo: c.nome,
      sub: `<span>${esc(paga ? "pago" : quandoVence(c))}</span>`,
      rotulo: numeroValido(c.valor) ? "valor" : "",
      valor: numeroValido(c.valor) ? esc(reais(c.valor)) : "",
      attrs: ` data-conta="${esc(c.id)}" data-feito-chave="${esc(`conta:${c.id}`)}"${paga ? ' data-pago="1"' : ""}`,
      corpo:
        (linhas.length ? `<div class="v-linhas">${linhas.map(([r, v]) => `<div class="v-linha"><span>${esc(r)}</span><span>${esc(v)}</span></div>`).join("")}</div>` : "") +
        (paga ? `<p class="v-nota">Já tá pago.</p>` : cd.deslizaHTML("conta_paga", "deslize se já pagou", ` data-conta="${esc(c.id)}"`)) +
        `<p class="ce-msg v-nota" aria-live="polite" hidden></p>` +
        cd.botoes(card, copia),
    });
  }
  function contaPagaD(vivo) {
    vivo.classList.add("pago");
    const dz = vivo.querySelector(".v-desliza");
    if (dz) {
      dz.dataset.feito = "1";
      dz.classList.add("solto");
      dz.style.setProperty("--x", `${Math.max(0, dz.clientWidth - 56)}px`);
      dz.style.setProperty("--f", "1");
      const t = dz.querySelector(".txt");
      if (t) t.textContent = "pago";
      const b = dz.querySelector(".bolinha");
      if (b) {
        b.setAttribute("aria-valuenow", "100");
        b.setAttribute("aria-disabled", "true");
        b.tabIndex = -1;
      }
    }
    const rot = vivo.querySelector(".v-dir small");
    if (rot) rot.textContent = "pago";
    const sub = vivo.querySelector(".v-s span");
    if (sub) sub.textContent = "pago";
  }
  if (D()) {
    D().registrarDesliza("conta_paga", async (dz, vivo, deps) => {
      const res = await postar(deps, `/api/contas-email/${encodeURIComponent(dz.dataset.conta)}/status`, { status: "paga" });
      const msg = vivo && vivo.querySelector(".ce-msg");
      if (!res || !res.ok) {
        if (msg) {
          msg.hidden = false;
          msg.textContent = "Não deu agora. Tenta de novo?";
        }
        return false;
      }
      lembrar(vivo.dataset.feitoChave, { tipo: "paga" });
      D().semRolar(() => {
        contaPagaD(vivo);
        if (msg) {
          msg.hidden = false;
          msg.textContent = "Pago. A tarefa do lembrete também fechou.";
        }
      });
      if (typeof deps.aoMudar === "function") deps.aoMudar();
      return true;
    });
  }

  Cards.registrar("contas_email", (data, card) => {
    if (!data) return null;
    if (data.oculto) {
      return `<div class="sd ce">${olho(I.email, "Achei no e-mail", "")}<p class="cu-nota">${esc(Cards.MOEDA_OCULTA)} · contas ocultas no modo visitante</p></div>`;
    }
    const contas = lista(data.contas).filter((c) => c && c.id && c.nome);
    if (!contas.length) return null;
    if (contas.length === 1 && contas[0].tipo !== "rastreio") return contaD(contas[0], card);
    const linhas = contas
      .map((c, k) => {
        const paga = c.status === "paga";
        const rastreio = c.tipo === "rastreio";
        const valor = rastreio ? "a caminho" : numeroValido(c.valor) ? reais(c.valor) : "—";
        const copia =
          !rastreio && c.codigo && ROTULO_COPIA[c.tipo]
            ? `<button type="button" class="mini ce-copia" data-acao="conta_copiar" data-codigo="${esc(c.codigo)}" data-tipo="${esc(c.tipo)}"><span>${esc(ROTULO_COPIA[c.tipo])}</span></button>`
            : "";
        const rastro = rastreio
          ? `<button type="button" class="mini ce-copia" data-acao="conta_copiar" data-codigo="${esc(c.codigo)}" data-tipo="rastreio"><span>Copiar rastreio</span></button>` +
            `<a class="mini ce-link" href="${URL_CORREIOS}" target="_blank" rel="noopener noreferrer"><span>Ver rastreio</span></a>`
          : "";
        const pago = rastreio
          ? ""
          : `<button type="button" class="mini ce-pago" data-acao="conta_paga" data-conta="${esc(c.id)}"><span>Já paguei</span></button>`;
        return (
          `<div class="ce-conta${paga ? " paga" : ""}" style="--k:${k}" data-conta="${esc(c.id)}" data-feito-chave="${esc(`conta:${c.id}`)}">` +
          `<div class="ce-quem"><b>${esc(c.nome)}</b><small>${esc(quandoVence(c))}</small></div>` +
          `<span class="ce-v">${esc(valor)}</span>` +
          `<div class="ce-acoes">${copia}${rastro}${paga ? "" : pago}</div>` +
          `<p class="ce-msg" hidden></p>` +
          `</div>`
        );
      })
      .join("");
    const lidos = numeroValido(data.lidos) ? data.lidos : null;
    const faixa = lidos !== null ? `Li ${lidos} ${lidos === 1 ? "e-mail" : "e-mails"} · achei ${contas.length}` : `Achei ${contas.length} no e-mail`;
    return (
      `<div class="sd ce">` +
      olho(I.email, "Achei no e-mail", data.varredura ? `varredura ${data.varredura}` : "") +
      `<div class="ce-faixa"><span>${esc(faixa)}</span></div>` +
      `<div class="ce-res">${linhas}</div>` +
      `<p class="sd-status" aria-live="polite"></p>` +
      `</div>`
    );
  });

  // ============================================================== interacoes
  const vibrar = (ms) => typeof raiz.vibrar === "function" && raiz.vibrar(ms);
  const CHAVE_FEITO = "cards-dinheiro-feito";
  function lerFeitos() {
    try {
      const v = JSON.parse(raiz.localStorage.getItem(CHAVE_FEITO) || "{}");
      return v && typeof v === "object" ? v : {};
    } catch (_) {
      return {};
    }
  }
  function lembrar(chave, valor) {
    try {
      const f = lerFeitos();
      f[chave] = valor;
      const chaves = Object.keys(f);
      if (chaves.length > 200) delete f[chaves[0]];
      raiz.localStorage.setItem(CHAVE_FEITO, JSON.stringify(f));
    } catch (_) {
      /* Safari privado / sem storage: so nao lembra */
    }
  }
  const status = (el, icone, texto, classe = "ok") => {
    if (!el) return;
    el.className = `sd-status ${classe}`;
    el.innerHTML = `${icone}<span class="sd-troca">${esc(texto)}</span>`;
  };
  async function postar(deps, url, corpo) {
    if (typeof deps.apiFetch !== "function") return null;
    try {
      return await deps.apiFetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) });
    } catch (_) {
      return null;
    }
  }
  async function copiarTexto(texto) {
    try {
      if (raiz.navigator && raiz.navigator.clipboard && raiz.navigator.clipboard.writeText) {
        await raiz.navigator.clipboard.writeText(texto);
        return true;
      }
    } catch (_) {
      /* cai pro plano B */
    }
    try {
      const ta = raiz.document.createElement("textarea");
      ta.value = texto;
      ta.setAttribute("readonly", "");
      ta.style.cssText = "position:fixed;top:0;left:0;opacity:0";
      raiz.document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, texto.length);
      const ok = raiz.document.execCommand("copy");
      ta.remove();
      return !!ok;
    } catch (_) {
      return false;
    }
  }

  function aplicarFeito(alvo, feito) {
    if (!alvo || !feito) return;
    if (alvo.classList.contains("cu")) {
      const b = alvo.querySelector(".cu-registrar");
      if (b) b.hidden = true;
      status(alvo.querySelector(".sd-status"), I.ok, "Já tá no teu extrato.");
      return;
    }
    if (alvo.classList.contains("vivo-d") && feito.tipo === "paga") {
      contaPagaD(alvo);
      return;
    }
    if (alvo.classList.contains("ce-conta") && feito.tipo === "paga") {
      alvo.classList.add("paga");
      const p = alvo.querySelector(".ce-pago");
      if (p) p.hidden = true;
      const msg = alvo.querySelector(".ce-msg");
      if (msg) {
        msg.hidden = false;
        msg.textContent = "pago · a tarefa do lembrete também fechou";
      }
    }
  }

  function preparar(el) {
    if (!el || !el.querySelectorAll) return;
    const feitos = lerFeitos();
    el.querySelectorAll("[data-feito-chave]").forEach((alvo) => {
      const f = feitos[alvo.dataset.feitoChave];
      if (f) aplicarFeito(alvo, f);
    });
  }

  if (typeof Cards.registrarAcao === "function") {
    Cards.registrarAcao("cupom_registrar", async (btn, _cardEl, deps) => {
      const alvo = btn.closest(".cu");
      if (!alvo || btn.disabled) return;
      btn.disabled = true;
      const res = await postar(deps, `/api/cupons/${encodeURIComponent(btn.dataset.cupom)}/registrar`, {});
      btn.disabled = false;
      if (!res || !res.ok) {
        status(alvo.querySelector(".sd-status"), I.alerta, "Não deu pra registrar agora. Tenta de novo?", "alerta");
        return;
      }
      lembrar(alvo.dataset.feitoChave, { tipo: "registrado" });
      aplicarFeito(alvo, { tipo: "registrado" });
      status(
        alvo.querySelector(".sd-status"),
        I.ok,
        res.vinculado ? "Esse gasto já tava no extrato — juntei com o cupom, sem duplicar." : "Entrou no extrato, em mercado.",
      );
      vibrar([6, 50, 14]);
      if (typeof deps.aoMudar === "function") deps.aoMudar();
    });

    Cards.registrarAcao("conta_copiar", async (btn) => {
      const linha = btn.closest(".ce-conta, .vivo-d");
      const ok = await copiarTexto(btn.dataset.codigo || "");
      const msg = linha && linha.querySelector(".ce-msg");
      const rastreio = btn.dataset.tipo === "rastreio";
      if (msg) {
        msg.hidden = false;
        msg.textContent = ok ? (rastreio ? "código copiado" : "código copiado · o lembrete do vencimento já tá na tua lista") : "não consegui copiar — segura o código e copia na mão";
        msg.classList.toggle("alerta", !ok);
      }
      if (!ok) return;
      btn.classList.add("on");
      const s = btn.querySelector("span");
      if (s) s.textContent = "Copiado";
      else if (btn.closest(".v-bts")) btn.textContent = "Copiado";
      vibrar(8);
    });

    Cards.registrarAcao("conta_paga", async (btn, _cardEl, deps) => {
      const linha = btn.closest(".ce-conta");
      if (!linha || btn.disabled) return;
      btn.disabled = true;
      const res = await postar(deps, `/api/contas-email/${encodeURIComponent(btn.dataset.conta)}/status`, { status: "paga" });
      btn.disabled = false;
      if (!res || !res.ok) {
        const msg = linha.querySelector(".ce-msg");
        if (msg) {
          msg.hidden = false;
          msg.textContent = "não deu agora — tenta de novo?";
        }
        return;
      }
      lembrar(linha.dataset.feitoChave, { tipo: "paga" });
      aplicarFeito(linha, { tipo: "paga" });
      vibrar([6, 50, 14]);
      if (typeof deps.aoMudar === "function") deps.aoMudar();
    });
  }

  const CardsDinheiro = { preparar, aplicarFeito, quandoVence };
  raiz.CardsDinheiro = CardsDinheiro;
  if (typeof module !== "undefined" && module.exports) module.exports = CardsDinheiro;
})(typeof window !== "undefined" ? window : globalThis);
