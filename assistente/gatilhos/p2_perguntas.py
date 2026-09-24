"""Fase 7, faixa P2 (Perguntas de acompanhamento) - gatilhos sem IA que
transformam um evento do dia a dia (conta vencendo, reuniao que terminou,
tarefa atrasada, lembrete sem resposta, espera de terceiro parada) numa
pergunta na Caixa do assistente, e que sabem atualizar o estado real quando
o Alex responde.

Contrato comum: docs/agentes/fase7-assistente.md
Regras da faixa: docs/agentes/fase7-regras-faixa.md

`enfileirar`/`resolver` (assistente/caixa.py, faixa P1a) ainda nao existem
nesta integracao - importados tardiamente (dentro da funcao) como o
contrato manda, pra essa faixa nao depender da P1a estar pronta. Idem pra
`aviso_permitido` (faixa P8), que NAO e usado aqui: quem cria perguntas na
Caixa nao manda push diretamente, isso e responsabilidade da P1a/P8.

Convenção de `origem`/`chave_unica` usada por todo item criado aqui:
`p2_<subtipo>:<id-da-entidade>:<referencia-de-data>` (ex.:
`p2_conta:7:2026-09-24`). O prefixo antes do primeiro "_" ("p2") e o que a
P1a usa pra achar de volta este arquivo (qualquer `assistente/gatilhos/p2_*.py`
serve, ver `docs/agentes/fase7-assistente.md`); manter os quatro pedaços
"p2_<subtipo>:id:data" tambem deixa o dado auto-descritivo pra depurar.
"""

from datetime import date, datetime, timedelta

from assistente import perguntas
import vida

FLAG_ATIVO = "assistente.p2.ativo"
CONFIG_ESPERA_DIAS = "assistente.p2.espera_dias"

OPCOES_CONTA = ["sim", "ainda_nao", "adiar"]
OPCOES_EVENTO = ["anotar", "nada"]
OPCOES_TAREFA = ["sim", "amanha", "proxima_semana", "escolher_data"]
OPCOES_LEMBRETE = ["feito", "adiar"]
OPCOES_ESPERA = ["cobrar", "ja_respondeu", "adiar"]


def _enfileirar(**kwargs):
    # Late import de proposito (contrato, P1a ainda nao mergeada aqui).
    from assistente.caixa import enfileirar

    return enfileirar(**kwargs)


def executar(conn, agora: datetime) -> None:
    """Chamado pelo tick (POST /api/tick, via
    assistente.gatilhos.executar_todos). Idempotente: cada sub-gatilho usa
    uma chave_unica estavel, entao rodar 2x no mesmo minuto (ou em dias
    diferentes enquanto o item seguir em aberto) nao duplica nada."""
    from db import obter_configuracao

    if not perguntas.flag_ativa(obter_configuracao(conn, FLAG_ATIVO)):
        return
    hoje = agora.date()
    _perguntar_contas_pessoais(conn, hoje)
    _perguntar_eventos_terminados(conn, agora)
    _perguntar_tarefas_vencidas(conn, hoje)
    _perguntar_lembretes(conn, hoje)
    _perguntar_esperas(conn, hoje)


# ---- Conta pessoal vencendo hoje -------------------------------------------


def _perguntar_contas_pessoais(conn, hoje: date) -> None:
    from db import conta_paga, list_contas_pessoais

    for conta in list_contas_pessoais(conn):
        nome = conta["nome"]
        if perguntas.eh_relacionamento(nome):
            continue
        vencimento = vida.vencimento_anterior(conta["dia_vencimento"], hoje)
        if vencimento != hoje:
            continue
        if conta_paga(conn, conta["id"], vencimento.isoformat()):
            continue
        chave = f"p2_conta:{conta['id']}:{vencimento.isoformat()}"
        valor = conta.get("valor")
        corpo = f"Vence hoje. Valor: R$ {valor:.2f}" if valor else "Vence hoje."
        _enfileirar(
            tipo="pergunta",
            titulo=perguntas.texto_pergunta_conta(nome),
            corpo=corpo,
            opcoes=OPCOES_CONTA,
            origem=chave,
            chave_unica=chave,
        )


