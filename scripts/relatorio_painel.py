#!/usr/bin/env python3
"""scripts/relatorio_painel.py - relatorio do painel inteiro pro Claude Code achar bug, erro e
"coisa que ainda nao sai como o Alex quer" (pedido dele, 2026-10-16).

Junta num markdown so (`data/relatorio_painel.md`, gitignored - tem coisa pessoal):
  1. o que olhar primeiro (sinais ordenados por peso);
  2. conversa: correcoes dele, vezes que a IA admitiu falha, mensagens repetidas, resposta que
     ele precisou refazer (reaproveita `ler_chat`);
  3. aparelho: erros de JavaScript, barra de abas fora da tela, microfone;
  4. servidor: erros de `data/erros_servidor.log` (log_erros.py) agrupados;
  5. dados: tarefas atrasadas/duplicadas, acoes que ele DESFEZ, avisos que ele ignorou, gasto sem
     categoria, custo de IA por funcao, cota do Maps/voz.

So LE o banco real (`mode=ro`), nunca grava e nunca importa app.py. Cada secao e independente:
tabela faltando ou erro numa nao derruba o resto.

Uso:
  .venv/Scripts/python.exe scripts/relatorio_painel.py            # ultimos 7 dias
  .venv/Scripts/python.exe scripts/relatorio_painel.py --dias 30
"""

import argparse
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ler_chat  # noqa: E402

BANCO_PADRAO = RAIZ / "data" / "painel.db"
LOG_PADRAO = RAIZ / "data" / "erros_servidor.log"
SAIDA_PADRAO = RAIZ / "data" / "relatorio_painel.md"

# A IA reconhecendo que algo nao deu certo - quem le decide se era bug de verdade.
_FALHA_IA = re.compile(
    r"nao consegui|nao deu (certo|pra)|deu erro|tive um (erro|problema)|falhou|desculp|me enganei|"
    r"errei|veio com o titulo antigo|confere no card|nao aparece|nao salvou|nao foi salv|"
    r"nao tenho (essa )?ferramenta|nao consigo (fazer|mexer|criar|alterar)"
)
_SO_HORARIO = re.compile(r"^\s*(as\s+)?\d{1,2}\s*([:h]\s*\d{0,2})?\s*(horas?)?\s*$", re.IGNORECASE)
_LINHA_LOG = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}),\d+ (WARNING|ERROR|CRITICAL) (\S+): (.*)$")


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", _sem_acento(t))).strip()


def _trecho(t: str, n: int = 110) -> str:
    t = ler_chat.ocultar_sensivel(t or "").replace("\n", " ").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


class Achado:
    """Um sinal do relatorio. `peso` ordena "o que olhar primeiro" (3 = quebrado, 2 = suspeito, 1 = ruido provavel)."""

    def __init__(self, peso: int, titulo: str, detalhe: str = ""):
        self.peso, self.titulo, self.detalhe = peso, titulo, detalhe


def _tabela_existe(conn, nome: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone())


def _local(criado_em):
    return ler_chat.hora_local(criado_em)


