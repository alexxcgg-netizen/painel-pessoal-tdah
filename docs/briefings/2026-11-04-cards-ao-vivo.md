# Leva "Cards ao vivo" (D) + assistente que avisa passo a passo + Dynamic Island e widgets — 04/11/2026

## Origem
O Alex disse que os cards do chat estavam com "cara de IA" e pediu uma melhorada grande. O protótipo com 5
caminhos está em https://claude.ai/artifact/HG3Kq8ZjWrgCUfHCHLiFvh, com a fonte no scratchpad da sessão
(`cards-sem-ia.html`). Ele votou no **D · Ao vivo** e aprovou as rodadas 1, 2 e 3: "gostei de tudo". Também pediu:
"se for atualizar o app já coloca pra ele usar o dynamic island e widgets".

Do card atual, ele quer manter **o tempo**: temperatura, casaco sim/não e chuva na previsão, no date e na balada.
Ele também quer a IA agindo como **assistente de verdade**:
- de uma frase ("sexta date 19h, sábado balada 23h no Viva Beach") ela já planeja tudo;
- deixa agendada a hora de se arrumar;
- vai avisando passo a passo: se arrumar → sair → passar na casa do guri → chegar.

Pro voo: **teto, vento em nós e cabeceira em uso** de cada aeródromo da rota.

## O que dá "cara de IA" (sai do app)
- fio de luz correndo na borda e luz seguindo o dedo;
- inclinação 3D (cards-premium);
- selo aceso com brilho, chips com emoji, título em degradê;
- rótulo em MAIÚSCULAS espaçadas em todo card;
- emoji na fala da IA ("Anotado! ✨").

O "pensando" (recibo de passos) fica como está: ele já aprovou antes e não entrou no voto.

## Linguagem D (o que ele aprovou)
- **Fechado:** o card é uma pílula escura lisa, sem borda brilhante. Tem:
  - ícone num círculo com a cor do assunto (`--card-cor`);
  - título, e embaixo uma linha com o tempo quando houver (ex.: "chegar 19:00 · 18° · 60%");
  - à direita, um rótulo pequeno ("sai em", "arrumar em", "gasto", "de casa") e o valor ao vivo na cor do assunto.
- **Toque abre:** grid-rows 0fr→1fr com mola `cubic-bezier(.32,1.2,.42,1)` e conteúdo entrando com fade/blur.
  Números trocam rolando, tipo placar: só o dígito que mudou. Contagem regressiva ao vivo, segundo a segundo, no
  expandido. O front recebe SEGUNDOS até o evento, nunca a hora absoluta (regra de `tempo.py`).
- **Visual:** fonte do sistema (SF no iPhone), linhas finas (`.5px`), cantos 26–30 px, botões em pílula (o principal
  na cor do assunto), alvo ≥ 44 px. Com `prefers-reduced-motion`, nada se mexe e o card nasce no estado final.
- **Texto da IA:** curto, de gente, sem emoji. Ex.: "Fechado. Pra chegar 8h30 tu sai 8h15."

## Cenas aprovadas (o que cada card vira)
1. **Tarefa com hora e lugar.**
   - Fechado: "sai em 14 min".
   - Aberto: contagem grande; rota casa → destino com um carrinho que anda quando ele toca "Já saí"; "+10 min".
2. **Saída (date, balada, compromisso arrumado).**
   - Cadeia em 3 caixas: Se arrumar / Sair / Chegar.
   - Tempo hora a hora: 7 colunas da hora antes da chegada até a volta, com temperatura, ícone e barrinha de chuva.
     As horas de "chegada" e "volta" ficam marcadas.
   - Bloco "o que levar": guarda-chuva se a chuva for ≥ 40% na chegada; casaco se fizer ≤ 17° na volta, com o motivo.
   - Nota: "Se mudar até a hora, eu ajusto a saída e te aviso".
3. **Voo.**
   - Seletor SSBL | SBNF (os aeródromos da rota). Ao trocar, gira a pista desenhada até a direção real da
     cabeceira em uso e a seta do vento (direção magnética).
   - Números rolando: cabeceira, proa e través. Teto, visibilidade e vento em caixas.
   - Frase-veredito: través vs limite pessoal, categoria VFR/MVFR/IFR. METAR cru embaixo.
   - Linhas: sair de casa / briefing (45 min antes) / decolagem / horas no curso.
   - **SSBL é 01/19** (o Alex confirmou em 04/11). Aeródromo sem pista conferida mostra o vento sem inventar
     cabeceira, ou diz "não conferi".
4. **Gasto:** anel do mês enche até o % da categoria. Mostra quanto sobra e quanto dá por dia até o fim do mês.
5. **Concluída:** anel com um pedaço por tarefa de hoje e a lista do dia (feitas riscadas, próxima em destaque).
6. **Lugar salvo (novo):** ícone de pin, apelido + nome achado no Google + "de casa: N min" quando houver.
   Aberto: desenho do círculo de 150 m ("quando o iPhone te ver aqui dentro, eu aviso") e os botões "Não é essa" /
   "Abrir no Mapas".
