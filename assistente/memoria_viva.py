"""assistente/memoria_viva.py — faixa P9 (memoria viva), Fase 7.

Uma vez por semana, olha padroes de comportamento (horario de treino, sono,
gastos recorrentes, itens de rotina cumpridos com consistencia) e PROPOE
mudancas em "O que eu lembro sobre voce" (memorias, US-E10 da Fase 6). O
texto so muda se o Alex aceitar a proposta na Caixa - este modulo nunca
grava em `memorias` diretamente (quem aplica e `assistente/gatilhos/
p9_memoria.py`, so depois de aceitar).

Regra de ouro: OS NUMEROS VEM DO CODIGO. Cada "fato" (dict com `chave`,
`tipo`, `contexto_ia`) e calculado aqui em Python, sem IA nenhuma - a IA
(`ia.core.chamar_ia("propor_memoria", ...)`) so redige o texto final a
partir do fato pronto, nunca inventa numero/data novo. Por isso a chamada e
feita 1 vez POR FATO (nao 1 vez com todos os fatos juntos): isso da a cada
proposta uma `chave` estavel, ligada ao fato que a gerou (nao ao texto que a
IA escreveu, que pode variar de uma semana pra outra) - e essa chave estavel
e o que permite ao gatilho nunca repropor a mesma coisa por 8 semanas depois
de um "recusar" (ver assistente/gatilhos/p9_memoria.py).

Filtro obrigatorio (contrato comum das faixas P, fase7-assistente.md):
NUNCA propor nada sobre vida amorosa/relacionamento. Alem disso (regra
propria desta faixa, ver AGENTS.md do financeiro-construtora e o seed de
`seus_planos` em db.py): NUNCA propor memoria com valor financeiro da
construtora - esse e outro painel, outro dono de dado, financeiro real de
empresa. `contem_assunto_proibido` cobre os dois casos e roda tanto no
texto de origem (nome de habito, texto de item de rotina, descricao de
gasto) quanto no texto final que a IA devolve - defesa em duas camadas.
"""

import logging
import re
from datetime import timedelta

import db
import gastos
import vida
from ia import core as ia_core

log = logging.getLogger(__name__)

FUNCAO_IA = "propor_memoria"

# ---------------------------------------------------------------------------
# Limiares de deteccao (todos code-side, nada disso vai pra IA decidir)
# ---------------------------------------------------------------------------
DIAS_JANELA_TREINO = 90
MIN_MARCACOES_TREINO = 6
DESVIO_MAX_MIN_TREINO = 75  # desvio-padrao do horario, em minutos

DIAS_JANELA_SONO = 30
MIN_AMOSTRAS_SONO = 7

LIMITE_GASTOS_RECORRENTES = 3

DIAS_JANELA_ROTINA = 14
LIMIAR_ROTINA_CONSISTENTE = 0.85
LIMITE_ROTINA_CONSISTENTE = 2

LIMITE_FATOS_POR_SEMANA = 5

_PALAVRAS_TREINO = (
    "trein", "academia", "gym", "exercicio", "musculacao", "corrida",
    "pilates", "yoga", "natacao", "crossfit", "alongamento",
)

# Fora do escopo por decisao do Alex (fase7-assistente.md): nunca vira
# aviso/pergunta/proposta de memoria. Radicais (sem acento, ja normalizados
# por `_normalizar`) pra pegar variacoes/conjugacoes (namorada/namorado/
# namoro/namorando/namorar...) - casados em BORDA DE PALAVRA (nao substring
# solta), pra "date" nao acertar "update" nem "namor" perder "namorando"
# por causa de sufixo.
PALAVRAS_AMOROSAS = (
    "namor", "relacionament", "casament", "casad", "noiv", "paquera",
    "crush", "affair", "conjuge", "esposa", "marido", "romance",
    "romantic", "beijo", "paixao", "date", "encontro amoroso",
)

# Regra propria desta faixa: nunca misturar dado do financeiro-construtora
# (outro projeto, outro dono de dado - ver AGENTS.md la e o seed de
# `seus_planos` em db.py, que ja diz "sem numero financeiro... nunca aqui").
PALAVRAS_CONSTRUTORA = (
    "construtora", "vgv", "obra", "canteiro",
    "faturamento da empresa", "caixa da empresa",
)


def _normalizar(texto: str | None) -> str:
    return vida.normalizar_nome(texto)


