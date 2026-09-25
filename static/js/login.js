const modo = document.body.dataset.modo; // "login" ou "configurar"

function configurarGrupo(grupoEl, aoCompletar) {
  const caixas = [...grupoEl.querySelectorAll(".pin-caixa")];

  function valor() {
    return caixas.map((c) => c.value).join("");
  }

  function limpar() {
    caixas.forEach((c) => (c.value = ""));
    caixas[0].focus();
  }

  function marcarPreenchida(caixa) {
    caixa.classList.remove("preenchida");
    // reforca o reflow pra animacao poder rodar de novo em digitos seguidos
    void caixa.offsetWidth;
    caixa.classList.add("preenchida");

    // mostra o digito por um instante (estilo teclado de banco) e depois
    // mascara com -webkit-text-security - so afeta a exibicao, o valor lido
    // por valor()/postJson continua sendo caixa.value normalmente
    caixa.classList.add("mostra-digito");
    clearTimeout(caixa._timerMascara);
    caixa._timerMascara = setTimeout(() => {
      caixa.classList.remove("mostra-digito");
    }, 400);
  }

  caixas.forEach((caixa, i) => {
    caixa.addEventListener("input", () => {
      caixa.value = caixa.value.replace(/[^0-9]/g, "").slice(-1);
      if (caixa.value) {
        marcarPreenchida(caixa);
        if (i < caixas.length - 1) caixas[i + 1].focus();
      }
      if (valor().length === caixas.length) aoCompletar(valor());
    });

    caixa.addEventListener("keydown", (e) => {
      if (e.key === "Backspace" && !caixa.value && i > 0) {
        caixas[i - 1].focus();
      } else if (e.key === "ArrowLeft" && i > 0) {
        caixas[i - 1].focus();
      } else if (e.key === "ArrowRight" && i < caixas.length - 1) {
        caixas[i + 1].focus();
      }
    });

    caixa.addEventListener("paste", (e) => {
      e.preventDefault();
      const colado = (e.clipboardData || window.clipboardData).getData("text").replace(/[^0-9]/g, "");
      if (!colado) return;
      caixas.forEach((c, j) => {
        c.value = colado[j] || "";
        if (c.value) marcarPreenchida(c);
      });
      const proximoVazio = caixas.findIndex((c) => !c.value);
      (proximoVazio === -1 ? caixas[caixas.length - 1] : caixas[proximoVazio]).focus();
      if (valor().length === caixas.length) aoCompletar(valor());
    });
  });

  return { valor, limpar, focar: () => caixas[0].focus() };
}

function mostrarMensagem(el, texto, tipo) {
  el.textContent = texto;
  el.className = "mensagem visivel" + (tipo ? ` ${tipo}` : "");
}

function limparMensagem(el) {
  el.className = "mensagem";
}

function marcarEstado(grupoEl, classe) {
  grupoEl.classList.remove("erro", "sucesso");
  if (classe) grupoEl.classList.add(classe);
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let dados = {};
  try {
    dados = await res.json();
  } catch {
    dados = {};
  }
  return { ok: res.ok, status: res.status, dados };
}

if (modo === "login") {
  const grupo = document.getElementById("pin-grupo");
  const msgEl = document.getElementById("mensagem");
  const esperaEl = document.getElementById("espera");
  const pin = configurarGrupo(grupo, async (valor) => {
    limparMensagem(msgEl);
    esperaEl.hidden = false;
    const { ok, status, dados } = await postJson("/login", { pin: valor });
    esperaEl.hidden = true;

    if (ok) {
      marcarEstado(grupo, "sucesso");
      setTimeout(() => (window.location.href = "/"), 380);
      return;
    }

    marcarEstado(grupo, "erro");
    if (status === 429) {
      document.body.dataset.estado = "bloqueado";
      grupo.querySelectorAll(".pin-caixa").forEach((c) => (c.disabled = true));
    }
    mostrarMensagem(msgEl, dados.error || "Nao foi possivel entrar.", null);
    setTimeout(() => {
      marcarEstado(grupo, null);
      if (document.body.dataset.estado !== "bloqueado") pin.limpar();
    }, 480);
  });
  pin.focar();
}

if (modo === "configurar") {
  const grupoPin = document.getElementById("pin-grupo");
  const grupoConfirmacao = document.getElementById("confirmacao-grupo");
  const msgEl = document.getElementById("mensagem");
  const esperaEl = document.getElementById("espera");

  const pin = configurarGrupo(grupoPin, () => {
    confirmacao.focar();
  });

  const confirmacao = configurarGrupo(grupoConfirmacao, async (valorConfirmacao) => {
    limparMensagem(msgEl);
    esperaEl.hidden = false;
    const { ok, dados } = await postJson("/configurar-pin", {
      pin: pin.valor(),
      confirmacao: valorConfirmacao,
    });
    esperaEl.hidden = true;

    if (ok) {
      marcarEstado(grupoPin, "sucesso");
      marcarEstado(grupoConfirmacao, "sucesso");
      setTimeout(() => (window.location.href = "/"), 380);
      return;
    }

    marcarEstado(grupoPin, "erro");
    marcarEstado(grupoConfirmacao, "erro");
    mostrarMensagem(msgEl, dados.error || "Nao foi possivel salvar o PIN.", null);
    setTimeout(() => {
      marcarEstado(grupoPin, null);
      marcarEstado(grupoConfirmacao, null);
      pin.limpar();
      confirmacao.limpar();
      pin.focar();
    }, 480);
  });

  pin.focar();
}
