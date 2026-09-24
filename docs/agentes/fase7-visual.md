# Fase 7B: direção visual (vale para todas as faixas V e para a P1b)

## O que o Alex pediu (decisão dele, não negociável)
- **Não mexer** em cores, cor de destaque, fontes nem animações. A paleta e a tipografia atuais continuam iguais.
- **O que mudar:** elementos que parecem antigos ou simples demais, com cara de "Windows 1990" ou de sistema genérico. Ele quer uma aparência atual, de 2026: **cards atualizados, efeitos de profundidade** (camadas, elevação sutil, bordas finas em vez de sombra pesada) e um visual que saia do genérico. Deve ficar sério, tecnológico e refinado, na linha do app Néctar.
- A aba **Hoje** está boa: mantenha a estrutura e ajuste só ao novo acabamento.
- Pedidos específicos:
  1. **Botões "adicionar"**: hoje são azuis, pequenos e feios. Aparecem em Hábitos, Projetos, Agenda ("+ criar evento"), Garantia de Produtos, Ideias de Presente, Tarefas e onde mais houver. Eles viram um botão único, grande e bem desenhado (`.btn-adicionar`) que abre o formulário num painel deslizante (`.bottom-sheet`).
  2. **Seções recolhíveis**: "O que lembro sobre você" (com "Sua rotina" e "Seus planos") e "Fora do painel, outras coisas que anotei" começam **recolhidas**, com uma setinha ao lado do título. Faça o mesmo em qualquer seção longa parecida. O estado aberto/fechado fica salvo por seção (localStorage, com try/catch).
- Ícones de traço consistentes. Troque emoji usado como ícone de interface. Gráficos em Chart.js. Área de toque mínima de 44px e contraste adequado. Grade de 8px.

## Contrato de UI (use **só** estas classes; as faixas V0b a V0d implementam o visual delas)
- Botões: `.btn.btn-primario`, `.btn-secundario`, `.btn-perigo`, `.btn-fab`, `.btn-adicionar` (altura mínima de 48px, sem o azul padrão do navegador).
- Seção recolhível:
  ```html
  <section class="secao-recolhivel" data-aberto="false" data-secao-id="memoria">
    <button class="secao-cabecalho" aria-expanded="false">Título <span class="chevron"></span></button>
    <div class="secao-conteudo">…</div>
  </section>
  ```
  O comportamento fica em `static/js/ui/secao-recolhivel.js` (V0c): ele liga sozinho toda `.secao-recolhivel` da página e guarda o estado.
- Painel deslizante: `<div class="bottom-sheet" hidden>…</div>`. A API JS fica em `static/js/ui/bottom-sheet.js` (V0d): `abrirBottomSheet(elOuId)` e `fecharBottomSheet(elOuId)`, com fundo escurecido, ESC e toque fora para fechar, e foco preso dentro do painel.
- Estruturais: `.card`, `.card-titulo`, `.chip`, `.campo`, `.lista-item`.
- Tokens (V0a, em `static/css/ui/tokens.css`): **reaproveitam as variáveis de cor que já existem** em `style.css` (`--surface`, `--text`, `--cor-painel` etc.; confira com `grep -n "^\s*--" static/css/style.css | head -80`). Os tokens novos são só de forma e profundidade: `--raio`, `--raio-sm`, `--espaco-1..6` (8px), `--elevacao-1..3`, `--borda-sutil`, `--superficie-2`/`--superficie-3` (derivadas da cor de superfície atual com transparência). Não crie cor nova de destaque.

## Como trabalhar sem conflito
- O mapa seção → arquivos está em `docs/agentes/mapa-frontend.md` (leia esse arquivo primeiro).
- Cada faixa edita **só** os HTML/JS/CSS das próprias seções. Não edite `static/css/style.css`, `static/js/nucleo/*`, `templates/index.html`, `templates/head.html`, `templates/scripts.html` nem `static/service-worker.js`. Se precisar mexer num desses, anote no `progress.txt` o que e onde, e o integrador faz.
- O CSS da sua seção vai em `static/css/secoes/<aba>/<secao>.css`. Ele sobrescreve o `style.css` por cascata, então use seletores específicos. Nada de `!important`, a não ser que não haja alternativa (e documente).
- Enquanto V0a a V0d não entram na integração, use as classes do contrato mesmo assim e teste a estrutura. A verificação visual no Playwright é sempre a **última** história da faixa. Nessa hora, faça `git merge origin/fase7/integracao` para pegar os componentes prontos.
- Arquivo JS/CSS **novo**, fora dos que a Etapa 0 já criou vazios, precisa entrar no `static/service-worker.js` e no `templates/scripts.html` ou no `static/css/fase7.css`. Esses arquivos são do integrador: anote no progress com o caminho exato. Prefira preencher os arquivos que já existem.
- Verificação: Playwright headless em 390x844, com o app num banco de teste (nunca o real) e na porta 5100 + o índice da faixa. Nenhum erro de console. No máximo 2 screenshots por tela, salvos em `scripts/ralph-<faixa>/` (não versione PNG grande: use a pasta e depois `git rm --cached`, ou deixe fora do commit).
