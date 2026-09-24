# Widget com Atalhos (Shortcuts/app Atalhos)

O app **Atalhos** (Shortcuts) do iOS permite criar automações e widgets que executam ações, incluindo chamar endpoints HTTP e exibir resultados. É mais poderoso que os outros (você programa o comportamento), mas também requer alguns passos.

## Antes de começar

- Use o app nativo **Atalhos** (vem pré-instalado no iOS 12+) ou baixe se não tiver.
- Tenha o endereço do painel e o token de acesso (se configurado).
- O endpoint: `GET /api/widget` ou `GET /api/widget?token=<PAINEL_WIDGET_TOKEN>`

## Atalho 1: Obter dados do painel e exibir

Este é o atalho mais simples: busca o JSON do painel e exibe em um alert.

### Passos para criar

1. Abra o app **Atalhos**.
2. Toque em **Criar atalho** (ou **+**).
3. Procure e adicione estes blocos (ações) **nesta ordem**:

#### Passo 1: "Obter conteúdo de URL"
- Ação: **Obter conteúdo de URL**
- URL: `http://seu-painel.com/api/widget?token=SEU_TOKEN`
- Método: GET
- (Deixe outros campos em branco)

#### Passo 2: "Obter valor do dicionário"
- Ação: **Obter valor do dicionário**
- Dicionário: `Resultado do passo anterior` (conecte ao bloco acima)
- Chave: procure a opção **"especificar chave customizada"** e digite `linhas`

  *Alternativa*: Se a interface mostrar `linhas[0]`, use isso para pegar só a primeira linha.

#### Passo 3: "Mostrar resultado" (alert)
- Ação: **Mostrar resultado**
- Variável: `Resultado do passo anterior`

### O que esse atalho faz

Quando você toca nele:
1. Busca os dados do painel (`/api/widget`).
2. Extrai o array `linhas` (que contém 4 textos prontos).
3. Exibe em um alert na tela.

**Resultado esperado**:
```
Foco: Revisar contrato em 19 min
Conta: Cartão em 3 dias
Hábitos: 3/5
IA: 42% do teto
```

### Salvando o atalho

1. Toque em **Concluído** (canto superior).
2. Escolha um nome (ex: "Painel resumo").
3. Escolha um ícone e cor (opcional).
4. Toque em **Salvar**.

## Atalho 2: Widget na tela de início

Para colocar o atalho como widget (não apenas na lista de Atalhos), você precisa:

### Passo 1: Editar o atalho (adicionar interface visual)

Opcionalmente, altere o atalho anterior para mostrar um resultado mais bonito:

1. No fim do atalho, antes de **"Mostrar resultado"**, adicione:
   - Ação: **Texto** (ou **Text**)
   - Digite: `"Painel - "` (ou qualquer prefixo)

2. Depois, use **Juntar textos** (Combine) para montar a mensagem:
   - Juntar: `"Painel - "` + `Resultado anterior`

### Passo 2: Adicionar o widget à tela de início

1. Na tela de início do iPhone, **mantenha pressionado** em um espaço vazio.
2. Toque em **Atalhos** (no painel de widgets que aparecer, ou procure à direita na lista).
3. Procure pelo atalho **"Painel resumo"** (ou o nome que você deu).
4. Escolha o tamanho: pequeno (1 ação), médio (2-3 ações) ou grande (mais).
5. Toque em **Adicionar widget**.

O widget aparece na tela de início. Tocar nele executa o atalho.

## Atalho 3: Captura rápida (Menu rápido - iOS 17+)

Se você tiver iOS 17 ou superior, pode adicionar o atalho à **Captura rápida** (Quick actions), que aparece quando você segura o botão lateral ou a tela de bloqueio:

1. Abra o atalho **"Painel resumo"**.
2. Toque em **Compartilhar** (canto inferior direito).
3. Procure por **"Mostrar na captura rápida"** ou **"Show in Quick Actions"**.
4. Toque em ativá-lo (deve ficar com uma marca de seleção).

Agora, na tela de bloqueio, quando você segura no botão lateral, o atalho aparece como ação rápida.

## Estrutura completa do atalho (exemplo)

```
┌─ Obter conteúdo de URL
│  └─ http://seu-painel.com/api/widget?token=SEU_TOKEN
│
├─ Obter valor do dicionário
│  ├─ Dicionário: [resultado anterior]
│  └─ Chave: linhas
│
├─ Obter valor do dicionário  (opcional, para timestamp)
│  ├─ Dicionário: [resultado da primeira busca]
│  └─ Chave: atualizado_em
│
├─ Texto
│  └─ "Atualizado em: "
│
├─ Juntar textos
│  ├─ Texto 1: "Atualizado em: "
│  └─ Texto 2: [resultado do timestamp]
│
└─ Mostrar resultado
   └─ [resultado das linhas]
```

## Autenticação com token

Se o painel tiver `PAINEL_WIDGET_TOKEN`:

- **Na URL**: `http://seu-painel.com/api/widget?token=seu_token_aqui`
- O atalho fará um GET simples.

**Nota sobre segurança**: O token fica visível no atalho (abra a edição e vê a URL). É aceitável agora e será revisado na Fase de Segurança.

## Campos disponíveis do JSON (para customizar)

Se você quiser modificar o atalho e mostrar campos específicos, use estes caminhos:

| Campo | Caminho no Atalhos | Exemplo |
|---|---|---|
| Foco (título) | `foco` → `titulo` | "Revisar contrato" |
| Foco (minutos) | `foco` → `em_minutos` | 19 |
| Próxima conta | `proxima_conta` → `nome` | "Cartão" |
| Dias até conta | `proxima_conta` → `em_dias` | 3 |
| Hábitos feitos | `habitos` → `feitos` | 3 |
| Hábitos total | `habitos` → `total` | 5 |
| % IA | `custo_ia` → `percentual_teto` | 42 |
| Linhas prontas | `linhas` → `[0]`, `[1]`, `[2]`, `[3]` | textos prontos |
| Estado | `estado` | "normal", "vazio", "erro" |
| Última atualização | `atualizado_em` | ISO 8601 |

## Dicas

- **O widget não atualiza automaticamente**: Os widgets de Atalhos atualizam quando você toca neles ou em um horário configurável. Configure a atualização em **Editar atalho** → **Mais opções** → procure por **"Executar atalho"** ou **"When run"**.
- **Diferente dos outros widgets**: Atalhos é mais uma ferramenta de automação. Use quando quiser controle total sobre o que mostrar.
- **Combinações**: Você pode combinar múltiplas ações no mesmo atalho (chamar painel + abrir app, chamar painel + enviar notificação, etc).

## Testando antes de instalar no widget

1. Abra o atalho recém-criado tocando nele.
2. Confirme que ele busca os dados e exibe corretamente.
3. Se funcionar, adicione à tela de início como widget (passo anterior).
4. Se não funcionar, verifique a URL no bloco **"Obter conteúdo de URL"**.

## Alternativa: Automação periódica

Em vez de um widget, você pode criar uma **Automação** que roda em horários definidos:

1. Abra Atalhos → guia **Automação**.
2. Toque em **Criar automação pessoal**.
3. Escolha **"Hora do dia"** (para rodar todo dia em horário específico).
4. Configure o horário (ex: 9:00 da manhã).
5. Escolha o atalho **"Painel resumo"** para executar.
6. Ative **"Notificar-me quando executado"** se quiser um aviso.

Assim, o atalho roda automaticamente e mostra uma notificação com os dados.
