"""METAR/TAF oficiais via aviationweather.gov (NOAA) - gratuito, sem chave,
cobre aerodromos no mundo todo, nao so EUA (https://aviationweather.gov/data/api/).

O texto BRUTO oficial sempre vem junto, exatamente como a fonte manda. Alem
disso, os grupos padronizados (vento, visibilidade, nuvens/teto, temperatura,
altimetro) sao decodificados pra numero/unidade real - isso e conversao
exata e sem ambiguidade (tipo "BKN008" so pode significar "nublado a 800
pes", nao ha outra leitura possivel), igual o que qualquer curso de
meteorologia aeronautica ensina a fazer na mao.

`categoria_voo` (Fase 6 F3, US-F15) e a UNICA excecao a essa regra de "so
conversao, nunca julgamento" - e a classificacao PADRAO VFR/MVFR/IFR/LIFR
definida pela FAA/AIM (mesmos limiares de teto/visibilidade que o proprio
aviationweather.gov publica como "flight_category" em todo METAR), nao uma
opiniao deste app nem um "pode voar ou nao": e so mais uma conversao
tabelada de numero pra rotulo, igual BKN008 -> 800 pes, so que com 2
variaveis (teto + visibilidade) em vez de 1. A decisao de voar OU NAO
continua sendo sempre do Alex, com a licenca dele - por isso a tela sempre
mostra "Sempre confira antes de voar" junto (nunca escondido atras da
cor)."""

import re

import requests

METAR_URL = "https://aviationweather.gov/api/data/metar"
TAF_URL = "https://aviationweather.gov/api/data/taf"

_RE_VENTO = re.compile(r"^(\d{3}|VRB)(\d{2,3})(G(\d{2,3}))?KT$")
_RE_VENTO_VARIAVEL = re.compile(r"^(\d{3})V(\d{3})$")
_RE_VISIBILIDADE = re.compile(r"^(\d{4})$")
_RE_NUVEM = re.compile(r"^(FEW|SCT|BKN|OVC)(\d{3})(CB|TCU)?$")
_RE_CEU_CLARO = re.compile(r"^(NSC|SKC|CLR)$")
_RE_VIS_VERTICAL = re.compile(r"^VV(\d{3})$")
_RE_TEMP = re.compile(r"^(M?\d{2})/(M?\d{2})$")
_RE_QNH = re.compile(r"^Q(\d{4})$")
_RE_ALTIMETRO_INHG = re.compile(r"^A(\d{4})$")
_RE_PERIODO = re.compile(r"^(\d{2})(\d{2})/(\d{2})(\d{2})$")
_RE_FM = re.compile(r"^FM(\d{2})(\d{2})(\d{2})$")

# so pra decidir se uma camada conta como "teto" - definicao padrao de
# meteorologia aeronautica: teto e a camada BKN/OVC (ou visibilidade
# vertical) mais baixa, nunca uma camada FEW/SCT (essas nao cobrem a
# maior parte do ceu por definicao, entao nao formam teto)
_TIPOS_DE_TETO = ("BKN", "OVC", "VV")

_NUVEM_FALADA = {
    "FEW": "poucas nuvens",
    "SCT": "nuvens esparsas",
    "BKN": "nublado",
    "OVC": "encoberto",
    "VV": "ceu obscurecido, visibilidade vertical",
}


def _parse_temp(token: str) -> int:
    return -int(token[1:]) if token.startswith("M") else int(token)