def _resolver_conta(conn, conta_id: int, vencimento: str, resposta: str) -> None:
    if resposta != "sim":
        return
    from db import marcar_conta_paga

    marcar_conta_paga(conn, conta_id, vencimento)


# ---- Evento/reuniao que terminou -------------------------------------------


def _eventos_do_dia(hoje: date) -> list[dict]:
    """Le a agenda (CalDAV/iCloud) com seguranca: sem credencial configurada
    ou com a API fora do ar, devolve lista vazia em vez de quebrar o tick.
    Late import de proposito - caldav_client faz chamada de rede real fora
    de teste, e nos testes esta funcao e mockada."""
    import caldav_client

    if not caldav_client.configurado():
        return []
    try:
        return caldav_client.eventos_do_dia(hoje)
    except Exception:
        return []


def _perguntar_eventos_terminados(conn, agora: datetime) -> None:
    hoje = agora.date()
    for evento in _eventos_do_dia(hoje):
        if evento.get("dia_inteiro"):
            continue
        titulo = evento.get("titulo") or ""
        if perguntas.eh_relacionamento(titulo):
            continue
        try:
            fim = datetime.fromisoformat(evento["fim"])
        except (KeyError, TypeError, ValueError):
            continue
        if fim > agora:
            continue
        chave_id = vida.id_estavel("p2_evento", titulo, evento.get("inicio"), evento.get("fim"))
        chave = f"p2_evento:{chave_id}:{hoje.isoformat()}"
        _enfileirar(
            tipo="pergunta",
            titulo=perguntas.texto_pergunta_evento(titulo),
            corpo=titulo,
            opcoes=OPCOES_EVENTO,
            origem=chave,
            chave_unica=chave,
        )


def _resolver_evento(conn, titulo_evento: str, resposta: str, texto: str) -> None:
    if resposta != "anotar":
        return
    nota = (texto or "").strip()
    if not nota:
        return
    if perguntas.eh_relacionamento(titulo_evento) or perguntas.eh_relacionamento(nota):
        return
    from db import create_nota

    create_nota(
        conn,
        titulo=f"Como foi: {titulo_evento}",
        corpo=nota,
        tags=["assistente", "p2"],
        source_text=nota,
    )


# ---- Tarefa com prazo vencido -----------------------------------------------


def _perguntar_tarefas_vencidas(conn, hoje: date) -> None:
    rows = conn.execute(
        "SELECT id, title, due_date FROM tasks "
        "WHERE completed_at IS NULL AND due_date IS NOT NULL AND due_date < ?",
        (hoje.isoformat(),),
    ).fetchall()
    for row in rows:
        titulo = row["title"]
        if perguntas.eh_relacionamento(titulo):
            continue
        chave = f"p2_tarefa:{row['id']}:{row['due_date']}"
        dias_atraso = (hoje - date.fromisoformat(row["due_date"])).days
        _enfileirar(
            tipo="pergunta",
            titulo=perguntas.texto_pergunta_tarefa(titulo),
            corpo=f"Prazo era {row['due_date']} ({dias_atraso} dia(s) atras).",
            opcoes=OPCOES_TAREFA,
            origem=chave,
            chave_unica=chave,
        )


def _resolver_tarefa(conn, task_id: int, resposta: str, texto: str, hoje: date) -> None:
    if resposta == "sim":
        from db import complete_task

        complete_task(conn, task_id)
        return
    nova_data = perguntas.data_adiar_tarefa(resposta, hoje, texto)
    if nova_data is None:
        return
    conn.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (nova_data.isoformat(), task_id))
    conn.commit()


# ---- Lembrete sem resposta ---------------------------------------------------


