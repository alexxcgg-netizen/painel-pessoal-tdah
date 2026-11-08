"""Faixa P3 - montagem por codigo (sem IA) dos dois briefings proativos do
dia: o da manha (agenda, tarefas, contas proximas, habitos) e o da noite
(fechamento, o que passa pra amanha, pergunta de fechamento).

Reaproveita a coleta de dado que ja existe nas Fases 5/6 em vez de duplicar:
- notificacoes.mensagem_fechamento_noturno (Fase 6, US-C? fechamento ativo)
- app._eventos_de_hoje_com_seguranca / app._tarefas_pendentes_sem_horario_hoje
  (Fase 6, plano do dia / visao do dia)
- app._contas_pessoais_com_status (contas pessoais, ja calcula o proximo
  vencimento em aberto)
- app._buscar_contas_a_vencer_construtora (integracao HTTP read-only com o
  financeiro-construtora, v3.99.16 do outro lado - so devolve o que a API de
  la ja manda pronto)

`app` e importado de forma tardia (dentro de cada funcao que precisa dele),
nunca no topo do modulo: app.py e quem eventualmente vai carregar este
pacote via assistente/gatilhos (Etapa 0/X1), e um import no topo criaria
ciclo. Nos testes, os helpers de app sao trocados por
`unittest.mock.patch("app...")`.

IMPORTANTE (regra do financeiro-construtora, AGENTS.md de la): a proxima
conta a pagar da construtora entra aqui SO com nome e "quando" - nunca com
valor em R$. O valor mora so no financeiro-construtora."""

import re
from datetime import date, timedelta

import db
import notificacoes
import vida

CHAVE_HORARIO_MANHA = "assistente.p3.horario_manha"
CHAVE_HORARIO_NOITE = "assistente.p3.horario_noite"
CHAVE_ATIVO = "assistente.p3.ativo"
CHAVE_REESCREVER_IA = "assistente.p3.reescrever_ia"

HORARIO_MANHA_PADRAO = "07:30"
HORARIO_NOITE_PADRAO = "21:00"

# Ate quantos dias a frente uma conta pessoal entra no briefing da manha -
# igual ao aviso proativo (v3.99.16) usa 3 dias pra alertar; aqui e so
# informativo (nao manda push extra por conta), entao a janela pode ser um
# pouco maior sem virar ruido.
JANELA_CONTAS_DIAS = 7

OPCOES_FECHAMENTO = ["Otimo", "Bom", "Neutro", "Dificil", "Pessimo"]
_HUMOR_POR_OPCAO = {"otimo": 5, "bom": 4, "neutro": 3, "dificil": 2, "pessimo": 1}

_RE_HORARIO = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ---- horarios / flags (configuracoes) --------------------------------


def horario_valido(valor) -> bool:
    return isinstance(valor, str) and bool(_RE_HORARIO.match(valor))


def horario_manha(conn) -> str:
    return db.obter_configuracao(conn, CHAVE_HORARIO_MANHA) or HORARIO_MANHA_PADRAO


def horario_noite(conn) -> str:
    return db.obter_configuracao(conn, CHAVE_HORARIO_NOITE) or HORARIO_NOITE_PADRAO


def definir_horario_manha(conn, valor: str) -> None:
    db.definir_configuracao(conn, CHAVE_HORARIO_MANHA, valor)


def definir_horario_noite(conn, valor: str) -> None:
    db.definir_configuracao(conn, CHAVE_HORARIO_NOITE, valor)


def ativo(conn) -> bool:
    """Flag assistente.p3.ativo - padrao ligado, so desliga com '0' explicito
    (contrato comum das faixas P, docs/agentes/fase7-assistente.md)."""
    return db.obter_configuracao(conn, CHAVE_ATIVO) != "0"


def reescrever_ia_ativo(conn) -> bool:
    """Flag assistente.p3.reescrever_ia - opcional, padrao DESLIGADO."""
    return db.obter_configuracao(conn, CHAVE_REESCREVER_IA) == "1"


def humor_da_resposta(resposta) -> int | None:
    """Converte a opcao escolhida no fechamento noturno (ex.: 'Otimo') pro
    inteiro 1-5 que db.salvar_checkin ja usa em checkins.humor. None se a
    resposta nao bater com nenhuma opcao (ex.: 'adiar')."""
    if not isinstance(resposta, str) or not resposta.strip():
        return None
    return _HUMOR_POR_OPCAO.get(resposta.strip().lower())


