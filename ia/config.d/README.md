# ia/config.d — uma config por funcao de IA

Cada funcao de IA do app (ex.: `classify_capture`, `chat`, `extrair_nota_fiscal`) tem
um arquivo `ia/config.d/<funcao>.json`. O codigo so chama
`ia.core.chamar_ia("<funcao>", mensagens, ...)` — qual provedor/modelo atende e decidido
aqui. Trocar de modelo = editar o JSON (o cache confere o mtime, nao precisa reiniciar).

## Formato

```json
{
  "funcao": "classify_capture",
  "ativo": false,
  "modelo_atual": {"provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001"},
  "alvo": {"provedor": "openai", "modelo": "gpt-6-luna", "esforco": "medio"},
  "fallback": [{"provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001"}],
  "max_tokens_saida": 300,
  "cache": {"ativo": false, "ttl": "5m"},
  "modo": "padrao"
}
```

| Campo | Obrigatorio | O que e |
|---|---|---|
| `funcao` | nao (recomendado) | Tem que ser igual ao nome do arquivo sem `.json`. So minusculas, numeros e `_`. |
| `ativo` | nao (padrao `false`) | `false` = usa `modelo_atual` (o que ja roda hoje). `true` = usa `alvo` (a migracao). |
| `modelo_atual` | sim | `{"provedor", "modelo", "esforco"?}` do comportamento atual. |
| `alvo` | se `ativo: true` | Modelo pra onde a funcao esta migrando. |
| `fallback` | nao (padrao `[]`) | Lista tentada em ordem se a principal falhar (erro do provedor, excecao, JSON fora do schema). Entrada identica (mesmo provedor/modelo/esforco) a uma ja tentada e pulada. |
| `max_tokens_saida` | nao (padrao `1024`) | Inteiro > 0. |
| `cache` | nao (padrao `{"ativo": false, "ttl": "5m"}`) | Repassado ao adapter (cache de prompt do `contexto_fixo`). |
| `modo` | nao (padrao `"padrao"`) | Repassado ao adapter (ex.: `"padrao"`, `"lote"`). |

- `provedor`: `"anthropic"` ou `"openai"` (adapters em `ia/adapters/`).
- `esforco`: texto livre repassado ao adapter (`"baixo"`, `"medio"`). Nesta fase, nunca
  `alto`/`xhigh`/`max`. Omitido = `""` (adapter usa o padrao dele).

## Como a chamada roda (`ia/core.py`)

1. Consulta o teto mensal (`ia.teto.teto_permite`). Estourado -> `Resposta(ok=False, erro="teto_ia_estourado")`, sem chamar ninguem.
2. Tenta a principal (`alvo` se ativo, senao `modelo_atual`), depois cada `fallback`.
3. Excecao de rede/timeout no adapter -> 1 retry no mesmo modelo antes do fallback.
   Por isso **adapters devem deixar subir** (ou re-levantar) erro de conexao/timeout do
   SDK em vez de engolir em `Resposta(ok=False)`. Pra forcar, defina
   `exc.retentavel = True/False` na excecao.
4. Com `schema`, o JSON (`resp.dados`, ou `json.loads(resp.texto)`, tolerando cerca
   ```` ```json ````) precisa ser objeto e validar contra o schema (subconjunto de JSON
   Schema: `type`, `properties`, `required`, `additionalProperties: false`, `items`,
   `enum`, `const`, min/max). Invalido = falha -> proximo fallback.
5. Toda tentativa (inclusive retry/falha) vai pra `ia.medicao.registrar_uso`.
6. `resp.fallback_usado = True` quando quem respondeu nao foi a principal.

Config ausente ou mal formada levanta `ia.core.ConfigIAErro` (erro de programacao);
falha de IA nunca levanta, volta `Resposta(ok=False, erro=...)`.

## Criando uma config nova (faixas de migracao)

1. Copie o exemplo acima pra `ia/config.d/<sua_funcao>.json`, com `ativo: false` e
   `modelo_atual` = o modelo que o codigo usa hoje (comportamento identico).
2. Troque a chamada antiga por `chamar_ia("<sua_funcao>", ...)`.
3. Rode `ia.core.carregar_todas_configs()` num teste pra pegar JSON mal formado cedo.
4. So vire `ativo: true` depois de comparar qualidade/custo do `alvo`.
