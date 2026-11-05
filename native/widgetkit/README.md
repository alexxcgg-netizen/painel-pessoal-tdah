# Widget nativo iOS (WidgetKit) — faixa N3e

> **Status: código PREPARADO, não compilado, não testado.** Esta faixa (`n3e-widgetkit`,
> Fase 7) rodou num ambiente Linux sem Mac e sem Xcode — não existe forma de compilar,
> rodar no simulador ou validar em dispositivo aqui. Os arquivos `.swift` abaixo foram
> escritos e revisados por leitura cuidadosa da API pública do WidgetKit/SwiftUI/Foundation
> documentada pela Apple, seguindo o mesmo contrato JSON que os outros widgets do painel já
> usam (`scriptable/widget_lockscreen.js`, `docs/WIDGET_TELA_BLOQUEIO.md`). **Antes de usar de
> verdade**: abra num Mac com Xcode, resolva qualquer erro de compilação, confira o preview
> das 5 famílias e teste num dispositivo real (a tela de bloqueio não funciona no simulador
> antigo de forma confiável).

> **Atualização 2026-10-22:** o endpoint `/api/widget` já existe (`rotas/n3a_widget.py`, token
> Bearer ou sessão) e o projeto Xcode agora sai pronto do CI: `native/ios/project.yml` (XcodeGen) +
> `.github/workflows/build-ios.yml` geram o `.ipa` com app + este widget. Instalar pelo Windows:
> `docs/IOS_APP.md`. O passo a passo do PWABuilder abaixo fica como alternativa.

## Widgets nativos da tela de início + pareamento (2026-11-05)

Leva `docs/briefings/2026-11-05-widgets-ios.md`, a partir dos votos no protótipo "Widgets e ícone".

- **O conserto do "Configure a URL do painel no app":** a assinatura grátis do Sideloadly corta o App Group,
  então o widget não enxerga o que o app guardou. Agora o **endereço** vem do arquivo `Painel-endereco.txt`
  que `scripts/ipa_com_endereco.py` grava também dentro da extensão (`PainelConfig.enderecoDeFabrica`), e o
  **token** vem do **pareamento por código**: o widget mostra 4 números, o app (que tem o token) pergunta
  "Liberar este widget?" (`native/ios/App/ParearWidget.swift`), o painel entrega o token uma vez pro widget
  (`rotas/widget_ios.py`). O token nunca vai dentro do `.ipa`.
- **Widgets (todos leem `GET /api/widget`, um provedor só, `PainelDados.swift`):** Próximo (pequeno, kind
  `PainelWidget`), Proteína (pequeno + medidor da tela bloqueada), Dia (médio), Voo (médio), Hoje (grande, com
  caixinha que marca feito), Água (pequeno, com +), Horas de voo (pequeno + medidor), Conta (pequeno).
- **Toque sem abrir o app (iOS 17+):** `IntentsDoWidget.swift` (`POST /api/widget/tarefa/<id>`,
  `POST /api/widget/agua`). Muda o cache primeiro (redesenha na hora), desfaz se o painel não responder.
- **Visual:** jeito dos widgets da Apple (`PainelEstilo.swift`): branco/#1C1C1E, cores do sistema, SF Rounded
  nos números, `containerBackground` (o sistema tira no vidro, no tingido e no StandBy) e `.widgetAccentable()`.
- **Tela bloqueada:** `ProximoCompromisso.swift` virou "Sair às 18:45 / lugar · 25 min de carro"; sem
  compromisso, mostra o próximo voo (a linha em cima da hora: "✈ sáb. 07:30").

### Como instalar e ligar
1. Depois do build: `.venv/Scripts/python.exe scripts/ipa_com_endereco.py` e instala pelo Sideloadly.
2. Abre o app com o PIN uma vez (o token do app vem sozinho).
3. Adiciona os widgets (tela de início → segura → Editar → Adicionar widget → Painel). Na primeira vez eles
   mostram um código (o mesmo em todos, é um pedido só); abre o app e toca **Liberar** (o código do alerta é o
   do widget). Liberou uma vez, todos os widgets da extensão usam o mesmo token.
4. Pilha inteligente (horas + conta): arrasta um widget pequeno em cima do outro.

## Atividade ao vivo + widgets do próximo compromisso (2026-11-04)

Leva "Cards ao vivo" (`docs/briefings/2026-11-04-cards-ao-vivo.md`). O próximo compromisso de **saída ou
voo** das próximas 6 h vira uma atividade ao vivo (tela bloqueada + Dynamic Island) e aparece nos widgets.
Tudo local, sem push de APNs (conta Apple grátis).

