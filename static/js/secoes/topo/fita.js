// static/js/secoes/topo/fita.js - Fita do tempo (Grupo B da leva do Laboratorio v4, demo "fita"): uma fita fina no topo
// do app que vai encolhendo ate o proximo compromisso ("Sair pra academia em 1h40"). Nos ultimos 15 min muda de cor;
// na hora de sair, pulsa. Um toque esconde pelo resto do dia.
//
// O servidor manda SEGUNDOS ate sair/ate o compromisso (`GET /api/tempo/fita`), nunca a hora do relogio: o servidor
// pode estar em outro fuso que o celular. O resto e conta local, a cada 20 s. Script classico (ordem em
// templates/scripts.html); `textoDaFita` e puro e testavel no Node.

(function (raiz) {
  "use strict";

  const PERTO_MIN = 15;
  const TICK_MS = 20000;
  const BUSCA_MS = 5 * 60000;

  // 100 -> "1h40"; 45 -> "45 min"; sempre arredonda pra cima (nunca "0 min" antes da hora)
  function dur(min) {
    min = Math.max(1, Math.ceil(min));
    const h = Math.floor(min / 60);
    const m = min % 60;
    return h ? `${h}h${m ? String(m).padStart(2, "0") : ""}` : `${m} min`;
  }
  // "Academia" -> "academia", mas "CIV" e "Voo" nao: so baixa a 1a letra quando a 2a nao e maiuscula
  const minuscula = (t) => (t.length > 1 && t[1] === t[1].toUpperCase() && t[1] !== t[1].toLowerCase() ? t : t.charAt(0).toLowerCase() + t.slice(1));

  // f = resposta do servidor; passou_s = quanto tempo a pagina esta com essa resposta
  function textoDaFita(f, passou_s) {
    const sair = f.sair_em_s - passou_s;
    const evento = f.evento_em_s - passou_s;
    const nome = String(f.titulo || "Compromisso");
    const janela = (f.janela_min || 180) * 60;
    let estado = "normal";
    let texto;
    if (f.tem_saida) {
      if (sair > 0) texto = `Sair pra ${minuscula(nome)} em ${dur(sair / 60)}`;
      else if (evento > 0) texto = `Hora de sair. ${nome} às ${f.hora}`;
      else texto = `${nome} agora`;
      if (sair <= 0) estado = "ja";
      else if (sair / 60 <= PERTO_MIN) estado = "perto";
    } else {
      if (evento > 0) texto = `${nome} em ${dur(evento / 60)}`;
      else texto = `${nome} agora`;
      if (evento <= 0) estado = "ja";
      else if (evento / 60 <= PERTO_MIN) estado = "perto";
    }
    const falta = f.tem_saida ? sair : evento;
    return { texto, estado, p: Math.max(0, Math.min(1, falta / janela)) };
  }

  const hojeChave = () => {
    const d = new Date();
    return `fita-escondida-${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  };
  function escondida() {
    try {
      return raiz.localStorage.getItem(hojeChave()) === "1";
    } catch (e) {
      return false;
    }
  }
  function esconder() {
    try {
      raiz.localStorage.setItem(hojeChave(), "1");
    } catch (e) {
      /* sem armazenamento: esconde so ate recarregar */
    }
  }

  const estadoFita = { dados: null, t0: 0, timer: null, busca: null, ultimoTexto: "" };

  function pintar() {
    const el = raiz.document && raiz.document.getElementById("fita-tempo");
    if (!el) return;
    const f = estadoFita.dados;
    if (!f || escondida()) {
      el.hidden = true;
      return;
    }
    const r = textoDaFita(f, (Date.now() - estadoFita.t0) / 1000);
    // passou 5 min do horario do compromisso: some e pergunta de novo ao servidor (pode haver outro)
    if (f.evento_em_s - (Date.now() - estadoFita.t0) / 1000 < -300) {
      estadoFita.dados = null;
      buscar();
      el.hidden = true;
      return;
    }
    el.hidden = false;
    el.classList.remove("some");
    el.classList.toggle("perto", r.estado === "perto");
    el.classList.toggle("ja", r.estado === "ja");
    el.querySelector("i").style.transform = `scaleX(${r.p.toFixed(4)})`;
    if (r.texto !== estadoFita.ultimoTexto) {
      const txt = el.querySelector(".fita-txt");
      txt.innerHTML = "";
      const s = raiz.document.createElement("span");
      s.textContent = r.texto;
      txt.appendChild(s);
      estadoFita.ultimoTexto = r.texto;
    }
    el.setAttribute("aria-label", `${r.texto}. Toca pra esconder até amanhã.`);
  }

  async function buscar() {
    if (typeof raiz.fetch !== "function") return;
    try {
      // fetch direto (nao o apiFetch): a fita pergunta sozinha de tempos em tempos e nao pode abrir toast de erro offline
      const resp = await raiz.fetch("/api/tempo/fita", { credentials: "same-origin" });
      const r = resp.ok ? await resp.json() : null;
      estadoFita.dados = r && r.fita ? r.fita : null;
      estadoFita.t0 = Date.now();
      estadoFita.ultimoTexto = "";
    } catch (e) {
      estadoFita.dados = null;
    }
    pintar();
  }

  function iniciar() {
    const el = raiz.document && raiz.document.getElementById("fita-tempo");
    if (!el || el.dataset.ligada) return;
    el.dataset.ligada = "1";
    el.setAttribute("role", "button");
    el.tabIndex = 0;
    el.innerHTML = '<i aria-hidden="true"></i><span class="fita-txt"></span>';
    const some = () => {
      esconder();
      el.classList.add("some");
      setTimeout(() => (el.hidden = true), 450);
    };
    el.addEventListener("click", some);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        some();
      }
    });
    buscar();
    estadoFita.timer = setInterval(pintar, TICK_MS);
    estadoFita.busca = setInterval(buscar, BUSCA_MS);
    raiz.document.addEventListener("visibilitychange", () => {
      if (!raiz.document.hidden) buscar();
    });
  }

  if (raiz.document) {
    if (raiz.document.readyState === "loading") raiz.document.addEventListener("DOMContentLoaded", iniciar);
    else iniciar();
  }

  const FitaTempo = { textoDaFita, dur, minuscula, iniciar };
  raiz.FitaTempo = FitaTempo;
  if (typeof module !== "undefined" && module.exports) module.exports = FitaTempo;
})(typeof window !== "undefined" ? window : globalThis);
