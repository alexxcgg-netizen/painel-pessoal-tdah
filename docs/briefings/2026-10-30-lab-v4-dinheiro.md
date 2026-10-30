# Lab v4, Grupo E: Dinheiro (30/10/2026)

Ideias: cupom-impresso, cupom (vira itens), contas-email. Dinheiro PESSOAL do Alex, nada da construtora.

## O que entrou
- **cupom-impresso**: o card de gasto que já existia (`transacao` com `mes`/`dias`) agora imprime em 16 degraus
  (`steps(16)`, antes era deslize liso) e o total só rola (odômetro que já existia) quando o papel termina de sair
  (`cards-premium.js`, `odometro(el, espera)`). Visual só do card de gasto; nada de dado novo.
- **cupom (vira itens)**: `nfce.py` + regra local `classificador_local/regras/e_dinheiro_lab.py` + card `cupom_itens`
  (`static/js/cards-dinheiro.js`, `cards-dinheiro.css`). Cola o link do QR no chat (ou manda pelo Atalho do iPhone
  em `/api/atalho/capturar`, que já existe): o painel abre a nota na SEFAZ (só https + `*.gov.br`, timeout 8 s,
  1,5 MB, redirect fora de gov.br é recusado), separa item a item, categoriza por palavra-chave (Comida, Besteira,
  Limpeza, Suplemento, Outros; local, sem IA) e mostra o QR "lendo", a barra e uma linha por categoria. Botão
  "Registrar como gasto" (`POST /api/cupons/<id>/registrar`): cria o gasto em `expenses` (categoria mercado) ou, se
  já existe gasto do mesmo valor nos últimos 3 dias, só vincula (nunca duplica; idempotente). Pergunta
  "quanto eu gasto com besteira/suplemento/limpeza" responde pela soma dos cupons de 30 dias (`GET /api/cupons/resumo`).
  Mesmo cupom mandado 2x devolve o já lido (chave de acesso única).
- **contas-email**: `email_contas.py`, tabela `contas_email`, card `contas_email`, rotas em `rotas/dinheiro_lab.py`,
  passo `contas_do_email` no `conversa_proativa` (a cada 30 min, 9h-21h, só se ligado). Acha boleto (linha digitável
  de 47/48 dígitos, DV conferido; valor e vencimento saem do próprio código), PIX copia-e-cola (CRC16 conferido) e
  fatura sem código (só se achar valor E vencimento), e rastreio dos Correios (vai como link). Conta com vencimento vira
  tarefa "Pagar conta: X" no dia. Card: "Copiar boleto/PIX", "Já paguei" (fecha a tarefa). Chat: "olha as contas do
  e-mail" varre na hora.

## Decisões (veta quem quiser)
- Código que não passa na conferência (DV/CRC) nunca vira botão de copiar: copiar boleto quebrado é pior que nada.
- Só a chave de 44 dígitos NÃO basta (a consulta por chave pede captcha): o painel responde pedindo o link do QR.
- Registrar o gasto é um toque explícito, não automático (evita duplicar o "gastei 312 no mercado" falado antes).
- No card do e-mail a "caixa de entrada" do protótipo virou uma faixa "Li N e-mails · achei M" com a varredura passando
  (o painel só guarda o que achou, não a caixa toda).
- O link dos Correios é a página inicial do rastreio (não conferi parâmetro de link direto); o código vai pra área de transferência.
- E-mail é só dado: nada vai pra IA; senha só no `.env`; IMAP em modo `readonly` + `BODY.PEEK` (não marca lido, não apaga).
- Campos sensíveis (visitante não vê): `cupom_itens` = total/categorias/exemplos; `contas_email` = contas.

## O que ficou de fora
- **Leitura do QR dentro do app**: Safari sem BarcodeDetector e biblioteca de QR seria dependência nova. Usa-se a câmera
  nativa do iPhone (abre o link) + colar/compartilhar.
- **Layouts de outros estados**: o leitor entende a página de NFC-e mais comum (tabela `tabResult`, `txtTit`, `Rqtd`,
  `valor`, `totalNumb`). Estado com página diferente responde "não reconheci o layout" e precisa de um leitor novo
  (me manda o estado e um link). Não testei contra SEFAZ real, só HTML de exemplo inventado.
- Boleto de concessionária (48 dígitos) só confere tamanho e prefixo 8; vencimento vem do texto do e-mail.
- Boleto/fatura só em anexo PDF: não lê anexo.

## Passos do Alex
1. **E-mail (opcional, desligado até fazer):** na conta Google, ligar a verificação em 2 etapas e criar uma "senha de app"
   (https://support.google.com/accounts/answer/185833). Gmail: Configurações > Encaminhamento e POP/IMAP > IMAP ativado.
   No `.env` do painel (tu digita, eu não): `EMAIL_IMAP_USUARIO=teu@gmail.com` e `EMAIL_IMAP_SENHA_APP=<a senha de app>`
   (opcionais `EMAIL_IMAP_HOST`, `EMAIL_IMAP_PASTA`). Reiniciar o painel. Testar: no chat, "olha as contas do e-mail".
2. **Atalho do iPhone pro cupom (opcional):** Atalhos > novo atalho > ativar "Mostrar na Folha de Compartilhamento"
   (tipo URLs) > ação "Obter conteúdo da URL" apontando pra `<teu painel>/api/atalho/capturar`, método POST, corpo JSON
   `{"texto": "<URL recebida>"}` e o header `X-Webhook-Token` igual ao atalho de captura que já usas (mesmo formato dele).
   Uso: câmera do iPhone no QR do cupom > abrir > compartilhar > o atalho. Sem atalho, basta copiar o link e colar no chat.
3. Testar um cupom real e me dizer o estado; se der "layout", mando o leitor dele.
4. Integrador: conferir `CACHE_NAME` do service worker (arquivos novos já estão no `ASSETS`), CHANGELOG, `docs/CARDS.md`
   (tabela "O que já está no app": cupom_itens e contas_email; gasto agora imprime em degraus) e a suíte completa.

## Arquivos
Novos: `nfce.py`, `email_contas.py`, `classificador_local/regras/e_dinheiro_lab.py`, `rotas/dinheiro_lab.py`,
`migracoes/202610301200_e_dinheiro_cupons_contas_email.sql`, `static/js/cards-dinheiro.js`,
`static/css/secoes/hoje/cards-dinheiro.css`, `tests/test_lab4_dinheiro.py`, `tests/js/cards_dinheiro.test.js`.
Alterados: `cards.py` (builders, TIPOS_CARD, CAMPOS_SENSIVEIS), `conversa_proativa.py`, `static/js/cards-premium.js`,
`static/js/cards-vivos.js`, `static/css/secoes/hoje/cards-vivos.css`, `templates/scripts.html`, `static/css/fase7.css`,
`static/service-worker.js` (só lista ASSETS).
