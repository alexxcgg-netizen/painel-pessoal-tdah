# Leva: widgets nativos do iPhone + ícone novo (2026-11-05)

Origem: o Alex mandou print dos widgets mostrando "Configure a URL do painel no app" (tela de início e tela
bloqueada) e pediu: resolver isso, criar vários widgets, trocar o ícone, "mais cara da Apple, premium, não IA".
Protótipo: artefato "Widgets e ícone" (rodada 2, https://claude.ai/artifact/Ji8mm1fFo6hD7tUUKpwNS8), votos no
banco do artefato (`widgets/alex`).

Votos: ícone **mostrador**; widgets **todos** (próximo, proteína, dia, voo, hoje com caixinha, água, horas, conta);
tela bloqueada **todos** (linha, retângulo, medidor de proteína, medidor de horas); **StandBy**; aparência que ele
usa: **escuro**. Nota dele: "muito bom gostei de todos e da pra adicionar muito mais opcoes da eu vou trocando".
Os itens "cara de IA" ficaram sem voto: não mexi neles.

## Causa do "Configure a URL"
O `.ipa` é assinado pelo Sideloadly com conta grátis, que corta o App Group. O widget roda em outro processo e
`UserDefaults(suiteName:)` devolve um cofre só dele: nunca via a URL nem o token que o app gravou.

## Conserto
- **Endereço:** `scripts/ipa_com_endereco.py` grava `Painel-endereco.txt` também dentro de
  `PlugIns/PainelWidgetExtension.appex/`; `PainelConfig.enderecoDeFabrica` lê de lá.
- **Token por pareamento** (`rotas/widget_ios.py`): o widget sem token faz `POST /api/widget/parear {id}` e mostra
  o código de 4 números; o app, ao abrir, olha `GET /api/widget/parear/pendentes` (com o token dele) e pergunta
  "Liberar este widget?" com o mesmo código; `POST /api/widget/parear/liberar {codigo}`; o widget busca
  `GET /api/widget/parear/<id>` e recebe o token **uma vez** (depois o pedido some). O token nunca vai no `.ipa`.
  Limites: 3 pedidos abertos, 12 por hora, 10 min de validade; pedidos ficam só na memória do servidor.
  `/api/widget/instalacao` continua só com sessão.

## O que entrou
- **Servidor:** `/api/widget` ganhou `agua`, `horas_voo`, `hoje` (tarefas do dia com id, pra caixinha), `voo`
  (próximo voo em 7 dias; até 2 dias antes, condição, vento e 6 horas de previsão do Open-Meteo no aeródromo de
  saída) e `fim` nos itens da agenda. Rotas de toque: `POST /api/widget/tarefa/<id> {feita}` e
  `POST /api/widget/agua`. Testes: `tests/test_widget_ios.py`.
- **Widgets (Swift, `native/widgetkit/`):** Próximo (pequeno), Proteína (pequeno + medidor), Dia (médio), Voo
  (médio), Hoje (grande, caixinha marca feito sem abrir o app no iOS 17+), Água (pequeno, + registra copo),
  Horas de voo (pequeno + medidor), Conta (pequeno). Tela bloqueada: retângulo novo e linha com o voo.
- **App:** alerta "Liberar este widget?" (`native/ios/App/ParearWidget.swift`); ao abrir, o app manda os widgets
  se atualizarem.
- **Ícone mostrador:** `scripts/icone_mostrador.py` gera o SVG/PNGs do PWA (escuro) e o ícone do iOS em 3
  versões (claro, escuro, tingido).

## Decisões tomadas sem perguntar (pra ele vetar)
1. Widget de voo **sem categoria VFR/IFR** (só a previsão do Open-Meteo): o METAR/TAF é lento pro widget.
2. Pedidos de pareamento só na memória (reiniciar o painel derruba um pedido aberto; o widget pede outro).
3. Água sozinha não conta como "tem dado" (todo dia tem meta).
4. A conta do widget é a mesma "próxima conta" que já existia (pessoal ou da construtora, só nome e dias).
5. As famílias de tela bloqueada saíram do widget "Painel" antigo (o "Próximo compromisso" e os medidores cobrem):
   os widgets que ele já tinha colocado precisam ser colocados de novo.
6. A pilha (horas + conta) ele monta arrastando um em cima do outro no iPhone (não dá pra criar por código).
7. Ícone: claro por padrão no iOS, com versões escura e tingida; o PWA usa o escuro.
8. Retângulo da tela bloqueada sem a contagem andando (como no protótipo votado: "Sair às 18:45"); a contagem
   continua na atividade ao vivo e no circular.

## Como testar
1. Build no GitHub (precisa do "pode subir"), `scripts/ipa_com_endereco.py`, Sideloadly.
2. Abre o app com o PIN; adiciona os widgets; eles mostram um código (o mesmo em todos); abre o app e toca
   Liberar.
3. Toca numa bolinha do "Hoje" e no "+" da Água: muda na hora e aparece no painel.
