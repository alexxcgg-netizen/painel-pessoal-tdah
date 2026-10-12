"""Limpeza da fala transcrita (2026-10-12, pedido do Alex: "no ChatGPT/Gemini eu posso errar
que ele entende; no nosso sai tudo bagunçado").

O Whisper devolve o que ouviu, literalmente: gagueira, "é, tipo, né", começo de frase
abandonado, correção no meio ("às três, não, às quatro") e nome próprio mal ouvido
("Dom Joaquim" -> "dom Joaquin", "Fiorino" -> "fiorino"). Esta função reescreve UMA vez,
rápido, do jeito que ele quis dizer - usando o vocabulário dele (lugares, aeronaves, tarefas)
pra acertar nome - e nunca acrescenta informação. Falhou / saída suspeita = devolve o texto
cru (o chat ainda sabe que veio de áudio e interpreta).
"""

from __future__ import annotations

from ia import core
from ia.funcoes.chat import _garantir_adapter_anthropic_legado

FUNCAO_LIMPAR_FALA = "limpar_fala"

PROMPT_LIMPAR_FALA = """Você recebe a transcrição automática de um ÁUDIO que o Alex gravou pro assistente pessoal dele
(português do Brasil, falado do jeito dele, às vezes cansado ou com pressa). Reescreva como ele QUIS dizer:

- Aplique as autocorreções: "às três, não, às quatro" -> "às quatro"; "compra pão, ah não, já tem" -> tira o pão.
- Tire gagueira, repetição, "é...", "tipo", "né", "sabe", "assim" quando forem só muleta, e começos de frase abandonados.
- Conserte palavra claramente mal transcrita usando o VOCABULÁRIO abaixo e o sentido da frase (nome de lugar,
  pessoa, aeronave, empresa). Na dúvida entre duas leituras, mantenha a do texto.
- NÃO acrescente nada que ele não disse, NÃO responda, NÃO resuma demais: todo pedido, data, hora, valor e nome
  continua lá. Mantenha a primeira pessoa e o tom dele (pode ficar informal).
- Pode juntar em frases bem pontuadas; se ele listou várias coisas, mantenha todas, na ordem.

Devolva SÓ o texto reescrito, sem aspas, sem comentário."""


def limpar(bruto: str, vocabulario: str = "") -> tuple[str, bool]:
    """(texto, limpou). Nunca levanta: qualquer falha devolve (bruto, False)."""
    bruto = (bruto or "").strip()
    if len(bruto.split()) <= 3:  # "sim", "beleza manda", "pode ser" - nada pra limpar (economiza a chamada)
        return bruto, False
    contexto = f"VOCABULÁRIO do Alex (grafia certa): {vocabulario}" if vocabulario else ""
    try:
        _garantir_adapter_anthropic_legado()
        resp = core.chamar_ia(
            FUNCAO_LIMPAR_FALA,
            [{"role": "user", "content": f"TRANSCRIÇÃO:\n{bruto}"}],
            sistema=PROMPT_LIMPAR_FALA,
            contexto_fixo=contexto,
        )
    except Exception:  # noqa: BLE001 - limpeza e um extra; nunca derruba o audio
        return bruto, False
    texto = (getattr(resp, "texto", "") or "").strip().strip('"').strip()
    if not getattr(resp, "ok", False) or not texto:
        return bruto, False
    # saida suspeita: muito mais longa (inventou/respondeu) ou curta demais (cortou pedido)
    if len(texto) > len(bruto) * 1.5 + 40 or len(texto) < len(bruto) * 0.25:
        return bruto, False
    return texto, True
