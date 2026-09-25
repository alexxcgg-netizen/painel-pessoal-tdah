"""Fase 8, Faixa F1: sincronizacao automatica do Nubank via Pluggy (item ja
autorizado, sem passar pelo Connect) + lista unificada de gastos com selo de
origem (Nubank/manual) na tela de Financeiro > Gastos.

Fase 8, Faixa F2: "Proximas cobrancas" (assinaturas + parcelas, Fase 7) na
mesma tela, reusando financas_recorrentes.proximas_cobrancas (nao recalcula
data em lugar nenhum) + cruzamento com o que ja veio do banco pra nao
duplicar uma cobranca que ja foi cadastrada manualmente e tambem apareceu
como transacao do Nubank.

So usa o item_id de PLUGGY_ITEM_ID_NUBANK (.env) - nunca inventa nem aceita
item_id vindo do corpo da requisicao pra essa rota (evita que qualquer um
sincronize um item alheio). O fluxo de Connect (usuario escolhe o banco na
hora) continua em app.py, sem mudanca.
"""

import os
import re
import threading
import unicodedata
from datetime import date, datetime

import requests
from flask import Blueprint, jsonify

import db
import financas_recorrentes as fr
import pluggy_client
from rotas._base import app_modulo

bp = Blueprint("f8_banco", __name__)

_TOLERANCIA_VALOR = 0.50
_TOLERANCIA_DIAS = 5

# Fase 9 (faixa uso/m2-sync): trava simples pra nunca rodar duas
# sincronizacoes do Nubank ao mesmo tempo - o botao manual (rota abaixo) e o
# job de madrugada do scheduler (app.py, ver iniciar_scheduler) chamam a
# MESMA sincronizar_nubank() e podem colidir por acaso (Alex acordado
# sincronizando na mao as 4h). So processo em memoria (gunicorn roda com
# --workers 1, ver render.yaml), nao precisa de lock no banco.
_lock_sincronizacao_nubank = threading.Lock()

CHAVE_ULTIMO_SYNC_NUBANK_OK = "ultimo_sync_nubank_ok"


def _normalizar_nome(texto: str) -> str:
    """Sem acento, minusculo, so letras/numeros/espaco - pra comparar nome
    de assinatura/parcela com descricao de transacao bancaria sem que
    acento ou caixa atrapalhe o "contem"."""
    texto = texto or ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    sem_acento = sem_acento.lower()
    return re.sub(r"[^a-z0-9 ]", " ", sem_acento).strip()


def _cobranca_bate_com_gasto(cobranca: dict, gasto: dict) -> bool:
    nome_cobranca = _normalizar_nome(cobranca.get("nome") or cobranca.get("descricao") or "")
    nome_gasto = _normalizar_nome(gasto.get("description") or "")
    if not nome_cobranca or not nome_gasto:
        return False
    if nome_cobranca not in nome_gasto and nome_gasto not in nome_cobranca:
        return False

    valor_cobranca = cobranca.get("valor")
    valor_gasto = gasto.get("amount")
    if valor_cobranca is None or valor_gasto is None:
        return False
    if abs(float(valor_cobranca) - float(valor_gasto)) > _TOLERANCIA_VALOR:
        return False

    try:
        data_cobranca = date.fromisoformat(cobranca["data"])
        data_gasto = date.fromisoformat(str(gasto.get("created_at"))[:10])
    except (KeyError, ValueError, TypeError):
        return False
    if abs((data_cobranca - data_gasto).days) > _TOLERANCIA_DIAS:
        return False
    return True


def cruzar_proximas_cobrancas_com_gastos(cobrancas: list[dict], gastos: list[dict]) -> list[dict]:
    """Funcao pura (sem banco): marca cada cobranca (assinatura/parcela)
    com `duplicado`/`aviso` quando ela bate (nome parecido + valor com
    tolerancia de R$0,50 + data a +-5 dias) com um gasto que veio do
    banco (origem != 'manual') - pra tela mostrar so uma vez com aviso
    em vez de duas cobrancas iguais (cadastrada e tambem sincronizada)."""
    gastos_do_banco = [g for g in gastos if g.get("origem") and g.get("origem") != "manual"]
    resultado = []
    for cobranca in cobrancas:
        item = dict(cobranca)
        bate = any(_cobranca_bate_com_gasto(cobranca, g) for g in gastos_do_banco)
        item["duplicado"] = bate
        item["aviso"] = "possível duplicidade: cadastrada e também veio do Nubank" if bate else None
        resultado.append(item)
    return resultado


