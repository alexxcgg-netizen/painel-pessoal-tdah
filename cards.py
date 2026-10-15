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
from datetime import date, datetime, timedelta

import calculos
import db
import financas_recorrentes as fr
import vida

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
    "consultar_meta": "Metas",
    "registrar_habito": "Hábitos",
    "marcar_habito": "Hábitos",
    "consultar_habitos": "Hábitos",
    "criar_projeto": "Projetos",
    "adicionar_etapa": "Projetos",
    "concluir_etapa": "Projetos",
    "consultar_projeto": "Projetos",
    "agendar_evento": "Agenda",
    "consultar_treinos": "Saúde",
    "consultar_saude_dia": "Saúde",
    "consultar_tarefas": "Tarefas",
    "consultar_gastos": "Finanças",
    "consultar_agenda": "Agenda",
    "consultar_voos": "Aviação",
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
    "ajustar_antecedencia_voo": "Aviação",
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
    "consultar_projeto": "Buscou o projeto",
    "consultar_meta": "Buscou a meta",
    "consultar_habitos": "Buscou os hábitos",
    "consultar_treinos": "Buscou os treinos",
    "consultar_saude_dia": "Buscou a saúde do dia",
    "consultar_tarefas": "Consultou as tarefas",
    "ajustar_tarefa": "Ajustou uma tarefa",
    "mover_tarefas": "Moveu as tarefas",
    "ajustar_lembrete": "Ajustou um lembrete",
    "ajustar_voo": "Corrigiu um voo",
    "ajustar_gasto": "Ajustou um gasto",
    "definir_meta_horas_voo": "Definiu a meta de horas",
    "planejar_compras_viagem": "Planejou as compras da viagem",
    "consultar_clima": "Consultou o tempo",
    "estimar_trajeto": "Calculou o trajeto",
    "consultar_gastos": "Consultou os gastos",
    "consultar_agenda": "Consultou a agenda",
    "consultar_voos": "Consultou os voos",
    "briefing_meteo_voo": "Leu o METAR e o TAF",
    "fazer_pergunta_aviacao": "Montou uma pergunta da banca",
    "revisar_pergunta_aviacao": "Puxou uma revisão",
    "responder_pergunta_aviacao": "Corrigiu a resposta",
    "marcar_habito": "Marcou o hábito de hoje",
    "concluir_etapa": "Concluiu a etapa do projeto",
}

# Linha "pensando" ao vivo (2026-10-14, 3a leva): o que a ferramenta esta fazendo AGORA, no
# presente. Mesma regra de `passos`: nunca valor em dinheiro.
AO_VIVO_TOOL = {
    "registrar_voo": "Montando a rota do voo",
    "registrar_feito": "Marcando como feito",
    "ajustar_tarefa": "Ajustando a tarefa",
    "mover_tarefas": "Movendo as tarefas",
    "consultar_tarefas": "Olhando tuas tarefas",
    "consultar_agenda": "Olhando a agenda",
    "consultar_gastos": "Somando os gastos",
    "consultar_gastos_fixos": "Olhando os gastos fixos",
    "consultar_sobra_do_mes": "Calculando a sobra do mês",
    "consultar_voos": "Olhando os voos",
    "consultar_clima": "Vendo o tempo",
    "estimar_trajeto": "Calculando o trajeto",
    "briefing_meteo_voo": "Lendo o METAR e o TAF",
    "gerar_plano_do_dia": "Montando o plano do dia",
    "sugerir_horario_livre": "Procurando horário livre",
    "sugerir_tarefa_para_agora": "Escolhendo uma tarefa pra agora",
    "registrar_memoria": "Guardando isso na memória",
    "consultar_notas": "Procurando nas notas",
    "salvar_nota": "Salvando a nota",
    "registrar_hidratacao": "Contando o copo d'água",
    "registrar_treino": "Registrando o treino",
    "adicionar_compras": "Pondo na lista de compras",
    "consultar_noticias": "Buscando notícias",
    "fazer_pergunta_aviacao": "Escolhendo uma pergunta da banca",
    "revisar_pergunta_aviacao": "Puxando uma revisão",
    "responder_pergunta_aviacao": "Corrigindo a resposta",
    "consultar_saude_dia": "Olhando a saúde de hoje",
    "consultar_habitos": "Olhando os hábitos",
    "marcar_habito": "Marcando o hábito",
    "ajustar_lembrete": "Ajustando o lembrete",
    "ajustar_gasto": "Ajustando o gasto",
    "ajustar_voo": "Corrigindo o voo",
}
_AO_VIVO_COM_TITULO = {
    "registrar_tarefa": ("titulo", "Anotando"),
    "registrar_gasto": ("titulo", "Registrando o gasto"),
    "registrar_lembrete": ("titulo", "Criando o lembrete"),
    "registrar_meta": ("titulo", "Criando a meta"),
    "registrar_habito": ("nome", "Criando o hábito"),
    "criar_projeto": ("nome", "Criando o projeto"),
}


def passo_ao_vivo(tool: str, entrada) -> str:
    entrada = entrada if isinstance(entrada, dict) else {}
    if tool in _AO_VIVO_COM_TITULO:
        campo, verbo = _AO_VIVO_COM_TITULO[tool]
        titulo = _titulo_curto(entrada.get(campo), 40)
        return f'{verbo} "{titulo}"' if titulo else verbo
    if tool in AO_VIVO_TOOL:
        return AO_VIVO_TOOL[tool]
    modulo = MODULO_POR_TOOL.get(tool)
    return f"Mexendo em {modulo.lower()}" if modulo else "Trabalhando nisso"


def _avisar_passo(texto: str) -> None:
    try:
        import claude_client

        claude_client.avisar_passo(texto)
    except Exception:  # noqa: BLE001 - aviso de tela nunca derruba a ferramenta
        pass


ABA_POR_ENTIDADE = {
    "tarefa": ("tarefas", "Abrir Tarefas"),
    "gasto": ("gastos", "Abrir no extrato"),
    "renda": ("gastos", "Abrir no extrato"),
    "meta": ("gastos", "Abrir Metas"),
    "lembrete": ("painel", "Abrir em Lembretes"),
    "habito": ("vida", "Abrir Hábitos"),
    "projeto": ("vida", "Abrir Projetos"),
    "viagem": ("vida", "Abrir Viagens"),
    "evento": ("vida", "Abrir Agenda"),
    "treino": ("vida", "Abrir Treinos"),
    # Fase 7 (N1, ligado na C1): secao Assinaturas mora na aba gastos
    # (templates/secoes/gastos/assinaturas.html).
    "assinatura": ("gastos", "Abrir Assinaturas"),
    "compra_parcelada": ("gastos", "Abrir Assinaturas"),
}

# Campos com valor em dinheiro, por type - removidos no modo visitante
# (docs/CARDS.md, "Modo visitante"). Card novo com dinheiro entra aqui.
CAMPOS_SENSIVEIS = {
    "transacao": ("valor", "saldo", "mes", "dias"),
    "assinatura_subiu": ("de", "para", "pct"),
    # 2026-10-13 (conversa_proativa): dinheiro e agua (saude) saem no modo visitante
    "fechar_dia": ("gasto", "agua"),
    "semana": ("gasto", "gasto_ant", "gastos_dia", "agua_dia"),
    "meta": ("valor_guardado", "valor_alvo", "falta"),
    # Revisao da Fase 6: dado de saude (Apple Saude/treinos/agua) e tao
    # sensivel quanto dinheiro - /api/saude/hoje ja devolvia `oculto` no
    # modo visitante, mas os cards do chat/historico vazavam sono/passos.
    "saude_dia": ("agua_copos", "passos", "sono_horas", "treino_min"),
    "saude_treino": ("sessoes", "semana"),
    "agua": ("copos",),
    "gastos_resumo": ("total", "por_categoria", "maiores"),
    # Fase 7 (N1, ligado na C1 - checklist de docs/contrato-assinaturas.md).
    # `proximas_cobrancas`/`proxima_cobranca` saem inteiros no modo
    # visitante (trazem `valor` dentro).
    "assinatura": ("valor",),
    "compra_parcelada": ("valor_total", "valor_parcela"),
    "resumo_financeiro_recorrente": (
        "total_mensal", "assinaturas_total", "parcelas_total", "total_mes",
        "proximas_cobrancas", "proxima_cobranca",
    ),
}