# ---------------------------------------------------------------- 2. conversa
def secao_conversa(conn, desde: date, ate: date) -> tuple[list[str], list[Achado]]:
    achados: list[Achado] = []
    if not _tabela_existe(conn, "chat_mensagens"):
        return ["_(sem tabela de chat)_\n"], achados
    margem_ini = (desde - timedelta(days=1)).isoformat()
    margem_fim = (ate + timedelta(days=2)).isoformat()
    linhas = []
    for r in conn.execute(
        "SELECT papel, texto, criado_em FROM chat_mensagens WHERE criado_em >= ? AND criado_em < ? ORDER BY criado_em, id",
        (margem_ini, margem_fim),
    ):
        quando = _local(r["criado_em"])
        if quando and desde <= quando.date() <= ate:
            linhas.append((quando, r["papel"], r["texto"] or ""))
    alex = [x for x in linhas if x[1] == "user"]
    ia = [x for x in linhas if x[1] != "user"]
    saida = [f"{len(alex)} mensagens dele, {len(ia)} da IA.\n\n"]

    correcoes, admissoes, repetidas, horarios = [], [], [], []
    for i, (quando, papel, texto) in enumerate(linhas):
        anterior = linhas[i - 1] if i else None
        if papel == "user":
            if anterior and anterior[1] != "user" and ler_chat.parece_correcao(texto):
                correcoes.append((quando, texto, anterior[2]))
            if anterior and anterior[1] != "user" and _SO_HORARIO.match(texto):
                horarios.append((quando, texto, anterior[2]))
            n = _norm(texto)
            if len(n) >= 6:
                for q2, p2, t2 in linhas[:i]:
                    if p2 == "user" and quando - q2 <= timedelta(hours=3) and _norm(t2) == n:
                        repetidas.append((quando, texto))
                        break
        elif _FALHA_IA.search(_sem_acento(texto)):
            admissoes.append((quando, texto))

    def lista(titulo, itens, formato, peso, o_que):
        if not itens:
            return
        saida.append(f"### {titulo} ({len(itens)})\n\n")
        saida.extend(formato(x) for x in itens[:12])
        if len(itens) > 12:
            saida.append(f"- … e mais {len(itens) - 12}\n")
        saida.append("\n")
        achados.append(Achado(peso, f"Conversa: {titulo.lower()} ({len(itens)})", o_que))

    lista("Ele corrigiu / reclamou", correcoes,
          lambda x: f"- {x[0]:%d/%m %H:%M} ele: “{_trecho(x[1])}” (depois de: “{_trecho(x[2], 80)}”)\n", 3,
          "mensagem dele logo depois de resposta da IA que parece correção - ler o contexto")
    lista("A IA admitiu falha", admissoes, lambda x: f"- {x[0]:%d/%m %H:%M} IA: “{_trecho(x[1], 140)}”\n", 3,
          "a própria IA disse que algo não deu certo")
    lista("Ele repetiu a mesma mensagem", repetidas, lambda x: f"- {x[0]:%d/%m %H:%M}: “{_trecho(x[1])}”\n", 2,
          "mesma frase em até 3 h - a primeira vez provavelmente não funcionou")
    lista("Só um horário solto depois de resposta", horarios,
          lambda x: f"- {x[0]:%d/%m %H:%M}: “{_trecho(x[1], 40)}” (depois de: “{_trecho(x[2], 90)}”)\n", 2,
          "conferir se a IA gravou esse horário na tarefa certa")
    if not (correcoes or admissoes or repetidas or horarios):
        saida.append("Nenhum sinal automático na conversa (isso não prova que está tudo certo - a cópia completa "
                     "está em `data/chat_para_claude.md`, gerada por `scripts/ler_chat.py`).\n")
    return saida, achados


# ---------------------------------------------------------------- 3. aparelho
def secao_aparelho(conn, desde: date, ate: date) -> tuple[list[str], list[Achado]]:
    import json

    achados: list[Achado] = []
    if not _tabela_existe(conn, "diagnostico_cliente"):
        return ["_(sem diagnóstico do aparelho)_\n"], achados
    ini = (desde - timedelta(days=1)).isoformat()
    fim = (ate + timedelta(days=2)).isoformat()
    por_tipo: Counter = Counter()
    erros_js: Counter = Counter()
    ultimo_js: dict = {}
    fora, ignoradas, mic = [], 0, Counter()
    for r in conn.execute("SELECT tipo, dados_json, criado_em FROM diagnostico_cliente WHERE criado_em >= ? AND criado_em < ? ORDER BY id", (ini, fim)):
        quando = _local(r["criado_em"])
        if not quando or not (desde <= quando.date() <= ate):
            continue
        try:
            d = json.loads(r["dados_json"])
        except ValueError:
            continue
        por_tipo[r["tipo"]] += 1
        if r["tipo"] == "erro_js":
            chave = (d.get("msg"), d.get("arq"), d.get("linha"))
            erros_js[chave] += 1
            ultimo_js[chave] = (quando, d.get("aba"))
        elif r["tipo"] == "tela":
            if d.get("motivo") == "ignorada":
                ignoradas += 1
            for k in ("barraFundo", "innerH"):
                if not isinstance(d.get(k), (int, float)):
                    break
            else:
                # o fundo visivel e vvTopo+vvH (teclado/barra de endereco empurram a janela visual)
                limite = d["innerH"]
                if isinstance(d.get("vvTopo"), (int, float)) and isinstance(d.get("vvH"), (int, float)):
                    limite = max(limite, d["vvTopo"] + d["vvH"])
                if d["barraFundo"] > limite + 2:
                    fora.append((quando, d))
        elif r["tipo"] == "mic":
            mic[d.get("evento") or "?"] += 1
    saida = [f"Registros: {', '.join(f'{t}={n}' for t, n in por_tipo.items()) or 'nenhum'}.\n\n"]
    if erros_js:
        saida.append(f"### Erros de JavaScript no aparelho ({sum(erros_js.values())} em {len(erros_js)} tipos)\n\n")
        for (msg, arq, linha), n in erros_js.most_common(10):
            q, aba = ultimo_js[(msg, arq, linha)]
            saida.append(f"- {n}x `{msg}` em `{arq}:{linha}` (aba {aba or '?'}, última {q:%d/%m %H:%M})\n")
        saida.append("\n")
        achados.append(Achado(3, f"Aparelho: {len(erros_js)} tipo(s) de erro de JavaScript", "ver a seção Aparelho"))
    if fora:
        saida.append(f"### Barra de abas fora da tela ({len(fora)} medidas)\n\n")
        for q, d in fora[-6:]:
            saida.append(f"- {q:%d/%m %H:%M} barraFundo={d['barraFundo']} > innerH={d['innerH']} (bruto={d.get('bruto')}, aplicado={d.get('aplicado')})\n")
        saida.append("\n")
        achados.append(Achado(3, f"Aparelho: barra de abas saiu da tela ({len(fora)}x)", "`init.js` _medirDesvioTela"))
    if ignoradas:
        saida.append(f"Medidas impossíveis da tela descartadas pela proteção: {ignoradas}.\n\n")
        achados.append(Achado(1, f"Aparelho: {ignoradas} medida(s) impossível(is) da tela descartada(s)", "a proteção funcionou; se forem muitas, o iOS está instável"))
    falhas_mic = {k: n for k, n in mic.items() if k not in ("ok", "gravou")}
    if falhas_mic:
        saida.append(f"### Microfone: {', '.join(f'{k}={n}' for k, n in falhas_mic.items())}\n\n")
        achados.append(Achado(2, "Aparelho: eventos de falha do microfone", ", ".join(f"{k}={n}" for k, n in falhas_mic.items())))
    if not (erros_js or fora or ignoradas or falhas_mic):
        saida.append("Nenhuma falha registrada pelo aparelho no período.\n")
    return saida, achados


