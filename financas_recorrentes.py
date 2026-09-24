"""Faixa N1 (Fase 7): assinaturas e compras parceladas, declaradas a mao.

Modulo de CRUD + calculo PURO, sem IA (a extracao de parametros do texto
livre fica em `classificador_local/regras/n1_financas.py`; este modulo nunca
sabe de frase nenhuma). Tabelas: `assinatura`, `compra_parcelada`
(migracao `migracoes/202609241300_n1_assinaturas.sql`). Contrato completo
(JSON de rota e de card) em `docs/contrato-assinaturas.md`.

Relacao com o que ja existe (nao duplica, ver o contrato pra mais detalhe):
- `gastos.detectar_gastos_recorrentes` DETECTA recorrencia observando o
  HISTORICO de gasto/extrato - nao sabe de "assinatura" como conceito, so
  percebe um padrao depois dele acontecer 2+ vezes. As tabelas daqui sao
  DECLARADAS pelo Alex (ou pelo classificador local) ANTES/no momento da
  contratacao - a fonte é diferente (intencao declarada x observacao),
  entao os dois convivem sem se sobrepor.
- `bank_accounts.limite` (US-E15, `vida.fracao_limite_cartao`) e o limite
  MANUAL de cada cartao. `impacto_limite_cartao_proximos_meses` (abaixo)
  cruza a soma das assinaturas/parcelas com esse limite pra projetar o
  impacto futuro - reusa `vida.fracao_limite_cartao`, nao reimplementa a
  conta de fracao.

Dinheiro: soma-se tudo em `Decimal` (evita deriva de ponto flutuante ao
somar varias assinaturas/parcelas) e converte pra `float` arredondado a 2
casas só na saida de cada funcao - mesma convencao de "valor sempre numero"
do resto do contrato de card (`docs/CARDS.md`). `calculos.py` (faixa A13)
ainda nao chegou na integracao (`fase7/integracao`) quando este modulo foi
escrito; quando chegar, e o helper de dinheiro dele for equivalente, trocar
essas funcoes locais por ele fica pra uma faixa de integracao futura (nao
percebi diferenca de comportamento que justificasse esperar).
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import vida  # NOMES_MES, somar_meses, fracao_limite_cartao (reuso, nao duplicacao)

try:
    import db  # buscar_conta_por_nome (cartao citado -> bank_accounts, se existir)
except ImportError:  # pragma: no cover - so em teste isolado sem o pacote inteiro
    db = None

try:
    import criptografia
except ImportError:  # pragma: no cover - so em teste isolado sem o pacote inteiro
    criptografia = None


def _cripto(texto: str) -> str:
    return criptografia.criptografar(texto) if criptografia else texto


def _decripto(valor: str) -> str:
    return criptografia.descriptografar(valor) if criptografia else valor


# ---- dinheiro (Decimal interno, float na borda) -----------------------------


def _d(valor) -> Decimal:
    """Converte pra Decimal SEM passar por float (str(valor) evita o erro de
    representacao binaria que `Decimal(0.1)` teria). C1: entrada que nao e
    numero finito (texto, bool, NaN, infinito) vira ValueError - antes subia
    decimal.InvalidOperation e a rota respondia 500."""
    if isinstance(valor, Decimal):
        d = valor
    else:
        if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
            raise ValueError("valor precisa ser um numero")
        try:
            d = Decimal(str(valor).strip())
        except (ArithmeticError, ValueError):
            raise ValueError(f"valor invalido: {str(valor)[:40]!r}") from None
    if not d.is_finite():
        raise ValueError("valor precisa ser um numero finito")
    return d


# C1: teto de sanidade pra valor digitado (acima disso e erro de digitacao, e
# um valor gigante quebrava o arredondamento com InvalidOperation -> 500) e
# pro numero de parcelas (40 anos; com 100000 a data da ultima parcela passava
# do ano 9999 e a listagem inteira quebrava).
VALOR_MAXIMO = Decimal("1000000000")
N_PARCELAS_MAX = 480


def _valor_entrada(valor, campo: str) -> Decimal:
    d = _d(valor)
    if d <= 0:
        raise ValueError(f"{campo} precisa ser positivo")
    if d > VALOR_MAXIMO:
        raise ValueError(f"{campo} grande demais")
    return d


def _data_entrada(texto, campo: str) -> str:
    """Data ISO (AAAA-MM-DD) valida, entre 1900 e 2200 - C1: antes gravava
    qualquer texto e a listagem quebrava depois (500 em toda leitura)."""
    if not isinstance(texto, str):
        raise ValueError(f"{campo} precisa ser uma data AAAA-MM-DD")
    try:
        d = date.fromisoformat(texto.strip()[:10])
    except ValueError:
        raise ValueError(f"{campo} invalida (use AAAA-MM-DD)") from None
    if not (1900 <= d.year <= 2200):
        raise ValueError(f"{campo} fora do intervalo")
    return d.isoformat()


def _money(valor: Decimal) -> float:
    return float(valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ---- datas --------------------------------------------------------------


def _dia_no_mes(ano: int, mes: int, dia: int) -> date:
    """Crava no ultimo dia do mes quando `dia` nao existir nele (ex: 31 em
    fevereiro vira 28 ou 29) - mesma decisao de `vida.somar_meses`."""
    return date(ano, mes, min(dia, monthrange(ano, mes)[1]))


def _mes_seguinte(ano: int, mes: int) -> tuple[int, int]:
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def _diferenca_em_meses(inicio: date, fim: date) -> int:
    """Quantos meses de `inicio` (dia 1) ate `fim` (dia 1) - negativo se
    `fim` for antes de `inicio`."""
    return (fim.year - inicio.year) * 12 + (fim.month - inicio.month)


def _ano_mes(d: date) -> str:
    return d.strftime("%Y-%m")


def nome_mes_ano(d: date) -> str:
    return f"{vida.NOMES_MES[d.month - 1]} de {d.year}"


# =============================================================================
# Assinatura - CRUD
# =============================================================================


def criar_assinatura(
    conn: sqlite3.Connection,
    nome: str,
    valor,
    dia_cobranca: int,
    *,
    cartao_ou_forma: str | None = None,
    categoria: str | None = None,
    inicio: str | None = None,
    observacao: str | None = None,
    hoje: date | None = None,
) -> int:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("nome da assinatura vazio")
    valor_dec = _valor_entrada(valor, "valor da assinatura")
    if isinstance(dia_cobranca, bool) or not isinstance(dia_cobranca, int) or not (1 <= dia_cobranca <= 31):
        raise ValueError("dia_cobranca precisa ser um inteiro entre 1 e 31")
    inicio = _data_entrada(inicio, "inicio") if inicio else (hoje or date.today()).isoformat()
    cur = conn.execute(
        """INSERT INTO assinatura
           (nome, valor, dia_cobranca, cartao_ou_forma, categoria, ativa, inicio, observacao)
           VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
        (nome, _money(valor_dec), dia_cobranca, cartao_ou_forma, categoria, inicio, observacao),
    )
    conn.commit()
    return cur.lastrowid


