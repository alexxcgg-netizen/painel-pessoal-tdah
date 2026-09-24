# Widget com API Widget (apps "API Widget" ou "API Widgets")

Existem vários apps no App Store que funcionam como "construtores de widget" lendo JSON de um endpoint HTTP. Alguns nomes comuns:

- **API Widget** (by Aweb)
- **API Widgets**
- Outros apps similares que permitem "Custom JSON" ou "HTTP Widget"

Todos funcionam de forma parecida: você configura uma URL de um endpoint JSON, mapeando os campos do JSON diretamente para elementos visuais do widget.

## Antes de começar

- Instale um desses apps (veja qual tem melhor avaliação na App Store ou teste um trial).
- Tenha o endereço do painel e o token de acesso (se configurado).
- O endpoint: `GET /api/widget` ou `GET /api/widget?token=<PAINEL_WIDGET_TOKEN>`

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
  "linhas": ["Foco: Revisar contrato em 19 min", "Conta: Cartão em 3 dias", "Hábitos: 3/5", "IA: 42% do teto"]
}
```

## Como configurar (passos gerais)

1. Abra o app (API Widget, API Widgets, etc).
2. Toque em **Novo widget** ou **Adicionar widget**.
3. Escolha **"Custom JSON"** ou **"HTTP"** (o nome pode variar).
4. Preencha a URL:
   - `http://seu-painel.com/api/widget` (sem autenticação)
   - `http://seu-painel.com/api/widget?token=SEU_TOKEN` (com token)
5. Configure o **intervalo de atualização**: recomenda-se 15 a 30 minutos.
6. Procure a opção de **"Mapear campos"** ou **"JSON fields"**.

## Mapeamento dos campos (JSON paths)

Os apps costumam ter uma interface gráfica para você "arrastar" campos do JSON. Os caminhos exatos a usar são:

| O que você quer mostrar | Caminho JSON | Exemplo |
|---|---|---|
| Título do foco atual | `foco.titulo` | "Revisar contrato" |
| Tempo restante do foco (minutos) | `foco.em_minutos` | 19 |
| Nome da próxima conta a vencer | `proxima_conta.nome` | "Cartão" |
| Dias até a próxima conta vencer | `proxima_conta.em_dias` | 3 |
| Hábitos completados hoje | `habitos.feitos` | 3 |
| Total de hábitos do dia | `habitos.total` | 5 |
| Percentual do teto de IA usado | `custo_ia.percentual_teto` | 42 |
| Texto pronto (linha 1) | `linhas[0]` | "Foco: Revisar contrato em 19 min" |
| Texto pronto (linha 2) | `linhas[1]` | "Conta: Cartão em 3 dias" |
| Texto pronto (linha 3) | `linhas[2]` | "Hábitos: 3/5" |
| Texto pronto (linha 4) | `linhas[3]` | "IA: 42% do teto" |
| Estado do widget | `estado` | "normal", "vazio" ou "erro" |
| Data/hora da última atualização | `atualizado_em` | "2026-09-23T20:10:00Z" |

**Nota importante**: O app pode chamar arrays de forma diferente. Se digitar `linhas[0]` não funcionar, tente:
- `linhas.0`
- `linhas.first`
- Procure na documentação do seu app específico como referenciar posições de array.

## Exemplos por tamanho de widget

### Widget pequeno (2x2)

Mostrar as 4 linhas principais (já vêm prontas no JSON):

```
Foco: Revisar contrato em 19 min
Conta: Cartão em 3 dias
Hábitos: 3/5
IA: 42% do teto
```

**No app**:
- Adicione 4 campos de **Text** (ou **Label**).
- Mapeie cada um para: `linhas[0]`, `linhas[1]`, `linhas[2]`, `linhas[3]`.

### Widget médio (3x3)

Usar as mesmas 4 linhas, mas com mais espaço visual. Talvez adicione um título ou icone:

```
PAINEL RESUMO
━━━━━━━━━━━━━
Foco: Revisar contrato em 19 min
Conta: Cartão em 3 dias
Hábitos: 3/5

IA: 42% do teto
```

**No app**:
- Adicione um **Text** ou **Title** com o valor fixo "PAINEL RESUMO".
- Adicione 4 campos **Text** mapeados para `linhas[0]` a `linhas[3]`.

### Tela de bloqueio (iOS 16+)

A tela de bloqueio é menor. Use apenas as informações principais:

```
Revisar contrato (19 min)
Cartão: em 3 dias
```

**No app**, procure a opção de **"Lock Screen"** ou **"Compact view"**:
- Mapeie `foco.titulo` em um campo.
- Mapeie `proxima_conta.nome` e `proxima_conta.em_dias` em outro.

## Autenticação

Se o painel tiver `PAINEL_WIDGET_TOKEN` configurado:

- **Com token na URL** (recomendado): `http://seu-painel.com/api/widget?token=seu_token_aqui`
- O app fará um GET simples. Não há suporte para headers customizados na maioria dos apps.

**Nota sobre segurança**: O token fica visível na URL. Isso é aceitável agora e será revisado na Fase de Segurança.

## Dicas

- **O iOS controla a atualização**: Independente do intervalo que você configurar, o iOS decide quando o widget atualiza. Pode levar alguns minutos.
- **Toque no widget**: Tocar no widget abre um link no Safari. Configure o app para abrir `http://seu-painel.com` (ou o endereço do seu painel).
- **Se não atualizar**: Verifique na documentação do seu app específico se há um limite de requisições por hora.
- **Apps diferentes, comportamentos diferentes**: Cada app tem sua própria interface. Se uma opção não existir, procure no menu equivalente ou na documentação do app.

## Testando antes de instalar

1. Abra um navegador e acesse: `http://seu-painel.com/api/widget` (ou com token).
2. Confirme que você vê um JSON com os campos acima.
3. Copie o JSON inteiro.
4. Configure o app apontando para essa URL.
5. Se o widget aparecer corretamente no preview do app, você está pronto.
