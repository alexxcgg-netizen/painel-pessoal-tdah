# Segurança: criptografia de dado sensível em repouso

Este documento cobre a criptografia em repouso implementada no painel: o que é
criptografado, com quê, como a chave é gerenciada, o que **não** é
criptografado (e por quê) e o que fazer se a chave se perder.

## O que é criptografado

Escopo: os dois tipos de dado mais sensíveis do painel - dinheiro vindo do
Open Finance e dado de saúde. Campo a campo, conferido direto no schema
(`db.py`):

| Tabela | Campos criptografados | Campos em texto plano (e por quê) |
| :--- | :--- | :--- |
| `bank_accounts` | `saldo` | `banco`, `tipo` (nomes de instituição/categoria, não segredo) |
| `bank_transactions` | `descricao`, `valor` | `data` (usado em `ORDER BY`/filtro de mês), `external_id`, `categoria` |
| `saude_dados` | `passos`, `distancia_km`, `sono_horas`, `andares_subidos` | `data` (chave/filtro) |
| `medidas_corporais` | `valor` (o número - peso, cintura, etc) | `tipo` (categoria, usado em `WHERE tipo = ?`), `unidade`, `data` (usado em `ORDER BY`) |
| `medicamentos` | `nome`, `dosagem`, `horario` | `recorrencia`, `ativo`, `tarefa_modelo_id` (metadado estrutural, não conteúdo do remédio em si) |

Todos os campos acima são criptografados com **Fernet** (biblioteca
`cryptography`) - AES-128 em modo CBC com HMAC-SHA256 autenticado, ou seja,
além de sigilo o token cifrado também detecta adulteração. Cada valor
cifrado é auto-contido (inclui timestamp e IV aleatório), então o mesmo
valor gravado duas vezes gera textos cifrados diferentes.

O módulo é `criptografia.py` (`criptografar(texto)` / `descriptografar(valor)`,
tratando `None` de forma transparente). Números (`saldo`, `passos`,
`sono_horas`, etc.) são serializados com `str()` antes de cifrar e
convertidos de volta com `int()`/`float()` ao ler - o texto cifrado em si
sempre é uma string.

### `hidratacao_registros` - decisão de não criptografar

A tabela só tem um campo de conteúdo: `data` (o dia em que um copo de água
foi registrado - a própria tabela existe só pra contar `COUNT(*) WHERE data
= ?`). Diferente de `medidas_corporais.data` (usado em `ORDER BY`, onde
criptografar quebraria só a ordenação), aqui `data` é a **chave de
igualdade** que toda a função depende (`contar_hidratacao_dia`). Criptografar
um valor usado em `WHERE data = ?` não funciona com Fernet (o mesmo texto
plano gera cifrados diferentes a cada chamada, por causa do IV aleatório -
nunca dá pra comparar `=` no SQL), e não sobra nenhum outro campo sensível
na tabela pra proteger. Decisão: **não criptografado**, o "dado" real aqui é
só "quantas vezes por dia você lembrou de beber água", que não carrega
conteúdo sensível por si (é uma contagem, sem hora exata nem outro detalhe).

### Por que `incomes`/`expenses`/`goals` ficam de fora

O pedido original definiu o escopo como "dado financeiro vindo do Open
Finance (Pluggy)" - isso é especificamente `bank_accounts`/`bank_transactions`,
que só existem porque vieram de uma sincronização bancária real (Pluggy ou
OFX). `incomes`, `expenses` e `goals` são gasto/renda/meta **digitados à mão
pelo Alex** no chat ou captura rápida - não são "Open Finance", então ficam
fora deste escopo por interpretação explícita do pedido, documentada aqui.
Candidato a criptografia futura, se um dia fizer sentido (são dado
financeiro pessoal também, mesmo não vindo de banco) - não implementado
agora porque o pedido foi específico sobre o que cobrir nesta rodada.

### Verificação feita antes de implementar: token do Pluggy não é persistido

