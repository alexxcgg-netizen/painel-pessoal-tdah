# TODO - execucao do BRIEFING.md

Arquivo de progresso pra retomar depois de qualquer interrupcao (regra 2 do
`BRIEFING.md`). Ordem: Fase 1 -> Fase 2 -> Fase 3, sem parar pra perguntar.
Marque `[x]` ao terminar cada item (com commit). Decisoes tomadas por
julgamento proprio ficam na secao "Decisoes" no fim.

## ⚠️ Protocolo obrigatorio antes de rodar agentes em paralelo (leia primeiro)
Achado real na Fase 4 (ver "Decisoes da Fase 4" mais abaixo pro relato completo) e pedido
explicito do Alex pra virar regra permanente, nao so um registro do que aconteceu. Vale pra
QUALQUER leva futura que use mais de um agente/subagente ao mesmo tempo neste repositorio (ou
entre este repositorio e o `financeiro-construtora`, o outro projeto do Alex que roda na mesma
maquina/sessao):

1. **Confirme, antes de comecar, em qual repositorio cada agente vai trabalhar** - nome do
   repositorio E caminho completo, nunca assumido. Cada agente deve rodar `pwd` e `git remote
   -v` como primeiro passo, antes de qualquer leitura/escrita, e conferir que bate exatamente
   com o projeto pedido (`painel-pessoal-tdah` ou `financeiro-construtora` - nunca os dois ao
   mesmo tempo por engano).
2. **Isolamento de verdade por agente, cobrindo os dois projetos** - o parametro de worktree
   isolado deste ambiente so cobre o repositorio principal da sessao automaticamente; se o
   trabalho for num repositorio irmao (como aconteceu na Fase 4), isso NAO isola sozinho. Pra
   cada agente que vai escrever, crie manualmente um `git worktree add` (ou clone separado)
   dentro do repositorio certo, antes de disparar o agente - nunca deixe dois agentes editando
   o mesmo checkout ao mesmo tempo.
3. **Nunca dar a um agente trabalhando no `painel-pessoal-tdah` acesso de escrita ao
   `financeiro-construtora`, nem vice-versa** - mesmo sem querer. O `financeiro-construtora` e
   dado real de empresa (`AGENTS.md` proprio, regras rigidas de backup/homologacao) - uma
   confusao de repositorio la e muito mais grave do que ja foi aqui. Se a estrutura do
   ambiente nao permitir bloquear isso tecnicamente, documente a regra explicita no prompt de
   cada agente e faca ele confirmar antes de escrever.
4. **So depois da integracao** (merge de verdade se cada agente ficou em worktree/branch
   separada) rode a suite completa e uma revisao independente - nunca confie so no "cada
   agente disse que passou nos testes dele" quando houve qualquer risco de checkout
   compartilhado.

## Ja existia antes do briefing (nao refazer)
Captura unica com classificacao automatica (chat + tool-use), quebra de tarefa
em passos (subtasks), resumo/fechamento do dia sem cobranca, gasto solto
categorizado, gasto por categoria/orcamento, deteccao de assinatura
recorrente, datas importantes (lembretes), cutucada de tarefa parada, roteamento
Haiku/Sonnet, Web Push no iPhone, Pluggy (Open Finance), agua (contador),
correlacao sono x produtividade, clima do dia, "devo sair ate que horas"
(transito), medicamentos, voos com diario de bordo, metas com dias restantes,
"quanto sobra no mes", notas com tags.

## Fase 1
- [x] Check-in de 1 toque (energia/sono/humor, ruim/ok/bom) de manha
- [x] Rotina matinal (7h-7h30) e noturna (22h) guiada - checklist curto + push
- [x] Modo hiperfoco (25/50/90 min) - so notificacao critica passa
- [x] Modo "so o essencial" - IA escolhe 1-3, Alex pode trocar
- [x] Tarefa empacada -> sugere quebrar diferente
- [x] Contas pessoais recorrentes (so estrutura) - aviso 3 dias antes
- [x] Assinatura sem uso - pergunta mensal "ainda usa X?" 1 toque
- [x] Pessoas: lista com frequencia, nota de conversa, "faz tempo que nao fala com X"
- [x] Data importante com sugestao de acao ("ja pensou em mandar algo?")
- [x] Decisao rapida: "vale a pena?" + pros e contras