def obter_assinatura(conn: sqlite3.Connection, id_: int) -> dict | None:
    row = conn.execute("SELECT * FROM assinatura WHERE id = ?", (id_,)).fetchone()
    return dict(row) if row else None


def listar_assinaturas(conn: sqlite3.Connection, apenas_ativas: bool = False) -> list[dict]:
    sql = "SELECT * FROM assinatura"
    if apenas_ativas:
        sql += " WHERE ativa = 1"
    sql += " ORDER BY nome COLLATE NOCASE"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def buscar_assinatura_por_nome(conn: sqlite3.Connection, nome: str, apenas_ativas: bool = True) -> dict | None:
    """Acha por nome parecido (LIKE, sem diferenciar maiusculas) - prefere
    combinacao exata quando existir, senao a mais recente que contem o
    texto. Nunca inventa: sem nada parecido, devolve None."""
    nome = (nome or "").strip()
    if not nome:
        return None
    sql = "SELECT * FROM assinatura WHERE nome LIKE ?"
    params: list = [f"%{nome}%"]
    if apenas_ativas:
        sql += " AND ativa = 1"
    sql += " ORDER BY (LOWER(nome) = LOWER(?)) DESC, id DESC LIMIT 1"
    params.append(nome)
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def atualizar_assinatura(conn: sqlite3.Connection, id_: int, **campos) -> bool:
    """Atualiza so os campos editaveis presentes em `campos` (nome, valor,
    dia_cobranca, cartao_ou_forma, categoria, observacao). Ignora chave
    desconhecida em vez de falhar (corpo de request pode trazer lixo)."""
    editaveis = {"nome", "valor", "dia_cobranca", "cartao_ou_forma", "categoria", "observacao"}
    campos_validos = {k: v for k, v in campos.items() if k in editaveis and v is not None}
    if "valor" in campos_validos:
        campos_validos["valor"] = _money(_valor_entrada(campos_validos["valor"], "valor da assinatura"))
    if "dia_cobranca" in campos_validos:
        dia = campos_validos["dia_cobranca"]
        if isinstance(dia, bool) or not isinstance(dia, int) or not (1 <= dia <= 31):
            raise ValueError("dia_cobranca precisa ser um inteiro entre 1 e 31")
    if "nome" in campos_validos:
        campos_validos["nome"] = str(campos_validos["nome"]).strip()
        if not campos_validos["nome"]:
            raise ValueError("nome da assinatura vazio")
    if not campos_validos:
        return False
    set_sql = ", ".join(f"{k} = ?" for k in campos_validos)
    cur = conn.execute(f"UPDATE assinatura SET {set_sql} WHERE id = ?", (*campos_validos.values(), id_))
    conn.commit()
    return cur.rowcount > 0


