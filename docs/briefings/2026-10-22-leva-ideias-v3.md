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