- **Dado:** `GET /api/ao-vivo` (`rotas/ao_vivo.py`), com o mesmo token Bearer do widget. Devolve
  `{"ativo": false}` ou o compromisso com `passos` (Arrumar → Sair → Parada → Chegar, ISO com fuso),
  `cor`, `icone` (SF Symbol), `lugar` (só o apelido, nunca o endereço), `clima` na chegada, `levar` e `fim_em`.
- **`CompromissoAtributos.swift`** (entra nos DOIS alvos, ver `project.yml`): `ActivityAttributes` +
  `ContentState`, o `Codable` da resposta e a busca/cache no App Group.
- **`AtividadeCompromisso.swift`**: o desenho. Tela bloqueada = a barra do protótipo D (pílula escura,
  ícone na cor do assunto, contagem à direita, fileira de passos com o de agora em destaque). Ilha:
  compacta (ícone | contagem), mínima (ícone), expandida (título, próximo passo, passos, tempo).
- **`ProximoCompromisso.swift`**: widgets da tela bloqueada (retangular, circular com anel até o próximo
  passo, em linha). A timeline ganha uma entrada em cada virada de passo.
- **`PainelWidget.swift`**: o widget da tela inicial mostra o compromisso no topo (pequeno: no lugar do foco;
  médio: faixa em cima, o resto embaixo).
- **App (`native/ios/App/AoVivo.swift`)**: busca a rota quando o app abre/volta, quando pega o token depois
  do PIN e quando o iOS acorda o app por uma visita (`Localizacao.swift`). Liga (só com o app aberto: regra do
  iOS), atualiza (mesmo `id`) ou encerra (chegou: fica até `fim_em`; sem compromisso: some na hora).

### Como testar no iPhone
1. Instala o `.ipa` novo (o build do GitHub Actions) e abre o app uma vez com o PIN (o token vem sozinho).
2. Ajustes do iPhone → Painel → **Atividades ao Vivo** ligado (ou a tela "Gerar relatório" do app mostra
   "Atividades ao vivo: ligadas").
3. Cria um compromisso de **saída** pra daqui a menos de 6 h (ex.: no chat "date às 21h no centro", ou uma
   tarefa com hora e local) ou um voo de hoje com hora.
4. Abre o app (ou tira e volta pro app). Vai pra tela inicial: a ilha mostra o ícone e a contagem.
   Segura a ilha pra abrir a expandida. Bloqueia o iPhone: a barra com os passos aparece embaixo.
   Dentro do app ela não aparece (regra do iOS).
5. Tela bloqueada → segura → **Personalizar** → toca na área de widgets abaixo do relógio → **+** →
   "Painel" → "Próximo compromisso" (retangular, circular ou em linha).
6. Pra conferir a rota sem o iPhone: `curl -H "Authorization: Bearer <token>" <endereço>/api/ao-vivo`
   (o token e o endereço ficam só no teu PC/iPhone, nunca em arquivo do repositório).

Limites conhecidos (sem push): a contagem anda sozinha, e a fileira de passos avança quando o iOS redesenha
a atividade (o `staleDate` é o próximo passo). Se o app ficar fechado e sem visita até depois da chegada, a
atividade só some quando o app abrir de novo, ou depois de 8 h (limite do iOS).
O teste da ilha da tela "Gerar relatório" (`IlhaTeste*.swift`) continua lá, separado.

## O que tem aqui

| Arquivo | Papel |
|---|---|
| `PainelWidget.swift` | Provedor comum (`PainelProvedor`, a cada ~20 min + viradas da agenda e meia-noite) e o widget Próximo (kind `PainelWidget`). |
| `PainelDados.swift` | Modelo `Codable` do JSON de `/api/widget`, carga com cache de 90 s, pareamento por código (`actor Pareamento`). |
| `PainelEstilo.swift` | Cores, fundo, margem e peças repetidas no jeito Apple; tela do código de pareamento. |
| `WidgetsCorpo.swift` / `WidgetsDia.swift` / `WidgetsVoo.swift` | Proteína e Água / Dia, Hoje e Conta / Voo e Horas de voo. |
| `IntentsDoWidget.swift` | Toques do widget interativo (marcar tarefa, +1 copo). |
| `PainelWidgetBundle.swift` | Ponto de entrada `@main` da extensão (`WidgetBundle`; os da tela de início num pacote aninhado). |
| `Config.swift` | Endereço (cofre ou arquivo de fábrica) e token (cofre, vindo do pareamento) do painel; último payload bom. |
| `CompromissoAtributos.swift` | Atributos da atividade ao vivo + resposta de `/api/ao-vivo` (app e widget). |
| `AtividadeCompromisso.swift` | Desenho da atividade ao vivo (tela bloqueada e Dynamic Island). |
| `ProximoCompromisso.swift` | Widgets da tela bloqueada do próximo compromisso. |
| `IlhaTeste*.swift` | Atividade de teste da tela "Gerar relatório". |
| `PainelControle*.swift` | Botão da Central de Controle (iOS 18). |

