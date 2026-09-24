"""Acesso ao modulo do app a partir de um blueprint, sem import circular.

`rotas.registrar_todas(app)` roda no FIM de app.py, com app.py ainda sendo
importado - um `import app` no topo de um arquivo de rota criaria um segundo
modulo app (quando rodando via `python app.py`, o modulo de verdade se chama
`__main__`) ou pegaria um modulo pela metade. Chame `app_modulo()` dentro da
funcao da rota (na hora da requisicao) e use os helpers dele."""

import sys


def app_modulo():
    """O modulo app.py ja carregado: `sys.modules["__main__"]` quando rodando
    `python app.py` (e ele que serve as requisicoes), senao `sys.modules["app"]`
    (wsgi.py, testes)."""
    principal = sys.modules.get("__main__")
    if principal is not None and hasattr(principal, "_verificar_autenticacao"):
        return principal
    modulo = sys.modules.get("app")
    if modulo is not None:
        return modulo
    raise RuntimeError("app.py ainda nao foi carregado - app_modulo() so funciona dentro de uma requisicao")