def decodificar_grupo(tokens: list[str]) -> dict:
    """Decodifica os campos padronizados de UM bloco METAR/TAF (vento,
    visibilidade, nuvens/teto, temperatura, altimetro) - pura conversao de
    codigo pra numero/unidade, sem nenhuma interpretacao de categoria de
    voo. Tokens que nao batem com nenhum padrao conhecido sao ignorados
    (fenomenos de tempo tipo RA/TS, remarks, etc. - nao decodificados aqui,
    mas continuam disponiveis no texto bruto)."""
    resultado: dict = {
        "vento": None,
        "visibilidade_m": None,
        "nuvens": [],
        "teto_ft": None,
        "temp": None,
        "ponto_orvalho": None,
        "qnh_hpa": None,
        "altimetro_inhg": None,
    }
    for tok in tokens:
        m = _RE_VENTO.match(tok)
        if m:
            resultado["vento"] = {
                "direcao": None if m.group(1) == "VRB" else int(m.group(1)),
                "variavel": m.group(1) == "VRB",
                "velocidade_kt": int(m.group(2)),
                "rajada_kt": int(m.group(4)) if m.group(4) else None,
            }
            continue
        m = _RE_VENTO_VARIAVEL.match(tok)
        if m and resultado["vento"]:
            resultado["vento"]["variavel_entre"] = [int(m.group(1)), int(m.group(2))]
            continue
        m = _RE_NUVEM.match(tok)
        if m:
            resultado["nuvens"].append({"tipo": m.group(1), "altura_ft": int(m.group(2)) * 100})
            continue
        m = _RE_VIS_VERTICAL.match(tok)
        if m:
            resultado["nuvens"].append({"tipo": "VV", "altura_ft": int(m.group(1)) * 100})
            continue
        if _RE_CEU_CLARO.match(tok):
            continue
        if tok == "CAVOK":
            if resultado["visibilidade_m"] is None:
                resultado["visibilidade_m"] = 9999
            continue
        m = _RE_TEMP.match(tok)
        if m:
            resultado["temp"] = _parse_temp(m.group(1))
            resultado["ponto_orvalho"] = _parse_temp(m.group(2))
            continue
        m = _RE_QNH.match(tok)
        if m:
            resultado["qnh_hpa"] = int(m.group(1))
            continue
        m = _RE_ALTIMETRO_INHG.match(tok)
        if m:
            resultado["altimetro_inhg"] = int(m.group(1)) / 100
            continue
        m = _RE_VISIBILIDADE.match(tok)
        if m and resultado["visibilidade_m"] is None:
            resultado["visibilidade_m"] = int(m.group(1))
            continue

    candidatas_teto = [n["altura_ft"] for n in resultado["nuvens"] if n["tipo"] in _TIPOS_DE_TETO]
    if candidatas_teto:
        resultado["teto_ft"] = min(candidatas_teto)
    return resultado


# ---- US-F15: categoria VFR/MVFR/IFR/LIFR (definicao padrao FAA/AIM) -------
# Limiares oficiais (identicos aos que aviationweather.gov publica como
# "flight_category" em todo METAR - conferido no formato da propria fonte
# deste modulo, nao inventado): teto em pes AGL, visibilidade em statute
# miles (SM). "Sem teto" (ceu limpo/CAVOK, nenhuma nuvem BKN/OVC/VV
# reportada) conta como teto acima de 3000ft pra fins desta classificacao -
# e exatamente como a definicao oficial trata ausencia de teto.
_METROS_POR_SM = 1609.34


def categoria_voo(decodificado: dict) -> str | None:
    """None quando nao ha teto NEM visibilidade decodificados (dado
    insuficiente - nunca adivinha)."""
    teto_ft = decodificado.get("teto_ft")
    vis_m = decodificado.get("visibilidade_m")
    if teto_ft is None and vis_m is None:
        return None
    teto = teto_ft if teto_ft is not None else float("inf")
    vis_sm = (vis_m / _METROS_POR_SM) if vis_m is not None else float("inf")
    if teto < 500 or vis_sm < 1:
        return "LIFR"
    if teto < 1000 or vis_sm < 3:
        return "IFR"
    if teto <= 3000 or vis_sm <= 5:
        return "MVFR"
    return "VFR"


def _falar_vento(vento: dict | None) -> str | None:
    if not vento:
        return None
    if vento["variavel"]:
        base = f"vento variavel a {vento['velocidade_kt']} nos"
    else:
        base = f"vento de {vento['direcao']:03d} graus a {vento['velocidade_kt']} nos"
    if vento.get("rajada_kt"):
        base += f", rajadas de {vento['rajada_kt']} nos"
    return base