# ---------------------------------------------------------------- 4. servidor
def secao_servidor(log: Path, desde: date, ate: date) -> tuple[list[str], list[Achado]]:
    achados: list[Achado] = []
    if not log.exists():
        return [f"_(ainda não há `{log.name}`: o registro de erros do servidor começou em 16/10/2026 e só "
                "vale depois de reiniciar o painel)_\n"], achados
    grupos: Counter = Counter()
    exemplo: dict = {}
    for arquivo in sorted(log.parent.glob(log.name + "*")):
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for linha in texto.splitlines():
            m = _LINHA_LOG.match(linha)
            if not m:
                continue
            dia = date.fromisoformat(m.group(1))
            if not (desde <= dia <= ate):
                continue
            msg = re.sub(r"\d+", "N", m.group(5))[:120]
            chave = (m.group(3), m.group(4), msg)
            grupos[chave] += 1
            exemplo[chave] = f"{m.group(1)} {m.group(2)}"
    if not grupos:
        return ["Nenhum WARNING/ERROR no período.\n"], achados
    saida = [f"{sum(grupos.values())} ocorrências em {len(grupos)} tipos:\n\n"]
    for (nivel, nome, msg), n in grupos.most_common(15):
        saida.append(f"- {n}x **{nivel}** `{nome}`: {msg} (última {exemplo[(nivel, nome, msg)]})\n")
        achados.append(Achado(3 if nivel != "WARNING" else 2, f"Servidor: {n}x {nivel} {nome}", msg))
    saida.append("\nTraceback completo: abrir `data/erros_servidor.log` na data indicada.\n")
    return saida, achados


