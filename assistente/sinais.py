"""Fase 7, faixa P7 (sinais do iPhone via app Atalhos).

Consultas sobre a tabela `sinais` (migracoes/202609241240_p7_sinais.sql,
gravada por `rotas/p7_sinais.py` via POST /api/sinal) - e o que o motor de
regras (faixa P4) vai importar pra perguntar "o Alex acabou de chegar em
algum lugar?" sem escrever SQL repetido. Tambem mora aqui a reacao simples
embutida do proprio P7 (flag `assistente.p7.reacoes`, ligada por padrao).

Nao confundir com /api/atalho/local (app.py, ja existente): aquele e
especifico pra geofence casa/mercado e devolve uma MENSAGEM pro Atalho
mostrar na hora, sem gravar nada de generico. `sinais` e generica (qualquer
tipo de automacao pessoal) e nao devolve mensagem de display.
"""

import hmac
from datetime import datetime, timedelta

import db

FLAG_REACOES = "assistente.p7.reacoes"

# Tipos aceitos por POST /api/sinal (rotas/p7_sinais.py) - fonte unica da
# validacao, compartilhada entre a rota e os testes.
TIPOS_VALIDOS = ("cheguei", "sai", "acordei", "dormir", "carregando")

# Valores que desligam uma flag guardada via db.definir_configuracao (que so
# lida com string). Qualquer outra coisa (inclusive None = nunca configurada)
# conta como ligado - o padrao da faixa e "ligada".
_VALORES_DESLIGADOS = {"0", "false", "off", "nao", "desligado"}


def token_valido(cabecalho_authorization: str | None, token_configurado: str | None) -> bool:
    """Compara em tempo constante (`hmac.compare_digest`) o token do
    cabecalho `Authorization: Bearer <token>` com o `PAINEL_SINAL_TOKEN`
    configurado. Sem token configurado a rota fica sempre FECHADA - ela e
    maquina-a-maquina (ROTAS_COM_TOKEN, Etapa 0), sem sessao de PIN
    protegendo por baixo, entao "sem configuracao" nunca pode virar "aberta
    pra qualquer um"."""
    if not token_configurado:
        return False
    cabecalho = cabecalho_authorization or ""
    enviado = cabecalho[7:] if cabecalho.startswith("Bearer ") else ""
    return hmac.compare_digest(enviado.encode(), token_configurado.encode())


