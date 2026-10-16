# Leva 2026-10-16 - despertador pedido no chat + relatório do painel

Pedido do Alex: (1) "se eu falar 'amanhã quero acordar às 7', ele coloca um despertador no meu
iPhone"; (2) "ler o relatório do painel inteiro pra ver bugs, erros, coisas que ainda não saem
como eu quero".

## 1. Despertador
Limite da plataforma: o iOS **não deixa um site/PWA criar alarme**. Só o app Atalhos cria
("Criar Alarme"). Então o painel guarda o pedido e o Atalho do iPhone faz o alarme.
- Ferramenta do chat `definir_despertador(hora, quando_data?, cancelar?)` (sem data = amanhã; madrugada
  antes das 4h = o próprio dia). Aceita "7h", "7h30", "07:00". Hora de hoje que já passou = erro.
- `despertador.py` guarda `{data, hora}` em `configuracoes` (um pedido por vez, vale só pra aquela data).
- `GET /api/atalho/despertador` devolve o pedido (ignora o `?ate=`); **se um voo/compromisso do mesmo dia
  exigir acordar antes, vale o mais cedo** (acordar atrasado perde o voo) e a IA recebe `aviso_compromisso`
  pra te contar.
- Card `despertador` no chat: hora grande + botão "Pôr no despertador do iPhone" =
  `shortcuts://run-shortcut?name=Despertador%20do%20Painel` (allowlist estrita no `cards.js`).
- **Você precisa criar o Atalho** com esse nome exato (passo a passo em `docs/ATALHOS.md`, seção 2c-bis).
  Sem ele o botão não faz nada e o alarme só sai pela automação das 22h.

## 2. Relatório do painel
- `scripts/relatorio_painel.py` + habilidade `relatorio-painel`: conversa, aparelho, servidor, dados;
  "o que olhar primeiro" ordenado. Só leitura. Saída em `data/` (gitignored).
- Faltava o principal: **erro de servidor só ia pro console e sumia** e **erro de JavaScript do celular
  nunca chegava**. Agora: `log_erros.py` grava WARNING+ em `data/erros_servidor.log` (rotativo 3x500 KB;
  não liga sob teste) e o `init.js` manda `erro_js` (mensagem curta + arquivo:linha, sem conteúdo) pro
  `/api/diagnostico`.

## Decisões (vetáveis)
- Mais cedo ganha entre o pedido e o compromisso (em vez de obedecer cegamente a hora pedida).
- Um pedido de despertador por vez (o novo substitui o anterior).
- O botão depende do nome do Atalho; não tentei criar/instalar Atalho por link (iCloud) nem pedir permissão.
- Registro de erros começa agora: o relatório só vê erro de servidor depois do próximo reinício.
