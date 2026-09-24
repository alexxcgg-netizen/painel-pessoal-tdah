# Aprendizados - Fase 7, faixa V5-extra (Viagens, Lugares, Cotações, Aviação)

## `.bottom-sheet` sem componente compartilhado ainda: nunca estilize a classe sem escopo
Comecei a faixa antes de `fase7/integracao` ter V0a/V0b/V0c mesclados (so a Etapa 0 X2
estava la). Escrevi a primeira versão do CSS do bottom-sheet usando a classe `.bottom-sheet`
sem escopo (`#viagem-sheet.bottom-sheet` ficou certo, mas cheguei a cogitar so
`.bottom-sheet` puro). Depois de mesclar `fase7/integracao` na última história, vi que
**v3-organizacao já tinha essa exata situação e definiu um fallback de `.bottom-sheet`
SEM escopo** (`static/css/secoes/vida/habitos.css`) - inofensivo pra eles, porque foram os
primeiros a escrever a regra. Se eu tivesse feito o mesmo (unscoped) depois deles, minha
regra (carregada depois na cascata, mesma especificidade) teria **sobrescrito
globalmente** o `.bottom-sheet` de habitos/projetos/tarefas/agenda-painel também, virando
um backdrop fixo em tela cheia pra sheets que não são meus. Corrigi pra `#meu-id
.bottom-sheet` em tudo (nunca a classe pura) exatamente por causa disso. **Regra pra quem
mexer em CSS compartilhado sem componente pronto: qualquer classe do contrato
(`.bottom-sheet`, `.btn-adicionar`...) que ainda não tem dono (`ui/componentes/*.css`
vazio) só pode ganhar estilo aqui se estiver escopada por ID da sua própria seção -
nunca pela classe pura, mesmo que pareça "só um fallback temporário".**

## Depois que `V0b`/`V0c` chegam na integração, o botão real é `.btn.btn-adicionar` (com `.btn`)
O contrato documentado (`fase7-visual.md`) fala só em `.btn-adicionar`, mas o CSS real
(`ui/componentes/botao.css`, V0b) seleciona `.btn.btn-adicionar` - **as DUAS classes**. Um
elemento só com `class="btn-adicionar"` (sem `.btn`) não recebe nenhum estilo do
componente real. Descobri isso só depois do merge, comparando com as seções que V3-
organizacao já tinha feito (`habitos.html`, `projetos.html`...), que usam
`class="btn btn-adicionar"` e `id="<nome>-abrir-btn"`. Corrigi as 3 seções minhas pra
esse mesmo padrão (e troquei meu CSS próprio de "CTA cheio" pelos componentes reais
`.btn.btn-primario`/`.btn.btn-secundario`/`.campo`, removendo a duplicação).

## `.btn.btn-adicionar` já desenha o próprio ícone "+" via `::before`
O componente real desenha um selo circular com "+" via `background-image` no
`::before`. Toda seção já integrada (habitos, projetos, tarefas, agenda-painel) MESMO
ASSIM mantém o `<svg>` de "+" inline dentro do botão - dá um "+" duplicado visualmente
(selo + ícone). Confirmei no screenshot que é assim em toda seção já integrada, não um
bug meu: segui o mesmo padrão por consistência em vez de "corrigir" só as minhas (o que
destoaria do resto do app). Se algum dia isso for revisado, é decisão de quem dono do
`botao.css`/dos templates já integrados, não desta faixa.

## `loadCotacoes()` reconstrói a `<li>` inteira ao adicionar um fornecedor (comportamento pré-existente)
Ao adicionar um fornecedor numa cotação expandida, o handler de submit chama
`preencherDetalheCotacao()` (repopula o detalhe) E `loadCotacoes()` (reconstrói a lista
inteira) em sequência. Como `loadCotacoes()` troca `#lista-cotacoes` inteiro por `<li>`
novas (sempre com `detalhe.hidden = true`, `carregado = false`), o painel que acabou de
ser preenchido fecha de novo sozinho. Não é um bug desta faixa (não toquei nessa lógica),
mas quebrou minha primeira versão do script de verificação (ficava tentando preencher um
`.cotacao-add-form` que já tinha sumido do DOM). Corrigido reabrindo o cabeçalho da
cotação a cada fornecedor adicionado, em vez de assumir que o painel continua aberto.

## `/api/voos/resumo` busca previsão do tempo de verdade (chamada de rede real, 8s de timeout por request)
Depois de registrar um voo, `loadVoosResumo()` chama `/api/voos/resumo`, que por sua vez
tenta `clima.previsao_para_cidade_e_data()` pro destino - uma chamada HTTP real (timeout
de 8s por request no `clima.py`) pro serviço de previsão. Neste sandbox sem internet
confiável, isso pode levar bem mais que alguns segundos pra desistir. Meu script de
verificação (`scripts/ralph-v5-extra/verificar.py`) esperava só 8s pelo texto do voo na
lista e falhava por timeout, mesmo com o voo já salvo no banco (o POST em si volta rápido
- é só a releitura da lista que demora). Aumentei a espera dessa checagem específica pra
25s. Isso é comportamento de produção normal (na rede real do Alex a previsão volta
rápido) - é só o sandbox de verificação que precisa de mais paciência.
