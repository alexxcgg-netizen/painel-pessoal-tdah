# Widget via Scriptable (tela inicial + tela de bloqueio)

Fase 7 (faixa N3b). Um script só — `scriptable/scriptable-widget.js` — cobre
os 4 tamanhos usando `config.widgetFamily` pra escolher o layout certo:

| Tela | Tamanho | `config.widgetFamily` |
| :--- | :--- | :--- |
| Inicial | Pequeno | `small` |
| Inicial | Médio | `medium` |
| Bloqueio | Circular | `accessoryCircular` |
| Bloqueio | Retangular | `accessoryRectangular` |

Qualquer outro valor (ex: widget Grande, ou `accessoryInline`) cai no layout
de `small` por segurança — o widget nunca fica em branco ou quebrado por
causa de um tamanho não previsto.

Busca em `GET /api/widget` (ver contrato abaixo) e guarda a última resposta
boa em disco: se a rede falhar, mostra os dados salvos com "atualizado há X"
em vez de deixar o widget vazio.

> Os scripts antigos `scriptable/widget_painel.js` e
> `scriptable/widget_lockscreen.js` (que liam `/api/atalho/resumo`) continuam
> no repositório só como referência histórica — não fazem parte deste guia e
> não devem ser usados para widgets novos.

## Passo a passo

1. Instala o app **Scriptable** (App Store, gratuito).
2. Abre o Scriptable, toca em **+** pra criar um script novo.
3. Copia o conteúdo inteiro de `scriptable/scriptable-widget.js` e cola no
   script novo.
4. No topo do arquivo, edita as duas constantes:
   ```js
   const PAINEL_URL = "http://SEU-IP-OU-DOMINIO:5001"; // <- troca aqui
   const TOKEN = ""; // <- troca aqui se configurou PAINEL_WIDGET_TOKEN no .env
   ```
   (o backend aceita o token tanto por `Authorization: Bearer <token>` quanto
   por `?token=<token>` na URL — este script usa sempre o header
   `Authorization`, que não fica visível em nenhum log de URL).
5. Roda o script uma vez dentro do próprio Scriptable (botão de play) pra
   testar — mostra uma prévia do widget.
6. **Tela inicial**: segura o dedo numa área vazia da tela → **+** → procura
   **Scriptable** → escolhe o tamanho **pequeno** ou **médio** → na
   configuração do widget que aparece, escolhe o script que você colou.
7. **Tela de bloqueio** (iOS 16+): segura o dedo na tela de bloqueio →
   **Personalizar** → toca num dos widgets abaixo do relógio → **+** →
   procura **Scriptable** → escolhe **Circular** ou **Retangular** → escolhe
   o mesmo script.

O iOS decide sozinho o intervalo de atualização do widget (o Scriptable não
controla isso) — normal levar alguns minutos pra refletir uma mudança.

## Configurando por parâmetro do widget (sem editar o script)

Em vez de editar `PAINEL_URL`/`TOKEN` toda vez (por exemplo, pra ter dois
widgets apontando pra ambientes diferentes), dá pra usar o campo
**Parâmetro** da configuração do widget no formato:

```
http://SEU-IP-OU-DOMINIO:5001|SEU_TOKEN
```

- Só a URL (`http://SEU-IP-OU-DOMINIO:5001`) também funciona, se não usar
  token.
- Quando o parâmetro está preenchido, ele sempre tem prioridade sobre as
  constantes do topo do script.

## Contrato do endpoint (`GET /api/widget`)

```json
{
  "versao": 1,
  "atualizado_em": "2026-09-23T20:10:00Z",
  "estado": "normal",
  "foco": { "titulo": "Revisar contrato", "em_minutos": 19 },
  "proxima_conta": { "nome": "Cartão", "em_dias": 3 },
  "habitos": { "feitos": 3, "total": 5 },
  "custo_ia": { "percentual_teto": 42 },
  "linhas": [
    "Foco: Revisar contrato em 19 min",
    "Conta: Cartão em 3 dias",
    "Hábitos: 3/5",
    "IA: 42% do teto"
  ]
}
```