Conferido em `app.py`/`pluggy_client.py`: o `item_id` do Pluggy (que dá
acesso à conta bancária real via API) **nunca é gravado no banco** - ele
chega do frontend a cada chamada em `/api/bancos/conectar/finalizar`
(`_corpo_json().get("item_id")`) e é usado na hora, sem persistir em
nenhuma tabela. Se isso mudasse no futuro, esse token precisaria de
criptografia (é muito mais sensível que saldo/descrição - dá acesso direto
à conta bancária real, não só aos números já sincronizados), mas hoje não
há nada a criptografar aqui.

## O que NÃO é criptografado (o resto do banco) - e por quê

Todo o resto do banco (tarefas, notas, gastos digitados, metas, chat,
lembretes, viagem, aviação, etc.) fica em texto plano. Isso é uma decisão
deliberada, não um esquecimento: a superfície de ataque que esta mudança
protege é especificamente **alguém obter uma cópia isolada do arquivo
`.db`** (um backup vazado, um disco antigo, um dump de erro) sem ter
também o `.env`/`ENCRYPTION_KEY` do servidor - nesse cenário, os dois tipos
de dado mais sensíveis (dinheiro bancário real e saúde) ficam protegidos,
e o resto (que já era menos sensível de cara) permanece legível.

**Limitação honesta**: isso não é proteção contra um servidor
comprometido. Quem tem acesso ao servidor rodando **e** ao `.env` consegue
ler tudo mesmo assim - a chave fica na mesma máquina que o banco, porque é
assim que o app consegue funcionar sozinho sem pedir senha toda hora (app
de uso pessoal, sem fricção). Criptografia de campo protege contra
vazamento do **arquivo do banco sozinho**, não contra comprometimento total
do servidor. Se um dia isso importar mais (hospedagem compartilhada,
múltiplos operadores, etc.), o próximo passo seria mover `ENCRYPTION_KEY`
pra um gerenciador de segredos externo ao servidor (ex: AWS KMS/Secrets
Manager, Vault) em vez do `.env` local - fora do escopo desta rodada.

## Gerenciamento da chave (`ENCRYPTION_KEY`)

- Uma variável de ambiente nova: `ENCRYPTION_KEY`, uma chave Fernet (32
  bytes aleatórios, codificados em base64 urlsafe).
- Gere com `python scripts/gerar_chave_criptografia.py` - imprime a chave
  pronta pra colar no `.env`. O script não salva em arquivo nenhum (ao
  contrário de `scripts/gerar_chaves_push.py`) - `ENCRYPTION_KEY` é a
  **única cópia** dela, então o lugar certo é direto no `.env`.
- **Nunca vai pro git.** O `.env` já está no `.gitignore` deste repositório
  - confirmado antes de implementar. Nunca cole a chave em código, commit,
  issue, print de tela público ou qualquer lugar versionado.
- Guarde uma cópia da chave em algum lugar seguro **fora do servidor** -
  recomendado: um gerenciador de senhas (1Password, Bitwarden, etc). Se o
  servidor morrer (disco, HD, VM apagada) e a única cópia da chave estava
  só lá, o dado cifrado no backup vira irrecuperável junto.

### Decisão de design: o que acontece sem `ENCRYPTION_KEY`?

**O app continua funcionando normalmente.** Este é um app pessoal de uso
único - ele nunca deve travar ou bloquear o Alex por causa de uma variável
de ambiente que faltou. Sem `ENCRYPTION_KEY`:

- Os campos do escopo acima são gravados e lidos **em texto plano**, como
  sempre foram antes desta mudança.
- Um aviso é logado (uma vez por processo, não flood) explicando a
  situação e como resolver.
- A rota `GET /api/seguranca/status` devolve
  `{"criptografia_ativa": false, "aviso": "..."}` - existe justamente pra
  isso nunca ficar escondido, só silencioso no log.
- A interface mostra um aviso discreto na aba "Bancos" (`#cripto-aviso`)
  quando a criptografia está desligada.

Ou seja: a ausência da chave nunca falha silenciosamente sem indicar isso
em algum lugar visível (log + rota de diagnóstico + UI), mas também nunca
impede o app de subir e funcionar.

## Migração de dado pré-existente

Na primeira subida do app **depois** que `ENCRYPTION_KEY` é configurada, uma
migração incremental (`db._migrar_criptografia_campos_sensiveis`, mesmo
padrão de `_seed_rotina_padrao`) percorre as tabelas do escopo e cifra
qualquer valor que ainda esteja em texto plano. Ela:

