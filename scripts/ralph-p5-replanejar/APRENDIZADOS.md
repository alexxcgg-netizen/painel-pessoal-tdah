# Aprendizados - faixa P5 (replanejar o dia)

Notas pro integrador (Etapa 0 / P1a / quem ligar rotas e front desta faixa).

## 1. `POST /api/plano-do-dia` (app.py) não checa o teto de IA hoje
Conferido (`grep -n "teto\|TETO_IA_MSG\|resumo_custo_api" app.py`): a rota
`/api/plano-do-dia` (linha ~2326) chama `claude_client.plano_do_dia` direto,
sem passar por `_TETO_IA_LOCK`/`resumo_custo_api`/`ia.teto.teto_permite`
como os outros caminhos de IA do app fazem. `assistente/replanejar.py`
(usado por esta faixa) já checa `ia.teto.teto_permite("plano_do_dia")`
antes de chamar a IA - mas a rota antiga continua sem essa proteção. Fora
dos arquivos desta faixa (`app.py` não é meu), só deixando registrado.

## 2. Onde a "ordem do dia" fica guardada
Não existe (até a Etapa 0 atual) tabela/coluna de ordem ou horário
replanejado por tarefa em `db.py` - só `due_date`/`hora`, sem posição
relativa. Usei a tabela genérica `configuracoes`
(`db.obter_configuracao`/`definir_configuracao`, já existentes), chave por
dia: `p5_ordem_dia:AAAA-MM-DD` (JSON `{"plano_texto", "aplicado_em"}`) e
`p5_desfazer:<token>` (JSON `{"dia", "anterior"}`, apagado após o uso). Se
uma faixa futura criar uma forma "de verdade" de guardar ordem/horário por
tarefa, migrar isso pra lá.

## 3. Desfazer não usa `acoes_desfazer`/`ENTIDADES_DESFAZIVEIS`
O padrão genérico de Desfazer (`db.criar_acao_desfazer`,
`ENTIDADES_DESFAZIVEIS`, `POST /api/desfazer/<token>` em `app.py`) exige
registrar uma entidade nova em `db.py` (fora dos meus arquivos). Por isso a
faixa implementou o próprio esquema de token (mesmo espírito: token único
de uso único, grava o estado anterior, `False` em vez de 404/409 -
`assistente.replanejar.desfazer_plano`). A action do card usa o tipo
**`desfazer_replanejamento`** (não `desfazer` genérico) exatamente pra não
cair silenciosamente no `POST /api/desfazer/<token>` compartilhado, que não
vai achar o token (está em `configuracoes`, não em `acoes_desfazer`).
Quem ligar o botão no front precisa de uma rota própria (ex.:
`rotas/p5_replanejar.py`, ainda não existe) que chame
`assistente.replanejar.desfazer_plano(conn, token)`.

## 4. Botão "Aplicar" - card já vem aplicado
A frase reconhecida ("replaneja meu dia", "atrasei"...) já é um pedido
imperativo, não uma pergunta - `classificador_local/regras/p5_replanejar.py`
propõe **e aplica** na mesma chamada (`data.aplicado: true`), devolvendo
`Desfazer` de verdade. A action `aplicar_replanejamento` continua no card
(pedido explícito da história) com `"ja_aplicado": true`, útil se o front
quiser oferecer "reaplicar este mesmo plano" depois de um Desfazer - quem
ligar isso a uma rota chama `assistente.replanejar.aplicar_plano(conn,
dia_iso, plano_texto)` de novo com o `plano_texto` que já está em
`data.plano_texto`.

## 5. Nome do arquivo do gatilho x convenção de `ao_resolver`
`docs/agentes/fase7-assistente.md` diz que a P1a despacha `ao_resolver`
pelo "texto de `origem` antes do `_`", o que combina com gatilhos chamados
`<faixa>.py` (ex. `p2.py`). Só que `docs/agentes/fase7-regras-faixa.md`
("Donos de arquivo") me deu o nome explícito
`assistente/gatilhos/p5_replanejar.py` (a faixa se chama `p5-replanejar`,
com hífen - não dá pra ter `p5-replanejar.py` como módulo Python). Usei
`origem="p5_replanejar"` (sem sufixo de id) e implementei `ao_resolver`
nesse mesmo arquivo. Se a P1a implementar o despacho literalmente como
"tudo antes do primeiro `_`", vai procurar `assistente/gatilhos/p5.py` e
não vai achar - sugiro a P1a casar pelo nome do arquivo inteiro (sem
`.py`) quando `origem` não tiver `:`, ou then usar `origem.rsplit("_",
1)[0]` só quando houver um sufixo depois do último `_` (ex.
`p2_conta:123` -> `p2_conta`). Não decidi isso sozinho porque
`assistente/caixa.py` é arquivo da P1a, não meu.

## 6. Testes sem `assistente/caixa.py` existir ainda
Os testes do gatilho injetam um módulo falso em `sys.modules["assistente.
caixa"]` (`unittest.mock.patch.dict`) pra poder mockar `enfileirar` sem
criar o arquivo de verdade (que é da P1a). Quando a P1a mergear
`assistente/caixa.py` de verdade, os testes continuam passando sem
mudança (o fake só é usado dentro do `with patch.dict(...)`).
