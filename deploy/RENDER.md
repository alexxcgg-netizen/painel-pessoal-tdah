# Testar o painel no iPhone pelo Render (grátis, ~10 minutos)

Isto é um **teste**, não a hospedagem definitiva (essa é a VPS do `deploy/DEPLOY.md`).
No plano grátis do Render:

- o site **dorme** depois de ~15 min sem ninguém usar. O primeiro acesso depois disso
  demora uns 30-50 segundos pra carregar. Depois fica rápido;
- os dados **somem** toda vez que o site é atualizado **e também quando ele dorme** (o disco
  do plano grátis é temporário). Ou seja: teste tudo numa sentada só, e não coloque nada
  que você não possa perder. O PIN não se perde - ele volta sozinho a cada vez que o site
  acorda (mas você vai ter que digitá-lo de novo);
- as **notificações** não vão funcionar direito (o site dormindo não manda nada).

---

## Antes de começar: escolha 2 coisas

1. **Seu PIN**: 6 números (ex: `482913`). É com ele que você entra no painel. Anote.
2. **Chave da IA (opcional)**: se quiser testar o chat/foto de nota fiscal, pegue uma chave
   em <https://console.anthropic.com> → *API Keys* → *Create Key* (começa com `sk-ant-`).
   Se não quiser agora, use a palavra `nenhuma` - o app funciona, só a parte de IA não.

## Passo 1 - Criar a conta no Render

1. Abra <https://render.com> e clique em **Get Started** (ou *Sign Up*).
2. Escolha **GitHub** e autorize com a sua conta do GitHub (a mesma do repositório).
3. O plano grátis normalmente não pede cartão. Se pedir, pare aqui e me avise.

## Passo 2 - Criar o site a partir do repositório

1. No painel do Render, clique em **New +** (canto superior direito) → **Blueprint**.
2. Se aparecer um botão para conectar o GitHub (*Connect GitHub* / *Configure account*):
   clique, escolha **Only select repositories**, marque **painel-pessoal-tdah** e confirme.
3. Na lista de repositórios, clique em **Connect** ao lado de `painel-pessoal-tdah`.
4. O Render lê sozinho as instruções que eu deixei no repositório (`render.yaml`) e mostra
   um serviço chamado **painel-pessoal-tdah** (plano *Free*).
5. Ele vai pedir **2 valores** - preencha:
   - `PAINEL_PIN_INICIAL` → o seu PIN de 6 números;
   - `ANTHROPIC_API_KEY` → a sua chave `sk-ant-...` **ou** a palavra `nenhuma`.
6. Clique em **Apply** (ou *Deploy Blueprint*).

## Passo 3 - Esperar ficar pronto (3 a 5 minutos)

1. Clique no serviço **painel-pessoal-tdah**.
2. Espere o status ficar **Live** (verde). Na aba *Logs* aparece algo como
   *"Your service is live"*.
3. No topo da página tem o endereço, algo como
   **`https://painel-pessoal-tdah.onrender.com`** (às vezes com letras extras no fim).
   Esse é o seu link.

## Passo 4 - Abrir no iPhone

1. Abra o link no **Safari** do iPhone (tem que ser o Safari, não o Chrome, pra instalar).
2. Digite o seu PIN.
3. Pra usar como aplicativo: toque no botão **Compartilhar** (quadrado com seta pra cima)
   → **Adicionar à Tela de Início** → **Adicionar**. Vai aparecer um ícone igual app.

## O que vale testar

- Navegar pelas abas, criar tarefa, gasto, entrada no diário de decisão, garantia etc.
- **Botão de comando de voz**: é o teste mais importante - ele nunca foi testado num
  iPhone de verdade. Teste tanto no Safari normal quanto no ícone da Tela de Início. Se
  aparecer a mensagem "use os Atalhos da Siri", é o comportamento esperado quando o iPhone
  não libera o microfone pro site.
- **Modo visitante**: ligar, conferir que os valores somem, desligar com o PIN.

## Se algo der errado

- **Status "Failed" (vermelho)**: abra a aba *Logs* e procure a última linha de erro:
  - `PAINEL_PIN_INICIAL invalido` → o PIN não tem exatamente 6 números. Vá em
    **Environment**, corrija o valor, salve e clique em **Manual Deploy → Deploy latest commit**.
  - `Hospedado no Render sem PIN configurado` → faltou `PAINEL_PIN_INICIAL` (o painel se
    recusa a subir sem PIN numa URL pública, de propósito). Mesmo caminho: **Environment** →
    preencher os 6 números → salvar → **Manual Deploy**.
  - `KeyError: 'ANTHROPIC_API_KEY'` → faltou esse valor. Mesmo caminho: **Environment** →
    adicionar (pode ser `nenhuma`) → salvar → **Manual Deploy**.
  - Qualquer outra coisa: copie as últimas linhas do *Logs* e me mande.
- **Página demora muito pra abrir**: normal no primeiro acesso depois de um tempo parado
  (o site estava dormindo). Espere até 1 minuto.
- **Esqueceu o PIN**: em **Environment**, troque `PAINEL_PIN_INICIAL` e faça
  **Manual Deploy** - como o banco zera no deploy, o PIN novo passa a valer.

## Atualizar ou desligar

- **Atualizar**: toda vez que algo novo entra na branch `main` do GitHub, o Render
  atualiza sozinho (e os dados de teste zeram).
- **Desligar de vez**: no serviço → **Settings** → no fim da página, **Delete Web Service**.
