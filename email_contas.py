"""Cacador de contas no e-mail (Laboratorio v4, ideia "contas-email", 30/10/2026).

Le a caixa de entrada por IMAP (SO LEITURA: `select(readonly=True)` + `BODY.PEEK[]`, nunca marca como
lido, nunca apaga, nunca responde), acha boleto, PIX copia-e-cola, fatura e codigo de rastreio e guarda
em `contas_email`. Cada conta com vencimento ganha uma tarefa pessoal ("Pagar conta: Enel") no dia.

Ligado SO com as 2 variaveis no `.env` (a senha e uma "senha de app" do Google, nunca a senha da conta;
quem digita no `.env` e o Alex - ver docs/briefings/2026-10-30-lab-v4-dinheiro.md):
    EMAIL_IMAP_USUARIO=  EMAIL_IMAP_SENHA_APP=  (opcionais: EMAIL_IMAP_HOST, EMAIL_IMAP_PASTA)
Sem elas `configurado()` e False e nada aqui toca em rede.

Nada de IA: tudo e regex + conferencia (modulo 10 da linha digitavel, CRC16 do PIX). Codigo que nao
fecha a conferencia NAO vira botao de "Copiar" (copiar um codigo quebrado e pior que nao ter o botao).
O conteudo do e-mail e DADO: nunca vira instrucao, nunca vai pra Claude.

Dinheiro PESSOAL do Alex. Nunca toca o banco nem a API da construtora.
"""

from __future__ import annotations

import email
import email.header
import email.utils
import html as _html
import imaplib
import logging
import os
import re
from datetime import date, datetime, timedelta

log = logging.getLogger(__name__)

INTERVALO_MIN = 30
JANELA_DIAS = 14
MAX_MENSAGENS = 60
TIMEOUT_S = 20
TAMANHO_MAX_TEXTO = 200_000

TIPOS = ("boleto", "pix", "fatura", "rastreio")


def configurado(env=None) -> bool:
    env = os.environ if env is None else env
    return bool((env.get("EMAIL_IMAP_USUARIO") or "").strip() and (env.get("EMAIL_IMAP_SENHA_APP") or "").strip())


# ---------------------------------------------------------------- codigos


def _mod10(campo: str) -> int:
    soma, peso = 0, 2
    for c in reversed(campo):
        p = int(c) * peso
        soma += p // 10 + p % 10
        peso = 1 if peso == 2 else 2
    return (10 - soma % 10) % 10


def linha_valida(digitos: str) -> bool:
    """47 digitos (boleto bancario): confere o DV (modulo 10) dos 3 primeiros campos. 48 (concessionaria:
    luz, agua, telefone): so tamanho e comecar com 8 (o DV muda conforme o 3o digito)."""
    if not digitos.isdigit():
        return False
    if len(digitos) == 48:
        return digitos[0] == "8"
    if len(digitos) != 47:
        return False
    return all(_mod10(digitos[a:b - 1]) == int(digitos[b - 1]) for a, b in ((0, 10), (10, 21), (21, 32)))


def _vencimento_do_fator(fator: int, hoje: date) -> date | None:
    if fator <= 0:
        return None
    c1 = date(1997, 10, 7) + timedelta(days=fator)
    c2 = date(2025, 2, 22) + timedelta(days=fator - 1000) if fator >= 1000 else None  # fator reiniciou em 22/02/2025
    for c in (c2, c1):
        if c and hoje - timedelta(days=120) <= c <= hoje + timedelta(days=400):
            return c
    return None


def dados_da_linha(digitos: str, hoje: date) -> dict:
    """{valor, vencimento ISO|None} que a propria linha digitavel carrega."""
    if len(digitos) == 47:
        valor = int(digitos[37:47]) / 100
        venc = _vencimento_do_fator(int(digitos[33:37]), hoje)
        return {"valor": valor or None, "vencimento": venc.isoformat() if venc else None}
    valor = int(digitos[4:15]) / 100 if digitos[2] in "6789" else None
    return {"valor": valor or None, "vencimento": None}


_RE_LINHA47 = re.compile(r"(?<!\d)\d{5}[.\s]?\d{5}\s+\d{5}[.\s]?\d{6}\s+\d{5}[.\s]?\d{6}\s+\d\s+\d{14}(?!\d)")
_RE_LINHA48 = re.compile(r"(?<!\d)(?:\d{11}[\s\-]?\d\s+){3}\d{11}[\s\-]?\d(?!\d)")
_RE_CORRIDO = re.compile(r"(?<!\d)\d{47,48}(?!\d)")


