"""Contrato de cards da aba Hoje (Fase 6, "Padrao Nectar") - lado servidor.

Fonte unica do formato {cards, resumo_texto, passos} que /api/chat e
/api/capture devolvem. O contrato completo (formato de `data` de cada type,
actions, passos, modo visitante) esta em docs/CARDS.md - qualquer mudanca aqui
precisa bater com aquele documento (so aditivo).

Divisao de responsabilidade:
- executores de tool do chat (app.py) so gravam no banco e descrevem o que
  criaram numa chave privada `_efeito` do resultado ({"entidade", "id", ...});
- `RegistroExecucao` envolve os executores: cronometra (passos), guarda o
  `_efeito` e tira as chaves privadas antes do resultado voltar pra IA;
- `cards_dos_efeitos` e o UNICO lugar que traduz efeito -> card (le a linha
  real do banco pelo id, nunca confia no texto da IA pra montar o card).
"""

from __future__ import annotations

import copy
import re
import time
from datetime import date

# ---- rotulos humanos -------------------------------------------------------

# Modulo (rotulo humano) de cada tool do chat - usado em `passos` e no
# resumo_final. Tool que nao estiver aqui cai em "Assistente".
MODULO_POR_TOOL = {
    "registrar_tarefa": "Tarefas",
    "distribuir_tarefas_na_semana": "Tarefas",
    "confirmar_plano_semana": "Tarefas",
    "cancelar_plano_semana": "Tarefas",
    "sugerir_tarefa_para_agora": "Tarefas",
    "registrar_feito": "Tarefas",
    "gerar_plano_do_dia": "Tarefas",
    "registrar_gasto": "Finanças",
    "registrar_renda": "Finanças",
    "definir_orcamento": "Finanças",
    "registrar_conta_pessoal": "Finanças",
    "rotular_cobranca_generica": "Finanças",
    "consultar_gastos_fixos": "Finanças",
    "consultar_sobra_do_mes": "Finanças",
    "calcular_gasto_viagem": "Finanças",
    "registrar_meta": "Metas",
    "registrar_lembrete": "Lembretes",
    "registrar_medicamento": "Saúde",
    "registrar_hidratacao": "Saúde",
    "registrar_medida": "Saúde",
    "registrar_checkin": "Saúde",
    "salvar_ficha_treino": "Saúde",
    "registrar_treino": "Saúde",
    "registrar_viagem": "Viagens",
    "registrar_lugar": "Viagens",
    "sugerir_horario_livre": "Agenda",
    "registrar_voo": "Aviação",
    "adicionar_compras": "Compras",
    "registrar_memoria": "Memória",
    "salvar_nota": "Notas",
    "consultar_notas": "Notas",
}

# Descricao curta de cada tool pra `passos` quando o efeito nao da uma frase
# melhor (ver _descricao_passo). Nunca inclui valor em dinheiro - `passos`
# nao passa pelo mascaramento do modo visitante.
DESCRICAO_TOOL = {
    "gerar_plano_do_dia": "Montou o plano do dia",
    "registrar_hidratacao": "Registrou um copo de água",
    "registrar_checkin": "Registrou o check-in",
    "registrar_treino": "Registrou o treino",
    "registrar_memoria": "Guardou uma memória",
    "consultar_noticias": "Buscou notícias",
    "consultar_notas": "Consultou as notas",
    "consultar_gastos_fixos": "Consultou os gastos fixos",
    "consultar_sobra_do_mes": "Calculou a sobra do mês",
    "sugerir_horario_livre": "Procurou horário livre",
    "sugerir_tarefa_para_agora": "Escolheu uma tarefa pra agora",
}

ABA_POR_ENTIDADE = {
    "tarefa": ("tarefas", "Abrir Tarefas"),
    "gasto": ("gastos", "Abrir no extrato"),
    "renda": ("gastos", "Abrir no extrato"),
    "meta": ("gastos", "Abrir Metas"),
    "lembrete": ("painel", "Abrir em Lembretes"),
}

# Campos com valor em dinheiro, por type - removidos no modo visitante
# (docs/CARDS.md, "Modo visitante"). Card novo com dinheiro entra aqui.
CAMPOS_SENSIVEIS = {
    "transacao": ("valor", "saldo"),
    "meta": ("valor_guardado", "valor_alvo", "falta"),
}

