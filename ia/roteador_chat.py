# ia/roteador_chat.py — faixa A14 (roteador de mensagem simples do chat)
#
# O chat (A6) e 85-95% do custo de IA do painel inteiro. Antes de chamar o
# modelo grande (padrao), este modulo tenta resolver a mensagem por um
# caminho mais barato:
#   "local" -> classificador local / padrao aprendido / consulta conhecida
#              resolvem sem nenhuma chamada de IA.
#   "luna"  -> mensagem simples que ainda precisa de IA, mas nao precisa do
#              modelo grande (Luna e o modelo pequeno/barato).
#   "padrao" -> tudo o resto (comportamento de hoje, sem nenhuma mudanca).
#
# Fica ATRAS DE FLAG (ia/roteador_chat.json, {"ativo": false} por padrao):
# com a flag desligada `decidir`/`decidir_com_motivo` SEMPRE devolvem
# "padrao" - zero mudanca de comportamento ate o Alex ligar de proposito.
#
# NUNCA levanta excecao: qualquer erro interno (import que falhou, conexao
# ausente, JSON corrompido, regra local que quebrou) cai em "padrao" - o
# roteador so pode ECONOMIZAR chamada de IA, nunca pode ser motivo do chat
# quebrar ou responder errado. A6 so chama `decidir`/`decidir_com_motivo`
# antes de responder; nao mexe em mais nada do chat (isso e da A6).
#
# `ia/` nao pode importar `app.py` (import circular - ver comentario em
# ia/teto.py). Os modulos usados aqui (db, aprendizado, classificador_local)
# nao importam app.py, entao seguem seguros de importar.

import json
import re
import unicodedata
from pathlib import Path

CAMINHO_CONFIG = Path(__file__).resolve().parent / "roteador_chat.json"

# Chave alternativa em `configuracoes` (db.obter_configuracao/definir_configuracao)
# pra quem preferir ligar a flag por ali (ex: futura tela de admin) em vez de
# editar o JSON a mao. "1"/"true"/"on"/"ativo" (case-insensitive) ligam;
# qualquer outra coisa (incluindo ausente) mantem desligado.
CHAVE_CONFIG_DB = "roteador_chat_ativo"

# Mensagem "curta" o bastante pra Luna resolver sozinha sem o modelo grande.
# Acima disso, mesmo sem nenhum gatilho de conselho/decisao/emocao, a
# mensagem pode ter contexto demais pra confiar na Luna - vai pro padrao.
LIMITE_CARACTERES_LUNA = 140

# Historico "longo demais" pra Luna: contexto com muita conversa acumulada
# tende a precisar do modelo grande pra nao perder o fio. `contexto` e
# defensivo (dict solto, sem contrato fixo ainda da A6) - so olhamos pra
# chaves que poderiam existir, nunca assumimos formato.
LIMITE_HISTORICO_LUNA = 6

# Palavras/padroes que exigem o modelo grande mesmo em mensagem curta:
# pedido de conselho/decisao (a lista do prompt da faixa: "devo", "vale a
# pena", "me ajuda a decidir", "como falo com") e pergunta sobre sentimento/
# emocao. Comparado contra texto ja normalizado (minusculo, sem acento).
_RE_CONSELHO_DECISAO = re.compile(
    r"\bdevo\b"
    r"|\bdeveria\b"
    r"|vale a pena"
    r"|me ajuda(?:r)? a decidir"
    r"|como (?:eu )?falo com"
    r"|o que (?:voce |vc )?ach(?:a|o)\b"
    r"|o que (?:eu )?fac[oa]\b"
    r"|\bconselho\b"
    r"|\bme aconselh"
    r"|\bo que (?:voce |vc )?sugere\b"
    r"|\bqual (?:a )?melhor decisao\b"
    r"|\bnao sei se\b"
    r"|\bo que (?:eu )?devo fazer\b"
)
_RE_EMOCAO = re.compile(
    r"\b(?:estou|to|tô)(?: (?:muito|bem|super|meio|tao|bastante))? "
    r"(?:triste|ansios[oa]|deprimid[oa]|estressad[oa]|com raiva|mal|pessim[oa])\b"
    r"|\bme sinto\b"
    r"|\bsinto que\b"
    r"|\bnao aguento mais\b"
    r"|\bansiedade\b"
    r"|\bdepressao\b"
    r"|\bcomo (?:eu )?(?:estou|to|tô) me sentindo\b"
)