# ---- formatacao pequena, sem calculo de dominio -----------------------


def _frase_vencimento(dias_ate: int) -> str:
    if dias_ate < 0:
        return f"venceu há {abs(dias_ate)} {'dia' if dias_ate == -1 else 'dias'}"
    if dias_ate == 0:
        return "vence hoje"
    if dias_ate == 1:
        return "vence amanhã"
    return f"vence em {dias_ate} dias"


def _hora_de(inicio) -> str:
    if not isinstance(inicio, str) or "T" not in inicio:
        return ""
    return inicio.split("T", 1)[1][:5]


# ---- coleta (reaproveitando o que ja existe) ---------------------------


def _agenda_do_dia(conn) -> list[dict]:
    """Reaproveita app._eventos_de_hoje_com_seguranca (Fase 6, visao do
    dia/plano do dia) - ja junta iCloud (se configurado, com seguranca
    contra falha de rede) e tarefas com horario marcado hoje, ordenado. So
    opera no dia real (date.today()) porque a funcao reaproveitada nao
    aceita data - na pratica sempre bate com `hoje`, ja que o gatilho roda
    no dia corrente. Testes trocam este helper por mock."""
    import app  # tardio: evita ciclo (app.py carrega assistente.gatilhos)

    eventos = app._eventos_de_hoje_com_seguranca(conn)
    return [
        {"titulo": e.get("titulo") or e.get("title") or "(sem titulo)", "inicio": e.get("inicio")}
        for e in eventos
    ]


def _tarefas_do_dia(conn) -> list[str]:
    """Reaproveita app._tarefas_pendentes_sem_horario_hoje (Fase 6, plano do
    dia) - tarefa com horario ja aparece na agenda (acima); aqui so entra o
    que ainda nao tem lugar marcado, sem listar a mesma tarefa duas vezes."""
    import app  # tardio

    return [r["title"] for r in app._tarefas_pendentes_sem_horario_hoje(conn)]


def _habitos_do_dia(conn, hoje: date) -> list[dict]:
    """Mesma regra de devido-hoje que _contagem_dia/visao-dia ja usam
    (vida.habito_devido_em + marcacoes da semana), so que aqui pega TODOS os
    habitos devidos (nao so os com horario, que ja aparecem na agenda)."""
    ini_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana = ini_semana + timedelta(days=6)
    hoje_iso = hoje.isoformat()
    resultado = []
    for h in db.list_habitos(conn):
        vezes_feitas_semana = len(
            db.marcacoes_habito_no_periodo(conn, h["id"], ini_semana.isoformat(), fim_semana.isoformat())
        )
        if not vida.habito_devido_em(h, hoje, vezes_feitas_semana):
            continue
        resultado.append({"nome": h["nome"], "concluido": db.habito_marcado(conn, hoje_iso, h["id"])})
    return resultado


def _contas_pessoais_proximas(conn, hoje: date) -> list[dict]:
    """Reaproveita app._contas_pessoais_com_status (ja calcula qual
    vencimento esta em aberto) - so filtra o que ainda nao foi pago e cai
    dentro da janela de 'proximos dias'."""
    import app  # tardio

    resultado = []
    for c in app._contas_pessoais_com_status(conn, hoje):
        if c["paga"] or c["dias_ate_vencer"] > JANELA_CONTAS_DIAS:
            continue
        resultado.append(
            {"nome": c["nome"], "valor": c.get("valor"), "quando": _frase_vencimento(c["dias_ate_vencer"])}
        )
    return resultado


def _proxima_conta_construtora() -> dict | None:
    """So nome e 'quando' - NUNCA valor (AGENTS.md do financeiro-construtora:
    numero de dinheiro real da empresa fica so la). Reaproveita
    app._buscar_contas_a_vencer_construtora, que ja cacheia e ja falha
    fechado (None) se a integracao nao estiver configurada ou a chamada
    falhar - este modulo nunca faz a chamada de rede diretamente."""
    import app  # tardio

    dados = app._buscar_contas_a_vencer_construtora(dias=30)
    if not dados or dados.get("status") != "ok":
        return None
    contas = dados.get("contas") or []
    if not contas:
        return None
    proxima = contas[0]
    nome = proxima.get("fornecedor") or proxima.get("descricao") or "fornecedor não informado"
    return {"nome": nome, "quando": _frase_vencimento(proxima["dias_ate_vencer"])}


