# Leva 08/11/2026 - o que a conversa inteira mostrou (leva 1: comportamento e dados)

Origem: 4 agentes leram a conversa inteira do chat (05/10 a 07/11) e cruzaram com o banco (só leitura).
Pedido do Alex: "faça a leva um, use agentes se precisar, corrija tudo" (sem chave da API nova; os testes
usam IA mockada). Nada de visual novo nesta leva; microfone fica para a leva 2 (precisa de iPhone).

Regras de sempre: dado inventado em teste; nada da conversa real em código, teste, doc ou commit; banco real
nunca é escrito; avisos NUNCA diminuem em quantidade (TDAH) - muda texto, hora e momento, não corta.

## Frente A - compromisso de sair (date, balada, buscar alguém) não é tarefa comum
Arquivos: `aviso_cara.py`, `notificacoes.py`, `onde_estou.py`, `onde_vou.py`, `vida_assistente.py`,
`conversa_proativa.py`, `avisos_texto.py`, `fechamento_dia.py`, `essencial*`.
1. Texto dos avisos de compromisso de sair: nunca "primeiro passo", "está na tua lista há N dias", "toca em
   Feito", "ainda dá tempo de resolver hoje". Depois da hora de sair: texto de saída ("Ainda em casa? Saindo
   agora chega HH:MM"). Mesma quantidade de avisos. (`aviso_cara.py:30` TIPOS_DE_TAREFA, caras 195-212;
   `notificacoes.py` ~151 e ~1093/1111.)
2. Cascata da manhã não empurra compromisso de sair: date/balada/`sai_na_hora`/com outra pessoa viram parede
   como voo e inegociável (`onde_estou.py` `_fixa` ~666).
3. Compromisso de sair que já passou e o GPS confirma que ele foi (visita perto da hora): não vira "prazo
   vencido"/essencial do dia seguinte nem "em aberto" no fechamento - fecha sozinho ou pergunta uma vez "rolou?".
4. Parada absurda: teto (~180 min) em `notificacoes.caminho_com_parada` (~282) e `vida_assistente.resolver_parada`
   (~173); acima disso usa os minutos que ele disse ou a folga. "casa d@ <nome>" sem apelido salvo não vai pro
   Google (virava uma cidade de mesmo nome, 2158 min).
5. Recado de atraso pronto só para compromisso com pessoa (date, balada, com_quem) - nunca banco/órgão
   (`onde_vou.py` ~620 e ~659).
6. Aviso "é agora" que sai atrasado mais de 60 min (servidor voltou de parada): uma mensagem só, dizendo o atraso
   real, sem "Passou um pouquinho" e sem disparar junto o "passou da hora" da mesma tarefa no mesmo tick.
7. Manhã: ele acorda ~9h40-11h; 70% dos avisos antes das 9h nunca são vistos. Remédio/aviso da manhã ainda
   pendente REPETE no primeiro sinal de acordado (abriu o app / saiu de casa pelo GPS / check-in). Check-in fixo
   das 07:00 (`conversa_proativa.py` ~699) passa a sair no primeiro sinal de acordado (com teto de horário).
8. Mensagens automáticas do chat não ocupam a janela de memória da conversa (histórico de 20 em `app.py` ~2779
   pega as proativas; tirar ou não contar).

## Frente B - jeito de falar e roteamento do chat
Arquivos: `ia/funcoes/chat.py` (prompt), `ia/roteador_chat.py`, `ia/revisor_chat.py`, `aprendizado.py`,
`ia/funcoes/fala.py`.
1. Sempre "tu", nunca "você/seu/sua" (regra no topo do JEITO DE FALAR).
2. Tirar do prompt os exemplos que semeiam "Anotei…" e "é só falar"; revisor corta abertura igual à da
   resposta anterior e pega "é só falar / me fala que eu ajusto" em qualquer ponto da última frase.