## Fase 2
- [x] Lembrete de agua/pausa a cada 2h, 9h-19h, dia util (silencia no hiperfoco)
- [x] Treino: ficha por grupo muscular + botao "!" na tarefa de treino + registro leve
- [x] Sintoma no chat -> sugere marcar medico/dentista + cria lembrete
- [x] Alerta de sono ruim 3+ noites (<6h no Saude ou "ruim" no check-in)
- [x] Correlacao sono x humor (check-in)
- [x] Localizacao via Atalhos: chegou/saiu de casa (contextual), mercado so com lista
- [x] Checklist de saida do dia a dia (carteira, carregador <50%, fone+garrafa se academia, bigode/cavanhaque sex/sab a noite)
- [x] Clima atrapalha compromisso do dia (aviso de manha)
- [x] Checklist pre-voo (fone, carta WAC, cartas de aerodromo, plano de voo, peso e balanceamento)
- [x] Mala automatica pra viagem (IA por destino/clima) + documento 3 dias antes e na manha
- [x] Lugares que gostei (sugere de novo ao voltar pra mesma cidade)
- [x] Manutencao recorrente por tempo (carro, casa, equipamento)
- [x] Lista de compras que enche com "acabou o X"
- [x] Redigir mensagem dificil
- [x] "Responder depois" -> lembrete dia seguinte 10h ate marcar respondido

## Fase 3
- [x] Projecao de sobra no fim do mes (conferir o que ja existe e completar)
- [x] Meta de compra grande com projecao de quando bate
- [x] Lista "quero aprender sobre X" que lembra de retomar
- [x] Resumo de artigo/video salvo
- [x] Painel de progresso pessoal (habitos, metas)
- [x] Revisao mensal automatica sem julgamento
- [x] Burocracia: IR, CNH, prazos de documento
- [x] Aviacao: validade de licenca + nota pos-voo (conferir o que ja existe)
- [x] Uso de apps (automacao "App abriu/fechou" do Atalhos) + bateria -> resumo semanal

## Final
- [x] Guia de Atalhos pro Alex (docs/ATALHOS.md)
- [x] Lista exata de credenciais que faltam (secao abaixo)
- [x] Revisao independente (agente) + artifact atualizado

## Credenciais (tudo no `.env` do servidor - nada disso vai pro Git)
Necessarias pro briefing funcionar:
- `ANTHROPIC_API_KEY` - chat, "so o essencial", quebrar tarefa, vale a pena, mala, mensagem
  dificil, resumo de link. Sem ela o resto funciona, mas sem IA.
- `PAINEL_ATALHOS_TOKEN` - voce mesmo gera (senha longa). Obrigatorio pra localizacao
  (casa/mercado) e uso de apps. Guia: `docs/ATALHOS.md`.
- Pelo menos um canal de aviso proativo:
  - Push no iPhone: rodar `python scripts/gerar_chaves_push.py` (gera `VAPID_PUBLIC_KEY` + chave
    privada) e preencher `VAPID_SUBJECT` com seu e-mail; ou
  - Telegram: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (@BotFather, ver README).
- `CIDADE_PADRAO` (nao e segredo) - liga o aviso "vai chover no horario do compromisso".

Opcionais (ja existiam):
- `SAUDE_WEBHOOK_TOKEN` (voce gera) - Atalho de Saude (sono ruim, sono x humor).
- `ICLOUD_USERNAME` + `ICLOUD_APP_PASSWORD` - agenda do iCloud no "cheguei em casa"/chuva.
- `GOOGLE_MAPS_API_KEY` + `ENDERECO_CASA` - "que horas sair" com transito.
- `PLUGGY_CLIENT_ID`/`SECRET`, `CONSTRUTORA_API_URL`/`KEY`, `UBER_CLIENT_ID`/`SECRET`.

