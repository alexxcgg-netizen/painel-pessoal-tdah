# changelog.d - entradas de changelog por faixa

Mecanismo criado na Fase 7 para dezenas de faixas paralelas não editarem o mesmo
`CHANGELOG.md` (conflito de merge garantido no topo do arquivo).

## Como funciona
1. Cada faixa escreve **só** a própria entrada em `changelog.d/<faixa>.md` (ex.:
   `changelog.d/a6-chat.md`). O nome é o mesmo da branch `fase<N>/<faixa>` e da pasta
   `scripts/ralph-<faixa>/`. `scripts/checar_donos.py` e `scripts/integrar.sh` já liberam esse
   arquivo para a faixa dona, sem precisar listar no `donos.json`.
2. Conteúdo: título `### Fase N - faixa X (assunto)` e bullets curtos com o que muda para o
   Alex e o que uma próxima sessão de IA precisa saber: arquivos novos, flags, variáveis de
   ambiente, decisões e pendências. Nada de segredo, nem dado real.
3. A faixa **não** edita `CHANGELOG.md`, `AGENTS.md`, `TODO.md`, `STATUS.md`, `README.md`,
   `.env.example`, `requirements.txt` nem `static/service-worker.js`. Aprendizados vão em
   `scripts/ralph-<faixa>/APRENDIZADOS.md`, e dependência ou variável nova vai no
   `scripts/ralph-<faixa>/progress.txt`.
4. No fim da fase, a faixa de consolidação (M1) junta todos os fragmentos numa entrada única
   no topo do `CHANGELOG.md` (resumo para o Alex + subseções por grupo), apaga os
   `changelog.d/*.md` e deixa só este README.

## Histórico
- Fase 7: 40 fragmentos consolidados em "2026-09-24 - Fase 7 (v12)" no `CHANGELOG.md`.
  Referências antigas a `changelog.d/<faixa>.md` (ex.: docstrings de `tests/test_app.py` e
  `tests/test_vida_fase3.py` citando `a12-testes.md`) apontam agora para essa entrada.