3. Revisor: falar do sistema ("o card mostra", "a ferramenta de rota", "o painel sugere/calcula") pede refazer.
4. "oq?", "o quê?", "não entendi", "repete": repetir o essencial em 1-2 frases, sem ferramenta, sem defensiva.
5. "Vale a pena / compensa": veredito na primeira frase; prós/contras só se ele pedir ou se não estiver com
   pressa (atrasado / na rua / voz). Resolver o conflito com "sem lista".
6. Reenvio da mesma mensagem: conferir; se já está feito diz "já tá: …"; nunca "antes não tinha feito".
   Ampliar `_RE_AFIRMOU` do revisor (Anotado, Ajustei, Passei, Deixei, Empurrei, tá riscado…).
7. Horário relativo solto ("daqui 10 min", "em meia hora", "depois da janta") vale como hora da última coisa dita.
8. "Marca o aviso de se arrumar": não responde "dispara sozinho"; diz os horários (se arrumar · sai · chega) e
   mostra o compromisso.
9. ATRASO DITO ("atrasou tudo", "vou atrasar 20 min"): refaz a conta com as durações que ele disse + tempo de se
   arrumar, chama `ajustar_tarefa` no próximo compromisso e diz a hora nova.
10. "Marca horário pra falar/ligar/cobrar alguém": cria a tarefa (dia + hora sugerida) e só depois pergunta.
11. Plano que ele anunciou ("vou terminar o café e vou lavar") não se muda sozinho: avisa o risco numa frase.
12. "Saí de X / já fiz X / depositei": conclui a tarefa correspondente. "Fui mas não deu": não conclui.
13. Roteador: `horarios?` (plural) e verbos de remontar (ajusta/justo/estima/muda/atualiza + horários; "atrasei")
    sobem pro degrau pensar.
14. Atalho local (`aprendizado._RE_SUGESTAO` ~627): perguntas de trajeto ("que horas vou chegar em casa?", "que
    horas vou sair?", "como vou pra casa de X?", "quando vou buscar X?") vão pra IA, não pro card de horário livre.
    Varrer com frases realistas por outros desvios da mesma família.
15. `fala.py`: exemplo "Justo/Juste os horários" = "Ajusta".

## Frente C - dados e lugares
Arquivos: `app.py` (executores do chat, vocabulário, MODO_VOZ_INSTRUCAO), `db.py`, `ia/core.py`,
`assistente/briefing.py`, `rotas/resumo.py`, geração do `chat_resumo_historico`, card da semana.
1. `completed_at` num fuso só (UTC, como `db.complete_task`); `exec_ajustar_tarefa` grava `datetime.now()` local
   (`app.py` ~3133). Conferir os leitores (`fechamento_dia.py:30` desconta 3 h; `briefing.py:289`,
   `rotas/resumo.py:49`, `notificacoes.py:956` não).
2. `exec_ajustar_tarefa` registra adiamento (`dia_ruim.registrar_adiamento`) quando a data nova é maior.
3. Tarefa repetida que volta "é hoje" grava o dia (tarefa com hora sem dia nunca avisa).
4. Endereço que ele dá para um lugar de tarefa vira apelido salvo no código (não depende do modelo); lugar sem
   endereço não é salvo (pergunta). Vocabulário da transcrição inclui `tasks.local` e títulos dos últimos 30 dias.
5. Resumo do histórico (`chat_resumo_historico`) não guarda pendências velhas (as vivas vêm do banco) ou confere
   com tarefas/esperas antes de gravar.
6. Card da semana não sugere voo/treino quando o último foi há mais de ~60 dias.
7. Chave da API recusada (401): não tenta 3x; um aviso único por dia "IA fora: chave recusada" e o chat responde
   uma mensagem clara em vez de erro genérico.
8. `MODO_VOZ_INSTRUCAO` (`app.py` ~2665): tirar "números do jeito que se fala" (conflita com o prompt; o app
   converte na fala premium).

## Fora desta leva
Microfone surdo (leva 2), tempo de permanência aprendido por tipo de lugar, busca na internet para "o que levar",
memórias velhas no banco (o Alex corrige pelo chat), dados antigos em fuso errado.