def reescrever_se_configurado(conn, corpo: str, tipo: str) -> str:
    """Opcional (flag assistente.p3.reescrever_ia, desligada por padrao):
    Luna reescreve o texto via ia.core.chamar_ia. Qualquer problema (flag
    desligada, config ausente, falha de IA, teto estourado) devolve o corpo
    original sem quebrar o briefing - reescrita e cosmetica, nunca pode
    impedir o briefing de sair."""
    if not reescrever_ia_ativo(conn):
        return corpo
    try:
        import ia.core as ia_core
    except Exception:
        return corpo
    try:
        resposta = ia_core.chamar_ia(
            "reescrever_briefing",
            mensagens=[{"role": "user", "content": corpo}],
            sistema=(
                "Reescreva o texto a seguir em portugues do Brasil, mantendo todo o "
                "conteúdo e os fatos, tom direto e sem cobrança, frases curtas. "
                f"E o briefing da {tipo}. Devolva so o texto reescrito, sem comentario."
            ),
        )
    except Exception:
        return corpo
    if not resposta or not getattr(resposta, "ok", False):
        return corpo
    texto = (getattr(resposta, "texto", None) or "").strip()
    return texto or corpo


# ---- montagem -----------------------------------------------------------


def montar_manha(conn, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()

    import app  # tardio

    app.materializar_tarefas_recorrentes(conn, hoje)

    agenda = _agenda_do_dia(conn)
    tarefas = _tarefas_do_dia(conn)
    habitos = _habitos_do_dia(conn, hoje)
    contas_pessoais = _contas_pessoais_proximas(conn, hoje)
    conta_construtora = _proxima_conta_construtora()

    partes = []
    if agenda:
        itens = ", ".join(
            f"{_hora_de(a['inicio'])} {a['titulo']}".strip() if a.get("inicio") else a["titulo"]
            for a in agenda
        )
        plural = "" if len(agenda) == 1 else "s"
        partes.append(f"{len(agenda)} compromisso{plural} na agenda: {itens}.")
    else:
        partes.append("Sem compromisso marcado na agenda.")

    if tarefas:
        plural = "" if len(tarefas) == 1 else "s"
        partes.append(f"{len(tarefas)} tarefa{plural} pendente{plural}: {', '.join(tarefas)}.")
    else:
        partes.append("Nenhuma tarefa pendente.")

    if habitos:
        partes.append(f"Hábitos de hoje: {', '.join(h['nome'] for h in habitos)}.")

    contas_texto = []
    for c in contas_pessoais:
        valor_texto = f" (R$ {c['valor']:.2f})" if c.get("valor") else ""
        contas_texto.append(f"{c['nome']} {c['quando']}{valor_texto}")
    if conta_construtora:
        contas_texto.append(f"{conta_construtora['nome']} (construtora) {conta_construtora['quando']}")
    if contas_texto:
        partes.append(f"Contas nos próximos dias: {', '.join(contas_texto)}.")

    corpo = reescrever_se_configurado(conn, " ".join(partes), "manha")

    return {
        "tipo": "manha",
        "data": hoje.isoformat(),
        "titulo": "Bom dia",
        "corpo": corpo,
        "opcoes": None,
        "agenda": agenda,
        "tarefas": tarefas,
        "habitos": habitos,
        "contas": contas_pessoais,
        "conta_construtora": conta_construtora,
    }


def montar_noite(conn, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    hoje_iso = hoje.isoformat()

    concluidas = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE date(completed_at, '-3 hours') = ?", (hoje_iso,)  # UTC -> dia de Brasilia
    ).fetchone()["n"]
    pendentes = [
        r["title"]
        for r in conn.execute(
            "SELECT title FROM tasks WHERE completed_at IS NULL AND due_date = ? "
            "ORDER BY hora IS NULL, hora",
            (hoje_iso,),
        ).fetchall()
    ]

    # Reaproveita o texto pronto do fechamento ativo (Fase 6) - ja fala
    # concluidas/pendentes/gasto do dia numa frase so, sem refazer o calculo.
    resumo = notificacoes.mensagem_fechamento_noturno(conn, hoje)

    partes = [resumo]
    if pendentes:
        partes.append("O que ficou passa pra amanhã.")
    partes.append("Como foi o dia?")

    corpo = reescrever_se_configurado(conn, " ".join(partes), "noite")

    return {
        "tipo": "noite",
        "data": hoje_iso,
        "titulo": "Fechando o dia",
        "corpo": corpo,
        "opcoes": list(OPCOES_FECHAMENTO),
        "concluidas": concluidas,
        "pendentes": pendentes,
    }