def _normalizar(texto) -> str:
    """Minusculo, sem acento, espacos colapsados - mesmo estilo de
    aprendizado.normalizar_consulta. Nunca levanta excecao; texto invalido
    vira string vazia."""
    if not isinstance(texto, str):
        return ""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sem_acento).strip()


def _flag_ativa(contexto: dict) -> bool:
    """Le a flag do roteador: primeiro `ia/roteador_chat.json` (fonte
    principal), depois a chave em `configuracoes` (via conn, se o chamador
    passou uma em contexto["conn"]). Qualquer problema (arquivo ausente,
    JSON corrompido, tabela ausente, conn ausente) -> False (comportamento
    atual, nunca quebra o chat)."""
    try:
        with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, dict) and dados.get("ativo") is True:
            return True
    except (OSError, json.JSONDecodeError):
        pass

    conn = contexto.get("conn")
    if conn is not None:
        try:
            import db

            valor = db.obter_configuracao(conn, CHAVE_CONFIG_DB)
            if isinstance(valor, str) and valor.strip().lower() in ("1", "true", "on", "ativo"):
                return True
        except Exception:
            pass

    return False


def _casar_classificador_local(texto: str) -> bool:
    """Import tardio/defensivo: `classificador_local` e infra da Etapa 0
    (X1) que pode ainda nao estar disponivel nesta branch/instalacao. Sem o
    modulo, ou com qualquer erro dentro dele, simplesmente nao resolve local
    por essa via (cai pros proximos passos) - nunca propaga excecao."""
    try:
        import classificador_local
    except ImportError:
        return False
    try:
        return bool(classificador_local.casar(texto))
    except Exception:
        return False


def _resolve_local_aprendido(texto: str, contexto: dict) -> bool:
    """Mesma logica local que app._classificar_intent(somente_local=True) ja
    usa antes de cair pra IA: padrao aprendido com confirmacoes suficientes
    (precisa de conn) ou consulta de formato conhecido (nao precisa de
    conn). Qualquer erro -> False (nao resolve local, segue o fluxo)."""
    try:
        import aprendizado
    except ImportError:
        return False

    try:
        if aprendizado.consulta_conhecida(texto):
            return True
    except Exception:
        pass

    conn = contexto.get("conn")
    if conn is not None:
        try:
            if aprendizado.padrao_intent_confiavel(conn, texto):
                return True
        except Exception:
            pass

    return False


def _historico_longo(contexto: dict) -> bool:
    for chave in ("historico", "mensagens_recentes", "historico_chat"):
        valor = contexto.get(chave)
        if isinstance(valor, (list, tuple)) and len(valor) > LIMITE_HISTORICO_LUNA:
            return True
    return False


def decidir_com_motivo(mensagem: str, contexto: dict | None = None) -> tuple[str, str]:
    """Decide o destino da mensagem do chat e registra o motivo (pra A/B e
    logs). NUNCA levanta excecao - qualquer erro interno cai em
    ("padrao", "erro:<algo>"), que e exatamente o comportamento de hoje."""
    try:
        contexto = contexto if isinstance(contexto, dict) else {}

        if not _flag_ativa(contexto):
            return "padrao", "flag_desligada"

        texto = mensagem if isinstance(mensagem, str) else ""
        texto_original = texto.strip()
        if not texto_original:
            return "padrao", "mensagem_vazia"

        normalizado = _normalizar(texto_original)
        if not normalizado:
            return "padrao", "mensagem_vazia"

        # 1) Resolve sem IA nenhuma: classificador local ou padrao/consulta
        # ja conhecidos.
        if _casar_classificador_local(texto_original):
            return "local", "classificador_local"

        if _resolve_local_aprendido(texto_original, contexto):
            return "local", "padrao_local_conhecido"

        # 2) Gatilhos que exigem o modelo grande mesmo em mensagem curta:
        # pedido de conselho/decisao ou pergunta sobre sentimento/emocao.
        if _RE_CONSELHO_DECISAO.search(normalizado):
            return "padrao", "gatilho_conselho_decisao"

        if _RE_EMOCAO.search(normalizado):
            return "padrao", "gatilho_emocao"

        # 3) Mensagem longa demais ou historico acumulado demais -> modelo
        # grande, mesmo sem gatilho de palavra.
        if len(texto_original) > LIMITE_CARACTERES_LUNA:
            return "padrao", "mensagem_longa"

        if _historico_longo(contexto):
            return "padrao", "historico_longo"

        # 4) Sobrou mensagem curta e simples, sem gatilho - Luna resolve.
        return "luna", "heuristica_luna"
    except Exception as exc:  # nunca deixa o roteador derrubar o chat
        return "padrao", f"erro:{type(exc).__name__}"