7. **Chegou (atraso_lugar / onde_estou):** pílula "Na oficina · 17 min depois". A hora da próxima tarefa rola de
   09:30 → 09:45, e "Desfazer" devolve.
8. **Conta a vencer:** "deslize se já pagou", só se já existir rota de marcar paga. Senão fica o botão.

## Assistente passo a passo
- **Várias coisas numa frase:** ela registra cada compromisso na mesma rodada, cada um com hora, local e estilo
  de saída. Responde com o plano em 1–2 frases.
- **Parada no caminho** ("passo na casa do guri antes"): o compromisso ganha uma parada. A hora de sair conta casa →
  parada → destino, com 5 min parado. O aviso "hora de sair" diz "10 min até a casa do guri".
- **Sequência de avisos** de um compromisso de saída, um de cada, sem duplicar o que já existe:
  1. 15 min antes de se arrumar: "Daqui 15 min começa a se arrumar pro X. <tempo>. <o que levar>."
  2. Hora de se arrumar: "Hora de se arrumar. Tu sai HH:MM."
  3. 5 min antes de sair: "5 min pra sair. Leva <porta>."
  4. Hora de sair: "Hora de sair. N min até <parada|destino>."
  5. Chegada (onde_estou): "Chegou no guri. Saindo HH:MM vocês chegam HH:MM." / "Chegou no X."
- **Tempo que piora:** se a chance de chuva na hora da chegada passa de < 70% pra ≥ 70% (comparando com a
  previsão guardada no plano), ela adianta a saída 10 min uma vez e avisa: "A previsão piorou: X% de chuva às HHh.
  Adiantei a saída pra HH:MM."
- Os avisos não diminuem (memória "avisos-nao-reduzir"). Respeitar as paredes que já existem: inegociável e voo.

## iPhone: Dynamic Island + atividade ao vivo + widgets
- **Atividade ao vivo do próximo compromisso de saída/voo** (ActivityKit, local, sem push de APNs: conta grátis).
  O app inicia ou atualiza a atividade quando abre e quando o iOS o acorda pela localização (CLVisit).
  - Contagem com `Text(timerInterval:)`, que anda sozinha.
  - Passos Arrumar → Sair → (Parada) → Chegar, com o atual destacado.
  - Ícone e cor do assunto; tempo na chegada (temperatura e chuva).
  - Ilha compacta: ícone à esquerda e contagem à direita. Mínima: ícone. Expandida: título, próximo passo, passos
    e tempo. Tela bloqueada: igual à barra do protótipo.
  - Termina sozinha depois da chegada (staleDate/dismissal).
- **Rota nova `GET /api/ao-vivo`** (mesmo token Bearer do widget): devolve o próximo compromisso das próximas
  ~6 h, com passos em ISO, tempo e cor. É reaproveitada pelo widget.
- **Widgets:**
  - o widget de tela inicial existente ganha o próximo compromisso no jeito D (contagem e tempo);
  - widgets da **tela bloqueada**: accessoryRectangular ("Date · sai em 1h20 · 18°"), accessoryCircular (anel
    do tempo até sair) e accessoryInline.
- Não dá pra compilar Swift no Windows: o build é só pelo GitHub Actions (`build-ios.yml`), depois de push. Conferir
  `native/ios/checar_projeto.py`.

## Divisão (3 frentes em paralelo, cada uma dona dos seus arquivos)
- **Frente 1 · Cards D (PWA):** `static/js/cards*.js`, `static/css/secoes/hoje/cards*.css`, `cards.py` (dados
  novos dos builders: clima_horas, levar, cadeia, por aeródromo do voo, lugar_salvo), `docs/CARDS.md`,
  `.claude/skills/cards-ia/SKILL.md`, testes de card. Bump do SW.
- **Frente 2 · Assistente:**
  - `ia/funcoes/chat.py` (prompt e ferramentas), executores no `app.py`, `tempo.py`, `conversa_proativa.py`,
    `onde_estou.py`, migração nova (parada);
  - os avisos e o replanejamento pelo tempo, com testes.
  - Só acrescenta campos novos em `cards.py` se combinar com a Frente 1 (nome de campo no briefing de baixo).
- **Frente 3 · iPhone:** `native/**`, rota nova `rotas/ao_vivo.py` (registrada como as outras), testes da rota,
  `docs/ATALHOS.md` ou `native/widgetkit/README.md`.

Contrato de campos entre as frentes 1 e 2: o card de saída recebe `parada` ({"nome", "min_ate"}) quando houver.
O resto do dado de tempo (`clima_horas`, `levar`) a Frente 1 monta, usando `clima.previsao_na_hora` e
`clima.previsao_horaria`.

## Decisões tomadas sem perguntar (pra ele vetar no fim)
- O "pensando" fica como está.
- Cards que não estão na lista acima ganham só a casca calma: sem fio, luz, inclinação, maiúsculas nem emoji.
- "Já saí" e "+10 min" no card da tarefa:
  - "+10 min" muda a hora da tarefa pela rota que já existe;
  - "Já saí" só anima e guarda a hora (não manda nada).
- A atividade ao vivo só nasce pra compromisso de saída e voo nas próximas 6 h, nunca pra tarefa solta.
