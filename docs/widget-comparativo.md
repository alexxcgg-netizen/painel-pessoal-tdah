# Comparativo de Opções de Widget — Resultados do Teste

Esta tabela é **em branco** para você preencher testando cada opção e anotando os resultados. Teste em real (iPhone, Apple Watch se aplicável) e anote o que funcionou melhor para você.

## Instruções de preenchimento

1. **Teste cada opção** listada abaixo por pelo menos 2 dias.
2. **Preencha os campos** com sua experiência pessoal (não há resposta "certa", é subjetivo).
3. **Notas** são opcionais, mas ajudam a lembrar por que você escolheu uma opção.
4. Depois de testar todas, **coloque em produção** a que melhor se encaixou no seu fluxo.

## Tabela de comparação

| Aspecto | Scriptable | Widgy | API Widget | Glimpse 2 | Atalhos | WidgetKit nativo |
|---------|-----------|-------|-----------|-----------|---------|-----------------|
| **Custo** | | | | | | |
| **Frequência de atualização** | | | | | | |
| **Aparência / UI** | | | | | | |
| **Tela de bloqueio (iOS 16+)** | | | | | | |
| **O que o toque abre** | | | | | | |
| **Facilidade de configuração** | | | | | | |
| **Notas pessoais** | | | | | | |

## Guia de preenchimento por linha

### Custo
- Escreva: **Grátis**, **Pago (R$...)**, **Trial com limite**, etc.
- Qual opção oferece o melhor custo-benefício?

### Frequência de atualização
- Escreva: **Tempo real**, **A cada 5 min**, **15-30 min**, **1 hora**, **Manual (toque)**
- Qual é o intervalo mínimo que o app permite?
- O iOS respeitou o intervalo ou atualizou menos frequentemente?

### Aparência / UI
- Escreva: **Textual simples**, **Moderno com ícones**, **Customizável**, **HTML renderizado**, etc.
- Como ficou visualmente? Fácil de ler?

### Tela de bloqueio (iOS 16+)
- Escreva: **Suportado (tamanho: circular/retangular/inline)**, **Não suportado**, **Suportado mas feio**, etc.
- Funcionou bem na tela de bloqueio?

### O que o toque abre
- Escreva: **Abre o painel**, **Abre o app nativo**, **Nada/não é interativo**, **Customizável (qual ação?)**
- O toque faz o que você espera?

### Facilidade de configuração
- Escreva: **Muito fácil (1-2 passos)**, **Normal (5-10 passos)**, **Complexo (programar)**, etc.
- Você precisou de ajuda? Qual foi o maior obstáculo?

### Notas pessoais
- Espaço livre para qualquer observação:
  - Problemas que encontrou
  - Recursos que gostaria que tivesse
  - Razão pela qual escolheu (ou não) essa opção
  - Caso de uso ideal para essa opção

## Exemplo de preenchimento (fictício)

| Aspecto | Scriptable | Widgy |
|---------|-----------|-------|
| **Custo** | Grátis | Grátis com Pro ($4.99/mês) |
| **Frequência de atualização** | 5-10 min | 15 min (mínimo free) |
| **Aparência / UI** | Textual, customizável com cores | Muito customizável, ícones bonitos |
| **Tela de bloqueio (iOS 16+)** | Retangular funciona bem | Suportado (pequeno) |
| **O que o toque abre** | Abre o painel no Safari | Abre o link customizável |
| **Facilidade de configuração** | Copiar script = fácil | Interface gráfica = mais intuitiva |
| **Notas pessoais** | Leve, rápido, sem UI bonita. Bom para info crua. | Mais visual, atualiza menos. Tive que pagar Pro. |

(Este é só um exemplo; preencha com seus verdadeiros testes!)

## Notas importantes

- **O iOS decide a atualização**: Independente do intervalo que você configurar, o iOS pode atualizar menos frequentemente para poupar bateria. A frequência que você coloca é o *máximo*, não o garantido.
- **Tocar no widget no iOS**: Geralmente abre o navegador no Safari (para HTTP/HTTPS). O PWA instalado abre só se você tiver configurado um link para `seu-domínio.com` e o PWA instalado naquele domínio.
- **Segurança do token**: Todas as opções que colocam o token na URL expõem ele. Isso é aceitável agora e será revisado na Fase 10 (revisão de segurança).
- **Testando**: Abra o painel em outro device ou navegador, faça uma mudança (marque uma tarefa, complete um hábito), e veja se o widget atualiza.

## Opções não documentadas (pesquisa extra)

Se você quiser testar outras opções (Scriptable, WidgetKit nativo, ou apps não listados), adicione linhas extras na tabela acima.

## Próximos passos após preencher

1. **Escolher a melhor opção** com base em seus testes.
2. **Desinstalar as outras** (libera espaço e reduz confusão).
3. **Otimizar a escolhida** com base nas notas.
4. Se precisar de ajustes no endpoint `/api/widget` ou `/widget`, abra uma issue ou conversation.