# Cards gerados pelo servidor hoje (os de visual complexo - agenda,
# projeto_viagem, saude_treino, sugestao, habito - tem renderizador pronto
# no front mas o dado real e ligado por outras faixas; ver docs/CARDS.md).
TIPOS_CARD = (
    "tarefas_criadas",
    "transacao",
    "lembrete",
    "meta",
    "resumo_final",
    "agenda",
    "projeto_viagem",
    "saude_treino",
    "sugestao",
    "habito",
)


# ---- construtores basicos ---------------------------------------------------


def novo_card(tipo: str, data: dict, actions: list | None = None) -> dict:
    """`id` e preenchido por `envelope` (chave de DOM unica na resposta)."""
    return {"type": tipo, "data": data, "actions": list(actions or [])}


def acao_abrir_aba(aba: str, rotulo: str, entidade: str | None = None, id_: int | None = None) -> dict:
    acao = {"tipo": "abrir_aba", "rotulo": rotulo, "aba": aba}
    if entidade and id_ is not None:
        acao["destaque"] = {"entidade": entidade, "id": id_}
    return acao


def acao_desfazer(token: str, alvo: list[dict]) -> dict:
    """`alvo` e so informativo (o servidor confia no que gravou junto do
    token em acoes_desfazer, nunca no que o cliente mandar de volta)."""
    return {
        "tipo": "desfazer",
        "rotulo": "Desfazer",
        "token": token,
        "alvo": [{k: v for k, v in item.items() if k in ("entidade", "id", "uid")} for item in alvo],
    }


def acao_despertar(lembrete_id: int, ativo: bool) -> dict:
    return {"tipo": "despertar", "rotulo": "Desperta você", "lembrete_id": lembrete_id, "ativo": bool(ativo)}


def envelope(cards_lista: list[dict], resumo_texto: str, passos: list[dict]) -> dict:
    """Monta o envelope final e numera os cards (c1, c2...)."""
    numerados = []
    for i, card in enumerate(cards_lista, start=1):
        c = dict(card)
        c["id"] = f"c{i}"
        numerados.append(c)
    return {"cards": numerados, "resumo_texto": resumo_texto or "", "passos": list(passos or [])}


# ---- registro de execucao (passos + efeitos) --------------------------------


class RegistroExecucao:
    """Envolve os executores de tool do chat sem mudar o que a IA ve:
    cronometra cada chamada (vira `passos`), guarda o `_efeito` que o
    executor declarou e tira TODA chave comecando com `_` do resultado antes
    de devolver pro loop de tool-use (claude_client.chat)."""

    def __init__(self):
        self.chamadas: list[dict] = []

    def envolver(self, executores: dict) -> dict:
        return {nome: self._envolver_um(nome, fn) for nome, fn in executores.items()}

    def _envolver_um(self, nome, fn):
        def executor(entrada):
            inicio = time.perf_counter()
            resultado = fn(entrada)
            ms = int(round((time.perf_counter() - inicio) * 1000))
            self.chamadas.append({"tool": nome, "entrada": entrada, "resultado": resultado, "ms": ms})
            if isinstance(resultado, dict):
                return {k: v for k, v in resultado.items() if not str(k).startswith("_")}
            return resultado

        return executor

    def passos(self) -> list[dict]:
        return [passo_da_chamada(c) for c in self.chamadas]

    def efeitos(self) -> list[dict]:
        """Efeitos na ordem em que aconteceram (uma tool pode declarar um
        efeito so ou uma lista)."""
        saida = []
        for c in self.chamadas:
            res = c["resultado"]
            if not isinstance(res, dict) or res.get("erro"):
                continue
            efeito = res.get("_efeito")
            if isinstance(efeito, dict):
                saida.append(efeito)
            elif isinstance(efeito, list):
                saida.extend(e for e in efeito if isinstance(e, dict))
        return saida


