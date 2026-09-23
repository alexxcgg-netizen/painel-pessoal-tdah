# TODO - execucao do BRIEFING.md

Arquivo de progresso pra retomar depois de qualquer interrupcao (regra 2 do
`BRIEFING.md`). Ordem: Fase 1 -> Fase 2 -> Fase 3, sem parar pra perguntar.
Marque `[x]` ao terminar cada item (com commit). Decisoes tomadas por
julgamento proprio ficam na secao "Decisoes" no fim.

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
- **Isolamento dos agentes em paralelo nao funcionou como esperado**: o parametro de
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