def cancelar_assinatura(conn: sqlite3.Connection, id_: int, hoje: date | None = None) -> bool:
    hoje = hoje or date.today()
    cur = conn.execute(
        "UPDATE assinatura SET ativa = 0, cancelada_em = ? WHERE id = ? AND ativa = 1",
        (hoje.isoformat(), id_),
    )
    conn.commit()
    return cur.rowcount > 0


def reativar_assinatura(conn: sqlite3.Connection, id_: int) -> bool:
    """Usado pelo Desfazer de um cancelamento - volta pro estado ativo."""
    cur = conn.execute(
        "UPDATE assinatura SET ativa = 1, cancelada_em = NULL WHERE id = ? AND ativa = 0", (id_,)
    )
    conn.commit()
    return cur.rowcount > 0


def excluir_assinatura(conn: sqlite3.Connection, id_: int) -> bool:
    cur = conn.execute("DELETE FROM assinatura WHERE id = ?", (id_,))
    conn.commit()
    return cur.rowcount > 0


# =============================================================================
# Compra parcelada - CRUD
# =============================================================================


def criar_compra_parcelada(
    conn: sqlite3.Connection,
    descricao: str,
    n_parcelas: int,
    *,
    valor_total=None,
    valor_parcela=None,
    cartao: str | None = None,
    primeira_parcela: str | None = None,
    categoria: str | None = None,
    hoje: date | None = None,
) -> int:
    """Precisa de `n_parcelas` + (`valor_total` OU `valor_parcela`) - o que
    faltar e derivado do outro (arredondado a 2 casas; a ultima parcela
    absorve a diferenca de arredondamento na hora do calculo, nunca aqui:
    ver `parcela_info`)."""
    descricao = (descricao or "").strip()
    if not descricao:
        raise ValueError("descricao da compra parcelada vazia")
    if isinstance(n_parcelas, bool) or not isinstance(n_parcelas, int) or n_parcelas <= 0:
        raise ValueError("n_parcelas precisa ser um inteiro positivo")
    if n_parcelas > N_PARCELAS_MAX:
        raise ValueError(f"n_parcelas no maximo {N_PARCELAS_MAX}")
    if valor_total is None and valor_parcela is None:
        raise ValueError("informe valor_total ou valor_parcela")
    if valor_parcela is not None:
        valor_parcela_dec = _valor_entrada(valor_parcela, "valor_parcela")
        valor_total_dec = (_valor_entrada(valor_total, "valor_total") if valor_total is not None
                           else valor_parcela_dec * n_parcelas)
    else:
        valor_total_dec = _valor_entrada(valor_total, "valor_total")
        valor_parcela_dec = valor_total_dec / n_parcelas
    if valor_total_dec > VALOR_MAXIMO * N_PARCELAS_MAX:
        raise ValueError("valor_total grande demais")
    primeira_parcela = (_data_entrada(primeira_parcela, "primeira_parcela") if primeira_parcela
                        else (hoje or date.today()).isoformat())
    cur = conn.execute(
        """INSERT INTO compra_parcelada
           (descricao, valor_total, n_parcelas, parcela_atual, valor_parcela, cartao, primeira_parcela, categoria)
           VALUES (?, ?, ?, 1, ?, ?, ?, ?)""",
        (
            descricao,
            _money(valor_total_dec),
            n_parcelas,
            _money(valor_parcela_dec),
            cartao,
            primeira_parcela,
            categoria,
        ),
    )
    conn.commit()
    return cur.lastrowid


