"""Fase 8, faixa F3 (+ faixa uso/m5-parcela) - avisa 3/2/1 dia antes de uma
cobranca recorrente acontecer de novo. Duas fontes, mesmo mecanismo (nao
duplica logica entre elas - so o "adaptador" por fonte muda):

- Assinatura: so pra quem tem o interruptor `assinatura.avisar_antes_cobrar`
  ligado (migracoes/202609251200_f8_assinatura_aviso.sql, DESLIGADO por
  padrao - nenhuma assinatura avisa sozinha). Data da proxima cobranca vem
  de `financas_recorrentes.proxima_cobranca_assinatura` (a mesma conta que
  a rota GET /api/financas/assinaturas ja usa) - nao reimplementada aqui.
- Parcela (compra_parcelada): avisa por padrao pra toda compra em
  andamento - nao tem coluna equivalente a `avisar_antes_cobrar` (decisao
  da faixa uso/m5-parcela: criar uma so pra isso seria mais uma migracao +
  tela de toggle por parcela pra um caso que, ao contrario da assinatura
  -que e recorrencia indefinida-, ja tem fim natural (quita e some sozinha);
  quem quiser desligar aviso de cobranca por completo usa o mesmo
  liga/desliga de categoria "aviso_cobranca" em assistente/avisos.py, que
  ja vale pras duas fontes). Progresso/data vem de
  `financas_recorrentes.parcela_info` (mesma conta que
  `/api/gastos/proximas-cobrancas` em rotas/f8_banco.py ja usa) - tambem
  nao reimplementada aqui.

Idempotente pela `chave_unica` que `assistente.contrato.enfileirar` recebe:
inclui a fonte (assinatura/parcela), o id da fonte (pra parcela, tambem o
numero da parcela - "3/10" - pra nao confundir uma parcela com a seguinte
da mesma compra), a data ISO da cobranca-alvo e a contagem de dias. Rodar o
tick varias vezes no mesmo dia (ou em dias diferentes, enquanto a
cobranca-alvo nao mudar) nunca duplica o aviso, o mesmo aviso nunca repete
2x pro mesmo ciclo de cobranca, e a parcela seguinte da mesma compra sempre
gera um aviso novo e distinto (chave inclui o numero dela).

Nao mistura com o aviso de teto de gasto (`valor_para_aviso_custos_fixos`/
tipo "orcamento") nem chama IA - so texto fixo com nome/descricao e prazo.
"""

from datetime import date, datetime

import financas_recorrentes as fr

PREFIXO = "f8_aviso_cobranca"  # nome deste arquivo sem .py
DIAS_AVISO = (3, 2, 1)


def _enfileirar(**kwargs):
    # Late import de proposito - mesmo padrao dos outros gatilhos
    # (assistente/gatilhos/p2_perguntas.py), assistente.contrato pode nao
    # estar pronto quando este modulo e importado.
    from assistente.contrato import enfileirar

    return enfileirar(**kwargs)


def _texto_prazo(dias: int) -> str:
    return "amanha" if dias == 1 else f"em {dias} dias"


def _valor_txt(valor) -> str:
    return f"R$ {valor:.2f}" if isinstance(valor, (int, float)) else "valor a confirmar"


# ---------------------------------------------------------------------------
# Adaptadores por fonte: cada um so sabe ler a PROPRIA tabela e devolve um
# dict no formato comum abaixo - quem decide dias/prazo/chave_unica e o
# `executar` no final do arquivo, uma vez so pras duas fontes.
#   subtipo   -> vira o sufixo da origem ("f8_aviso_cobranca:<subtipo>")
#   chave_id  -> parte que identifica a cobranca dentro da fonte (distingue
#                assinatura x assinatura, e parcela x parcela - inclui o
#                numero da parcela pra nao colidir com a proxima)
#   proxima   -> date da proxima cobranca (fonte unica: financas_recorrentes)
#   valor     -> valor da cobranca (float) ou None
# ---------------------------------------------------------------------------

def _cobrancas_assinatura(conn, hoje: date):
    for assinatura in fr.listar_assinaturas(conn, apenas_ativas=True):
        if not assinatura.get("avisar_antes_cobrar"):
            continue
        proxima = fr.proxima_cobranca_assinatura(assinatura, hoje)
        if proxima is None:
            continue
        yield {
            "subtipo": "assinatura",
            "chave_id": str(assinatura["id"]),
            "proxima": proxima,
            "valor": assinatura.get("valor"),
            "nome": (assinatura.get("nome") or "Assinatura").strip(),
        }


def _cobrancas_parcela(conn, hoje: date):
    for compra in fr.listar_compras_parceladas(conn, apenas_em_andamento=True, hoje=hoje):
        info = fr.parcela_info(compra, hoje)
        if info["quitada"] or info["proxima_cobranca"] is None:
            continue
        proxima = date.fromisoformat(info["proxima_cobranca"])
        atual = info["parcela_atual_calculada"]
        yield {
            "subtipo": "parcela",
            "chave_id": f"{compra['id']}:{atual}",
            "proxima": proxima,
            "valor": compra.get("valor_parcela"),
            "descricao": (compra.get("descricao") or "Compra parcelada").strip(),
            "parcela_atual": atual,
            "n_parcelas": int(compra["n_parcelas"]),
        }


def _titulo_assinatura(cobranca: dict, prazo: str) -> str:
    return f"{cobranca['nome']} cobra de novo {prazo}"


def _titulo_parcela(cobranca: dict, prazo: str) -> str:
    return (
        f"Parcela {cobranca['parcela_atual']}/{cobranca['n_parcelas']} de "
        f"{cobranca['descricao']}, {_valor_txt(cobranca['valor'])}, {prazo}"
    )


# subtipo -> (fonte dos dados, formatador de titulo). Corpo e sempre o
# mesmo formato (valor + data ISO) pras duas fontes, ver `_corpo` abaixo.
_FONTES = {
    "assinatura": (_cobrancas_assinatura, _titulo_assinatura),
    "parcela": (_cobrancas_parcela, _titulo_parcela),
}


def _corpo(cobranca: dict) -> str:
    valor = cobranca.get("valor")
    if not isinstance(valor, (int, float)):
        return ""
    return f"Cobrança de R$ {valor:.2f} prevista para {cobranca['proxima'].isoformat()}."


def executar(conn, agora: datetime) -> dict:
    hoje = agora.date()
    criados = 0
    for subtipo, (listar_cobrancas, titulo_fn) in _FONTES.items():
        for cobranca in listar_cobrancas(conn, hoje):
            dias = (cobranca["proxima"] - hoje).days
            if dias not in DIAS_AVISO:
                continue
            prazo = _texto_prazo(dias)

            _enfileirar(
                tipo="aviso",
                titulo=titulo_fn(cobranca, prazo),
                corpo=_corpo(cobranca),
                origem=f"{PREFIXO}:{subtipo}",
                chave_unica=f"{PREFIXO}:{subtipo}:{cobranca['chave_id']}:{cobranca['proxima'].isoformat()}:{dias}",
            )
            criados += 1
    return {"avisos_criados": criados}
