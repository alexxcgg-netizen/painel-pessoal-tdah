### Fase 7 - faixa C3c (polimento visual de Finanças)

Gastos (com Assinaturas e parcelas), Bancos, Construtora e Contas pessoais (aba
Vida). Sem cor, fonte nem animação nova (decisão do Alex).

- **Bottom sheets só pelo componente da V0d.** Saíram a moldura provisória
  `.bottom-sheet-financas`, o pegador duplicado e o fallback local de
  abrir/fechar, que pintavam a moldura do componente real e deixavam o título
  do sheet de parcela fora da tela. O foco vai para o 1º campo ao abrir.
- **Formulários com validação própria em pt-BR** (`novalidate`), com o erro
  dentro do sheet (texto `--danger` + ícone). O valor em R$ aceita vírgula e
  milhar (`21,90`, `1.234,56`). Teto de R$ 100 milhões, 1 a 600 parcelas,
  data da 1ª parcela entre 2000 e 2100, dia de cobrança de 1 a 31. Salvar em
  duplo clique não duplica o lançamento. O botão final diz o que faz ("Salvar
  conta").
- **Toque de 44px e botões do contrato.** Saíram os botões nativos cinza
  (Cancelar/Apagar/Paga/Salvar limite/Salvar teto): agora são
  `.btn.btn-secundario`, e "apagar" virou ícone de 44px. O chip de categoria
  do gasto virou `<button>`, com a área de toque completada por `::after`.
  Campos com `.campo` e 44px de altura.
- **Números em mono e sem estouro em 390px.** R$ em `--font-tech` nas linhas,
  chips e frases (fim do mês, resumo semanal, patrimônio, metas). O nome da
  conta pessoal ou assinatura quebra em vez de sumir com reticências, e o
  valor vai para a linha de baixo.
- **Contraste:** valores que usavam a cor da aba em texto (3,2 a 4,0:1)
  passaram para `--text`. A cor da aba fica numa barra de 3px e no ícone.
- **Construtora:** mostra só entradas, gastos e o tempo até a próxima conta.
  `construtora.js` lê só `tot_entradas`/`tot_saidas` (lista branca) e
  descarta lucro, margem e VGV, mesmo que venham no JSON. Quando a rota
  responde 500/502 ou JSON inválido, aparece um estado de erro no lugar do
  "Carregando..." que ficava para sempre. As contas a pagar viraram
  `.lista-item` dentro de card, com selo "vencida" + ícone.
- **Sem `NaN`/`undefined` na tela:** helpers `numeroFinancas`,
  `fmtMoedaFinancas` e `fmtDataFinancas` (em `assinaturas.js`, reusados pelas
  outras seções da faixa) protegem contra campo faltando ou de tipo errado
  vindo da API.
- Emoji do selo "meta batida!" trocado por ícone de traço.
- Verificação: `scripts/ralph-c3c-financas/` (`servidor.py` com banco
  temporário e Construtora em mock, `auditar.py` para o levantamento,
  `fuzz.py` com 97 cenários de UI).
