# STATUS - Fase 8 (atualizado pelo integrador a cada rodada)

Atualizado: 2026-09-25 (fechamento)

## Estado
**Fase 8 concluída, faixas D1-D6 e F1-F3 na `main`.**
- D1 tema escuro neutro (tokens em `static/css/ui/tokens.css`), D2 humor/LED sóbrios, D3
  hiperfoco no topo, D4 checkbox `--cor-sucesso`, D5 visão do dia recolhida por padrão,
  D6 clima (já existia antes da fase, sem mudança).
- F1 sincronização Nubank via Pluggy (`rotas/f8_banco.py`) + gastos unificados manual/banco.
- F2 bloco de próximas cobranças na aba Gastos com aviso de duplicidade.
- F3 interruptor "avisar antes de cobrar" por assinatura + gatilho de aviso 3/2/1 dias.
- Fechamento (`fase8/fechamento`): dedup da lista antiga de "próximas cobranças" dentro
  da seção Assinaturas (mantido só o bloco novo da F2).

## Pendências
- Item Pluggy `ce7aa441` devolve `404 ITEM_NOT_FOUND` com as credenciais atuais -
  conexão parece ter sido feita em outra aplicação Pluggy; reconectar pelo "Conectar
  banco" do painel.
- Compra parcelada ainda sem interruptor de aviso (só assinatura tem).
- Aba Tarefas só lista pendentes.

## Chamadas por faixa (lição pra próxima fase)
- F1: 63 chamadas (teto era 50) - estourou.
- D2+D4: 62 chamadas (teto combinado) - estourou.
- F2: 53 chamadas - estourou.
- F3: 78 chamadas - estourou bem além do teto.
- **Lição:** os prompts de cada faixa precisam de um teto menor e escopo menor por
  rodada (dividir faixas grandes tipo F3 em sub-passos), em vez de um teto único de 50
  pra faixas com escopo desigual.

## Testes
`test_fase8_*.py` e correlatos: verde (só a falha pré-existente e conhecida em
`test_fase7_n1_rotas.py::test_formato_da_resposta`, dependente de data, não relacionada
à Fase 8).
