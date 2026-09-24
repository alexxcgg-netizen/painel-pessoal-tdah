# Contrato de assinaturas e compras parceladas (Fase 7, faixa N1)

Formato de rota e de card das duas entidades novas desta faixa: `assinatura` (um
compromisso mensal declarado - "assinei o Spotify por 21,90") e `compra_parcelada`
(uma compra em N vezes - "comprei geladeira 3000 em 12 vezes no nubank"). Publicado
**primeiro**, antes da lógica estar toda pronta, para as faixas de UI (V1 Hoje, V6
Financeiro/Contas/Cartão) poderem desenhar contra um formato estável sem esperar.
Regra de evolução (mesma do `CARDS.md`/`INTENT.md`): **só aditivo** - um campo novo
pode ser *acrescentado* depois, nome/tipo de campo já publicado nunca muda.

Código de referência:

| Parte | Onde |
| :--- | :--- |
| Modelos + CRUD + cálculos derivados | `financas_recorrentes.py` |
| Migração (tabelas `assinatura`, `compra_parcelada`) | `migracoes/202609241300_n1_assinaturas.sql` |
| Classificador local (frase → card, sem IA) | `classificador_local/regras/n1_financas.py` |
| Rotas (CRUD + resumo pra tela do cartão) | `rotas/n1_financas.py` |
| Testes | `tests/test_fase7_n1_calculos.py`, `tests/test_fase7_n1_classificador.py`, `tests/test_fase7_n1_rotas.py` |

## Relação com o que já existe (não duplica)

- **`gastos.detectar_gastos_recorrentes`/`detectar_aumento_assinatura`** (Fase 3/4,
  `gastos.py`): DETECTAM recorrência observando o HISTÓRICO de gasto/extrato bancário -
  não sabem de "assinatura" como conceito antes dela acontecer 2+ vezes, e não têm
  `dia_cobranca`/`n_parcelas` nenhum. As tabelas desta faixa são DECLARADAS (pelo Alex ou
  pelo classificador local) no momento da contratação, fonte diferente (intenção x
  observação) - convivem sem se sobrepor. `financas_recorrentes.valor_para_aviso_custos_fixos`
  é a ponte entre as duas (ver abaixo).
- **`bank_accounts.limite`** (US-E15, campo manual, `vida.fracao_limite_cartao`): o limite
  do cartão. `assinatura.cartao_ou_forma`/`compra_parcelada.cartao` são texto livre; quando
  batem com o `banco` de uma linha `bank_accounts` (`tipo='cartao'`, via
  `db.buscar_conta_por_nome`), `financas_recorrentes.impacto_limite_cartao_proximos_meses`
  cruza com esse limite. Quando não batem (ex: "pix", "boleto", forma sem cartão
  cadastrado), o valor ainda entra no total comprometido, só não entra no cálculo de
  fração de limite (`limite: null` na resposta).