def obter_compra_parcelada(conn: sqlite3.Connection, id_: int) -> dict | None:
    row = conn.execute("SELECT * FROM compra_parcelada WHERE id = ?", (id_,)).fetchone()
    return dict(row) if row else None


def listar_compras_parceladas(conn: sqlite3.Connection, apenas_em_andamento: bool = False, hoje: date | None = None) -> list[dict]:
    rows = [dict(r) for r in conn.execute("SELECT * FROM compra_parcelada ORDER BY primeira_parcela DESC").fetchall()]
    if not apenas_em_andamento:
        return rows
    hoje = hoje or date.today()
    return [r for r in rows if not parcela_info(r, hoje)["quitada"]]


def buscar_compra_parcelada_por_descricao(conn: sqlite3.Connection, descricao: str) -> dict | None:
    descricao = (descricao or "").strip()
    if not descricao:
        return None
    row = conn.execute(
        "SELECT * FROM compra_parcelada WHERE descricao LIKE ? "
        "ORDER BY (LOWER(descricao) = LOWER(?)) DESC, id DESC LIMIT 1",
        (f"%{descricao}%", descricao),
    ).fetchone()
    return dict(row) if row else None


def excluir_compra_parcelada(conn: sqlite3.Connection, id_: int) -> bool:
    cur = conn.execute("DELETE FROM compra_parcelada WHERE id = ?", (id_,))
    conn.commit()
    return cur.rowcount > 0


# =============================================================================
# Calculos derivados (por codigo, sem IA)
# =============================================================================


