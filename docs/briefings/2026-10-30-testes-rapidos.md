# Testes mais rápidos (2026-10-30)

Pedido do Alex: deixar a suíte bem mais rápida, sem mudar o que ela confere.

## Medições de partida
- Suíte inteira: 11 min com o painel ligado (filas: rápida 9 min, grandes 5 min 48 s, navegador 11 min).
- `db.init_db()` num banco vazio: 330 ms. Copiar um banco pronto: 0,4 ms.
- Teste trivial do `test_app.py`: 0,35 s, quase tudo `init_db`.
- PC: 20 núcleos, 15,7 GB de RAM, cerca de 2 GB livres com o painel ligado.

## O que entra
1. **Banco modelo**: `tests/banco_modelo.py` troca `db.init_db` só nos testes. Banco vazio vira cópia de um modelo feito
   pelo `init_db` de verdade. Banco que já existe, pasta de migrações trocada e o banco real seguem pelo `init_db` normal.
2. **Só o afetado**: `scripts/testes_afetados.py` escolhe os testes pela mudança em relação ao último commit.
3. **Cópia separada**: a suíte roda numa cópia temporária do código, pra dar pra seguir mexendo enquanto ela anda.
4. **Fila do navegador**: atacar o que as medições mostrarem.

## Decisões
- Nenhuma dependência nova.
- A suíte inteira continua sendo a régua antes de commit: o "só o afetado" é pra agilizar, não substitui.
- As falhas depois das 21h (data UTC x Brasília) são outro assunto: ficam na tarefa própria.

## Segunda rodada (2026-10-31): "tenta achar uma forma de ser mais rápido e faça"
Medição com o PC livre: 4 min 25 s, 4.717 aprovados, nenhuma falha. O que segurava:
- **Fila do navegador (4 min 22 s):** um processo só. Três processos `xdist` davam falha em massa porque cada um importa
  todos os arquivos e sobe todos os servidores nas mesmas portas: o teste falava com o servidor de outro processo.
- **Fila rápida (2 min):** presa em 1 arquivo: `test_fase7_n2_telegram_rota` ia pra internet de verdade (15 s por resposta).
- **Um teste de 30 s:** arquivo temporário aberto, e o `os.unlink` do `conftest.py` tentando apagar por 30 s no Windows.

O que entra:
1. **Rede fechada nos testes:** conexão pra fora falha na hora, localhost segue livre.
2. **Navegador em paralelo:** um `pytest` por arquivo, o mais demorado primeiro, tempos guardados em `data/testes/`.
3. **Refazer sozinho:** teste do navegador que falhou roda de novo no fim, com o PC livre. Se passar, a suíte aceita, mas
   o relatório mostra quais foram: teste de tempo não vira falha falsa, nem some em silêncio.
4. **JS na suíte:** `node --test tests/js` vira a quarta fila (490 testes, 1,7 s). Antes a suíte inteira não rodava JS.
5. **Esperas fixas viram condição real:** `wait_for_timeout` soma 77 s na fila e é o que quebra com o PC cheio. Espera que
   existe pra provar que algo NÃO acontece, ou que mede o próprio tempo, fica. Nenhum `assert` sai ou afrouxa.

## Revisão adversarial (2026-10-31)
3 revisores quebraram o app de propósito numa cópia. Todo `assert` estava igual e mesmo assim:
- **Teste que passou a passar à toa:** contar a lista logo depois do erro passava com o rollback quebrado. Voltou a espera
  do prazo (500 ms) e entrou a checagem de `li.saindo`. `test_cada_linha` ganhou espião da rolagem imediata; as telas do R2
  voltaram a esperar a carga antes de conferir `pageerror`.
- **Suíte verde com falha real:** `cod_nav = cod_refeito` escondia arquivo que morreu e `SUBFAILED`. Agora o refazer só
  perdoa o que ele refez de fato.
- **Teste que escondia bug do app:** a espera nova tirava os testes do Tomei da corrida de `medicamentos.js`. Ficou um teste
  próprio com `expectedFailure`, que vira falha quando o app for corrigido.

Decisões:
- 8 testes de navegador do R4 nunca rodavam no Windows (só procuravam Chromium em caminho do Linux). Ligados: 14 s no
  arquivo, sem mudar o tempo total, e foram eles que acharam o bug do Tomei.
- Chromium fechado pra fora num ponto só. Os `ctx.route("**/*")` manuais saíram: sobravam, passavam todo pedido pelo Python
  e quebravam com pedido em voo no fechamento.
- `test_app_aberto...` não provava a pausa de 20 s nem o bloqueio de escondido. Agora prova os dois.
- Limites implícitos que ficaram mais largos e continuam assim, porque o teste não confere tempo: `test_limpa_a` 600 ms ->
  30 s, `test_anim2` 900 ms -> 30 s, microfone 5,6 s -> 10 s. O que importa nesses testes é sair, não o prazo exato.