# ---------------------------------------------------------------- conversa de verdade
# Independente da flag acima: decide so se a mensagem e CONVERSA (pergunta,
# explicacao, conselho, estudo, desabafo) - ai o chat usa o modelo de conversa
# (chat.json "conversa") com mais espaco de resposta, em vez do modelo barato
# que respondia raso. Registro/operacao ("gastei 50", "anota", "marca") nunca e.
_RE_CONVERSA = re.compile(
    r"\bpor ?que\b|\bpq\b"
    r"|\b(?:me )?expli(?:ca|que)\b|\bexplicar\b"
    r"|\bo que (?:e|eh|significa|quer dizer|acontece)\b"
    r"|\bqual (?:e )?a diferenca\b|\bdiferenca entre\b"
    r"|\bcomo (?:eu )?(?:faco|fazer|consigo|melhoro|melhorar|estudo|estudar|funciona|lido|aprendo|organizo)\b"
    r"|\bme (?:ensina|ajuda a (?:entender|pensar|estudar|organizar|resolver|escrever|redigir|responder|falar))\b"
    r"|\bcomo (?:eu )?(?:respondo|escrevo|digo|falo)\b"
    r"|\bdicas?\b|\bduvida\b|\bopiniao\b|\bsincer"
    r"|\bconversa(?:r)?\b|\bdesabaf"
    r"|\bplano de estudo\b|\bestud(?:ar|ando|o)\b|\bprova\b|\bsimulado\b|\bcheck ?ride\b|\bbanca\b"
    r"|\baerodinamica\b|\bmeteorologia\b|\bnavegacao\b|\bregulamento\b|\bteoria de voo\b"
    r"|\bsustentacao\b|\bestol\b|\bperformance\b|\bpeso e balanceamento\b|\bmotor(?:es)?\b"
    r"|\b(?:ifr|vfr|metar|taf|notam|qnh|carta|aerovia)\b"
    r"|\bmotivacao\b|\bfoco\b|\bprocrastin|\btdah\b|\brotina\b"
)
_RE_OPERACAO = re.compile(
    r"^(?:gastei|paguei|comprei|recebi|anota|anote|registra|registre|lembra|lembre|marca|marque|"
    r"agenda|agende|apaga|apague|cancela|cancele|tira|adiciona|coloca|bota|muda|move|troca|"
    r"tomei|comi|bebi|fiz|terminei|acabei|acordei|dormi)\b"
)
LIMITE_CONVERSA_LONGA = 220  # pergunta/relato longo sem verbo de registro tambem e conversa


def e_conversa(mensagem) -> bool:
    """True quando a mensagem pede uma resposta pensada (nao um registro).
    Nunca levanta excecao."""
    try:
        texto = _normalizar(mensagem)
        if not texto or _RE_OPERACAO.search(texto):
            return False
        if _RE_CONSELHO_DECISAO.search(texto) or _RE_EMOCAO.search(texto) or _RE_CONVERSA.search(texto):
            return True
        return len(texto) > LIMITE_CONVERSA_LONGA and "?" in texto
    except Exception:
        return False


def decidir(mensagem: str, contexto: dict | None = None) -> str:
    """Devolve so o destino ('local', 'luna' ou 'padrao') - ver
    decidir_com_motivo para o motivo (A/B, logs)."""
    destino, _motivo = decidir_com_motivo(mensagem, contexto)
    return destino