def achar_linhas(texto: str) -> list[str]:
    achadas = []
    for rx in (_RE_LINHA47, _RE_LINHA48, _RE_CORRIDO):
        for m in rx.finditer(texto):
            d = re.sub(r"\D", "", m.group(0))
            if linha_valida(d) and d not in achadas:
                achadas.append(d)
    return achadas


def formatar_linha(d: str) -> str:
    if len(d) == 47:
        return f"{d[0:5]}.{d[5:10]} {d[10:15]}.{d[15:21]} {d[21:26]}.{d[26:32]} {d[32]} {d[33:]}"
    return " ".join(f"{d[i:i + 12]}" for i in range(0, 48, 12))


def _crc16(texto: str) -> str:
    crc = 0xFFFF
    for b in texto.encode("utf-8"):
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def _tlv(payload: str) -> dict:
    campos, i = {}, 0
    while i + 4 <= len(payload):
        tag, n = payload[i:i + 2], payload[i + 2:i + 4]
        if not n.isdigit():
            break
        n = int(n)
        campos[tag] = payload[i + 4:i + 4 + n]
        i += 4 + n
    return campos


def pix_valido(payload: str) -> bool:
    p = payload.strip()
    return (
        len(p) > 40 and p.startswith("000201") and "br.gov.bcb.pix" in p.lower()
        and _crc16(p[:-4]) == p[-4:].upper()
    )


def achar_pix(texto: str) -> list[str]:
    achados = []
    for m in re.finditer(r"(?<![0-9A-Za-z])000201[^\r\n]{30,700}", texto):
        p = m.group(0)
        # nome/cidade do recebedor podem ter espaco; o CRC (4 ultimos caracteres) marca onde o codigo acaba -
        # texto depois dele (ponto, frase) nao entra
        for corte in range(len(p), 40, -1):
            if pix_valido(p[:corte]):
                if p[:corte] not in achados:
                    achados.append(p[:corte])
                break
    return achados


def dados_do_pix(payload: str) -> dict:
    t = _tlv(payload)
    try:
        valor = float(t["54"]) if "54" in t else None
    except ValueError:
        valor = None
    return {"valor": valor or None, "nome": (t.get("59") or "").strip().title() or None}


# ---------------------------------------------------------------- texto do e-mail


def _decodificar(h) -> str:
    if not h:
        return ""
    try:
        return str(email.header.make_header(email.header.decode_header(str(h))))
    except Exception:  # noqa: BLE001 - cabecalho torto nunca derruba a varredura
        return str(h)


def _texto_da_mensagem(msg) -> str:
    textos, htmls = [], []
    for parte in msg.walk():
        tipo = parte.get_content_type()
        if tipo not in ("text/plain", "text/html") or parte.get_filename():
            continue
        try:
            corpo = parte.get_payload(decode=True) or b""
            s = corpo.decode(parte.get_content_charset() or "utf-8", errors="replace")
        except (LookupError, ValueError):
            continue
        (textos if tipo == "text/plain" else htmls).append(s)
    if textos:
        t = "\n".join(textos)
    else:
        t = "\n".join(htmls)
        t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
        t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", t)
        t = _html.unescape(re.sub(r"<[^>]+>", " ", t))
    return t[:TAMANHO_MAX_TEXTO]


_PALAVRAS_CONTA = (
    "boleto", "fatura", "vencimento", "vence em", "vence dia", "pix copia", "copia e cola", "copia e cola",
    "linha digit", "segunda via", "mensalidade", "cobranca", "cobrança", "pagamento", "pague ate", "pague até",
)
_RE_VALOR = re.compile(r"R\$\s*((?:\d{1,3}(?:\.\d{3})+|\d+),\d{2})")
_RE_VENC = re.compile(r"venc\w*[^0-9\n]{0,40}(\d{2})/(\d{2})(?:/(\d{4}))?", re.I)
_RE_RASTREIO = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2}\d{9}BR)(?![A-Za-z0-9])")


