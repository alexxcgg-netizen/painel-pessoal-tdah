# Leva "perfeição": tempo de resposta, IA e verificador (2026-11-05)

Pedido do Alex antes de dormir: "no painel veja melhorias em tempo de resposta ... esperteza da ia ... diminuir tempo
pra passar o verificador ... eu quero nível perfeição ... não me pergunte nada". Feito sem perguntar no meio (regra
das levas); as decisões ficam no fim pra ele vetar.

## Medido antes de mexer
- **Servidor:** `tests/medir_tempos.py` (cópia do banco de verdade, só leitura) chama as 131 rotas GET. Somam ~650 ms
  quentes; a mais lenta leva 44 ms. O código das rotas não era o gargalo.
- **Abrir o app:** a página puxa ~220 arquivos (106 `<script>`, 15 `<link>`, 99 `@import` no `fase7.css`). O Flask
  servia `/static/` com "no-cache" (revalida um por um) e o service worker ia à rede primeiro. No app nativo
  (WKWebView, sem App-Bound Domains) o service worker nem roda. `tests/medir_abertura.py` (Chromium, 80 ms por ida e
  volta, sem service worker como no app nativo): **2ª abertura 2,5 s, 1ª 3,3 s**.
- **Servidor engasgando:** o relatório do painel (02 a 04/11) tinha 764 avisos "Task queue depth" e 75 "connection
  limit" do waitress, todos amontoados no mesmo minuto em que o app abria.
- **Chat:** antes de chamar a IA, o contexto ia em fila ao iCloud (~4 s quando o cache de 60 s vence), à construtora
  (2 pedidos) e ao Open-Meteo. A IA em si: mediana de 2,6 s por chamada, cache de prompt já funcionando (~39 mil
  tokens lidos do cache, 2 fora dele).

## O que mudou
1. **`estaticos.py` (novo):** toda URL `/static/...` da página ganha `?v=<impressão do conteúdo>`. Com a impressão
   atual, a resposta sai "immutable" por 1 ano; o `fase7.css` sai reescrito com o `?v` de cada camada (a impressão dele
   inclui a das camadas). Também entra gzip em texto de 1 KB pra cima (a página: 183 KB → ~25 KB). SSE e downloads
   passam direto, e se algo der erro aqui a resposta sai intacta.
2. **Service worker v102:** arquivo com `?v` cuja cópia guardada tem o mesmo `X-Versao` sai do cache sem ir à rede;
   uma cópia por arquivo (o cache não cresce). O precache é baixado 8 por vez (antes ia tudo de uma vez e o waitress
   recusava conexão). Pedido com `Range` (áudio) fica com o navegador.
   **Resultado (`medir_abertura`): 2ª abertura 2,5 s → 0,31 s** (218 de ~226 arquivos do cache local); 1ª 3,3 s → 2,6 s.
3. **Chat começa a responder mais cedo:** o iCloud, a construtora e o tempo agora saem juntos (`_contexto_chat`), e
   ao tocar no campo ou no microfone o front chama `POST /api/chat/aquecer`, que põe a agenda e a construtora no cache
   antes de a mensagem sair (no máximo 1 vez a cada 30 s, não grava nada).
4. **Animação:** o carrinho do "Já saí" (card D) andava por `left`/`width` com transição renovada a cada segundo, o
   que recalculava o layout em todo quadro do trajeto. Agora anda por `transform` (`100cqw`), na mesma posição até o
   pixel (conferido em 0, 37% e 100%). O resto da auditoria não achou nada que trave: os pulsos infinitos são
   `box-shadow` em elementos pequenos (só pintura) e já respeitam `prefers-reduced-motion`.
5. **Verificador:** ver a entrada do CHANGELOG do dia (mexida nos testes de navegador mais lentos).

Testes novos: `tests/test_estaticos.py`, `tests/test_contexto_chat_paralelo.py`; `test_service_worker_real.py` agora
confere que, depois de recarregar, nenhum arquivo versionado vai à rede.

## Decisões pra ele vetar
- Cache de 1 ano só vale pra URL com a impressão atual: arquivo mudou, a URL muda junto. Nada fica velho, e o
  `CACHE_NAME` continua subindo a cada mudança de CSS/JS, como sempre.
- O aquecimento do chat busca a agenda e a construtora mesmo se ele tocar no campo e desistir (no máximo 1 vez a cada
  30 s). São os mesmos pedidos que o chat já faria.
- gzip feito no próprio Python (nível 6, sem dependência nova). Arquivo de `/static/` fica comprimido em memória até
  mudar.
- **Não feito (proposta):** trocar o xdist da fila rápida por processos separados (economiza ~10-18 s), porque um
  teste (`test_modo_visitante_telas`) depende de estado deixado por outro arquivo e precisa ser consertado antes.
  Subir o `--connection-limit` do waitress no `iniciar_painel.bat` também ficou de fora: o arquivo é dele, e com
  ~8 pedidos por abertura o limite não deve mais ser atingido.
- **Sem mudança:** barra de abas fora da tela (2 medidas de 03 e 04/11, sem dado novo do aparelho); avisos
  insistentes não vistos (regra dele: não reduzir).