# ---------------------------------------------------------------- 5. dados
def secao_dados(conn, desde: date, ate: date, hoje: date) -> tuple[list[str], list[Achado]]:
    achados: list[Achado] = []
    saida: list[str] = []

    def tenta(nome, fn):
        try:
            fn()
        except sqlite3.Error as e:
            saida.append(f"_({nome}: não deu pra ler - {e})_\n\n")

    def atrasadas():
        if not _tabela_existe(conn, "tasks"):
            return
        linhas = conn.execute(
            "SELECT title, due_date FROM tasks WHERE completed_at IS NULL AND due_date IS NOT NULL AND due_date < ? "
            "AND NOT (recorrencia IS NOT NULL AND due_date IS NULL) ORDER BY due_date", (hoje.isoformat(),)
        ).fetchall()
        saida.append(f"### Tarefas atrasadas ({len(linhas)})\n\n")
        if linhas:
            saida.extend(f"- {r['due_date']}: {_trecho(r['title'], 70)}\n" for r in linhas[:8])
            if len(linhas) > 8:
                saida.append(f"- … e mais {len(linhas) - 8}\n")
            muito = [r for r in linhas if (hoje - date.fromisoformat(r["due_date"])).days >= 14]
            achados.append(Achado(2 if muito else 1, f"Dados: {len(linhas)} tarefa(s) atrasada(s)"
                                  + (f", {len(muito)} há 14+ dias" if muito else ""), "decidir: fazer, mover ou apagar"))
        saida.append("\n")
        dup = Counter((_norm(r["title"]), r["due_date"]) for r in conn.execute(
            "SELECT title, due_date FROM tasks WHERE completed_at IS NULL"))
        repetidas = [(k, n) for k, n in dup.items() if n > 1 and k[0]]
        if repetidas:
            saida.append(f"### Tarefas duplicadas ({len(repetidas)})\n\n")
            saida.extend(f"- {n}x “{_trecho(k[0], 60)}” em {k[1]}\n" for k, n in repetidas[:8])
            saida.append("\n")
            achados.append(Achado(3, f"Dados: {len(repetidas)} tarefa(s) duplicada(s)", "o fluxo de criar tarefa duplicou"))

    def desfeitas():
        if not _tabela_existe(conn, "acoes_desfazer"):
            return
        n = 0
        for r in conn.execute("SELECT desfeito_em FROM acoes_desfazer WHERE desfeito_em IS NOT NULL"):
            q = _local(r["desfeito_em"])
            if q and desde <= q.date() <= ate:
                n += 1
        if n:
            saida.append(f"### Ações que ele desfez: {n}\n\nCada uma é algo que a IA fez e ele não queria "
                         "(ou fez errado). Ver na conversa o que foi pedido logo antes.\n\n")
            achados.append(Achado(2, f"Dados: {n} ação(ões) desfeita(s) por ele", "ver a conversa nesses horários"))

    def avisos():
        if not _tabela_existe(conn, "avisos_insistentes"):
            return
        ini = (desde - timedelta(days=1)).isoformat()
        linhas = conn.execute(
            "SELECT tipo, tentativas, aberto_em, encerrado_em, enviado_em FROM avisos_insistentes WHERE data >= ? AND data <= ?",
            (ini, ate.isoformat())).fetchall()
        if not linhas:
            return
        sem_abrir = [r for r in linhas if not r["aberto_em"]]
        insistiu = [r for r in linhas if (r["tentativas"] or 0) >= 3]
        por_tipo = Counter(r["tipo"] for r in sem_abrir)
        saida.append(f"### Avisos insistentes: {len(linhas)} enviados, {len(sem_abrir)} nunca vistos, "
                     f"{len(insistiu)} chegaram a 3+ tentativas\n\n")
        if por_tipo:
            saida.append("Nunca vistos por tipo (visto = tocou OU abriu o app; antes de 16/10/2026 só o toque contava): " + ", ".join(f"{t}={n}" for t, n in por_tipo.most_common(6)) + "\n\n")
        if linhas and len(sem_abrir) / len(linhas) >= 0.5 and len(linhas) >= 4:
            achados.append(Achado(2, f"Dados: {len(sem_abrir)}/{len(linhas)} avisos insistentes nunca vistos",
                                  "ele ignora esse tipo de aviso? ou não está chegando"))

    def gastos():
        if not _tabela_existe(conn, "expenses"):
            return
        n = conn.execute("SELECT COUNT(*) FROM expenses WHERE (category IS NULL OR TRIM(category) = '' OR category = 'outros') "
                         "AND date(created_at) >= ?", (desde.isoformat(),)).fetchone()[0]
        if n:
            saida.append(f"### Gastos sem categoria útil: {n}\n\n")
            achados.append(Achado(1, f"Dados: {n} gasto(s) sem categoria (ou 'outros')", "classificação pode estar fraca"))

    def custo():
        if not _tabela_existe(conn, "api_usage"):
            return
        linhas = conn.execute(
            "SELECT feature, COUNT(*) n, ROUND(SUM(cost_usd), 3) usd FROM api_usage WHERE date(created_at) >= ? GROUP BY feature ORDER BY usd DESC",
            (desde.isoformat(),)).fetchall()
        if linhas:
            total = sum(r["usd"] or 0 for r in linhas)
            saida.append(f"### Custo de IA no período: US$ {total:.2f}\n\n")
            saida.extend(f"- {r['feature'] or '?'}: {r['n']} chamadas, US$ {r['usd']}\n" for r in linhas[:6])
            saida.append("\n")

    def cotas():
        partes = []
        if _tabela_existe(conn, "uso_maps"):
            mes = hoje.strftime("%Y-%m")
            partes += [f"Maps {r['nivel']}={r['chamadas']}" for r in conn.execute("SELECT nivel, chamadas FROM uso_maps WHERE mes = ?", (mes,))]
        if _tabela_existe(conn, "voz_uso"):
            r = conn.execute("SELECT caracteres FROM voz_uso WHERE mes = ?", (hoje.strftime("%Y-%m"),)).fetchone()
            if r:
                partes.append(f"voz={r['caracteres']} caracteres")
        if partes:
            saida.append("Cotas do mês: " + ", ".join(partes) + ".\n\n")

    for nome, fn in (("atrasadas", atrasadas), ("desfeitas", desfeitas), ("avisos", avisos), ("gastos", gastos),
                     ("custo", custo), ("cotas", cotas)):
        tenta(nome, fn)
    if not saida:
        saida.append("Nada de anormal nos dados.\n")
    return saida, achados


