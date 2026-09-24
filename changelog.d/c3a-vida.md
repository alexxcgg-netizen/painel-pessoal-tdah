### Fase 7 - faixa C3a (polimento visual da aba Vida)

Sem cor, fonte ou animação nova (decisão do Alex): só forma, profundidade e toque. Vale para
as 14 seções da faixa na aba Vida (Garantia, Ideias de presente, Pessoas, Treino, Manutenção,
Quero aprender, Salvos, Lista de compras, Pra responder, Ainda usa?, Mensagem difícil, Vale a
pena?, Seu progresso, Revisão trimestral) e para Painel > Peso e medidas.

- **Sheet no componente compartilhado:** saiu do `vida.css` o antigo "fallback" `#tab-vida
  .bottom-sheet`, que pintava a moldura fixa da tela inteira (o véu sumia e o sheet virava um
  bloco escuro com borda). Os 10 sheets (9 da Vida + Peso e medidas) agora usam só o
  componente: título `.bottom-sheet-titulo` repetindo o verbo do botão, rótulo visível acima
  das datas, campos `.campo` de 44px e botão final "Salvar produto/ideia/pessoa/…". O input
  de arquivo da nota fiscal deixou de mostrar o "Choose File" nativo.
- **Cabeçalho das seções:** título à esquerda e chevron à direita (antes o título ficava
  centralizado). Ícone de 18px.
- **Hierarquia sem card dentro de card:** cada item das listas virou bloco interno
  (`--superficie-3`, `--raio-sm`, borda sutil, `--elevacao-0`). Item que pede atenção mantém
  a borda tingida e ganha elevação 1. Seu progresso e Revisão trimestral também viraram
  bloco interno, e o rótulo "USO DO CELULAR" saiu da caixa-alta.
- **Toque de 44px:** ações das linhas (antes 28px), linha da dica "!", link do salvo,
  checklist de compras e campos. "Apagar" virou ícone de lixeira de 44px em `--text-muted`,
  que só fica vermelho no hover/foco (o texto continua para leitor de tela).
- **Nada nativo:** "Adicionar exercício" e "Ver" (revisão) viraram `.btn.btn-secundario`;
  "Escrever pra mim" e "Analisar" viraram `.btn.btn-primario`.
- **Contraste:** o título de salvo já visto (4,3:1) volta a 4,6:1: o item lido perde o
  preenchimento (resolvido pela superfície, sem cor nova). Campos inline usam
  `--superficie-1` (placeholder a 4,7:1).
- **Chip da garantia** voltou a ser pílula: um comentário do `style.css` fechava antes da
  hora e engolia a regra `.garantia-chip`. A regra foi reposta no `garantia.css`.
- **Robustez:** as 13 listas da faixa ignoram resposta fora do formato (ex.: `{}` no lugar
  de lista) em vez de lançar exceção. Um toque em "Adicionar" durante a animação de fechar
  o sheet é ignorado (antes o sheet podia ficar preso e travar o scroll).
- **Escopo:** as regras de lista, ações e campos ficam em `.vida-acabamento`, marcador das
  seções da faixa. Seções de outras faixas na mesma aba não são tocadas.
- **Verificação:** auditoria e fuzz de UI no Playwright 390x844, com banco temporário e rede
  travada (sem chamada a provedor de IA). 56 cenários, 0 erro de console e 0 exceção.
