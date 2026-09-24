# Aprendizados - Fase 7, faixa V0b (botoes)

## Comentario CSS com "fecha comentario" escondido no meio da prosa
Um comentario de cabecalho em `botao.css` descrevia os tokens reaproveitados usando
notacao de wildcard em prosa, algo como `--surface-` + asterisco + `/` + `--border` +
asterisco (dois tokens com o mesmo prefixo, abreviados). Só que **asterisco seguido
imediatamente de barra, em QUALQUER lugar dentro de um comentario CSS, fecha esse
comentario ali mesmo** - nao importa se a intencao era so descrever um wildcard em texto.

O comentario tinha um "fecha" de verdade mais adiante (varias linhas depois), entao o
fechamento acidental cortou o comentario no meio, e tudo entre os dois "fecha comentario"
virou CSS de verdade para o parser - que, sendo invalido, descartou a proxima regra
inteira (`:root { --btn-icone-mais: ...; }` sumiu do CSSOM). O sintoma visivel foi um
icone "+" renderizando como quadrado solido (a mask nao tinha valor nenhum pra aplicar,
entao `mask-image` computava `none` e o pseudo-elemento aparecia cheio).

Como eu achei: o arquivo tinha sintaxe CSS "correta" a olho nu, os testes de
console/rede do Playwright passavam limpos (CSS invalido nao gera erro de console - o
parser so ignora a regra quebrada), e a screenshot mostrava o bug visualmente (quadrado
em vez de "+"). Precisei comparar `document.styleSheets[i].cssRules.length` e o
`selectorText` de cada regra pra confirmar que a regra `:root` literalmente nao estava no
CSSOM carregado, isolando o arquivo em testes cada vez menores ate achar a linha exata.

**Regra pra quem mexer em CSS depois:** nunca escrever asterisco+barra adjacentes dentro
de um comentario, nem em prosa (varie a redacao, separe com espaco, ou escreva o nome
completo em vez de abreviar com wildcard). E depois de qualquer alteracao em CSS que
declare uma custom property ou uma regra nova, vale a pena confirmar no
DevTools/CSSOM (ou via Playwright) que a regra realmente esta no `styleSheet.cssRules`
carregado - nao só que o arquivo-fonte "parece certo".

## Empate de especificidade que faz a ordem no arquivo decidir
`.btn:focus-visible` (classe + pseudo-classe) e `.btn.is-carregando` (2 classes) têm a
MESMA especificidade CSS que `.btn.btn-primario`/`.btn.btn-secundario`/etc (tambem 2
classes). Quando duas regras empatam em especificidade, quem vem DEPOIS no arquivo
vence - entao, com o anel de foco e o estado "carregando" declarados ANTES das variantes,
o `box-shadow`/`color` de cada variante sobrescrevia o anel de foco e o texto some do
carregando na pratica (o elemento continuava mostrando a aparencia normal, sem nunca sinalizar
foco/carregamento).

Fix: mover as duas secoes (foco visivel e estado carregando) pro FINAL do arquivo, depois
de todas as variantes - assim, no empate de especificidade, elas ganham por serem as
ultimas declaradas. Alternativa que eu NAO usei (mas seria valida): aumentar a
especificidade repetindo uma classe (`.is-carregando.is-carregando`), só que isso e mais
fragil de ler/manter do que so cuidar da ordem no arquivo.

Como eu achei: o `verificar.py` originalmente so conferia "existe algum box-shadow com
`rgb` no valor" ao focar um botao - o que sempre era verdade, porque o box-shadow "de
repouso" da variante ja tem `rgb(...)`. Troquei a checagem pra comparar o box-shadow
focado com o box-shadow do MESMO elemento sem foco (`sem_foco` capturado antes do Tab) -
só aí o teste realmente provava que o anel mudava algo, e pegou o bug na primeira
tentativa depois do fix ter sido feito por outro motivo (o mesmo padrao de bug que
achei primeiro no `is-carregando`).