- **`docs/CARDS.md`** (Fase 6, "Padrão Nectar"): os cards `assinatura`,
  `compra_parcelada` e `resumo_financeiro_recorrente` descritos aqui seguem o MESMO
  envelope (`{cards, resumo_texto, passos}`), a mesma convenção de Desfazer e o mesmo
  fallback do frontend pra `type` desconhecido - só não estão ainda cadastrados em
  `cards.py` (`ABA_POR_ENTIDADE`, `CAMPOS_SENSIVEIS`, `TIPOS_CARD`) nem em
  `static/js/cards-tipos.js`, porque esses arquivos não são desta faixa. **Checklist pra
  quem for ligar a UI (V1/V6):**
  1. Registrar `assinatura` e `compra_parcelada` em `cards.CAMPOS_SENSIVEIS` (têm campo de
     dinheiro - `valor`/`valor_total`/`valor_parcela` somem no modo visitante, igual
     `transacao`/`meta`).
  2. Escolher o id da aba financeira (ainda não existe em `ABA_POR_ENTIDADE` - hoje só há
     `gastos`) e acrescentar `assinatura`/`compra_parcelada` lá, se quiser o botão
     "Abrir em ...".
  3. `Cards.registrar("assinatura", ...)` e `Cards.registrar("compra_parcelada", ...)` e
     `Cards.registrar("resumo_financeiro_recorrente", ...)` em `static/js/cards-tipos.js`
     (até lá, o fallback "Este trecho não pode ser exibido" mostra o card cru - sem quebrar
     nada, só sem visual dedicado).
  4. Acrescentar `assinatura`/`compra_parcelada` em `docs/CARDS.md` também (seção "Tipos de
     card"), pra virar a fonte única quando a UI estiver pronta - este documento pode ser
     aposentado nesse momento.
- **Desfazer**: o mecanismo geral (US-E5, `db.ENTIDADES_DESFAZIVEIS` +
  `app._desfazer_itens`, `POST /api/desfazer/<token>`) ainda não conhece as entidades
  `assinatura`/`compra_parcelada` (`db.py`/`app.py` não são arquivos desta faixa). Até
  alguém acrescentar as duas lá, o botão Desfazer dos cards desta faixa chama
  `POST /api/financas/desfazer/<token>` (rota própria, mesmo formato de resposta) em vez
  da rota genérica - ver "Desfazer" mais abaixo. O `token` no card é opaco pro frontend
  nos dois casos (não precisa saber qual rota é de qual faixa só olhando o card).

## Modelos

### `assinatura`

| Campo | Tipo | Obrigatório | Observação |
| :--- | :--- | :--- | :--- |
| `id` | int | - | gerado |
| `nome` | string | sim | |
| `valor` | number | sim | sempre positivo, mensal |
| `dia_cobranca` | int (1-31) | sim | dia do mês; cravado no último dia dele quando não existir (dia 31 em fevereiro → 28/29) |
| `cartao_ou_forma` | string ou null | não | texto livre ("nubank", "pix", "débito automático"...) |
| `categoria` | string ou null | não | |
| `ativa` | bool | - | `false` depois de cancelada |
| `inicio` | string (data ISO) | sim | primeiro mês em que ela cobra; default = hoje |
| `observacao` | string ou null | não | |
| `cancelada_em` | string (data ISO) ou null | - | preenchido só no cancelamento |

### `compra_parcelada`

| Campo | Tipo | Obrigatório | Observação |
| :--- | :--- | :--- | :--- |
| `id` | int | - | gerado |
| `descricao` | string | sim | |
| `valor_total` | number | um dos dois | derivado de `valor_parcela × n_parcelas` se não vier |
| `n_parcelas` | int (> 0) | sim | |
| `parcela_atual` | int | - | **informativa/editável a mão** (ex: importar uma compra que já estava na parcela 4) - o número CANÔNICO usado em todo cálculo é sempre recalculado a partir de `primeira_parcela` + `n_parcelas` + a data de hoje (`financas_recorrentes.parcela_info`), nunca lido desta coluna |
| `valor_parcela` | number | um dos dois | derivado de `valor_total ÷ n_parcelas` (2 casas) se não vier |
| `cartao` | string ou null | não | texto livre, mesma relação com `bank_accounts` que `cartao_ou_forma` |
| `primeira_parcela` | string (data ISO) | sim | default = hoje |
| `categoria` | string ou null | não | |

Granularidade de **mês**, de propósito: dentro do mês em que uma parcela cobra, ela conta
como "em andamento" o mês INTEIRO (inclusive no próprio dia em que cobra) - só vira
"quitada" a partir do mês seguinte ao da última parcela. O dia exato de `primeira_parcela`
só entra pra calcular a *data* da próxima cobrança, nunca pra decidir se uma parcela já
"aconteceu" ou não dentro do mês dela.

## Derivados (`financas_recorrentes.py`, por código, sem IA)

Todo valor em dinheiro é somado internamente em `Decimal` e devolvido como `float`
arredondado a 2 casas (evita deriva de ponto flutuante ao somar várias assinaturas).

- **`total_mensal_comprometido(conn, hoje)`** → `{"mes", "assinaturas_total",
  "parcelas_total", "total", "detalhe_assinaturas": [...], "detalhe_parcelas": [...]}`.
  Considera TODA assinatura (não só `ativa=1`): uma cancelada no meio do mês ainda contou
  se a cobrança daquele mês já tinha passado quando cancelou.
- **`valor_para_aviso_custos_fixos(conn, hoje)`** → `float`. É o número que alimenta o
  aviso já existente **"custos fixos já comprometem X%"**
  (`notificacoes.mes_seguinte_apertado`, que hoje soma só
  `gastos.total_gasto_fixo_mensal`). Projeta o MÊS SEGUINTE (mesmo mês que aquele aviso já
  projeta). O integrador liga assim, sem duplicar o cálculo de fração/limiar que já existe
  lá:
  ```python
  custos_fixos = gastos.total_gasto_fixo_mensal(recorrentes)
  custos_fixos += financas_recorrentes.valor_para_aviso_custos_fixos(conn, hoje)
  fracao = custos_fixos / renda_media
  ```
- **`proximas_cobrancas(conn, hoje, limite=20)`** → lista ordenada da mais próxima pra
  mais longe, misturando assinaturas ativas e parcelas em andamento:
  `{"tipo": "assinatura"|"compra_parcelada", "id", "nome"|"descricao", "valor", "data"
  (ISO), "dias" (int, 0 = hoje), "label" ("hoje" | "amanhã" | "em N dias"), ...}`.
- **`parcela_info(compra, hoje)`** → `{"parcela_atual_calculada", "parcelas_pagas",
  "parcelas_restantes", "mes_termino" ("AAAA-MM"), "mes_termino_nome", "quitada",
  "proxima_cobranca"}`.
- **`impacto_limite_cartao_proximos_meses(conn, hoje, meses=6)`** → lista por cartão
  citado: `{"cartao", "limite" (float ou null), "meses": [{"mes", "total", "fracao"
  (0..1 ou null), "sobra" (ou null)}, ...]}`. Soma **só** o que esta faixa conhece
  (assinatura + parcela) - não inclui outro gasto no mesmo cartão vindo de
  `expenses`/`bank_transactions`; é um PISO do comprometimento, não o total gasto no
  cartão. `fracao`/`sobra` vêm de `vida.fracao_limite_cartao` (reuso, não reimplementação).
- **`resumo_financeiro_recorrente(conn, hoje)`** → o dado por trás do card
  `resumo_financeiro_recorrente` (ver abaixo).

## Rotas (`rotas/n1_financas.py`, sessão - mesma autenticação por PIN do resto do app)

| Rota | Método | Corpo | Resposta |
| :--- | :--- | :--- | :--- |
| `/api/financas/assinaturas` | GET | `?ativas=1` opcional | `{"assinaturas": [assinatura + "proxima_cobranca", ...]}` |
| `/api/financas/assinaturas/<id>` | GET | - | `assinatura` ou 404 |
| `/api/financas/assinaturas` | POST | `{nome, valor, dia_cobranca, cartao_ou_forma?, categoria?, inicio?, observacao?}` | `assinatura`, 201; 400 se faltar campo obrigatório |
| `/api/financas/assinaturas/<id>` | PATCH | campos editáveis (`nome`, `valor`, `dia_cobranca`, `cartao_ou_forma`, `categoria`, `observacao`) | `assinatura` atualizada; 404 se não existir/nada mudou |
| `/api/financas/assinaturas/<id>/cancelar` | POST | - | `assinatura` cancelada; 404 se não existir/já cancelada |
| `/api/financas/assinaturas/<id>` | DELETE | - | `{"ok": true}`; 404 se não existir |
| `/api/financas/parcelas` | GET | `?em_andamento=1` opcional | `{"parcelas": [compra_parcelada + parcela_info, ...]}` |
| `/api/financas/parcelas/<id>` | GET | - | `compra_parcelada` + `parcela_info`; 404 |
| `/api/financas/parcelas` | POST | `{descricao, n_parcelas, valor_total? ou valor_parcela?, cartao?, primeira_parcela?, categoria?}` | `compra_parcelada` + `parcela_info`, 201; 400 se faltar `valor_total`/`valor_parcela` |
| `/api/financas/parcelas/<id>` | DELETE | - | `{"ok": true}`; 404 |
| `/api/financas/comprometido` | GET | - | `{"total_mensal": ..., "proximas_cobrancas": [...], "impacto_limite_cartao": [...]}` - resumo pronto pra tela do cartão (V6) |
| `/api/financas/desfazer/<token>` | POST | - | `{"ok": true, "desfeitos": n}` 200 / `{"error": "..."}` 404 / 409 |

## Classificador local (`classificador_local/regras/n1_financas.py`)

Segue o contrato de `classificador_local/__init__.py` (Etapa 0): `casar(texto) ->
{"acao", "parametros"} | None`, `executar(conn, parametros) -> {"cards", "resumo_texto",
"passos"}`. Frases reconhecidas (exemplos - ver o módulo pros regex exatos, aceitam
variação de espaço/maiúscula, `R$`, "reais", vírgula decimal, "10x"/"10 vezes"):

| Frase (exemplo) | Ação |
| :--- | :--- |
| "assinei Netflix 55 por mês" / "assinei o Spotify por 21,90" | cria `assinatura` (dia de cobrança = hoje) |
| "comprei o celular em 10x de 300" | cria `compra_parcelada` (valor_parcela informado) |
| "comprei geladeira 3000 em 12 vezes no nubank" | cria `compra_parcelada` (valor_total + cartão) |
| "cancelei a Netflix" | cancela a assinatura ativa com esse nome (busca aproximada) - "não encontrei" sem cards se não achar |
| "quanto tenho de parcelas?" | consulta: card `resumo_financeiro_recorrente` + um `compra_parcelada` por compra em andamento |
| "quais assinaturas eu tenho" | consulta: card `resumo_financeiro_recorrente` + um `assinatura` por assinatura ativa |

## Cards

Mesmo envelope de `docs/CARDS.md` (`{cards: [{type, id, data, actions}], resumo_texto,
passos}`). Card de consulta traz `data.consulta = true` e sem action `desfazer` (mesma
regra do resto do contrato).

### `assinatura`

```json
{
  "id": 5, "nome": "Spotify", "valor": 21.9, "dia_cobranca": 24,
  "cartao_ou_forma": "nubank", "categoria": null, "ativa": true,
  "inicio": "2026-09-24", "cancelada_em": null,
  "proxima_cobranca": "2026-10-24"
}
```

- `proxima_cobranca` (data ISO) é `null` só se a assinatura estiver cancelada (sem
  cancelamento, sempre tem uma próxima data - a fórmula avança pro mês seguinte quando o
  dia deste mês já passou).
- Card sensível (dinheiro): `valor` some no modo visitante quando `cards.py` cadastrar em
  `CAMPOS_SENSIVEIS` (ver checklist acima).

### `compra_parcelada`

```json
{
  "id": 2, "descricao": "geladeira", "valor_total": 3000.0, "n_parcelas": 12,
  "valor_parcela": 250.0, "cartao": "nubank", "primeira_parcela": "2026-09-24",
  "categoria": null, "parcela_atual": 1, "parcelas_restantes": 12,
  "mes_termino": "2027-08", "quitada": false
}
```

- `parcela_atual`/`parcelas_restantes`/`mes_termino`/`quitada` aqui são sempre os valores
  CALCULADOS (`parcela_info`), nunca a coluna crua `parcela_atual` do banco.
- Card sensível: `valor_total`/`valor_parcela`.

### `resumo_financeiro_recorrente`

```json
{
  "mes": "2026-09", "total_mensal": 571.9, "assinaturas_total": 21.9,
  "parcelas_total": 550.0, "n_assinaturas_ativas": 1, "n_compras_em_andamento": 2,
  "proximas_cobrancas": [
    { "tipo": "assinatura", "id": 5, "nome": "Spotify", "valor": 21.9,
      "data": "2026-10-24", "dias": 30, "label": "em 30 dias", "cartao_ou_forma": "nubank" }
  ],
  "consulta": true
}
```

- `proximas_cobrancas` aqui vem limitado a 5 itens (a lista completa é
  `GET /api/financas/comprometido`).
- Card sensível: `total_mensal`, `assinaturas_total`, `parcelas_total`, e o `valor` dentro
  de cada item de `proximas_cobrancas`.

## Desfazer

Mecanismo próprio desta faixa (`financas_recorrentes.criar_token_desfazer` /
`aplicar_desfazer`), até `db.ENTIDADES_DESFAZIVEIS`/`app._desfazer_itens` ganharem as
entidades `assinatura`/`compra_parcelada` (ver "Relação com o que já existe" acima). Grava
na MESMA tabela `acoes_desfazer` (schema genérico, já existente desde a Fase 6), então
convive sem conflito com o Desfazer geral - só a ROTA que aplica é diferente:
`POST /api/financas/desfazer/<token>` em vez de `POST /api/desfazer/<token>`. Pro
frontend, o card é idêntico ao de qualquer outra entidade (`docs/CARDS.md`, action
`desfazer`, mesmo formato `{tipo, rotulo, token, alvo}`) - só o endpoint que o botão chama
muda, e isso é decidido pelo `type` do card (`assinatura`/`compra_parcelada` → rota desta
faixa; qualquer outro → rota geral). Respostas: `200 {"ok": true, "desfeitos": n}` / `404`
token desconhecido (inclusive um token de OUTRA faixa) / `409` já desfeito.

Ações desfazíveis: criar assinatura (apaga), cancelar assinatura (reativa), criar compra
parcelada (apaga). Editar (`PATCH`) e excluir (`DELETE`) direto pela rota não têm Desfazer
(mesmo padrão de outras entidades do app: só a ação que o CHAT/classificador executa tem
botão Desfazer).
