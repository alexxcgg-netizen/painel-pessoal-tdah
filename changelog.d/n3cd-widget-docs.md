# N3cd: Documentação de Opções de Widget do iPhone

## Resumo

Fase 7, bandas N3c e N3d. Documentação completa de 5 opções de widget para iPhone que consomem o novo endpoint de widget (`GET /api/widget` em JSON, `GET /widget` em HTML). Sem código de produção; só docs para o Alex testar e escolher a melhor opção.

## Novo

### Documentação de Widgets (N3c)

- **`docs/widget-widgy.md`**: Documentação do app Widgy
  - Configuração passo-a-passo
  - Mapeamento de JSON paths (foco.titulo, proxima_conta.nome, linhas[0-3], etc)
  - Exemplos para pequeno (2x2), médio (3x3), tela de bloqueio
  - Autenticação com token na URL
  - Troubleshooting

- **`docs/widget-api-widget.md`**: Documentação de apps "API Widget"/"API Widgets"
  - Configuração para apps JSON genéricos
  - Mapeamento de campos (JSON paths)
  - Exemplos por tamanho de widget
  - Notas sobre variações entre apps

### Documentação de Widgets (N3d)

- **`docs/widget-glimpse.md`**: Documentação do app Glimpse 2
  - Renderiza página HTML `/widget`
  - Configuração de URL com token
  - Exemplos de renderização por tamanho
  - Interatividade e dicas

- **`docs/widget-atalhos.md`**: Documentação do app nativo Atalhos (Shortcuts)
  - Atalho 1: Obter dados e exibir (alert)
  - Atalho 2: Widget na tela de início
  - Atalho 3: Captura rápida (iOS 17+)
  - Automação periódica (bônus)
  - Estrutura completa de blocos (actions)

- **`docs/widget-comparativo.md`**: Tabela comparativa em branco
  - Para o Alex preencher testando cada opção (Scriptable, Widgy, API Widget, Glimpse 2, Atalhos, WidgetKit nativo)
  - Colunas: custo, frequência de atualização, aparência, tela de bloqueio, o que o toque abre, facilidade, notas
  - Inclui notas importantes (iOS controla atualização, token na URL, segurança)

## Scripts

- **`scripts/ralph-n3cd-widget-docs/progress.txt`**: Rastreamento de progresso
  - 5 histórias: Widgy docs, API Widget docs, Glimpse docs, Atalhos docs, Tabela comparativa
  - Tudo concluído, nenhuma bloqueada

- **`scripts/ralph-n3cd-widget-docs/APRENDIZADOS.md`**: Notas técnicas
  - JSON paths, variabilidade entre apps
  - Tamanhos de widget padrão
  - Token na URL vs header
  - Comportamento de atualização do iOS
  - Recomendações para escolher widget
  - Testes sugeridos para implementação
  - Padrões de documentação usados

## Changelog

- **`changelog.d/n3cd-widget-docs.md`**: Esta entrada

## Contexto Técnico

O novo endpoint `/api/widget` (JSON) e `/widget` (HTML) expõem um resumo do painel:

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

Documentação cobre:
- Como cada app consome esse JSON
- Mapeamento preciso de campos (ex: `foco.titulo`, `linhas[0]`)
- Exemplos visuais por tamanho de widget
- Autenticação (token na URL é aceitável agora, revisado na Fase 10)
- Comportamento específico do iOS (atualização controlada pelo sistema)

## Notas

- **Documentação em português**, passo-a-passo para quem não programa.
- **Sem código de produção**, só docs educacionais.
- **Token na URL**: Documentação menciona que é aceitável temporariamente, será revisado na Fase 10 (segurança).
- **Cada doc é independente**: Alex pode ler só o que interessa sem dependências.
- **Tabela comparativa em branco**: Alex preenche testando cada opção em real (iPhone) por ~2 dias.

## Próximos Passos

1. Alex testa as 5 opções documentadas (Scriptable já coberto em WIDGET_TELA_BLOQUEIO.md).
2. Preenche `widget-comparativo.md` com seus resultados.
3. Escolhe a melhor opção(ões) e descarta as outras.
4. Se encontrar problemas ou discrepâncias, abre issue com detalhes (app, comportamento esperado vs observado).

## Versão

Relacionado a Fase 7, bandas N3c e N3d (widget docs).