# ---------------------------------------------------------------- montagem
def montar(conn, log: Path, desde: date, ate: date, hoje: date | None = None) -> tuple[str, list[Achado]]:
    hoje = hoje or date.today()
    todas: list[Achado] = []
    blocos = []
    for titulo, (texto, achados) in (
        ("Conversa", secao_conversa(conn, desde, ate)),
        ("Aparelho (celular)", secao_aparelho(conn, desde, ate)),
        ("Servidor", secao_servidor(log, desde, ate)),
        ("Dados", secao_dados(conn, desde, ate, hoje)),
    ):
        blocos.append(f"\n## {titulo}\n\n" + "".join(texto))
        todas += achados
    todas.sort(key=lambda a: -a.peso)
    topo = [f"# Relatório do painel — {desde:%d/%m} a {ate:%d/%m/%Y}\n\n",
            f"Gerado em {datetime.now():%d/%m/%Y %H:%M}. Cópia local, fora do git (tem coisa pessoal). "
            "Os sinais são **pistas automáticas**: conferir no código e na conversa antes de afirmar que é bug.\n\n",
            "## O que olhar primeiro\n\n"]
    if todas:
        nomes = {3: "quebrado", 2: "suspeito", 1: "provável ruído"}
        topo += [f"{i}. **[{nomes[a.peso]}]** {a.titulo}" + (f" — {a.detalhe}" if a.detalhe else "") + "\n" for i, a in enumerate(todas, 1)]
    else:
        topo.append("Nenhum sinal automático. Isso não prova que está tudo certo: ler a conversa completa.\n")
    return "".join(topo) + "".join(blocos), todas


def abrir_so_leitura(caminho: Path) -> sqlite3.Connection:
    return ler_chat.abrir_so_leitura(caminho)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--dias", type=int, default=7, help="últimos N dias (padrão 7)")
    p.add_argument("--desde", type=date.fromisoformat)
    p.add_argument("--ate", type=date.fromisoformat)
    p.add_argument("--banco", type=Path, default=BANCO_PADRAO)
    p.add_argument("--log", type=Path, default=LOG_PADRAO)
    p.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = p.parse_args(argv)

    ate = args.ate or date.today()
    desde = args.desde or ate - timedelta(days=max(args.dias, 1) - 1)
    if desde > ate:
        print("--desde depois de --ate", file=sys.stderr)
        return 2
    if not args.banco.exists():
        print(f"banco não encontrado: {args.banco}", file=sys.stderr)
        return 1
    try:
        from dotenv import load_dotenv

        load_dotenv(RAIZ / ".env")
    except ImportError:
        pass
    conn = abrir_so_leitura(args.banco)
    try:
        texto, achados = montar(conn, args.log, desde, ate)
    finally:
        conn.close()
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(texto, encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    contagem = Counter(a.peso for a in achados)
    print(f"{len(achados)} sinais ({contagem[3]} quebrado, {contagem[2]} suspeito, {contagem[1]} ruído) "
          f"de {desde:%d/%m} a {ate:%d/%m} -> {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