Novas da Fase 4 (opcionais - sem elas o app funciona normal, so sem essas camadas extras):
- `ENCRYPTION_KEY` - liga a criptografia em repouso de dado do Open Finance e de saude.
  Gere com `python scripts/gerar_chave_criptografia.py` e cole no `.env`. **Guarde uma
  copia fora do servidor** (gerenciador de senhas) - perder essa chave torna o dado
  cifrado irrecuperavel. Ver `docs/SEGURANCA.md`.
- `BACKUP_DIR` - so se quiser o backup automatico semanal num lugar diferente de
  `data/backups/` (o padrao ja funciona sem configurar nada). Ver `docs/BACKUP.md`.

## Decisoes (tomadas sem perguntar, pela regra 3)
- Base: continua no painel-pessoal-tdah, pula o que ja existe.
- Calendario/Contatos da Apple (CalDAV/CardDAV): fora, a pedido do Alex.
- Cofre "onde guardei documento": fora, a pedido do Alex.
- Screen Time: o Atalhos nao le o dado; aproximamos com a automacao "App abriu/fechou".
- Consulta medica/dentista: sem recorrencia fixa - so quando o Alex falar ou citar sintoma.
- Manutencao: so por tempo por enquanto (sem km).
- Chegada em casa e contextual (hora + agenda), nunca repete a mesma mensagem em 2h.
- Aba nova "Vida" pras secoes pessoais (Painel estava longo demais).
- Localizacao: o Atalho recebe a mensagem na resposta e mostra ele mesmo (sem push duplicado).
- Treino: casa ficha pelo nome do grupo no titulo da tarefa; titulo generico mostra todas.
- Hiperfoco: aviso de janela curta fica guardado e sai no fim do foco; agua/pausa some.
- Validade de licenca/CMA: entra como lembrete de burocracia (aviso 30 dias antes), sem tabela nova.
- Salvar link: o servidor so busca endereco publico; se nao ler/resumir, guarda o link mesmo assim.
- Uso de apps: sessao sem "fechou" ou > 3h e descartada (subestimar e melhor que inventar).
- Progresso/revisao mensal: so numeros e fatos, sem nota nem comparacao com "ideal".

## Fase 4 - Resiliencia, Backup e Seguranca (leva adicional, pos-BRIEFING.md)
- [x] Item 1: Backup e exportacao completa (JSON + CSV/.zip, botao manual, backup
  automatico semanal com rotacao + envio opcional pro Telegram, `docs/BACKUP.md`)
- [x] Item 2: Resiliencia offline (fila em IndexedDB pra `/api/capture`/`/api/checkin`,
  idempotencia por `client_id` no servidor, indicador visual, sync automatico)
- [x] Item 3: Criptografia em repouso pra dado do Open Finance (`bank_accounts`/
  `bank_transactions`) e de saude (`saude_dados`/`medidas_corporais`/`medicamentos`),
  `docs/SEGURANCA.md`
- [x] Item 4: Correcao rapida de classificacao errada (reclassificar tarefa<->gasto,
  corrigir categoria em 2 toques) + aprendizado leve (contexto no prompt a partir de
  correcoes parecidas anteriores)
- [x] Integracao dos 4 itens (feitos em paralelo, 3 deles sem isolamento de verdade
  - ver "Decisoes" abaixo) + merge real do 4o via git + suite completa
- [x] Revisao independente (2 agentes, codigo/integracao e seguranca) + correcao dos
  achados reais

