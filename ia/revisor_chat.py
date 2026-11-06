"""Revisor da resposta do chat (leva "agentes", 2026-11-05).

Lendo 30 dias de conversa, os erros que mais voltaram eram de conta, e o modelo maior não errou menos:
- hora de sair diferente da que a ferramenta calculou (o card dizia uma coisa, o texto outra);
- "sai às 14h" quando já eram 15h;
- "das 14h às 16h (3 h)": conta de intervalo errada;
- "leva 20 min de carro" quando a rota dava 45;
- "anotei"/"marquei" sem ter chamado nenhuma ferramenta que grava.

Tudo aqui é código, sem IA: compara o texto com o que as ferramentas devolveram NESTA resposta e com o
relógio. Achou erro: `ia.funcoes.chat.chat` devolve uma nota curta pro modelo e ele refaz a resposta
UMA vez (o achado diz o certo, então a correção não precisa de modelo maior). Frase de robô no fim
("Se quiser, ...", "Espero ter ajudado") sai direto no código, sem nova chamada.

Regra do revisor: na dúvida, não acusa. Um falso alarme custa uma rodada a mais (~3 s); deixar
passar custa o que já custava antes.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

# Ferramentas que só leem ou calculam. Qualquer outra chamada sem "erro" conta como "gravou algo".
_PREFIXOS_SO_LEITURA = ("consultar_", "sugerir_", "estimar_", "calcular_", "comparar_")
_SO_LEITURA = {"briefing_meteo_voo", "fazer_pergunta_aviacao", "revisar_pergunta_aviacao"}

_HORA = r"(\d{1,2})(?:[:h](\d{2})|h)(?![\d])"
_RE_SAIR = re.compile(
    r"\b(?:sai|sair|saia|saindo|sa[ií]da)\b(?:\s+de\s+casa)?\s+(?:(?:[aà]s?|por\s+volta\s+das|l[aá]\s+pelas|umas)\s+)?"
    + _HORA, re.IGNORECASE)
_RE_ARRUMAR = re.compile(
    r"\barrumar\b[^.!?\n]{0,25}?\b(?:[aà]s?|umas)\s+" + _HORA, re.IGNORECASE)
_RE_PASSADO_ANTES = re.compile(
    r"(?:devia|deveria|tinha\s+que|era\s+pra|ia|teria\s+que|j[aá])\s+(?:ter\s+)?$", re.IGNORECASE)
_RE_OUTRO_DIA = re.compile(
    r"\b(amanh[aã]|depois\s+de\s+amanh[aã]|segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo|"
    r"semana\s+que\s+vem|pr[oó]xima\s+semana|dia\s+\d{1,2})\b", re.IGNORECASE)
_RE_INTERVALO = re.compile(
    r"\bd[ae]s?\s+" + _HORA + r"\s+(?:[aà]s?|at[eé])\s+" + _HORA
    + r"[^.!?\n]{0,20}?\(?\s*(?:s[aã]o\s+|d[aá]\s+|=\s*|,\s*)?(\d{1,2})\s*(h|horas?|min(?:utos)?)(?:\s*e\s*(\d{1,2})\s*min)?",
    re.IGNORECASE)
_RE_TRAJETO = re.compile(
    r"(?:\bleva\s+(?:uns\s+|cerca\s+de\s+|mais\s+ou\s+menos\s+)?|\b)(\d{1,3})\s*(?:min(?:utos)?|h(?:oras?)?(?:\s*e?\s*(\d{1,2})\s*(?:min)?)?)"
    r"\s+(?:de\s+)?(?:carro|viagem|estrada|trajeto|caminho|dirigindo)\b", re.IGNORECASE)
_RE_AFIRMOU = re.compile(
    r"\b(anotei|registrei|marquei|agendei|salvei|coloquei|lancei|criei|adicionei|botei|guardei|"
    r"atualizei|mudei|troquei|movi|remarquei|conclu[ií]|desmarquei)\b", re.IGNORECASE)
_RE_NEGACAO_ANTES = re.compile(r"\b(n[aã]o|nunca|ainda\s+n[aã]o|nem)\s+(?:\w+\s+){0,1}$", re.IGNORECASE)

# fecho de robô (o prompt já proíbe; quando escapa, sai aqui). Só a ÚLTIMA frase, e só se sobrar texto.
_RE_FECHO_ROBO = re.compile(
    r"(?:^|(?<=[.!?…\n]))\s*(?:se\s+quiser\b|se\s+precisar\b|qualquer\s+coisa,?\s+(?:[eé]\s+s[oó]|me)\b|"
    r"estou\s+aqui\b|t[oô]\s+aqui\s+(?:pra|para)\b|fico\s+[aà]\s+disposi[cç][aã]o|espero\s+ter\s+ajudado|"
    r"espero\s+que\s+(?:isso\s+)?ajude)[^.!?…]*[.!?…]*\s*$",
    re.IGNORECASE)


def _minutos(h: str, m: str | None) -> int | None:
    hora, minuto = int(h), int(m or 0)
    if hora > 23 or minuto > 59:
        return None
    return hora * 60 + minuto


def _hhmm(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def _hora_de(valor) -> int | None:
    if not isinstance(valor, str):
        return None
    achou = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", valor)
    return _minutos(achou.group(1), achou.group(2)) if achou else None


def _valores(obj, chave_pai=""):
    """Todos os (chave, valor) folha de um resultado de ferramenta (dict/list aninhados)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _valores(v, str(k))
    elif isinstance(obj, list):
        for v in obj:
            yield from _valores(v, chave_pai)
    else:
        yield chave_pai, obj