def _titulo_curto(texto, limite: int = 60) -> str:
    texto = str(texto or "").strip()
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _descricao_passo(tool: str, entrada) -> str:
    entrada = entrada if isinstance(entrada, dict) else {}
    if tool == "registrar_tarefa":
        return f'Criou a tarefa "{_titulo_curto(entrada.get("titulo"))}"'
    if tool == "registrar_gasto":
        return f'Registrou o gasto "{_titulo_curto(entrada.get("titulo"))}"'
    if tool == "registrar_renda":
        return f'Registrou a entrada "{_titulo_curto(entrada.get("descricao") or entrada.get("categoria"))}"'
    if tool == "registrar_meta":
        return f'Criou a meta "{_titulo_curto(entrada.get("titulo"))}"'
    if tool == "registrar_lembrete":
        return f'Criou o lembrete "{_titulo_curto(entrada.get("titulo"))}"'
    if tool in DESCRICAO_TOOL:
        return DESCRICAO_TOOL[tool]
    return tool.replace("_", " ").capitalize()


def passo_da_chamada(chamada: dict) -> dict:
    passo = {
        "modulo": MODULO_POR_TOOL.get(chamada["tool"], "Assistente"),
        "descricao": _descricao_passo(chamada["tool"], chamada.get("entrada")),
        "ms": int(chamada.get("ms") or 0),
    }
    res = chamada.get("resultado")
    if isinstance(res, dict) and res.get("erro"):
        passo["erro"] = True
    return passo


# ---- efeito -> card (UNICO mapeamento) --------------------------------------


def _tarefa_dict(row) -> dict:
    return {
        "id": row["id"],
        "titulo": row["title"],
        "data": row["due_date"],
        "hora": row["hora"],
        "quando": row["due_at"],
        "recorrencia": row["recorrencia"],
        "concluida": bool(row["completed_at"]),
    }


def card_tarefas_criadas(conn, ids: list[int], actions_extra: list | None = None) -> dict | None:
    if not ids:
        return None
    marcadores = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT id, title, due_date, hora, due_at, recorrencia, completed_at FROM tasks WHERE id IN ({marcadores})",
        list(ids),
    ).fetchall()
    por_id = {r["id"]: r for r in rows}
    tarefas = [_tarefa_dict(por_id[i]) for i in ids if i in por_id]
    if not tarefas:
        return None
    aba, rotulo = ABA_POR_ENTIDADE["tarefa"]
    actions = [acao_abrir_aba(aba, rotulo, "tarefa", tarefas[0]["id"])] + list(actions_extra or [])
    return novo_card("tarefas_criadas", {"tarefas": tarefas}, actions)


def card_transacao(conn, entidade: str, id_: int, meio=None, saldo=None, actions_extra=None) -> dict | None:
    if entidade == "gasto":
        row = conn.execute(
            "SELECT id, amount, category, description, tipo FROM expenses WHERE id = ?", (id_,)
        ).fetchone()
        if not row:
            return None
        data = {
            "id": row["id"],
            "entidade": "gasto",
            "sentido": "saida",
            "titulo": row["description"] or row["category"],
            "valor": float(row["amount"]),
            "categoria": row["category"],
            "status": row["tipo"] or "real",
        }
    elif entidade == "renda":
        row = conn.execute("SELECT id, amount, category, description FROM incomes WHERE id = ?", (id_,)).fetchone()
        if not row:
            return None
        data = {
            "id": row["id"],
            "entidade": "renda",
            "sentido": "entrada",
            "titulo": row["description"] or row["category"],
            "valor": float(row["amount"]),
            "categoria": row["category"],
            "status": "real",
        }
    else:
        return None
    data["data"] = date.today().isoformat()
    data["meio"] = (str(meio).strip() or None) if meio else None
    data["saldo"] = (
        {"conta": saldo.get("banco"), "antes": saldo.get("antes"), "depois": saldo.get("depois")}
        if isinstance(saldo, dict)
        else None
    )
    data["oculto"] = False
    aba, rotulo = ABA_POR_ENTIDADE[entidade]
    actions = [acao_abrir_aba(aba, rotulo, entidade, data["id"])] + list(actions_extra or [])
    return novo_card("transacao", data, actions)