def _perguntar_lembretes(conn, hoje: date) -> None:
    import notificacoes
    from db import list_lembretes

    for lembrete in list_lembretes(conn):
        titulo = lembrete["titulo"]
        if perguntas.eh_relacionamento(titulo):
            continue
        try:
            base = date.fromisoformat(lembrete["data"])
        except (TypeError, ValueError):
            continue
        proxima = notificacoes.proxima_ocorrencia_lembrete(base, bool(lembrete["recorrente"]), hoje)
        if proxima > hoje:
            continue
        chave = f"p2_lembrete:{lembrete['id']}:{proxima.isoformat()}"
        _enfileirar(
            tipo="pergunta",
            titulo=perguntas.texto_pergunta_lembrete(titulo),
            corpo=f"Data: {proxima.isoformat()}.",
            opcoes=OPCOES_LEMBRETE,
            origem=chave,
            chave_unica=chave,
        )


def _resolver_lembrete(conn, lembrete_id: int, resposta: str, hoje: date) -> None:
    if resposta in ("feito", "sim", "ok"):
        row = conn.execute(
            "SELECT recorrente FROM lembretes WHERE id = ?", (lembrete_id,)
        ).fetchone()
        if row and not row["recorrente"]:
            from db import delete_lembrete

            delete_lembrete(conn, lembrete_id)
        return
    if resposta == "adiar":
        nova = hoje + timedelta(days=1)
        conn.execute("UPDATE lembretes SET data = ? WHERE id = ?", (nova.isoformat(), lembrete_id))
        conn.commit()


# ---- "Esperando resposta de X" parada ---------------------------------------


def _perguntar_esperas(conn, hoje: date) -> None:
    from db import list_esperas_pendentes, obter_configuracao

    dias = perguntas.limiar_espera_dias(obter_configuracao(conn, CONFIG_ESPERA_DIAS))
    for espera in list_esperas_pendentes(conn):
        quem = espera["quem"]
        sobre = espera["sobre"]
        if perguntas.eh_relacionamento(quem) or perguntas.eh_relacionamento(sobre):
            continue
        try:
            criado = datetime.fromisoformat(espera["criado_em"]).date()
        except (TypeError, ValueError):
            continue
        if (hoje - criado).days < dias:
            continue
        chave = f"p2_espera:{espera['id']}:{criado.isoformat()}"
        dias_passados = (hoje - criado).days
        _enfileirar(
            tipo="pergunta",
            titulo=perguntas.texto_pergunta_espera(quem, sobre),
            corpo=f"Esperando desde {criado.isoformat()} ({dias_passados} dia(s)).",
            opcoes=OPCOES_ESPERA,
            origem=chave,
            chave_unica=chave,
        )


def _resolver_espera(conn, espera_id: int, resposta: str) -> None:
    if resposta != "ja_respondeu":
        return
    from db import resolver_espera

    resolver_espera(conn, espera_id)


# ---- ao_resolver: despacha pela origem do item ------------------------------


def ao_resolver(conn, item, resposta: str, texto: str = "", agora: datetime | None = None) -> None:
    """Chamado pela P1a quando o Alex responde um item cuja origem comeca
    com o prefixo desta faixa. `agora` e opcional (nao faz parte do
    contrato fixo) so pra dar um relogio controlavel em teste; em producao
    cai no relogio real se nao vier."""
    dados = item if isinstance(item, dict) else dict(item)
    origem = dados.get("origem") or ""
    partes = origem.split(":")
    if len(partes) < 2:
        return
    subtipo = partes[0][len("p2_"):] if partes[0].startswith("p2_") else partes[0]
    hoje = (agora or datetime.now()).date()

    try:
        if subtipo == "conta" and len(partes) >= 3:
            _resolver_conta(conn, int(partes[1]), partes[2], resposta)
        elif subtipo == "evento":
            _resolver_evento(conn, dados.get("corpo") or "", resposta, texto)
        elif subtipo == "tarefa":
            _resolver_tarefa(conn, int(partes[1]), resposta, texto, hoje)
        elif subtipo == "lembrete":
            _resolver_lembrete(conn, int(partes[1]), resposta, hoje)
        elif subtipo == "espera":
            _resolver_espera(conn, int(partes[1]), resposta)
    except (TypeError, ValueError):
        # origem malformada/id nao numerico - nao derruba o resolver da P1a.
        return