Nenhum desses três arquivos faz parte do alvo principal do app — todos são pensados pra
viver dentro de um **Widget Extension target** separado, dentro do projeto Xcode gerado a
partir do PWA (passo a passo abaixo).

## Contrato JSON (`GET /api/widget`)

```json
{
  "versao": 1,
  "atualizado_em": "2026-09-23T20:10:00Z",
  "estado": "normal",
  "foco": {"titulo": "Revisar contrato", "em_minutos": 19},
  "proxima_conta": {"nome": "Cartão", "em_dias": 3},
  "habitos": {"feitos": 3, "total": 5},
  "custo_ia": {"percentual_teto": 42},
  "linhas": [
    "Foco: Revisar contrato em 19 min",
    "Conta: Cartão em 3 dias",
    "Hábitos: 3/5",
    "IA: 42% do teto"
  ]
}
```

Autenticação: header `Authorization: Bearer <token>`. `foco`, `proxima_conta`, `habitos` e
`custo_ia` são opcionais (podem vir `null` quando não há nada pra mostrar naquele bloco);
`linhas` é a versão já pronta em texto, usada pelas famílias de tela de bloqueio
(`accessoryRectangular`/`accessoryInline`), do mesmo jeito que `resumo_curto`/`linha_extra`
já funcionam hoje em `/api/atalho/resumo` (ver `docs/WIDGET_TELA_BLOQUEIO.md`).

