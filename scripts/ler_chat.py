#!/usr/bin/env python3
"""scripts/ler_chat.py - copia do chat do app (Alex <-> IA do painel) pro Claude
Code ler e entender melhor o que o Alex pede, o que ele corrige e o que ele nao
gosta. Pedido dele (2026-10-15): "toda vez que tu pedir, essa copia do chat vai
pra voce". Texto em vez de PDF/print: o Claude le direto, sem perder nada.

So LE o banco real (sqlite `mode=ro` - nunca grava, nunca importa app.py).
Gera markdown em `data/chat_para_claude.md` (data/ esta no .gitignore - a copia
tem coisa pessoal e nunca pode ir pro git). Os cards da resposta (criptografados
em repouso) sao lidos com a chave do .env e resumidos numa linha.

Uso:
  .venv/Scripts/python.exe scripts/ler_chat.py            # ultimos 7 dias
  .venv/Scripts/python.exe scripts/ler_chat.py --dias 30
  .venv/Scripts/python.exe scripts/ler_chat.py --desde 2026-10-01 --ate 2026-10-10
"""

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

BANCO_PADRAO = RAIZ / "data" / "painel.db"
SAIDA_PADRAO = RAIZ / "data" / "chat_para_claude.md"
DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

# Tua mensagem logo depois de uma resposta da IA que soa como correção/reclamação.
# Só uma pista pra achar rápido - quem decide se era reclamação é quem lê.
_CORRECAO = re.compile(
    r"\bnao (era|e|foi) (isso|assim)|\bnao (quero|gostei|pedi|entendeu)|errad|nada a ver|"
    r"\b(para|pare) de\b|\bja (falei|disse)|de novo\b|\bnao funciona|\bpior\b|horrivel|"
    r"\bchato\b|\bestranho\b|\bfeio\b|\bnao ta\b|\bta errado|\besquece\b|\bmuito (lento|longo|grande)"
)
_NUMERO_LONGO = re.compile(r"(?<!\d)(?:\d[ .\-/]?){10,}\d(?!\d)")
_SENHA = re.compile(r"(?i)\b(senha|password|pin|token|chave pix)\b(\s*(?:[:=]|é|e)?\s*)(\S+)")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def parece_correcao(texto: str) -> bool:
    return bool(_CORRECAO.search(_sem_acento(texto or "")))


def ocultar_sensivel(texto: str) -> str:
    """CPF, cartão, conta, telefone (11+ dígitos) e o que vem depois de "senha"/"pin"/
    "token" nunca saem na cópia - o resto vai como ele escreveu."""
    texto = _NUMERO_LONGO.sub("[número oculto]", texto or "")
    return _SENHA.sub(lambda m: f"{m.group(1)}{m.group(2)}[oculto]", texto)


def hora_local(criado_em: str) -> datetime | None:
    """`criado_em` é UTC (DEFAULT datetime('now')) - converte pro horário daqui."""
    try:
        utc = datetime.fromisoformat((criado_em or "").strip()).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return utc.astimezone().replace(tzinfo=None)


def _curto(valor, limite: int = 40) -> str:
    texto = ocultar_sensivel(str(valor)).replace("\n", " ")
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def resumo_card(card: dict) -> str:
    """`tipo`: até 6 campos simples do data (lista vira os itens curtos ou a contagem)."""
    tipo = card.get("type") or card.get("tipo") or "?"
    dados = card.get("data") if isinstance(card.get("data"), dict) else {}
    partes = []
    for chave, valor in dados.items():
        if len(partes) >= 6:
            break
        if valor is None or valor == "" or isinstance(valor, dict):
            continue
        if isinstance(valor, list):
            simples = [v for v in valor if isinstance(v, (str, int, float))]
            if simples and len(simples) == len(valor) and len(valor) <= 4:
                partes.append(f"{chave}={_curto(', '.join(map(str, simples)))}")
            else:
                partes.append(f"{chave}=[{len(valor)}]")
        else:
            partes.append(f"{chave}={_curto(valor)}")
    acoes = [a.get("label") for a in card.get("actions") or [] if isinstance(a, dict) and a.get("label")]
    linha = f"card `{tipo}`" + (": " + " · ".join(partes) if partes else "")
    if acoes:
        linha += f" (botões: {', '.join(_curto(a, 24) for a in acoes[:4])})"
    return linha


def _cards(cards_json) -> list:
    if not cards_json:
        return []
    try:
        import criptografia

        cards = json.loads(criptografia.descriptografar(cards_json) or "[]")
    except Exception:  # chave ausente/dado ilegível: a cópia sai sem o card, nunca quebra
        return [{"type": "(não deu pra ler o card)"}]
    return [c for c in cards if isinstance(c, dict)] if isinstance(cards, list) else []


