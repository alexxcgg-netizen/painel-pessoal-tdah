# Aprendizados - faixa C1 (polimento do backend)

## Dubles com assinatura fixa travam kwargs novos
Mais de 40 testes (vários fora da faixa) fazem `patch("claude_client.chat", side_effect=fake)`
com `fake(mensagens, contexto, memorias, executores)`. Passar kwargs novos do app quebraria
todos. Saída: `ia.funcoes.chat.opcoes_chat(...)` (contextvar) - o app entra no `with` e chama
com os mesmos 4 argumentos; kwarg explícito sempre ganha. Serve pra qualquer opção nova do chat.

## Duas tabelas de uso: nunca somar
`api_usage` (antiga, card antigo) e `uso_ia` (nova) recebem a MESMA chamada. A fonte única é
`ia.medicao.gasto_mes_atual`: `uso_ia` + só o legado de `api_usage` anterior à primeira linha
de `uso_ia` do mês (virada do deploy). Funciona porque toda chamada grava `uso_ia` ANTES do
`_log_usage` antigo. Caminho novo de IA fora do `chamar_ia` precisa gravar `uso_ia` sozinho.

## Classificar falha de `chamar_ia` sem mudar o contrato
`Resposta.erro` é texto agregado `"prov/modelo: erro | ..."`. `ia.core.classificar_falha`
separa teto (`teto_ia_estourado`), formato (prefixos fixos de `_chamar_uma_vez`) e provedor
(o resto). Exceções herdam de `ValueError` pra não quebrar quem já capturava.

## `origem` da Caixa = nome do arquivo do gatilho
A P1a acha o `ao_resolver` pelo prefixo da `origem` antes do primeiro `:`. A P3 usava
`p3_briefing_noite:<data>` (arquivo é `p3_briefing.py`) e o `ao_resolver` nunca rodava.
Formato certo: `<arquivo>:<subtipo>:...`. O mesmo prefixo+subtipo mapeia pro catálogo da P8
(`assistente.avisos.TIPO_POR_ORIGEM`) - faixa P nova precisa cadastrar lá (teste confere).

## Vazamento entre arquivos de teste
Padrões que quebravam outro teste só no mesmo processo/ordem: trocar `sys.modules[...]` ou
atributo de módulo na IMPORTAÇÃO e nunca restaurar; `sys.modules.pop()` de um módulo real (o
próximo import cria um 2º objeto e os `patch()` miram o errado); trocar instância padrão de
módulo (`construtora_cliente._padrao`) sem `addCleanup`. Reproduzir com
`pytest -x tests/test_fase7_*.py` (um processo) além do `scripts/suite.sh` (paralelo).

## Validar antes de gravar, ler com tolerância
A N1 gravava data/valor inválido e toda leitura seguinte dava 500. Agora: valida tudo antes do
INSERT (`_valor_entrada`, `_data_entrada`, teto de 1e9 e 480 parcelas) e as leituras pulam
(com log) linha ruim já existente - nunca apagam dado sozinhas.

## Rede nos testes
`tests/conftest.py` aponta `ANTHROPIC_BASE_URL`/`OPENAI_BASE_URL`/`GOOGLE_GEMINI_BASE_URL`
pra `127.0.0.1:9` antes de qualquer import: uma chamada que escape de um duble morre na hora.
O fuzz ainda troca `socket.connect`/`getaddrinfo` e falha se houver qualquer conexão externa.

## OpenAI e PDF (confirmado em 2026-09-24)
SDK instalado: content part `File` (`{"type": "file", "file": {"file_data", "filename"}}`).
Guia oficial "PDF files" (developers.openai.com): `file_data` com data URI
`data:application/pdf;base64,...`; Chat Completions só aceita PDF ali. Ainda sem chamada real.
