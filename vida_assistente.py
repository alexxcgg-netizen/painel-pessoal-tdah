"""Assistente de vida (2026-10-11, pedido do Alex: "um puta assistente, tipo um assistente de
vida"). Tudo que a IA precisa saber de FIXO sobre ele pra montar o dia sozinha:

- perfil do corpo (peso da ultima medida, altura, idade, objetivo) e a meta de comida que sai
  disso - conta feita AQUI, em codigo, nunca de cabeca pela IA;
- rotinas fixas que ele ensinou (voo: chegar 30 min antes pro briefing + 30 min de
  debriefing; se arrumar pra sair: 40 min);
- lugares com apelido ("obra" -> endereco da obra), que viram endereco de
  verdade no trajeto e nos avisos;
- a hora que ele acordou hoje.

Modulo puro (so SQLite via db) - app.py monta as linhas do contexto do chat com isto.
Orientacao de comida e geral (fisiologia basica), nao plano de nutricionista."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime

import db

OBJETIVOS = {"ganhar_massa": "ganhar massa muscular", "manter": "manter o peso", "perder": "perder gordura"}


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in base if not unicodedata.combining(c)).strip()


def _int_config(conn, chave: str, padrao: int, minimo: int, maximo: int) -> int:
    try:
        return max(minimo, min(maximo, int(db.obter_configuracao(conn, chave) or padrao)))
    except ValueError:
        return padrao


# ---- perfil e comida -------------------------------------------------------------

def idade(nascimento: str | None, hoje: date) -> int | None:
    try:
        n = date.fromisoformat(nascimento or "")
    except ValueError:
        return None
    return hoje.year - n.year - ((hoje.month, hoje.day) < (n.month, n.day))


def perfil(conn, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    # o valor da medida e criptografado em repouso (ENCRYPTION_KEY) - sempre pelo db._dnum
    peso, peso_data = None, None
    for r in conn.execute(
        "SELECT valor, data FROM medidas_corporais WHERE tipo = 'peso' ORDER BY data DESC, id DESC LIMIT 5"
    ).fetchall():
        valor = db._dnum(r["valor"], float)
        if valor:
            peso, peso_data = valor, r["data"]
            break
    altura = db.obter_configuracao(conn, "perfil_altura_cm")
    return {
        "peso_kg": peso,
        "peso_data": peso_data,
        "altura_cm": float(altura) if altura and re.fullmatch(r"\d{2,3}(\.\d+)?", altura) else None,
        "idade": idade(db.obter_configuracao(conn, "perfil_nascimento"), hoje),
        "objetivo": db.obter_configuracao(conn, "perfil_objetivo") or None,
        "academia": db.obter_configuracao(conn, "perfil_academia") or None,
    }


def metas_comida(peso_kg: float, altura_cm: float | None, idade_anos: int | None, objetivo: str | None) -> dict:
    """Mifflin-St Jeor (homem) x 1,5 (dia ativo, sem academia pesada todo dia) + ajuste do
    objetivo. Proteina: 2 g/kg pra ganhar massa (faixa 1,6-2,2 da literatura), 1,6 senao.
    Arredonda pra numero de gente (50 kcal / 5 g)."""
    altura_cm = altura_cm or 170.0
    idade_anos = idade_anos or 25
    basal = 10 * peso_kg + 6.25 * altura_cm - 5 * idade_anos + 5
    ajuste = {"ganhar_massa": 350, "perder": -400}.get(objetivo or "", 0)
    kcal = int(round((basal * 1.5 + ajuste) / 50) * 50)
    g_kg = 2.0 if objetivo == "ganhar_massa" else 1.6
    proteina = int(round(peso_kg * g_kg / 5) * 5)
    refeicoes = 5 if objetivo == "ganhar_massa" else 4
    return {
        "kcal": kcal,
        "proteina_g": proteina,
        "refeicoes": refeicoes,
        "proteina_por_refeicao_g": int(round(proteina / refeicoes / 5) * 5),
        "intervalo_h": "3 a 4",
    }


# ---- rotinas fixas -----------------------------------------------------------------

def voo_briefing_min(conn) -> int:
    return _int_config(conn, "voo_briefing_min", 30, 0, 180)


def voo_debriefing_min(conn) -> int:
    return _int_config(conn, "voo_debriefing_min", 30, 0, 180)


def se_arrumar_min(conn) -> int:
    return _int_config(conn, "tempo_se_arrumar_min", 40, 5, 180)


# ---- lugares com apelido ---------------------------------------------------------

_PREFIXOS_LUGAR = re.compile(r"^(a |o |na |no |pra |pro |para |ate |minha |meu |nossa |nosso )+")


def _chave_apelido(texto: str) -> str:
    chave = _sem_acento(texto)
    chave = _PREFIXOS_LUGAR.sub("", chave)
    return re.sub(r"\s+", " ", chave).strip()[:40]


def apelidos(conn) -> dict[str, str]:
    try:
        dado = json.loads(db.obter_configuracao(conn, "lugares_apelidos") or "{}")
    except ValueError:
        return {}
    return {k: v for k, v in dado.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(dado, dict) else {}


def salvar_apelido(conn, apelido: str, endereco: str) -> str | None:
    chave = _chave_apelido(apelido)
    endereco = (endereco or "").strip()[:200]
    if not chave or not endereco or chave in ("casa", "aqui", "daqui"):
        return None
    dado = apelidos(conn)
    dado[chave] = endereco
    db.definir_configuracao(conn, "lugares_apelidos", json.dumps(dado, ensure_ascii=False))
    return chave


def esquecer_apelido(conn, apelido: str) -> str | None:
    """Tira o lugar da lista ("esquece a oficina 2"). Devolve a chave tirada ou None se nao tinha."""
    chave = _chave_apelido(apelido)
    dado = apelidos(conn)
    if chave not in dado:
        return None
    del dado[chave]
    db.definir_configuracao(conn, "lugares_apelidos", json.dumps(dado, ensure_ascii=False))
    return chave


# Codigo ICAO do voo (CIV/diario) -> lugar que o Google acha. SSBL = Blumenau (Quero-Quero),
# onde fica o aeroclube dele; o apelido "aeroclube", se existir, ganha.
_ICAO_LUGAR = {"SSBL": "aeroclube", "SBNF": "Aeroporto Internacional de Navegantes"}


def resolver_lugar(conn, texto: str) -> str:
    """Apelido ('obra', 'a obra', 'minha obra') ou ICAO conhecido -> endereco; senao devolve o
    proprio texto (o Google resolve nome de lugar normal)."""
    bruto = (texto or "").strip()
    mapa = apelidos(conn)
    icao = _ICAO_LUGAR.get(bruto.upper())
    if icao:
        return mapa.get(icao, "Aeroclube de Blumenau, Blumenau - SC" if icao == "aeroclube" else icao)
    return mapa.get(_chave_apelido(bruto), bruto)


def apelido_dentro(conn, texto: str) -> str | None:
    """Apelido salvo que aparece inteiro no texto ('casa do guri' -> 'guri'), o mais comprido
    ganha. Parada do caminho (04/11) e falada solta, nunca igual ao apelido."""
    t = f" {re.sub(r'[^a-z0-9 ]', ' ', _sem_acento(texto))} "
    for chave in sorted(apelidos(conn), key=len, reverse=True):
        if chave and f" {chave} " in t:
            return chave
    return None


_RE_CASA_DE = re.compile(r"^(?:a |na |pra |pro |ate |para )?casa d[aoe]s? [a-z]+(?: [a-z]+){0,2}$")


def _casa_de_pessoa(texto: str) -> bool:
    """'casa da Fulana' / 'casa da mae' (pessoa) x 'Casa do Construtor' / 'Casa da Picanha' (loja), pelo
    db.casa_de_pessoa. Tudo minusculo ('casa da bia') a maiuscula nao diz nada: confere com o nome capitalizado
    ('casa do construtor' continua loja)."""
    if db.casa_de_pessoa(texto):
        return True
    bruto = " ".join(str(texto or "").split())
    if bruto != bruto.lower():
        return False
    capitalizado = re.sub(r"(casa d[aoe]s? )(\w)", lambda m: m.group(1) + m.group(2).upper(), bruto, count=1)
    return capitalizado != bruto and db.casa_de_pessoa(capitalizado)


def casa_de_alguem_sem_apelido(conn, texto: str) -> bool:
    """'casa da Fulana' sem apelido salvo (nem o inteiro, nem o nome dentro) e sem endereco junto: o Google
    acha uma CIDADE com aquele nome (08/11: virou 2158 min de trajeto). Isso nunca vai pro Google.
    Rodada 3: loja com "Casa" no nome ('Casa do Construtor', 'Casa da Picanha') nao e casa de ninguem - vai."""
    t = re.sub(r"\s+", " ", _sem_acento(texto))
    if not _RE_CASA_DE.match(t) or not _casa_de_pessoa(texto):
        return False
    return _chave_apelido(texto) not in apelidos(conn) and not apelido_dentro(conn, texto)


def resolver_parada(conn, texto: str) -> str:
    """Parada do caminho -> endereco: o apelido exato, senao um apelido dentro da frase
    ('casa do guri' com o apelido 'guri'), senao o proprio texto (o Google tenta).
    08/11 (A4): "casa d@ <nome>" sem apelido salvo devolve "" - quem chama usa a folga, sem Google."""
    bruto = (texto or "").strip()
    mapa = apelidos(conn)
    exato = mapa.get(_chave_apelido(bruto))
    if exato:
        return exato
    dentro = apelido_dentro(conn, bruto)
    if dentro:
        return mapa[dentro]
    return "" if casa_de_alguem_sem_apelido(conn, bruto) else bruto


# ---- acordou -----------------------------------------------------------------------

def registrar_acordou(conn, quando: datetime) -> None:
    db.definir_configuracao(conn, "acordou_em", quando.isoformat(timespec="minutes"))


def acordou_hoje(conn, agora: datetime) -> datetime | None:
    try:
        quando = datetime.fromisoformat(db.obter_configuracao(conn, "acordou_em") or "")
    except ValueError:
        return None
    return quando if quando.date() == agora.date() and quando <= agora else None


# 08/11 (frente A, A7): ele acorda ~9h40-11h e a maioria dos avisos antes das 9h nunca e vista. O primeiro
# sinal de acordado (abriu o app, check-in, bom dia, mensagem no chat, saiu de casa pelo GPS) e a hora em que
# o aviso da manha que ficou pendente repete e o check-in do dia aparece.
CONFIG_ACORDADO = "acordado_sinal"  # {"dia", "em" (local), "fonte"} - o primeiro sinal visto no dia
INICIO_DIA_ACORDADO = (5, 0)  # sinal antes disso e da madrugada (insonia, celular na mao), nao conta


def _utc_para_local(texto) -> datetime | None:
    from datetime import timezone

    try:
        dt = datetime.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().replace(tzinfo=None)


def _local_para_utc_txt(dt: datetime) -> str:
    from datetime import timezone

    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _sinais_acordado(conn, inicio: datetime, agora: datetime) -> list[tuple[datetime, str]]:
    sinais = []

    def dentro(dt):
        return dt is not None and inicio <= dt <= agora

    a = acordou_hoje(conn, agora)
    if dentro(a):
        sinais.append((a, "bom_dia"))
    try:
        c = db.get_checkin(conn, agora.date().isoformat()) or {}
        t = _utc_para_local(c.get("atualizado_em")) if any(c.get(k) for k in ("energia", "sono", "humor")) else None
        if dentro(t):
            sinais.append((t, "checkin"))
    except Exception:  # noqa: BLE001 - banco velho de teste
        pass
    visto = _utc_para_local(db.obter_configuracao(conn, "ultimo_visto_em"))  # app aberto (de_onde_parei)
    if dentro(visto):
        sinais.append((visto, "app"))
    consultas = (
        ("chat", "SELECT MIN(criado_em) FROM chat_mensagens WHERE papel = 'user' AND criado_em >= ? AND criado_em <= ?",
         (_local_para_utc_txt(inicio), _local_para_utc_txt(agora)), True),
        ("gps", "SELECT MIN(saida) FROM visitas WHERE lugar = 'casa' AND saida >= ? AND saida <= ?",
         (inicio.isoformat(timespec="seconds"), agora.isoformat(timespec="seconds")), False),
        ("gps", "SELECT MIN(chegada) FROM visitas WHERE lugar IS NOT NULL AND lugar != 'casa' "
                "AND chegada >= ? AND chegada <= ?",
         (inicio.isoformat(timespec="seconds"), agora.isoformat(timespec="seconds")), False),
    )
    for fonte, sql, args, utc in consultas:
        try:
            v = conn.execute(sql, args).fetchone()[0]
        except Exception:  # noqa: BLE001 - tabela que ainda nao existe
            continue
        if not v:
            continue
        try:
            dt = _utc_para_local(v) if utc else datetime.fromisoformat(v)
        except ValueError:
            continue
        if dentro(dt):
            sinais.append((dt, fonte))
    return sinais


def primeiro_sinal_acordado(conn, agora: datetime) -> datetime | None:
    """Hora (local) do primeiro sinal de acordado de hoje, a partir das 05:00; None se ainda nao teve.
    Guarda o primeiro que viu (o "app aberto" so guarda o ultimo batimento): fica o mesmo o dia todo."""
    hoje = agora.date().isoformat()
    try:
        salvo = json.loads(db.obter_configuracao(conn, CONFIG_ACORDADO) or "{}")
    except ValueError:
        salvo = {}
    if isinstance(salvo, dict) and salvo.get("dia") == hoje:
        try:
            em = datetime.fromisoformat(salvo.get("em") or "")
            if em <= agora:
                return em
        except ValueError:
            pass
    inicio = agora.replace(hour=INICIO_DIA_ACORDADO[0], minute=INICIO_DIA_ACORDADO[1], second=0, microsecond=0)
    if agora < inicio:
        return None
    sinais = _sinais_acordado(conn, inicio, agora)
    if not sinais:
        return None
    em, fonte = min(sinais)
    em = em.replace(microsecond=0)
    db.definir_configuracao(conn, CONFIG_ACORDADO, json.dumps({"dia": hoje, "em": em.isoformat(), "fonte": fonte}))
    conn.commit()
    return em


# ---- linhas do contexto do chat ----------------------------------------------------

def _num_br(v: float, casas: int = 1) -> str:
    return f"{v:.{casas}f}".rstrip("0").rstrip(".").replace(".", ",")


def linhas_contexto(conn, agora: datetime) -> list[str]:
    linhas = []
    p = perfil(conn, agora.date())
    partes = []
    if p["peso_kg"]:
        partes.append(f"{_num_br(p['peso_kg'])} kg (medido {p['peso_data']})")
    if p["altura_cm"]:
        partes.append(f"{_num_br(p['altura_cm'] / 100, 2)} m")
    if p["idade"]:
        partes.append(f"{p['idade']} anos")
    if p["objetivo"]:
        partes.append(f"objetivo: {OBJETIVOS.get(p['objetivo'], p['objetivo'])}")
    if p["academia"]:
        partes.append(f"academia: {p['academia']}")
    if partes:
        linhas.append("Perfil do Alex: " + ", ".join(partes))
    if p["peso_kg"]:
        m = metas_comida(p["peso_kg"], p["altura_cm"], p["idade"], p["objetivo"])
        linhas.append(
            f"Meta de comida (calculada pelo painel, use estes numeros): ~{m['kcal']} kcal e ~{m['proteina_g']} g "
            f"de proteina por dia, em {m['refeicoes']} refeicoes a cada {m['intervalo_h']} h "
            f"(~{m['proteina_por_refeicao_g']} g de proteina cada)"
        )
    linhas.append(
        f"Rotinas fixas do Alex: voo = chegar {voo_briefing_min(conn)} min antes da hora do voo pro briefing e "
        f"ficar {voo_debriefing_min(conn)} min depois de pousar pro debriefing; se arrumar pra sair (date, festa, "
        f"jantar) = {se_arrumar_min(conn)} min"
    )
    try:
        import tempo

        fator_tempo = tempo.linha_contexto(conn)
    except Exception:
        fator_tempo = None
    if fator_tempo:
        linhas.append(fator_tempo)
    mapa = apelidos(conn)
    if mapa:
        linhas.append("Lugares do Alex (apelido = endereco; pode usar o apelido no estimar_trajeto): "
                      + "; ".join(f"{k} = {v}" for k, v in sorted(mapa.items())))
    acordou = acordou_hoje(conn, agora)
    if acordou:
        minutos = int((agora - acordou).total_seconds() // 60)
        linhas.append(f"Acordou hoje as {acordou:%H:%M} (ha {minutos // 60}h{minutos % 60:02d})")
    return linhas
