# Aprendizados — N3cd: Widget Docs

## Estrutura e Padrões Encontrados

### JSON Path Consistency
Os caminhos JSON devem ser precisos e consistentes:
- Objetos aninhados: `foco.titulo`, `proxima_conta.nome`
- Arrays: `linhas[0]`, `linhas[1]`, etc (alguns apps podem usar `.0`, `.first` — foi mencionado nos docs)
- Versão e timestamp: `versao`, `atualizado_em`, `estado`

Isso foi testado conceitualmente contra a especificação fornecida no prompt.

### Variabilidade Entre Apps

Cada app tem sua própria interface e convenção de nomeação:
- **Widgy**: Usa interface gráfica, permite drag-and-drop, recomenda usar `[índice]` para arrays
- **API Widget/Widgets**: Genérico, cada app pode nomear diferente (procure no seu app específico)
- **Glimpse 2**: Renderiza HTML inteiro, não precisa mapear campos
- **Atalhos**: Usa ações (actions/blocks) em sequência, interface textual
- **Scriptable**: JavaScript puro (já documentado em WIDGET_TELA_BLOQUEIO.md)

### Tamanhos de Widget Padrão

Todos os apps seguem um padrão de grades iOS:
- **Pequeno (2x2)**: ~155x155 pt (mínimo, mostra pouco)
- **Médio (3x3)**: ~155x344 pt ou ~344x155 (paisagem)
- **Grande (4x4)**: ~344x344 pt (raro, não foi documentado pois nenhum app suporta bem)
- **Tela de bloqueio**: Retangular, circular, inline (tamanhos especiais iOS 16+)

## Segurança e Token

### Token na URL vs Header

- **URL**: `?token=...` funciona em todos os apps (GET simples). Fica visível em histórico de requisições.
- **Header**: `Authorization: Bearer` ou `X-Custom-Header` — nem todos os apps suportam customizar headers.

**Decisão**: Documentação menciona que token na URL é aceitável agora, será revisado na Fase 10.

### Segurança em Produção (Fase 10)

- Implementar HTTPS (não HTTP)
- Considerar OAuth ou short-lived tokens
- Considerar rate limiting
- Remover token da URL, usar header ou cookie

## Atualização de Widget

### iOS controla a frequência
Independente do intervalo que você configurar, o iOS pode:
- Aumentar o intervalo para economizar bateria
- Diminuir em momentos de pouco uso
- Bloquear completamente se o widget não tiver dados

Isso é importante mencionar em todos os docs.

## Dicas para Documentação Futura

### Nomes de Botões e Opções
Evitar nomes específicos de versão ou assumidos. Usar:
- "procure a opção de..."
- "pode estar chamado de..."
- "em algumas versões é..."

Isso torna a doc mais robusta contra atualizações dos apps.

### Estrutura de Docs
Cada doc seguiu:
1. Introdução (o que é)
2. Pré-requisitos
3. Estrutura de dados (JSON)
4. Como configurar (passo-a-passo)
5. Mapeamento de campos (tabela com JSON paths)
6. Exemplos por tamanho
7. Autenticação
8. Dicas e troubleshooting
9. Teste local

Isso facilita encontrar informação rapidamente.

## Considerações Técnicas

### Endpoint `/api/widget`
- Retorna JSON com versão, timestamp, estado, e dados estruturados
- Array `linhas` tem 4 textos prontos (facilita apps que não suportam template)
- Estado: `normal`, `vazio`, `erro` (para feedback visual)

### Endpoint `/widget`
- Retorna HTML leve (para Glimpse 2)
- Responsivo (adapta a tela de bloqueio, pequeno, médio, grande)
- Modo claro/escuro respeitado
- Sem JavaScript pesado

### Autenticação
Endpoint espera:
- Sem autenticação: funciona aberto
- Com `PAINEL_WIDGET_TOKEN`: espera `?token=...` ou header `Authorization: Bearer`

Documentação usa `?token=...` por ser mais universal.

## Recomendações para o Alex

1. **Comece por Atalhos** se quer controle total e rápido feedback.
2. **Widgy** se quer visual customizável e atualização rápida.
3. **Glimpse 2** se quer renderizar HTML pronto, mínima configuração.
4. **API Widget** é bom meio termo, mas cada app é diferente.
5. **Scriptable** já documentado em WIDGET_TELA_BLOQUEIO.md (tela de bloqueio).

## Testes Recomendados (quando implementação de /api/widget estiver pronta)

1. Teste com dados vazios (estado: "vazio") — cada app deve lidar gracefully
2. Teste com dados muito longos (próxima_conta.nome com 50+ chars) — como trunca?
3. Teste com timestamp muito antigo (última atualização > 1 hora) — indicar "fora de data"?
4. Teste a mudança de dados em tempo real (toque widget em <1 min após mudança de dados)

## Notas de Implementação (pra fase de código)

Nenhuma necessidade detectada. A documentação é apenas instructional para o Alex.

Se uma funcionalidade não estiver clara depois de testar, abrir issue com:
- Qual app (Widgy, Glimpse 2, etc)
- O que não funciona
- Screenshot ou erro esperado vs observado
