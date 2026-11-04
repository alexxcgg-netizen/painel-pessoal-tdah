import os
import threading

from waitress import serve

try:
    from playwright.sync_api import Browser, BrowserType
except ImportError:
    Browser = BrowserType = None

# Teste nenhum sai da maquina: o bloqueio do conftest nao alcanca o Chromium, que e outro processo.
# Sem isso, quem nao barrava na mao ia buscar a fonte no Google a cada pagina aberta. Fica aqui, e
# nao no conftest, pra fila sem navegador nao pagar os 200 ms de importar o Playwright.
if BrowserType is not None:
    _launch_real = BrowserType.launch

    def _launch_so_local(self, **kwargs):
        regra = "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1"
        kwargs["args"] = [*(kwargs.get("args") or []), regra]
        return _launch_real(self, **kwargs)

    BrowserType.launch = _launch_so_local

    # Contexto novo = service worker instalando do zero, e o `cache.addAll` dele abre uma conexao por
    # arquivo (medido: ~220 por teste, ver `subir_servidor`). Ele so mexe em /static/, nao em dado.
    # Quem confere o service worker de verdade pede `service_workers="allow"`.
    _contexto_real = Browser.new_context

    def _contexto_sem_sw(self, **kwargs):
        kwargs.setdefault("service_workers", "block")
        return _contexto_real(self, **kwargs)

    Browser.new_context = _contexto_sem_sw


def subir_servidor(app, porta):
    """Sobe o app numa thread com o waitress, o mesmo servidor do painel.

    Nao usar `app.run`: o servidor do Flask fecha a conexao a cada pedido e uma pagina daqui puxa
    centenas de arquivos. A fila do navegador passava de 17 mil conexoes em TIME_WAIT, o Windows tem
    16.384 portas de saida e segura cada uma por 30 s: script deixava de carregar ao acaso.
    Pelo mesmo motivo os contextos nascem sem service worker, ver `_contexto_sem_sw`.
    """
    threading.Thread(target=lambda: serve(app, host="127.0.0.1", port=porta, threads=16, _quiet=True), daemon=True).start()


def get_chrome_path():
    linux_paths = [
        "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
        "/opt/pw-browsers/chromium"
    ]
    for path in linux_paths:
        if os.path.exists(path):
            return path
    return None


# R1 (reformulacao): a barra de baixo passou a ter 5 itens (hoje, tarefas,
# assistente, gastos, mais). painel, vida, aviacao, construtora (e as telas
# novas ajustes-ia/config) sairam da barra e abrem pela tela Mais. Testes que
# abriam essas abas clicando no .tab-btn delas usam estes helpers: clique de
# verdade no botao da barra quando ele existe; senao, abre o Mais e toca na
# linha que abre a tela (mesmo showTab() por baixo).
BARRA_R1 = ["hoje", "tarefas", "assistente", "gastos", "mais"]


def abrir_tela(page, aba):
    if page.locator(f'.tab-btn[data-tab="{aba}"]').count():
        page.click(f'.tab-btn[data-tab="{aba}"]')
    else:
        page.click('.tab-btn[data-tab="mais"]')
        page.click(f'#tab-mais [data-abre-tela="{aba}"]:not([data-alvo])')


def js_clicar_aba(aba):
    """Expressao JS que clica (via .click(), sem esperar visibilidade - pra troca
    rapida em sequencia) no botao da barra da aba ou na linha do Mais que a abre."""
    return (
        f"(document.querySelector('.tab-btn[data-tab=\"{aba}\"]')"
        f" || document.querySelector('#tab-mais [data-abre-tela=\"{aba}\"]:not([data-alvo])')).click()"
    )


def item_da_barra(aba):
    """Item da barra que fica ativo com `aba` aberta (telas do Mais -> "mais")."""
    return aba if aba in BARRA_R1 else "mais"