# Action que MUDA dado (nunca sai no modo visitante - o servidor tambem
# recusa POST /api/desfazer com 403, isto so evita mostrar o botao/token).
ACTIONS_BLOQUEADAS_VISITANTE = ("desfazer",)

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
    "saude_dia",
    # Fase 7 (N1, ligado na C1)
    "assinatura",
    "compra_parcelada",
    "resumo_financeiro_recorrente",
    "rota",
    "refeicao",
    # cartoes vivos (2026-10-09): animados no front (static/js/cards-vivos.js)
    "edicao",
    "voo_resumo",
    "clima",
    "gastos_resumo",
    "dia",
    "viagem_janelas",
    "agua",
    "tarefas_lista",
    # professor de aviacao (2026-10-13)
    "briefing_voo",
    "quiz_aviacao",
    # painel puxando assunto (2026-10-13, conversa_proativa.py)
    "fechar_dia",
    "semana",
    # linguagem visual aprovada (2026-10-14, docs/CARDS.md)
    "voo_agendado",
    "tarefa_feita",
    # 2a leva (2026-10-14): compromisso com cara propria (tasks.estilo)
    "date",
    "balada",
    "documentos",
    "presente",
    # 3a leva (2026-10-14): quanto deu o voo (conversa_proativa, depois do pouso)
    "voo_horas",
    # 4a leva (2026-10-15, docs/briefings/2026-10-15-4a-leva.md): automacoes
    "vespera_voo",
    "documento_validade",
    "compras_previsao",
    "assinatura_subiu",
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
        # chave com "_" (ex: "_consulta") e marcador interno do servidor
        c = {k: v for k, v in card.items() if not str(k).startswith("_")}
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
            _avisar_passo(passo_ao_vivo(nome, entrada))
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
    if tool == "registrar_habito":
        return f'Criou o hábito "{_titulo_curto(entrada.get("nome"))}"'
    if tool == "criar_projeto":
        return f'Criou o projeto "{_titulo_curto(entrada.get("nome"))}"'
    if tool == "adicionar_etapa":
        return f'Adicionou a etapa "{_titulo_curto(entrada.get("texto"))}"'
    if tool == "agendar_evento":
        return f'Agendou "{_titulo_curto(entrada.get("titulo"))}"'
    if tool == "registrar_viagem":
        return f'Registrou a viagem pra {_titulo_curto(entrada.get("destino"))}'
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
        "local": row["local"] if "local" in row.keys() else None,
    }


def _e_conclusao(ef: dict) -> bool:
    """Tarefa concluida pelo chat: registrar_feito marca `feito`; ajustar_tarefa(status=concluir)
    vira uma edicao so do completed_at. As duas viram o card tarefa_feita."""
    if not isinstance(ef.get("id"), int):
        return False
    if ef.get("feito") is True and ef.get("entidade") in ("edicao", "tarefa"):
        return True
    depois = ef.get("depois")
    return (
        ef.get("entidade") == "edicao" and ef.get("tabela") == "tasks" and isinstance(depois, dict)
        and set(depois) == {"completed_at"} and bool(depois["completed_at"])
    )


def card_tarefa_feita(conn, id_: int, actions_extra: list | None = None, agora: datetime | None = None) -> dict | None:
    """Concluir (2026-10-14, docs/CARDS.md "Linguagem visual"): a tarefa riscada, o anel do dia
    (feitas/total das tarefas de hoje, contando esta) e a proxima pendente de hoje."""
    agora = agora or datetime.now()
    hoje = agora.date().isoformat()
    row = conn.execute("SELECT id, title, completed_at FROM tasks WHERE id = ?", (id_,)).fetchone()
    if not row:
        return None
    dia = conn.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(completed_at IS NOT NULL), 0) AS feitas FROM tasks "
        "WHERE (due_date = ? OR id = ?) AND NOT (recorrencia IS NOT NULL AND due_date IS NULL)",
        (hoje, id_),
    ).fetchone()
    pendentes = conn.execute(
        "SELECT title, hora FROM tasks WHERE due_date = ? AND completed_at IS NULL AND id != ? "
        "AND NOT (recorrencia IS NOT NULL AND due_date IS NULL) ORDER BY hora IS NULL, hora, id",
        (hoje, id_),
    ).fetchall()
    agora_hhmm = agora.strftime("%H:%M")
    # a proxima com hora que ainda nao passou; senao a primeira sem hora
    prox = next((p for p in pendentes if p["hora"] and p["hora"] >= agora_hhmm), None) or next(
        (p for p in pendentes if not p["hora"]), None
    )
    proxima = None
    if prox:
        # quanto falta e conta do front (com a hora de quem esta vendo - no historico tambem)
        proxima = {"titulo": _titulo_curto(prox["title"], 70), "hora": prox["hora"]}
    aba, rotulo = ABA_POR_ENTIDADE["tarefa"]
    data = {
        "id": row["id"],
        "titulo": _titulo_curto(row["title"], 120),
        "data": hoje,
        "hora": agora_hhmm,
        "feitas": int(dia["feitas"]),
        "total": int(dia["total"]),
        "faltam": len(pendentes),
        "proxima": proxima,
    }
    return novo_card("tarefa_feita", data, list(actions_extra or []) + [acao_abrir_aba(aba, rotulo, "tarefa", row["id"])])


# Tarefa com aperto (2026-10-14, docs/CARDS.md "Linguagem visual"): a nova cai a menos de
# APERTO_MIN de outra pendente do mesmo dia. So horarios de inicio (tarefa nao tem duracao);
# a sugestao poe a outra a SUGESTAO_MIN de distancia, se nao apertar uma terceira.
APERTO_MIN = 45
SUGESTAO_MIN = 60


def _min_do_dia(hora) -> int | None:
    try:
        h, m = (int(x) for x in str(hora).split(":")[:2])
    except (TypeError, ValueError):
        return None
    return h * 60 + m if 0 <= h <= 23 and 0 <= m <= 59 else None


def _aperto(conn, tarefa: dict) -> dict | None:
    nova = _min_do_dia(tarefa.get("hora"))
    if nova is None or not tarefa.get("data") or tarefa.get("recorrencia") or tarefa.get("concluida"):
        return None
    outras = [
        (r, _min_do_dia(r["hora"]))
        for r in conn.execute(
            "SELECT id, title, hora FROM tasks WHERE due_date = ? AND id != ? AND completed_at IS NULL "
            "AND hora IS NOT NULL AND NOT (recorrencia IS NOT NULL AND due_date IS NULL)",
            (tarefa["data"], tarefa["id"]),
        ).fetchall()
    ]
    outras = [(r, m) for r, m in outras if m is not None]
    perto = sorted(((abs(m - nova), r, m) for r, m in outras if abs(m - nova) < APERTO_MIN), key=lambda x: (x[0], x[1]["id"]))
    if not perto:
        return None
    _, outra, m_outra = perto[0]
    alvo = nova - SUGESTAO_MIN if m_outra <= nova else nova + SUGESTAO_MIN
    livre = 5 * 60 <= alvo <= 23 * 60 + 30 and all(
        abs(m - alvo) >= APERTO_MIN for r, m in outras if r["id"] != outra["id"]
    )
    return {
        "id": outra["id"],
        "titulo": _titulo_curto(outra["title"], 60),
        "hora": f"{m_outra // 60:02d}:{m_outra % 60:02d}",
        "sugestao": f"{alvo // 60:02d}:{alvo % 60:02d}" if livre else None,
    }


VOLTA_MODOS = ("dirigindo", "carona", "uber")


def modo_volta(extras: dict) -> str:
    """Como volta da balada; card da 2a leva com a chave do Uber ligada (`uber`) = Uber."""
    if extras.get("volta_modo") in VOLTA_MODOS:
        return extras["volta_modo"]
    return "uber" if extras.get("uber") else "dirigindo"  # 3a leva: o normal dele e voltar dirigindo
VOLTA_PADRAO_BALADA = "03:00"  # pedido do Alex: so conta sono se tiver compromisso com hora no dia seguinte


def _hhmm_menos(hora: str | None, minutos: int) -> str | None:
    m = _min_do_dia(hora)
    if m is None:
        return None
    m = (m - minutos) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def card_compromisso(conn, ef: dict, actions_extra: list | None = None, hoje: date | None = None) -> dict | None:
    """Date, balada, documentos e presente (2026-10-14, docs/CARDS.md "Linguagem visual" - 2a
    leva). Tudo que precisou de rede (trajeto, clima, horario do Google, compromisso do dia
    seguinte) veio pronto no efeito; o resto e conta daqui, sem rede."""
    import vida_assistente

    hoje = hoje or date.today()
    row = conn.execute(
        "SELECT id, title, due_date, hora, local, estilo, extras FROM tasks WHERE id = ?", (ef.get("id"),)
    ).fetchone()
    if not row or row["estilo"] not in db.ESTILOS_TAREFA or not row["due_date"]:
        return None
    estilo = row["estilo"]
    extras = db.extras_tarefa(conn, row["id"])
    data = {
        "id": row["id"],
        "titulo": _titulo_curto(row["title"], 90),
        "data": row["due_date"],
        "hora": row["hora"],
        "lugar": row["local"],
        "com_quem": extras.get("com_quem"),
    }
    if estilo in ("date", "balada") and row["hora"]:
        arrumar = vida_assistente.se_arrumar_min(conn)
        saida = ef.get("saida") if isinstance(ef.get("saida"), dict) else None
        sair = (saida or {}).get("sair") or _hhmm_menos(row["hora"], 15)
        data.update({
            "comecar": _hhmm_menos(sair, arrumar),
            "sair": sair,
            "arrumar_min": arrumar,
            "trajeto_min": (saida or {}).get("trajeto_min"),
        })
        if isinstance(ef.get("clima"), dict):
            data["clima"] = {"temp": ef["clima"].get("temp"), "chuva_pct": ef["clima"].get("chuva_pct")}
    if estilo == "date":
        data["lista"] = extras.get("lista") or []
    elif estilo == "balada":
        amanha = ef.get("amanha") if isinstance(ef.get("amanha"), dict) else None
        volta = extras.get("volta") or (VOLTA_PADRAO_BALADA if amanha else None)
        data["volta"] = volta
        data["volta_dita"] = bool(extras.get("volta"))
        data["volta_modo"] = modo_volta(extras)
        if amanha and volta and _min_do_dia(amanha.get("acordar")) is not None:
            v, a = _min_do_dia(volta), _min_do_dia(amanha["acordar"])
            # volta antes do meio-dia = madrugada do dia seguinte; senao ainda e a mesma noite
            sono = a - v if v < 12 * 60 else (24 * 60 - v) + a
            data["sono"] = {
                "min": max(0, sono), "volta": volta, "acordar": amanha["acordar"],
                "compromisso": _titulo_curto(amanha.get("titulo") or "", 40), "hora": amanha.get("hora"),
            }
    elif estilo == "documentos":
        data["lista"] = extras.get("lista") or []
        if isinstance(ef.get("horario"), dict):
            data["horario"] = ef["horario"]
    elif estilo == "presente":
        dia = date.fromisoformat(row["due_date"])
        compra = max(hoje, dia - timedelta(days=4))
        data.update({
            "dias": (dia - hoje).days,
            "compra_ate": compra.isoformat(),
            "ideias": extras.get("ideias") or [],
            "escolha": extras.get("escolha") if isinstance(extras.get("escolha"), int) else None,
            "anual": bool(extras.get("anual")),
            "ano_passado": ((extras.get("historico") or [None])[-1] or {}).get("presente"),
        })
    aba, rotulo = ABA_POR_ENTIDADE["tarefa"]
    actions = list(actions_extra or []) + [acao_abrir_aba(aba, rotulo, "tarefa", row["id"])]
    return novo_card(estilo, data, actions)


