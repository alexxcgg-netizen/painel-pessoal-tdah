# Histórico de Versões (Changelog) - Painel Pessoal (Alex)

Este arquivo documenta as mudanças relevantes no painel pessoal, por dia de trabalho.
Serve como memória base para futuras sessões de IA - sem isso, cada sessão nova tem que
reconstruir contexto lendo o `git log` inteiro. Ver também `README.md` pra visão geral das
features e da integração com o painel da construtora (`financeiro-construtora`, outro repo).

## 2026-09-21 - Contas a pagar da construtora, auditoria noturna de qualidade

**Integração com a construtora:** consome o novo `GET /api/contas_a_vencer` do painel da
construtora (`financeiro-construtora` v3.99.16) - aba Construtora mostra a lista de contas
a vencer/vencidas, e o scheduler avisa por push quando uma conta vence hoje, já venceu, ou
vence nos próximos 3 dias (dedup por dia, sem repetir aviso). Entra como contexto no resumo
do dia e no chat.

**Assistente mais esperto (turno anterior do mesmo dia):** sugere o dia menos corrido da
semana pra tarefas sem data fixa, sugere horário livre no dia, calcula custo de combustível
de viagem com distância real (Google Maps), sugere posto no meio do caminho pra abastecer.
Uber por voz com o risco de cobrança errada eliminado (fare travado + confirmação explícita
antes de qualquer corrida de verdade ser pedida - decisão do Alex: "tirar o risco", não
abandonar a feature). Currency de voo (avisa depois de 21 dias sem voar), lembrete de
desacelerar às 22h, rotação de 3 temas de estudo pra aviação, aviso proativo quando o tempo
fica bom pra uma tarefa marcada como dependente do clima. Cotação de fornecedores com leitura
automática de PDF (Claude lê o orçamento escaneado e extrai os itens). Atalhos do iPhone
(captura por voz, PDF direto pro Compartilhar) e widget de tela inicial via Scriptable.

**Auditoria noturna de qualidade (pedido do Alex: "20 ou mais coisas que vc consegue fazer
sem ficar me perguntando"):**
- Cache de 60s nas chamadas pra API da construtora (evita estourar o rate limit de 20 req/min
  de lá quando várias partes do painel pedem o mesmo dado em sequência rápida). Corrigido de
  quebra: a rota `/api/construtora/resumo` tinha uma chamada direta que não passava pelo cache.
- `/healthz` pra monitoramento externo, sem autenticação, sem tocar no banco.
- Índices no SQLite nas colunas mais filtradas/ordenadas (`tasks.completed_at`/`due_date`,
  `expenses.created_at`/`tipo`, `subtasks.task_id`, etc.) - idempotente, sem mudar nenhum
  resultado de query, só a velocidade conforme o histórico cresce.
- Corrigido N+1 real em `GET /api/tasks` (1 query de subtarefas por tarefa em vez de uma
  query só pra todas).
- Export de gastos em CSV e backup/export do banco (cópia consistente via API de backup do
  sqlite3, não uma cópia de arquivo crua) - botões no cabeçalho/aba Gastos.
- Acessibilidade: cabeçalho expansível de cada cotação ganhou `role="button"` +
  `aria-expanded` (era uma `<div>` focável sem semântica de estado pra leitor de tela).
- Dias restantes (além de meses) nas metas financeiras, com aviso de atraso quando o prazo já
  passou e a meta não foi batida.
- Auditorias sem achado (documentadas, não geraram mudança): formatação de moeda/data em
  `app.js` já usa `fmtMoeda`/`fmtDataBr` em todo lugar, sem inconsistência.

## 2026-09-20 - Gráficos técnicos e paleta final

Gráficos redesenhados com a skill de dataviz interna (mais "técnico", menos genérico) e
paleta validada. Troca completa de fontes (Libre Bodoni/Jost/IBM Plex Mono), fundo escurecido
70%, fonte separada pra valores em destaque (Bricolage Grotesque). Menos mistura de cor
(referência: trabalho do Pierre) e textos mais diretos/com personalidade, menos genéricos.

## 2026-09-19 - Deploy real, login, gráficos, identidade visual

Deploy pra VPS com HTTPS (necessário pro push funcionar no iPhone de verdade). Login por PIN
de 6 dígitos imposto pelo servidor. Tarefa/lembrete com horário viram compromisso de agenda e
push de verdade, com deep link pra já abrir o Uber. Gráficos de gasto diário, evolução de
meta e horas de voo. Várias passadas de identidade visual (paleta joia mais escura, tipografia
premium, saudação pessoal, som/vibração em momentos-chave). Horário no voo, separação de
gasto real x planejado.

## 2026-09-18 - Chat vira o centro do app, integrações externas

Chat com tool-use vira a tela principal (antes era só captura por texto). Notificações
proativas, memória durável entre conversas, datas importantes pra vida toda (licença de
piloto, seguro etc). Integração com Open Finance via Pluggy, com Saúde do iPhone via Atalhos,
com agenda do iCloud, e primeira ligação com o resumo financeiro da construtora no contexto
do chat. Aba Aviação: horas voadas, voos agendados, previsão do tempo e decodificação de
METAR/TAF (com leitura em voz alta). Comando de voz no chat via Web Speech API do navegador.
Notificação push funcionando de ponta a ponta.

## 2026-09-17 - Estrutura inicial (v1)

Primeira versão: captura rápida de tarefas/gastos/metas por texto livre (Claude classifica),
rastreio de custo de IA por chamada, pergunta de esclarecimento quando o texto é ambíguo,
testes automatizados com mock das chamadas ao Claude, base pra integração bancária via OFX.
