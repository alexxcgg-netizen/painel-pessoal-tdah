# Contrato do classificador de intent (Fase 5)

Este documento define o contrato de `POST /api/intent/classificar` **antes**
da implementação de verdade (US-A2) - existe pra o Grupo B (navegação por
voz) poder começar a integrar contra um formato estável sem esperar o
classificador inteiro ficar pronto. Nada aqui deve mudar de forma
incompatível depois de publicado; um campo novo pode ser *adicionado*, mas
os já existentes mantêm nome e tipo.

## Lista fechada de ações

Toda resposta do endpoint traz uma `acao` dentro deste conjunto fechado -
nenhum valor fora desta lista é um contrato válido:

| Ação | Quando se aplica |
| :--- | :--- |
| `registrar_tarefa` | Comando que descreve algo a fazer (mesmo domínio de `POST /api/capture` tipo "tarefa"). |
| `registrar_gasto` | Comando que descreve um gasto/despesa (mesmo domínio de `POST /api/capture` tipo "gasto"). |
| `registrar_checkin` | Comando de check-in do dia (energia/sono/humor - ver tabela `checkins`). |
| `navegar_tela` | Pedido pra ir a uma tela/aba do painel (ex: "abre os gastos", "mostra minhas metas"). |
| `consultar` | Pergunta sobre dado já existente, sem criar nada novo (ex: "quanto eu gastei esse mês"). |
| `corrigir_ultimo` | Correção do último item capturado/classificado (mesmo espírito de `correcoes_classificacao`, Fase 4). |
| `desconhecido` | Não deu pra classificar com confiança em nenhuma das ações acima. |

## Formato de entrada

```json
{
  "texto": "string livre, obrigatório, não pode ser vazio/só espaço",
  "client_id": "string opcional (UUID do cliente) - mesmo papel de client_id em /api/capture, usado pra idempotência de reenvio"
}
```

- `texto` vazio, ausente, ou de outro tipo que não string → `400`.
- `client_id` é opcional; quando ausente, o endpoint funciona normalmente
  (sem idempotência).

## Formato de saída

```json
{
  "acao": "uma das acoes da lista fechada acima",
  "confianca": 0.0,
  "parametros": {},
  "precisa_confirmacao": true
}
```

- `acao`: string, sempre um dos 7 valores da tabela acima.
- `confianca`: número entre `0.0` e `1.0` (inclusive), o quanto o
  classificador está seguro da `acao` escolhida.
- `parametros`: objeto (pode ser vazio `{}`) com os campos extraídos
  específicos da ação - o formato interno de cada `acao` é decidido na
  implementação de verdade (US-A2) e documentado aqui quando isso acontecer;
  nesta fase de contrato, o campo sempre existe mas pode vir vazio.
- `precisa_confirmacao`: booleano. `true` quando a confiança for baixa
  demais pra executar direto (o chamador deve confirmar com o usuário antes
  de agir); `false` quando pode agir direto.
- `teto_ia_estourado` (campo **aditivo**, US-A6): só aparece (sempre `true`
  quando presente) na resposta específica em que o teto mensal de IA já
  estourou e por isso o classificador nem chamou a API - ver "Estado atual"
  abaixo. Ausência do campo não significa nada (trate como `false`).

## Erros

| Situação | Resposta |
| :--- | :--- |
| `texto` vazio/ausente/tipo errado | `400 {"error": "texto vazio"}` |

## Estado atual

- **US-A1**: contrato fechado (este documento) + endpoint stub.
- **US-A2**: o endpoint classifica de verdade via
  `claude_client.classify_intent` (modelo **Haiku**, mais barato - mesmo
  critério de `classify_capture`). Limiar de confiança:
  `claude_client.CONFIANCA_MINIMA_INTENT` (0.6) - abaixo disso,
  `precisa_confirmacao` vem `true` em vez do chamador assumir que pode agir
  direto. Cada chamada registra uso/custo em `api_usage`
  (`db.record_usage`), o mesmo mecanismo já usado pelo chat.
- **US-A3**: antes de chamar a API, o endpoint tenta resolver localmente por
  padrão aprendido (`aprendizado.padrao_intent_confiavel` - mesmo texto
  normalizado confirmado pelo menos 3 vezes com a mesma ação). Quando
  resolve local, `confianca` vem fixa em `aprendizado.CONFIANCA_PADRAO_INTENT`
  (0.95) e `precisa_confirmacao` sempre `false` - a IA não é chamada nesse
  caminho.
- **US-A4**: toda correção manual da Fase 4
  (`db.registrar_correcao_classificacao`) também vira um padrão de confiança
  alta direto (sem precisar repetir 3 vezes) - próxima vez que um texto
  parecido aparecer, resolve local desde a primeira tentativa.
- **US-A6**: quando o teto mensal de gasto com IA (configurável em
  `GET`/`POST /api/ia/custo` e `/api/ia/teto`, card financeiro) já estourou
  (100%+) no mês, o endpoint **não chama a API** mesmo sem padrão local
  confiável - devolve `acao: "desconhecido"`, `confianca: 0.0`,
  `precisa_confirmacao: true` e `teto_ia_estourado: true`. Um padrão local
  já confiável continua resolvendo normalmente mesmo com o teto estourado
  (só a chamada à API é que fica bloqueada). Volta ao normal quando o mês
  vira (o cálculo do teto é sempre "gasto do mês calendário atual").