def card_meta(conn, id_: int, actions_extra=None) -> dict | None:
    row = conn.execute(
        "SELECT id, titulo, valor_alvo, valor_guardado, prazo FROM goals WHERE id = ?", (id_,)
    ).fetchone()
    if not row:
        return None
    alvo = float(row["valor_alvo"] or 0)
    guardado = float(row["valor_guardado"] or 0)
    percentual = round(min(100.0, guardado / alvo * 100), 1) if alvo > 0 else 0.0
    data = {
        "id": row["id"],
        "titulo": row["titulo"],
        "valor_guardado": guardado,
        "valor_alvo": alvo,
        "percentual": percentual,
        "falta": round(max(0.0, alvo - guardado), 2),
        "prazo": row["prazo"],
        "oculto": False,
    }
    aba, rotulo = ABA_POR_ENTIDADE["meta"]
    actions = [acao_abrir_aba(aba, rotulo, "meta", row["id"])] + list(actions_extra or [])
    return novo_card("meta", data, actions)


def card_lembrete(conn, id_: int, actions_extra=None) -> dict | None:
    row = conn.execute("SELECT * FROM lembretes WHERE id = ?", (id_,)).fetchone()
    if not row:
        return None
    chaves = row.keys()
    despertar = bool(row["despertar"]) if "despertar" in chaves else False
    data = {
        "id": row["id"],
        "titulo": row["titulo"],
        "data": row["data"],
        "hora": row["hora"] if "hora" in chaves else None,
        "recorrente": bool(row["recorrente"]),
        "despertar": despertar,
    }
    aba, rotulo = ABA_POR_ENTIDADE["lembrete"]
    actions = list(actions_extra or []) + [
        acao_despertar(row["id"], despertar),
        acao_abrir_aba(aba, rotulo, "lembrete", row["id"]),
    ]
    return novo_card("lembrete", data, actions)


