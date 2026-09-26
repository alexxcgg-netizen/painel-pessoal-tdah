"""Rotas por Blueprint com carga automatica (Fase 7, Etapa 0).

Cada faixa da Fase 7 cria o PROPRIO arquivo aqui (`rotas/<assunto>.py`) em vez
de editar `app.py` - assim duas faixas nunca mexem no mesmo arquivo.
`registrar_todas(app)` e chamada uma vez so, no fim de `app.py`: importa todo
modulo desta pasta (menos `__init__`), em ordem alfabetica, e registra o
atributo `bp` (um `flask.Blueprint`) de quem tiver. Modulo sem `bp` (ex:
`_base.py`, helpers) e so importado.

Regras pra quem cria um arquivo aqui:
- Autenticacao ja e GLOBAL (`@app.before_request` em app.py,
  `_verificar_autenticacao`): toda rota de blueprint exige login igual as
  outras, sem decorator nenhum. Rota que precisa ser publica (token proprio,
  ex: Atalho do iPhone) ainda precisa entrar na lista de excecoes de la -
  combine com a integracao antes.
- Nome do blueprint unico (o nome do arquivo e um bom padrao) e prefixo de URL
  que nao colida com rota existente de app.py.
- Helpers de app.py (`_corpo_json`, `_texto_seguro`, `_modo_visitante_ativo`,
  `_recusar_no_modo_visitante`, `_resposta_contrato`, `get_db`, ...) SEMPRE via
  `app_modulo()` DENTRO da funcao da rota, nunca `import app` no topo do
  arquivo: este pacote e importado no fim de app.py (import circular), e em
  `python app.py` o modulo carregado se chama `__main__`, nao `app`.
- Rota maquina-a-maquina (sem sessao de PIN, token proprio - ex: /api/tick,
  /api/sinal, webhook do Telegram, /widget): declare no modulo
  `ROTAS_COM_TOKEN = {"/api/tick"}` (caminhos EXATOS) e/ou
  `PREFIXOS_COM_TOKEN = ("/widget/",)`. `registrar_todas` junta tudo em
  `rotas.CAMINHOS_COM_TOKEN` / `rotas.PREFIXOS_COM_TOKEN` e
  `_verificar_autenticacao` (app.py) libera esses caminhos SEM login - alem
  da tupla fixa que ja existia la. A ROTA DECLARADA E RESPONSAVEL POR CHECAR
  O PROPRIO TOKEN (comparacao em tempo constante, `hmac.compare_digest`) logo
  na primeira linha - sem isso ela fica aberta pra internet. Nunca declare
  caminho de rota que grava dado sem token. Prefixo largo demais ("/",
  "/api", "/api/"), caminho sem "/" no comeco, ou prefixo que cubra rota de
  OUTRO blueprint/app.py derruba o boot (ValueError).
- Banco: `db.get_db()` direto (ou `app_modulo().get_db()`), sempre fechando a
  conexao no `finally`.
- Teste da rota no arquivo de teste da propria faixa (`tests/test_fase7_<faixa>_*.py`).

Exemplo minimo (`rotas/exemplo.py` - NAO existe de verdade, e so o molde):

    from flask import Blueprint, jsonify

    import db
    from rotas._base import app_modulo

    bp = Blueprint("exemplo", __name__)


    @bp.route("/api/exemplo", methods=["POST"])
    def criar_exemplo():
        app = app_modulo()
        recusa = app._recusar_no_modo_visitante()  # rota que grava algo
        if recusa:
            return recusa
        corpo = app._corpo_json()
        texto = app._texto_seguro(corpo.get("texto"))
        if not texto:
            return jsonify({"error": "texto vazio"}), 400
        conn = db.get_db()
        try:
            ...
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True}), 201
"""

import importlib
import pkgutil

from flask import Blueprint


def nomes_modulos() -> list[str]:
    """Nomes (sem o prefixo do pacote) de todo modulo desta pasta, em ordem
    alfabetica. Usa `__path__`, entao um teste pode acrescentar uma pasta
    temporaria ao pacote sem criar arquivo aqui."""
    return sorted({m.name for m in pkgutil.iter_modules(__path__) if not m.ispkg and m.name != "__init__"})


CAMINHOS_COM_TOKEN: set[str] = set()
PREFIXOS_COM_TOKEN: tuple[str, ...] = ()

# Prefixos que liberariam o app inteiro (ou toda a API) sem login.
_PREFIXOS_PROIBIDOS = {"/", "/api", "/api/", "/static", "/static/"}


def _caminhos_com_token(modulo, nome: str) -> tuple[set[str], set[str]]:
    caminhos = getattr(modulo, "ROTAS_COM_TOKEN", None) or ()
    prefixos = getattr(modulo, "PREFIXOS_COM_TOKEN", None) or ()
    if isinstance(caminhos, str) or isinstance(prefixos, str):
        raise ValueError(f"rotas/{nome}.py: ROTAS_COM_TOKEN/PREFIXOS_COM_TOKEN precisam ser set/tuple, não str")
    for c in list(caminhos) + list(prefixos):
        if not isinstance(c, str) or not c.startswith("/"):
            raise ValueError(f"rotas/{nome}.py: caminho com token inválido {c!r} (precisa comecar com '/')")
    for p in prefixos:
        if p.rstrip("/") in {x.rstrip("/") for x in _PREFIXOS_PROIBIDOS} or len(p.strip("/")) < 3:
            raise ValueError(f"rotas/{nome}.py: prefixo com token largo demais {p!r}")
    return set(caminhos), set(prefixos)


def rota_com_token(path: str) -> bool:
    """True se `path` foi declarado por algum modulo de rota como
    maquina-a-maquina (a propria rota checa o token). Usado pelo
    `_verificar_autenticacao` de app.py."""
    return path in CAMINHOS_COM_TOKEN or (bool(PREFIXOS_COM_TOKEN) and path.startswith(PREFIXOS_COM_TOKEN))


def registrar_todas(app) -> list[str]:
    """Importa todo `rotas/*.py`, registra o `bp` de cada um no app e junta os
    `ROTAS_COM_TOKEN`/`PREFIXOS_COM_TOKEN` declarados. Devolve os nomes dos
    blueprints registrados, na ordem."""
    global PREFIXOS_COM_TOKEN
    registrados = []
    caminhos: set[str] = set()
    prefixos: dict[str, str | None] = {}
    for nome in nomes_modulos():
        modulo = importlib.import_module(f"{__name__}.{nome}")
        c, p = _caminhos_com_token(modulo, nome)
        bp = getattr(modulo, "bp", None)
        if isinstance(bp, Blueprint):
            app.register_blueprint(bp)
            registrados.append(bp.name)
        caminhos |= c
        for prefixo in p:
            prefixos[prefixo] = bp.name if isinstance(bp, Blueprint) else None
    # Prefixo so pode cobrir rota do PROPRIO blueprint que o declarou - nunca
    # abrir sem login uma rota de app.py ou de outra faixa por acidente.
    for regra in app.url_map.iter_rules():
        dono = regra.endpoint.split(".", 1)[0] if "." in regra.endpoint else None
        for prefixo, bp_nome in prefixos.items():
            if regra.rule.startswith(prefixo) and dono != bp_nome:
                raise ValueError(
                    f"prefixo com token {prefixo!r} cobre a rota {regra.rule!r} ({regra.endpoint}), "
                    "que não e do blueprint que declarou o prefixo"
                )
    CAMINHOS_COM_TOKEN.update(caminhos)
    PREFIXOS_COM_TOKEN = tuple(sorted(set(PREFIXOS_COM_TOKEN) | set(prefixos)))
    return registrados
