# REGRAS DE OPERAÇÃO — painel-pessoal-tdah
## Economia, velocidade e precisão — valem para QUALQUER fase, sempre

Este arquivo é fixo. Toda fase (segurança, funcionalidade, visual, o que for) lê isto antes de começar, independente do que o briefing daquela fase pedir.

---

## 0.1 Por que existem (números medidos, não estimados, da Fase 7)

- Fase 7: ~1,16 bilhão de tokens, 98% releitura de contexto em cache. Saída foi só 1,94M.
- `/usage`: 86–90% do uso aconteceu com contexto **acima de 150k**, numa sessão de 8h+, 85% em subagentes genéricos.
- Subagentes pesados cruzaram 150k entre as chamadas 55 e 92 ao modelo e terminaram com 390k a 530k de contexto.
- **~60% do custo veio de chamadas com contexto acima de 200k.** Valores em preço equivalente de API; o dono usa o plano Max, então o que conta é o **limite**, não dólar.
- Sessão principal chegou a **783k de contexto** numa fase anterior.
- Todo subagente começa com **32k a 49k** de contexto (mediana 47k). O `AGENTS.md`/`CLAUDE.md` sozinho é ~13,5k disso.
- 112 dos 217 minutos de uma fase anterior foram a sessão principal esperando Bash ou subagente.

**Conclusão:** o custo é contexto grande relido. A regra-mãe é **nenhum agente passa de 150k de contexto, nunca**.

**Resultado na Fase 8 (com estas regras):** ~3,6M por subagente contra ~23M na Fase 7 (6× menos), maior contexto de subagente 116k, zero chamadas acima de 150k. O gargalo passou a ser a **sessão principal**: 45% do gasto da fase, relendo 450k–519k a cada mensagem porque vinha herdando as fases anteriores.

## 0.2 Modelo: decidido por medição, não por suposição

Pelos preços tabelados, Sonnet sai mais barato que Opus, mas a tela de uso já mostrou o contrário sem explicação clara. No plano Max o que importa é quanto do limite cada um consome. Então:

1. Quando a fase tiver dúvida sobre qual modelo usar no código: rode a menor faixa da fase duas vezes em paralelo, uma com Sonnet 5 médio e outra com Opus 5.5 médio, ambas limitadas a 150k. Anote o percentual da janela de 5h e do semanal antes e depois de cada versão. Descarte a pior, integre a melhor.
2. O vencedor vira o **modelo de código** de todas as faixas daquela fase. Grave a escolha e os números no `STATUS.md`.
3. Haiku 4.5 sempre para trabalho mecânico: mapa do código, `.gitignore`, CHANGELOG, listas, varredura com grep.
4. O modelo é passado **explicitamente** ao lançar cada subagente. Nunca herdado. Não troque o `/model` da sessão com subagentes rodando.
5. Esforço: médio para código, baixo para Haiku. Nunca alto.

## 0.3 Contexto: o subagente não explora, ele recebe o mapa

1. **Etapa 0 de cada fase gera/atualiza `MAPA.md` (Haiku):** para cada área que a fase vai tocar, lista arquivo → funções/rotas → linhas. Uma varredura só, com grep.
2. Cada ficha/faixa recebe **só o trecho do MAPA dela**. O subagente abre só isso. Se precisar de outro arquivo, 1 grep pontual; se precisar mexer nele, para e reporta.
3. Leitura por trecho (`sed -n 'A,Bp'` ou Read com offset/limit). Nunca arquivo inteiro acima de 300 linhas.
4. **Teto duro por subagente: 150k de contexto ou 40 chamadas de ferramenta**, o que vier primeiro. Ao chegar perto: commit do que está pronto, 3 linhas no `STATUS.md`, encerra. Um subagente novo continua.
5. Uma história por subagente. Juntar só tarefas pequenas que mexem no mesmo arquivo (na Fase 8, juntar D2+D4 e D3+D6 poupou 3 partidas de ~47k). Na Fase 8, quatro faixas passaram do teto (71, 63, 59, 54 chamadas): sinal de escopo grande demais por faixa.
6. **Tamanho mínimo:** como todo subagente já nasce com ~47k de contexto, não crie subagente para tarefa de menos de ~15 chamadas. Agrupe tarefas mecânicas pequenas num subagente Haiku só.
7. **Por que reiniciar compensa:** um subagente novo recomeça em ~47k, não carrega os 150k do anterior. O custo de partida é pequeno perto de continuar relendo 300k–500k a cada chamada.
8. Toda saída de Bash limitada: `| tail -30` ou `| head -60`. Testes: `pytest -q -x --tb=line <arquivos da faixa> 2>&1 | tail -15`. Nunca `git diff` inteiro, nunca `donos.json` inteiro, nunca log completo.
9. Agrupar comandos: um Bash que roda grep + teste + resumo vale mais que três chamadas.
10. `AGENTS.md`/`CLAUDE.md` enxugado (≤ 12 mil caracteres): só regras fixas; o resto em `docs/` lido sob demanda.

## 0.4 Sessão principal (coordenador)

0. **Uma sessão nova por fase. Obrigatório.** Antes de fechar uma fase, a sessão grava o estado no `STATUS.md`; a fase seguinte abre numa sessão nova que lê só o `STATUS.md`, este arquivo e o briefing. Começa em ~50k em vez de ~500k. É a maior economia que sobrou.

1. Só coordena: lança subagentes, lê relatórios de 10 linhas, integra, decide o que precisa decidir. Não escreve código (exceção: conflito de merge).
2. Opus 5.5 médio.
3. **Ao passar de 120k de contexto:** grava estado no `STATUS.md` e faz `/compact`. Se passar de 150k de novo, pede sessão nova.
4. Controle de trabalho só no `TODO.md`. Nunca na lista interna de tarefas.
5. Suíte e integração em segundo plano; consulta só quando termina. Sem conferir de poucos em poucos minutos.

## 0.5 Velocidade

1. **6 a 8 subagentes ao mesmo tempo**, desde que os donos não se sobreponham (`donos.json` + `checar_donos.py`).
2. Assim que um termina, o próximo da fila entra. Sem esperar lote.
3. Durante a faixa, só os testes da faixa. Suíte completa **uma vez**, no fim da fase.
4. Arquivos compartilhados têm dono único: `CHANGELOG.md`, `conftest.py`, CSS/tokens globais, cabeçalhos HTTP/CSP. Subagente pede a mudança no relatório, não edita.
5. Testes não vazam estado entre arquivos (`sys.modules`, globais): fixture que restaura.

## 0.6 Precisão

1. Cada história: critério DEVE e NÃO DEVE. Escreve o teste primeiro, vê falhar, corrige, vê passar.
2. Datas, valores e permissões calculados em código. Texto de IA nunca decide permissão.
3. Testes com banco temporário e porta local desligada. Nenhuma chamada real a Anthropic, OpenAI, Gemini, Telegram ou Pluggy em teste automatizado.
4. Nenhum achado é "corrigido" sem teste que prove.

## 0.7 Relatório padrão de cada faixa (máximo 10 linhas, sem log/diff completo)

```
FAIXA | feito | NÃO feito (por quê) | achados novos | testes X ok / Y falha | commit | chamadas usadas
```