def _rotulo_contagem(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def card_resumo_final(cards_lista: list[dict], passos: list[dict]) -> dict | None:
    """So faz sentido quando a resposta tocou 2+ cards (brain dump). Texto
    das linhas nunca tem valor em dinheiro (nao passa por mascaramento)."""
    contagem: dict[tuple[str, str], int] = {}
    for c in cards_lista:
        t = c.get("type")
        d = c.get("data") or {}
        if t == "tarefas_criadas":
            chave = ("Tarefas", "tarefa")
            contagem[chave] = contagem.get(chave, 0) + len(d.get("tarefas") or [])
        elif t == "transacao":
            chave = ("Finanças", "renda" if d.get("sentido") == "entrada" else "gasto")
            contagem[chave] = contagem.get(chave, 0) + 1
        elif t == "meta":
            contagem[("Metas", "meta")] = contagem.get(("Metas", "meta"), 0) + 1
        elif t == "lembrete":
            contagem[("Lembretes", "lembrete")] = contagem.get(("Lembretes", "lembrete"), 0) + 1
        elif t in ("agenda", "habito", "projeto_viagem", "saude_treino", "sugestao"):
            modulo = {
                "agenda": "Agenda",
                "habito": "Hábitos",
                "projeto_viagem": "Projetos",
                "saude_treino": "Saúde",
                "sugestao": "Agenda",
            }[t]
            contagem[(modulo, t)] = contagem.get((modulo, t), 0) + 1
    frases = {
        "tarefa": ("tarefa criada", "tarefas criadas"),
        "gasto": ("gasto registrado", "gastos registrados"),
        "renda": ("entrada registrada", "entradas registradas"),
        "meta": ("meta criada", "metas criadas"),
        "lembrete": ("lembrete criado", "lembretes criados"),
        "agenda": ("evento na agenda", "eventos na agenda"),
        "habito": ("hábito atualizado", "hábitos atualizados"),
        "projeto_viagem": ("projeto atualizado", "projetos atualizados"),
        "saude_treino": ("registro de treino", "registros de treino"),
        "sugestao": ("horário sugerido", "horários sugeridos"),
    }
    por_modulo: dict[str, list[str]] = {}
    for (modulo, chave), n in contagem.items():
        if n <= 0:
            continue
        singular, plural = frases[chave]
        por_modulo.setdefault(modulo, []).append(_rotulo_contagem(n, singular, plural))
    if not por_modulo:
        return None
    linhas = [{"modulo": m, "texto": ", ".join(txts)} for m, txts in por_modulo.items()]
    modulos = []
    for p in passos:
        if p.get("modulo") and p["modulo"] not in modulos:
            modulos.append(p["modulo"])
    for m in por_modulo:
        if m not in modulos:
            modulos.append(m)
    data = {
        "linhas": linhas,
        "passos_total": len(passos),
        "duracao_ms": sum(int(p.get("ms") or 0) for p in passos),
        "modulos": modulos,
    }
    return novo_card("resumo_final", data, [])


def _acoes_desfazer(criar_token, itens: list[dict]) -> list[dict]:
    if not criar_token or not itens:
        return []
    token = criar_token(itens)
    return [acao_desfazer(token, itens)] if token else []


def cards_dos_efeitos(conn, efeitos: list[dict], criar_token=None) -> list[dict]:
    """UNICO mapeamento efeito -> card. Tarefas criadas na mesma resposta
    viram UM card `tarefas_criadas` (na posicao da primeira) com um token de
    desfazer so pra elas; todo outro efeito vira o proprio card com o proprio
    token (brain dump: cada card se desfaz independente).

    `criar_token(itens) -> str`: grava os ids exatos numa tabela de desfazer
    (db.criar_acao_desfazer) e devolve o token; None = sem botao Desfazer."""
    saida: list[dict] = []
    tarefas_ids: list[int] = []
    pos_tarefas = None
    tarefas_itens: list[dict] = []
    for ef in efeitos:
        entidade = ef.get("entidade")
        id_ = ef.get("id")
        if entidade == "tarefa" and isinstance(id_, int):
            if pos_tarefas is None:
                pos_tarefas = len(saida)
                saida.append(None)  # reserva a posicao
            tarefas_ids.append(id_)
            tarefas_itens.append(ef)
            continue
        card = None
        if entidade in ("gasto", "renda") and isinstance(id_, int):
            card = card_transacao(
                conn, entidade, id_, ef.get("meio"), ef.get("saldo"), _acoes_desfazer(criar_token, [ef])
            )
        elif entidade == "meta" and isinstance(id_, int):
            card = card_meta(conn, id_, _acoes_desfazer(criar_token, [ef]))
        elif entidade == "lembrete" and isinstance(id_, int):
            card = card_lembrete(conn, id_, _acoes_desfazer(criar_token, [ef]))
        if card:
            saida.append(card)
    if pos_tarefas is not None:
        card = card_tarefas_criadas(conn, tarefas_ids, _acoes_desfazer(criar_token, tarefas_itens))
        saida[pos_tarefas] = card
    saida = [c for c in saida if c]
    return saida


def montar_resposta(conn, efeitos: list[dict], resumo_texto: str, passos: list[dict], criar_token=None) -> dict:
    """Efeitos -> cards (+ resumo_final quando 2+ cards) -> envelope."""
    lista = cards_dos_efeitos(conn, efeitos, criar_token)
    if len(lista) >= 2:
        resumo = card_resumo_final(lista, passos)
        if resumo:
            lista.append(resumo)
    return envelope(lista, resumo_texto, passos)


# ---- modo visitante ---------------------------------------------------------

_RE_VALOR = re.compile(r"(?:R\$|US\$|\$)\s*-?\s*\d[\d.,]*")


def ocultar_valores_texto(texto):
    """Troca valor em dinheiro escrito no texto (R$ 1.234,56 / US$ 3) por
    'R$ •••' - rede de seguranca pra prosa (resposta da IA, resumo_texto) no
    modo visitante; o card em si ja sai sem o campo."""
    if not isinstance(texto, str):
        return texto
    return _RE_VALOR.sub("R$ •••", texto)


def mascarar_cards(cards_lista: list) -> list:
    saida = []
    for card in cards_lista or []:
        c = copy.deepcopy(card)
        campos = CAMPOS_SENSIVEIS.get(c.get("type"))
        if campos and isinstance(c.get("data"), dict):
            for campo in campos:
                c["data"].pop(campo, None)
            c["data"]["oculto"] = True
        saida.append(c)
    return saida


def mascarar_visitante(resposta: dict) -> dict:
    """Copia da resposta (envelope + campos legados) sem nenhum valor em
    dinheiro: cards sem os campos sensiveis, prosa com valor trocado por
    'R$ •••', legado `valor`/`saldo_banco` removido."""
    r = copy.deepcopy(resposta)
    if "cards" in r:
        r["cards"] = mascarar_cards(r["cards"])
    for campo in ("resumo_texto", "resposta", "duvida"):
        if campo in r:
            r[campo] = ocultar_valores_texto(r[campo])
    r.pop("valor", None)
    return r
