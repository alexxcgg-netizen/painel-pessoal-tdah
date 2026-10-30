# Lab v4, Grupo D: Memória da IA (30/10/2026)

Ideias: onde-guardei, o-que-falei, neste-dia, coincidencias. Seguem as demos de `docs/prototipos/laboratorio-v4/demos/40-ia.js` e `90-bonus.js`, com dado real.

## O que entrou
- **Onde guardei**: tabela `guardados` (migração `202610301000_md_guardados.sql`), módulo `guardados.py`. Ferramentas do chat `guardar_objeto` e `onde_esta`; prompt manda usar `guardar_objeto` em vez de `registrar_memoria`. Guardar de novo atualiza o lugar (e o card diz "Antes estava em..."). Card `guardados` com 4 modos (guardado, achei, não achei, lista). Rotas `GET /api/guardados` e `DELETE /api/guardados/<id>` (botão "tirar", dois toques).
- **O que eu falei**: `memoria.buscar_falas` reaproveita a busca da memória sob demanda, mas só devolve o que ELE disse/escreveu (chat, anotação do diário, nota, decisão, espera), datado. Ferramenta `buscar_o_que_falei`; card `o_que_falei`. O "Resumo" da demo é a resposta em texto do próprio chat (que só vê os trechos achados, no máximo 8, 160 caracteres cada). Nenhuma chamada extra à Claude.
- **Neste dia**: `neste_dia.py`. Marcos de 2 anos, 1 ano, 6 meses, 3 meses e 1 mês atrás (janela de ±2 dias; cada linha mostra a data real). Só progresso: voos (o primeiro registrado ganha destaque) e carga de treino que subiu. Dia comum não devolve nada e o card não aparece. Sai sozinho no chat de manhã (7h30 a 11h), no máximo a cada 3 dias, sem push. Ferramenta `consultar_neste_dia` para pedir na hora.
- **Coincidências**: `coincidencias.py`. Janela de 30 dias; padrões sono (<6 h x 7 h+) e treino (treinou x não) contra tarefas fechadas e gasto em Delivery. Só aparece com 3+ dias de cada lado e diferença de 25% ou mais (e mínimo absoluto). Sempre com "coincidência nos teus dados, não prova de causa". "Não ligo pra isso" grava `coincidencias_ocultas` (config) e esconde o tipo para sempre (`POST /api/coincidencias/ocultar`). "Quero ver mais" abre a tabela dia a dia (últimos 14). Sai no chat aos sábados (9h a 21h), sem push. Ferramenta `consultar_coincidencias` (só números agregados).
- Front: `static/js/cards-memoria.js` + `static/css/secoes/hoje/cards-memoria.css`, já em `scripts.html`, `fase7.css` e `ASSETS` do SW (sem bump do CACHE_NAME). Modo visitante: os 4 cards perdem os dados (`CAMPOS_SENSIVEIS`), as ferramentas recusam leitura e a rota de listar volta vazia.

## Decisões para o Alex vetar
- "Resumo" do o-que-falei é texto do chat, não um bloco dentro do card.
- Neste dia só olha voo e carga (não puxa diário/anotação, que pode ser coisa ruim). Dá pra somar tarefas grandes, metas e recordes depois.
- Dia de treino x tarefas conta só dias "ativos" (com tarefa, treino, gasto ou sono registrado).
- O sono do dia D é a noite que terminou na manhã de D (como o `dia_ruim.py` já usa).
- Neste dia e coincidências não mandam push (são agrado, não aviso).

## Ficou de fora
- Entrada por voz específica: usa o chat por voz que já existe, nada novo.
- Fotos de refeição e "conversas marcadas" no Neste dia (não há data confiável de "marco" nesses dados).
- Captura no app real logado: fiz em harness 390 px (sem rolagem lateral, alvos de 44 px, sem erro de JS) em `scratchpad/memoria_390.png`. O clique de "Quero ver mais" depende da delegação do `Cards.ligar`, então só valida no app.

## Passos do Alex
- Nenhum de configuração. O integrador faz bump do `CACHE_NAME`, CHANGELOG e suíte completa. A migração roda sozinha no `init_db`.
- Depois de subir: dizer "guardei o passaporte na gaveta azul" e perguntar "cadê o passaporte?" no chat para conferir.

## Testes
`tests/test_memoria_ia.py` (Python) e `tests/js/cards_memoria.test.js` (Node).