- Fica pra depois (fora de "deixar rápido"): corrigir o Tomei, a folha de captura que não desliza, a rolagem do Mais em rede
  lenta. Os 6 testes pulados que sobraram (`test_vel4_abas`) precisam de gunicorn, só Linux.

## Portas esgotadas (2026-10-31)
3 rodadas verdes, mas com 3 a 5 testes passando só no refazer. A primeira explicação (porta de teste na faixa dinâmica do
Windows) estava errada: a falha voltou em porta 23577. A medição das conexões mostrou a causa: 17.436 em TIME_WAIT, acima
das 16.384 portas de saída, cada uma presa 30 s (`TcpTimedWaitDelay` deste PC; os "2 minutos" que escrevi antes eram o
padrão do Windows, sem conferir).
- **Duas fontes, as duas precisam sair:** o servidor do Flask fecha a conexão a cada pedido (~250 por página) e o
  service worker abre uma por arquivo no `cache.addAll` (222, mesmo com waitress; o porquê de ele não reaproveitar não foi
  investigado).
- **Waitress nos testes:** o mesmo servidor do painel, `threads=16`. Estava instalado e fora do `requirements.txt`.
- **Service worker desligado por padrão nos testes:** ele só mexe em `/static/` e nenhum teste de navegador o conferia.
  `test_service_worker_real.py` passa a conferir de verdade: instala, assume a página e guarda todo `ASSETS`.
- **Portas abaixo de 49152:** ficam, por outro motivo: a porta sai de um `bind(0)` solto e uma conexão de saída podia pegar
  o número antes de o servidor subir.
- **Cronômetro dentro da página:** `test_vel_a2b` media com o relógio do Python. O limite de 150 ms não mudou. A medida vai do
  `pointerdown` até o quadro que mostra a mudança: a primeira versão (clique até a mudança no DOM) não via trava de 1 s no toque
  nem no quadro. Com o PC livre o caminho leva 17 a 30 ms; sob carga pesada passou uma vez (328 ms) e aparece em
  `so passou sozinho`: é um teste de tempo de verdade, e pra isso existe o refazer.
- **Esperas de 5 s desta leva viraram o padrão de 30 s:** 3 estouros em testes diferentes (`_esperar_aba`, `test_limpa_d`),
  sempre com outro programa apertando o PC, e nenhuma mede tempo: limite curto só adiantava a falha. Causa não provada; uma
  corrida do app daria o mesmo sintoma, e aí a falha segue aparecendo em `so passou sozinho`. As 4 de 5 s que já existiam
  antes (`test_r2`, `test_r3`) ficaram como estavam.
- Resultado: pico de ~700 conexões e fila do navegador em 63 a 92 s, antes de 75 a 93 s com falhas no meio.

## Revisão final (2026-10-31)
Revisão adversária do que esta leva mudou. O que entrou:
- **Limite de 600 s nas filas rápida, grandes e JS:** só o navegador tinha limite; teste preso travava a suíte sem aviso.
- **`testes_afetados`:** dava 0 testes em 8 rotas e 37 arquivos citados com a pasta. Agora pega URL da rota e nome com pasta.
  "Nada ligado" avisa que isso não prova nada. Não virou suíte inteira porque arquivos soltos fora do git (`scripts/lacre_joao.py`,
  `amostras_voz/`) estão sempre na lista e a ferramenta deixaria de servir.
- **Concluir tarefa:** o desfazer só era testado com erro instantâneo. Agora tem erro que chega com a linha já fora do DOM, e confere
  que ela volta sem risco e tocável.
- **Service worker:** o teste recarrega com ele no comando. Sem isso, um `fetch` quebrado matava o app e o teste passava.
- **Duas suítes juntas:** retirado. Os relatórios de `data/testes/` têm nome fixo, e o `SO_REUSEADDR` deixa dois servidores na mesma
  porta sem erro (chance ~0,1% por par de suítes, igual a antes). Não troquei por `SO_EXCLUSIVEADDRUSE` no servidor: atrapalha
  re-rodar na mesma porta e o ganho é pra um uso que não existe.
- **`CLAUDE.md` e `README.md`:** mandavam `unittest discover`, que agora dá erro e roda sem a rede fechada.

Resultado final (3 rodadas com tudo pronto): 73, 68 e 73 s, código 0, nenhum teste refeito, pico de 934 conexões em TIME_WAIT.
Rápida 4.059 + 1.311 subtestes, grandes 536 + 126 subtestes (1 pulado), JS 490, navegador 175 (6 pulados, só Linux). 19 de 19
quebras de propósito pegas. As rodadas foram na janela em que o render do Blender montava a cena; com ele renderizando, a
reserva do sistema oscila até 2,4 GB e a suíte em paralelo não cabe com segurança (ver `docs/testes.md`).