def _para_float(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _valor_do_texto(texto: str) -> float | None:
    sem_acento = texto
    for rot in ("valor", "total", "pagar", "fatura"):
        i = sem_acento.lower().find(rot)
        if i >= 0:
            m = _RE_VALOR.search(sem_acento, i)
            if m and m.start() - i < 120:
                return _para_float(m.group(1))
    m = _RE_VALOR.search(texto)
    return _para_float(m.group(1)) if m else None


def _vencimento_do_texto(texto: str, hoje: date) -> str | None:
    m = _RE_VENC.search(texto)
    if not m:
        return None
    d, mes, a = int(m.group(1)), int(m.group(2)), m.group(3)
    try:
        if a:
            return date(int(a), mes, d).isoformat()
        for ano in (hoje.year, hoje.year + 1):
            v = date(ano, mes, d)
            if v >= hoje - timedelta(days=5):
                return v.isoformat()
    except ValueError:
        return None
    return None


def _nome_remetente(msg) -> str:
    nome, endereco = email.utils.parseaddr(_decodificar(msg.get("From")))
    nome = re.sub(r"[\"<>]", "", nome or "").strip()
    if not nome and "@" in endereco:
        dominio = endereco.split("@", 1)[1].split(".")[0]
        nome = dominio.title()
    return (nome or "Remetente")[:60]


def analisar(raw: bytes, hoje: date) -> list[dict]:
    """E-mail cru -> 0..2 achados {msg_sufixo, tipo, remetente, assunto, valor, vencimento, codigo}.
    Funcao pura (sem rede, sem banco): e o que os testes exercitam com e-mails inventados."""
    msg = email.message_from_bytes(raw)
    assunto = _decodificar(msg.get("Subject")).strip()[:140]
    remetente = _nome_remetente(msg)
    texto = _texto_da_mensagem(msg)
    baixo = (assunto + " " + texto).lower()
    achados = []

    linhas = achar_linhas(texto)
    pixes = achar_pix(texto)
    if linhas:
        d = linhas[0]
        da_linha = dados_da_linha(d, hoje)
        achados.append({
            "sufixo": "", "tipo": "boleto", "remetente": remetente, "assunto": assunto, "codigo": formatar_linha(d),
            "valor": da_linha["valor"] or _valor_do_texto(texto),
            "vencimento": da_linha["vencimento"] or _vencimento_do_texto(texto, hoje),
        })
    elif pixes:
        dp = dados_do_pix(pixes[0])
        achados.append({
            "sufixo": "", "tipo": "pix", "remetente": remetente, "assunto": assunto, "codigo": pixes[0],
            "valor": dp["valor"] or _valor_do_texto(texto), "vencimento": _vencimento_do_texto(texto, hoje),
        })
    elif any(p in baixo for p in _PALAVRAS_CONTA):
        # fatura sem codigo no corpo (o boleto vem em anexo/no site): so vale se tem valor E vencimento
        valor, venc = _valor_do_texto(texto), _vencimento_do_texto(texto, hoje)
        if valor and venc:
            achados.append({
                "sufixo": "", "tipo": "fatura", "remetente": remetente, "assunto": assunto, "codigo": None,
                "valor": valor, "vencimento": venc,
            })
    m = _RE_RASTREIO.search(texto)
    if m:
        achados.append({
            "sufixo": "#rastreio", "tipo": "rastreio", "remetente": remetente, "assunto": assunto,
            "codigo": m.group(1), "valor": None, "vencimento": None,
        })
    return achados


# ---------------------------------------------------------------- IMAP (so leitura)


def _fonte_imap(vistos, env=None, hoje=None):
    """Gera (msg_id, bytes) das mensagens recentes ainda nao vistas. `vistos(msg_id) -> bool`."""
    env = os.environ if env is None else env
    host = (env.get("EMAIL_IMAP_HOST") or "imap.gmail.com").strip()
    pasta = (env.get("EMAIL_IMAP_PASTA") or "INBOX").strip()
    hoje = hoje or date.today()
    desde = (hoje - timedelta(days=JANELA_DIAS)).strftime("%d-%b-%Y")
    M = imaplib.IMAP4_SSL(host, 993, timeout=TIMEOUT_S)
    try:
        M.login(env["EMAIL_IMAP_USUARIO"].strip(), env["EMAIL_IMAP_SENHA_APP"].strip())
        M.select(pasta, readonly=True)  # readonly: o servidor nem deixa mudar flag
        typ, dados = M.search(None, "SINCE", desde)
        ids = (dados[0] or b"").split()[-MAX_MENSAGENS:] if typ == "OK" else []
        for num in reversed(ids):
            typ, cab = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
            if typ != "OK" or not cab or not isinstance(cab[0], tuple):
                continue
            mid = email.message_from_bytes(cab[0][1]).get("Message-ID", "").strip()[:300]
            if not mid or vistos(mid):
                continue
            typ, corpo = M.fetch(num, "(BODY.PEEK[])")
            if typ == "OK" and corpo and isinstance(corpo[0], tuple):
                yield mid, corpo[0][1]
    finally:
        try:
            M.logout()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- varredura + banco


def _nome_curto(c: dict) -> str:
    return (c.get("remetente") or "Conta")[:40]


def varrer(conn, agora: datetime, fonte=None, forcar: bool = False, env=None) -> dict:
    """Uma passada. Respeita o intervalo de 30 min (a nao ser `forcar`). `fonte` e injetavel (teste):
    `fonte(vistos) -> iteravel de (msg_id, bytes)`. Devolve
    {"ligado", "rodou", "novas": [contas], "lidos": n, "erro": str|None}."""
    from db import criar_tarefa_de_brain_dump, definir_configuracao, obter_configuracao

    if fonte is None and not configurado(env):
        return {"ligado": False, "rodou": False, "novas": [], "lidos": 0, "erro": None}
    ultima = obter_configuracao(conn, "contas_email_ultima")
    if ultima and not forcar:
        try:
            if agora - datetime.fromisoformat(ultima) < timedelta(minutes=INTERVALO_MIN):
                return {"ligado": True, "rodou": False, "novas": [], "lidos": 0, "erro": None}
        except ValueError:
            pass
    definir_configuracao(conn, "contas_email_ultima", agora.isoformat())  # marca ANTES: falha de rede nao vira martelada
    conn.commit()

    def visto(mid):
        return bool(conn.execute("SELECT 1 FROM email_vistos WHERE msg_id = ?", (mid,)).fetchone())

    gerador = fonte(visto) if fonte else _fonte_imap(visto, env, agora.date())
    novas, lidos, erro = [], 0, None
    try:
        for mid, raw in gerador:
            lidos += 1
            try:
                achados = analisar(raw, agora.date())
            except Exception:  # noqa: BLE001 - uma mensagem torta nao derruba as outras
                log.exception("contas_email: nao consegui ler uma mensagem")
                achados = []
            conn.execute("INSERT OR IGNORE INTO email_vistos (msg_id) VALUES (?)", (mid,))
            for a in achados:
                chave = mid + a["sufixo"]
                tarefa_id = None
                if a["tipo"] != "rastreio" and a["vencimento"] and a["vencimento"] >= agora.date().isoformat():
                    tarefa_id = criar_tarefa_de_brain_dump(
                        conn, f"Pagar conta: {_nome_curto(a)}", a["vencimento"], None, "e-mail (caçador de contas)"
                    )
                cur = conn.execute(
                    "INSERT OR IGNORE INTO contas_email (msg_id, remetente, assunto, tipo, valor, vencimento, codigo, tarefa_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (chave, a["remetente"], a["assunto"], a["tipo"], a["valor"], a["vencimento"], a["codigo"], tarefa_id),
                )
                if cur.rowcount:
                    novas.append(obter(conn, cur.lastrowid))
            conn.commit()
    except Exception as e:  # noqa: BLE001 - login errado, rede fora, timeout: frase pronta, nunca stack trace
        conn.rollback()
        log.warning("contas_email: varredura falhou (%s)", type(e).__name__)
        erro = "Não consegui entrar no e-mail agora (confere a senha de app no .env ou tenta mais tarde)."
    return {"ligado": True, "rodou": True, "novas": novas, "lidos": lidos, "erro": erro}


def obter(conn, conta_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM contas_email WHERE id = ?", (conta_id,)).fetchone()
    return dict(r) if r else None


def pendentes(conn, limite: int = 8) -> list[dict]:
    rs = conn.execute(
        "SELECT * FROM contas_email WHERE status = 'nova' ORDER BY (vencimento IS NULL), vencimento, id DESC LIMIT ?",
        (max(1, min(int(limite), 30)),),
    ).fetchall()
    return [dict(r) for r in rs]


def marcar(conn, conta_id: int, status: str) -> bool:
    """paga | ignorada. Paga tambem conclui a tarefa de lembrete (se ainda aberta)."""
    if status not in ("paga", "ignorada", "nova"):
        return False
    c = obter(conn, conta_id)
    if not c:
        return False
    conn.execute("UPDATE contas_email SET status = ? WHERE id = ?", (status, conta_id))
    if status == "paga" and c.get("tarefa_id"):
        conn.execute("UPDATE tasks SET completed_at = datetime('now') WHERE id = ? AND completed_at IS NULL", (c["tarefa_id"],))
    conn.commit()
    return True
