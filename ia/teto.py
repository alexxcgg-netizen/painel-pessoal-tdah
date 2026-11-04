# ia/teto.py — faixa A4 (medicao e teto)
#
# Implementa `teto_permite` do contrato (`ia/contrato.py`, NAO alterado aqui).
# Reaproveita o mecanismo de teto JA EXISTENTE (`db.CHAVE_TETO_MENSAL_IA`/
# `db.obter_teto_mensal_ia`/`db.definir_teto_mensal_ia`, US-A6 da Fase 5) em
# vez de duplicar um sistema paralelo: o teto configurado por ali (em USD,
# via o card financeiro do painel) continua valendo, so que agora comparado
# em BRL (cambio fixo de `ia/precos.json`) contra o gasto medido em
# `uso_ia` (`ia/medicao.py`), que e a nova fonte hibrida (Anthropic +
# OpenAI). Sem nada configurado (comportamento padrao de
# `db.obter_teto_mensal_ia` == None), nao ha teto: o gasto so e medido. O
# padrao de R$40/mes da Fase 7 saiu a pedido do Alex (2026-11-01).
#
# Mensagem de erro: reaproveita o MESMO texto de `app.TETO_IA_MSG` (copiado
# aqui, nao importado - `ia/` nao pode importar `app.py`, que ainda nao
# importa `ia/` nenhum: importar na outra direcao criaria import circular no
# dia em que uma faixa futura ligar `app.py` em `ia/*`). Ver
# `app.py:TETO_IA_MSG` - qualquer mudanca de texto la deve ser copiada pra
# ca tambem, os dois tem que ficar identicos.
#
# Lock: `app._TETO_IA_LOCK` existe pra fechar a janela TOCTOU entre "checar
# se o teto estourou" e "gravar o gasto da chamada" nos 2 pontos que hoje
# passam por `resumo_custo_api`. Pelo mesmo motivo de nao importar `app.py`
# acima, `ia/teto.py` expõe o proprio lock (`_TETO_IA_LOCK`) pro MESMO
# proposito, pra quem for escrever um novo caminho de chamada de IA em cima
# do contrato (`teto_permite(...)` -> chamar a IA -> `registrar_uso(...)`)
# poder serializar as 2 pontas contra corrida, igual `app.py` ja faz hoje
# pros caminhos antigos.

import threading

import db
from ia.medicao import cambio_usd_brl, gasto_mes_atual_brl

# Mesmo texto de app.TETO_IA_MSG (ver comentario acima) - copiado, nao
# importado.
TETO_IA_MSG = (
    "teto mensal de gasto com IA estourado - tente de novo mes que vem ou ajuste o teto no card financeiro"
)

# Serializa checar-o-teto -> chamar a IA -> gravar o gasto, mesmo papel de
# `app._TETO_IA_LOCK` pro novo caminho baseado no contrato (`ia/contrato.py`).
_TETO_IA_LOCK = threading.Lock()

# Teto (R$) quando o Alex nunca configurou nada pelo card financeiro
# (db.obter_teto_mensal_ia(conn) is None). Zero = sem teto: `_fracao_teto` fica
# em 0 e nada bloqueia. Quem configurar um valor no card volta a ter limite.
TETO_PADRAO_BRL = 0.0

# Fracao do teto a partir da qual entra o "modo economia" (aviso, mas ainda
# permite) - 80%, conforme pedido da tarefa.
FRACAO_AVISO = 0.8

# Funcoes que continuam liberadas mesmo com o teto 100% estourado (modo
# economia "duro"): as baratas/locais, que rodam no modelo mais barato
# (Luna) ou nem chamam IA nenhuma - nunca as caras (Sonnet/Sol). Lista
# ajustavel: comeca com as funcoes de classificacao (hoje Haiku, a
# equivalente barata da migracao hibrida) e a captura rapida, que sustentam
# o uso basico do dia a dia do painel. "desfazer" tambem entra aqui por
# completude (documentacao), mas ja e tratado a parte, incondicional, logo
# no topo de `teto_permite` (nunca bloqueia, com ou sem essa lista).
FUNCOES_ESSENCIAIS_MODO_ECONOMIA = (
    "desfazer",
    "intent",
    "captura",
)

# "Desfazer" nunca pode ficar bloqueado por teto de IA: e uma acao local
# (so mexe no banco - POST /api/desfazer/<token> -> app._desfazer_itens),
# nunca chama nenhum provedor de IA. Ver app.py (_desfazer_itens,
# cards.ACTIONS_BLOQUEADAS_VISITANTE) - bloquear ela por teto tiraria do
# Alex justamente a ferramenta de corrigir um erro, o pior momento possivel
# pra isso falhar.
FUNCAO_DESFAZER = "desfazer"


def _teto_mensal_brl() -> float:
    """Teto mensal em BRL: le o valor configurado pelo mecanismo existente
    (`db.CHAVE_TETO_MENSAL_IA`, em USD) e converte pelo cambio fixo de
    `ia/precos.json`; sem nada configurado, 0 (sem teto)."""
    conn = db.get_db()
    try:
        teto_usd = db.obter_teto_mensal_ia(conn)
    finally:
        conn.close()
    if teto_usd is None:
        return TETO_PADRAO_BRL
    return teto_usd * cambio_usd_brl()


def _fracao_teto() -> float:
    """gasto do mes / teto mensal, ambos em BRL. Teto <= 0 e "sem teto
    nenhum" (fracao 0), nunca divisao por zero."""
    teto = _teto_mensal_brl()
    if teto <= 0:
        return 0.0
    return gasto_mes_atual_brl() / teto


def nivel_alerta() -> str:
    """"normal" | "aviso_80" | "estourado_100", conforme a fracao do gasto
    do mes (BRL) sobre o teto mensal (BRL)."""
    fracao = _fracao_teto()
    if fracao >= 1.0:
        return "estourado_100"
    if fracao >= FRACAO_AVISO:
        return "aviso_80"
    return "normal"


def teto_permite(funcao: str) -> bool:
    """True se o teto mensal de IA ainda permite a `funcao` chamar IA.

    - "desfazer" sempre True (nao chama IA, nunca pode ficar bloqueado).
    - Abaixo de 100% (normal ou aviso_80): sempre True - "modo economia" no
      nivel 80% e so um aviso pra quem consulta `nivel_alerta()`, nao um
      bloqueio.
    - Em 100% (estourado_100): True so pras funcoes em
      FUNCOES_ESSENCIAIS_MODO_ECONOMIA (baratas/locais); qualquer outra
      (as caras, tipo chat/quebra de tarefa em Sonnet ou Sol) volta False.
    """
    if funcao == FUNCAO_DESFAZER:
        return True
    if nivel_alerta() != "estourado_100":
        return True
    return funcao in FUNCOES_ESSENCIAIS_MODO_ECONOMIA