def _regex_palavras(palavras: tuple[str, ...]) -> re.Pattern:
    """Cada palavra vira um radical casado so no INICIO de uma palavra do
    texto (\\b), com qualquer sufixo depois (\\w*) - pega conjugacao
    (namor -> namorando/namorada/namoro) sem confundir com substring solta
    no meio de outra palavra (date -> nao bate em update)."""
    alternativas = "|".join(re.escape(_normalizar(p)) for p in palavras)
    return re.compile(rf"\b(?:{alternativas})\w*")


_REGEX_AMOROSO = _regex_palavras(PALAVRAS_AMOROSAS)
_REGEX_CONSTRUTORA = _regex_palavras(PALAVRAS_CONSTRUTORA)


def contem_assunto_proibido(texto: str | None) -> str | None:
    """None se o texto passa no filtro. Senao, devolve qual categoria
    proibida bateu ('vida_amorosa' ou 'financeiro_construtora'), pra log."""
    norm = _normalizar(texto)
    if not norm:
        return None
    if _REGEX_AMOROSO.search(norm):
        return "vida_amorosa"
    if _REGEX_CONSTRUTORA.search(norm):
        return "financeiro_construtora"
    return None


# ---------------------------------------------------------------------------
# Deteccao de fatos (code-only)
# ---------------------------------------------------------------------------

def _habito_de_treino(conn) -> dict | None:
    for habito in db.list_habitos(conn):
        if any(p in _normalizar(habito["nome"]) for p in _PALAVRAS_TREINO):
            return habito
    return None


def _fato_treino_horario(conn, agora, dias: int = DIAS_JANELA_TREINO,
                          minimo: int = MIN_MARCACOES_TREINO,
                          desvio_max_min: int = DESVIO_MAX_MIN_TREINO) -> dict | None:
    habito = _habito_de_treino(conn)
    if not habito or contem_assunto_proibido(habito["nome"]):
        return None
    desde = (agora.date() - timedelta(days=dias)).isoformat()
    rows = conn.execute(
        "SELECT marcado_em FROM habito_marcacoes WHERE habito_id = ? AND data >= ? ORDER BY marcado_em",
        (habito["id"], desde),
    ).fetchall()
    minutos = []
    for row in rows:
        marcado = row["marcado_em"] or ""
        try:
            hh, mm = marcado[11:16].split(":")
            minutos.append(int(hh) * 60 + int(mm))
        except (ValueError, IndexError):
            continue
    if len(minutos) < minimo:
        return None
    media = sum(minutos) / len(minutos)
    desvio = (sum((m - media) ** 2 for m in minutos) / len(minutos)) ** 0.5
    if desvio > desvio_max_min:
        return None
    h_media, m_media = divmod(round(media), 60)
    horario_str = f"{h_media:02d}:{m_media:02d}"
    contexto = (
        f"Nos ultimos {dias} dias, o habito '{habito['nome']}' foi marcado {len(minutos)} vezes, "
        f"em media por volta das {horario_str} (desvio-padrao de {round(desvio)} min entre as marcacoes)."
    )
    return {
        "chave": f"treino_horario:{habito['id']}",
        "tipo": "treino_horario",
        "contexto_ia": contexto,
        "categoria_sugerida": "sua_rotina",
    }


def _fato_sono_medio(conn, agora, dias: int = DIAS_JANELA_SONO,
                      minimo: int = MIN_AMOSTRAS_SONO) -> dict | None:
    inicio = (agora.date() - timedelta(days=dias)).isoformat()
    linhas = db.list_saude_dados(conn, desde=inicio, ate=agora.date().isoformat())
    horas = [l["sono_horas"] for l in linhas if l.get("sono_horas") is not None]
    if len(horas) < minimo:
        return None
    media = sum(horas) / len(horas)
    contexto = (
        f"Nos ultimos {dias} dias, a media de sono registrada foi de {media:.1f}h por noite "
        f"({len(horas)} noites com dado de sono)."
    )
    return {
        "chave": "sono_medio",
        "tipo": "sono_medio",
        "contexto_ia": contexto,
        "categoria_sugerida": "sua_rotina",
    }