# Um quadro com limite: se a pagina parar de desenhar (requestAnimationFrame trocado, aba escondida)
# o erro sai na hora certa, em vez de o `page.evaluate` esperar pra sempre.
_QUADRO = """const quadro = (erro) => new Promise((pronto, falhou) => {
    const limite = setTimeout(() => falhou(new Error(erro)), Math.max(0, fim - performance.now()));
    requestAnimationFrame(() => { clearTimeout(limite); pronto(); });
  });"""

_ASSENTAR = """async ([seletor, limite]) => {
  const fim = performance.now() + limite;
  const erro = `${seletor} nao assentou em ${limite} ms`;
  """ + _QUADRO + """
  const foto = () => {
    const els = [...document.querySelectorAll(seletor)];
    if (!els.length) return null;
    const rodando = els.some((el) => el.getAnimations({ subtree: true }).some(
      (a) => a.playState === "running" && a.effect.getComputedTiming().iterations !== Infinity));
    if (rodando) return null;
    const rolagem = document.scrollingElement;
    const caixas = els.map((el) => {
      const r = el.getBoundingClientRect();
      return [r.x, r.y, r.width, r.height];
    });
    return JSON.stringify([caixas, rolagem.scrollLeft, rolagem.scrollTop]);
  };
  let anterior = null, iguais = 0;
  while (iguais < 6) {
    await quadro(erro);
    const agora = foto();
    iguais = agora !== null && agora === anterior ? iguais + 1 : 0;
    anterior = agora;
    if (performance.now() > fim) throw new Error(erro);
  }
}"""


def esperar_assentar(page, seletor="body", timeout=30000):
    """Espera a tela parar: nenhuma animacao/transicao finita rodando em nenhum elemento de
    `seletor` (e filhos) e posicao + rolagem iguais por 6 quadros seguidos. Termina assim que
    assenta, em vez de um `wait_for_timeout` fixo que sobra no PC livre e falta no PC cheio.
    Seletor sem elemento nao conta como parado: estoura `timeout`."""
    page.evaluate(_ASSENTAR, [seletor, timeout])


# Conta os fetch abertos, do disparo ao corpo lido, e guarda a URL de cada JSON entregue. Depois
# do showTab o networkidle do Playwright nao serve: so dispara uma vez por navegacao. fetch e
# json() viram uma corrente sem buraco: um termina e o outro comeca na mesma leva de microtarefas.
CONTAR_FETCH = r"""
(() => {
  let abertos = 0;
  window.__jsonLidos = [];
  window.__fetchesAbertos = () => abertos;
  const contar = (promessa, aoFim) => {
    abertos++;
    const fim = () => { abertos--; if (aoFim) aoFim(); };
    promessa.then(fim, fim);
    return promessa;
  };
  const fetchReal = window.fetch;
  const jsonReal = Response.prototype.json;
  window.fetch = (...args) => contar(fetchReal(...args));
  Response.prototype.json = function () {
    return contar(jsonReal.call(this), () => window.__jsonLidos.push(this.url));
  };
})();
"""

_CARGA_ACABOU = """async (limite) => {
  const fim = performance.now() + limite;
  const erro = `carga nao acabou em ${limite} ms`;
  """ + _QUADRO + """
  let parados = 0;
  while (parados < 6) {
    await quadro(erro);
    parados = window.__fetchesAbertos() === 0 ? parados + 1 : 0;
    if (performance.now() > fim) throw new Error(erro);
  }
}"""


def esperar_carga(page, timeout=30000):
    """Espera as cargas da tela acabarem (precisa de `add_init_script(CONTAR_FETCH)`). Os loaders
    do showTab saem depois de um rAF + setTimeout(0) e nao marcam nada no DOM: zero fetch aberto so
    vale por quadros seguidos. Sem isso um erro ao desenhar a resposta nem chega em `pageerror`."""
    page.evaluate(_CARGA_ACABOU, timeout)
