# Plano: app do iPhone (.ipa) com widgets e Dynamic Island (30/10/2026)

Pedido do Alex: "planejar um app pra eu instalar no iPhone, .ipa, bem certinho com widgets, Dynamic Island, tudo bem
redondo pra se conectar no meu iPhone pra gente ir testando". Disse pra fazer tudo no Opus.

## O que já existe (conferido no código em 30/10)
- `native/ios/` (XcodeGen `project.yml`) + `.github/workflows/build-ios.yml`: app "casca" (WKWebView abrindo o
  painel + tela Configurar com endereço e token) e a extensão de widget (`native/widgetkit/`, 5 famílias: tela inicial
  pequeno/médio, bloqueio circular/retangular/linha) + botão da Central de Controle (lab v4, iOS 18).
- `GET /api/widget` (`rotas/n3a_widget.py`) com token Bearer.
- Instalação documentada em `docs/IOS_APP.md`: build na nuvem (Mac do GitHub, sem assinatura) → Sideloadly no
  Windows assina com o Apple ID dele.
- **Já compilou uma vez:** build da nuvem de 23/10 (fb8c358) passou, `.ipa` disponível até 22/11 (artefato Painel-ipa-2).
  O que veio depois (Central de Controle, ajustes da Fase 0) ainda não foi compilado.

## Os fatos que decidem o caminho
Conferido na fonte: só a lista de capacidades da Apple
(developer.apple.com/help/account/reference/supported-capabilities-ios), mas as marcações de quem tem o quê não
vieram na leitura. **Não conferido** (do que eu sei, a testar no aparelho):
- **Conta grátis (Apple ID comum):** app expira em 7 dias (Sideloadly renova sozinho com o PC ligado na mesma
  rede); **sem push da Apple (APNs)**. Widget e App Group: provável que funcionem, mas não garantido.
- **Conta paga (Apple Developer, US$ 99/ano):** 1 ano, instala pelo **TestFlight** (sem cabo, sem PC ligado),
  push da Apple, e a Dynamic Island atualizada pelo painel mesmo com o app fechado.
- **Dynamic Island = Live Activity (ActivityKit, iOS 16.1+).** Sem push ela ainda funciona: o app liga a atividade
  e o próprio iPhone conta o tempo sozinho (contagem regressiva nativa, sem gastar bateria nem rede). Então
  "sair em 23 min", "decola às 14:00", "foco 18:42", "descanso 0:45" funcionam na conta grátis. O que a grátis
  não faz: o painel mudar o conteúdo da ilha com o app fechado.
- **Push dentro do app nativo:** o Web Push do PWA não funciona dentro de WebView de app. Na conta grátis, os
  avisos continuam vindo pelo PWA na tela de início (manter os dois instalados). Na paga, o app recebe push direto.

## Proposta (fases, cada uma testável no iPhone)
1. **Fase 0: o build passar.** Rodar o workflow, corrigir o Swift até o `.ipa` sair, instalar, abrir o painel no
   app, widget mostrando dado real. Critério: ele usa o app em vez do Safari por um dia sem nada estranho.
2. **Fase 1: casca redonda.** Barra de status/área segura certa, sem "pulo" branco ao abrir, puxar pra atualizar,
   volta do segundo plano sem recarregar, microfone e câmera do chat funcionando dentro do app, haptics nativos
   nas ações do painel (ponte JS → Swift), ícone e tela de abertura do app.
3. **Fase 2: Dynamic Island (Live Activities).** Uma atividade por assunto, cada uma com a cara do card dele
   (mesma linguagem do `docs/CARDS.md`): voo (sair → chegar → decolar), compromisso (hora de sair), foco (Parceiro de
   foco), treino ao vivo (série, rep, descanso). Estados: compacta, mínima, expandida e tela de bloqueio. O painel
   manda o comando pela WebView (ponte JS) quando ele toca "começar"; o iPhone conta sozinho.
4. **Fase 3: widgets de verdade.** Revisar os 5 tamanhos com a linguagem dos cards, widget interativo (iOS 17:
   marcar tarefa/remédio feito sem abrir o app), botão da Central de Controle.
5. **Fase 4 (só conta paga): push nativo.** Avisos insistentes com botões, Dynamic Island atualizada pelo
   servidor, sem PWA.

**Protótipo primeiro** (regra da casa): antes da Fase 2/3, artefato com a Dynamic Island e os widgets desenhados
num iPhone de mentira com dado inventado, pra ele vetar o visual antes do Swift.

## Decisões dele (30/10)
- **Conta grátis** por enquanto (Sideloadly). Tudo pronto pra trocar pra paga depois sem refazer.
- **Painel de sempre + extras nativos** (WebView + ilha, widgets, haptics, microfone, câmera). Nada de telas SwiftUI.
- **Dynamic Island: os 4 assuntos** (voo, hora de sair, foco, treino) - "depende do momento aonde eu estou". Regra
  proposta: uma atividade por vez, a que estiver mais perto de acontecer ganha (treino e foco, que ele começa na mão,
  passam na frente; voo passa na frente de compromisso comum).
- **Protótipo primeiro** num artefato; Fase 0 (build passar) anda em paralelo.

## Riscos
- Sem Mac: todo erro de compilação só aparece no build da nuvem (5-10 min por volta). Repositório privado gasta
  10× os minutos grátis do GitHub em Mac: agrupar correções antes de rodar.
- Sideloadly pede a senha do Apple ID: quem digita é ele, sempre.
- App Group com conta grátis pode falhar: aí o widget não lê o token. Plano B: token embutido no próprio widget
  pela tela de configuração do widget (intent), sem App Group.
