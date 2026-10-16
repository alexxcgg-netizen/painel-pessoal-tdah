---
name: relatorio-painel
description: Gera e lê o relatório do painel inteiro (conversa, aparelho, erros do servidor, dados) pra achar bug, erro e coisa que ainda não sai como o Alex quer. Usar quando ele pedir "olha o relatório do painel", "vê se tem bug/erro", "o que ainda tá errado", "confere o painel todo", ou antes de decidir o que consertar numa leva.
---

# Relatório do painel

Pedido do Alex (2026-10-16): ler o painel inteiro e dizer o que está com bug, erro ou fora do que ele quer.
Complementa a `ler-chat` (que só mostra a conversa): aqui tudo é cruzado e ordenado por gravidade.

## Como
1. `.venv/Scripts/python.exe scripts/relatorio_painel.py` (últimos 7 dias; `--dias 30` ou
   `--desde AAAA-MM-DD --ate AAAA-MM-DD`). Abre `data/painel.db` em **modo só leitura** (`mode=ro`); nunca
   grava e nunca importa `app.py`. Escreve `data/relatorio_painel.md` (gitignored).
2. Ler o arquivo (Read). Começa com **"O que olhar primeiro"**: sinais ordenados (`quebrado` > `suspeito` >
   `provável ruído`). Depois uma seção por fonte:
   - **Conversa**: ele corrigiu/reclamou, a IA admitiu falha, ele repetiu a mesma mensagem, só um horário solto
     depois de resposta (a IA gravou na tarefa certa?). Para ler a conversa inteira: skill `ler-chat`.
   - **Aparelho**: erros de JavaScript do celular (`erro_js`), barra de abas fora da tela, medidas impossíveis
     descartadas, falhas do microfone.
   - **Servidor**: WARNING/ERROR agrupados de `data/erros_servidor.log` (existe desde 16/10/2026 e só enche
     depois de reiniciar o painel; traceback completo está nesse arquivo).
   - **Dados**: tarefas atrasadas e duplicadas, ações que ele **desfez** (a IA fez e ele não queria), avisos
     insistentes que ele nunca abriu, gasto sem categoria, custo de IA por função, cotas do mês.
3. **Os sinais são pistas, não veredito.** Antes de afirmar que algo é bug:
   - cruzar com o **índice do `CHANGELOG.md`** - muita coisa do período já foi consertada (ex.: "modo
     visitante esquecido" aparece na conversa de 10 e 12/10 e foi corrigido em 13/10);
   - ler o código/contexto do trecho; separar **"já corrigido"** de **"ainda acontece"**.
4. Responder ao Alex em português, curto: o que está quebrado agora, o que é suspeito, o que já foi resolvido,
   e o que sugere consertar primeiro. Por regra da casa (`levas-sem-perguntar`), conserto dentro de uma leva com
   briefing em `docs/briefings/`, e mostra as decisões no fim.

## Regras
- O relatório tem coisa pessoal (conversa, tarefas, gastos): fica só em `data/`. **Nunca** copiar trecho
  dele pra commit, `docs/`, CHANGELOG, teste ou artefato - nesses lugares só o aprendizado generalizado, sem
  nome, endereço ou valor. Números longos já saem como `[número oculto]`.
- Não rodar contra outro banco nem escrever no `painel.db`. Para testar o script, banco temporário (ver
  `tests/test_relatorio_painel.py`).
- Se aparecer erro de JavaScript novo e repetido: abrir o arquivo:linha apontado, reproduzir (Playwright
  headless, como em `tests/test_volta_do_segundo_plano.py`) e consertar com teste, não só silenciar.