def parcela_info(compra: dict, hoje: date | None = None) -> dict:
    """Progresso CANONICO da compra, recalculado a partir da data (nao da
    coluna `parcela_atual`, que e so informativa/editavel a mao - ver o
    comentario da migracao). Granularidade de MES, de proposito: dentro do
    mes em que uma parcela cobra, "parcela_atual_calculada" e "quitada" nao
    mudam dependendo do dia exato (o dia so entra pra calcular a DATA de
    `proxima_cobranca`) - assim a compra fica "em andamento" o mes INTEIRO
    da ultima parcela (inclusive no proprio dia em que ela cobra), so
    virando `quitada` a partir do mes seguinte. Devolve:
    - `parcela_atual_calculada` (1..n_parcelas)
    - `parcelas_pagas` (parcelas de meses estritamente anteriores ao mes
      atual - nunca inclui a do mes corrente, mesmo se o dia de cobranca
      dela ja passou)
    - `parcelas_restantes` (n_parcelas - parcelas_pagas; inclui a do mes
      corrente enquanto nao quitada)
    - `mes_termino` ("AAAA-MM" do mes da ultima parcela) e `mes_termino_nome`
    - `quitada` (bool): true a partir do mes SEGUINTE ao da ultima parcela
    - `proxima_cobranca` (data ISO da parcela do mes corrente, cravada no
      fim do mes quando o dia de `primeira_parcela` nao existir nele; None
      se quitada)
    """
    hoje = hoje or date.today()
    primeira = date.fromisoformat(compra["primeira_parcela"])
    n_parcelas = int(compra["n_parcelas"])
    idx = _diferenca_em_meses(date(primeira.year, primeira.month, 1), date(hoje.year, hoje.month, 1))
    idx = max(idx, 0)

    quitada = idx >= n_parcelas
    parcela_atual_calculada = n_parcelas if quitada else idx + 1
    parcelas_pagas = n_parcelas if quitada else idx
    parcelas_restantes = n_parcelas - parcelas_pagas

    ano_termino, mes_termino_num = primeira.year, primeira.month
    for _ in range(n_parcelas - 1):
        ano_termino, mes_termino_num = _mes_seguinte(ano_termino, mes_termino_num)
    mes_termino_data = date(ano_termino, mes_termino_num, 1)

    proxima_cobranca = None
    if not quitada:
        ano_p, mes_p = primeira.year, primeira.month
        for _ in range(idx):
            ano_p, mes_p = _mes_seguinte(ano_p, mes_p)
        proxima_cobranca = _dia_no_mes(ano_p, mes_p, primeira.day).isoformat()

    return {
        "parcela_atual_calculada": parcela_atual_calculada,
        "parcelas_pagas": parcelas_pagas,
        "parcelas_restantes": parcelas_restantes,
        "mes_termino": _ano_mes(mes_termino_data),
        "mes_termino_nome": nome_mes_ano(mes_termino_data),
        "quitada": quitada,
        "proxima_cobranca": proxima_cobranca,
    }


def _assinatura_cobra_no_mes(assinatura: dict, ano: int, mes: int) -> bool:
    """Verdadeiro se a assinatura ja tinha comecado (`inicio`) e ainda nao
    tinha cancelado (`cancelada_em`) na cobranca daquele mes (dia_cobranca,
    cravado no fim do mes quando nao existir)."""
    data_cobranca = _dia_no_mes(ano, mes, assinatura["dia_cobranca"])
    inicio = date.fromisoformat(assinatura["inicio"])
    if data_cobranca < inicio:
        return False
    cancelada_em = assinatura.get("cancelada_em")
    if cancelada_em:
        if date.fromisoformat(cancelada_em) < data_cobranca:
            return False
    return True


def _compra_cobra_no_mes(compra: dict, ano: int, mes: int) -> bool:
    primeira = date.fromisoformat(compra["primeira_parcela"])
    if (ano, mes) < (primeira.year, primeira.month):
        return False
    meses_ate_o_mes = _diferenca_em_meses(date(primeira.year, primeira.month, 1), date(ano, mes, 1))
    return 0 <= meses_ate_o_mes < int(compra["n_parcelas"])


def total_mensal_comprometido(conn: sqlite3.Connection, hoje: date | None = None) -> dict:
    """Total comprometido no mes de `hoje`: assinaturas que cobraram
    nesse mes (`_assinatura_cobra_no_mes` ja decide isso olhando `inicio`/
    `cancelada_em` - por isso lista TODAS, nao so `ativa=1`: uma assinatura
    cancelada NO MEIO do mes ainda cobrou antes de cancelar, entao ainda
    entra no total daquele mes) + parcelas de compras ainda em andamento
    nesse mes. Base do aviso "custos fixos ja comprometem X%" (ver
    `valor_para_aviso_custos_fixos`) e da tela do cartao
    (`GET /api/financas/comprometido`)."""
    hoje = hoje or date.today()
    assinaturas = listar_assinaturas(conn, apenas_ativas=False)
    compras = listar_compras_parceladas(conn)

    total_assinaturas = Decimal("0")
    detalhe_assinaturas = []
    for a in assinaturas:
        if _assinatura_cobra_no_mes(a, hoje.year, hoje.month):
            valor = _d(a["valor"])
            total_assinaturas += valor
            detalhe_assinaturas.append({"id": a["id"], "nome": a["nome"], "valor": _money(valor)})

    total_parcelas = Decimal("0")
    detalhe_parcelas = []
    for c in compras:
        if _compra_cobra_no_mes(c, hoje.year, hoje.month):
            valor = _d(c["valor_parcela"])
            total_parcelas += valor
            info = parcela_info(c, hoje)
            detalhe_parcelas.append(
                {
                    "id": c["id"],
                    "descricao": c["descricao"],
                    "valor_parcela": _money(valor),
                    "parcela_atual": info["parcela_atual_calculada"],
                    "n_parcelas": c["n_parcelas"],
                }
            )

    total = total_assinaturas + total_parcelas
    return {
        "mes": _ano_mes(hoje),
        "assinaturas_total": _money(total_assinaturas),
        "parcelas_total": _money(total_parcelas),
        "total": _money(total),
        "detalhe_assinaturas": detalhe_assinaturas,
        "detalhe_parcelas": detalhe_parcelas,
    }