- Só roda se `ENCRYPTION_KEY` estiver configurada (sem chave, não há com
  que cifrar).
- Só roda **uma vez** - marca `criptografia_migrada` em `configuracoes`
  depois de terminar, do mesmo jeito que `rotina_semeada` marca a seed de
  rotina. Rodar de novo cifraria um valor que já está cifrado, virando lixo
  ilegível - o flag evita isso.
- Não tenta detectar "isso já parece cifrado" linha a linha - a proteção é
  o flag acima, que garante que a migração inteira roda no máximo uma vez
  por banco.

## Índices e filtros afetados

Campo cifrado não pode ser comparado/ordenado/agregado direto no SQL - o
mesmo texto original vira um texto cifrado diferente a cada chamada
(Fernet usa IV aleatório), então `WHERE valor < 0`, `ORDER BY saldo`,
`SUM(valor)`, `AVG(sono_horas)` etc. pararam de fazer sentido nessas
colunas. Pontos que tinham isso e foram movidos para filtrar/somar/ordenar
em Python, depois de descriptografar (revisado com grep em `app.py`,
`db.py`, `aprendizado.py`, `notificacoes.py`):

- `db.total_gastos_bancarios_mes` - somava `SUM(-valor) WHERE valor < 0`.
- `db.estatisticas_conta` (usada por `GET /api/bancos`) - somava
  `SUM(CASE WHEN valor < 0 ...)`.
- `db.media_passos_ultimos_dias` - `AVG(passos)`.
- `db.list_medicamentos_ativos` - `ORDER BY horario`.
- `app._gastos_reais_unificados` - `WHERE valor < 0` no extrato bancário
  (usado por sobra do mês/detecção de gasto fixo).
- `app._avisos_fase2` (aviso de sono ruim seguido) - `WHERE sono_horas IS
  NOT NULL`.
- `app._fatos_periodo` (revisão semanal/mensal) - `AVG(sono_horas)`.
- `aprendizado.correlacao_sono_produtividade` e
  `aprendizado.media_checkin_por_faixa_sono` - filtro e `JOIN` por
  `sono_horas`.
- `notificacoes.cobrancas_genericas_sem_rotulo` - `WHERE valor < 0` no
  extrato bancário.

Nenhum desses vira um problema de performance real: é um app de uso
pessoal único, com uma tabela de transações bancárias e de dados de saúde
que nunca deve crescer além de alguns milhares de linhas.

## Backup

O backup do `.db` bruto (ver `docs/BACKUP.md`) contém os campos já
criptografados - isso é o comportamento esperado e correto: só quem tem a
`ENCRYPTION_KEY` consegue ler o backup também. Um backup vazado sozinho,
sem a chave, expõe saldo/extrato/saúde só como texto cifrado ilegível.

## Se você perder a `ENCRYPTION_KEY`

**Dado cifrado sem a chave é irrecuperável.** Não existe "recuperar senha"
nem "resetar" pra criptografia simétrica - a chave *é* a única forma de
reverter o texto cifrado pro original. Se a `ENCRYPTION_KEY` for perdida:

- Todo saldo, transação bancária, dado de saúde e medicamento gravado
  desde que a criptografia foi ligada fica ilegível pra sempre (o app ainda
  vai rodar, mas vai mostrar/computar com base em texto cifrado tentando
  virar número, o que normalmente aparece como o campo vazio/`None` -
  `criptografia.descriptografar` nunca derruba a leitura, só devolve o
  valor cifrado como está quando não consegue decifrar).
- Não há como recuperar isso a não ser tendo uma cópia da chave guardada em
  outro lugar (por isso a recomendação forte de guardá-la num gerenciador
  de senhas, fora do servidor).
- Se isso acontecer e não houver cópia da chave: a única saída prática é
  aceitar a perda desses campos específicos (ou restaurar de um backup mais
  antigo que ainda tenha sido feito com a chave antiga, se ela ainda
  existir em algum lugar) e gerar uma `ENCRYPTION_KEY` nova pra daqui pra
  frente.