**Nota de escopo desta faixa**: o endpoint `/api/widget` em si (rota Flask, cálculo do JSON)
**não faz parte** desta faixa — os arquivos aqui só consomem o contrato acima, definido no
prompt da tarefa. Confira no `CHANGELOG.md`/`TODO.md` se outra faixa já implementou essa
rota antes de apontar `Config.swift` pra produção; se ainda não existir, o widget nativo
segue "preparado, mas sem dado real pra mostrar" (vai cair no estado de erro "Painel
respondeu com erro" até a rota existir).

## Cores (tema escuro, lido de `static/css/style.css`)

Nenhuma cor foi inventada — vieram direto do `:root` do CSS real do painel:

| Uso no widget | Variável CSS | Hex |
|---|---|---|
| Fundo | `--surface` | `#121212` |
| Texto principal | `--text` | `#eceef3` |
| Texto secundário | `--text-muted` | `#a7afbc` |
| Texto apagado (rótulo/label) | `--text-faint` | `#788292` |
| Destaque (accent) | `--cor-painel` (esmeralda) | `#41aa75` |
| Erro | `--danger` | `#ff5c72` |
| Borda | `--border` | `rgba(218,226,243,0.09)` |

`--cor-painel` foi escolhido como accent (em vez de `--accent` global, que é um grafite
quase neutro `#45454a` — ver comentário "Round 8" no topo do `style.css`) porque este widget
é um resumo geral do painel — mesma lógica de identidade de cor por aba que o app web já usa
(`--glass-tint: var(--cor-painel)` na aba Painel).

Nas famílias de **tela de bloqueio** (`accessoryCircular`/`accessoryRectangular`/
`accessoryInline`) o próprio iOS renderiza tudo **monocromático** e ignora cor customizada —
mesma observação já registrada pro widget Scriptable em `docs/WIDGET_TELA_BLOQUEIO.md`. Por
isso essas três views em `PainelWidget.swift` usam só `.primary`/`.secondary`/ícones SF
Symbols, nunca `PainelCores`.

## Passo a passo (fazer num Mac com Xcode)

### 0. Pré-requisitos
- **Mac com Xcode** (versão recente — WidgetKit precisa de Xcode moderno; famílias
  `accessory*` de tela de bloqueio exigem iOS 16+ como deployment target).
- **Conta Apple Developer paga** (US$ 99/ano) **só é necessária pra instalar num iPhone
  físico fora do simulador** e pra publicar na App Store — rodar no simulador do Xcode
  funciona com conta Apple grátis, mas widget de tela de bloqueio no simulador é limitado
  (vale testar direto num iPhone real assim que possível).
- Node.js (pra rodar o PWABuilder CLI) ou acesso a [pwabuilder.com](https://www.pwabuilder.com/)
  pela web.

### 1. Gerar o projeto Xcode a partir do PWA (PWABuilder)
1. Rode o painel publicamente acessível (URL https, com `manifest.json` e service worker
   válidos — já existem em `static/`) ou use a URL de produção.
2. Em [pwabuilder.com](https://www.pwabuilder.com/), cole a URL do painel e deixe ele
   analisar o manifest/service worker.
3. Na aba **iOS**, gere o pacote (**"Package for stores" → iOS**). O PWABuilder empacota o
   PWA como um app WKWebView nativo e entrega um projeto Xcode pronto (`.xcodeproj` ou
   workspace, dependendo da versão do gerador).
4. Baixe o pacote, extraia, e abra o `.xcodeproj`/`.xcworkspace` gerado no Xcode.

> A tela exata do PWABuilder muda de vez em quando (é um produto da Microsoft, atualizado
> com frequência) — se os nomes dos botões não baterem exatamente com o passo 3, procure por
> "Package for iOS"/"Generate iOS package" na aba de plataformas.

### 2. Adicionar o Widget Extension
1. No Xcode, com o projeto do PWABuilder aberto: **File → New → Target…**
2. Escolha o template **Widget Extension** (categoria iOS).
3. Nome sugerido: `PainelWidgetExtension` (o nome do *produto*; o `kind` interno do widget já
   está fixo como `"PainelWidget"` em `PainelWidget.swift`, não precisa bater com o nome do
   target).
4. **Desmarque** "Include Configuration Intent" (este widget não usa `AppIntent` de
   configuração — a configuração vem do App Group, não de um menu de opções do widget).
5. O Xcode cria um grupo/pasta com um `<Nome>.swift` de exemplo — **apague o conteúdo
   gerado automaticamente** (ou o arquivo inteiro) e cole os três arquivos desta pasta:
   `PainelWidget.swift`, `PainelWidgetBundle.swift`, `Config.swift`.
6. Confirme que os três arquivos têm **Target Membership** marcado só pro target da extensão
   (`PainelWidgetExtension`), não pro app principal.

### 3. Configurar o App Group
O widget roda num processo separado do app principal e só enxerga `UserDefaults` compartilhado
via **App Group** — é assim que ele descobre a URL/token do painel (ver `Config.swift`).

1. No target do **app principal** (o gerado pelo PWABuilder): **Signing & Capabilities → + Capability
   → App Groups**. Adicione um grupo, ex: `group.com.<seubundleid>.painel` (o identifier
   precisa começar com `group.` e geralmente incluir o bundle id do app pra ser único).
2. Repita no target da **extensão de widget** (`PainelWidgetExtension`): mesma capability,
   **mesmo identifier exato**.
3. Em `Config.swift`, ajuste `appGroupID` pro identifier real escolhido (o arquivo vem com um
   placeholder `"group.com.alexxcgg.painel"` — troque).
4. No app principal, crie (ou reaproveite) uma tela de configurações que grave, no
   `UserDefaults(suiteName: appGroupID)`, as duas chaves que `Config.swift` lê:
   - `painel_widget_url_base` (string, ex: `"https://painel.example.com"`, sem barra final)
   - `painel_widget_token` (string, o token do `Authorization: Bearer`)

   Isso não veio pronto nesta faixa — é UI do app principal (fora do escopo `native/widgetkit/`
   desta faixa), só o *contrato* de onde o widget vai ler está definido em `Config.swift`.

### 4. Compilar, rodar, testar
1. Selecione o esquema (`Scheme`) do **app principal** (não da extensão) e rode num
   simulador ou dispositivo — isso instala os dois (app + extensão) juntos.
2. Adicione o widget: segura o dedo na tela inicial → **+** (canto superior) → procura
   "Painel" → escolhe o tamanho (pequeno/médio) → adiciona.
3. Pra tela de bloqueio (iOS 16+): segura o dedo na tela de bloqueio → **Personalizar** →
   toca num widget abaixo do relógio → **+** → procura "Painel" → escolhe
   circular/retangular/em linha.
4. **Instalar num iPhone físico fora do simulador exige conta Apple Developer paga**
   (assinatura de código com um Team válido em Signing & Capabilities). Sem isso, dá pra
   rodar só no simulador do Xcode (que não simula bem a tela de bloqueio).

## O que NÃO está pronto / próximos passos de quem for compilar

- **Compilação nunca foi tentada** — é bem provável que apareça pelo menos 1-2 erros triviais
  (import faltando, nome de API que mudou entre versões do SDK, etc.) na primeira tentativa;
  revise contra a documentação oficial do WidgetKit no Xcode instalado, não confie cegamente
  neste comentário.
- A **tela de configurações do App Group** (onde o Alex digita URL/token) não existe ainda —
  fica fora do escopo desta faixa (`native/widgetkit/**` só cobre a extensão de widget em si).
- O endpoint `GET /api/widget` em si também é de **outra faixa** (ver nota em "Contrato JSON"
  acima) — confirme se já existe antes de testar contra o painel de verdade.
- Ícone do widget, cor de tema do app principal (accent color do iOS), e qualquer ajuste de
  App Transport Security (se a URL do painel for `http://` puro numa rede local, precisa de
  exceção de ATS no `Info.plist` do app principal — não incluso aqui) ficam por conta de quem
  compilar.
