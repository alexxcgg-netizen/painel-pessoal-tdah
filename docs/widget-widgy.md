# Widget Widgy (app Widgy)

O **Widgy** é um app de widgets personalizáveis que lê dados em JSON via HTTP. Funciona na tela inicial e tela de bloqueio (a partir do iOS 16).

## Antes de começar

- Instale o **Widgy** (App Store, versão gratuita com recursos básicos).
- Configure `PAINEL_WIDGET_TOKEN` no `.env` do painel **antes** de tentar usar
  o widget — sem ele, o endpoint sempre devolve 401, mesmo sem nenhum token
  na URL (nunca fica aberto por padrão).
- O endpoint que o Widgy vai chamar: `GET /api/widget?token=<PAINEL_WIDGET_TOKEN>`

## Estrutura do JSON

O endpoint retorna um JSON com esta estrutura:

```json
{
  "versao": 1,
  "atualizado_em": "2026-09-23T20:10:00Z",
  "estado": "normal",
  "foco": {"titulo": "Revisar contrato", "em_minutos": 19},
  "proxima_conta": {"nome": "Cartão", "em_dias": 3},
  "habitos": {"feitos": 3, "total": 5},
  "custo_ia": {"percentual_teto": 42},
  "comida": {"kcal": 415, "proteina_g": 83, "carbo_g": 60, "gordura_g": 20, "refeicoes": 2, "meta_kcal": 2550, "meta_proteina_g": 115},
  "agenda": [{"hora": "10:40", "titulo": "Dentista", "em_minutos": 40, "tipo": "compromisso", "concluido": false}],
  "linhas": ["Foco: Revisar contrato em 19 min", "Conta: Cartão em 3 dias", "Hábitos: 3/5", "IA: 42% do teto"]
}
```

`agenda` é sempre uma lista (`[]` quando não tem nada hoje; `null` só no estado `erro`).
Até 6 itens de hoje, em ordem de horário; `tipo` é `compromisso`, `tarefa` ou `habito`.
A agenda NÃO entra em `linhas`. `comida` traz também `carbo_g` e `gordura_g` (inteiros, 0 por padrão).

## Como configurar

### 1. Adicionar uma nova fonte de dados no Widgy

1. Abra o app **Widgy**.
2. Toque no **+** (nova tela) ou edite uma existente.
3. Toque em **Adicionar widget** ou **Editar fonte de dados**.
4. Procure por **"Dados HTTP"** ou **"Custom URL"** (o nome exato depende da versão do Widgy).
5. Preencha com:
   - **URL**: `http://seu-painel.com/api/widget` ou `http://seu-painel.com/api/widget?token=SEU_TOKEN`
   - **Método**: GET
   - **Intervalo de atualização**: recomenda-se 15 a 30 minutos (quanto menor, mais bateria consome)

### 2. Mapeamento dos campos (JSON paths)

No Widgy, quando você escolhe "inserir campo do JSON", use estes caminhos **exatos**:

| O que você quer mostrar | Caminho JSON | Exemplo |
|---|---|---|
| Título do foco atual | `foco.titulo` | "Revisar contrato" |
| Tempo restante do foco (minutos) | `foco.em_minutos` | 19 |
| Nome da próxima conta a vencer | `proxima_conta.nome` | "Cartão" |
| Dias até a próxima conta vencer | `proxima_conta.em_dias` | 3 |
| Hábitos completados hoje | `habitos.feitos` | 3 |
| Total de hábitos do dia | `habitos.total` | 5 |
| Percentual do teto de IA usado | `custo_ia.percentual_teto` | 42 |
| Texto pronto (linha) | `linhas[0]` ou `linhas[1]`, etc | "Foco: Revisar contrato em 19 min" |
| Estado do widget | `estado` | "normal", "vazio" ou "erro" |
| Data/hora da última atualização | `atualizado_em` | "2026-09-23T20:10:00Z" |

**Observação**: O Widgy pode chamar de `índice` em vez de `[0]`, `[1]`, etc. Se disso, procure a opção **"Índice"** ou **"Array index"** na documentação do Widgy.

## Exemplos por tamanho de widget

### Widget pequeno (2x2)

Mostrar as informações principais em 4 linhas:

```
Foco: Revisar contrato em 19 min
Próxima conta: Cartão em 3 dias
Hábitos: 3/5 completos
IA: 42% do teto
```

**Caminhos a usar**: `linhas[0]`, `linhas[1]`, `linhas[2]`, `linhas[3]`

Ou construir manualmente:
- Linha 1: `foco.titulo` + " em " + `foco.em_minutos` + " min"
- Linha 2: `proxima_conta.nome` + " em " + `proxima_conta.em_dias` + " dias"
- Linha 3: "Hábitos: " + `habitos.feitos` + "/" + `habitos.total`
- Linha 4: "IA: " + `custo_ia.percentual_teto` + "%"

### Widget médio (3x3)

Mostrar as linhas prontas com um pouco mais de espaço, talvez adicionar a hora da atualização:

```
Foco: Revisar contrato em 19 min
Próxima conta: Cartão em 3 dias
Hábitos: 3/5 completos

IA: 42% do teto
Atualizado em: 20:10
```

**Caminhos a usar**:
- `linhas[0]`, `linhas[1]`, `linhas[2]`, `linhas[3]`
- `atualizado_em` (formatado sem a data: apenas a hora)

### Tela de bloqueio (iOS 16+, formato retangular)

No Widgy, a tela de bloqueio usa o formato **Retangular** (ou procure por **"Lock Screen"**):

```
Foco: Revisar contrato
Próxima: Cartão em 3 dias
```

**Caminhos**: `foco.titulo` e uma combinação de `proxima_conta.nome` + `proxima_conta.em_dias`

## Autenticação

Se o painel tiver `PAINEL_WIDGET_TOKEN` configurado no `.env`:

- **Com token na URL**: `GET /api/widget?token=seu_token_aqui`
- **Com token no header**: Não é possível no Widgy de forma nativa (o app envia GET simples). Neste caso, passe o token como parâmetro na URL (`?token=...`).

**Nota sobre segurança**: O token na URL fica visível no histórico de requisições. Isso é aceitável agora e será revisado na Fase de Segurança (Fase 10).

## Dicas

- O iOS decide quando o widget atualiza, independente do intervalo que você configurar. Pode levar alguns minutos para refletir mudanças.
- Se o Widgy mostrar "Erro ao carregar", verifique:
  1. A URL está correta e acessível (teste no navegador).
  2. Se houver token, ele está correto.
  3. O intervalo de atualização não é muito curto (menos de 5 minutos pode ser rejeitado).

## Testes locais

Para testar antes de colocar no iPhone:

1. Abra um navegador no computador e cole: `http://seu-painel.com/api/widget` (ou com token).
2. Confirme que você vê um JSON com os campos descritos acima.
3. Configure o Widgy apontando para esse URL.
