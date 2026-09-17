import re
from datetime import datetime

_STMTTRN_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.IGNORECASE | re.DOTALL)


def _tag(block: str, tag: str) -> str | None:
    """Le uma tag OFX tanto no formato SGML (OFX 1.x, sem fechamento) quanto XML (OFX 2.x)."""
    match = re.search(rf"<{tag}>([^\n\r<]*)", block, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _parse_date(raw: str) -> str:
    # Formato OFX: AAAAMMDD[HHMMSS[.mmm][[-3:BRT]]] - so os 8 primeiros digitos importam aqui.
    digits = raw[:8]
    return datetime.strptime(digits, "%Y%m%d").date().isoformat()


def decode_ofx(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def parse_transactions(ofx_text: str) -> list[dict]:
    transacoes = []
    for block in _STMTTRN_RE.findall(ofx_text):
        fitid = _tag(block, "FITID")
        dtposted = _tag(block, "DTPOSTED")
        trnamt = _tag(block, "TRNAMT")
        memo = _tag(block, "MEMO") or _tag(block, "NAME") or ""
        if not (fitid and dtposted and trnamt):
            continue
        transacoes.append(
            {
                "external_id": fitid,
                "data": _parse_date(dtposted),
                "valor": float(trnamt),
                "descricao": memo,
            }
        )
    return transacoes
