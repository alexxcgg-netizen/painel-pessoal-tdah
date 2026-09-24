# classificador_local/

Frases que o painel resolve **sem chamar IA**. Cada faixa cria o proprio arquivo em
`classificador_local/regras/<nome>.py` - nunca edita `app.py` nem a regra de outra faixa.
Contrato completo no docstring de `classificador_local/__init__.py`.

## Onde entra

`app.py` consulta `classificador_local.casar(texto)` antes de qualquer IA:

| Caminho | O que acontece quando uma regra casa |
|---|---|
| `_processar_mensagem_chat` (`/api/chat`, Telegram) | roda `executar` da regra; se devolveu algo, a resposta e so isso (cards + `resumo_texto`), sem IA |
| `_executar_captura` (`/api/capture`, `/api/atalho/capturar`) | idem, status 201, com `regra_local` e `acao` no corpo |
| `_classificar_intent` (`/api/intent/classificar`, `/api/atalho/comando-voz`) | so classifica (primeira camada, antes do padrao aprendido); campo aditivo `regra_local` |

Se `executar` devolver `None` (ou levantar excecao - loga e faz rollback), o fluxo normal
segue como se nenhuma regra tivesse casado.

## Ordem

Arquivos rodam em ordem alfabetica e vale a **primeira** regra que casar. Use nome com
prefixo da faixa (`a7_assinatura.py`, `p3_lembrete_condicional.py`) e faca o `casar` estrito
(frase inteira, `re.fullmatch`) pra nao roubar frase de outra regra.

## Exemplo (NAO e uma regra ativa - so o molde)

```python
# classificador_local/regras/exemplo_agua.py
import re

from db import registrar_hidratacao  # funcao que ja existe

_RE = re.compile(r"(tomei|bebi) (um|1) copo d[e']? ?agua", re.IGNORECASE)


def casar(texto):
    """Rapido e sem efeito colateral: so texto, nunca banco nem rede."""
    if not _RE.fullmatch(texto.strip().rstrip(".!")):
        return None
    return {"acao": "registrar_hidratacao", "confianca": 1.0, "parametros": {}}


def executar(conn, parametros):
    """Faz a acao SEM commit (quem chama commita) e devolve os efeitos no
    formato `_efeito` de docs/CARDS.md - viram os mesmos cards do chat."""
    from datetime import date

    hoje = date.today().isoformat()
    total = registrar_hidratacao(conn, hoje)
    registro_id = conn.execute(
        "SELECT MAX(id) AS id FROM hidratacao_registros WHERE data = ?", (hoje,)
    ).fetchone()["id"]
    return {
        "efeitos": [{"entidade": "hidratacao", "id": registro_id}],
        "resumo_texto": f"+1 copo de agua. {total} hoje.",
    }
```

Retornos aceitos por `executar`:

- `{"efeitos": [...], "resumo_texto": "...", "passos": [...]?}` - recomendado: vira
  `cards.montar_resposta` (mesmos cards do chat, com Desfazer).
- `{"cards": [...], "resumo_texto": "...", "passos": [...]?}` - cards ja montados (`cards.novo_card`).
- `None` - desisti, segue o fluxo normal (IA).

Sem `passos`, entra um passo padrao "Resolveu sem IA (<regra>)".

## Teste

No arquivo de teste da sua faixa, chame `classificador_local.casar("...")` com frases que
DEVEM e que NAO devem casar, e o caminho completo via `/api/chat` com
`patch("claude_client.chat")` garantindo que a IA nao foi chamada. Ver
`tests/test_fase7_infra_classificador.py` pra injetar regra falsa sem criar arquivo aqui.