def _montar_gastos_unificados(conn) -> list[dict]:
    """Monta a lista unica (manual + banco) - usada tanto pela rota
    /api/gastos/unificados quanto pelo cruzamento de proximas cobrancas."""
    expenses_reais = conn.execute(
        "SELECT amount, category, description, source_text, created_at "
        "FROM expenses WHERE tipo = 'real' ORDER BY created_at DESC"
    ).fetchall()
    unificado = []
    for r in expenses_reais:
        item = dict(r)
        item["origem"] = "manual"
        unificado.append(item)

    contas_por_id = {c["id"]: c for c in db.list_bank_accounts(conn)}
    for r in db.list_all_bank_transactions(conn):
        if r["valor"] is None or r["valor"] >= 0:
            continue
        conta = contas_por_id.get(r["bank_account_id"])
        banco = (conta["banco"] if conta else "banco").strip()
        unificado.append(
            {
                "amount": -r["valor"],
                "category": r["categoria"] or "outros",
                "description": r["descricao"],
                "source_text": None,
                "created_at": r["data"],
                "origem": banco.capitalize() if banco else "banco",
            }
        )
    unificado.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return unificado


_CAMPOS_COMPARAVEIS = (
    "data",
    "valor",
    "descricao",
    "estabelecimento",
    "categoria_pluggy",
    "descricao_original",
    "tipo_operacao",
    "estorno_de_external_id",
)


