### Fase 7B - faixa V3 (Hábitos, Projetos, Agenda, Tarefas)

- **Botão "adicionar" único e maior (`.btn-adicionar`), abre o formulário num
  painel deslizante (`.bottom-sheet`).** Nas seções `vida/habitos`, `vida/
  projetos`, `vida/agenda-painel` ("+ criar evento") e `tarefas/tarefas`, o
  botão azul pequeno de antes virou um `.btn-adicionar` de largura cheia
  (mín. 48px) que abre o mesmo formulário de sempre dentro de um painel
  (`window.abrirBottomSheet?.(...)`/`fecharBottomSheet?.(...)`, faixa V0d;
  com fallback de mostrar o formulário inline enquanto essa faixa não chega
  na integração). O formulário continua enviando para as mesmas rotas de
  hoje (`POST /api/habitos`, `/api/projetos`, `/api/agenda/eventos`,
  `/api/tasks`); ao salvar, fecha o painel e recarrega a lista - mesmo
  comportamento de antes.
- Itens das quatro listas ganham `.lista-item`; cards (`.card`), chips
  (status do projeto, tags de tarefa, meta/horário do hábito) e campos de
  formulário (`.campo`) seguem o contrato de classes de
  `docs/agentes/fase7-visual.md`, sem mudar cor/fonte/animação.
- Verificação Playwright 390x844 (`scripts/ralph-v3-organizacao/`): abre
  cada formulário pelo botão novo, cria 1 item de teste em cada seção (banco
  de teste, nunca o real - agenda usa um dublê local do iCloud, sem chamada
  de rede real), confere que aparece na lista. Zero erro de console.
