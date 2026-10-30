"""Numero no icone do app (leva Lab v4, ideia "badge", 30/10/2026).

O icone do painel na tela de inicio ganha o numero vermelho com o que ainda esta aberto pra hoje (tarefa
com data ate hoje, atrasadas inclusive - sao as que mais escapam). Concluiu, o numero desce na hora.

Como chega no icone:
  - app aberto: `static/js/nucleo/badge.js` chama `navigator.setAppBadge(n)` (Badging API, iOS 16.4+ em web app
    da tela de inicio) ao abrir, ao voltar pra tela e depois de qualquer escrita;
  - app fechado: o service worker faz o mesmo com o `badge` que vai junto de cada aviso push
    (`push_client.enviar(..., badge=n)`) e com o que volta do botao Feito do aviso (`/api/push/acao`).
O iOS nao tem push silencioso pra PWA: o numero so se atualiza com o app aberto ou quando chega um aviso.

Rotina recorrente (remedio, academia) nao entra: o molde nao e tarefa; a ocorrencia do dia ja vira tarefa normal.
"""

from __future__ import annotations

from datetime import date

LIMITE = 99  # o iOS mostra qualquer numero, mas "99" ja e "tem coisa demais"; o numero exato fica na tela


def contagem(conn, hoje: date) -> int:
    """Tarefas abertas com data ate `hoje`. Nunca levanta (banco ocupado = 0 e o numero some, nao quebra)."""
    try:
        linha = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
            "AND due_date IS NOT NULL AND due_date != '' AND due_date <= ?",
            (hoje.isoformat(),),
        ).fetchone()
        return min(int(linha["n"]), LIMITE)
    except Exception:  # noqa: BLE001
        return 0
