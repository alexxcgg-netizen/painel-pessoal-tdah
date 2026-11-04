# Leva "onde eu estou" - o painel acompanha o Alex pela localização do iPhone (2026-11-04)

## Pedido
"Eu sinto que ele não me acompanha em tempo real o app" → escolheu "não sabe onde eu estou".
Decisões dele (04/11):
- **Como saber**: app nativo, automático (permissão "Sempre"), não Atalhos.
- **O que a IA faz**: "se eu chegar no mecânico ela já fala 'chegou no mecânico, próxima tarefa'; se eu
  atrasei no mecânico ela já reajusta os horários. Claro que vou ter que colocar onde fica o mecânico."

Caso real que motivou (chat de 03/11): ele foi levar o carro no mecânico de Uber e voltar pra imprimir as
contas; a IA só soube de cada passo quando ele contou, e o horário das contas passou sem ninguém reajustar.

## Como funciona
1. **iPhone (native/ios/App)**: `CLLocationManager.startMonitoringVisits()` com autorização "Sempre".
   O iOS acorda o app (mesmo fechado) quando ele chega e quando sai de um lugar onde ficou parado; o app
   manda `POST /api/localizacao/visita` com o token do widget (header, como o widget já faz) e
   `{lat, lon, precisao, chegada, saida}` (ISO 8601; `saida` nula = chegou e ainda está lá). Sem rede ou PC
   fora: guarda numa fila local (até 50, a mais velha sai) e manda quando der. Pedido de permissão e o
   estado ficam na tela Configurar (nenhum botão por cima do painel). Nada de `startUpdatingLocation`
   contínuo (bateria).
2. **Servidor**: grava a visita (tabela nova `visitas`, guarda 30 dias), reconhece o lugar comparando com
   os lugares com apelido (`vida_assistente.apelidos`, geocodificados uma vez e guardados) e casa
   (raio ~150 m).
3. **Chegou num lugar conhecido**: mensagem no chat + push/Telegram, uma por visita:
   "Chegou no mecânico. Agora é: levar o carro. Depois: imprimir as contas às 11h." Não dá baixa sozinho.
   Tarefa do lugar = tarefa de hoje, aberta, cujo título (sem acento) ou `local` contém o apelido.
4. **Atrasou**: enquanto está num lugar (visita aberta) ou ao sair dele, se `agora + trajeto até a próxima
   tarefa com hora` passa da hora dela por mais de 10 min, empurra essa e as seguintes de hoje pelo atraso
   (arredondado pra 5 min), com Desfazer, e avisa no chat + push: "Atrasou no mecânico: empurrei imprimir
   as contas pras 11h20." Não mexe em: tarefa inegociável (cadeado), voo, compromisso de agenda.
   Uma vez por tarefa por dia (sem ficar empurrando a cada 5 min); trajeto com cache.
5. **Chat sabe onde ele está**: o contexto do chat ganha "Agora (pelo iPhone): no mecânico desde 07:20"
   (ou "saiu de casa às 07:05"), pra IA não precisar perguntar.
6. **"Onde fica o mecânico"**: já existe `salvar_lugar_apelido` ("o mecânico fica na rua tal"). Ao salvar,
   geocodifica e guarda a coordenada.

## Regras
- Localização é dado sensível: fica só no banco do PC; 30 dias; coordenadas arredondadas a 4 casas
  (~11 m); nunca na URL; rota exige o token do widget (sem token = 401) e recusa visitante.
- Testes: Python (rota, token, gravação, reconhecimento, chegada, atraso + Desfazer, retenção, chat
  context). Swift não compila no Windows: build pelo workflow `build-ios.yml` depois de push (só com ok
  dele). Bump do SW se mexer em CSS/JS. CHANGELOG + índice.
- Não dá pra testar o caminho do iPhone de verdade daqui: o Alex testa depois do `.ipa` novo.
