import os

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
