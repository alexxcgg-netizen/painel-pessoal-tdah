# Widget Glimpse 2

O **Glimpse 2** é um app de widgets que exibe páginas web completas (HTML) como widget. Ele carrega e renderiza uma página inteira, permitindo conteúdo mais rico e interativo que apps JSON simples.

## Antes de começar

- Instale o **Glimpse 2** (App Store, há versão gratuita).
- Tenha o endereço do painel e o token de acesso (se configurado).
- O endpoint que o Glimpse vai carregar: `GET /widget` ou `GET /widget?token=<PAINEL_WIDGET_TOKEN>`

## O que o Glimpse vai receber

O endpoint `GET /widget` retorna uma página HTML leve e responsiva, otimizada para widget. O HTML mostra o mesmo resumo que o JSON:

```
┌─────────────────────┐
│  PAINEL RESUMO      │
├─────────────────────┤
│ Revisar contrato    │
│ em 19 minutos       │
│                     │
│ Próxima: Cartão     │
│ em 3 dias           │
│                     │
│ Hábitos: 3/5        │
│ IA: 42% do teto     │
└─────────────────────┘
```

## Como configurar

### 1. Adicionar um widget Glimpse

1. Abra o app **Glimpse 2**.
2. Toque em **+** (novo widget) ou **Add widget**.
3. Escolha **"Web page"** ou **"HTML widget"**.
4. Preencha com:
   - **URL**: `http://seu-painel.com/widget` ou `http://seu-painel.com/widget?token=SEU_TOKEN`
   - **Intervalo de atualização**: recomenda-se 15 a 30 minutos.
   - **Tamanho**: escolha entre pequeno, médio ou grande (widget ajusta automaticamente).

### 2. Configurações de segurança e token

Se o painel tiver `PAINEL_WIDGET_TOKEN`:

- **Com token na URL**: `http://seu-painel.com/widget?token=seu_token_aqui`
- O Glimpse fará um GET simples e renderizará a página normalmente.

**Nota sobre segurança**: O token fica visível na URL. Isso é aceitável agora e será revisado na Fase de Segurança.

## Exemplos por tamanho de widget

### Widget pequeno (2x2)

Mostra apenas as informações principais em texto simples:

```
PAINEL
Foco: Revisar contrato
em 19 minutos

Próxima: Cartão em 3 dias
```

A página HTML é renderizada de forma compacta.

### Widget médio (3x3)

Mostra um resumo mais completo com melhor formatação:

```
PAINEL RESUMO
━━━━━━━━━━━━━━━━━━
Foco: Revisar contrato
       em 19 minutos

Próxima conta: Cartão
                em 3 dias

Hábitos: 3/5 completos
IA: 42% do teto
```

### Tela de bloqueio (iOS 16+)

O Glimpse renderiza a mesma página em tamanho menor:

```
PAINEL
Revisar contrato (19 min)
Cartão em 3 dias
Hábitos: 3/5
```

## Recursos da página HTML

A página `/widget` é otimizada para:

- **Responsividade**: Ajusta-se a diferentes tamanhos de tela.
- **Modo claro/escuro**: Respeita a preferência de tema do iPhone.
- **Carregamento rápido**: HTML leve, sem JavaScript pesado.
- **Atualização**: Carrega dados da mesma API que o JSON (`/api/widget`), então sempre mostra informações atualizadas.

## Interatividade

- **Toque no widget**: Abre o link principal do painel no Safari (não é interativo dentro do widget, apenas o toque abre a URL).
- **Botões e links**: Se a página HTML incluir links, tocar abre o link padrão do painel no Safari.

## Dicas

- **O iOS controla a atualização**: Pode levar alguns minutos para refletir mudanças.
- **Se aparecer em branco**: 
  1. Confira se a URL é acessível no navegador.
  2. Se houver token, verifique se está correto.
  3. Verifique se o painel está rodando.
- **Renderização**: O Glimpse renderiza HTML padrão. Se a página tiver CSS customizado, o Glimpse respeita (fonte, cor, layout).

## Testando antes de instalar

1. Abra um navegador no iPhone ou computador.
2. Acesse: `http://seu-painel.com/widget` (ou com token).
3. Confirme que você vê uma página HTML legível com o resumo.
4. Configure o Glimpse apontando para essa URL.
5. Se o widget aparecer corretamente, você está pronto.

## Diferenças entre Glimpse 2 e outras opções

- **vs. Widgy**: Widgy é mais customizável (você constrói o layout), Glimpse renderiza o HTML como está.
- **vs. API Widget**: API Widget usa JSON com mapeamento de campos, Glimpse renderiza HTML completo.
- **vs. Atalhos**: Glimpse é mais simples (nenhuma programação), Atalhos permite automação mais complexa.
