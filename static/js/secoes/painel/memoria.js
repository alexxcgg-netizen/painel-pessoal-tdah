// static/js/secoes/painel/memoria.js - Secao painel > memoria (HTML: templates/secoes/painel/memoria.html).
// Fase 7 (X2): extraido sem mudanca de logica do antigo app.js 1463-1601.
// Script classico (escopo global compartilhado) - a ordem de carga esta em templates/scripts.html.

const CATEGORIAS_MEMORIA_FIXAS = ["sua_rotina", "seus_planos", "fora_do_painel"];

// Fase 6 (US-E10): item de memoria com "editar" (vira input no lugar do
// texto, Salvar/Cancelar) alem de Apagar - usado tanto nos 3 grupos fixos
// quanto na lista generica "Outras coisas que anotei" (mesmo componente,
// so precisa do id/texto).
function criarItemMemoria(m, onMudou) {
  const li = document.createElement("li");
  li.className = "item";

  const linha = document.createElement("div");
  linha.className = "item-linha";

  const titulo = document.createElement("span");
  titulo.className = "item-titulo";
  titulo.textContent = m.texto;
  linha.appendChild(titulo);

  const acoes = document.createElement("div");
  acoes.className = "item-acoes";

  const editarBtn = document.createElement("button");
  editarBtn.className = "btn-com-icone";
  editarBtn.innerHTML = `${ICONE_CORRIGIR}Editar`;
  editarBtn.addEventListener("click", () => iniciarEdicaoMemoria(m, li, titulo, acoes, editarBtn, apagarBtn, onMudou));

  const apagarBtn = document.createElement("button");
  apagarBtn.className = "btn-com-icone";
  apagarBtn.innerHTML = `${ICONE_TRASH}Apagar`;
  apagarBtn.addEventListener("click", async () => {
    apagarBtn.disabled = true;
    const ok = await apiFetch(`/api/memorias/${m.id}`, { method: "DELETE" });
    if (ok) {
      removerLiAnimado(li);
    } else {
      apagarBtn.disabled = false;
    }
  });

  acoes.appendChild(editarBtn);
  acoes.appendChild(apagarBtn);
  linha.appendChild(acoes);
  li.appendChild(linha);
  return li;
}

function iniciarEdicaoMemoria(m, li, titulo, acoes, editarBtn, apagarBtn, onMudou) {
  const input = document.createElement("input");
  input.type = "text";
  input.value = m.texto;
  input.maxLength = 500;
  input.className = "memoria-edit-input";
  titulo.replaceWith(input);
  input.focus();
  editarBtn.hidden = true;
  apagarBtn.hidden = true;

  const salvarBtn = document.createElement("button");
  salvarBtn.className = "btn-com-icone primario";
  salvarBtn.innerHTML = `${ICONE_CHECK}Salvar`;
  const cancelarBtn = document.createElement("button");
  cancelarBtn.className = "btn-com-icone";
  cancelarBtn.textContent = "Cancelar";

  const sair = () => {
    input.replaceWith(titulo);
    salvarBtn.remove();
    cancelarBtn.remove();
    editarBtn.hidden = false;
    apagarBtn.hidden = false;
  };
  cancelarBtn.addEventListener("click", sair);
  salvarBtn.addEventListener("click", async () => {
    const novoTexto = input.value.trim();
    if (!novoTexto) {
      mostrarErro("O texto não pode ficar vazio.");
      return;
    }
    salvarBtn.disabled = true;
    const r = await apiFetch(`/api/memorias/${m.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texto: novoTexto }),
    });
    if (r) {
      titulo.textContent = novoTexto;
      pulsarSucesso(input);
      sair();
      if (onMudou) onMudou();
    } else {
      salvarBtn.disabled = false;
    }
  });
  acoes.appendChild(salvarBtn);
  acoes.appendChild(cancelarBtn);
}

async function loadMemorias() {
  const memorias = await apiFetch("/api/memorias");
  if (!memorias) return;

  CATEGORIAS_MEMORIA_FIXAS.forEach((categoria) => {
    const lista = $(`#lista-memorias-${categoria}`);
    if (!lista) return;
    lista.innerHTML = "";
    memorias
      .filter((m) => m.categoria === categoria)
      .forEach((m) => lista.appendChild(criarItemMemoria(m, loadMemorias)));
  });

  const outras = memorias.filter((m) => !CATEGORIAS_MEMORIA_FIXAS.includes(m.categoria));
  const list = $("#lista-memorias");
  list.innerHTML = "";
  $("#memorias-vazio").hidden = outras.length > 0;
  outras.forEach((m) => list.appendChild(criarItemMemoria(m, loadMemorias)));
}

document.querySelectorAll(".memoria-add-form").forEach((form) => {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = form.querySelector(".memoria-add-input");
    const texto = input.value.trim();
    if (!texto) return;
    const btn = form.querySelector("button");
    setBotaoCarregando(btn, true, "salvando...");
    const r = await apiFetch("/api/memorias", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texto, categoria: form.dataset.categoria }),
    });
    setBotaoCarregando(btn, false, "Adicionar");
    if (!r) return;
    form.reset();
    pulsarSucesso(input);
    loadMemorias();
  });
});
