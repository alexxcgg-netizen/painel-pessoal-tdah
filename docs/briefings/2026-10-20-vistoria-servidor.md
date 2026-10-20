# Vistoria de 20/10/2026: servidor saturando

Relatório do painel (`scripts/relatorio_painel.py`, 14 a 20/10) cruzado com o índice do CHANGELOG.

## O que estava errado (ainda acontecia)
- `waitress.queue` / "connection limit": fila enchendo em rajadas (16/10 12h, 18/10 19h, 19/10 12h-16h,
  20/10 17h), chegando a recusar conexão nova. Numa dessas (18/10 19h) o Alex repetiu a mesma mensagem
  no chat: provavelmente o painel não respondeu.
- Causa: `iniciar_painel.bat` rodava o Waitress com o padrão de 4 threads, e cada resposta ao vivo do
  chat (`/api/chat/stream`, `rotas/chat.py`) segura uma thread até a IA terminar. O deploy
  (`render.yaml`, `deploy/DEPLOY.md`) já usava `--threads 8`.

## O que mudou
- `iniciar_painel.bat`: `--threads=16` (arquivo local do Alex, fora do git).
- `db.py` `get_db()`: `timeout=30` (antes 5 s do padrão), pra mais threads não virarem "database is locked".
  O banco continua em modo `delete` (sem WAL) de propósito: WAL cria arquivos extras e mexeria nos backups.

## Conferido e sem ação
- Barra de abas fora da tela: 5 medidas, todas de 15/10, consertadas em 15 e 16/10 (SW v82 e v84).
- Avisos insistentes "nunca vistos": os 25 do relatório são quase todos de 15 e 16/10, antes do conserto
  de 17/10; depois dele foram 4 de 25 enviados.
- `MustDowngradeError` (urllib3, h3): vem da sincronização do iCloud (`caldav` -> `niquests`); a conexão
  repete e funciona. Ruído, e o log já parou de gravar isso em 18/10 (por isso o último é de 18/10 20:11).
- Falha do detector de microfone: 1 caso só.

## Como conferir depois
Rodar `scripts/relatorio_painel.py` em alguns dias: `waitress.queue` e "connection limit" devem sumir
ou cair muito. Se continuarem, o gargalo é outro (Maps, voz, resumo do dia) e vale medir tempo por rota.
