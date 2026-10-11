"""assistente/avisos.py - Fase 7, faixa P8: central de avisos.

Implementa `aviso_permitido(tipo)` do contrato comum (assistente/contrato.py,
arquivo compartilhado, NAO alterado aqui) - quem manda um aviso proativo
(push e/ou item na Caixa do assistente) consulta esta funcao ANTES de
enviar, e so envia se ela devolver True. Tambem guarda a configuracao por
tipo (ligado/desligado, canal) e o horario de silencio (global, com um
inicio/fim opcional por tipo que sobrepoe o global quando presente).

Uso tipico de quem so consome (import tardio, como as outras faixas P):

    def _mandar_aviso_de_algo(...):
        from assistente.avisos import aviso_permitido
        if not aviso_permitido("cartao_limite"):
            return
        ...

## Persistencia: por que `configuracoes` em vez de tabela nova

O prompt desta faixa permite as duas formas ("tabela nova via
migracoes/202609241210_p8_avisos.sql ... ou chaves em configuracoes -
escolha a mais simples e documente"). Esta implementacao usa UMA linha na
tabela `configuracoes` (chave `CHAVE_CONFIG` abaixo), valor um JSON so, via
os helpers que db.py ja expoe (`obter_configuracao`/`definir_configuracao`
- ver db.py, funcao `obter_configuracao`). Motivos:

1. A infra de migracao automatica da Etapa 0 (`e0-backend`: `migracoes/*.sql`
   aplicado sozinho por `db.init_db()`, controle em `migracoes_aplicadas`)
   AINDA NAO chegou em `fase7/integracao` nesta sessao (checado com
   `git log origin/fase7/integracao --oneline` antes de comecar: sem
   `migracoes/` nem `rotas/` no branch). Depender dela bloquearia esta
   faixa inteira ate o merge acontecer, contra a regra de "faca primeiro
   as historias que nao dependem dela" de docs/agentes/fase7-regras-faixa.md.
2. O volume de dado e pequeno (config por tipo, `TIPOS` abaixo tem ~50
   entradas no maximo, cada uma so 4 campos) e nao precisa de indice, JOIN
   nem linha por tipo - um blob JSON e mais simples de ler/escrever inteiro
   de uma vez (`_carregar`/`_salvar` abaixo) do que uma tabela.
3. So guarda os OVERRIDES (tipo que o Alex mexeu explicitamente). Um tipo
   nunca tocado usa o padrao do catalogo (`TIPOS`) - um tipo novo adicionado
   depois (por qualquer faixa) ja funciona sem precisar de migracao de
   dado nem de UPDATE em massa.

Se, quando o `e0-backend` for integrado, o integrador preferir migrar isso
para uma tabela de verdade (uma linha por tipo, mais facil de fazer
`UPDATE ... WHERE tipo = ?`), a troca fica isolada nas funcoes privadas
`_carregar`/`_salvar` deste arquivo - a API publica (`aviso_permitido`,
`esta_ligado`, `canal`, `definir_tipo`, `definir_silencio_global`,
`listar_estado`) nao muda.

## Catalogo de tipos (`TIPOS`)

Duas partes, comentadas separadamente abaixo:

- Tipos JA EXISTENTES no pipeline antigo de push (`notificacoes.py` +
  `app.py:verificar_e_notificar`), usando o MESMO texto de `tipo` que
  `app.py` ja usa em `avisos.append((tipo, ...))` - assim, quando o
  integrador ligar `aviso_permitido` la (ver `scripts/ralph-p8-avisos/
  progress.txt` pro arquivo:linha exato), e so chamar
  `aviso_permitido(tipo)` com a mesma variavel `tipo` que ja esta no loop,
  sem precisar traduzir nome nenhum.
- Tipos NOVOS da Fase 7 (contrato `assistente/caixa.py`, US do prompt desta
  faixa): pergunta sobre conta, reuniao, tarefa vencida, lembrete, espera,
  briefing de manha/noite, regra, sinal, memoria viva, replanejar. Ainda
  sem funcao correspondente (as faixas P2-P9 que os criam ainda nao
  existem nesta integracao) - os nomes abaixo sao a chave que essas faixas
  devem usar ao chamar `aviso_permitido`/`enfileirar`.

Tipo desconhecido (fora de `TIPOS`, ex: faixa nova que ainda nao foi
cadastrada aqui): DECISAO desta faixa - `aviso_permitido` devolve True
(permitido por padrao, so respeitando o silencio GLOBAL) em vez de False.
Motivo: um tipo novo que ainda nao foi cadastrado no catalogo nao pode
ficar mudo por omissao - isso esconderia um aviso de verdade sem o Alex
nunca ter desligado nada explicitamente. `esta_ligado`/`canal` seguem a
mesma logica (True/"ambos"). Ja `definir_tipo` (a rota PUT) RECUSA tipo
desconhecido (ValueError/404) - so da pra configurar o que esta no
catalogo, pra nao criar override "orfao" sem tela nenhuma pra mostrar.
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from datetime import datetime

import db
from notificacoes import dentro_do_horario_silencioso

CHAVE_CONFIG = "assistente_avisos_config"

CANAIS = ("push", "caixa", "ambos")
CANAL_PADRAO = "ambos"

SILENCIO_PADRAO_INICIO = "22:00"
SILENCIO_PADRAO_FIM = "07:00"

_HORA_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class TipoDesconhecido(ValueError):
    """`tipo` fora do catalogo TIPOS - rotas devolvem 404 pra isso."""


# ---------------------------------------------------------------------------
# Catalogo. label = texto pt-BR pra UI (faixa visual, fora do escopo daqui).
# ligado_padrao/canal_padrao = o que vale ate o Alex mudar (aviso_permitido
# so consulta um override quando ele existir).
# ---------------------------------------------------------------------------

_PADRAO = {"ligado_padrao": True, "canal_padrao": CANAL_PADRAO}


def _tipo(label: str) -> dict:
    return {"label": label, **_PADRAO}


TIPOS: dict[str, dict] = {
    # -- Ja existentes em app.py/verificar_e_notificar (mesmo texto de tipo
    # que os `avisos.append((tipo, ...))` de la usam - ver progress.txt) --
    "rotina_manha": _tipo("Bom dia (rotina da manhã)"),
    "conta_pessoal": _tipo("Conta pessoal chegando"),
    "pessoa_sem_contato": _tipo("Faz tempo sem contato com alguém"),
    "pre_voo": _tipo("Pré-voo (véspera/dia do voo)"),
    "manutencao": _tipo("Manutenção (geral)"),
    "manutencao_veiculo": _tipo("Manutenção do veículo"),
    "responder": _tipo("Mensagens pra responder"),
    "revisao_mensal": _tipo("Revisão do mês"),
    "tarefas_atrasadas": _tipo("Tarefas atrasadas (resumo)"),
    "tarefa_parada": _tipo("Tarefa parada (cobrança individual)"),
    "espera_parada": _tipo("Espera parada"),
    "meta_atrasada": _tipo("Meta fora do ritmo"),
    "orcamento": _tipo("Orçamento perto ou estourado"),
    "teto_ia": _tipo("Teto de gasto com IA"),
    "cobranca_generica": _tipo("Cobrança sem identificar"),
    "assinatura_aumento_preco": _tipo("Assinatura ficou mais cara"),
    "gasto_elevado": _tipo("Gasto da semana elevado"),
    "gasto_dia_atipico": _tipo("Gasto do dia fora do padrão"),
    "gasto_categoria_atipico": _tipo("Gasto da categoria fora do padrão"),
    "lembrete_proximo": _tipo("Lembrete: data chegando"),
    "lembrete_despertar": _tipo("Lembrete: hora marcada"),
    "tarefa_horario": _tipo("Tarefa: horário chegando"),
    "tarefa_preparo": _tipo("Tarefa: aviso ~30 min antes"),
    "se_arrumar": _tipo("Hora de se arrumar (date, festa)"),
    "hora_de_sair": _tipo("Hora de sair (date, festa)"),
    "compromisso_chegando": _tipo("Compromisso da agenda chegando"),
    "voo_sair": _tipo("Hora de ir pro voo"),
    "planejamento_semanal": _tipo("Planejamento da semana (domingo)"),
    "semana_pesada": _tipo("Semana pesada pela frente"),
    "hora_de_dormir": _tipo("Hora de desacelerar (dormir)"),
    "fechamento_noturno": _tipo("Fechamento do dia (noite)"),
    "currency_voo": _tipo("Faz tempo que não voa"),
    "conta_a_vencer": _tipo("Conta a pagar (construtora)"),
    "clima_tarefa": _tipo("Dia bom pra tarefa pendente (clima)"),
    "uso_apps": _tipo("Resumo semanal de uso do celular"),
    "garantia_vencendo": _tipo("Garantia vencendo"),
    # -- Fase 6 (US-E8), as 6 proatividades: habito, tarefa, cartao, renda,
    # projeto, mes seguinte (mesmo texto de tipo de _avisos_proatividade_e8
    # em app.py) --
    "habito_passou_batido": _tipo("Hábito que passou batido"),
    "tarefa_horario_passou": _tipo("Tarefa que passou do horário"),
    "cartao_limite": _tipo("Cartão perto ou estourando o limite"),
    "renda_comprometida": _tipo("Renda do mês perto de acabar"),
    "projeto_poeira": _tipo("Projeto juntando poeira"),
    "mes_seguinte_apertado": _tipo("Projeção do mês seguinte apertada"),
    # -- Novos da Fase 7 (contrato assistente/caixa.py - ainda sem funcao
    # correspondente, chave que as faixas P2-P9 devem usar) --
    "pergunta_conta": _tipo("Pergunta sobre conta (ex: pagou o cartão?)"),
    "reuniao": _tipo("Reunião ou compromisso"),
    "tarefa_vencida": _tipo("Tarefa vencida"),
    "lembrete": _tipo("Lembrete"),
    "espera": _tipo("Espera parada"),
    "briefing_manha": _tipo("Briefing da manhã"),
    "briefing_noite": _tipo("Briefing da noite"),
    "regra": _tipo("Regra aprendida ou aplicada"),
    "sinal": _tipo("Sinal do iPhone (ex: cheguei no mercado)"),
    "memoria_viva": _tipo("Proposta de memória viva"),
    "replanejar": _tipo("Sugestão de replanejar a semana"),
    # -- Fase 8, faixa F3 (+ uso/m5-parcela): aviso de cobranca proxima -
    # assinatura (com o interruptor "avisar antes de cobrar" ligado) ou
    # parcela de compra parcelada (avisa por padrao) --
    "aviso_cobranca": _tipo("Assinatura ou parcela vai cobrar em breve"),
}


# ---------------------------------------------------------------------------
# Itens da Caixa -> tipo do catalogo (Fase 7, faixa C1)
# ---------------------------------------------------------------------------
# O `tipo` de um item da Caixa (pergunta/aviso/sugestao/briefing/
# proposta_memoria) e so a categoria de ordenacao da tela - nao e chave deste
# catalogo. Quem diz qual aviso e e a `origem` do item ("<arquivo do
# gatilho>:<subtipo>:..."), entao o mapa abaixo traduz origem -> chave de
# TIPOS. Toda origem que uma faixa P manda pra Caixa PRECISA estar aqui
# (tests/test_fase7_c1_caixa_avisos.py confere). Subtipo None = vale pra
# qualquer subtipo daquele gatilho.
TIPO_POR_ORIGEM: dict[tuple[str, str | None], str] = {
    ("p2_perguntas", "conta"): "pergunta_conta",
    ("p2_perguntas", "evento"): "reuniao",
    ("p2_perguntas", "tarefa"): "tarefa_vencida",
    ("p2_perguntas", "lembrete"): "lembrete",
    ("p2_perguntas", "espera"): "espera",
    ("p3_briefing", "manha"): "briefing_manha",
    ("p3_briefing", "noite"): "briefing_noite",
    # formato antigo da P3 (antes da C1), pra itens ja criados
    ("p3_briefing_manha", None): "briefing_manha",
    ("p3_briefing_noite", None): "briefing_noite",
    ("p4_regras", None): "regra",
    ("p5_replanejar", None): "replanejar",
    ("p7_sinais", None): "sinal",
    ("p9_memoria", None): "memoria_viva",
    ("f8_aviso_cobranca", "assinatura"): "aviso_cobranca",
    ("f8_aviso_cobranca", "parcela"): "aviso_cobranca",
}


def tipo_de_origem(origem) -> str | None:
    """Chave de TIPOS pra um item da Caixa, pela `origem` dele. None quando
    a origem nao e de gatilho conhecido (ex.: item criado a mao/por teste) -
    quem chama trata como "sem liga/desliga fino"."""
    if not isinstance(origem, str) or not origem.strip():
        return None
    partes = origem.strip().split(":")
    prefixo = partes[0]
    subtipo = partes[1] if len(partes) > 1 else None
    return TIPO_POR_ORIGEM.get((prefixo, subtipo)) or TIPO_POR_ORIGEM.get((prefixo, None))


# ---------------------------------------------------------------------------
# Persistencia (JSON em configuracoes.assistente_avisos_config)
# ---------------------------------------------------------------------------

def _carregar(conn) -> dict:
    """{"tipos": {tipo: {"ligado": bool?, "canal": str?, "silencio_inicio":
    str?, "silencio_fim": str?}}, "silencio": {"inicio": str, "fim": str}}.
    So guarda o que foi explicitamente definido - chave ausente cai no
    padrao do catalogo/global. JSON invalido ou de formato inesperado (ex:
    editado a mao, corrompido) volta pro estado vazio em vez de derrubar o
    app - nunca trava o pipeline de aviso por causa de config ruim."""
    bruto = db.obter_configuracao(conn, CHAVE_CONFIG)
    dado = None
    if bruto:
        try:
            dado = json.loads(bruto)
        except (TypeError, ValueError):
            dado = None
    if not isinstance(dado, dict):
        dado = {}
    tipos = dado.get("tipos")
    silencio = dado.get("silencio")
    return {
        "tipos": tipos if isinstance(tipos, dict) else {},
        "silencio": silencio if isinstance(silencio, dict) else {},
    }


def _salvar(conn, dado: dict) -> None:
    db.definir_configuracao(conn, CHAVE_CONFIG, json.dumps(dado, ensure_ascii=False))


@contextmanager
def _conexao(conn):
    """Usa `conn` se foi passada (rotas, testes que ja tem uma conexao
    aberta), senao abre e fecha uma propria - assim `aviso_permitido(tipo)`
    e `canal(tipo)` podem ser chamadas de qualquer lugar so com o tipo,
    igual o contrato pede, sem quem chama precisar gerenciar conexao."""
    if conn is not None:
        yield conn
        return
    nova = db.get_db()
    try:
        yield nova
    finally:
        nova.close()


def _override(dado: dict, tipo: str) -> dict:
    valor = dado["tipos"].get(tipo)
    return valor if isinstance(valor, dict) else {}


# ---------------------------------------------------------------------------
# Horario de silencio
# ---------------------------------------------------------------------------

def hora_valida(valor) -> bool:
    """True se `valor` e uma string 'HH:MM' (00-23:00-59)."""
    return isinstance(valor, str) and bool(_HORA_RE.match(valor))


def obter_silencio_global(conn=None) -> dict:
    with _conexao(conn) as c:
        dado = _carregar(c)
    inicio = dado["silencio"].get("inicio")
    fim = dado["silencio"].get("fim")
    return {
        "inicio": inicio if hora_valida(inicio) else SILENCIO_PADRAO_INICIO,
        "fim": fim if hora_valida(fim) else SILENCIO_PADRAO_FIM,
    }


def definir_silencio_global(inicio: str, fim: str, conn=None) -> dict:
    if not hora_valida(inicio):
        raise ValueError(f"inicio de silencio inválido (esperado HH:MM): {inicio!r}")
    if not hora_valida(fim):
        raise ValueError(f"fim de silencio inválido (esperado HH:MM): {fim!r}")
    with _conexao(conn) as c:
        dado = _carregar(c)
        dado["silencio"] = {"inicio": inicio, "fim": fim}
        _salvar(c, dado)
    return {"inicio": inicio, "fim": fim}


def _janela_silencio(tipo: str, conn=None) -> tuple[str, str]:
    """Janela efetiva pro tipo: o override do PROPRIO tipo (inicio e fim
    juntos - um so campo customizado nao mistura com o padrao global, pra
    nao criar uma janela que o Alex nunca pediu) se os dois estiverem
    presentes e validos, senao a global (customizada ou o padrao
    22:00-07:00)."""
    with _conexao(conn) as c:
        dado = _carregar(c)
    override = _override(dado, tipo)
    global_ = _silencio_global_de(dado)
    inicio_tipo = override.get("silencio_inicio")
    fim_tipo = override.get("silencio_fim")
    if hora_valida(inicio_tipo) and hora_valida(fim_tipo):
        return inicio_tipo, fim_tipo
    return global_["inicio"], global_["fim"]


def _silencio_global_de(dado: dict) -> dict:
    inicio = dado["silencio"].get("inicio")
    fim = dado["silencio"].get("fim")
    return {
        "inicio": inicio if hora_valida(inicio) else SILENCIO_PADRAO_INICIO,
        "fim": fim if hora_valida(fim) else SILENCIO_PADRAO_FIM,
    }


# ---------------------------------------------------------------------------
# Liga/desliga e canal por tipo
# ---------------------------------------------------------------------------

def esta_ligado(tipo: str, conn=None) -> bool:
    with _conexao(conn) as c:
        dado = _carregar(c)
    override = _override(dado, tipo)
    if "ligado" in override:
        return bool(override["ligado"])
    info = TIPOS.get(tipo)
    return True if info is None else info["ligado_padrao"]


def canal(tipo: str, conn=None) -> str:
    """Canal efetivo do tipo: 'push', 'caixa' ou 'ambos'."""
    with _conexao(conn) as c:
        dado = _carregar(c)
    override = _override(dado, tipo)
    valor = override.get("canal")
    if valor in CANAIS:
        return valor
    info = TIPOS.get(tipo)
    return info["canal_padrao"] if info else CANAL_PADRAO


def definir_tipo(
    tipo: str,
    *,
    ligado: bool | None = None,
    canal: str | None = None,
    silencio_inicio: str | None = None,
    silencio_fim: str | None = None,
    conn=None,
) -> dict:
    """Atualiza so os campos passados (None = nao mexe). `silencio_inicio`/
    `silencio_fim` com string vazia "" limpa o override (volta a seguir o
    silencio global)."""
    if tipo not in TIPOS:
        raise TipoDesconhecido(tipo)
    if canal is not None and canal not in CANAIS:
        raise ValueError(f"canal inválido: {canal!r} (use {CANAIS})")
    for nome, valor in (("silencio_inicio", silencio_inicio), ("silencio_fim", silencio_fim)):
        if valor not in (None, "") and not hora_valida(valor):
            raise ValueError(f"{nome} inválido (esperado HH:MM ou \"\" pra limpar): {valor!r}")
    with _conexao(conn) as c:
        dado = _carregar(c)
        override = dict(_override(dado, tipo))
        if ligado is not None:
            override["ligado"] = bool(ligado)
        if canal is not None:
            override["canal"] = canal
        if silencio_inicio is not None:
            if silencio_inicio == "":
                override.pop("silencio_inicio", None)
            else:
                override["silencio_inicio"] = silencio_inicio
        if silencio_fim is not None:
            if silencio_fim == "":
                override.pop("silencio_fim", None)
            else:
                override["silencio_fim"] = silencio_fim
        dado["tipos"][tipo] = override
        _salvar(c, dado)
        return estado_tipo(tipo, conn=c)


# ---------------------------------------------------------------------------
# Leitura consolidada (rotas)
# ---------------------------------------------------------------------------

def estado_tipo(tipo: str, conn=None) -> dict:
    info = TIPOS.get(tipo)
    with _conexao(conn) as c:
        dado = _carregar(c)
        override = _override(dado, tipo)
        silencio_global = _silencio_global_de(dado)
    inicio_tipo = override.get("silencio_inicio")
    fim_tipo = override.get("silencio_fim")
    tem_override_silencio = hora_valida(inicio_tipo) and hora_valida(fim_tipo)
    return {
        "tipo": tipo,
        "label": info["label"] if info else tipo,
        "conhecido": info is not None,
        "ligado": bool(override["ligado"]) if "ligado" in override else (info["ligado_padrao"] if info else True),
        "canal": override.get("canal") if override.get("canal") in CANAIS else (info["canal_padrao"] if info else CANAL_PADRAO),
        "silencio_inicio": inicio_tipo if tem_override_silencio else silencio_global["inicio"],
        "silencio_fim": fim_tipo if tem_override_silencio else silencio_global["fim"],
        "silencio_customizado": tem_override_silencio,
    }


def listar_estado(conn=None) -> list[dict]:
    with _conexao(conn) as c:
        return [estado_tipo(tipo, conn=c) for tipo in TIPOS]


# ---------------------------------------------------------------------------
# Contrato (assistente/contrato.py): aviso_permitido(tipo)
# ---------------------------------------------------------------------------

def aviso_permitido(tipo: str, agora: datetime | None = None, conn=None) -> bool:
    """False se `tipo` estiver desligado ou se `agora` cair na janela de
    silencio efetiva do tipo (a dele, se customizada, senao a global,
    padrao 22:00-07:00). `agora` e injetavel (default `datetime.now()`) pra
    poder testar sem depender do relogio real - nunca chama `datetime.now()`
    fora deste default. Tipo fora do catalogo: True (ver docstring do
    modulo), ainda respeitando o silencio global."""
    with _conexao(conn) as c:
        if not esta_ligado(tipo, conn=c):
            return False
        inicio, fim = _janela_silencio(tipo, conn=c)
        momento = agora if agora is not None else datetime.now()
        return not dentro_do_horario_silencioso(momento, inicio, fim)