`estado` é um de `normal`, `vazio` ou `erro`. Sem nenhum valor em R$ (o
widget nunca mostra dinheiro). O campo `linhas` já vem pronto em português,
uma linha por informação — é a fonte principal de texto do widget nos 3
estados, então o script continua funcionando mesmo que os outros campos
(`foco`, `proxima_conta`, ...) fiquem `null` em `vazio`/`erro`.

## O que cada tamanho mostra

- **Pequeno**: título "PAINEL" + as 2 primeiras linhas do contrato (foco e
  próxima conta).
- **Médio**: as 4 linhas do contrato, mais dois blocos com o número de
  hábitos (`3/5`) e o percentual do teto de IA (`42%`).
- **Circular** (bloqueio): a fração de hábitos feitos/total, monocromático
  (o iOS renderiza os widgets de bloqueio sempre em uma cor só — o script
  nunca define cor customizada nesses dois formatos, senão o iOS ignora ou
  distorce).
- **Retangular** (bloqueio): as 2 primeiras linhas do contrato, também
  monocromático.

Nos estados `vazio` e `erro`, o mesmo layout por tamanho é reaproveitado,
trocando o conteúdo pela mensagem que a API mandar em `linhas` (ou por um
texto padrão claro, se `linhas` vier vazio).

## Tema

As cores usadas (só nos tamanhos de tela inicial — pequeno/médio; tela de
bloqueio nunca leva cor customizada, ver acima) são as mesmas do app,
tiradas direto de `static/css/style.css`:

| Uso | Variável CSS | Cor |
| :--- | :--- | :--- |
| Fundo do widget | `--bg` | `#000000` |
| Fundo dos blocos de estatística | `--surface` | `#121212` |
| Texto principal | `--text` | `#eceef3` |
| Texto secundário | `--text-muted` | `#a7afbc` |
| Texto do rodapé "atualizado há X" | `--text-faint` | `#788292` |
| Destaque (título "PAINEL", estado normal) | `--cor-painel` | `#41aa75` |
| Destaque (título "PAINEL", estado de erro) | `--danger` | `#ff5c72` |

Se a paleta do app mudar no futuro, atualiza essas mesmas constantes no topo
de `scriptable/scriptable-widget.js` (`COR_BG`, `COR_SURFACE`, `COR_TEXT`,
`COR_TEXT_MUTED`, `COR_TEXT_FAINT`, `COR_ACCENT`, `COR_DANGER`).

## Cache (o que acontece quando a rede falha)

Toda busca com sucesso salva o JSON inteiro num arquivo local
(`FileManager`, `painel_widget_cache.json` nos documentos do Scriptable). Se
uma atualização seguinte falhar (sem internet, painel fora do ar, token
inválido, timeout), o widget:

1. Carrega o último JSON salvo.
2. Mostra o mesmo conteúdo de sempre (respeitando `estado`/`linhas` de
   quando foi salvo).
3. Acrescenta um texto "atualizado há X" (minutos, horas ou dias, calculado
   a partir de `atualizado_em`), pra deixar claro que aquele dado não é da
   busca mais recente.

Só quando **não existe nenhum cache ainda** (por exemplo, na primeira vez que
o widget roda sem internet) é que aparece a mensagem "Sem conexão com o
painel e sem dados salvos.".

## Testes

`tests/js/scriptable_widget.test.js` (`node --test`, ou
`scripts/testes.sh --js tests/js/scriptable_widget.test.js`) roda o script
real (`scriptable/scriptable-widget.js`) contra mocks em Node de toda a API
do Scriptable usada aqui (`Request`, `ListWidget`/`addText`/`addStack`,
`FileManager`, `config`, `Script`, `Color`, `Font`, `args`) — sem nenhuma
chamada de rede de verdade. Cobre os 4 tamanhos, os 3 estados
(`normal`/`vazio`/`erro`) e o fallback de cache (busca ok grava, busca
seguinte falha e usa o cache com "atualizado há X"), inclusive quando a
falha é uma resposta HTTP de erro (ex: `401`) e não só uma falha de rede.
