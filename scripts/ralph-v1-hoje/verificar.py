"""Verificacao V1-hoje (acabamento da aba Hoje + topo + brain dump) no Playwright
headless 390x844. Mesmo padrao de scripts/ralph-v0c-secoes/verificar.py.

Confere:
- zero erro de console/pageerror (fora as falhas de ambiente conhecidas: fontes
  externas e /api/summary/today sem chave de IA real, ver AMBIENTE abaixo);
- aba Hoje abre por padrao (sem clique), #caixa-assistente continua no topo antes
  de #saudacao-texto;
- cards novos (assinatura, compra_parcelada, resumo_financeiro_recorrente)
  renderizam via Cards.criarGrupo (mesmo pipeline do chat) sem virar fallback;
- brain-dump (aba Painel): o botao "Processar" por item NAO existe mais
  (id/classe antigos), "Guardar" continua existindo;
- 2 screenshots (Hoje e brain-dump) em scripts/ralph-v1-hoje/.

Uso: PORTA=5113 python scripts/ralph-v1-hoje/verificar.py
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5113")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

# Injeta um card de cada tipo novo dentro de #chat-mensagens usando o MESMO
# pipeline de renderizacao do chat (Cards.criarGrupo) - sem endpoint novo,
# so pra conferir visualmente o acabamento dos 3 tipos novos de uma vez.
INJETAR_CARDS = """() => {
  if (typeof Cards === 'undefined') return {ok: false, motivo: 'Cards indefinido'};
  const lista = document.querySelector('#chat-mensagens');
  if (!lista) return {ok: false, motivo: '#chat-mensagens nao encontrado'};
  const cards = [
    { type: 'assinatura', id: 'v1-a1', data: {
        nome: 'Netflix', valor: 44.9, dia_cobranca: 12, proxima_cobranca: '2026-10-12',
        em_dias: 18, cartao: 'Nubank', categoria: 'streaming', ativa: true },
      actions: [{ tipo: 'desfazer', rotulo: 'Desfazer', token: 'tok-v1-a1', alvo: [] }] },
    { type: 'compra_parcelada', id: 'v1-a2', data: {
        descricao: 'Notebook', valor_parcela: 350, parcela_atual: 3, n_parcelas: 10,
        restantes: 7, termina_em: '2027-05-15', cartao: 'Itau' },
      actions: [{ tipo: 'desfazer', rotulo: 'Desfazer', token: 'tok-v1-a2', alvo: [] }] },
    { type: 'resumo_financeiro_recorrente', id: 'v1-a3', data: {
        total_mes: 612.4, n_assinaturas: 4, n_parcelas: 2,
        proxima_cobranca: { nome: 'Netflix', data: '2026-10-01' } }, actions: [] },
  ];
  const grupo = Cards.criarGrupo(cards, []);
  grupo.id = 'v1-verificacao-cards';
  lista.appendChild(grupo);
  return { ok: true, tipos: cards.map((c) => c.type) };
}"""

MEDIR_CARDS = """() => {
  const raiz = document.querySelector('#v1-verificacao-cards');
  if (!raiz) return { achou: false };
  const artigos = Array.from(raiz.querySelectorAll('.card-contrato'));
  return {
    achou: true,
    total: artigos.length,
    tipos: artigos.map((a) => a.dataset.cardType),
    algum_fallback: artigos.some((a) => a.classList.contains('card-contrato-fallback')),
    tem_desfazer: artigos.filter((a) => a.querySelector('[data-acao="desfazer"]')).length,
    textos: artigos.map((a) => (a.querySelector('.card-titulo') || {}).textContent || null),
  };
}"""

erros, falhas_rede = [], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    r = ctx.request.post(
        BASE + "/configurar-pin",
        data=json.dumps({"pin": "135790", "confirmacao": "135790"}),
        headers={"Content-Type": "application/json"},
    )
    if r.status != 200:
        r = ctx.request.post(
            BASE + "/login", data=json.dumps({"pin": "135790"}), headers={"Content-Type": "application/json"}
        )
    assert r.status == 200, r.text()
    page = ctx.new_page()
    page.on("console", lambda m: erros.append(("console." + m.type, m.text)) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(("pageerror", str(e))))
    page.on("response", lambda resp: falhas_rede.append((resp.status, resp.url)) if resp.status >= 400 else None)
    page.on("requestfailed", lambda req: falhas_rede.append(("falhou", req.url)))

    page.goto(BASE + "/")
    page.wait_for_load_state("networkidle")
    time.sleep(1.0)

    # Hoje ja abre por padrao (templates/abas/hoje.html sem `hidden`).
    hoje_visivel = page.eval_on_selector("#tab-hoje", "el => !el.hidden")
    ordem_dom = page.evaluate(
        "() => { const wrap = document.querySelector('#tab-hoje');"
        " const ids = Array.from(wrap.children).map((el) => el.id || el.tagName);"
        " return ids; }"
    )
    caixa_antes_saudacao = page.evaluate(
        "() => { const caixa = document.querySelector('#caixa-assistente');"
        " const saud = document.querySelector('#saudacao-texto');"
        " if (!caixa || !saud) return null;"
        " return !!(caixa.compareDocumentPosition(saud) & Node.DOCUMENT_POSITION_FOLLOWING); }"
    )

    injecao = page.evaluate(INJETAR_CARDS)
    assert injecao.get("ok"), injecao
    time.sleep(0.4)
    medidas_cards = page.evaluate(MEDIR_CARDS)

    time.sleep(0.3)
    page.screenshot(path=os.path.join(AQUI, "v1-hoje.png"), full_page=True, animations="disabled")

    # Brain dump mora na aba Painel (templates/secoes/painel/brain-dump.html).
    page.click('#tabbar [data-tab="painel"]')
    page.wait_for_selector("#tab-painel:not([hidden])")
    time.sleep(0.8)

    processar_sumiu = page.evaluate("() => !document.querySelector('.btn-brain-processar')")
    guardar_existe = page.evaluate("() => !!document.querySelector('#brain-dump-btn')")
    guardar_texto = page.eval_on_selector("#brain-dump-btn", "el => el.textContent.trim()")

    page.eval_on_selector("#brain-dump-btn", "el => el.scrollIntoView({block: 'center'})")
    time.sleep(0.3)
    page.screenshot(path=os.path.join(AQUI, "v1-brain-dump.png"), animations="disabled")
    b.close()

# Falhas de ambiente conhecidas (sandbox sem internet confiavel e IA com chave
# falsa) - mesma lista de scripts/ralph-v0c-secoes/verificar.py.
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today")
falhas_ambiente = [f for f in falhas_rede if any(a in f[1] for a in AMBIENTE)]
falhas_rede = [f for f in falhas_rede if f not in falhas_ambiente]
erros = [e for e in erros if not e[1].startswith("Failed to load resource")] if not falhas_rede else erros

cards_ok = (
    medidas_cards.get("achou")
    and medidas_cards.get("total") == 3
    and not medidas_cards.get("algum_fallback")
    and medidas_cards.get("tem_desfazer") == 2  # assinatura + compra_parcelada tem desfazer; resumo nao
)

res = {
    "erros_console": erros,
    "falhas_rede": falhas_rede,
    "falhas_ambiente_ignoradas": falhas_ambiente,
    "hoje_visivel_por_padrao": hoje_visivel,
    "ordem_dom_tab_hoje": ordem_dom,
    "caixa_assistente_antes_da_saudacao": caixa_antes_saudacao,
    "cards_novos": medidas_cards,
    "cards_ok": cards_ok,
    "brain_dump_processar_sumiu": processar_sumiu,
    "brain_dump_guardar_existe": guardar_existe,
    "brain_dump_guardar_texto": guardar_texto,
}
json.dump(res, open(os.path.join(AQUI, "v1-hoje-resultado.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, ensure_ascii=False, indent=1))

ok = (
    not erros
    and not falhas_rede
    and hoje_visivel
    and caixa_antes_saudacao
    and cards_ok
    and processar_sumiu
    and guardar_existe
    and guardar_texto == "Guardar"
)
print("OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
