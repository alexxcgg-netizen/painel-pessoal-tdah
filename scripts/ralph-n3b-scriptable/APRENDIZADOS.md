# Aprendizados - faixa N3b (widget Scriptable)

- Não havia precedente no repo de testar um script Scriptable com
  `node --test` (só o padrão de `static/js/*.js`, que exporta funções puras
  sem depender de globais do navegador/app). Scriptable roda com globais
  verdadeiros (`Request`, `ListWidget`, `FileManager`, `config`, `Script`,
  `Color`, `Font`, `args`) que não existem em Node - a solução foi setar
  `global.Request = MockRequest` etc. **antes** de dar `require()` no
  script: dentro do wrapper CommonJS, um identificador solto (`new
  Request(...)`) sem `const`/`let` local resolve pelo objeto global, então
  o script roda de verdade contra os mocks sem precisar editar uma linha
  dele. O mesmo guard `typeof module !== "undefined" && module.exports`
  (padrão já usado em `static/js/*.js`) evita que o script tente rodar
  `main()` sozinho quando é `require()`ado.
- As funções exportadas (`montarWidget`, `buscarDados`, `resolverConfig`,
  `formatarAtualizadoHaX`, ...) leem os globais **em tempo de chamada**, não
  no momento do `require()` - então um teste muda `global.config.widgetFamily`
  ou troca `global.__mockFetchHandler` entre cenários sem precisar limpar
  `require.cache` e re-exigir o módulo a cada teste. Só o `FileManager`
  mockado precisa ser recriado a cada teste (`beforeEach`) pra isolar o
  cache em memória entre casos - exceto no teste que testa o próprio
  fallback de cache, que usa **de propósito** o mesmo `FileManager` em duas
  chamadas seguidas de `montarWidget()` dentro do mesmo teste (1ª grava, 2ª
  lê).
- O contrato fixo do `GET /api/widget` não define o formato exato dos
  campos (`foco`, `proxima_conta`, `habitos`, `custo_ia`) nos estados
  `vazio`/`erro` (só o exemplo do estado `normal`, mais o enum de
  `estado`). Decisão: o widget usa `linhas` (sempre presente, já pronto em
  português) como fonte principal de texto nos 3 estados, e só usa os
  campos estruturados (`foco`, `habitos`, ...) pra coisas que precisam de
  número cru (ex: fração de hábitos no `accessoryCircular`) - com
  `seguro()` (helper de acesso defensivo) cobrindo o caso desses campos
  virem `null`. Isso evita depender de suposição sobre o schema exato de
  `vazio`/`erro` que a faixa N3a ainda vai definir.
- `docs/widget-api-widget.md` (faixa irmã N3cd) já documentava o mesmo
  endpoint pra outros apps de widget e citava o nome do env var
  (`PAINEL_WIDGET_TOKEN`) - reaproveitei o nome nos comentários deste script
  e no guia novo, pra ficar consistente entre as duas faixas (nenhuma delas
  edita `.env.example`, então isso é só documentação/comentário, não muda
  comportamento).