### Decisoes da Fase 4
- **Isolamento dos agentes em paralelo nao funcionou como esperado** (o relato virou regra
  permanente no "Protocolo obrigatorio" no topo deste arquivo - leia la antes de repetir o
  padrao): o parametro de
  worktree isolado so cobre o repositorio principal da sessao (`financeiro-construtora`),
  nao o `painel-pessoal-tdah` (diretorio irmao onde o trabalho de verdade acontece). Os
  itens 1, 2 e 3 acabaram editando o MESMO checkout ao mesmo tempo, sem isolamento real -
  o item 4 percebeu o risco sozinho e criou seu proprio `git worktree`. Resultado: nenhum
  dado se perdeu (a suite ficou verde em cada etapa), mas a integracao final precisou de
  um merge git de verdade (2 conflitos resolvidos a mao em `app.py`/`tests/test_app.py`)
  em vez de ser so "colar os 4 diffs". Registrado aqui pra uma proxima sessao saber que
  precisa isolar manualmente (`git worktree add` dentro do proprio painel-pessoal-tdah)
  se for repetir o padrao de agentes em paralelo.
- Backup automatico: local sempre (`BACKUP_DIR`, ultimos 8) + Telegram se ja configurado
  (canal que ja existe, sem pedir credencial nova).
- Fila offline: so no JS da pagina (nao no Service Worker) - Background Sync API nao
  existe no Safari/iOS, que e o aparelho principal do Alex.
- Criptografia: campo a campo com Fernet (`cryptography`), chave em `ENCRYPTION_KEY`
  (opcional - sem ela o app funciona normal, so sem essa camada extra). Escopo restrito
  ao que o pedido especificou (Open Finance + saude), nao o banco inteiro.
- Export JSON/CSV completo sai **descriptografado** (rota autenticada, mesmo nivel de
  acesso que a tela ja mostra) - so o backup `.db` bruto fica cifrado de proposito (e o
  formato pensado pra restaurar sem passar pela aplicacao). Decisao ajustada depois de um
  achado da revisao independente (o export saia ilegivel, contradizendo a propria
  documentacao).
- Aprendizado da correcao: contexto extra no prompt do Claude (nao um override
  deterministico em Python) - o "erro" pode ser o tipo inteiro da captura (tarefa vs
  gasto), entao a decisao final continua sendo da IA olhando o texto atual.

## Fase 5 - Execucao noturna orquestrada (padrao Ralph, 4 grupos em paralelo)
Tracking detalhado por historia fica em `tasks/fase5/*.json` (formato Ralph:
userStories com `passes`/`notes`) e nos `progress-grupo-*.txt` de cada agente - este
arquivo so registra o resumo/decisoes, igual as fases anteriores. Ver `CHANGELOG.md`
(entradas 26 a 31) pro detalhe tecnico completo de cada historia e da rodada de correcao.

- [x] Grupo A - nucleo do classificador de intent (US-A1 a US-A6, `docs/INTENT.md`)
- [x] Grupo B - navegacao por voz best-effort + Atalhos/Siri + fallback offline (US-B1 a
  US-B6, dependia do contrato do Grupo A)
- [x] Grupo C - 22 historias independentes (brain dump, diario de decisao, garantias,
  manutencao veicular, patrimonio consolidado, revisao trimestral/anual, modo viagem,
  modo visitante, sinal de sobrecarga, etc - ver `tasks/fase5/grupo-c-*.json`)
- [x] Grupo D - polimento visual (US-D1 a US-D3, so comecou depois de A+B+C integrados
  na main, pra nao gerar conflito em cima de tela ainda sendo criada)
- [x] Integracao dos 4 grupos na main via merge git de verdade (worktree isolado por
  grupo, seguindo o protocolo do topo deste arquivo) + suite completa a cada etapa
- [x] Revisao independente (2 agentes, codigo/integracao e seguranca) + correcao de
  todas as 6 vulnerabilidades reais encontradas (o modo visitante incompleto - achado
  pelos dois agentes de forma independente - foi o mais serio) e dos 4 itens "deve
  corrigir em breve"
- Nenhuma historia ficou `blocked` em nenhum dos 4 grupos - nenhuma pergunta pendente
  pro Alex desbloquear nada.