def valor_para_aviso_custos_fixos(conn: sqlite3.Connection, hoje: date | None = None) -> float:
    """O numero que alimenta o aviso ja existente "custos fixos ja
    comprometem X%" (`notificacoes.mes_seguinte_apertado`, que hoje soma so
    `gastos.total_gasto_fixo_mensal`). O integrador liga assim, SEM duplicar
    o calculo de fracao/limiar que ja existe la:

        custos_fixos = gastos.total_gasto_fixo_mensal(recorrentes)
        custos_fixos += financas_recorrentes.valor_para_aviso_custos_fixos(conn, hoje)
        fracao = custos_fixos / renda_media

    Projeta pro MES SEGUINTE (mesmo mes que `mes_seguinte_apertado` projeta),
    nao pro mes corrente - e por isso que esta funcao existe em vez do
    chamador so usar `total_mensal_comprometido(conn, hoje)["total"]` direto."""
    hoje = hoje or date.today()
    proximo_mes = vida.somar_meses(hoje.replace(day=1), 1)
    return total_mensal_comprometido(conn, proximo_mes)["total"]


def proximas_cobrancas(conn: sqlite3.Connection, hoje: date | None = None, limite: int = 20) -> list[dict]:
    """Assinaturas ativas + parcelas em andamento, ordenadas pela proxima
    cobranca (mais perto primeiro). `dias` e o numero de dias corridos ate
    la (0 = hoje); `label` e o mesmo dado em texto ("hoje", "amanha", "em N
    dias" - a frase pedida no prompt da faixa)."""
    hoje = hoje or date.today()
    itens = []

    for a in listar_assinaturas(conn, apenas_ativas=True):
        proxima = proxima_cobranca_assinatura(a, hoje)
        if proxima is None:
            continue
        dias = (proxima - hoje).days
        itens.append(
            {
                "tipo": "assinatura",
                "id": a["id"],
                "nome": a["nome"],
                "valor": _money(_d(a["valor"])),
                "data": proxima.isoformat(),
                "dias": dias,
                "label": _label_dias(dias),
                "cartao_ou_forma": a["cartao_ou_forma"],
            }
        )

    for c in listar_compras_parceladas(conn, apenas_em_andamento=True, hoje=hoje):
        info = parcela_info(c, hoje)
        if info["proxima_cobranca"] is None:
            continue
        proxima = date.fromisoformat(info["proxima_cobranca"])
        dias = (proxima - hoje).days
        itens.append(
            {
                "tipo": "compra_parcelada",
                "id": c["id"],
                "descricao": c["descricao"],
                "valor": _money(_d(c["valor_parcela"])),
                "data": proxima.isoformat(),
                "dias": dias,
                "label": _label_dias(dias),
                "parcela_atual": info["parcela_atual_calculada"],
                "n_parcelas": c["n_parcelas"],
                "cartao": c["cartao"],
            }
        )

    itens.sort(key=lambda i: (i["dias"], i.get("nome") or i.get("descricao") or ""))
    return itens[:limite]