def abrir_so_leitura(caminho: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{caminho.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def montar_copia(conn, desde: date, ate: date) -> tuple[str, dict]:
    """Markdown da conversa entre `desde` e `ate` (dias locais, inclusive)."""
    # margem de 1 dia no filtro UTC; o corte certo é feito pela hora local
    ini = (desde - timedelta(days=1)).isoformat()
    fim = (ate + timedelta(days=2)).isoformat()
    tem_cards = any(r[1] == "cards_json" for r in conn.execute("PRAGMA table_info(chat_mensagens)"))
    colunas = "id, papel, texto, criado_em" + (", cards_json" if tem_cards else "")
    linhas = conn.execute(
        f"SELECT {colunas} FROM chat_mensagens WHERE criado_em >= ? AND criado_em < ? ORDER BY criado_em, id",
        (ini, fim),
    ).fetchall()

    corpo, dia_atual = [], None
    conta = {"alex": 0, "ia": 0, "correcoes": 0, "cards": 0}
    papel_anterior = None
    for r in linhas:
        quando = hora_local(r["criado_em"])
        if quando is None or not (desde <= quando.date() <= ate):
            continue
        if quando.date() != dia_atual:
            dia_atual = quando.date()
            corpo.append(f"\n## {DIAS_SEMANA[dia_atual.weekday()]} {dia_atual.strftime('%d/%m/%Y')}\n")
        texto = ocultar_sensivel(r["texto"]).strip()
        if r["papel"] == "user":
            conta["alex"] += 1
            marca = ""
            if papel_anterior == "assistant" and parece_correcao(r["texto"]):
                conta["correcoes"] += 1
                marca = "⚠ "
            corpo.append(f"**{quando:%H:%M} {marca}Alex:** {texto}\n")
        else:
            conta["ia"] += 1
            corpo.append(f"**{quando:%H:%M} IA:** {texto}\n")
            for card in _cards(r["cards_json"] if tem_cards else None):
                conta["cards"] += 1
                corpo.append(f"  ↳ {resumo_card(card)}\n")
        papel_anterior = r["papel"]

    cabeca = [
        f"# Chat com a IA do painel — {desde:%d/%m} a {ate:%d/%m/%Y}\n",
        f"{conta['alex']} mensagens tuas, {conta['ia']} da IA, {conta['cards']} cards. "
        f"Gerado em {datetime.now():%d/%m/%Y %H:%M}.\n",
        "Legenda: ⚠ = tua mensagem logo depois de uma resposta que parece correção/reclamação "
        "(só pista). Números longos e senhas aparecem como [oculto]. Cópia local, fora do git.\n",
    ]
    if not corpo:
        corpo = ["\n_(nenhuma mensagem nesse período)_\n"]
    return "".join(cabeca + corpo + _diagnostico(conn, desde, ate, ini, fim)), conta


def _diagnostico(conn, desde: date, ate: date, ini: str, fim: str) -> list[str]:
    """Medidas reais do aparelho no período (rotas/diagnostico.py): tela/barra e microfone."""
    existe = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'diagnostico_cliente'"
    ).fetchone()
    if not existe:
        return []
    linhas = []
    for r in conn.execute(
        "SELECT tipo, dados_json, criado_em FROM diagnostico_cliente WHERE criado_em >= ? AND criado_em < ? ORDER BY id",
        (ini, fim),
    ).fetchall():
        quando = hora_local(r["criado_em"])
        if quando is None or not (desde <= quando.date() <= ate):
            continue
        try:
            dados = json.loads(r["dados_json"])
        except ValueError:
            continue
        campos = " · ".join(f"{k}={v}" for k, v in dados.items())
        linhas.append(f"- {quando:%d/%m %H:%M} **{r['tipo']}**: {campos}\n")
    if not linhas:
        return []
    return [
        "\n## Diagnóstico do aparelho\n",
        "Medidas que o app mandou (tela/barra de abas e microfone). tela: `bruto` = fundo visível − onde a barra se prende (`ancora`), "
        "`aplicado` = quanto a barra desceu, `barraFundo` vs `vvH`/`innerH` = se ela "
        "cabe. mic: `evento` = o que falhou.\n",
        *linhas,
    ]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--dias", type=int, default=7, help="últimos N dias (padrão 7)")
    p.add_argument("--desde", type=date.fromisoformat)
    p.add_argument("--ate", type=date.fromisoformat)
    p.add_argument("--banco", type=Path, default=BANCO_PADRAO)
    p.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = p.parse_args(argv)

    try:
        from dotenv import load_dotenv

        load_dotenv(RAIZ / ".env")
    except ImportError:
        pass

    ate = args.ate or date.today()
    desde = args.desde or ate - timedelta(days=max(args.dias, 1) - 1)
    if desde > ate:
        print("--desde depois de --ate", file=sys.stderr)
        return 2
    if not args.banco.exists():
        print(f"banco não encontrado: {args.banco}", file=sys.stderr)
        return 1

    conn = abrir_so_leitura(args.banco)
    try:
        texto, conta = montar_copia(conn, desde, ate)
    finally:
        conn.close()
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(texto, encoding="utf-8")
    print(
        f"{conta['alex']} tuas + {conta['ia']} da IA ({conta['correcoes']} com ⚠) "
        f"de {desde:%d/%m} a {ate:%d/%m} -> {args.saida}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
