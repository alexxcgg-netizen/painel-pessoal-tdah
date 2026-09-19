"""Ponto de entrada pra producao (gunicorn), separado do `python app.py` de
desenvolvimento local. So existe por causa do agendador: `app.py` so chama
`iniciar_scheduler()` dentro do `if __name__ == "__main__"`, pra nao ligar
o APScheduler sozinho quando os testes fazem `import app`. Sob gunicorn
`app.py` e importado (nao executado como main), entao esse arquivo chama
`iniciar_scheduler()` explicitamente.

Roda com exatamente 1 worker (`gunicorn -w 1 wsgi:app`) - mais de um worker
duplicaria o agendador (varios processos verificando notificacao ao mesmo
tempo) e o SQLite nao foi pensado pra multiplos processos escrevendo nele
ao mesmo tempo. Ver deploy/DEPLOY.md.
"""

from app import app, iniciar_scheduler

iniciar_scheduler()