def _fatos_gastos_recorrentes(conn, agora, limite: int = LIMITE_GASTOS_RECORRENTES) -> list[dict]:
    rows = conn.execute(
        "SELECT amount, category, description, source_text, created_at FROM expenses WHERE tipo = 'real'"
    ).fetchall()
    expenses = [dict(r) for r in rows]
    recorrentes = gastos.detectar_gastos_recorrentes(expenses, agora.date())
    fatos = []
    for r in recorrentes:
        if len(fatos) >= limite:
            break
        descricao = r["descricao"] or ""
        categoria = r["categoria"] or ""
        if contem_assunto_proibido(descricao) or contem_assunto_proibido(categoria):
            continue
        chave_descricao = _normalizar(descricao).replace(" ", "_") or "sem_descricao"
        contexto = (
            f"Gasto recorrente identificado: '{descricao}' (categoria {categoria}), "
            f"valor medio R$ {r['valor_medio']:.2f}, confirmado em {r['meses_confirmados']} meses distintos."
        )
        fatos.append({
            "chave": f"gasto_recorrente:{chave_descricao}",
            "tipo": "gasto_recorrente",
            "contexto_ia": contexto,
            "categoria_sugerida": "sua_rotina",
        })
    return fatos


def _fatos_rotina_consistente(conn, agora, dias: int = DIAS_JANELA_ROTINA,
                               limiar: float = LIMIAR_ROTINA_CONSISTENTE,
                               limite: int = LIMITE_ROTINA_CONSISTENTE) -> list[dict]:
    fim = agora.date() - timedelta(days=1)  # so dia fechado, hoje ainda pode mudar
    inicio = fim - timedelta(days=dias - 1)
    fatos = []
    for momento in ("manha", "noite"):
        for item in db.list_rotina_itens(conn, momento):
            if len(fatos) >= limite:
                return fatos
            if contem_assunto_proibido(item["texto"]):
                continue
            row = conn.execute(
                "SELECT COUNT(DISTINCT data) AS n FROM rotina_marcacoes "
                "WHERE item_id = ? AND data BETWEEN ? AND ?",
                (item["id"], inicio.isoformat(), fim.isoformat()),
            ).fetchone()
            marcados = row["n"] if row else 0
            taxa = marcados / dias
            if taxa < limiar:
                continue
            contexto = (
                f"Nos ultimos {dias} dias, o item de rotina da {momento} '{item['texto']}' foi cumprido "
                f"em {marcados} desses dias ({taxa * 100:.0f}%)."
            )
            fatos.append({
                "chave": f"rotina_consistente:{momento}:{item['id']}",
                "tipo": "rotina_consistente",
                "contexto_ia": contexto,
                "categoria_sugerida": "sua_rotina",
            })
    return fatos


def detectar_fatos(conn, agora, limite_total: int = LIMITE_FATOS_POR_SEMANA) -> list[dict]:
    """Todos os fatos code-side detectados nesta semana, em ordem de
    prioridade (treino, sono, gastos, rotina), truncado em `limite_total`
    pra nao estourar o teto de IA numa unica rodada semanal."""
    fatos = []
    treino = _fato_treino_horario(conn, agora)
    if treino:
        fatos.append(treino)
    sono = _fato_sono_medio(conn, agora)
    if sono:
        fatos.append(sono)
    fatos.extend(_fatos_gastos_recorrentes(conn, agora))
    fatos.extend(_fatos_rotina_consistente(conn, agora))
    return fatos[:limite_total]


# ---------------------------------------------------------------------------
# Chamada de IA (so redige - schema valida contra invencao de campo)
# ---------------------------------------------------------------------------