def quando_valido(valor) -> str | None:
    """ISO 8601 valido (data ou datetime) -> devolve normalizado pelo
    parser; None se ausente, vazio, tipo errado ou invalido."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    try:
        return datetime.fromisoformat(valor.strip()).isoformat()
    except ValueError:
        return None


def gravar(conn, tipo: str, lugar: str | None, quando: str) -> int:
    """Grava uma linha em `sinais` (migracoes/202609241240_p7_sinais.sql) e
    devolve o id. `tipo` invalido levanta ValueError - a rota ja valida
    antes de chamar, isto e so um cinto de seguranca pra quem mais usar."""
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"tipo inválido: {tipo!r}")
    cur = conn.execute(
        "INSERT INTO sinais (tipo, lugar, quando) VALUES (?, ?, ?)",
        (tipo, lugar, quando),
    )
    conn.commit()
    return cur.lastrowid


def ultimos_sinais(conn, tipo: str | None = None, desde=None) -> list[dict]:
    """Sinais mais recentes primeiro (por `quando`). `tipo` filtra por tipo
    exato; `desde` (datetime ou string ISO) so sinais com `quando` >= ele.
    Sem nenhum filtro, devolve no maximo os 50 mais recentes - evita puxar a
    tabela inteira sem querer."""
    sql = "SELECT id, tipo, lugar, quando, recebido_em FROM sinais WHERE 1 = 1"
    parametros: list = []
    if tipo is not None:
        sql += " AND tipo = ?"
        parametros.append(tipo)
    if desde is not None:
        sql += " AND quando >= ?"
        parametros.append(desde.isoformat() if isinstance(desde, datetime) else desde)
    sql += " ORDER BY quando DESC, id DESC LIMIT 50"
    return [dict(linha) for linha in conn.execute(sql, parametros).fetchall()]


def sinal_recente(conn, tipo: str, lugar: str | None = None, janela_min: int = 10, agora=None) -> dict | None:
    """O sinal mais recente desse `tipo` (e desse `lugar`, se informado),
    como dict, se ele aconteceu ha no maximo `janela_min` minutos - senao
    None. `agora` e injetavel pra teste; sem ele usa datetime.now()."""
    agora = agora or datetime.now()
    sql = "SELECT id, tipo, lugar, quando, recebido_em FROM sinais WHERE tipo = ?"
    parametros: list = [tipo]
    if lugar is not None:
        sql += " AND lugar = ?"
        parametros.append(lugar)
    sql += " ORDER BY quando DESC, id DESC LIMIT 1"
    linha = conn.execute(sql, parametros).fetchone()
    if linha is None:
        return None
    registro = dict(linha)
    try:
        quando = datetime.fromisoformat(registro["quando"])
    except (TypeError, ValueError):
        return None
    if quando > agora or agora - quando > timedelta(minutes=janela_min):
        return None
    return registro


def _reacoes_ativas(conn) -> bool:
    valor = db.obter_configuracao(conn, FLAG_REACOES)
    return (valor or "").strip().lower() not in _VALORES_DESLIGADOS if valor is not None else True


def reagir(conn, tipo: str, lugar: str | None, quando: str, agora=None) -> None:
    """Reacoes simples embutidas do P7 (flag `assistente.p7.reacoes`). Chamada
    pela rota logo depois de gravar o sinal - nunca deve derrubar o POST:
    qualquer problema aqui fica so registrado no sinal em si (ja gravado).

    - 'acordei': garante que o briefing da manha apareca. Chamada tardia e
      defensiva num ponto de integracao plausivel da P3
      (assistente.gatilhos.p3_briefing.garantir_briefing(conn, agora)) - se a
      P3 ainda nao existir (ImportError/AttributeError) ou o nome real for
      outro, nao faz nada alem do que o sinal 'acordei' ja registrou:
      confirme o nome combinando com a P3/integracao antes de contar com
      isso em producao.
    - 'cheguei' no mercado: poe a lista de compras pendente como item na
      Caixa (nao repete no mesmo dia, via chave_unica)."""
    if not _reacoes_ativas(conn):
        return
    agora = agora or datetime.now()
    if tipo == "acordei":
        _reagir_acordei(conn, agora)
    elif tipo == "cheguei" and (lugar or "").strip().lower() == "mercado":
        _reagir_cheguei_mercado(conn, agora)


def _reagir_acordei(conn, agora: datetime) -> None:
    try:
        from assistente.gatilhos.p3_briefing import garantir_briefing
    except ImportError:
        return  # P3 ainda nao existe nesta integracao - o sinal ja ficou registrado
    try:
        garantir_briefing(conn, agora)
    except Exception:
        pass  # reacao e extra, nunca pode derrubar o POST /api/sinal


def _reagir_cheguei_mercado(conn, agora: datetime) -> None:
    pendentes = [item["item"] for item in db.list_compras_pendentes(conn)]
    if not pendentes:
        return
    try:
        from assistente.caixa import enfileirar
    except ImportError:
        return  # P1a ainda nao existe nesta integracao - o sinal ja ficou registrado
    try:
        enfileirar(
            "aviso",
            "Lista de compras",
            "Chegou no mercado. Pendente: " + ", ".join(pendentes) + ".",
            origem="p7_sinais",
            chave_unica=f"p7_mercado_{agora.date().isoformat()}",
        )
    except Exception:
        pass  # reacao e extra, nunca pode derrubar o POST /api/sinal