def card_tarefas_criadas(conn, ids: list[int], actions_extra: list | None = None) -> dict | None:
    if not ids:
        return None
    marcadores = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT id, title, due_date, hora, due_at, recorrencia, completed_at, local FROM tasks WHERE id IN ({marcadores})",
        list(ids),
    ).fetchall()
    por_id = {r["id"]: r for r in rows}
    tarefas = [_tarefa_dict(por_id[i]) for i in ids if i in por_id]
    if not tarefas:
        return None
    aba, rotulo = ABA_POR_ENTIDADE["tarefa"]
    actions = [acao_abrir_aba(aba, rotulo, "tarefa", tarefas[0]["id"])] + list(actions_extra or [])
    data = {"tarefas": tarefas}
    # cartao vivo (2026-10-10): o DIA em volta da tarefa nova - as outras do mesmo dia, pra
    # ela "pousar" no lugar certo da linha do tempo
    dia = next((t["data"] for t in tarefas if t.get("data") and not t.get("recorrencia")), None)
    if dia:
        novos = {t["id"] for t in tarefas}
        outras = conn.execute(
            "SELECT id, title, hora, completed_at FROM tasks WHERE due_date = ? "
            "AND NOT (recorrencia IS NOT NULL AND due_date IS NULL) ORDER BY hora IS NULL, hora, id LIMIT 12",
            (dia,),
        ).fetchall()
        data["dia"] = dia
        if len(tarefas) == 1:
            aperto = _aperto(conn, tarefas[0])
            if aperto:
                data["aperto"] = aperto
        data["agenda_do_dia"] = [
            {"id": r["id"], "titulo": r["title"], "hora": r["hora"], "concluida": bool(r["completed_at"]),
             "nova": r["id"] in novos}
            for r in outras
        ]
    return novo_card("tarefas_criadas", data, actions)


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
    if entidade == "gasto" and data["status"] == "real":
        data.update(_contexto_gasto(conn, data["categoria"], data["valor"]))
    aba, rotulo = ABA_POR_ENTIDADE[entidade]
    actions = [acao_abrir_aba(aba, rotulo, entidade, data["id"])] + list(actions_extra or [])
    return novo_card("transacao", data, actions)


def _contexto_gasto(conn, categoria: str, valor: float, hoje: date | None = None) -> dict:
    """Card do gasto (2026-10-14, docs/CARDS.md "Linguagem visual"): quanto a categoria ja
    tem no mes (com este gasto), o teto se houver orcamento, quanto sobra por dia ate o fim
    do mes e os ultimos 14 dias da categoria (barrinhas, hoje no fim). Mesma regra de
    db.gasto_mes_por_categoria (gasto real, mes do created_at)."""
    hoje = hoje or date.today()
    mes = db.gasto_mes_por_categoria(conn, categoria, hoje.strftime("%Y-%m"))
    limite = db.obter_orcamento(conn, categoria)
    proximo = (hoje.replace(day=28) + timedelta(days=4)).replace(day=1)
    dias_restantes = (proximo - hoje).days  # conta hoje
    inicio = hoje - timedelta(days=13)
    por_dia = {
        r["dia"]: float(r["total"])
        for r in conn.execute(
            # created_at e UTC (datetime('now')); o dia da barrinha e o dia daqui
            "SELECT date(created_at, 'localtime') AS dia, SUM(amount) AS total FROM expenses "
            "WHERE category = ? AND tipo = 'real' AND date(created_at, 'localtime') >= ? GROUP BY dia",
            (categoria, inicio.isoformat()),
        ).fetchall()
    }
    mes_ctx = {
        "categoria": categoria,
        "gasto": round(float(mes), 2),
        "antes": round(max(0.0, float(mes) - valor), 2),
        "limite": float(limite) if limite else None,
        "dias_restantes": dias_restantes,
    }
    if limite:
        mes_ctx["sobra"] = round(float(limite) - float(mes), 2)
        mes_ctx["sobra_dia"] = round(max(0.0, float(limite) - float(mes)) / dias_restantes, 2)
    return {
        "mes": mes_ctx,
        "dias": [round(por_dia.get((inicio + timedelta(days=i)).isoformat(), 0.0), 2) for i in range(14)],
    }


def card_meta(conn, id_: int, actions_extra=None) -> dict | None:
    row = conn.execute(
        "SELECT id, titulo, valor_alvo, valor_guardado, prazo FROM goals WHERE id = ?", (id_,)
    ).fetchone()
    if not row:
        return None
    alvo = float(row["valor_alvo"] or 0)
    guardado = float(row["valor_guardado"] or 0)
    percentual = calculos.percentual_meta_exibicao(guardado, alvo)  # C1: funcao unica
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
        "local": row["local"] if "local" in chaves else None,
    }
    aba, rotulo = ABA_POR_ENTIDADE["lembrete"]
    actions = list(actions_extra or []) + [
        acao_despertar(row["id"], despertar),
        acao_abrir_aba(aba, rotulo, "lembrete", row["id"]),
    ]
    return novo_card("lembrete", data, actions)


# ---- cards dos modulos da Fase 6 (US-E7: habito, projeto/viagem, agenda,
# saude, sugestao) - adaptadores de formato + builders ----------------------

DIAS_SEMANA_CURTOS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def semana_seg_dom(datas_feitas, hoje: date) -> list[dict]:
    """Adaptador (puro): o card `habito` quer SEMPRE 7 itens segunda->domingo
    da semana de `hoje` (docs/CARDS.md), enquanto GET /api/habitos expoe
    `ultimos_7` (janela movel dos 7 dias ate hoje, com letra/hoje). As datas
    feitas de qualquer fonte viram a semana calendario aqui."""
    feitas = {str(d) for d in (datas_feitas or ())}
    segunda = hoje - timedelta(days=hoje.weekday())
    semana = []
    for i in range(7):
        dia = (segunda + timedelta(days=i)).isoformat()
        semana.append({"data": dia, "feito": dia in feitas})
    return semana


def texto_frequencia_habito(habito: dict) -> str | None:
    tipo = habito.get("frequencia_tipo")
    if tipo == "dias_semana":
        dias = sorted(d for d in vida.parse_dias_semana(habito.get("dias_semana")) if 0 <= d <= 6)
        return ", ".join(DIAS_SEMANA_CURTOS[d] for d in dias) or None
    if tipo == "n_vezes_semana" and habito.get("vezes_por_semana"):
        return f"{habito['vezes_por_semana']}x por semana · qualquer dia conta"
    return "todo dia"


def habito_para_card(habito: dict, datas_feitas, hoje: date, ativos_antes=None, ativos_depois=None, contexto=None) -> dict:
    """Adaptador (puro): linha de `habitos` + datas marcadas -> `data` do card habito."""
    return {
        "id": habito["id"],
        "nome": habito["nome"],
        "meta": habito.get("meta"),
        "frequencia": texto_frequencia_habito(habito),
        "horario": habito.get("horario"),
        "hoje": hoje.isoformat(),
        "semana": semana_seg_dom(datas_feitas, hoje),
        "ativos_antes": ativos_antes,
        "ativos_depois": ativos_depois,
        "contexto": contexto,
    }


