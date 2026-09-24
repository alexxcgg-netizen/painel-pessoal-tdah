# Fase 7 — regras de toda faixa (leia antes de começar)

Repo `painel-pessoal-tdah`: painel pessoal do Alex (TDAH). Flask + SQLite + JS puro. Tudo em português.

## Ambiente
- **Nunca** edite `/home/user/financeiro-construtora`, que é outro projeto e guarda o financeiro real de uma empresa. **Nunca** edite também o checkout principal `/home/user/painel-pessoal-tdah`. Se o ambiente te deu uma worktree automática, ignore: ela é do repo errado.
- Crie sua worktree a partir da integração:
  `git -C /home/user/painel-pessoal-tdah worktree add -b fase7/<faixa> /home/user/painel-pessoal-tdah-fase7-<faixa> fase7/integracao`
  Trabalhe só dentro dela. Se a branch já existir, rode o comando sem `-b`.
- Python: `/home/user/painel-pessoal-tdah/.venv/bin/python`. A worktree não tem `.venv`.
- Testes: `scripts/testes.sh tests/test_x.py` (JS: `scripts/testes.sh --js tests/js/x.test.js`). A saída traz só as falhas e o resumo. Rode **só os testes do seu módulo**, porque a suíte completa é do integrador. Existem 6 falhas conhecidas, que dependem de horário (voo/agrupamento).
- Leia trechos em vez de arquivos inteiros: use `grep -n ... | head -40` e `sed -n A,Bp`. O `app.py` tem mais de 8 mil linhas.

## Donos de arquivo
- Mexa **só** nos arquivos listados como seus no seu prompt. Se precisar de algo fora da lista, **não edite**: anote em `scripts/ralph-<faixa>/progress.txt` e siga em frente.
- **Não edite** `AGENTS.md`, `CHANGELOG.md`, `TODO.md`, `README.md`, `STATUS.md`, `.env.example`, `requirements.txt` nem `static/service-worker.js`. Esses arquivos são compartilhados e o integrador consolida. Coloque aprendizados em `scripts/ralph-<faixa>/APRENDIZADOS.md` e sua entrada de changelog em `changelog.d/<faixa>.md`. Dependência nova ou variável de ambiente nova vai no `progress.txt`.
- Infra da Etapa 0 (quando já estiver na `fase7/integracao`; confira com `git log origin/fase7/integracao --oneline | head`):
  - Rota nova: crie `rotas/<faixa>.py` com um Blueprint `bp`, que é registrado sozinho. Não edite o `app.py`.
  - Tabela nova: crie `migracoes/AAAAMMDDHHMM_<faixa>_<desc>.sql`, que é aplicado sozinho. Nunca edite migração existente nem o `db.py`.
  - Frase resolvida sem IA: crie `classificador_local/regras/<faixa>_<nome>.py` com `casar(texto)` e `executar(conn, parametros)`.
  - Tarefa periódica do assistente: crie `assistente/gatilhos/<faixa>.py` com `executar(conn, agora)`.
  - Funções de IA: `ia/funcoes/{chat,captura,planejamento,visao}.py`. O `claude_client.py` virou fachada.
  - Chamada de IA nova: use `ia.contrato`/`ia.core.chamar_ia(funcao, ...)` com `ia/config.d/<funcao>.json`.
  - Front: HTML em `templates/secoes/<aba>/<secao>.html`, JS em `static/js/secoes/...`, CSS novo em `static/css/secoes/<aba>.css` ou `static/css/ui/componentes/*.css`. O mapa está em `docs/agentes/mapa-frontend.md`.
  - Se precisar dessa infra e ela ainda não estiver na integração, faça primeiro as histórias que não dependem dela. Depois rode `git fetch origin && git merge origin/fase7/integracao` na sua branch e tente de novo, verificando a cada ~10 min por até 60 min. Se não chegar, marque a história como `blocked`.

## Trabalho
- Quebre a faixa em histórias pequenas, de 15 a 30 minutos cada. Registre o estado em `scripts/ralph-<faixa>/progress.txt`, com no máximo cerca de 40 linhas.
- A cada história concluída, faça commit e depois `git push -u origin fase7/<faixa>`, porque a sessão pode ser reciclada. A mensagem de commit termina com:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01VJzoYB1yYVL6gVFtBEB1Q7
  ```
- Antes de cada commit, rode `gitleaks detect --no-git --source . -q` se o gitleaks estiver instalado.
- Nos testes, use dublê/mock. Não faça **nenhuma** chamada real de API e não peça credencial. Os dados de exemplo são sintéticos, em pt-BR. Nenhum dado real do Alex sai do ambiente.
- Revisão de segurança, modo visitante, XSS e sanitização ficam para a Fase 10. As únicas exceções são o teto de IA, o gitleaks e a allowlist do Telegram.
- Tudo que for extra ou opcional entra isolado: arquivo próprio mais uma flag, para o Alex poder desligar.
- Se o mesmo teste falhar 2 vezes com a mesma abordagem, rode `git restore .` e tente outro caminho. Se a história não avançar, marque `blocked` no progress com a pergunta específica e passe para a próxima.
- Não assuma parâmetros de API de memória. Confira no SDK instalado (`help()`/código do pacote) ou na documentação oficial, e registre o que confirmou.
- Tela nova só fecha com verificação no Playwright headless em 390x844. O Chromium fica em `/opt/pw-browsers`; se o pacote pedir, use `executable_path='/opt/pw-browsers/chromium'`. Suba o app com banco de teste, nunca o real. Use a porta 5100 mais o índice da faixa. Faça no máximo 2 screenshots por tela, só na última história.

## Relatório final (curto)
Liste as histórias feitas e bloqueadas (com a pergunta), o resultado dos testes, os arquivos criados ou alterados e a branch. Não abra PR.