### Decisoes da Fase 5
- **3 regras novas viraram padrao permanente do projeto, pedidas em pleno andamento sem
  parar o que ja estava rodando**: (1) atualizar `AGENTS.md` por historia com
  padrao/pegadinha/convencao descoberta, nao so `progress.txt`; (2) `gitleaks detect`
  antes de todo commit; (3) auditoria de dependencia nova (`pip-audit`/`npm audit`) antes
  de fechar qualquer historia com lib nova; (4) smoke-test do app depois de integrar cada
  grupo (nao so o teste unitario); (5) verificacao visual headless com Playwright pra
  toda historia de UI (Chromium pre-instalado do ambiente - ver AGENTS.md pra pegadinha
  do `executable_path`); (6) todo teste/migracao roda contra copia de desenvolvimento,
  nunca o banco real - `db.garantir_banco_nao_producao()` existe por causa disso (um quase-
  incidente real, pego antes de rodar, documentado no proprio commit); (7) `.env.example`
  e o lockfile de dependencia consolidados numa passada so na integracao final.
- **Mensagens "do coordenador" durante a execucao dispararam o classificador de seguranca
  de 3 agentes diferentes** (Grupo A, C1, C2), que se recusaram a agir nelas por nao
  conseguir verificar quem realmente mandou - comportamento defensivo correto (o
  orquestrador nao tem como provar identidade pro subagente no meio da tarefa), confirmado
  como legitimo caso a caso, sem nenhum dado real em risco.
- Mesma leitura da Fase 4 sobre isolamento: cada grupo rodou em `git worktree` proprio
  dentro do `painel-pessoal-tdah` (nunca o parametro de isolamento automatico do ambiente,
  que so cobre o `financeiro-construtora`), com `pwd`/`git remote -v` conferido antes de
  qualquer escrita - sem incidente de repositorio errado nesta fase.
- Nenhuma credencial nova foi necessaria em nenhum dos 4 grupos.

## Fase 6 - Polimento de interface e centralizacao via chat (Padrao Nectar)
Tracking por historia em `tasks/fase6/*.json` (formato Ralph) + `progress-*.txt` de cada faixa.
Rollback: branch `pre-fase-6` (c838e1f). Ordem: E1+E2+E3 em paralelo -> integra -> E4+E5 em
paralelo -> integra -> F1+F2+F3 em paralelo -> integra -> revisao independente.

- [x] E1 base: bugs (manutencao unificada, lista de compras, rainbow), memoria visivel, estilo de resposta
- [x] E2 modulos: Habitos, Projetos, agenda no calendario "Painel" do iCloud, limite do cartao
- [x] E3 cards: contrato {cards, resumo_texto, passos}, registro de cards, cards simples e complexos, desfazer/link
- [x] E4 chat: brain dump em cards, consulta -> card no classificador local, ligacao dos modulos novos
- [x] E5 dia: proatividade unificada (6 textos/timings), visao do dia
- [x] F1 vida / F2 painel / F3 extra (Viagens com API de voo, Lugares com OpenStreetMap, Cotacoes, Aviacao)
- [x] Integracao + revisao independente (codigo + seguranca) + resumo final em 3 blocos

### Resultado da Fase 6 (fechada em 2026-09-23 ~22h UTC)
- 32/32 historias com passes=true, nenhuma blocked. Suite final: 1757 testes Python (so as 6
  falhas conhecidas dependentes do horario - voo/agrupamento) + 88/88 JS, gitleaks limpo.
- Revisao independente: seguranca achou 3 ALTO + 5 MEDIO + 5 BAIXO reais (modo visitante no
  Desfazer/cards de saude/memorias/agenda, XSS no popup do mapa, teto de IA fora do chat,
  envenenamento do banco de padroes, lockout atras de proxy...) - todos corrigidos com teste
  de regressao (ver CHANGELOG "correcoes da revisao independente"). Codigo: sem bloqueador.