def _falar_visibilidade(vis_m: int | None) -> str | None:
    if vis_m is None:
        return None
    if vis_m >= 9999:
        return "visibilidade de 10 quilometros ou mais"
    if vis_m >= 5000:
        return f"visibilidade de {vis_m / 1000:g} quilometros"
    return f"visibilidade de {vis_m} metros"


def _falar_nuvens(nuvens: list[dict], teto_ft: int | None) -> str:
    if not nuvens:
        return "ceu limpo, sem nuvem significativa reportada"
    partes = [f"{_NUVEM_FALADA.get(n['tipo'], n['tipo'].lower())} a {n['altura_ft']} pes" for n in nuvens]
    txt = ", ".join(partes)
    return f"teto de {teto_ft} pes - {txt}" if teto_ft is not None else txt


def _falar_temp(temp: int | None, orvalho: int | None) -> str | None:
    if temp is None:
        return None
    partes = [f"temperatura {temp} graus"]
    if orvalho is not None:
        partes.append(f"ponto de orvalho {orvalho} graus")
    return ", ".join(partes)


def _falar_qnh(qnh: int | None) -> str | None:
    return f"altimetro {qnh} hectopascais" if qnh else None


def resumo_falado(decodificado: dict) -> str:
    """Monta uma frase em portugues a partir dos campos ja decodificados -
    usada pro botao de "ouvir". So texto gerado por template em Python,
    nunca pela IA, e nunca inclui nenhum julgamento de categoria de voo."""
    algo_decodificado = any(
        [
            decodificado.get("vento"),
            decodificado.get("visibilidade_m") is not None,
            decodificado.get("nuvens"),
            decodificado.get("temp") is not None,
            decodificado.get("qnh_hpa"),
        ]
    )
    if not algo_decodificado:
        return "Sem dados suficientes pra descrever."

    partes = [
        _falar_vento(decodificado.get("vento")),
        _falar_visibilidade(decodificado.get("visibilidade_m")),
        _falar_nuvens(decodificado.get("nuvens") or [], decodificado.get("teto_ft")),
        _falar_temp(decodificado.get("temp"), decodificado.get("ponto_orvalho")),
        _falar_qnh(decodificado.get("qnh_hpa")),
    ]
    partes = [p for p in partes if p]
    return ". ".join(p[0].upper() + p[1:] for p in partes) + "."


def decodificar_taf(tokens: list[str]) -> list[dict]:
    """Quebra os tokens do TAF (ja sem 'TAF', estacao, hora de emissao e o
    periodo geral de validade) em segmentos: previsao inicial + cada grupo
    de mudanca (BECMG/TEMPO/FM/PROB), cada um decodificado separado - o
    tempo pode mudar de um jeito muito diferente entre um segmento e
    outro, entao misturar tudo numa decodificacao so daria um resultado
    errado."""
    segmentos = [{"tipo": "Previsão inicial", "periodo": None, "tokens": []}]
    prob_pendente = None
    for tok in tokens:
        if tok == "RMK":
            break
        if tok.startswith("PROB") and tok[4:].isdigit():
            prob_pendente = tok[4:]
            continue
        if tok in ("BECMG", "TEMPO"):
            rotulo = "Tornando-se" if tok == "BECMG" else "Temporariamente"
            if prob_pendente:
                rotulo = f"Probabilidade {prob_pendente}% {rotulo.lower()}"
                prob_pendente = None
            segmentos.append({"tipo": rotulo, "periodo": None, "tokens": []})
            continue
        m = _RE_FM.match(tok)
        if m:
            segmentos.append(
                {"tipo": f"A partir do dia {m.group(1)} as {m.group(2)}:{m.group(3)}Z", "periodo": None, "tokens": []}
            )
            continue
        if tok.startswith("TX") or tok.startswith("TN"):
            continue
        m = _RE_PERIODO.match(tok)
        if m and not segmentos[-1]["tokens"] and segmentos[-1]["periodo"] is None:
            segmentos[-1]["periodo"] = f"dia {m.group(1)} {m.group(2)}Z até dia {m.group(3)} {m.group(4)}Z"
            continue
        # token normal de meteo - se tinha um PROB pendente sem TEMPO/BECMG
        # na sequencia (raro, mas a gramatica do TAF permite), abre o
        # segmento pra ele agora, na primeira info real que aparece
        if prob_pendente:
            segmentos.append({"tipo": f"Probabilidade {prob_pendente}%", "periodo": None, "tokens": []})
            prob_pendente = None
        segmentos[-1]["tokens"].append(tok)

    def _com_decodificado(s):
        dec = decodificar_grupo(s["tokens"])
        return {**s, "decodificado": dec, "categoria_voo": categoria_voo(dec)}

    return [_com_decodificado(s) for s in segmentos if s["tokens"]] or [_com_decodificado(segmentos[0])]