def proxima_cobranca_assinatura(assinatura: dict, hoje: date) -> date | None:
    inicio = date.fromisoformat(assinatura["inicio"])
    candidata = _dia_no_mes(hoje.year, hoje.month, assinatura["dia_cobranca"])
    if candidata < hoje or candidata < inicio:
        ano, mes = _mes_seguinte(hoje.year, hoje.month)
        candidata = _dia_no_mes(ano, mes, assinatura["dia_cobranca"])
    return candidata


def _label_dias(dias: int) -> str:
    if dias <= 0:
        return "hoje" if dias == 0 else "atrasada"
    if dias == 1:
        return "amanhã"
    return f"em {dias} dias"


def impacto_limite_cartao_proximos_meses(conn: sqlite3.Connection, hoje: date | None = None, meses: int = 6) -> list[dict]:
    """Pra cada cartao citado (em `assinatura.cartao_ou_forma` ou
    `compra_parcelada.cartao`), projeta os proximos `meses` meses: quanto
    das assinaturas/parcelas cai naquele cartao e a fracao do limite
    manual (`bank_accounts.limite`, US-E15) que isso representa - reusa
    `vida.fracao_limite_cartao`, nao reimplementa a conta.

    Importante (documentar tambem no card, `docs/contrato-assinaturas.md`):
    isso soma SO o que esta faixa conhece (assinatura + parcela). Nao inclui
    outros gastos no mesmo cartao vindos de `expenses`/`bank_transactions` -
    a fracao aqui e um PISO do quanto o cartao ja vai estar comprometido,
    nao o total gasto nele. Lista TODAS as assinaturas (nao so `ativa=1`),
    mesma razao de `total_mensal_comprometido`: uma cancelada no meio do
    mes corrente ainda pode ter cobrado antes de cancelar."""
    hoje = hoje or date.today()
    assinaturas = listar_assinaturas(conn, apenas_ativas=False)
    compras = listar_compras_parceladas(conn)

    nomes_cartao = sorted(
        {(a.get("cartao_ou_forma") or "").strip() for a in assinaturas if a.get("cartao_ou_forma")}
        | {(c.get("cartao") or "").strip() for c in compras if c.get("cartao")}
    )

    resultado = []
    ano_base, mes_base = hoje.year, hoje.month
    for cartao in nomes_cartao:
        conta = db.buscar_conta_por_nome(conn, cartao) if db else None
        limite = conta.get("limite") if conta else None
        meses_projetados = []
        ano, mes = ano_base, mes_base
        for _ in range(meses):
            total = Decimal("0")
            for a in assinaturas:
                if (a.get("cartao_ou_forma") or "").strip().lower() == cartao.lower() and _assinatura_cobra_no_mes(a, ano, mes):
                    total += _d(a["valor"])
            for c in compras:
                if (c.get("cartao") or "").strip().lower() == cartao.lower() and _compra_cobra_no_mes(c, ano, mes):
                    total += _d(c["valor_parcela"])
            fracao_info = vida.fracao_limite_cartao(float(total), limite)
            meses_projetados.append(
                {
                    "mes": f"{ano:04d}-{mes:02d}",
                    "total": _money(total),
                    "fracao": fracao_info["fracao"] if fracao_info else None,
                    "sobra": fracao_info["sobra"] if fracao_info else None,
                }
            )
            ano, mes = _mes_seguinte(ano, mes)
        resultado.append({"cartao": cartao, "limite": limite, "meses": meses_projetados})
    return resultado