- Em aberto (fora do escopo desta rodada, pra proxima): teto de IA tambem em /api/capture,
  lista de mala e leitura de PDF de cotacao; chat ainda aceita escrita por outras tools no
  modo visitante; texto de IA ja gravado no historico nao e mascarado; valor em R$ no push de
  limite do cartao (mantido de proposito - texto pedido pelo Alex).
- Perguntas pro Alex (nada bloqueado): (1) numero real da construtora que ja aparece no plano/
  resumo do dia (feature v3.99.14/16) deve sumir tambem, ou a regra "nunca numero da
  construtora" vale so pra resposta livre da IA? (2) agua ganha acao de intent propria ou
  continua via check-in? (3) "Guardar" no brain dump deve ja processar em cards direto?
- Credenciais novas opcionais: AVIATIONSTACK_API_KEY (status de voo em tempo real, gratis so
  com email). Variavel nova de infra: PAINEL_ATRAS_DE_PROXY=1 (Render ja configurado; ligar na
  VPS com Caddy).

### Decisoes do Alex antes de comecar (rodada unica de perguntas)
- Repositorio privado (confirmado) -> texto inicial de "O que lembro sobre voce" vai direto no codigo.
- Habitos = modulo novo (separado da Rotina guiada). Projetos = modulo generico novo; Viagens reaproveita o visual.
- Agenda escreve SO num calendario "Painel" do iCloud; nunca mexe em evento que o painel nao criou.
- Viagens: as duas coisas - linha do tempo de planejamento (regra pratica) E status de voo por numero.
- Mapa: OpenStreetMap agora (sem chave/cartao). Push real validado depois, em hospedagem que nao dorme.
- Limite do cartao: campo manual. Widget via Scriptable: mantido.
- Plugins: frontend-design (oficial) + ui-ux-pro-max (comunidade, inspecionado: so skills, sem hook/MCP).

### API de voo (Fase 6 F3, US-F12)
Pesquisado em 2026-09-23 (WebSearch - situacao "hoje", free tier muda com frequencia,
reconfirmar se isso for revisitado muito tempo depois). Comparacao completa e o raciocinio
inteiro em `tasks/fase6/progress-f3.txt` (secao US-F12) - resumo aqui:

| API | Cadastro gratuito | Limite gratis | HTTPS | Escolhida? |
|---|---|---|---|---|
| **AviationStack** | So email, sem cartao | 100 req/mes | Nao (so paga) | **Sim** |
| AeroDataBox (RapidAPI) | Pede cartao mesmo no $0/mes | 600 unid./mes (~2400 req) | Sim | Nao |
| FlightAware AeroAPI (Personal) | Nao confirmado se pede cartao | $5 gratis/mes, sem minimo | Sim | Nao |
| Amadeus Self-Service | MORTO - portal free encerrou em 2026-07-17 | - | - | Nao (nem existe mais) |

Escolhida: **AviationStack** - e a unica sem cartao de credito no cadastro gratuito
("Voce NAO consegue criar conta por ele" - cartao e decisao financeira do Alex, entao
qualquer API que exija um mesmo no plano "gratis" ficou de fora ate ele mesmo decidir
cadastrar). Troca-off aceito: o plano gratuito so aceita HTTP (nao HTTPS) - a chave viaja
sem criptografia nessa chamada especifica (documentado tambem no `.env.example`).

Variavel de ambiente: `AVIATIONSTACK_API_KEY` (`.env.example`). Chave gratuita em
https://aviationstack.com/product -> "Get Free API Key". Sem ela, o card de voo funciona
100% no modo manual (numero do voo digitado a mao) e mostra "status em tempo real:
configurar chave" - nunca quebra por falta de chave.

Se um dia o Alex quiser trocar pra AeroDataBox (limite maior, HTTPS de verdade, mas
precisa cadastrar cartao no RapidAPI primeiro): so trocar a URL/parsing dentro de
`voo_status.py` (`_buscar_na_api`/`_mapear_resposta`) - o cache (`voo_status_cache`) e o
contrato de dado que o front consome (`status_voo`) nao mudam.