def resumo_falado_taf(segmentos: list[dict]) -> str:
    blocos = []
    for seg in segmentos:
        corpo = resumo_falado(seg["decodificado"])
        if corpo == "Sem dados suficientes pra descrever.":
            continue
        prefixo = seg["tipo"]
        if seg.get("periodo"):
            prefixo += f" ({seg['periodo']})"
        blocos.append(f"{prefixo}: {corpo}")
    return " ".join(blocos) if blocos else "Sem previsão detalhada disponível."


def _tokens_uteis_metar(texto: str) -> list[str]:
    """Tira o prefixo 'METAR' (a fonte as vezes manda, as vezes nao),
    estacao e hora do METAR bruto - o resto e o que da pra decodificar."""
    tokens = texto.split()
    if tokens and tokens[0] == "METAR":
        tokens = tokens[1:]
    return tokens[2:] if len(tokens) > 2 else []


def _tokens_uteis_taf(texto: str) -> list[str]:
    """Tira 'TAF', estacao, hora de emissao e o periodo geral de validade
    do TAF bruto (os 4 primeiros tokens, quando o formato bate) - o resto
    e o que vai pro decodificador de segmentos."""
    tokens = texto.split()
    if tokens and tokens[0] == "TAF":
        tokens = tokens[1:]
    return tokens[2:] if len(tokens) > 2 else []


def buscar_metar_taf(icao: str) -> dict:
    icao = (icao or "").strip().upper()
    if not icao:
        return {
            "metar": None,
            "taf": None,
            "erro": "informe o código ICAO do aerodromo",
            "metar_decodificado": None,
            "metar_falado": None,
            "metar_categoria": None,
            "taf_segmentos": None,
            "taf_falado": None,
        }

    metar, taf, erro = None, None, None
    try:
        resp = requests.get(METAR_URL, params={"ids": icao, "format": "raw"}, timeout=8)
        resp.raise_for_status()
        metar = resp.text.strip() or None
    except requests.RequestException:
        erro = "não consegui buscar o METAR agora"

    try:
        resp = requests.get(TAF_URL, params={"ids": icao, "format": "raw"}, timeout=8)
        resp.raise_for_status()
        taf = resp.text.strip() or None
    except requests.RequestException:
        if not erro:
            erro = "não consegui buscar o TAF agora"

    if not metar and not taf and not erro:
        erro = f"nenhum dado encontrado pra {icao} - confere o código ICAO"

    metar_decodificado = metar_falado = metar_cat = taf_segmentos = taf_falado = None
    if metar:
        metar_decodificado = decodificar_grupo(_tokens_uteis_metar(metar))
        metar_falado = resumo_falado(metar_decodificado)
        metar_cat = categoria_voo(metar_decodificado)
    if taf:
        taf_segmentos = decodificar_taf(_tokens_uteis_taf(taf))
        taf_falado = resumo_falado_taf(taf_segmentos)

    return {
        "metar": metar,
        "taf": taf,
        "erro": erro,
        "metar_decodificado": metar_decodificado,
        "metar_falado": metar_falado,
        "metar_categoria": metar_cat,
        "taf_segmentos": taf_segmentos,
        "taf_falado": taf_falado,
    }