def card_habito(conn, habito_id: int, hoje: date | None = None, ativos_antes=None, ativos_depois=None,
                contexto=None, actions_extra=None) -> dict | None:
    hoje = hoje or date.today()
    row = conn.execute("SELECT * FROM habitos WHERE id = ?", (habito_id,)).fetchone()
    if not row:
        return None
    habito = dict(row)
    segunda = hoje - timedelta(days=hoje.weekday())
    feitas = db.marcacoes_habito_no_periodo(
        conn, habito_id, segunda.isoformat(), (segunda + timedelta(days=6)).isoformat()
    )
    if contexto is None and habito.get("frequencia_tipo") == "n_vezes_semana" and habito.get("vezes_por_semana"):
        contexto = f"{len(feitas)} de {habito['vezes_por_semana']} vezes nesta semana."
    data = habito_para_card(habito, feitas, hoje, ativos_antes, ativos_depois, contexto)
    aba, rotulo = ABA_POR_ENTIDADE["habito"]
    actions = list(actions_extra or []) + [acao_abrir_aba(aba, rotulo, "habito", habito_id)]
    return novo_card("habito", data, actions)


def projeto_para_card(detalhe: dict, origem: str = "projeto", titulo: str | None = None, id_=None) -> dict:
    """Adaptador (puro): formato de GET /api/projetos (vida.projeto_detalhado)
    ou de /api/viagens/<id>/como-projeto -> `data` do card projeto_viagem.
    Escala: `posicao_hoje` do modulo e 0-100 (ou None); o card quer
    `hoje_fracao` 0..1."""
    etapas = []
    for e in detalhe.get("etapas") or []:
        data_etapa = e.get("data_prevista") or ((e.get("feita_em") or "")[:10] or None)
        etapas.append({"titulo": e.get("texto"), "feito": bool(e.get("feita")), "data": data_etapa})
    proxima = detalhe.get("proxima_etapa")
    posicao = detalhe.get("posicao_hoje")
    return {
        "id": id_ if id_ is not None else detalhe.get("id"),
        "origem": origem,
        "titulo": titulo or detalhe.get("nome"),
        "inicio": (detalhe.get("criado_em") or "")[:10] or None,
        "prazo": detalhe.get("prazo_final"),
        "etapas": etapas,
        "proximo_marco": (
            {"titulo": proxima.get("texto"), "data": proxima.get("data_prevista")} if isinstance(proxima, dict) else None
        ),
        "status": detalhe.get("status") or "no_rumo",
        "percentual": detalhe.get("percentual"),
        "feitas": detalhe.get("etapas_feitas"),
        "total": detalhe.get("total_etapas"),
        "hoje_fracao": round(posicao / 100, 4) if isinstance(posicao, (int, float)) else None,
        # US-F11 (so existe quando `detalhe` vem de uma viagem - generico
        # nunca tem esses campos, o card so mostra a secao se vier preenchida)
        "marcos_planejamento": detalhe.get("marcos_planejamento"),
        "aviso_regra_pratica": detalhe.get("aviso_regra_pratica"),
    }


def card_projeto(conn, projeto_id: int, hoje: date | None = None, actions_extra=None) -> dict | None:
    projeto = db.get_projeto(conn, projeto_id)
    if not projeto:
        return None
    detalhe = vida.projeto_detalhado(projeto, db.list_etapas_projeto(conn, projeto_id), hoje or date.today())
    aba, rotulo = ABA_POR_ENTIDADE["projeto"]
    actions = list(actions_extra or []) + [acao_abrir_aba(aba, rotulo, "projeto", projeto_id)]
    return novo_card("projeto_viagem", projeto_para_card(detalhe), actions)


def card_viagem(conn, viagem_id: int, hoje: date | None = None, actions_extra=None) -> dict | None:
    row = conn.execute("SELECT * FROM viagens WHERE id = ?", (viagem_id,)).fetchone()
    if not row:
        return None
    viagem = dict(row)
    detalhe = vida.viagem_como_projeto_detalhada(viagem, db.list_itens_viagem(conn, viagem_id), hoje or date.today())
    data = projeto_para_card(detalhe, "viagem", f"Viagem pra {viagem['destino']}", viagem_id)
    if not data["etapas"]:
        # viagem sem checklist de mala ainda: o marco e a ida em si
        data["proximo_marco"] = {"titulo": "Ida", "data": viagem["data_ida"]}
    aba, rotulo = ABA_POR_ENTIDADE["viagem"]
    actions = list(actions_extra or []) + [acao_abrir_aba(aba, rotulo, "viagem", viagem_id)]
    return novo_card("projeto_viagem", data, actions)


def card_agenda(conn, uid: str, lembrar_min_antes=None, actions_extra=None) -> dict | None:
    row = conn.execute("SELECT * FROM eventos_criados WHERE uid = ?", (uid,)).fetchone() if uid else None
    if not row:
        return None
    lembrar = lembrar_min_antes if isinstance(lembrar_min_antes, int) and not isinstance(lembrar_min_antes, bool) else None
    data = {
        "titulo": row["titulo"],
        "inicio": str(row["inicio"])[:16],
        "fim": str(row["fim"])[:16] if row["fim"] else None,
        "lembrar_min_antes": lembrar,
        "uid": row["uid"],
        "calendario": "Painel",
        "confirmado": True,
    }
    aba, rotulo = ABA_POR_ENTIDADE["evento"]
    actions = list(actions_extra or []) + [acao_abrir_aba(aba, rotulo)]
    return novo_card("agenda", data, actions)


def _dias_periodo(dias) -> int:
    return dias if isinstance(dias, int) and not isinstance(dias, bool) and 1 <= dias <= 90 else 7


def card_saude_treino(conn, dias=7, registrado: bool = False, hoje: date | None = None, actions_extra=None) -> dict:
    """Sessoes da tabela `treinos` (registro do proprio painel - o Apple Saude
    so manda passos/sono/distancia via Atalho, nao treino)."""
    hoje = hoje or date.today()
    dias = _dias_periodo(dias)
    desde = (hoje - timedelta(days=dias - 1)).isoformat()
    rows = conn.execute(
        "SELECT * FROM treinos WHERE data BETWEEN ? AND ? ORDER BY data DESC, id DESC",
        (desde, hoje.isoformat()),
    ).fetchall()
    sessoes = [
        {
            "atividade": (r["grupo"] or "Treino").strip().capitalize() or "Treino",
            "fonte": "Painel",
            "minutos": int(r["duracao_min"] or 0),
            "data": r["data"],
        }
        for r in rows
    ]
    periodo = "hoje" if dias == 1 else f"últimos {dias} dias"
    aba, rotulo = ABA_POR_ENTIDADE["treino"]
    actions = list(actions_extra or []) + [acao_abrir_aba(aba, rotulo)]
    # aditivo (cartoes vivos): a semana seg..dom com os dias treinados - os aneis do card
    segunda = hoje - timedelta(days=hoje.weekday())
    feitos = {
        r["data"] for r in conn.execute(
            "SELECT DISTINCT data FROM treinos WHERE data BETWEEN ? AND ?",
            (segunda.isoformat(), (segunda + timedelta(days=6)).isoformat()),
        ).fetchall()
    }
    semana = [
        {"data": (segunda + timedelta(days=i)).isoformat(), "feito": (segunda + timedelta(days=i)).isoformat() in feitos,
         "hoje": segunda + timedelta(days=i) == hoje}
        for i in range(7)
    ]
    meta = db.obter_configuracao(conn, "treino_meta_semana")
    return novo_card(
        "saude_treino",
        {"periodo": periodo, "sessoes": sessoes, "registrado": bool(registrado), "semana": semana,
         "meta_semana": int(meta) if meta and meta.isdigit() else None},
        actions,
    )


def card_saude_dia(conn, dia: date | None = None, registrado: str | None = None, actions_extra=None) -> dict:
    """Card `saude_dia` (aditivo, US-E7): o dia de saude num olhar - copos de
    agua (contador do painel), passos/sono (Apple Saude via Atalho, quando
    chegou) e minutos de treino registrados."""
    dia = dia or date.today()
    iso = dia.isoformat()
    saude = db.get_saude_dia(conn, iso) or {}
    treino = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(duracao_min), 0) AS m FROM treinos WHERE data = ?", (iso,)
    ).fetchone()
    data = {
        "data": iso,
        "agua_copos": db.contar_hidratacao_dia(conn, iso),
        "passos": saude.get("passos"),
        "sono_horas": saude.get("sono_horas"),
        "treino_min": int(treino["m"]) if treino and treino["n"] else None,
        "registrado": registrado,
    }
    return novo_card("saude_dia", data, list(actions_extra or []))