SCHEMA_PROPOSTAS = {
    "type": "object",
    "properties": {
        "propostas": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "acao": {"type": "string", "enum": ["adicionar", "alterar", "remover"]},
                    "memoria_id": {"type": ["integer", "null"]},
                    "texto": {"type": "string", "minLength": 1, "maxLength": 300},
                    "motivo": {"type": "string", "minLength": 1, "maxLength": 200},
                },
                "required": ["acao", "memoria_id", "texto", "motivo"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["propostas"],
    "additionalProperties": False,
}

SISTEMA_PROPOR_MEMORIA = (
    "Voce ajuda a manter em dia a secao \"O que eu lembro sobre voce\" de um painel pessoal "
    "de TDAH, em portugues do Brasil, tom direto e curto. Voce SO redige texto a partir do "
    "FATO que o codigo ja calculou na mensagem do usuario - nunca invente numero, data, "
    "horario ou fato novo que nao esteja ali. Pra esse fato, proponha no maximo 1 mudanca "
    "(adicionar uma memoria nova, alterar ou remover uma existente) - ou nenhuma (lista de "
    "propostas vazia) se o fato ja estiver bem representado numa memoria existente ou nao "
    "valer a pena registrar. Regras que nunca podem ser quebradas: (1) nunca proponha nada "
    "sobre vida amorosa, namoro, relacionamento ou date; (2) nunca inclua valor financeiro "
    "da construtora - essa e uma empresa com painel financeiro proprio e separado, aqui so "
    "interessa habito/rotina/gasto pessoal do dono do painel."
)


def _texto_memorias_contexto(memorias: list[dict]) -> str:
    if not memorias:
        return "(nenhuma memoria cadastrada ainda nessa categoria)"
    return "\n".join(f"- id {m['id']}: {m['texto']}" for m in memorias)


def propor_para_fato(fato: dict, memorias_contexto: list[dict]) -> list[dict]:
    """1 chamada de IA pro fato dado. Devolve a lista de propostas ja
    validadas (estrutura do schema + filtro de assunto proibido) - cada
    proposta carrega `chave` (a mesma do fato, code-side) e `categoria`
    (sugerida pelo codigo, nao pela IA)."""
    conteudo = (
        f"Fato novo detectado pelo codigo:\n{fato['contexto_ia']}\n\n"
        "Memorias atuais na categoria 'sua_rotina' (decida se e caso de adicionar uma nova, "
        "ou alterar/remover uma dessas por ela ja cobrir o mesmo assunto):\n"
        f"{_texto_memorias_contexto(memorias_contexto)}\n\n"
        "Responda so com o JSON do schema combinado - 'propostas' pode ser uma lista vazia."
    )
    resp = ia_core.chamar_ia(
        FUNCAO_IA,
        [{"role": "user", "content": conteudo}],
        sistema=SISTEMA_PROPOR_MEMORIA,
        schema=SCHEMA_PROPOSTAS,
    )
    if not resp.ok:
        log.info("memoria_viva: ia nao respondeu pro fato %s (%s)", fato["chave"], resp.erro)
        return []
    if not isinstance(resp.dados, dict):
        log.warning("memoria_viva: resposta sem dados estruturados pro fato %s", fato["chave"])
        return []
    brutas = resp.dados.get("propostas")
    if not isinstance(brutas, list):
        return []

    ids_validos = {m["id"] for m in memorias_contexto}
    limpas = []
    for proposta in brutas:
        if not isinstance(proposta, dict):
            continue
        acao = proposta.get("acao")
        texto = (proposta.get("texto") or "").strip()
        motivo = (proposta.get("motivo") or "").strip()
        memoria_id = proposta.get("memoria_id")
        if acao not in ("adicionar", "alterar", "remover") or not texto or not motivo:
            continue
        if acao == "adicionar":
            memoria_id = None
        else:
            if not isinstance(memoria_id, int) or isinstance(memoria_id, bool) or memoria_id not in ids_validos:
                # alterar/remover apontando pra uma memoria que nao existe (ou que a IA
                # inventou) - descarta, nunca aplica um id que o codigo nao confirmou.
                continue
        if contem_assunto_proibido(texto) or contem_assunto_proibido(motivo):
            log.warning("memoria_viva: proposta descartada por assunto proibido (fato %s)", fato["chave"])
            continue
        limpas.append({
            "chave": fato["chave"],
            "acao": acao,
            "memoria_id": memoria_id,
            "texto": texto,
            "motivo": motivo,
            "categoria": fato.get("categoria_sugerida"),
        })
    return limpas


def gerar_propostas_da_semana(conn, agora, *, recusas_recentes=frozenset(),
                               limite_fatos: int = LIMITE_FATOS_POR_SEMANA) -> list[dict]:
    """Ponto de entrada da faixa: detecta os fatos da semana (pulando os que
    o Alex ja recusou nas ultimas 8 semanas), chama a IA 1x por fato e
    devolve a lista de propostas prontas pra `assistente/gatilhos/
    p9_memoria.py` enfileirar na Caixa. Nunca levanta por falha de IA -
    fato sem resposta valida so vira 0 propostas."""
    fatos = [f for f in detectar_fatos(conn, agora, limite_total=limite_fatos)
             if f["chave"] not in recusas_recentes]
    if not fatos:
        return []
    memorias_contexto = db.contexto_memorias_categorizadas(conn).get("sua_rotina", [])
    resultado = []
    for fato in fatos:
        resultado.extend(propor_para_fato(fato, memorias_contexto))
    return resultado
