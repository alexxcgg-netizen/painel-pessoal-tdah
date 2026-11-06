# App iOS nativo (.ipa) + widget: baixar do GitHub e instalar pelo Sideloadly

O app nativo é uma "casca" pro painel. Ele abre o painel de sempre numa WebView, com o login
pelo PIN de sempre, e traz junto o **widget nativo do iOS** (WidgetKit): tela inicial pequeno e
médio, e tela de bloqueio circular, retangular e em linha.

| Peça | Onde |
|---|---|
| App contêiner (WebView + tela Configurar) | `native/ios/App/PainelApp.swift` |
| Widget | `native/widgetkit/*.swift` (mesmos arquivos de antes) |
| Projeto Xcode | `native/ios/project.yml` (o `.xcodeproj` é gerado no CI pelo XcodeGen) |
| Build na nuvem | `.github/workflows/build-ios.yml` (Mac do GitHub, `xcodebuild`, sem assinatura) |
| Dado do widget | `GET /api/widget` (`rotas/n3a_widget.py`), com token Bearer ou sessão logada |

## 1. Antes da primeira vez (uma vez só)

1. **Token do widget no painel.** O `.env` do PC precisa de `PAINEL_WIDGET_TOKEN=` com um valor
   comprido. Sem ele, `/api/widget` sempre devolve 401 e o widget mostra erro. No painel, o
   token aparece em **Configurações → Widget do iPhone**, pra copiar no celular.
2. **Endereço que o iPhone alcança.** É o mesmo que tu já abre no Safari do iPhone.
3. **No Windows:** instala o **iTunes** (versão do site da Apple, não a da Microsoft Store) e o
   **Sideloadly** (sideloadly.io). O cabo USB serve na primeira vez.
4. **No iPhone:** em Ajustes → Privacidade e Segurança → **Modo de Desenvolvedor**, liga e
   reinicia. Essa opção só aparece depois que um app instalado por fora tenta abrir; se ainda não
   estiver lá, faz o passo 3 da parte seguinte e volta aqui.

## 2. Baixar o `.ipa` do GitHub Actions

1. Abre o repositório no GitHub → aba **Actions** → **Build iOS (.ipa)** na lista da esquerda.
2. Ele roda sozinho quando muda algo em `native/` no `main`. Pra rodar na hora, usa
   **Run workflow** → **Run workflow**. Leva uns 5 a 10 minutos.
3. Abre a execução com ✓ verde → lá embaixo, em **Artifacts**, baixa **Painel-ipa-N**.
4. O GitHub entrega um `.zip`; extrai e fica o **`Painel.ipa`**.

Se a execução ficar vermelha, baixa o artefato **xcodebuild-log-N**: as linhas com `error:`
dizem o que quebrou.

> Repositório **privado**: cada minuto de Mac nas Actions conta como 10 minutos da cota grátis
> do GitHub. Por isso o build só roda quando muda `native/` ou na mão, nunca a cada commit.

## 3. Instalar no iPhone com o Sideloadly (conta Apple grátis)

1. Liga o iPhone no PC pelo cabo, desbloqueia e toca **Confiar**.
2. Abre o Sideloadly. Arrasta o `Painel.ipa` pro ícone de IPA, confere que o iPhone aparece em
   **iDevice** e digita teu **Apple ID** no campo de cima.
3. Clica **Start**. Ele pede a senha do Apple ID (e o código de 2 fatores, se pedir). Quem digita
   é tu, direto no Sideloadly. A senha não passa pelo painel nem por mim.
4. No iPhone: **Ajustes → Geral → VPN e Gerenciamento de Dispositivo** → toca no teu Apple ID →
   **Confiar**.
5. Abre o app **Painel**. Na primeira vez abre a tela **Configurar**:
   - **Endereço do painel:** o mesmo do Safari.
   - **Token do widget:** o que tu copiou em Configurações → Widget do iPhone.
   - **Salvar** → o painel abre; entra com o PIN como sempre.
6. Pra mudar endereço ou token depois: **segura o ícone do app → Configurar**.
7. **Widget:** segura a tela inicial → **+** → "Painel". Na tela de bloqueio: segura →
   Personalizar → toca embaixo do relógio → "Painel".

## Instalar já configurado

`.venv/Scripts/python.exe scripts/ipa_com_endereco.py` pega `data/app-ios/Painel.ipa`, grava o endereço do painel
(`APP_URL_PUBLICA` do `.env` ou o `tailscale serve` da porta 5001) dentro dele e deixa em Downloads. O app abre direto no painel; depois do PIN ele busca o token sozinho
(`/api/widget/instalacao`). Essa cópia é só deste PC: o endereço nunca vai pro GitHub e o token não entra no arquivo.

## Gerar relatório (o que o app consegue fazer neste iPhone)

Segura o ícone do app → **Configurar** → **Gerar relatório**. Mostra aparelho, validade da assinatura, App Group,
widgets, Dynamic Island, permissões, conexão com o painel e o que a página consegue fazer dentro do app. Vai sozinho
pro painel (`POST /api/widget/relatorio`, token do widget; fica em `diagnostico_cliente`, tipo `app_ios`) e aparece
na skill `relatorio-painel`. Sem painel no ar: **Copiar tudo** e colar no chat. Endereço e token não entram.
**Testar a Dynamic Island** liga uma contagem de 2 minutos; ela só aparece fora do app.

## Avisos do app (sem push da Apple)

A conta grátis não tem push remoto (APNs). O app agenda **aviso local** dos avisos de hora conhecida (se arrumar,
hora de sair, tarefa com hora, voo), pegando a lista em `GET /api/app/avisos`. O iPhone toca na hora mesmo com o app
fechado e o PC desligado. O que não tem hora marcada continua no push do navegador (PWA). Detalhes e decisões:
`docs/briefings/2026-11-06-avisos-app.md`. Em Configurar → **Avisos do app**: permissão, quantos estão agendados,
última conferida e o botão **GPS sempre ligado** (desligado por padrão; gasta bateria).

## Limites da conta Apple grátis

Não achei fonte oficial da Apple nem do Sideloadly pra estes números; são relatos da comunidade.

- **O app expira em 7 dias.** Depois disso não abre até reinstalar. O Sideloadly tem
  **auto-refresh**, que renova sozinho enquanto o PC estiver ligado e o iPhone na mesma rede Wi-Fi
  (ou no cabo). Sem isso, é só repetir o passo 3 com o mesmo `.ipa`.
- **No máximo 3 apps instalados por fora** ao mesmo tempo, e cada extensão gasta um "App ID".
  O widget é uma extensão, então este app gasta 2.
- **Widget e App Group podem não funcionar com a assinatura grátis.** O widget lê endereço e
  token por um App Group (`group.com.alexxcgg.painel`), e a assinatura grátis pode não liberar
  isso. Se o app abrir mas o widget ficar sempre em "Configure o painel no app", é isso. O
  caminho aí é a conta Apple Developer paga (US$ 99/ano). O app em si (o painel na WebView)
  funciona nos dois casos.

## O que foi conferido e o que não foi

- **Conferido aqui:** `/api/widget` com testes (token Bearer, `?token=`, sessão logada e modo
  visitante barrado); `project.yml` e workflow são YAML válido.
- **Não conferido:** a compilação do Swift. Não há Mac neste PC e os arquivos de
  `native/widgetkit/` nunca tinham sido compilados (ver o README de lá). A **primeira execução
  do workflow é o primeiro build de verdade**: é provável que precise de um ou dois ajustes
  pequenos, que aparecem no log.