# =============================================================================
# Desfazer (mecanismo local desta faixa - ver nota abaixo)
# =============================================================================
#
# O Desfazer geral (US-E5, docs/CARDS.md) grava o token com `db.criar_acao_
# desfazer` e aplica com `app._desfazer_itens`/`POST /api/desfazer/<token>`.
# Nenhum dos dois arquivos (`db.py`, `app.py`) esta na lista de arquivos
# desta faixa, e `db.ENTIDADES_DESFAZIVEIS` ainda nao conhece "assinatura"/
# "compra_parcelada" - adicionar essas duas entidades la e no `app.py` fica
# pra quem integrar esta faixa (anotado em `progress.txt`). Ate isso
# acontecer, o classificador local usa este mecanismo PARALELO, que grava
# na MESMA tabela `acoes_desfazer` (schema generico e ja existente: token,
# itens_json, criado_em, desfeito_em) e e aplicado pela rota propria desta
# faixa (`POST /api/financas/desfazer/<token>`, `rotas/n1_financas.py`) -
# nunca pela rota generica. O formato do token no card (`{"tipo": "desfazer",
# "token": ...}`) e o mesmo, entao o front nao precisa saber da diferenca; a
# unica coisa que muda e qual rota o botao chama (documentado em
# `docs/contrato-assinaturas.md`).


def criar_token_desfazer(conn: sqlite3.Connection, entidade: str, acao: str, id_: int) -> str:
    if entidade not in ("assinatura", "compra_parcelada"):
        raise ValueError(f"entidade desconhecida pro desfazer local: {entidade!r}")
    item = {"entidade": entidade, "acao": acao, "id": id_}
    token = secrets.token_urlsafe(16)
    conn.execute(
        "INSERT INTO acoes_desfazer (token, itens_json) VALUES (?, ?)",
        (token, _cripto(json.dumps([item], ensure_ascii=False))),
    )
    conn.commit()
    return token


def aplicar_desfazer(conn: sqlite3.Connection, token: str) -> dict:
    """Mesmo formato de resposta do Desfazer geral (docs/CARDS.md): `status`
    200 com `{"ok": True, "desfeitos": n}`, 404 (token desconhecido/de outra
    faixa) ou 409 (ja desfeito)."""
    row = conn.execute("SELECT * FROM acoes_desfazer WHERE token = ?", (token,)).fetchone()
    if not row:
        return {"status": 404, "erro": "token desconhecido"}
    if row["desfeito_em"]:
        return {"status": 409, "erro": "ja desfeito"}
    try:
        itens = json.loads(_decripto(row["itens_json"]) or "[]")
    except (TypeError, ValueError):
        itens = []
    item = itens[0] if itens else {}
    if item.get("entidade") not in ("assinatura", "compra_parcelada") or not isinstance(item.get("id"), int):
        # token de outra faixa (Desfazer geral) - nao e nosso pra desfazer
        return {"status": 404, "erro": "token desconhecido"}

    desfeitos = 0
    if item["entidade"] == "assinatura":
        if item["acao"] == "criar":
            desfeitos = int(excluir_assinatura(conn, item["id"]))
        elif item["acao"] == "cancelar":
            desfeitos = int(reativar_assinatura(conn, item["id"]))
    elif item["entidade"] == "compra_parcelada" and item["acao"] == "criar":
        desfeitos = int(excluir_compra_parcelada(conn, item["id"]))

    conn.execute("UPDATE acoes_desfazer SET desfeito_em = datetime('now') WHERE token = ?", (token,))
    conn.commit()
    return {"status": 200, "ok": True, "desfeitos": desfeitos}


def resumo_financeiro_recorrente(conn: sqlite3.Connection, hoje: date | None = None) -> dict:
    """O dado por tras do card `resumo_financeiro_recorrente` (consulta
    "quanto tenho de parcelas?"/"quais assinaturas eu tenho" - ver
    `docs/contrato-assinaturas.md`)."""
    hoje = hoje or date.today()
    comprometido = total_mensal_comprometido(conn, hoje)
    assinaturas_ativas = listar_assinaturas(conn, apenas_ativas=True)
    compras_em_andamento = listar_compras_parceladas(conn, apenas_em_andamento=True, hoje=hoje)
    return {
        "mes": comprometido["mes"],
        "total_mensal": comprometido["total"],
        "assinaturas_total": comprometido["assinaturas_total"],
        "parcelas_total": comprometido["parcelas_total"],
        "n_assinaturas_ativas": len(assinaturas_ativas),
        "n_compras_em_andamento": len(compras_em_andamento),
        "proximas_cobrancas": proximas_cobrancas(conn, hoje, limite=5),
    }
