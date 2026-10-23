# Leva de 22/10 - "deixar o painel mais esperto"

Pedido do Alex (22/10): "faz todos". Fonte do desenho: protótipo aprovado "Ideias do Painel"
(https://claude.ai/artifact/PSBxhssPmYstutpN3yfA82, v3 aprovada inteira) + conversa de 22/10.
Regra da casa: faz tudo, um commit por item, mostra as decisões no fim (ver memória `levas-sem-perguntar`).

## Itens, na ordem
1. **Card "como tu tá hoje?"** - ele não acha onde dizer como está. Reaproveita o check-in que já existe
   (`checkins`: energia/sono/humor 1-3, `POST /api/checkin`). Card `checkin` no chat com chips de 1 toque;
   a IA pergunta sozinha de manhã (`conversa_proativa`) e o card também sai quando ele conta pelo chat
   ("dormi mal" → ferramenta `registrar_checkin`).
2. **Aviso com botão "Feito" / "Adiar"** - testar no iPhone se o push aceita `actions` (fontes divergem).
   O aviso ganha os botões; se o iOS ignorar, o toque abre direto o card da tarefa com os mesmos 2 botões.
3. **Inegociável + Botão dia ruim + Dia que vai dar errado** (ideias 8 e 3, ligadas): cadeado na tarefa,
   dia ruim alivia o resto, alerta da manhã com 2 sinais.
4. **De onde parei** (ideia 6).
5. **Parceiro de foco** (ideia 2).
6. **Quadro dos combinados** (ideia 5) - Empresa só leitura via API da construtora, como chega.
7. **Refeição pela proteína** (ideia 7).
8. **Diário de bordo** (ideia 1) - conferir RBAC 61 antes de pôr meta por categoria; nunca "Pista", é TGL.
9. **A IA propõe o horário** (agenda + sono + rotina) e **resumo da semana com padrão + sugestão**.

Sono automático (ShutEye → Saúde → Atalho): depois, a pedido dele.

## Decisões (ele veta no fim)
- Check-in: pergunta da manhã entre 7h e 11h, uma vez por dia, só se ainda não respondeu; vem com push
  (avisos ajudam - memória `avisos-nao-reduzir`). Os 3 campos ficam no mesmo card; cada toque salva na hora.
- Check-in é dado de saúde: no modo visitante o card some os valores (como `saude_dia`).
- Diário de bordo: metas por categoria do RBAC 61.101(a)(1), conferidas no texto da Emenda 00 (PC avião, curso
  homologado): 150 h total, 20 h navegação, 10 h instrumentos (até 5 h de simulador), 5 h noturno. O protótipo dizia
  20 h de instrumentos; o certo é 10. Emendas posteriores à 00 não conferidas. "Em comando" não dá pra saber pelo
  painel: o rodapé manda conferir na CIV. Voo antigo sem resposta conta como navegação quando origem ≠ destino.
  Simulador continua fora do total (igual à CIV) e entra em instrumentos até 5 h. TGL não é categoria do RBAC: só
  conta toques. O "Pousou? quanto deu?" (`voo_horas`) virou o diário (o tempo já vem preenchido pela rota).
- IA propõe o horário (`horario.py`): 15 min de folga depois do compromisso anterior (ele pediu "mais tempo entre
  as tarefas"); tarefa com hora ocupa 30 min e voo ocupa do briefing ao debriefing; hora de costume = mediana das
  tarefas parecidas feitas com hora (2+ vezes em 90 dias); dormiu pouco (relógio < 6 h ou check-in de sono 1) =
  nada depois das 21h. A regra do prompt (escolher em vez de perguntar) já existia; agora a ferramenta aceita `dia`.
- Resumo da semana: uma sugestão só, na ordem atrasadas ≥ 3 > categoria do diário mais atrasada > dia que mais
  rendeu > água. Sem botão por enquanto (só texto); se ele quiser, vira ação.