def _gravou(chamadas) -> bool:
    for nome, _entrada, resultado in chamadas:
        if nome in _SO_LEITURA or nome.startswith(_PREFIXOS_SO_LEITURA):
            continue
        if isinstance(resultado, dict) and resultado.get("erro"):
            continue
        return True
    return False


def _frase_em_volta(texto: str, inicio: int, fim: int) -> str:
    a = max(texto.rfind(c, 0, inicio) for c in ".!?\n")
    candidatos = [i for i in (texto.find(c, fim) for c in ".!?\n") if i >= 0]
    return texto[a + 1: min(candidatos) if candidatos else len(texto)]


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower()


def revisar(texto: str, chamadas: list, agora: datetime | None = None) -> list[dict]:
    """Confere `texto` contra `chamadas` [(ferramenta, entrada, resultado_que_a_IA_viu)] e o relógio.
    Devolve os achados [{"codigo", "detalhe"}] - cada `detalhe` já diz o certo, pronto pra nota."""
    agora = agora or datetime.now()
    texto = texto or ""
    achados: list[dict] = []

    # 1) disse que gravou sem ter gravado nada nesta resposta
    if not _gravou(chamadas):
        for m in _RE_AFIRMOU.finditer(texto):
            if _RE_NEGACAO_ANTES.search(texto[max(0, m.start() - 20): m.start()]):
                continue
            achados.append({"codigo": "afirmou_sem_fazer", "detalhe": (
                f'tu escreveu "{m.group(1)}", mas nesta resposta nenhuma ferramenta gravou nada. Se o Alex pediu '
                "pra gravar, chama a ferramenta certa agora; se não dá, diz que ainda não ficou anotado.")})
            break

    # horas que as ferramentas calcularam nesta resposta
    saidas, arrumar, duracoes = set(), set(), []
    for _nome, _entrada, resultado in chamadas:
        for chave, valor in _valores(resultado):
            if chave == "sair_de_casa" and _hora_de(valor) is not None:
                saidas.add(_hora_de(valor))
            elif chave == "comecar_a_se_arrumar" and _hora_de(valor) is not None:
                arrumar.add(_hora_de(valor))
            elif isinstance(valor, (int, float)) and not isinstance(valor, bool) and (
                    "min" in chave or "duracao" in chave):
                duracoes.append(float(valor))

    # 2) hora de sair diferente da calculada / 3) hora de sair que já passou
    for m in _RE_SAIR.finditer(texto):
        dita = _minutos(m.group(1), m.group(2))
        if dita is None:
            continue
        if saidas and dita not in saidas and all(abs(dita - s) > 2 for s in saidas):
            certas = " ou ".join(_hhmm(s) for s in sorted(saidas))
            achados.append({"codigo": "saida_diferente_do_calculo", "detalhe": (
                f"tu escreveu sair às {_hhmm(dita)}, mas o trajeto calculado deu sair às {certas}. "
                "Usa a hora calculada (é a mesma do card).")})
            continue
        if _RE_PASSADO_ANTES.search(texto[max(0, m.start() - 25): m.start()]):
            continue
        frase = _frase_em_volta(texto, m.start(), m.end())
        if _RE_OUTRO_DIA.search(frase) or _RE_OUTRO_DIA.search(texto[:m.start()][-120:]):
            continue
        agora_min = agora.hour * 60 + agora.minute
        if dita < agora_min - 5 and agora_min - dita < 12 * 60 and not saidas:
            achados.append({"codigo": "saida_no_passado", "detalhe": (
                f"tu mandou sair às {_hhmm(dita)}, mas agora já são {_hhmm(agora_min)}. Se é pra hoje, a saída "
                "tem que ser daqui pra frente (ou diz que já passou da hora e o que dá pra fazer agora).")})

    for m in _RE_ARRUMAR.finditer(texto):
        dita = _minutos(m.group(1), m.group(2))
        if dita is not None and arrumar and all(abs(dita - a) > 2 for a in arrumar):
            certas = " ou ".join(_hhmm(a) for a in sorted(arrumar))
            achados.append({"codigo": "arrumar_diferente_do_calculo", "detalhe": (
                f"tu escreveu começar a se arrumar às {_hhmm(dita)}, mas o cálculo deu {certas}.")})

    # 4) conta de intervalo: "das 14h às 16h (3 h)"
    for m in _RE_INTERVALO.finditer(texto):
        ini, fim = _minutos(m.group(1), m.group(2)), _minutos(m.group(3), m.group(4))
        if ini is None or fim is None:
            continue
        real = (fim - ini) % (24 * 60)
        n, unidade, extra = int(m.group(5)), m.group(6).lower(), int(m.group(7) or 0)
        dito = n * 60 + extra if unidade.startswith("h") else n
        if real and abs(dito - real) > 5:
            achados.append({"codigo": "conta_de_intervalo", "detalhe": (
                f"das {_hhmm(ini)} às {_hhmm(fim)} são {real // 60} h"
                + (f" {real % 60} min" if real % 60 else "") + f", não o que tu escreveu (\"{m.group(0).strip()}\").")})

    # 5) tempo de trajeto diferente do que a rota deu (só quando teve rota nesta resposta)
    if any(nome == "estimar_trajeto" for nome, _e, _r in chamadas) and duracoes:
        for m in _RE_TRAJETO.finditer(texto):
            numero = int(m.group(1))
            trecho = _sem_acento(m.group(0))
            dito = numero * 60 + int(m.group(2) or 0) if re.search(r"\d\s*h", trecho) else numero
            if dito and all(abs(dito - d) > max(5, 0.2 * d) for d in duracoes):
                perto = min(duracoes, key=lambda d: abs(d - dito))
                achados.append({"codigo": "trajeto_diferente", "detalhe": (
                    f"tu escreveu {m.group(0).strip()!r}, mas a rota calculada deu {round(perto)} min.")})
                break
    return achados


def nota_de_correcao(achados: list[dict]) -> str:
    """O que vai pro modelo refazer a resposta (uma vez)."""
    linhas = "\n".join(f"- {a['detalhe']}" for a in achados)
    so_texto = all(a["codigo"] != "afirmou_sem_fazer" for a in achados)
    return (
        "[revisão automática do painel - o Alex NÃO vê esta mensagem]\n"
        "A resposta acima tem erro de conta/fato:\n" + linhas + "\n"
        + ("Não chama ferramenta de novo (o que tinha que ser feito já foi). " if so_texto else "")
        + "Escreve a resposta inteira de novo, corrigida, no mesmo tom e tamanho, sem mencionar esta revisão."
    )


def limpar_fecho(texto: str) -> str:
    """Tira a última frase se ela for fecho de robô ("Se quiser, ...", "Espero ter ajudado") e sobrar texto."""
    if not texto:
        return texto
    m = _RE_FECHO_ROBO.search(texto)
    if not m:
        return texto
    resto = texto[:m.start()].rstrip()
    return resto if len(resto) >= 15 else texto