def card_sugestao(titulo, inicio, duracao_min, porque=None) -> dict | None:
    if not isinstance(inicio, str) or len(inicio) < 16:
        return None
    data = {
        "titulo": _titulo_curto(titulo, 80) or "Horário livre",
        "inicio": inicio[:16],
        "duracao_min": duracao_min if isinstance(duracao_min, int) and duracao_min > 0 else None,
        "porque": porque or None,
    }
    return novo_card("sugestao", data, [])



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
        elif t == "projeto_viagem" and d.get("origem") == "viagem":
            contagem[("Viagens", "viagem")] = contagem.get(("Viagens", "viagem"), 0) + 1
        elif t in ("agenda", "habito", "projeto_viagem", "saude_treino", "sugestao", "saude_dia"):
            modulo = {
                "agenda": "Agenda",
                "habito": "Hábitos",
                "projeto_viagem": "Projetos",
                "saude_treino": "Saúde",
                "sugestao": "Agenda",
                "saude_dia": "Saúde",
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
        "saude_dia": ("registro de saúde", "registros de saúde"),
        "viagem": ("viagem registrada", "viagens registradas"),
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


# ---- Fase 7 (N1, ligado na C1): assinatura / compra parcelada --------------
# Dado no formato de docs/contrato-assinaturas.md (N1). Alem dele, cada card
# leva os nomes que o renderizador ja escrito em static/js/cards-tipos.js (V1)
# le - `cartao`/`em_dias` (assinatura), `restantes`/`termina_em` (parcela),
# `total_mes`/`n_assinaturas`/`n_parcelas`/`proxima_cobranca` (resumo) - pra
# tela funcionar sem mexer no JS. Anotado pra C2 escolher um nome so.


def assinatura_para_card(a: dict, hoje: date, *, consulta: bool = False, actions: list | None = None) -> dict:
    proxima = fr.proxima_cobranca_assinatura(a, hoje)
    data = {
        "id": a["id"],
        "nome": a["nome"],
        "valor": a["valor"],
        "dia_cobranca": a["dia_cobranca"],
        "cartao_ou_forma": a.get("cartao_ou_forma"),
        "categoria": a.get("categoria"),
        "ativa": bool(a.get("ativa")),
        "inicio": a.get("inicio"),
        "cancelada_em": a.get("cancelada_em"),
        "proxima_cobranca": proxima.isoformat() if proxima else None,
        # nomes do renderizador V1
        "cartao": a.get("cartao_ou_forma"),
        "em_dias": (proxima - hoje).days if proxima else None,
    }
    if consulta:
        data["consulta"] = True
    return novo_card("assinatura", data, actions)


def compra_parcelada_para_card(c: dict, hoje: date, *, consulta: bool = False, actions: list | None = None) -> dict:
    info = fr.parcela_info(c, hoje)
    try:
        termina_em = calculos.data_ultima_parcela(c["primeira_parcela"], c["n_parcelas"]).isoformat()
    except (ValueError, TypeError, KeyError):
        termina_em = None
    data = {
        "id": c["id"],
        "descricao": c["descricao"],
        "valor_total": c["valor_total"],
        "n_parcelas": c["n_parcelas"],
        "valor_parcela": c["valor_parcela"],
        "cartao": c.get("cartao"),
        "primeira_parcela": c["primeira_parcela"],
        "categoria": c.get("categoria"),
        "parcela_atual": info["parcela_atual_calculada"],
        "parcelas_restantes": info["parcelas_restantes"],
        "mes_termino": info["mes_termino"],
        "quitada": info["quitada"],
        # nomes do renderizador V1
        "restantes": info["parcelas_restantes"],
        "termina_em": termina_em,
    }
    if consulta:
        data["consulta"] = True
    return novo_card("compra_parcelada", data, actions)


def resumo_recorrente_para_card(resumo: dict) -> dict:
    data = dict(resumo)
    proximas = data.get("proximas_cobrancas") or []
    primeira = proximas[0] if proximas and isinstance(proximas[0], dict) else None
    data.update({
        "consulta": True,
        # nomes do renderizador V1
        "total_mes": data.get("total_mensal"),
        "n_assinaturas": data.get("n_assinaturas_ativas"),
        "n_parcelas": data.get("n_compras_em_andamento"),
        "proxima_cobranca": {"nome": primeira.get("nome"), "data": primeira.get("data")} if primeira else None,
    })
    return novo_card("resumo_financeiro_recorrente", data, [])


def card_assinatura(conn, id_: int, hoje: date | None = None, actions_extra=None) -> dict | None:
    a = fr.obter_assinatura(conn, id_)
    if not a:
        return None
    return assinatura_para_card(a, hoje or date.today(), actions=_com_abrir(actions_extra, "assinatura", id_))


def card_compra_parcelada(conn, id_: int, hoje: date | None = None, actions_extra=None) -> dict | None:
    c = fr.obter_compra_parcelada(conn, id_)
    if not c:
        return None
    return compra_parcelada_para_card(c, hoje or date.today(),
                                      actions=_com_abrir(actions_extra, "compra_parcelada", id_))


def card_resumo_financeiro_recorrente(conn, hoje: date | None = None) -> dict:
    return resumo_recorrente_para_card(fr.resumo_financeiro_recorrente(conn, hoje or date.today()))


def card_rota(ef: dict) -> dict | None:
    """Trajeto calculado pelo estimar_trajeto (nao vem do banco). So aceita link
    do proprio Google Maps - o front tambem confere antes de abrir."""
    url = ef.get("url")
    paradas = [p for p in (ef.get("paradas") or []) if isinstance(p, dict)]
    if not isinstance(url, str) or not url.startswith("https://www.google.com/maps/") or len(paradas) < 2:
        return None
    return novo_card(
        "rota",
        {
            "paradas": paradas,
            "partir_de_onde_estou": bool(ef.get("partir_de_onde_estou")),
            "distancia_km": ef.get("distancia_km"),
            "duracao_min": ef.get("duracao_min"),
            "traco": ef.get("traco") if isinstance(ef.get("traco"), dict) else None,
        },
        [{"tipo": "abrir_link", "rotulo": "Abrir no Google Maps", "url": url}],
    )


def card_refeicao(conn, id_: int, ef: dict, actions_extra=None) -> dict | None:
    """Foto do prato (refeicoes.py): itens com gramas/macros estimados, total da refeicao, o
    dia ate agora e a meta. Valores sao estimativa por foto - o front mostra com "~"."""
    import refeicoes

    data = refeicoes.dados_card(conn, id_)
    if not data:
        return None
    if ef.get("dica"):
        data["dica"] = str(ef["dica"])[:200]
    if isinstance(ef.get("confianca"), (int, float)):
        data["confianca"] = round(float(ef["confianca"]), 2)
    return novo_card("refeicao", data, list(actions_extra or []))


# ---- cartoes vivos (2026-10-09) ----------------------------------------------

_NOME_CAMPO = {
    "title": "título", "hora": "hora", "due_date": "dia", "due_at": "prazo", "completed_at": "status",
    "titulo": "título", "data": "data", "recorrente": "repete todo ano", "despertar": "desperta você",
    "origem": "origem", "destino": "destino", "horas": "tempo de voo", "aeronave": "aeronave",
    "funcao": "função", "observacao": "observação", "category": "categoria", "description": "descrição",
    "amount": "valor", "local": "lugar", "situacao": "situação",
}


def _valor_legivel(campo: str, valor):
    if campo == "completed_at":
        return "concluída" if valor else "pendente"
    if valor is None or valor == "":
        return "—"
    if campo == "amount" and isinstance(valor, (int, float)):
        return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if campo in ("due_date", "data") and isinstance(valor, str):
        try:
            d = date.fromisoformat(valor[:10])
            return f"{DIAS_SEMANA_CURTOS[d.weekday()]}, {d:%d/%m}"
        except ValueError:
            return valor
    if campo == "horas":
        minutos = int(round(float(valor) * 60))
        return f"{minutos // 60}:{minutos % 60:02d}"
    if campo in ("recorrente", "despertar"):
        return "sim" if valor else "não"
    return str(valor)


def card_edicao(efeitos: list[dict], actions_extra=None) -> dict | None:
    itens = []
    for ef in efeitos:
        antes, depois = ef.get("antes") or {}, ef.get("depois") or {}
        mudancas = [
            {"campo": _NOME_CAMPO.get(c, c), "de": _valor_legivel(c, antes.get(c)), "para": _valor_legivel(c, depois.get(c))}
            for c in depois
        ]
        if mudancas:
            itens.append({"rotulo": ef.get("rotulo") or "Registro", "titulo": _titulo_curto(ef.get("titulo"), 70),
                          "mudancas": mudancas})
    if not itens:
        return None
    return novo_card("edicao", {"itens": itens}, list(actions_extra or []))


JANELA_PROJECAO_DIAS = 60
LIMITE_PROJECAO_DIAS = 5 * 365


def projecao_horas(conn, hoje: date | None = None) -> dict | None:
    """Quando ele chega na meta de horas (4a leva): ritmo dos ultimos 60 dias (h/semana) e o
    cenario "1 voo a mais por semana" (h por voo da mesma janela). Conta pura do historico -
    sem voo nos 60 dias ou meta ja batida = None. Data acima de 5 anos vira None (o front fala)."""
    import math

    hoje = hoje or date.today()
    rows = conn.execute(
        "SELECT data, horas FROM voos WHERE horas IS NOT NULL AND data <= ? AND COALESCE(tipo, '') != 'simulador'",
        (hoje.isoformat(),),
    ).fetchall()
    meta_cfg = db.obter_configuracao(conn, "aviacao_meta_horas")
    meta = int(meta_cfg) if meta_cfg and meta_cfg.isdigit() else 150
    falta = meta - sum(float(r["horas"]) for r in rows)
    inicio = (hoje - timedelta(days=JANELA_PROJECAO_DIAS)).isoformat()
    recentes = [float(r["horas"]) for r in rows if r["data"] > inicio and float(r["horas"]) > 0]
    if falta <= 0 or not recentes:
        return None
    semanas = JANELA_PROJECAO_DIAS / 7
    ritmo = sum(recentes) / semanas
    por_voo = sum(recentes) / len(recentes)

    def quando(h_semana: float) -> str | None:
        dias = math.ceil(falta / h_semana * 7)
        return (hoje + timedelta(days=dias)).isoformat() if dias <= LIMITE_PROJECAO_DIAS else None

    return {
        "ritmo_h_semana": round(ritmo, 1),
        "voos_semana": round(len(recentes) / semanas, 1),
        "horas_por_voo": round(por_voo, 1),
        "falta_h": round(falta, 1),
        "meta_horas": meta,
        "data_meta": quando(ritmo),
        "data_meta_mais_um": quando(ritmo + por_voo),
        "janela_dias": JANELA_PROJECAO_DIAS,
    }


def card_voo_resumo(conn, hoje: date | None = None) -> dict | None:
    hoje = hoje or date.today()
    rows = conn.execute(
        "SELECT data, origem, destino, horas, aeronave, funcao, tipo FROM voos "
        "WHERE horas IS NOT NULL AND data <= ? ORDER BY data, id",
        (hoje.isoformat(),),
    ).fetchall()
    reais = [r for r in rows if (r["tipo"] or "") != "simulador"]
    if not reais:
        return None
    total = 0
    por_funcao: dict = {}
    por_aeronave: dict = {}
    primeiro_solo = None
    for r in reais:
        minutos = int(round(float(r["horas"]) * 60))
        if primeiro_solo is None and "solo" in (r["funcao"] or "").lower():
            primeiro_solo = {"minutos": total, "data": r["data"]}
        total += minutos
        if r["funcao"]:
            por_funcao[r["funcao"]] = por_funcao.get(r["funcao"], 0) + minutos
        if r["aeronave"]:
            por_aeronave[r["aeronave"]] = por_aeronave.get(r["aeronave"], 0) + minutos
    ultimo = reais[-1]
    meta = db.obter_configuracao(conn, "aviacao_meta_horas")
    return novo_card(
        "voo_resumo",
        {
            "total_min": total,
            "voos": len(reais),
            "por_funcao": [{"nome": k, "min": v} for k, v in sorted(por_funcao.items(), key=lambda kv: -kv[1])],
            "por_aeronave": [{"nome": k, "min": v} for k, v in sorted(por_aeronave.items(), key=lambda kv: -kv[1])],
            "primeiro_solo": primeiro_solo,
            "ultimo": {"data": ultimo["data"], "aeronave": ultimo["aeronave"], "origem": ultimo["origem"],
                       "destino": ultimo["destino"]},
            "dias_sem_voar": (hoje - date.fromisoformat(ultimo["data"])).days,
            "simulador_min": sum(int(round(float(r["horas"]) * 60)) for r in rows if (r["tipo"] or "") == "simulador"),
            "meta_horas": int(meta) if meta and meta.isdigit() else 150,
            "meta_definida": bool(meta and meta.isdigit()),
            "projecao": projecao_horas(conn, hoje),
        },
        [acao_abrir_aba("aviacao", "Abrir Aviação")],
    )


def card_voo_agendado(conn, ef: dict, actions_extra: list | None = None, hoje: date | None = None) -> dict | None:
    """Voo marcado pelo chat (2026-10-14, docs/CARDS.md "Linguagem visual"): cartao de embarque
    com as pernas (NM de rota_voo), a hora de chegar (antecedencia das "Rotinas fixas"), a de
    sair de casa (quando o Maps calculou no executor) e as horas do curso ate a meta."""
    import rota_voo
    import vida_assistente

    id_ = ef.get("id")
    if not isinstance(id_, int):
        return None
    v = conn.execute("SELECT id, data, origem, destino, hora, escalas FROM voos WHERE id = ?", (id_,)).fetchone()
    if not v:
        return None
    rota = rota_voo.montar(v["origem"], v["escalas"], v["destino"], v["hora"])
    antes = vida_assistente.voo_briefing_min(conn)
    saida = ef.get("saida") if isinstance(ef.get("saida"), dict) else {}
    hoje = hoje or date.today()
    feitos = conn.execute(
        "SELECT horas FROM voos WHERE horas IS NOT NULL AND data <= ? AND COALESCE(tipo, '') != 'simulador'",
        (hoje.isoformat(),),
    ).fetchall()
    meta = db.obter_configuracao(conn, "aviacao_meta_horas")
    duracao = None
    if rota["em_voo_min"] is not None:
        duracao = rota["em_voo_min"] + rota_voo.MIN_POR_ESCALA * max(0, len(rota["paradas"]) - 2)
    return novo_card(
        "voo_agendado",
        {
            "id": id_,
            "data": v["data"],
            "hora": v["hora"],
            "paradas": rota["paradas"],
            "local": rota["local"],
            "pernas": rota["pernas"],
            "total_nm": rota["total_nm"],
            "duracao_min": duracao,
            "pouso": rota["pouso"],
            "antecedencia_min": antes,
            "chegar": rota_voo.menos_minutos(v["hora"], antes),
            "sair_casa": saida.get("sair"),
            "trajeto_min": saida.get("trajeto_min"),
            "horas_min": int(round(sum(float(r["horas"]) for r in feitos) * 60)),
            "meta_horas": int(meta) if meta and meta.isdigit() else 150,
            "projecao": projecao_horas(conn, hoje),
        },
        [*(actions_extra or []), acao_abrir_aba("aviacao", "Abrir Aviação")],
    )


HOBBS_EXTRA_MIN = 12  # motor ligado antes/depois do voo (taxi, cheque) - horas do diario sao de motor


def card_voo_horas(conn, voo_id: int, hoje: date | None = None) -> dict | None:
    """"Pousou? Quanto deu?" (2026-10-14, 3a leva): chips perto da estimativa da rota e a barra
    das horas do curso ate a meta (sem contar este voo - o front soma quando ele toca)."""
    import rota_voo

    v = conn.execute(
        "SELECT id, data, hora, origem, destino, escalas, horas FROM voos WHERE id = ?", (voo_id,)
    ).fetchone()
    if not v:
        return None
    hoje = hoje or date.today()
    rota = rota_voo.montar(v["origem"], v["escalas"], v["destino"], v["hora"])
    estimativa = None
    if rota["em_voo_min"] is not None:
        minutos = rota["em_voo_min"] + rota_voo.MIN_POR_ESCALA * max(0, len(rota["paradas"]) - 2) + HOBBS_EXTRA_MIN
        estimativa = max(0.3, round(minutos / 60, 1))
    if estimativa:
        sugestoes = sorted({round(max(0.3, estimativa - 0.2), 1), estimativa, round(estimativa + 0.2, 1)})
    else:
        sugestoes = [1.0, 1.2, 1.5]
    outros = conn.execute(
        "SELECT horas FROM voos WHERE horas IS NOT NULL AND id != ? AND data <= ? AND COALESCE(tipo, '') != 'simulador'",
        (voo_id, hoje.isoformat()),
    ).fetchall()
    meta = db.obter_configuracao(conn, "aviacao_meta_horas")
    return novo_card(
        "voo_horas",
        {
            "id": v["id"],
            "data": v["data"],
            "hora": v["hora"],
            "rota": " → ".join(p["icao"] for p in rota["paradas"]) if not rota["local"] else None,
            "icao": rota["paradas"][0]["icao"],
            "estimativa": estimativa,
            "sugestoes": sugestoes,
            "horas": float(v["horas"]) if v["horas"] is not None else None,
            "horas_min": int(round(sum(float(r["horas"]) for r in outros) * 60)),
            "meta_horas": int(meta) if meta and meta.isdigit() else 150,
            "projecao": projecao_horas(conn, hoje),
        },
        [acao_abrir_aba("aviacao", "Abrir Aviação")],
    )


FOLGA_SAIDA_MIN = 15  # sem Maps: mesma folga do aviso "hora de sair" (app.FOLGA_SEM_TRAJETO_MIN)
MOCHILA_VOO = ("CIV e CMA", *vida.CHECKLIST_PRE_VOO)


def mochila_feita(conn, voo_id: int) -> list[bool]:
    import json

    try:
        marcas = json.loads(db.obter_configuracao(conn, f"mochila_voo_{voo_id}") or "[]")
    except ValueError:
        marcas = []
    return [bool(marcas[i]) if i < len(marcas) else False for i in range(len(MOCHILA_VOO))]


def card_vespera_voo(conn, voo_id: int, saida: dict | None = None) -> dict | None:
    """Vespera do voo (4a leva): acorda -> sai -> chega -> decola, a faixa do TAF na hora do
    voo (o front pede sozinho) e a mochila que marca. `saida` = Maps (app._saida_pro_voo) ou
    None (folga de 15 min)."""
    import rota_voo
    import vida_assistente

    v = conn.execute(
        "SELECT id, data, hora, origem, destino, escalas FROM voos WHERE id = ? AND hora IS NOT NULL", (voo_id,)
    ).fetchone()
    if not v:
        return None
    rota = rota_voo.montar(v["origem"], v["escalas"], v["destino"], v["hora"])
    antes = vida_assistente.voo_briefing_min(conn)
    arrumar = vida_assistente.se_arrumar_min(conn)
    chegar = rota_voo.menos_minutos(v["hora"], antes)
    sair = (saida or {}).get("sair") or rota_voo.menos_minutos(chegar, FOLGA_SAIDA_MIN)
    feitos = mochila_feita(conn, voo_id)
    return novo_card(
        "vespera_voo",
        {
            "id": v["id"],
            "data": v["data"],
            "hora": v["hora"],
            "rota": None if rota["local"] else " → ".join(p["icao"] for p in rota["paradas"]),
            "icao": rota["paradas"][0]["icao"],
            "acordar": rota_voo.menos_minutos(sair, arrumar),
            "sair": sair,
            "chegar": chegar,
            "pouso": rota["pouso"],
            "trajeto_min": (saida or {}).get("trajeto_min"),
            "arrumar_min": arrumar,
            "antecedencia_min": antes,
            "mochila": [{"texto": t, "feito": f} for t, f in zip(MOCHILA_VOO, feitos)],
        },
        [acao_abrir_aba("aviacao", "Abrir Aviação")],
    )


MARCOS_DOCUMENTO = (60, 30, 7)


def marco_documento(dias: int) -> int | None:
    """60/30/7: o menor marco que ja chegou (20 dias -> 30). Vencido ou longe = None."""
    if dias < 0:
        return None
    chegados = [m for m in MARCOS_DOCUMENTO if dias <= m]
    return min(chegados) if chegados else None


def card_documento_validade(lembrete: dict, vence: date, hoje: date) -> dict | None:
    dias = (vence - hoje).days
    marco = marco_documento(dias)
    if marco is None:
        return None
    return novo_card(
        "documento_validade",
        {
            "id": lembrete["id"],
            "titulo": _titulo_curto(lembrete["titulo"], 70),
            "vence": vence.isoformat(),
            "dias": dias,
            "marco": marco,
            "recorrente": bool(lembrete.get("recorrente")),
        },
        [acao_abrir_aba("tarefas", "Abrir Tarefas")],
    )


def card_compras_previsao(itens: list[dict]) -> dict | None:
    itens = [i for i in itens if i.get("item")][:4]
    if not itens:
        return None
    return novo_card("compras_previsao", {"itens": itens})


def card_assinatura_subiu(a: dict) -> dict | None:
    if not a.get("descricao") or not a.get("valor_novo"):
        return None
    return novo_card(
        "assinatura_subiu",
        {
            "descricao": _titulo_curto(a["descricao"], 50),
            "categoria": a.get("categoria"),
            "de": round(float(a["valor_anterior_medio"]), 2),
            "para": round(float(a["valor_novo"]), 2),
            "pct": round(float(a["aumento_pct"])),
        },
    )


def card_clima(ef: dict) -> dict | None:
    agora = ef.get("agora")
    if not isinstance(agora, dict):
        return None
    horas = [h for h in (ef.get("proximas_horas") or []) if isinstance(h, dict)][:8]
    return novo_card("clima", {"lugar": _titulo_curto(ef.get("lugar"), 40), "agora": {
        k: agora.get(k) for k in ("condicao", "chovendo_agora", "temperatura", "sensacao", "umidade_pct", "vento_kmh")
    }, "proximas_horas": horas})


def card_briefing_voo(ef: dict) -> dict | None:
    """METAR/TAF decodificados (briefing_voo.montar) - so os campos que o front desenha."""
    d = ef.get("dados")
    if not isinstance(d, dict) or not d.get("icao"):
        return None
    campos = ("icao", "nome", "substituto_de", "categoria", "observado", "idade_min", "vento", "visibilidade_m",
              "teto_ft", "nuvens", "temp", "orvalho", "qnh", "fenomenos", "taf", "metar_bruto", "taf_bruto",
              "windy_url", "voo", "aviso")
    data = {k: d.get(k) for k in campos}
    url = d.get("windy_url") if str(d.get("windy_url") or "").startswith("https://www.windy.com/") else None
    acoes = [{"tipo": "abrir_link", "rotulo": "Abrir no Windy", "url": url}] if url else []
    return novo_card("briefing_voo", data, acoes)


def card_quiz_aviacao(ef: dict) -> dict | None:
    """Pergunta da banca (estudo_quiz.dados_card) - sem a certa enquanto nao respondeu."""
    d = ef.get("dados")
    if not isinstance(d, dict) or not isinstance(d.get("id"), int):
        return None
    alts = d.get("alternativas")
    if not isinstance(alts, list) or len(alts) != 4:
        return None
    data = {k: d.get(k) for k in ("id", "tema", "enunciado", "alternativas", "caixa", "caixa_max", "revisao")}
    r = d.get("resposta")
    if isinstance(r, dict):
        data["resposta"] = {k: r.get(k) for k in ("escolhida", "correta", "acertou", "explicacao", "caixa",
                                                  "proxima_revisao")}
    return novo_card("quiz_aviacao", data)


def card_gastos_resumo(ef: dict) -> dict | None:
    d = ef.get("dados")
    if not isinstance(d, dict):
        return None
    cats = [c for c in (d.get("por_categoria") or []) if isinstance(c, dict)]
    return novo_card(
        "gastos_resumo",
        {
            "periodo": d.get("periodo"),
            "total": d.get("total"),
            "quantidade": d.get("quantidade"),
            "por_categoria": cats[:8],
            "maiores": (d.get("maiores") or [])[:3],
            "categoria_filtrada": d.get("categoria_filtrada"),
        },
        [acao_abrir_aba("gastos", "Abrir Finanças")],
    )


def card_dia(ef: dict) -> dict | None:
    d = ef.get("dados")
    if not isinstance(d, dict):
        return None
    itens = [
        {k: c.get(k) for k in ("hora", "ate", "titulo", "origem", "concluida", "dia_inteiro")}
        for c in (d.get("compromissos") or []) if isinstance(c, dict)
    ]
    return novo_card("dia", {"dia": d.get("dia"), "compromissos": itens,
                             "tarefas_sem_hora": (d.get("tarefas_sem_hora") or [])[:8]})


def card_viagem_janelas(ef: dict) -> dict | None:
    plano = ef.get("plano")
    if not isinstance(plano, dict) or not isinstance(plano.get("cenarios"), dict):
        return None
    return novo_card("viagem_janelas", {
        "destino": ef.get("destino"), "mes": plano.get("mes"), "dia_definido": plano.get("dia_definido"),
        "internacional": plano.get("internacional"), "cenarios": plano["cenarios"], "fontes": plano.get("fontes"),
    })


_SEM_MODELO_SQL = "NOT (recorrencia IS NOT NULL AND due_date IS NULL)"


def card_tarefas_lista(conn, ef: dict, hoje: date | None = None) -> dict | None:
    """Cartao vivo das tarefas (consultar_tarefas): anel de feitas/total no periodo,
    atrasadas em destaque e a lista com caixinha pra concluir ali mesmo (mesmo
    handler de data-tarefa-id do card tarefas_criadas)."""
    hoje = hoje or date.today()
    try:
        de = date.fromisoformat(str(ef.get("de")))
        ate = date.fromisoformat(str(ef.get("ate")))
    except ValueError:
        return None
    de_s, ate_s, hoje_s = de.isoformat(), ate.isoformat(), hoje.isoformat()
    so_concluidas = ef.get("status") == "concluidas"
    linhas = conn.execute(
        "SELECT id, title, hora, due_date, completed_at FROM tasks "
        f"WHERE {_SEM_MODELO_SQL} AND due_date BETWEEN ? AND ? "
        "ORDER BY due_date, hora IS NULL, hora, id",
        (de_s, ate_s),
    ).fetchall()
    feitas = [r for r in linhas if r["completed_at"]]
    pendentes = [r for r in linhas if not r["completed_at"]]
    atrasadas = []
    if de <= hoje <= ate and not so_concluidas:
        atrasadas = conn.execute(
            "SELECT id, title, hora, due_date, completed_at FROM tasks "
            f"WHERE {_SEM_MODELO_SQL} AND completed_at IS NULL AND due_date < ? ORDER BY due_date, id LIMIT 6",
            (hoje_s,),
        ).fetchall()

    def item(r, atrasada=False):
        return {"id": r["id"], "titulo": r["title"], "hora": r["hora"], "data": r["due_date"],
                "concluida": bool(r["completed_at"]), "atrasada": atrasada}

    mostrar = feitas if so_concluidas else pendentes + feitas
    return novo_card(
        "tarefas_lista",
        {
            "de": de_s, "ate": ate_s, "hoje": hoje_s, "so_concluidas": so_concluidas,
            "total": len(linhas), "feitas": len(feitas),
            "itens": [item(r) for r in mostrar[:14]],
            "atrasadas": [item(r, True) for r in atrasadas],
            "mais": max(0, len(mostrar) - 14),
        },
        [acao_abrir_aba("tarefas", "Abrir Tarefas")],
    )


def card_agua(conn, actions_extra=None, dia: date | None = None) -> dict:
    iso = (dia or date.today()).isoformat()
    meta = db.obter_configuracao(conn, "agua_meta_copos")
    return novo_card("agua", {
        "data": iso, "copos": db.contar_hidratacao_dia(conn, iso),
        "meta": int(meta) if meta and meta.isdigit() else 8,
    }, list(actions_extra or []))


def _com_abrir(actions_extra, entidade: str, id_: int) -> list:
    aba, rotulo = ABA_POR_ENTIDADE[entidade]
    return list(actions_extra or []) + [acao_abrir_aba(aba, rotulo, entidade, id_)]


def _card_de_efeito_modulo(conn, ef: dict, criar_token) -> dict | None:
    """Efeitos dos modulos da Fase 6 (US-E7). `criar_token` None = consulta
    (sem Desfazer). O token guarda so o que o executor declarou (ids exatos)."""
    entidade = ef.get("entidade")
    id_ = ef.get("id")
    desfazer = _acoes_desfazer(criar_token, [ef])
    if entidade == "habito" and isinstance(id_, int):
        return card_habito(conn, id_, ativos_antes=ef.get("ativos_antes"), ativos_depois=ef.get("ativos_depois"),
                           actions_extra=desfazer)
    if entidade == "habito_marcacao" and isinstance(id_, int):
        contexto = "Marcado como feito hoje." if ef.get("feito") else "Desmarcado hoje."
        return card_habito(conn, id_, contexto=contexto, actions_extra=desfazer)
    if entidade == "projeto" and isinstance(id_, int):
        return card_projeto(conn, id_, actions_extra=desfazer)
    if entidade in ("projeto_etapa", "etapa_concluida") and isinstance(ef.get("projeto_id"), int):
        return card_projeto(conn, ef["projeto_id"], actions_extra=desfazer)
    if entidade == "viagem" and isinstance(id_, int):
        return card_viagem(conn, id_, actions_extra=desfazer)
    if entidade == "evento" and isinstance(ef.get("uid"), str):
        return card_agenda(conn, ef["uid"], ef.get("lembrar_min_antes"), desfazer)
    if entidade == "treino":
        return card_saude_treino(conn, ef.get("dias") or 7, registrado=not ef.get("consulta"), actions_extra=desfazer)
    if entidade == "treinos":
        return card_saude_treino(conn, ef.get("dias") or 7)
    if entidade == "hidratacao":
        return card_agua(conn, actions_extra=desfazer)
    if entidade == "saude_dia":
        return card_saude_dia(conn)
    if entidade == "sugestao":
        return card_sugestao(ef.get("titulo"), ef.get("inicio"), ef.get("duracao_min"), ef.get("porque"))
    if entidade == "assinatura" and isinstance(id_, int):
        return card_assinatura(conn, id_, actions_extra=desfazer)
    if entidade == "compra_parcelada" and isinstance(id_, int):
        return card_compra_parcelada(conn, id_, actions_extra=desfazer)
    if entidade == "resumo_financeiro_recorrente":
        return card_resumo_financeiro_recorrente(conn)
    if entidade == "rota":
        return card_rota(ef)
    if entidade == "refeicao" and isinstance(id_, int):
        return card_refeicao(conn, id_, ef, desfazer)
    if entidade == "voo_resumo":
        return card_voo_resumo(conn)
    if entidade == "voo_agendado":
        return card_voo_agendado(conn, ef, desfazer)
    if entidade == "clima":
        return card_clima(ef)
    if entidade == "gastos_resumo":
        return card_gastos_resumo(ef)
    if entidade == "dia":
        return card_dia(ef)
    if entidade == "viagem_janelas":
        return card_viagem_janelas(ef)
    if entidade == "tarefas_lista":
        return card_tarefas_lista(conn, ef)
    if entidade == "briefing_voo":
        return card_briefing_voo(ef)
    if entidade == "quiz_aviacao":
        return card_quiz_aviacao(ef)
    return None


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
    edicoes: list[dict] = []
    pos_edicoes = None
    vistos_consulta: set = set()
    # 2026-10-15 (lido no chat): "tomei 4 copos" virava 4 cards iguais (cada um ja com o total) -
    # vira UM card, com um Desfazer pros 4.
    aguas: list[dict] = []
    pos_agua = None
    # sugestao de horario e rascunho: se a mesma resposta ja gravou o horario de verdade (tarefa
    # criada/editada), o card da sugestao contradizia o que ficou ("15:00" x 9h45 marcado)
    gravou_horario = any(
        e.get("entidade") in ("edicao", "tarefa") and not e.get("consulta") for e in efeitos
    )
    for ef in efeitos:
        entidade = ef.get("entidade")
        id_ = ef.get("id")
        if entidade == "sugestao" and gravou_horario:
            continue
        if entidade == "hidratacao" and not ef.get("consulta"):
            if pos_agua is None:
                pos_agua = len(saida)
                saida.append(None)
            aguas.append(ef)
            continue
        if _e_conclusao(ef):
            card = card_tarefa_feita(conn, id_, _acoes_desfazer(criar_token, [ef]))
            if card:
                saida.append(card)
            continue
        if entidade in ("edicao", "tarefa_apagada") and isinstance(id_, int):
            if pos_edicoes is None:
                pos_edicoes = len(saida)
                saida.append(None)
            edicoes.append(ef)
            continue
        # o mesmo card de consulta (ex: voo_resumo depois de editar 2 voos) sai uma vez so
        if entidade in ("voo_resumo",):
            if entidade in vistos_consulta:
                continue
            vistos_consulta.add(entidade)
        if entidade == "tarefa" and isinstance(id_, int) and ef.get("estilo"):
            card = card_compromisso(conn, ef, _acoes_desfazer(criar_token, [ef]))
            if card:
                saida.append(card)
                continue
        if entidade == "tarefa" and isinstance(id_, int):
            if pos_tarefas is None:
                pos_tarefas = len(saida)
                saida.append(None)  # reserva a posicao
            tarefas_ids.append(id_)
            tarefas_itens.append(ef)
            continue
        card = None
        if ef.get("consulta"):
            # consulta nao cria nada - card sem Desfazer (so o link da aba)
            criar_token_ef = None
        else:
            criar_token_ef = criar_token
        if entidade in ("gasto", "renda") and isinstance(id_, int):
            card = card_transacao(
                conn, entidade, id_, ef.get("meio"), ef.get("saldo"), _acoes_desfazer(criar_token_ef, [ef])
            )
        elif entidade == "meta" and isinstance(id_, int):
            card = card_meta(conn, id_, _acoes_desfazer(criar_token_ef, [ef]))
        elif entidade == "lembrete" and isinstance(id_, int):
            card = card_lembrete(conn, id_, _acoes_desfazer(criar_token_ef, [ef]))
        else:
            card = _card_de_efeito_modulo(conn, ef, criar_token_ef)
        if card:
            if ef.get("consulta"):
                card["_consulta"] = True
                # aditivo (docs/CARDS.md): o front troca "Meta criada" por "Meta"
                card["data"]["consulta"] = True
            saida.append(card)
    if pos_tarefas is not None:
        card = card_tarefas_criadas(conn, tarefas_ids, _acoes_desfazer(criar_token, tarefas_itens))
        saida[pos_tarefas] = card
    if pos_edicoes is not None:
        saida[pos_edicoes] = card_edicao(edicoes, _acoes_desfazer(criar_token, edicoes))
    if pos_agua is not None:
        saida[pos_agua] = card_agua(conn, actions_extra=_acoes_desfazer(criar_token, aguas))
    saida = [c for c in saida if c]
    return saida


def montar_resposta(conn, efeitos: list[dict], resumo_texto: str, passos: list[dict], criar_token=None) -> dict:
    """Efeitos -> cards (+ resumo_final quando 2+ cards) -> envelope."""
    lista = cards_dos_efeitos(conn, efeitos, criar_token)
    # resumo_final so quando a resposta FEZ 2+ coisas (brain dump) - card de
    # consulta (US-E7, "me mostra o projeto e a meta") nao conta como feito.
    feitos = [c for c in lista if not c.get("_consulta")]
    if len(feitos) >= 2:
        resumo = card_resumo_final(feitos, passos)
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
        if c.get("type") == "edicao" and isinstance(c.get("data"), dict):
            for item in c["data"].get("itens") or []:
                for m in item.get("mudancas") or []:
                    if m.get("campo") == "valor":
                        m["de"] = m["para"] = "R$ •••"
        if c.get("type") == "presente" and isinstance(c.get("data"), dict):
            for ideia in c["data"].get("ideias") or []:
                if isinstance(ideia, dict):
                    ideia.pop("preco", None)
        campos = CAMPOS_SENSIVEIS.get(c.get("type"))
        if campos and isinstance(c.get("data"), dict):
            for campo in campos:
                c["data"].pop(campo, None)
            c["data"]["oculto"] = True
        if isinstance(c.get("actions"), list):
            c["actions"] = [
                a for a in c["actions"]
                if not (isinstance(a, dict) and a.get("tipo") in ACTIONS_BLOQUEADAS_VISITANTE)
            ]
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