def _upsert_bank_transacoes(conn, bank_account_id: int, transacoes: list[dict]) -> dict:
    """Upsert de verdade por `external_id` (o id da transacao na Pluggy) -
    chave de idempotencia da sincronizacao: nova -> insere; ja existe e
    mudou (valor/data/descricao/estabelecimento/categoria da Pluggy/tipo de
    operacao/estorno) -> atualiza; ja existe e igual -> nao mexe. Roda em
    `rotas/f8_banco.py` (nao em db.py) e usa as mesmas rotinas de
    criptografia de campo que db.py ja usa, pra ficar no mesmo padrao de
    dado em repouso sem duplicar a logica de cifrar/decifrar.

    A `categoria` (a nossa, decidida por gastos.sugerir_categoria) NUNCA e
    sobrescrita numa atualizacao - so e gravada na insercao. Se um dia
    existir edicao manual de categoria pelo usuario, uma sincronizacao nao
    apaga essa escolha."""
    novas = atualizadas = sem_mudanca = 0
    for t in transacoes:
        existente = conn.execute(
            "SELECT * FROM bank_transactions WHERE bank_account_id = ? AND external_id = ?",
            (bank_account_id, t["external_id"]),
        ).fetchone()

        if existente is None:
            conn.execute(
                """INSERT INTO bank_transactions
                   (bank_account_id, data, descricao, valor, external_id, categoria,
                    estabelecimento, categoria_pluggy, descricao_original, tipo_operacao,
                    estorno_de_external_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    bank_account_id,
                    t["data"],
                    db.criptografia.criptografar(t["descricao"]),
                    db._cnum(t["valor"]),
                    t["external_id"],
                    t.get("categoria"),
                    t.get("estabelecimento"),
                    t.get("categoria_pluggy"),
                    t.get("descricao_original"),
                    t.get("tipo_operacao"),
                    t.get("estorno_de_external_id"),
                ),
            )
            novas += 1
            continue

        atual = {
            "data": existente["data"],
            "valor": db._dnum(existente["valor"], float),
            "descricao": db.criptografia.descriptografar(existente["descricao"]),
            "estabelecimento": existente["estabelecimento"],
            "categoria_pluggy": existente["categoria_pluggy"],
            "descricao_original": existente["descricao_original"],
            "tipo_operacao": existente["tipo_operacao"],
            "estorno_de_external_id": existente["estorno_de_external_id"],
        }
        novo = {
            "data": t["data"],
            "valor": float(t["valor"]) if t["valor"] is not None else None,
            "descricao": t["descricao"],
            "estabelecimento": t.get("estabelecimento"),
            "categoria_pluggy": t.get("categoria_pluggy"),
            "descricao_original": t.get("descricao_original"),
            "tipo_operacao": t.get("tipo_operacao"),
            "estorno_de_external_id": t.get("estorno_de_external_id"),
        }
        if all(atual[campo] == novo[campo] for campo in _CAMPOS_COMPARAVEIS):
            sem_mudanca += 1
            continue

        conn.execute(
            """UPDATE bank_transactions
               SET data = ?, descricao = ?, valor = ?, estabelecimento = ?,
                   categoria_pluggy = ?, descricao_original = ?, tipo_operacao = ?,
                   estorno_de_external_id = ?
               WHERE id = ?""",
            (
                novo["data"],
                db.criptografia.criptografar(novo["descricao"]),
                db._cnum(novo["valor"]),
                novo["estabelecimento"],
                novo["categoria_pluggy"],
                novo["descricao_original"],
                novo["tipo_operacao"],
                novo["estorno_de_external_id"],
                existente["id"],
            ),
        )
        atualizadas += 1

    return {"novas": novas, "atualizadas": atualizadas, "sem_mudanca": sem_mudanca}


def _reconciliar_transacoes_removidas(
    conn, bank_account_id: int, transacoes: list[dict], truncado: bool
) -> int:
    """Depois do upsert, o que a Pluggy devolveu agora e tratado como fonte
    da verdade pro intervalo de datas [menor data, maior data] dessa leva -
    apaga de `bank_transactions` (so dessa `bank_account_id`) qualquer linha
    com `data` dentro desse intervalo cujo `external_id` NAO veio nessa
    resposta (ex.: o item Pluggy foi reconectado e reimportou o historico
    inteiro com ids novos - as linhas com os ids antigos, mesma janela de
    datas, ficam orfas e sao removidas aqui). `data` NAO e campo
    criptografado (so `valor`/`descricao` sao - ver criptografia.py), entao
    o filtro por intervalo roda direto em SQL, sem precisar decifrar nada.

    Transacao fora desse intervalo (historico mais antigo que a Pluggy nao
    devolve mais) fica intocada. Nunca toca em `expenses` (gasto manual).

    So roda quando a busca terminou completa: uma lista vazia ou uma busca
    truncada (`truncado=True`, bateu no teto de paginas do
    pluggy_client.get_transactions) nao pode ser tratada como fonte da
    verdade - apagaria transacao real por engano - entao devolve 0 sem
    tocar no banco."""
    if truncado or not transacoes:
        return 0

    ids_atuais = [t["external_id"] for t in transacoes]
    datas = [t["data"] for t in transacoes]
    dmin, dmax = min(datas), max(datas)
    placeholders = ",".join("?" for _ in ids_atuais)
    cur = conn.execute(
        "DELETE FROM bank_transactions "
        "WHERE bank_account_id = ? AND data BETWEEN ? AND ? "
        f"AND external_id NOT IN ({placeholders})",
        (bank_account_id, dmin, dmax, *ids_atuais),
    )
    return cur.rowcount


def _erro_amigavel_pluggy(exc: Exception) -> tuple[str, int]:
    """Converte qualquer erro de rede/HTTP da Pluggy numa mensagem que pode
    ir pra tela sem vazar corpo cru de resposta nem cabecalho com chave."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == 404:
        return "conexao Nubank nao encontrada nessa conta Pluggy - reconectar", 404
    if status == 401:
        return "credenciais da Pluggy invalidas ou expiradas - reconectar", 401
    return "nao consegui falar com a Pluggy agora, tenta de novo mais tarde", 502


def sincronizar_nubank(conn) -> dict:
    """Nucleo de verdade da sincronizacao com o Nubank via Pluggy - fonte
    unica usada tanto pela rota manual (`POST /api/bancos/sincronizar-nubank`
    abaixo) quanto pelo job automatico de madrugada do scheduler (ver
    `iniciar_scheduler`/`rodar_sincronizacao_nubank_automatica` em app.py):
    os dois so CHAMAM essa funcao, nenhum reimplementa a logica.

    Nao decide HTTP nem sessao (isso fica com quem chama) - devolve sempre
    um dict, nunca deixa `requests.RequestException` subir (vira
    `{"ok": False, "error": ..., "status": ...}`). `pluggy_client.configurado()`
    e responsabilidade de quem chama (a rota devolve 400 direto sem nem
    tentar; o job so entra aqui quando ja sabe que esta configurado, senao
    fica em silencio - ver app.py).

    So concede a corrida (lock) pra uma sincronizacao por vez (botao manual
    x job automatico) - quem perde devolve erro amigavel na hora em vez de
    esperar e arriscar duas escritas concorrentes no mesmo `conn`/banco.

    Idempotente e seguro contra falha parcial: se a Pluggy falhar no meio
    (ex: no 2o cartao de N), a funcao devolve erro SEM commitar nada dessa
    chamada - quem fechar `conn` sem commit descarta a transacao inteira
    (nunca fica pela metade), e o ultimo sync bom que ja estava commitado
    continua intacto no banco."""
    if not _lock_sincronizacao_nubank.acquire(blocking=False):
        return {
            "ok": False,
            "error": "ja tem uma sincronizacao do Nubank rodando, tenta de novo em instantes",
            "status": 409,
        }

    try:
        item_id = os.environ.get("PLUGGY_ITEM_ID_NUBANK")
        if not item_id:
            return {"ok": False, "error": "PLUGGY_ITEM_ID_NUBANK nao configurado", "status": 400}

        try:
            item = pluggy_client.get_item(item_id)
            contas_pluggy = pluggy_client.get_accounts(item_id)
        except requests.RequestException as exc:
            mensagem, status = _erro_amigavel_pluggy(exc)
            return {"ok": False, "error": mensagem, "status": status}

        app = app_modulo()
        resumo = []
        total_novas = total_atualizadas = total_sem_mudanca = total_removidas = 0
        for conta_pluggy in contas_pluggy:
            # tipo da conta Pluggy decide o "balde" em bank_accounts: CREDIT
            # -> cartao (saldo = fatura em aberto, positivo = quanto se
            # deve - o `balance` que a Pluggy devolve pra uma conta CREDIT),
            # qualquer outro tipo (ex: BANK) -> conta (saldo = dinheiro
            # disponivel de verdade). Nao soma cartao com conta em nenhum
            # lugar - cada um fica na sua linha de bank_accounts.
            tipo = "cartao" if conta_pluggy.get("type") == "CREDIT" else "conta"
            conta_id = db.get_or_create_bank_account(conn, "nubank", tipo)
            saldo_pluggy = conta_pluggy.get("balance")
            if saldo_pluggy is not None:
                db.atualizar_saldo_conta(conn, conta_id, saldo_pluggy)
            try:
                transacoes_pluggy, truncado = pluggy_client.get_transactions(conta_pluggy["id"])
            except requests.RequestException as exc:
                mensagem, status = _erro_amigavel_pluggy(exc)
                return {"ok": False, "error": mensagem, "status": status}
            transacoes = pluggy_client.normalizar_transacoes(transacoes_pluggy)
            transacoes = app._categorizar_transacoes_importadas(conn, transacoes)
            contagem = _upsert_bank_transacoes(conn, conta_id, transacoes)
            removidas = _reconciliar_transacoes_removidas(conn, conta_id, transacoes, truncado)
            contagem["removidas"] = removidas
            total_novas += contagem["novas"]
            total_atualizadas += contagem["atualizadas"]
            total_sem_mudanca += contagem["sem_mudanca"]
            total_removidas += removidas
            resumo.append({"conta_id": conta_id, "tipo": tipo, **contagem})

        mensagem = (
            f"{total_novas} nova(s), {total_atualizadas} atualizada(s), "
            f"{total_sem_mudanca} sem mudanca, {total_removidas} removida(s)"
        )
        # marca o sync bom ANTES do commit final: definir_configuracao ja
        # commita (db.py), entao esse commit cobre a leva toda (transacoes +
        # o carimbo) de uma vez so - so grava quando chega ate aqui sem
        # nenhum erro/excecao no meio.
        db.definir_configuracao(conn, CHAVE_ULTIMO_SYNC_NUBANK_OK, datetime.now().isoformat(timespec="seconds"))
        conn.commit()
        return {
            "ok": True,
            "banco": "nubank",
            "item_status": item.get("status"),
            "contas": resumo,
            "novas": total_novas,
            "atualizadas": total_atualizadas,
            "sem_mudanca": total_sem_mudanca,
            "removidas": total_removidas,
            "mensagem": mensagem,
        }
    finally:
        _lock_sincronizacao_nubank.release()


@bp.route("/api/bancos/sincronizar-nubank", methods=["POST"])
def sincronizar_nubank_rota():
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa

    if not pluggy_client.configurado():
        return jsonify({"error": "sincronizacao automatica nao configurada"}), 400

    conn = db.get_db()
    try:
        resultado = sincronizar_nubank(conn)
    finally:
        conn.close()

    if not resultado.get("ok"):
        return jsonify({"error": resultado.get("error", "falha na sincronizacao")}), resultado.get("status", 502)
    return jsonify(resultado)


@bp.route("/api/gastos/unificados", methods=["GET"])
def gastos_unificados():
    """Gastos manuais (expenses) + gastos automaticos (bank_transactions),
    numa lista so, cada item com 'origem' ('manual' ou o nome do banco,
    ex: 'Nubank'). Nao apaga nem altera nada - so leitura."""
    conn = db.get_db()
    try:
        unificado = _montar_gastos_unificados(conn)
    finally:
        conn.close()
    return jsonify(unificado)


@bp.route("/api/gastos/proximas-cobrancas", methods=["GET"])
def proximas_cobrancas():
    """Assinaturas + parcelas (Fase 7) que vao cobrar em breve, pra tela de
    Financeiro > Gastos mostrar junto com os gastos do banco. Reusa
    financas_recorrentes.proximas_cobrancas (a mesma conta de data usada na
    tela de Assinaturas) e so acrescenta o cruzamento de duplicidade com o
    que ja veio do Nubank - nao recalcula nenhuma data aqui."""
    conn = db.get_db()
    try:
        hoje = date.today()
        cobrancas = fr.proximas_cobrancas(conn, hoje=hoje)
        gastos = _montar_gastos_unificados(conn)
        cobrancas = cruzar_proximas_cobrancas_com_gastos(cobrancas, gastos)
    finally:
        conn.close()
    return jsonify(cobrancas)
