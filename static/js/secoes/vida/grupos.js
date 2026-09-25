// static/js/secoes/vida/grupos.js - Fase 9 C4 (faixa "Vida").
// Navegacao por grupo da aba Vida (direcao "Conversa", variante "Grupos" -
// docs/fase9-lab3/v03.js). NAO reimplementa nenhuma secao: so mostra/esconde
// os wrappers [data-grupo-secao] que templates/abas/vida.html declara em
// volta de cada include existente (habitos, treino, saude-hoje, etc.) e le o
// mapeamento grupo->ids do <script type="application/json" id="vida-grupos-dados">
// dentro de templates/secoes/vida/grupos.html.
//
// Contrato pro integrador (static/js/nucleo/navegacao.js, arquivo que esta
// faixa NAO edita): `showTab("aviacao")` hoje rola ate #secao-aviacao. Pra
// isso continuar funcionando com a aba em grupos, o trecho que faz
// `alvo.scrollIntoView(...)` em ROLAR_ATE_SECAO deve, antes de rolar, tentar
// `window.VidaGrupos && window.VidaGrupos.abrirSecao(idSecao)` - a funcao
// devolve `true` quando reconheceu o id (ai ela mesma cuida de abrir o grupo,
// mostrar a secao e rolar) e `false` quando o id nao e um dos ~30 desta aba
// (o chamador cai de volta pro scrollIntoView de sempre).
(function () {
  "use strict";

  const CHAVE_LS = "vida-grupo-aberto";

  const ICONES = {
    aviacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v16M12 9 3 14M12 9l9 5M12 16l-4 3M12 16l4 3"/></svg>',
    rotina: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8v4l2.5 2.5"/><circle cx="12" cy="13" r="8"/><path d="M9 2h6M12 2v3"/></svg>',
    saude: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l1.5-4L12 17l2-8 1.5 3H21"/></svg>',
    pessoas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M2.8 20c.7-3.4 3.2-5.4 6.2-5.4s5.5 2 6.2 5.4"/><circle cx="17.5" cy="8.5" r="2.4"/><path d="M15.8 14.8c2.2.4 4 2.1 4.6 5.2"/></svg>',
    coisas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 8.5 12 4l8.5 4.5L12 13z"/><path d="M3.5 8.5V16L12 20.5 20.5 16V8.5"/><path d="M12 13v7.5"/></svg>',
    mundo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18Z"/></svg>',
    mente: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.5.4.8 1 .8 1.6v.5h5.4v-.5c0-.6.3-1.2.8-1.6A6 6 0 0 0 12 3Z"/></svg>',
    secao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
    chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>'
  };

  function lerLS(chave) {
    try {
      return window.localStorage.getItem(chave);
    } catch (e) {
      return null;
    }
  }
  function gravarLS(chave, valor) {
    try {
      window.localStorage.setItem(chave, valor);
    } catch (e) {
      /* modo privado / storage bloqueado - navegacao continua funcionando sem lembrar */
    }
  }

  // Conta elementos de conteudo ja no DOM dentro do wrapper de uma secao -
  // nunca um numero inventado: se a secao ainda nao carregou via fetch (a
  // maioria usa load*() assincrono disparado por showTab("vida")), a barra
  // fica baixa/zerada ate a proxima recontagem, o que e honesto.
  function contarItensReais(wrapper) {
    if (!wrapper) return 0;
    return wrapper.querySelectorAll(
      "li, .lista-item, .convrow, .linha, tr, .assinrow, .li, [class*='-linha'], [class*='-item']:not(.chip)"
    ).length;
  }

  function montarBarras(valores) {
    const w = 130, h = 28, n = Math.max(valores.length, 1);
    const max = Math.max.apply(null, valores.concat([1]));
    const bw = w / n - 3;
    let out = "";
    for (let i = 0; i < valores.length; i++) {
      const v = valores[i];
      const bh = Math.max((v / max) * (h - 4), 2);
      out += '<rect x="' + (i * (w / n)).toFixed(1) + '" y="' + (h - bh).toFixed(1) +
        '" width="' + bw.toFixed(1) + '" height="' + bh.toFixed(1) + '" rx="2"></rect>';
    }
    return '<svg viewBox="0 0 ' + w + ' ' + h + '" class="vg-grafico" role="img" aria-label="Seções com conteúdo neste grupo">' + out + "</svg>";
  }

  function iniciar() {
    const raiz = document.getElementById("vida-grupos");
    if (!raiz) return;
    const dadosEl = document.getElementById("vida-grupos-dados");
    if (!dadosEl) return;

    let dados;
    try {
      dados = JSON.parse(dadosEl.textContent);
    } catch (e) {
      return;
    }
    const grupos = dados.grupos || [];
    const nomes = dados.nomes || {};
    const porChave = {};
    grupos.forEach(function (g) { porChave[g.chave] = g; });
    const grupoDoId = {};
    grupos.forEach(function (g) {
      (g.ids || []).forEach(function (id) { grupoDoId[id] = g.chave; });
    });

    const grade = document.getElementById("vg-grade");
    const areaGrupoAberto = document.getElementById("vg-grupo-aberto");
    const tituloGrupoAberto = document.getElementById("vg-grupo-aberto-titulo");
    const listaGrupoAberto = document.getElementById("vg-grupo-aberto-lista");
    const areaSecaoAberta = document.getElementById("vg-secao-aberta");
    const btnVoltar = document.getElementById("vg-voltar-btn");

    function wrapperDaSecao(id) {
      // #secao-aviacao ja e o proprio <section id="..."> (vida.html so
      // acrescenta [hidden] e data-grupo-secao nele, sem wrapper extra); as
      // demais ~29 secoes ganham um <div data-grupo-secao="..."> em volta.
      return document.getElementById(id) || document.querySelector('[data-grupo-secao="' + id + '"]');
    }

    function esconderTudoExceto(idVisivel) {
      grupos.forEach(function (g) {
        (g.ids || []).forEach(function (id) {
          const el = wrapperDaSecao(id);
          if (!el) return;
          el.hidden = id !== idVisivel;
        });
      });
    }

    function recontarGrupo(chave) {
      const g = porChave[chave];
      if (!g) return [];
      return (g.ids || []).map(function (id) { return contarItensReais(wrapperDaSecao(id)); });
    }

    function atualizarContadoresCartoes() {
      grupos.forEach(function (g) {
        const cartao = grade.querySelector('[data-grupo="' + g.chave + '"]');
        if (!cartao) return;
        const graf = cartao.querySelector(".vg-grafico-slot");
        if (graf) graf.innerHTML = montarBarras(recontarGrupo(g.chave));
      });
    }

    function renderCartoes() {
      grade.innerHTML = grupos.map(function (g) {
        const n = (g.ids || []).length;
        return (
          '<button type="button" class="vg-cartao' + (g.destaque ? " vg-cartao--destaque" : "") +
          '" data-grupo="' + g.chave + '" role="listitem" aria-expanded="false" aria-controls="vg-grupo-aberto">' +
          '<span class="vg-cartao-icone" aria-hidden="true">' + (ICONES[g.chave] || ICONES.secao) + "</span>" +
          '<span class="vg-cartao-corpo">' +
          '<span class="vg-cartao-nome">' + g.nome + "</span>" +
          '<span class="vg-cartao-contador">' + n + (n === 1 ? " seção" : " seções") + "</span>" +
          "</span>" +
          '<span class="vg-grafico-slot"></span>' +
          "</button>"
        );
      }).join("");
      grade.querySelectorAll(".vg-cartao").forEach(function (btn) {
        btn.addEventListener("click", function () { abrirGrupo(btn.dataset.grupo); });
      });
      atualizarContadoresCartoes();
    }

    function marcarCartaoAtivo(chave) {
      grade.querySelectorAll(".vg-cartao").forEach(function (btn) {
        const ativo = btn.dataset.grupo === chave;
        btn.classList.toggle("vg-cartao--ativo", ativo);
        btn.setAttribute("aria-expanded", String(ativo));
      });
    }

    function abrirGrupo(chave, semGravar) {
      const g = porChave[chave];
      if (!g) return;
      esconderTudoExceto(null);
      areaSecaoAberta.hidden = true;
      marcarCartaoAtivo(chave);
      tituloGrupoAberto.textContent = g.nome + ": " + g.ids.length + (g.ids.length === 1 ? " seção." : " seções.");
      listaGrupoAberto.innerHTML = g.ids.map(function (id) {
        return (
          '<button type="button" class="vg-linha" data-id="' + id + '" role="listitem">' +
          '<span class="vg-linha-icone" aria-hidden="true">' + ICONES.secao + "</span>" +
          '<span class="vg-linha-nome">' + (nomes[id] || id) + "</span>" +
          ICONES.chevron +
          "</button>"
        );
      }).join("");
      listaGrupoAberto.querySelectorAll(".vg-linha").forEach(function (row) {
        row.addEventListener("click", function () { abrirSecao(row.dataset.id); });
      });
      areaGrupoAberto.hidden = false;
      gravarLS(CHAVE_LS, chave);
    }

    function fecharParaGrupos() {
      areaSecaoAberta.hidden = true;
      const chaveAtual = lerLS(CHAVE_LS);
      if (chaveAtual && porChave[chaveAtual]) abrirGrupo(chaveAtual);
      atualizarContadoresCartoes();
    }

    // abrirSecao: contrato publico (window.VidaGrupos.abrirSecao) usado pelo
    // deep link de #secao-aviacao e por qualquer chip/atalho interno que
    // queira pular direto pra uma secao. Devolve true/false pro chamador
    // saber se o id pertence a esta aba (ver navegacao.js no topo do arquivo).
    function abrirSecao(id) {
      const chave = grupoDoId[id];
      const el = wrapperDaSecao(id);
      if (!chave || !el) return false;
      // Nao move o wrapper no DOM: so ele fica visivel (esconderTudoExceto),
      // os outros ~29 somem (display:none via [hidden]) - como o wrapper
      // alvo pode estar em qualquer lugar entre #secao-aviacao e
      // .vida-secoes, o botao "Voltar aos grupos" (#vg-secao-aberta, fixo
      // logo acima dessa faixa) acaba sempre colado nele, sem precisar
      // reparentar nada.
      abrirGrupo(chave);
      esconderTudoExceto(id);
      areaGrupoAberto.hidden = false;
      areaSecaoAberta.hidden = false;
      if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      } else {
        el.scrollIntoView({ block: "start" });
      }
      return true;
    }

    btnVoltar.addEventListener("click", fecharParaGrupos);

    renderCartoes();

    // Estado inicial: so os grupos, nada de secao aberta (regra do briefing -
    // a aba nao rola infinito). Se houver um grupo lembrado do localStorage,
    // a lista dele ja vem expandida (mais rapido pra quem sempre olha o
    // mesmo grupo), mas nenhuma secao individual abre sozinha.
    const chaveLembrada = lerLS(CHAVE_LS);
    if (chaveLembrada && porChave[chaveLembrada]) marcarCartaoAtivo(chaveLembrada);

    // Deep link por hash (ex.: alguem abre o app direto em #secao-aviacao).
    // O caminho via showTab("aviacao") chama window.VidaGrupos.abrirSecao
    // direto (ver navegacao.js) e nao depende do hash.
    if (location.hash === "#secao-aviacao") abrirSecao("secao-aviacao");

    // Recontagem honesta: varias secoes so preenchem a lista depois de um
    // fetch assincrono (loadHabitos(), loadSaude()...) disparado quando a
    // aba Vida e mostrada. Reconta quando a aba fica visivel e mais uma vez
    // pouco depois (cobre os fetches que ainda estao em voo).
    const tabVida = document.getElementById("tab-vida");
    if (tabVida && "MutationObserver" in window) {
      const obs = new MutationObserver(function () {
        if (!tabVida.hidden) {
          atualizarContadoresCartoes();
          setTimeout(atualizarContadoresCartoes, 900);
        }
      });
      obs.observe(tabVida, { attributes: true, attributeFilter: ["hidden"] });
    }

    window.VidaGrupos = { abrirSecao: abrirSecao, abrirGrupo: abrirGrupo, fecharParaGrupos: fecharParaGrupos };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
