// Foto no chat (2026-10-13, pedido do Alex: "mandar uma foto de um prato de comida e ela ver o que
// tem ali e dar uma media em gramas, carboidratos, proteinas... facil e pratico").
// Camera ao lado do campo -> escolhe/tira a foto -> reduz no celular (~1280 px, JPEG) pra subir
// rapido -> POST /api/chat/foto (rotas/chat.py). A resposta vem no mesmo contrato do chat (texto +
// card `refeicao`, com Desfazer). Se escreveu algo no campo antes ("so comi metade"), vai junto.
// A foto nao fica guardada no servidor - a miniatura so existe nesta tela.

const FOTO_LADO_MAX = 1280;
const FOTO_QUALIDADE = 0.82;

function carregarImagem(arquivo) {
  return new Promise((ok, falha) => {
    const url = URL.createObjectURL(arquivo);
    const img = new Image();
    img.onload = () => ok({ img, url });
    img.onerror = () => {
      URL.revokeObjectURL(url);
      falha(new Error("imagem ilegivel"));
    };
    img.src = url;
  });
}

// devolve {blob, url} - blob reduzido (ou o original se nao der pra redesenhar) e uma URL pra
// miniatura da bolha
async function prepararFoto(arquivo) {
  let carregada;
  try {
    carregada = await carregarImagem(arquivo);
  } catch {
    return { blob: arquivo, url: null };
  }
  const { img, url } = carregada;
  const lado = Math.max(img.naturalWidth, img.naturalHeight);
  if (!lado) return { blob: arquivo, url };
  const escala = Math.min(1, FOTO_LADO_MAX / lado);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(img.naturalWidth * escala);
  canvas.height = Math.round(img.naturalHeight * escala);
  const ctx = canvas.getContext("2d");
  if (!ctx) return { blob: arquivo, url };
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((ok) => canvas.toBlob(ok, "image/jpeg", FOTO_QUALIDADE));
  return { blob: blob && blob.size < arquivo.size ? blob : arquivo, url };
}

function criarBolhaFoto(url, legenda) {
  const linha = document.createElement("div");
  linha.className = "chat-linha user";
  const bolha = document.createElement("div");
  bolha.className = "chat-bolha user chat-bolha-foto";
  if (url) {
    const img = document.createElement("img");
    img.className = "chat-foto-mini";
    img.alt = "Foto do prato";
    img.decoding = "async";
    img.src = url;
    bolha.appendChild(img);
  }
  const txt = document.createElement("span");
  txt.textContent = legenda || (url ? "" : "📷 Foto do prato");
  if (txt.textContent) bolha.appendChild(txt);
  linha.appendChild(bolha);
  return linha;
}

function criarIndicadorAnalisando() {
  const linha = criarIndicadorDigitando();
  const bolha = linha.querySelector(".chat-bolha");
  const rotulo = document.createElement("span");
  rotulo.className = "chat-digitando-rotulo";
  rotulo.textContent = "olhando o prato…";
  bolha.appendChild(rotulo);
  return linha;
}

async function enviarFotoChat(arquivo) {
  const lista = $("#chat-mensagens");
  const input = $("#chat-input");
  const btn = $("#chat-foto");
  const vazio = lista.querySelector(".chat-vazio");
  if (vazio) vazio.remove();

  const legenda = input.value.trim().slice(0, 500);
  input.value = "";
  btn.disabled = true;
  btn.classList.add("enviando");

  const { blob, url } = await prepararFoto(arquivo);
  lista.appendChild(criarBolhaFoto(url, legenda));
  const analisando = criarIndicadorAnalisando();
  lista.appendChild(analisando);
  lista.scrollTop = lista.scrollHeight;

  const corpo = new FormData();
  const tipo = blob.type || arquivo.type || "image/jpeg";
  corpo.append("imagem", blob, tipo === "image/jpeg" ? "prato.jpg" : arquivo.name || "prato");
  if (legenda) corpo.append("texto", legenda);
  let data = null;
  try {
    data = await apiFetch("/api/chat/foto", { method: "POST", body: corpo });
  } finally {
    analisando.remove();
    btn.disabled = false;
    btn.classList.remove("enviando");
  }
  if (!data) return null;

  lista.appendChild(criarBolhaChat("assistant", data.resumo_texto || data.resposta, true));
  const grupoCards = anexarCardsResposta(lista, data.cards, data.passos, true);
  if (grupoCards && typeof CardsVivos !== "undefined") CardsVivos.animar(grupoCards);
  lista.scrollTop = lista.scrollHeight;
  if (data.acoes && data.acoes.length > 0) {
    vibrar(20);
    tocarSomSucesso();
  }
  return data;
}

function initFotoChat() {
  const btn = $("#chat-foto");
  const campo = $("#chat-foto-arquivo");
  if (!btn || !campo) return;
  btn.addEventListener("click", () => {
    if (btn.disabled) return;
    campo.value = "";
    campo.click();
  });
  campo.addEventListener("change", () => {
    const arquivo = campo.files && campo.files[0];
    if (!arquivo) return;
    if (arquivo.type && !arquivo.type.startsWith("image/")) {
      mostrarErro("Isso não é uma foto.");
      return;
    }
    enviarFotoChat(arquivo);
  });
}

initFotoChat();
