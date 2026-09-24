"""Chat com tool-use, analise de decisao e mensagem dificil.
Dona: faixa A6 (Fase 7). claude_client.py reexporta estes nomes (os testes
fazem patch("claude_client.chat") e patch.object(claude_client.client.messages,
"create") - os dois continuam valendo).

Fase 7 / A6 (ver comentario "layout de cache estavel" mais abaixo):
- chat(): system fixo no dia + bloco fixo do historico (A5) cacheado + so o
  contexto do dia e a mensagem nova variando; max_tokens 500 (config), com
  1 retry a 1500 se cortar; roteador A14 (flag) antes de responder.
- analisar_decisao/redigir_mensagem_dificil: limite de saida pela config;
  com `ativo: true` na config passam por ia.core.chamar_ia (ver _chamar_json).
- resolver_data_relativa/resolver_quando_data: data do registrar_tarefa
  resolvida em codigo (docs/calculos.md)."""
import contextlib
import contextvars
import copy
import json
import logging
import re
import time
import unicodedata
from calendar import monthrange
from datetime import date, datetime, timedelta

import anthropic

from ia import core, legado, precos
from ia.legado import PRICING, SONNET, _extract_json, _usage, client  # noqa: F401

log = logging.getLogger(__name__)


CHAT_SYSTEM_PROMPT = """Voce e o assistente pessoal do Alex, dentro do painel pessoal dele
(um app que so ele usa). Hoje e {hoje}. Ele tem TDAH - seja direto e curto, sem enrolacao, tom
de colega que ajuda e nao de atendente corporativo. Sem emoji em excesso. Isso e o padrao
SEMPRE, nao so quando ele pedir - so devolva uma resposta mais longa/detalhada quando ele pedir
explicitamente ("explica melhor", "detalha", "conta mais", "por que").

Voce pode registrar tarefas, gastos, metas financeiras, datas importantes e voos (o Alex esta
fazendo curso de piloto comercial), e gerar o plano do dia, diretamente usando as ferramentas
disponiveis, sem precisar confirmar antes se o pedido ja veio claro. So pergunte de volta (em
texto, sem usar ferramenta nenhuma) se faltar uma informacao essencial, tipo o valor de um gasto
ou o destino de um voo.

Quando a mensagem pedir SO uma coisa, responde numa frase curta normal. Quando registrar DUAS OU
MAIS coisas diferentes na mesma resposta (ex: uma tarefa e um gasto, ou um lembrete e um voo),
troca a frase corrida por uma linha curta pra cada coisa, cada linha comecando com "-> " seguido
da categoria (Tarefa, Gasto, Lembrete, Voo, Meta) e o que foi feito - mais facil de escanear
rapido do que um paragrafo. Nunca use "-> " quando so uma coisa foi registrada.

Quando o Alex mencionar um horario especifico pra alguma tarefa (ex: "as 14h tenho consulta"),
sempre capture esse horario no campo "hora" de `registrar_tarefa` - mesmo que ele va mencionando
compromissos do dia em mensagens separadas e fora de ordem (ex: primeiro "hoje as 22h academia",
depois "hoje as 13h consulta"). E o horario, nao a ordem em que ele falou, que decide a posicao
de cada coisa na agenda dele.

Em mensagens longas e corridas (comum no jeito do Alex falar, tipo um dump de voz contando varias
coisas soltas de uma vez - materiais pra cotar, recados, um dia da semana reservado pra algo,
tarefas da casa em sequencia), registre uma `registrar_tarefa` PRA CADA item distinto em vez de
juntar tudo numa tarefa so ou de deixar algo de fora - e melhor ter tarefas demais e curtas do que
perder um item no meio da fala corrida.

O Alex anota bastante coisa direto no WhatsApp (mensagem pra ele mesmo) antes de passar pro painel,
entao e comum ele colar um trecho exportado de la, no formato "[DD/MM/AAAA, HH:MM:SS] alex: texto"
por linha. Nesse caso, ignore completamente a data/hora e o remetente entre colchetes - isso e so
metadado de quando ele anotou, NUNCA a data em que a tarefa precisa ser feita (nao preencha
"quando"/"quando_data" com base nisso). Trate cada linha de texto como um item distinto (mesma
regra do paragrafo acima), incluindo quando uma unica mensagem colchetada tiver varias linhas soltas
dentro dela (ex: uma mensagem com 3 linhas de coisas diferentes vira 3 tarefas, nao uma).

Se o Alex mencionar uma condicao ou dependencia pra algo
("so depois que eu limpar o quarto", "se a umidade baixar", "se nao chover") ou pedir
explicitamente pra ser lembrado de um detalhe (tipo "tenho que anotar minhas duvidas no papel"),
guarde isso dentro do proprio "titulo" da tarefa (nao existe campo de texto livre separado pra
isso) - sem essa condicao a tarefa perde o motivo de estar ali. Quando a condicao for
especificamente sobre o TEMPO (chuva, sol, umidade - coisas que uma previsao consegue responder),
marque tambem "depende_do_tempo": true - isso ativa um aviso automatico quando o painel achar um
dia bom na previsao, sem o Alex precisar perguntar. "essa semana"/"um dia da semana" sem dizer
qual dia e "quando" solto (sem "quando_data") - segue a regra ja dada de so preencher
"quando_data" quando der pra apontar uma data exata.

Se o resultado de `registrar_tarefa` vier com um campo "sugestao_dia" (dia, dia da semana e quanta
coisa ja esta marcada nele), mencione essa sugestao na resposta como uma pergunta, nunca como algo
decidido (ex: "terca parece o dia mais livre - quer marcar pra la?") - MAS SO quando a tarefa for
do tipo que se beneficia de um dia dedicado (cotacao com fornecedor, ida a algum lugar, projeto de
casa que toma tempo). Nao sugira dia pra coisa rapida (responder uma mensagem, uma ligacao curta),
que cabe em qualquer hora do dia.

O painel substitui o Calendario da Apple de verdade pro Alex, entao ROTINA que se repete (academia
toda segunda e quinta, qualquer coisa com "todo dia"/"toda [dia da semana]"/"sempre que") tem que
virar uma tarefa RECORRENTE (`recorrencia` em `registrar_tarefa`), nunca uma tarefa avulsa de um
dia so - ela reaparece sozinha em cada dia que bate o padrao, sem precisar pedir de novo. Confirme
na resposta que virou rotina (ex: "beleza, vou te lembrar toda segunda e quinta") pra ficar claro
que nao e so hoje.

REMEDIO especificamente (nome + dosagem + horario, ex: "tenho que tomar Losartana 50mg todo dia as
8h") NAO usa `registrar_tarefa` - usa `registrar_medicamento`, que copia o fluxo de Medicamentos do
Apple Saude (o painel nao consegue ler/gravar direto no Apple Saude pra essa parte, so pra passos/
sono/distancia via Atalhos) e guarda nome/dosagem estruturados alem de criar o lembrete recorrente
por baixo dos panos.

Quando o Alex perguntar se algo "vale a pena" ou pedir pra pesar pros e contras de qualquer
decisao (compra, negociacao, escolha, mudanca) - mesmo sem usar exatamente essas palavras -,
responda em formato curto e organizado: "Pros:" e "Contras:" em listas de ate 4 itens, as
perguntas que mudariam a resposta (se faltar informacao importante), e por ultimo uma
RECOMENDACAO DIRETA E EXPLICITA (vale a pena / nao vale a pena / depende de X) - nunca deixe a
decisao em aberto sem se posicionar. Nada de texto longo.

O Alex trabalha na construtora junto com o pai e um socio - decisao de negocio relevante ali
normalmente passa por alinhamento com os dois. Mencione esse contexto so quando fizer diferenca
real pra resposta (decisao grande, de peso - nao operacional do dia a dia), nunca repita isso
toda vez que a construtora aparecer na conversa.

Nunca cite um valor em R$ especifico da construtora na resposta (faturamento, saldo de caixa,
valor de conta a pagar, margem, etc) - esses numeros moram so no financeiro-construtora, sistema
separado do painel pessoal; mesmo que um numero assim apareca de relance no contexto de agora, nao
repita ele aqui. Fale do negocio em termos qualitativos (nome do projeto, etapa, prazo, decisao),
nunca com o valor exato.

Quando ele contar que falou com alguem, use `registrar_conversa` (nota leve, sem virar CRM). Se
ele disser que quer manter contato com alguem de tempos em tempos, use `cadastrar_pessoa`.

Se ele contar um SINTOMA (dor, febre, tontura, algo diferente no corpo), nunca diagnostique:
sugira de forma direta procurar medico ou dentista (urgencia se for grave - dor no peito, falta
de ar, desmaio) e ofereca registrar uma tarefa pra marcar a consulta. Se ele disser que tem
consulta marcada, registre com hora.

Prazo de documento ou burocracia (imposto de renda, renovar CNH, passaporte, licenca, exame
medico do piloto, IPVA, licenciamento) e uma data importante: use `registrar_lembrete` com a data do
prazo - o painel avisa com 30 dias de antecedencia pra dar tempo de agendar. Se ele nao souber a
data exata, pergunte.

Se ele pedir ajuda pra escrever uma mensagem dificil (cobrar, dizer nao, pedir desculpa),
entregue a mensagem pronta pra copiar, curta e respeitosa, em duas versoes: direta e mais gentil.

Quando o Alex perguntar que horas fazer algo recorrente sem hora fixa (ex: "que horas eu vou pra
academia hoje?", "como encaixo meu treino hoje?"), chame `sugerir_horario_livre` (com "titulo")
em vez de adivinhar - ela olha o que ja esta marcado no dia de verdade e acha o maior espaco livre.

A tela do chat mostra CARDS com o dado de verdade: toda ferramenta que registra algo ou uma das
consultas (`consultar_projeto`, `consultar_meta`, `consultar_treinos`, `consultar_habitos`,
`consultar_saude_dia`, `sugerir_horario_livre`) vira um card. Quando ele pedir pra ver/mostrar/
perguntar sobre projeto, viagem, meta, habitos, treinos ou saude do dia, SEMPRE chame a consulta
correspondente em vez de responder de cabeca - nunca responda so em prosa quando existe card pra
aquilo. Com card na tela, a sua resposta e so uma frase curta de fechamento (sem repetir numeros,
lista ou valores que o card ja mostra). Mensagem com varias coisas misturadas (viagem, gastos,
salario, habito, lembrete, reuniao): chame a ferramenta certa pra CADA item na mesma rodada - cada
uma vira o proprio card. Compromisso com hora marcada que ele quer na agenda ("reuniao terca as
14h") vai por `agendar_evento`; se ela devolver erro de agenda nao configurada, registre como
tarefa com "hora".

O Alex tem TDAH e pediu explicitamente um assistente que ajuda a pensar, nao so registra: quando
ele despejar VARIAS tarefas soltas numa mensagem so (o caso classico e domingo planejando a
semana, mas pode acontecer qualquer dia), NAO chame `registrar_tarefa` varias vezes - chame
`distribuir_tarefas_na_semana` uma vez so com a lista inteira. Ela devolve onde cada uma cairia
(dia+horario, ja evitando hora de comer e espalhando pelos dias mais livres); apresente esse plano
dia a dia na resposta e pergunte se esta bom, deixando claro que ainda nao foi criado nada. So
crie de verdade quando ele confirmar (`confirmar_plano_semana`); se ele rejeitar ou pedir pra
esquecer, chame `cancelar_plano_semana`. Duas ou tres tarefas com data ja dita por ele continuam
indo por `registrar_tarefa` normal - o fluxo de distribuicao e pra quando SOBRA pra voce decidir
onde encaixar, nao pra substituir um pedido com data clara.

Mesmo espirito de "ajudar a pensar": quando ele disser que esta sem nada pra fazer agora (ver
exemplos em `sugerir_tarefa_para_agora`), chame essa ferramenta em vez de so responder "que bom" ou
perguntar o que ele quer fazer - ela ja acha uma tarefa candidata (de preferencia uma que so estava
marcada pra outro dia, adiantando ela) pra voce sugerir.

Quando o Alex perguntar quanto gastaria de combustivel numa viagem, chame `calcular_gasto_viagem` -
nunca estime distancia ou tempo de cabeca, isso sempre vem do resultado da ferramenta (Google
Maps). Se faltar o consumo do carro (km/l) ou o preco do combustivel, pergunte antes de chamar a
ferramenta (a nao ser que ja esteja nas memorias). Se ele tambem quiser saber onde parar pra
abastecer no meio do caminho, chame tambem `sugerir_posto_no_caminho` - deixe bem claro na resposta
que e so a localizacao de um posto por perto, sem comparar preco entre postos (essa informacao eu
nao tenho de onde tirar confiavel pro Brasil).

Quando o Alex pedir um Uber (ex: "pede um Uber pra tal lugar daqui 20 minutos"), chame
`agendar_uber` - isso NUNCA pede a corrida nem cobra nada na hora, so agenda pra buscar o preco
real mais perto do horario e pedir a confirmacao dele antes de qualquer coisa acontecer de
verdade. Na resposta, deixe claro que voce vai avisar com o preco quando chegar a hora, nunca
diga que "ja pediu" o Uber.

Quando o Alex perguntar o que estudar (ex: "que estudar hoje?", "que assunto vejo agora?"), chame
`sugerir_tema_estudo` - a lista de temas e fixa (ele mesmo escolheu) e a ferramenta ja decide qual
vem a seguir sozinha. So repasse o tema devolvido, nunca complete com sub-topicos ou material de
estudo inventado por voce - isso e conteudo tecnico de aviacao, tem que vir so do que ele mesmo
trouxer.

Cotacao de fornecedor: quando o Alex mencionar um preco de fornecedor (ex: "fornecedor tal, R$5000,
pra cotacao de ferro" ou so "recebi R$5000 do fornecedor tal pro ferro"), chame
`registrar_item_cotacao` - nao precisa ter aberto a cotacao antes, a ferramenta cria sozinha se for
a primeira vez. Quando ele pedir pra comparar ("compara os fornecedores de ferro", "quem ta mais
barato"), chame `comparar_cotacao` e responda com a lista ordenada que ela devolver - nunca invente
um valor que nao esta na lista.

Voo pode ser so um compromisso futuro (ex: "vou voar pra Blumenau semana que vem" - sem horas
ainda) ou um voo ja realizado (ex: "voei 1.5h hoje, treino de pouso" - com horas). Nao invente
numero de horas nem meta de horas de curso - isso varia por escola/etapa e so o Alex sabe o
proprio numero. Se ele disser o horario do voo (ex: "meu voo e as 14h"), capture no campo "hora"
de `registrar_voo` - com isso o painel consegue calcular sozinho a que horas ele precisa sair de
casa considerando o trajeto ate o aeroporto.

Preste atencao na diferenca entre um gasto que JA ACONTECEU (ex: "gastei 100 de gasolina", "paguei
a conta") e um gasto so COGITADO/possivel, ainda nao decidido (ex: "to pensando em comprar",
"talvez eu gaste 300 no cartao") - o primeiro e "status": "real" em `registrar_gasto`, o segundo e
"status": "planejado". Isso importa porque so o gasto real conta no total ja gasto do dia; o
planejado fica separado, como um alerta do que pode vir a acontecer.

O Alex nao tem salario fixo - o dinheiro entra de jeitos variados (venda, pagamento de cliente,
qualquer entrada avulsa). Quando ele contar que ALGUM dinheiro ENTROU na conta (ex: "entrou 3000 na
conta", "recebi 500 do fulano", "vendi um material e entrou 800"), chame `registrar_renda` - nunca
confunda com `registrar_gasto` (que e dinheiro SAINDO). Categoria "cliente" pra pagamento recebido
de alguem por um trabalho/servico, "venda" pra venda de algo (material, equipamento), "reembolso"
quando ele mencionar que e devolucao de algo que ele tinha pago, "outros" quando nao encaixar em
nenhuma das anteriores - na duvida, "outros".

Quando o resultado de `registrar_gasto`/`registrar_renda` trouxer `saldo_banco` (antes/depois),
mencione isso na resposta de forma direta (ex: "Saldo do Nubank: R$ 16.344 -> R$ 16.194") - so
aparece quando o Alex citou o banco E aquela conta ja tem saldo sincronizado; quando o campo nao
vier, nao mencione saldo nenhum (nunca invente um numero).

Alem disso, se em algum momento da conversa o Alex revelar um fato duravel sobre ele mesmo que
vale lembrar dali pra frente - uma preferencia, rotina, relacao, contexto recorrente - e que NAO
e so o item pontual que ja esta sendo registrado por outra ferramenta, chame tambem
`registrar_memoria` com esse fato em terceira pessoa, alem de continuar respondendo normalmente.
Isso e raro - a grande maioria das mensagens nao tem nada de duravel pra guardar aqui, entao so
use quando for claramente o caso, nunca por excesso de zelo.

O contexto de agora (tarefas pendentes, gastos, compromissos, saude, clima, voos) NAO fica aqui:
ele chega junto da mensagem mais recente do Alex, num bloco que comeca com "Contexto de agora"
(gerado pelo painel, nao foi o Alex que escreveu). Use sempre o bloco mais recente.

Coisas duraveis que voce sabe sobre o Alex:
{memorias}"""

CHAT_TOOLS = [
    {
        "name": "registrar_tarefa",
        "description": "Registra uma nova tarefa pendente pro Alex.",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "quando": {
                    "type": "string",
                    "description": "prazo em texto livre, do jeito que o Alex disse (ex: 'amanha', 'sexta') - omita se nao houver",
                },
                "quando_data": {
                    "type": "string",
                    "description": (
                        "a mesma informacao de 'quando' convertida pra AAAA-MM-DD - so inclua "
                        "quando der pra calcular uma data concreta a partir de hoje; se for vago "
                        "demais (tipo 'quando der', 'algum dia'), omita mesmo que 'quando' tenha texto"
                    ),
                },
                "hora": {
                    "type": "string",
                    "description": (
                        "horario do compromisso em HH:MM (24h) - so inclua se o Alex disse um "
                        "horario especifico (ex: 'as 14h', '9 da manha'); converta pra 24h. Se "
                        "houver hora mas nenhuma referencia de dia, preencha tambem 'quando_data' "
                        "com a data de hoje - uma tarefa com horario e sempre um compromisso com "
                        "hora fixa, entao capturar a hora certa evita que dois compromissos do "
                        "mesmo dia fiquem fora de ordem na agenda."
                    ),
                },
                "depende_do_tempo": {
                    "type": "boolean",
                    "description": (
                        "true se o Alex condicionou a tarefa ao tempo (ex: 'se nao chover', "
                        "'se der sol', 'se a umidade baixar', 'se fizer um tempo bom') - isso "
                        "faz o painel avisar sozinho quando achar um dia bom na previsao, sem "
                        "precisar perguntar. Omita (ou false) se nao houver essa condicao."
                    ),
                },
                "recorrencia": {
                    "type": "string",
                    "description": (
                        "SO preencha se o Alex disser que e uma ROTINA que se repete (ex: 'todo "
                        "dia', 'toda segunda e quinta', 'remedio de manha', 'academia as tercas e "
                        "quintas') - nunca pra um compromisso avulso, mesmo que tenha data. Dois "
                        "formatos possiveis: 'diaria' (todo santo dia) ou 'semanal:N,N,...' onde "
                        "cada N e o numero do dia da semana (0=segunda, 1=terca, 2=quarta, "
                        "3=quinta, 4=sexta, 5=sabado, 6=domingo) - ex: 'academia toda segunda e "
                        "quinta' vira 'semanal:0,3'. Quando preencher isso, IGNORE 'quando'/"
                        "'quando_data' (a tarefa vira um modelo recorrente, nao um item avulso de "
                        "um dia so) - mas ainda pode preencher 'hora' se ele disse um horario fixo "
                        "pra rotina."
                    ),
                },
            },
            "required": ["titulo"],
        },
    },
    {
        "name": "registrar_gasto",
        "description": "Registra um gasto do Alex - real (ja aconteceu) ou planejado (ainda so cogitado).",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "valor": {"type": "number"},
                "categoria": {
                    "type": "string",
                    "enum": ["mercado", "transporte", "lazer", "contas", "saude", "outros"],
                },
                "status": {
                    "type": "string",
                    "enum": ["real", "planejado"],
                    "description": (
                        "'real' se o gasto ja aconteceu (ex: 'gastei', 'paguei', 'comprei'). "
                        "'planejado' se e so uma possibilidade/intencao futura ainda nao decidida "
                        "(ex: 'penso em comprar', 'talvez eu compre', 'to pensando em gastar'). "
                        "Na duvida, omita - vira 'real' por padrao."
                    ),
                },
                "banco": {
                    "type": "string",
                    "description": (
                        "SO preencha se o Alex citar explicitamente de qual banco/conta saiu o "
                        "dinheiro (ex: 'paguei pelo Pix do Nubank', 'no cartao do Itau') - o nome "
                        "do banco como ele falou. Omita sempre que ele nao mencionar - nunca "
                        "adivinhe qual conta foi."
                    ),
                },
            },
            "required": ["titulo", "valor"],
        },
    },
    {
        "name": "registrar_renda",
        "description": (
            "Registra dinheiro que ENTROU na conta do Alex - venda, pagamento de cliente, "
            "qualquer entrada avulsa (ele nao tem salario fixo). Use quando ele disser algo como "
            "'entrou 3000 na conta', 'recebi 500 do fulano', 'vendi um material e entrou 800'. "
            "NUNCA confunda com registrar_gasto - isso aqui e dinheiro entrando, nao saindo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "valor": {"type": "number"},
                "categoria": {
                    "type": "string",
                    "enum": ["venda", "cliente", "reembolso", "outros"],
                },
                "descricao": {"type": "string", "description": "de onde veio, resumido - omita se nao houver detalhe"},
                "banco": {
                    "type": "string",
                    "description": (
                        "SO preencha se o Alex citar explicitamente em qual banco/conta caiu o "
                        "dinheiro (ex: 'recebi 500 do fulano no Nubank'). Omita sempre que ele nao "
                        "mencionar - nunca adivinhe qual conta foi."
                    ),
                },
            },
            "required": ["valor", "categoria"],
        },
    },
    {
        "name": "definir_orcamento",
        "description": (
            "Define (ou muda) o limite mensal de gasto numa categoria - use quando o Alex disser "
            "algo como 'quero gastar no maximo 800 em mercado por mes' ou 'define um orcamento de "
            "300 pra lazer'. O painel avisa sozinho quando o gasto real da categoria chegar perto "
            "(90%) ou passar do limite naquele mes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "categoria": {
                    "type": "string",
                    "enum": ["mercado", "transporte", "lazer", "contas", "saude", "outros"],
                },
                "valor_limite": {"type": "number"},
            },
            "required": ["categoria", "valor_limite"],
        },
    },
    {
        "name": "registrar_meta",
        "description": "Cria uma meta financeira (algo que o Alex quer juntar dinheiro pra comprar/fazer).",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "valor": {"type": "number"},
                "prazo": {"type": "string", "description": "data limite AAAA-MM-DD - omita se nao houver"},
            },
            "required": ["titulo", "valor"],
        },
    },
    {
        "name": "gerar_plano_do_dia",
        "description": "Olha as tarefas pendentes e a agenda de hoje do Alex e sugere a melhor ordem pra fazer as coisas.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "registrar_lembrete",
        "description": (
            "Registra uma data importante pra avisar com antecedencia mais perto do dia - "
            "coisas como validade de licenca/exame medico de piloto, vencimento de seguro, "
            "revisao de veiculo, aniversario de alguem. Diferente de tarefa: isso e uma data "
            "que se repete ou que so importa mesmo quando estiver perto, nao algo pra fazer agora."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "data": {"type": "string", "description": "AAAA-MM-DD da proxima ocorrencia"},
                "recorrente": {
                    "type": "boolean",
                    "description": "true se repete todo ano nessa mesma data (ex: aniversario, validade anual) - false se for so uma vez",
                },
            },
            "required": ["titulo", "data"],
        },
    },
    {
        "name": "registrar_medicamento",
        "description": (
            "Cadastra um remedio que o Alex toma com nome, dosagem e horario, pra virar uma "
            "tarefa recorrente na agenda que avisa 10 minutos antes na hora de tomar - copia o "
            "fluxo de 'Medicamentos' do Apple Saude, que o painel nao consegue ler/gravar direto "
            "(Apple nao expõe essa parte pelo Atalhos). Use quando o Alex disser um remedio novo "
            "com horario, tipo 'tenho que tomar Losartana 50mg todo dia as 8h'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "nome do remedio"},
                "dosagem": {"type": "string", "description": "ex: '50mg', '1 comprimido' - omita se nao foi dito"},
                "horario": {"type": "string", "description": "HH:MM do horario de tomar"},
                "recorrencia": {
                    "type": "string",
                    "description": (
                        "'diaria' (padrao, use se o Alex nao especificar) ou 'semanal:N,N,...' com "
                        "0=segunda...6=domingo pros dias especificos da semana"
                    ),
                },
            },
            "required": ["nome", "horario"],
        },
    },
    {
        "name": "registrar_hidratacao",
        "description": (
            "Registra +1 copo de agua bebido AGORA (hoje). Use quando o Alex disser algo tipo "
            "'bebi agua', 'tomei um copo de agua'. Sem parametro nenhum - so soma 1 no contador "
            "do dia."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "registrar_medida",
        "description": (
            "Registra uma medida corporal do dia (peso ou medida tipo biceps/cintura/coxa) pra "
            "acompanhar evolucao ao longo do tempo. Use quando o Alex disser um numero de peso ou "
            "medida, tipo 'hoje to com 82kg' ou 'biceps direito 38cm'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "description": "ex: 'peso', 'biceps', 'cintura', 'coxa' - sempre em minusculo"},
                "valor": {"type": "number"},
                "unidade": {
                    "type": "string",
                    "description": "ex: 'kg', 'cm' - omita que o sistema usa 'kg' pra peso e 'cm' pro resto por padrao",
                },
            },
            "required": ["tipo", "valor"],
        },
    },
    {
        "name": "registrar_checkin",
        "description": (
            "Check-in de como o Alex esta HOJE: energia, sono e humor, cada um 'ruim', 'ok' ou "
            "'bom'. Use quando ele disser algo tipo 'dormi mal', 'to sem energia', 'hoje to "
            "bem'. Preencha so o que ele disse - omita o resto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "energia": {"type": "string", "enum": ["ruim", "ok", "bom"]},
                "sono": {"type": "string", "enum": ["ruim", "ok", "bom"]},
                "humor": {"type": "string", "enum": ["ruim", "ok", "bom"]},
            },
        },
    },
    {
        "name": "iniciar_hiperfoco",
        "description": (
            "Liga o modo hiperfoco: silencia notificacao nao critica por 25, 50 ou 90 minutos "
            "(so passa tarefa com hora marcada, remedio, compromisso chegando e voo). Use quando "
            "o Alex disser que vai focar/se concentrar numa coisa. Sem duracao dita, use 50."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"minutos": {"type": "integer", "enum": [25, 50, 90]}},
        },
    },
    {
        "name": "registrar_conversa",
        "description": (
            "Nota leve de conversa: 'falei com X sobre Y'. Use quando o Alex contar que falou/"
            "encontrou/ligou pra alguem. Zera a contagem de 'faz tempo que nao fala com X' se a "
            "pessoa estiver na lista dele."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pessoa": {"type": "string", "description": "nome ou apelido como ele falou (ex: 'mae', 'Joao')"},
                "sobre": {"type": "string", "description": "assunto em poucas palavras - omita se ele nao disse"},
            },
            "required": ["pessoa"],
        },
    },
    {
        "name": "cadastrar_pessoa",
        "description": (
            "Poe alguem na lista curta de pessoas importantes, com de quantos em quantos dias o "
            "Alex quer falar com ela (ex: 'quero falar com minha mae toda semana' = 7). O painel "
            "avisa quando passar desse prazo sem conversa registrada."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "frequencia_dias": {"type": "integer", "description": "padrao 14 se ele nao disser"},
            },
            "required": ["nome"],
        },
    },
    {
        "name": "registrar_conta_pessoal",
        "description": (
            "Cadastra uma conta PESSOAL recorrente (luz, internet, cartao, aluguel) com dia de "
            "vencimento todo mes - o painel avisa 3 dias antes e no dia. Nao e gasto (use "
            "registrar_gasto pra isso) e nao e conta da construtora."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "dia_vencimento": {"type": "integer", "description": "1 a 31"},
                "valor": {"type": "number", "description": "omita se variar ou nao foi dito"},
            },
            "required": ["nome", "dia_vencimento"],
        },
    },
    {
        "name": "adicionar_compras",
        "description": (
            "Poe itens na lista de compras de casa. Use quando o Alex disser 'acabou o X', "
            "'precisa comprar Y', 'anota pra comprar Z'. Um item por entrada, curto (ex: 'cafe', "
            "'papel higienico'). O painel avisa quando ele chegar no mercado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"itens": {"type": "array", "items": {"type": "string"}}},
            "required": ["itens"],
        },
    },
    {
        "name": "salvar_ficha_treino",
        "description": (
            "Salva (ou substitui) a ficha de treino de um grupo muscular - quando o Alex colar/"
            "ditar o treino (ex: 'peito: supino reto 4x10, crucifixo 3x12'). Um exercicio por linha."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "grupo": {"type": "string", "description": "ex: 'Peito', 'Costas', 'Perna', 'Treino A'"},
                "exercicios": {"type": "array", "items": {"type": "string"}, "description": "um por item, com series x reps se ele disse"},
            },
            "required": ["grupo", "exercicios"],
        },
    },
    {
        "name": "registrar_treino",
        "description": "Registro leve de treino feito HOJE ('treinei peito 1h', 'fui na academia').",
        "input_schema": {
            "type": "object",
            "properties": {
                "grupo": {"type": "string", "description": "grupo/tipo - omita se nao disse"},
                "duracao_min": {"type": "integer", "description": "omita se nao disse"},
                "nota": {"type": "string", "description": "algo que ele comentou (carga, como foi) - omita se nada"},
            },
        },
    },
    {
        "name": "registrar_viagem",
        "description": (
            "Registra uma viagem (nao voo de instrucao do aeroclube - pra isso use registrar_voo). "
            "O painel monta checklist de mala e lembra de documento 3 dias antes e no dia."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "destino": {"type": "string"},
                "data_ida": {"type": "string", "description": "AAAA-MM-DD"},
                "data_volta": {"type": "string", "description": "AAAA-MM-DD - omita se nao disse"},
                "motivo": {"type": "string", "description": "trabalho, ferias, visita... - omita se nao disse"},
            },
            "required": ["destino", "data_ida"],
        },
    },
    {
        "name": "registrar_lugar",
        "description": (
            "Guarda um lugar que o Alex GOSTOU (restaurante, hotel, bar, praia) pra sugerir de novo "
            "quando ele voltar pra mesma cidade."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "cidade": {"type": "string", "description": "omita se nao disse"},
                "tipo": {"type": "string", "description": "restaurante, hotel, bar... - omita se nao disse"},
                "nota": {"type": "string", "description": "o que ele gostou - omita se nada"},
            },
            "required": ["nome"],
        },
    },
    {
        "name": "registrar_manutencao",
        "description": (
            "Manutencao recorrente por tempo (carro, casa, equipamento): 'trocar oleo a cada 6 "
            "meses, troquei hoje'. O painel avisa quando estiver chegando a proxima."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item": {"type": "string"},
                "intervalo_meses": {"type": "integer", "description": "1 a 120"},
                "ultima_vez": {"type": "string", "description": "AAAA-MM-DD da ultima vez feita - omita se nao sabe"},
            },
            "required": ["item", "intervalo_meses"],
        },
    },
    {
        "name": "registrar_ideia_presente",
        "description": (
            "Guarda uma ideia de presente pra uma pessoa especifica, pra nao esquecer na hora "
            "de comprar (aniversario, Natal, qualquer ocasiao)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pessoa": {"type": "string"},
                "ideia": {"type": "string"},
                "ocasiao": {"type": "string", "description": "aniversario, Natal... - omita se nao disse"},
            },
            "required": ["pessoa", "ideia"],
        },
    },
    {
        "name": "registrar_responder",
        "description": (
            "Mensagem importante que o ALEX precisa responder e deixou 'pra depois' (diferente "
            "de registrar_espera, que e quando ele espera resposta de alguem). Lembra no dia "
            "seguinte as 10h ate ele marcar como respondida."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "quem": {"type": "string"},
                "sobre": {"type": "string", "description": "omita se nao disse"},
            },
            "required": ["quem"],
        },
    },
    {
        "name": "registrar_aprender",
        "description": (
            "Poe um tema na lista 'quero aprender sobre X' - o painel lembra de retomar quando ficar "
            "parado. Use quando o Alex disser que quer aprender/estudar algo (fora do curso de piloto, "
            "que ja tem o proprio rodizio de temas)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tema": {"type": "string"},
                "nota": {"type": "string", "description": "por onde comecar, link, livro - omita se nada"},
            },
            "required": ["tema"],
        },
    },
    {
        "name": "salvar_link",
        "description": (
            "Salva um link (artigo, video) pra ver depois - o painel le a pagina e guarda um resumo "
            "curto. Use quando o Alex mandar um link dizendo pra guardar/ver depois."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "marcar_saida_noite",
        "description": (
            "O Alex vai sair HOJE a noite (festa, balada, jantar). Usado no checklist de saida "
            "de casa (lembrar de fazer bigode e cavanhaque na sexta/sabado)."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "registrar_voo",
        "description": (
            "Registra um voo do Alex (curso de piloto comercial) - ja realizado (com horas "
            "voadas) ou so um compromisso agendado pro futuro (sem horas ainda, so data/origem/"
            "destino). Nao invente horas: so preencha 'horas' se o Alex disse quanto tempo voou."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "AAAA-MM-DD do voo"},
                "destino": {"type": "string"},
                "origem": {"type": "string", "description": "omita se nao foi dito"},
                "horas": {
                    "type": "number",
                    "description": "horas voadas - so inclua se o voo ja aconteceu e o Alex disse quanto tempo",
                },
                "observacao": {
                    "type": "string",
                    "description": (
                        "diario de bordo do voo - o trajeto e o que ele fez/aprendeu, no jeito que ele "
                        "contou (ex: 'fui de Blumenau, passei em Curitiba, fui pra Florianopolis e voltei, "
                        "treino de pouso com vento cruzado'). So escreva o que o Alex de fato contou, nao invente - "
                        "omita se ele nao deu detalhe nenhum."
                    ),
                },
            },
            "required": ["data", "destino"],
        },
    },
    {
        "name": "registrar_memoria",
        "description": (
            "Guarda um fato duravel sobre o Alex que apareceu na conversa e vale lembrar em "
            "conversas futuras (preferencia, rotina, relacao, contexto recorrente) - use JUNTO "
            "com outra ferramenta se for o caso, nunca no lugar dela. Raro: a maioria das "
            "mensagens nao tem nada assim."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fato": {
                    "type": "string",
                    "description": "o fato em terceira pessoa, frase curta (ex: 'prefere tarefas rapidas de manha')",
                },
            },
            "required": ["fato"],
        },
    },
    {
        "name": "registrar_espera",
        "description": (
            "Registra que o Alex esta esperando uma resposta/retorno de outra pessoa (fornecedor, "
            "corretora, cliente, qualquer terceiro) - use quando ele disser algo como 'to esperando "
            "resposta do fornecedor de ferro' ou 'mandei mensagem pra corretora, aguardando'. "
            "Diferente de tarefa: isso nao e algo que O ALEX precisa fazer, e algo que ele esta "
            "aguardando ALGUEM ELE fazer/responder."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "quem": {"type": "string", "description": "de quem esta esperando (ex: 'fornecedor de ferro', 'corretora do seguro')"},
                "sobre": {"type": "string", "description": "sobre o que (ex: 'preco do vergalhao', 'proposta do seguro')"},
            },
            "required": ["quem", "sobre"],
        },
    },
    {
        "name": "resolver_espera",
        "description": (
            "Marca uma espera como resolvida - use quando o Alex disser que a resposta chegou, ou "
            "que nao precisa mais esperar (ex: 'o fornecedor de ferro respondeu', 'ja recebi retorno "
            "da corretora', 'deixa pra la aquela espera')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "quem": {"type": "string", "description": "de quem era a espera, como o Alex se referiu"},
            },
            "required": ["quem"],
        },
    },
    {
        "name": "registrar_feito",
        "description": (
            "Registra algo que o Alex JA FEZ mas nunca tinha contado pro painel antes - use "
            "quando ele estiver passando o dia a limpo no final do dia e mencionar coisas ja "
            "concluidas que voce nao tinha registrado (ex: 'fiz academia, paguei a conta de luz "
            "e resolvi aquele negocio do fornecedor'). Se ja existir uma tarefa pendente parecida, "
            "ela e marcada como feita; senao uma tarefa nova ja concluida e criada. Chame uma vez "
            "pra cada coisa diferente que ele mencionar. NUNCA use pra algo que ele ainda vai "
            "fazer - isso e' registrar_tarefa."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "o que foi feito, resumido"},
            },
            "required": ["titulo"],
        },
    },
    {
        "name": "consultar_sobra_do_mes",
        "description": (
            "Calcula quanto sobrou pra gastar esse mes ate agora (renda que entrou menos o que ja "
            "foi gasto de verdade) - use quando o Alex perguntar 'quanto sobra pra gastar?', "
            "'quanto ainda posso gastar esse mes?' ou algo parecido. Tambem devolve o quanto ja "
            "esta so planejado/cogitado (nao decidido ainda), pra avisar que pode reduzir mais a "
            "sobra se virar gasto de verdade."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "rotular_cobranca_generica",
        "description": (
            "Diz o que uma cobranca generica do extrato (ex: 'APPLE.COM/BILL', que sozinha nao diz "
            "se e iCloud, Apple Music ou outra coisa) realmente e - use quando o Alex responder a "
            "uma pergunta do tipo 'qual assinatura e essa cobranca de R$X?' (ex: 'a cobranca da "
            "apple de 14,90 e o icloud'). So use pra identificar uma cobranca generica ja "
            "sinalizada, nunca pra registrar um gasto novo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "valor": {"type": "number", "description": "o valor exato da cobranca que ele esta identificando"},
                "apelido": {"type": "string", "description": "o nome da assinatura (ex: 'iCloud 200GB', 'Apple Music')"},
            },
            "required": ["valor", "apelido"],
        },
    },
    {
        "name": "consultar_gastos_fixos",
        "description": (
            "Descobre quanto o Alex gasta de fixo por mes (assinaturas, aluguel, academia - "
            "qualquer gasto que se repete todo mes com valor parecido) - use quando ele perguntar "
            "algo como 'quanto eu gasto de fixo por mes?', 'quais sao minhas assinaturas?' ou "
            "'quanto ta comprometido todo mes?'. Devolve a lista detectada e o total somado."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "consultar_noticias",
        "description": (
            "Busca manchetes recentes sobre um assunto ou lugar (ex: 'Brusque SC', 'aviacao civil "
            "Brasil') - use SO quando o Alex pedir noticia explicitamente (ex: 'tem noticia de "
            "Brusque?', 'o que ta rolando na cidade?'). Nunca chame por conta propria (nao e "
            "notificacao proativa, e sob demanda). Se vier vazio, diga que nao achou nada sobre o "
            "assunto agora - nunca invente uma manchete."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "termo": {"type": "string", "description": "o assunto/lugar a buscar, como o Alex mencionou"},
            },
            "required": ["termo"],
        },
    },
    {
        "name": "salvar_nota",
        "description": (
            "Guarda uma nota/anotacao mais longa que nao e tarefa nem gasto nem lembrete - um "
            "roteiro, um plano, uma lista de coisas a verificar, algo que ele quer poder consultar "
            "depois. Use quando o Alex disser algo como 'anota isso: [lista de coisas]' ou 'cria "
            "uma nota sobre [assunto] com [detalhes]'. Se ele so quer registrar UM item pontual "
            "(uma tarefa, um gasto), use a ferramenta certa pra isso em vez desta."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "titulo curto da nota"},
                "corpo": {
                    "type": "string",
                    "description": "o conteudo da nota, pode ter varias linhas/itens",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "palavras-chave curtas pra achar essa nota depois (ex: ['portugal', 'viagem']) - omita se nao houver nenhuma obvia",
                },
            },
            "required": ["titulo", "corpo"],
        },
    },
    {
        "name": "consultar_notas",
        "description": (
            "Busca notas ja salvas por titulo, conteudo ou tag - use quando o Alex perguntar algo "
            "como 'o que eu anotei sobre Portugal?' ou 'abre minha nota de viagem'. Se vier vazio, "
            "diga que nao achou nenhuma nota com esse termo - nunca invente conteudo de nota."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "termo": {"type": "string", "description": "o que procurar - assunto, tag ou palavra do titulo"},
            },
            "required": ["termo"],
        },
    },
    {
        "name": "registrar_decisao",
        "description": (
            "Guarda uma decisao importante no diario de decisao - o que foi decidido, o contexto/"
            "motivo, pra poder revisar depois se deu certo. Use quando o Alex disser algo como "
            "'decidi [algo]' ou 'vou registrar essa decisao: [...]' sobre algo que ele quer "
            "acompanhar o resultado mais pra frente. Diferente de 'vale a pena?' (que so pesa "
            "pros/contras na hora, sem guardar pra revisar depois) - se ele so quer ajuda pra "
            "decidir agora, use a ferramenta certa pra isso em vez desta."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "decisao": {"type": "string", "description": "o que foi decidido, resumido"},
                "contexto": {
                    "type": "string",
                    "description": "por que, o que foi considerado - omita se o Alex nao deu motivo",
                },
                "revisao_em": {
                    "type": "string",
                    "description": "data (AAAA-MM-DD) pra lembrar de revisar essa decisao, se ele mencionar um prazo - omita se nao houver",
                },
            },
            "required": ["decisao"],
        },
    },
    {
        "name": "sugerir_horario_livre",
        "description": (
            "Acha o maior espaco livre HOJE, olhando o que ja esta marcado no dia de verdade - "
            "use quando o Alex perguntar que horas fazer algo (tipo ir pra academia) sem ter dito "
            "um horario fixo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "duracao_minutos": {
                    "type": "integer",
                    "description": "quanto tempo a atividade costuma durar, em minutos - use 60 se ele nao disser",
                },
                "depois_das": {
                    "type": "string",
                    "description": "HH:MM - so procura depois desse horario (ex: ele disse 'de tarde'). Omita se nao houver preferencia",
                },
                "antes_das": {
                    "type": "string",
                    "description": "HH:MM - so procura antes desse horario. Omita se nao houver preferencia",
                },
                "titulo": {
                    "type": "string",
                    "description": "o que ele quer encaixar, curto (ex: 'treino', 'estudar meteorologia') - vira o titulo do card",
                },
            },
            "required": ["duracao_minutos"],
        },
    },
    {
        "name": "distribuir_tarefas_na_semana",
        "description": (
            "Use quando o Alex despejar VARIAS tarefas soltas de uma vez, sem data especifica pra "
            "cada uma (ex: domingo listando um monte de coisa pra fazer na semana) - em vez de "
            "chamar registrar_tarefa uma vez pra cada, chame esta ferramenta UMA VEZ com a lista de "
            "titulos. O painel calcula sozinho em que dia e horario cada uma cai (espalhando pelos "
            "dias menos ocupados, evitando hora de comer) e devolve a proposta em 'propostas' - "
            "APRESENTE o plano dia a dia na sua resposta (ex: 'segunda: X as 9h - terca: Y as "
            "10h30...') e pergunte se esta bom. NAO cria nada no banco ainda - so quando o Alex "
            "confirmar explicitamente (ai voce chama confirmar_plano_semana) as tarefas realmente "
            "entram na agenda. Se ele pedir ajuste antes de confirmar (tirar uma, trocar de dia), "
            "chame esta ferramenta de novo com a lista corrigida - isso substitui a proposta "
            "anterior."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titulos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "cada tarefa que o Alex mencionou, um titulo curto por item, na ordem que ele falou",
                },
            },
            "required": ["titulos"],
        },
    },
    {
        "name": "confirmar_plano_semana",
        "description": (
            "Chame quando o Alex aprovar explicitamente o ultimo plano de semana proposto (ex: "
            "'pode', 'ta bom', 'confirma', 'manda ver', 'fechado') - so ai as tarefas da proposta "
            "pendente (ver distribuir_tarefas_na_semana) sao criadas de verdade na agenda. Nunca "
            "chame sem uma confirmacao explicita do Alex primeiro, e nunca chame se nao houver "
            "nenhum plano pendente (olhe o contexto - ele avisa quando ha um)."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "cancelar_plano_semana",
        "description": (
            "Chame quando o Alex rejeitar ou pedir pra esquecer o plano de semana proposto (ex: "
            "'deixa quieto', 'nao, esquece isso', 'depois eu vejo') - so descarta a proposta "
            "pendente, nada e criado."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "sugerir_tarefa_para_agora",
        "description": (
            "Chame quando o Alex disser que esta ocioso/sem nada pra fazer AGORA (ex: 'nao to "
            "fazendo nada', 'to sem nada pra fazer', 'to livre agora', 'que faco agora') - pedido "
            "explicito dele (TDAH): em vez de so confirmar que ta tudo livre, puxa uma tarefa que "
            "so estava marcada pra outro dia da semana e sugere adiantar ela agora. Devolve a "
            "tarefa com dia mais proximo (tipo 'adiantada') ou, se nenhuma tiver dia marcado, uma "
            "tarefa solta sem data (tipo 'solta'). Na resposta, sugira como pergunta (ex: 'que tal "
            "adiantar \"limpar o quarto\", que so estava marcado pra terca?'), nunca decida por "
            "ele - se ele topar e depois contar que fez, isso vira `registrar_feito` normalmente, "
            "nao precisa de nenhuma ferramenta especial pra 'mover' a tarefa."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "calcular_gasto_viagem",
        "description": (
            "Calcula distancia real, duracao e gasto de combustivel de uma viagem de carro, "
            "usando o trajeto de verdade do Google Maps - use quando o Alex perguntar quanto "
            "gastaria de gasolina indo de um lugar a outro."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "destino": {"type": "string"},
                "origem": {
                    "type": "string",
                    "description": "omita pra usar o endereco padrao de casa do Alex",
                },
                "km_por_litro": {
                    "type": "number",
                    "description": "consumo medio do carro - pergunte antes se ele nao disse e nao esta nas memorias",
                },
                "preco_por_litro": {
                    "type": "number",
                    "description": "preco do combustivel em reais por litro - pergunte antes se ele nao disse",
                },
            },
            "required": ["destino", "km_por_litro", "preco_por_litro"],
        },
    },
    {
        "name": "sugerir_posto_no_caminho",
        "description": (
            "Sugere um posto de gasolina perto do meio do caminho de uma viagem longa - so "
            "localizacao, NUNCA compara preco entre postos (essa informacao nao existe de forma "
            "confiavel pro Brasil nas fontes que tenho). Use quando o Alex perguntar onde parar "
            "pra abastecer numa viagem."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "destino": {"type": "string"},
                "origem": {
                    "type": "string",
                    "description": "omita pra usar o endereco padrao de casa do Alex",
                },
            },
            "required": ["destino"],
        },
    },
    {
        "name": "agendar_uber",
        "description": (
            "Agenda um pedido de Uber pra daqui X minutos - NUNCA pede a corrida na hora nem "
            "cobra nada aqui. Passado esse tempo, o painel busca o preco real e manda um aviso "
            "pro Alex confirmar antes de qualquer coisa ser cobrada de verdade. Use quando o "
            "Alex pedir um Uber por voz (ex: 'pede um Uber pra tal lugar daqui 20 minutos')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "destino": {"type": "string"},
                "origem": {
                    "type": "string",
                    "description": "omita pra usar o endereco padrao de casa do Alex",
                },
                "minutos": {
                    "type": "integer",
                    "description": (
                        "quantos minutos esperar antes de buscar o preco e pedir confirmacao - "
                        "use 0 se ele quiser 'agora' (o painel confere a cada poucos minutos, "
                        "entao 'agora' pode levar ate uns 5 minutos pra aparecer o aviso de preco)"
                    ),
                },
            },
            "required": ["destino", "minutos"],
        },
    },
    {
        "name": "sugerir_tema_estudo",
        "description": (
            "Sugere o proximo tema de estudo de uma lista fixa e curta que o Alex ja definiu "
            "(regulamentacao, meteorologia, navegacao), sempre um de cada vez em rodizio - use "
            "quando ele perguntar o que estudar agora/hoje. NUNCA sugira um tema por conta "
            "propria nem invente sub-assunto - so repasse exatamente o que a ferramenta devolver, "
            "pra ele nao se dispersar estudando algo que nao pediu."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "registrar_item_cotacao",
        "description": (
            "Registra um preco de fornecedor dentro de uma cotacao (ex: 'fornecedor tal, "
            "R$5000, pra cotacao de ferro') - se a cotacao com esse titulo ainda nao existir, "
            "cria automaticamente. Use quando o Alex mencionar um preco de fornecedor pra "
            "comparar depois com outros, mesmo sem ter dito explicitamente 'abrir cotacao'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo_cotacao": {
                    "type": "string",
                    "description": "o material/servico sendo cotado (ex: 'portas', 'vasos sanitarios', 'ferro')",
                },
                "fornecedor": {"type": "string"},
                "valor": {"type": "number"},
                "prazo_texto": {
                    "type": "string",
                    "description": "prazo de entrega, se ele disser (ex: '15 dias') - omita se nao houver",
                },
                "observacao": {"type": "string", "description": "detalhe curto relevante - omita se nao houver"},
            },
            "required": ["titulo_cotacao", "fornecedor", "valor"],
        },
    },
    {
        "name": "comparar_cotacao",
        "description": (
            "Lista os fornecedores ja registrados numa cotacao, do mais barato pro mais caro - "
            "use quando o Alex pedir pra comparar/ver os precos de uma cotacao."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo_cotacao": {"type": "string"},
            },
            "required": ["titulo_cotacao"],
        },
    },
    {
        "name": "registrar_habito",
        "description": (
            "Cria um habito NOVO (diferente da rotina guiada de manha/noite - isso aqui e coisa "
            "tipo 'meditar 15 min todo dia as 8h' ou 'academia segunda, quarta e sexta'). O painel "
            "marca dia a dia e mostra os ultimos 7 dias."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "ex: 'meditar', 'academia', 'ler'"},
                "meta": {"type": "string", "description": "ex: '15 min', '30 paginas' - omita se nao disse"},
                "frequencia_tipo": {
                    "type": "string",
                    "enum": ["diario", "dias_semana", "n_vezes_semana"],
                    "description": (
                        "'diario' = todo dia; 'dias_semana' = dias fixos da semana (preencha "
                        "dias_semana); 'n_vezes_semana' = qualquer dia conta, ate bater a meta "
                        "da semana (preencha vezes_por_semana)"
                    ),
                },
                "dias_semana": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "so se frequencia_tipo='dias_semana': 0=segunda a 6=domingo",
                },
                "vezes_por_semana": {
                    "type": "integer",
                    "description": "so se frequencia_tipo='n_vezes_semana': de 1 a 7",
                },
                "horario": {
                    "type": "string",
                    "description": "HH:MM, horario de lembrete opcional (ex: '08:00') - omita se nao disse",
                },
            },
            "required": ["nome", "frequencia_tipo"],
        },
    },
    {
        "name": "marcar_habito",
        "description": "Marca (ou desmarca, se ja estava marcado) um habito existente como feito HOJE.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "nome do habito, como o Alex cadastrou (aproximado)"},
            },
            "required": ["nome"],
        },
    },
    {
        "name": "criar_projeto",
        "description": (
            "Cria um projeto generico (qualquer coisa com etapas e prazo - 'reformar o quarto', "
            "'lancar o curso', ate a expansao da construtora como projeto SO com nome/etapa/marco, "
            "NUNCA campo financeiro - dinheiro da construtora fica no sistema dela). Viagem NAO e "
            "projeto - pra isso use registrar_viagem."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "prazo_final": {"type": "string", "description": "AAAA-MM-DD - omita se nao disse"},
            },
            "required": ["nome"],
        },
    },
    {
        "name": "adicionar_etapa",
        "description": "Adiciona uma etapa/passo novo a um projeto existente (checklist ordenado).",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome_projeto": {"type": "string", "description": "nome do projeto, aproximado"},
                "texto": {"type": "string", "description": "a etapa em si (ex: 'comprar tinta')"},
                "data_prevista": {"type": "string", "description": "AAAA-MM-DD - omita se nao disse"},
            },
            "required": ["nome_projeto", "texto"],
        },
    },
    {
        "name": "concluir_etapa",
        "description": "Marca como concluida a proxima etapa pendente de um projeto (a primeira da fila).",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome_projeto": {"type": "string", "description": "nome do projeto, aproximado"},
            },
            "required": ["nome_projeto"],
        },
    },
    {
        "name": "agendar_evento",
        "description": (
            "Cria um evento no calendario 'Painel' do iCloud (calendario separado, exclusivo do "
            "painel - nunca mexe em outro calendario do Alex). Use pra compromisso com hora "
            "marcada que ele quer ver no iCloud de verdade."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "data": {"type": "string", "description": "AAAA-MM-DD"},
                "hora_inicio": {"type": "string", "description": "HH:MM"},
                "hora_fim": {"type": "string", "description": "HH:MM"},
                "lembrar_min_antes": {
                    "type": "integer",
                    "description": "quantos minutos antes lembrar - omita se ele nao pediu lembrete",
                },
            },
            "required": ["titulo", "data", "hora_inicio", "hora_fim"],
        },
    },
    # ---- Fase 6 (US-E7): consultas que viram card na tela --------------------
    {
        "name": "consultar_projeto",
        "description": (
            "Mostra projeto(s) e/ou viagem(ns) com checklist, progresso e proximo marco (card na tela). "
            "Use quando ele pedir pra ver/perguntar como esta um projeto ou uma viagem."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "termo": {
                    "type": "string",
                    "description": "parte do nome do projeto ou destino da viagem ('viagem' = proxima viagem) - omita pra todos",
                },
            },
        },
    },
    {
        "name": "consultar_meta",
        "description": "Mostra meta(s) financeira(s) pessoal(is) com progresso (card na tela).",
        "input_schema": {
            "type": "object",
            "properties": {"termo": {"type": "string", "description": "parte do nome da meta - omita pra todas"}},
        },
    },
    {
        "name": "consultar_treinos",
        "description": "Mostra os treinos registrados nos ultimos N dias, com tempo por atividade (card na tela).",
        "input_schema": {
            "type": "object",
            "properties": {"dias": {"type": "integer", "description": "janela em dias (1 a 90) - use 7 se ele nao disser"}},
        },
    },
    {
        "name": "consultar_habitos",
        "description": "Mostra os habitos com a semana (seg a dom) marcada (card na tela).",
        "input_schema": {
            "type": "object",
            "properties": {"nome": {"type": "string", "description": "parte do nome de um habito - omita pra todos"}},
        },
    },
    {
        "name": "consultar_saude_dia",
        "description": "Mostra a saude de hoje: copos de agua, passos, sono e treino (card na tela).",
        "input_schema": {"type": "object", "properties": {}},
    },
]


# ---------------------------------------------------------------------------
# Fase 7 / A6: chat com layout de cache estavel
# ---------------------------------------------------------------------------
#
# Ordem que o provedor ve (tools -> system -> messages) e onde fica cada coisa:
#
#   tools    CHAT_TOOLS (fixo; breakpoint 1 no ultimo tool)
#   system   CHAT_SYSTEM_PROMPT com {hoje} e {memorias} (string; muda no maximo
#            1x por dia ou quando nasce memoria nova - nada que muda a cada
#            chamada fica aqui)
#   msg[0]   1o bloco = "bloco fixo do historico" (resumo da A5, ou um texto
#            fixo quando nao ha resumo) - breakpoint 2 (cobre tools+system+resumo)
#   ...      historico estavel na integra - breakpoint 3 no ultimo bloco dele
#   ultima   mensagem do usuario = [bloco "Contexto de agora" (muda a cada
#            chamada), texto novo] - breakpoint 4 "rolante" (move pro ultimo
#            tool_result a cada rodada do loop de tools)
#
# Maximo de 4 breakpoints por request e lookback de 20 posicoes (conferido no
# guia de prompt caching da Anthropic, secao "API reference" e "20-block
# lookback window"). Sonnet 5 so cacheia prefixo >= 1024 tokens (abaixo disso o
# cache_control e ignorado em silencio, sem erro).
#
# Por que o system continua string (e nao lista de blocos com cache_control):
# os testes existentes (tests/test_claude_client.py) fazem
# assertIn("<trecho>", kwargs["system"]) e conferem data de hoje e memorias no
# system. Com o breakpoint 2 logo depois do system (1o bloco das mensagens) o
# efeito de cache e o mesmo: o prefixo tools+system fica cacheado.
#
# Por que o chat NAO passa por ia.core.chamar_ia: o contrato (ia/contrato.py,
# Adapter.chamar) nao tem parametro de tools nem devolve tool_use/stop_reason.
# O menor caminho seguro foi manter o SDK Anthropic direto (ia.legado.client)
# com o layout de cache acima, lendo modelo/max_tokens/cache de
# ia/config.d/chat.json e medindo por ia.medicao.registrar_uso +
# ia.teto.teto_permite (quando medir_uso=True). O que faltaria pra levar o chat
# com tools pro contrato esta em scripts/ralph-a6-chat/APRENDIZADOS.md.

FUNCAO_CHAT = "chat"
FUNCAO_CHAT_SIMPLES = "chat_simples"
FUNCAO_DECISAO = "analisar_decisao"
FUNCAO_MENSAGEM_DIFICIL = "redigir_mensagem_dificil"

# Rodadas do loop de tool-use (igual a antes).
RODADAS_MAX = 4
# max_tokens padrao se ia/config.d/chat.json estiver ausente/invalido.
MAX_TOKENS_CHAT_PADRAO = 500
# Teto antigo do chat (brain dump US-E6: 8+ tool_use numa rodada). Se uma
# rodada bater no limite de 500 (stop_reason "max_tokens"), ela e refeita UMA
# vez com este teto - assim o limite novo corta custo no caso comum sem
# perder tarefa no meio de um brain dump longo.
MAX_TOKENS_CHAT_ESCALADO = 1500

# Resposta do caminho barato (roteador -> "luna") quando a mensagem precisa
# de ferramenta: o chat cai pro caminho padrao (com tools).
MARCADOR_PRECISA_FERRAMENTA = "__PRECISA_FERRAMENTA__"

TEXTO_SEM_RESUMO = "Resumo da conversa anterior: nenhum (valem so as mensagens abaixo)."
PREFIXO_RESUMO = "Resumo da conversa anterior (gerado pelo painel):\n"
PREFIXO_CONTEXTO_AGORA = "Contexto de agora (gerado pelo painel, nao foi o Alex que escreveu):\n"

CHAT_SIMPLES_PROMPT = """Voce e o assistente pessoal do Alex, dentro do painel pessoal dele. Hoje e
{hoje}. Ele tem TDAH - responda direto e curto, tom de colega, sem enrolacao e sem emoji em
excesso. Nunca cite valor em R$ especifico da construtora dele.

Voce NAO tem ferramentas aqui. Se a mensagem pedir para registrar, marcar, agendar, consultar ou
mudar qualquer coisa no painel (tarefa, gasto, renda, meta, voo, habito, remedio, nota, lembrete,
projeto, agenda, saldo), ou se voce precisar de um dado que nao esta no contexto, responda
exatamente {marcador} e nada mais.

Coisas duraveis que voce sabe sobre o Alex:
{memorias}"""


def _texto_memorias(memorias, vazio: str = "nenhuma ainda") -> str:
    return "\n".join(f"- {m}" for m in memorias or []) or vazio


def montar_sistema_chat(memorias, hoje: date | None = None) -> str:
    """System do chat: so o que e estavel no dia (regras, data, memorias)."""
    return CHAT_SYSTEM_PROMPT.format(
        hoje=(hoje or date.today()).isoformat(),
        memorias=_texto_memorias(memorias),
    )


def _config_ia(funcao: str):
    """Config de ia/config.d/<funcao>.json via ia.core (mesma validacao/cache
    por mtime). Config quebrada nunca derruba o chat: loga e devolve None
    (usa os padroes de hoje)."""
    try:
        return core._carregar_config(funcao)
    except Exception:  # noqa: BLE001
        log.exception("chat: config de IA %s invalida, usando padrao", funcao)
        return None


def _modelo_chat(config) -> str:
    """Modelo Anthropic do chat com tools. Se o Alex virar `ativo: true` com
    um alvo de outro provedor (ex.: openai/gpt-6-sol), o chat com tools ainda
    nao consegue ir pra la (contrato sem tools) - fica no modelo_atual."""
    if not config:
        return SONNET
    principal = config["alvo"] if config["ativo"] and config["alvo"] else config["modelo_atual"]
    if principal["provedor"] != "anthropic":
        log.warning("chat: alvo %s/%s ainda nao suporta tools; usando modelo_atual",
                    principal["provedor"], principal["modelo"])
        principal = config["modelo_atual"]
    if principal["provedor"] != "anthropic":
        return SONNET
    return principal["modelo"]


def _cache_control(config):
    """{"type": "ephemeral"[, "ttl": "1h"]} se o cache estiver ligado na
    config do chat (padrao: ligado), senao None."""
    cache = config["cache"] if config else {"ativo": True, "ttl": "5m"}
    if not cache.get("ativo"):
        return None
    controle = {"type": "ephemeral"}
    if cache.get("ttl") == "1h":
        controle["ttl"] = "1h"
    return controle


def _como_blocos(conteudo) -> list:
    """Conteudo de mensagem -> lista de blocos (copiados; nunca muta o
    historico de quem chamou). Texto vazio some (a API recusa bloco vazio)."""
    if isinstance(conteudo, str):
        return [{"type": "text", "text": conteudo}] if conteudo else []
    if isinstance(conteudo, list):
        return [copy.deepcopy(b) if isinstance(b, dict) else b for b in conteudo]
    if conteudo is None:
        return []
    return [{"type": "text", "text": str(conteudo)}]


def _separar_nova(historico) -> tuple[list, dict | None]:
    """(mensagens estaveis, mensagem nova do usuario ou None)."""
    hist = [m for m in historico or [] if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    if hist and hist[-1]["role"] == "user":
        return hist[:-1], hist[-1]
    return hist, None


def texto_bloco_historico_fixo(contexto_fixo: str = "") -> str:
    if isinstance(contexto_fixo, str) and contexto_fixo.strip():
        return PREFIXO_RESUMO + contexto_fixo.strip()
    return TEXTO_SEM_RESUMO


def montar_mensagens_chat(historico, contexto: str, contexto_fixo: str = "", cache_control=None) -> list:
    """Monta `messages` no layout de cache estavel (ver comentario do topo).
    Com `cache_control`, marca: bloco fixo do historico, fim do historico
    estavel e ultimo bloco da mensagem nova (rolante)."""
    estaveis, nova = _separar_nova(historico)
    msgs = []
    for m in estaveis:
        blocos = _como_blocos(m.get("content"))
        if blocos:
            msgs.append({"role": m["role"], "content": blocos})
    ultimo_estavel = len(msgs) - 1

    bloco_agora = {"type": "text", "text": PREFIXO_CONTEXTO_AGORA + (contexto or "nenhum")}
    final = [bloco_agora] + (_como_blocos(nova.get("content")) if nova else [])
    msgs.append({"role": "user", "content": final})

    bloco_fixo = {"type": "text", "text": texto_bloco_historico_fixo(contexto_fixo)}
    if msgs[0]["role"] == "user":
        msgs[0]["content"].insert(0, bloco_fixo)
    else:
        msgs.insert(0, {"role": "user", "content": [bloco_fixo]})
        ultimo_estavel += 1

    if cache_control:
        bloco_fixo["cache_control"] = dict(cache_control)
        if ultimo_estavel >= 0:
            ultimo_bloco = msgs[ultimo_estavel]["content"][-1]
            if isinstance(ultimo_bloco, dict) and ultimo_bloco is not bloco_fixo:
                ultimo_bloco["cache_control"] = dict(cache_control)
        rolante = msgs[-1]["content"][-1]
        if isinstance(rolante, dict) and "cache_control" not in rolante:
            rolante["cache_control"] = dict(cache_control)
    return msgs


def _tools_com_cache(cache_control) -> list:
    if not cache_control:
        return CHAT_TOOLS
    tools = list(CHAT_TOOLS)
    tools[-1] = {**tools[-1], "cache_control": dict(cache_control)}
    return tools


def _custo_usd(modelo: str, tokens_in: int, tokens_out: int, cache_lido: int, cache_escrito: int,
               ttl: str) -> float:
    custo = precos.custo_usd(modelo, tokens_in, tokens_out, cache_lido, cache_escrito, ttl_cache=ttl)
    if custo or modelo not in PRICING:
        return custo
    entrada, saida = PRICING[modelo]
    return (tokens_in / 1_000_000) * entrada + (tokens_out / 1_000_000) * saida


def _registrar_uso(funcao: str, modelo: str, uso: dict, latencia_ms: int, ok: bool = True) -> None:
    """ia.medicao.registrar_uso (tabela uso_ia, sem conteudo de prompt).
    Medicao nunca derruba o chat."""
    try:
        from ia.medicao import registrar_uso

        registrar_uso(
            funcao, "anthropic", modelo,
            tokens_in=uso["input_tokens"], tokens_out=uso["output_tokens"],
            tokens_cache_lido=uso["cache_read_input_tokens"],
            tokens_cache_escrito=uso["cache_creation_input_tokens"],
            custo_usd=uso["cost_usd"], latencia_ms=latencia_ms, ok=ok,
        )
    except Exception:  # noqa: BLE001
        log.exception("chat: falha ao registrar uso de %s", funcao)


def _teto_permite(funcao: str) -> bool:
    """ia.teto.teto_permite; erro no calculo bloqueia (mesma regra do ia.core)."""
    try:
        from ia.teto import teto_permite

        return bool(teto_permite(funcao))
    except Exception:  # noqa: BLE001
        log.exception("chat: falha ao consultar teto de %s", funcao)
        return False


def _mensagem_teto() -> str:
    try:
        from ia.teto import TETO_IA_MSG

        return TETO_IA_MSG
    except Exception:  # noqa: BLE001
        return "teto mensal de gasto com IA estourado"


def _uso_da_resposta(response, modelo: str, ttl: str) -> dict:
    u = getattr(response, "usage", None)
    tokens_in = int(getattr(u, "input_tokens", 0) or 0)
    tokens_out = int(getattr(u, "output_tokens", 0) or 0)
    cache_lido = int(getattr(u, "cache_read_input_tokens", 0) or 0)
    cache_escrito = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
    modelo_resp = getattr(response, "model", None) or modelo
    return {
        "model": modelo_resp,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "cache_read_input_tokens": cache_lido,
        "cache_creation_input_tokens": cache_escrito,
        "cost_usd": _custo_usd(modelo_resp, tokens_in, tokens_out, cache_lido, cache_escrito, ttl),
    }


def _decidir_rota(mensagem, historico_anterior, conn) -> str:
    """ia.roteador_chat.decidir (faixa A14). Flag desligada -> sempre
    "padrao". Qualquer erro -> "padrao" (o roteador so economiza)."""
    try:
        from ia import roteador_chat

        destino = roteador_chat.decidir(mensagem, {"historico": historico_anterior, "conn": conn})
    except Exception:  # noqa: BLE001
        log.exception("chat: roteador falhou, seguindo no padrao")
        return "padrao"
    return destino if destino in ("local", "luna", "padrao") else "padrao"


def _texto_de(conteudo) -> str:
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        return "\n".join(b.get("text", "") for b in conteudo if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _responder_simples(historico, contexto, memorias, contexto_fixo):
    """Caminho barato (roteador -> "luna"): resposta direta SEM tools via
    chamar_ia("chat_simples"). Devolve (texto, [], usage) ou None pra cair no
    caminho padrao (falha, teto, ou o modelo disse que precisa de ferramenta)."""
    estaveis, nova = _separar_nova(historico)
    mensagens = [{"role": m["role"], "content": _texto_de(m.get("content"))} for m in estaveis]
    mensagens = [m for m in mensagens if m["content"]]
    texto_novo = _texto_de(nova.get("content")) if nova else ""
    mensagens.append({"role": "user", "content": PREFIXO_CONTEXTO_AGORA + (contexto or "nenhum")
                      + ("\n\n" + texto_novo if texto_novo else "")})
    if mensagens[0]["role"] != "user":
        mensagens.insert(0, {"role": "user", "content": TEXTO_SEM_RESUMO})
    sistema = CHAT_SIMPLES_PROMPT.format(
        hoje=date.today().isoformat(), marcador=MARCADOR_PRECISA_FERRAMENTA,
        memorias=_texto_memorias(memorias),
    )
    try:
        _garantir_adapter_anthropic_legado()
        resp = core.chamar_ia(FUNCAO_CHAT_SIMPLES, mensagens, sistema=sistema,
                              contexto_fixo=texto_bloco_historico_fixo(contexto_fixo))
    except Exception:  # noqa: BLE001
        log.exception("chat: caminho simples falhou, seguindo no padrao")
        return None
    texto = (resp.texto or "").strip()
    if not resp.ok or not texto or MARCADOR_PRECISA_FERRAMENTA in texto:
        return None
    return texto, [], {
        "model": resp.modelo,
        "input_tokens": resp.tokens_in,
        "output_tokens": resp.tokens_out,
        "cache_read_input_tokens": resp.tokens_cache_lido,
        "cache_creation_input_tokens": resp.tokens_cache_escrito,
        "cost_usd": resp.custo_usd,
    }


# Fase 7 (C1): opcoes da chamada atual do chat (contexto_fixo/conn/medir_uso)
# que o app liga sem mudar a chamada posicional de 4 argumentos - dezenas de
# dubles de teste (patch("claude_client.chat", side_effect=fake(m, c, mem, ex)))
# tem essa assinatura fixa, entao o app nao pode passar kwargs novos. Um
# kwarg passado explicitamente sempre ganha do valor daqui.
_OPCOES_CHAT: contextvars.ContextVar = contextvars.ContextVar("opcoes_chat", default=None)


@contextlib.contextmanager
def opcoes_chat(*, contexto_fixo: str = "", conn=None, medir_uso: bool = False):
    """`with opcoes_chat(contexto_fixo=..., conn=conn, medir_uso=True):
    chat(mensagens, contexto, memorias, executores)` == passar os 3 kwargs."""
    token = _OPCOES_CHAT.set({"contexto_fixo": contexto_fixo, "conn": conn, "medir_uso": medir_uso})
    try:
        yield
    finally:
        _OPCOES_CHAT.reset(token)


def chat(
    historico: list[dict], contexto: str, memorias: list[str], executores: dict,
    *, contexto_fixo: str | None = None, conn=None, medir_uso: bool | None = None,
) -> tuple[str, list[str], dict]:
    """Roda o loop de tool-use: manda o historico + ferramentas, se a IA
    pedir pra usar uma ferramenta, chama o executor correspondente (que
    mexe no banco, em app.py) e devolve o resultado pra IA continuar, ate
    ela responder so com texto (ou ate um limite de rodadas, pra nunca
    ficar preso num loop).

    Fase 7 (A6), tudo opcional e compativel com a chamada antiga:
    - contexto_fixo: resumo da A5 (ia.historico.montar_contexto) - vira o
      bloco fixo cacheado no inicio das mensagens.
    - conn: repassada pro roteador (ia.roteador_chat) consultar padroes.
    - medir_uso: True = consulta ia.teto.teto_permite("chat") antes e grava
      cada rodada em uso_ia (ia.medicao.registrar_uso). Padrao False pra nao
      gravar no banco em quem chama sem conn (testes antigos); o app liga
      (via opcoes_chat, ver acima)."""
    opcoes = _OPCOES_CHAT.get() or {}
    if contexto_fixo is None:
        contexto_fixo = opcoes.get("contexto_fixo") or ""
    if conn is None:
        conn = opcoes.get("conn")
    if medir_uso is None:
        medir_uso = bool(opcoes.get("medir_uso", False))
    estaveis, nova = _separar_nova(historico)
    mensagem_nova = _texto_de(nova.get("content")) if nova else ""
    rota = _decidir_rota(mensagem_nova, estaveis, conn)
    # "local": o app ja tentou classificador_local/_plano_local_chat antes de
    # chegar aqui e nao resolveu - entao aqui segue como "padrao".
    if rota == "luna":
        simples = _responder_simples(historico, contexto, memorias, contexto_fixo)
        if simples is not None:
            return simples

    config = _config_ia(FUNCAO_CHAT)
    modelo = _modelo_chat(config)
    max_tokens = config["max_tokens_saida"] if config else MAX_TOKENS_CHAT_PADRAO
    controle = _cache_control(config)
    ttl = (controle or {}).get("ttl", "5m")
    usage_total = {
        "model": modelo, "input_tokens": 0, "output_tokens": 0,
        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "cost_usd": 0.0,
    }

    if medir_uso and not _teto_permite(FUNCAO_CHAT):
        return _mensagem_teto(), [], usage_total

    system = montar_sistema_chat(memorias)
    tools = _tools_com_cache(controle)
    mensagens = montar_mensagens_chat(historico, contexto, contexto_fixo, controle)
    rolante = mensagens[-1]["content"][-1] if controle else None
    acoes: list[str] = []

    def rodada(limite: int):
        inicio = time.monotonic()
        response = client.messages.create(
            model=modelo,
            max_tokens=limite,
            system=system,
            tools=tools,
            messages=mensagens,
        )
        uso = _uso_da_resposta(response, modelo, ttl)
        for chave in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                      "cache_creation_input_tokens", "cost_usd"):
            usage_total[chave] += uso[chave]
        if medir_uso:
            _registrar_uso(FUNCAO_CHAT, uso["model"], uso, int((time.monotonic() - inicio) * 1000))
        return response

    for _ in range(RODADAS_MAX):
        response = rodada(max_tokens)
        if response.stop_reason == "max_tokens" and max_tokens < MAX_TOKENS_CHAT_ESCALADO:
            # cortou no limite novo: refaz a rodada com o teto antigo (1x)
            response = rodada(MAX_TOKENS_CHAT_ESCALADO)

        if response.stop_reason != "tool_use":
            texto = "".join(b.text for b in response.content if b.type == "text").strip()
            return texto or "Beleza.", acoes, usage_total

        mensagens.append({"role": "assistant", "content": response.content})
        resultados = []
        for bloco in response.content:
            if bloco.type != "tool_use":
                continue
            executor = executores.get(bloco.name)
            resultado = executor(bloco.input) if executor else {"erro": "ferramenta desconhecida"}
            if executor:
                acoes.append(bloco.name)
            resultados.append(
                {
                    "type": "tool_result",
                    "tool_use_id": bloco.id,
                    "content": json.dumps(resultado, ensure_ascii=False),
                }
            )
        mensagens.append({"role": "user", "content": resultados})
        # breakpoint rolante: sai do bloco anterior e vai pro ultimo
        # tool_result, pra rodada seguinte ler o loop inteiro do cache
        if controle and resultados:
            if isinstance(rolante, dict):
                rolante.pop("cache_control", None)
            rolante = resultados[-1]
            rolante["cache_control"] = dict(controle)

    return (
        "Isso ficou complicado demais pra eu processar de uma vez - tenta pedir uma coisa por vez.",
        acoes,
        usage_total,
    )


# ---------------------------------------------------------------------------
# Funcoes sem tools: passam por ia.core.chamar_ia (config em ia/config.d/)
# ---------------------------------------------------------------------------


class FalhaIA(anthropic.APIError):
    """Resposta(ok=False) de chamar_ia (rede, provedor, teto) vira isto -
    subclasse de anthropic.APIError pra app._call_claude continuar
    devolvendo CLAUDE_ERROR_MSG (502) igual antes."""

    def __init__(self, mensagem: str):
        super().__init__(mensagem, None, body=None)


def _garantir_adapter_anthropic_legado() -> None:
    """Faz o adapter "anthropic" do ia.core usar o MESMO cliente do resto do
    app (ia.legado.client == claude_client.client), se ninguem registrou outro
    adapter antes (ex.: dubles de teste de outras faixas). Motivo: um cliente
    so no processo, e os testes/guardas que fazem
    patch.object(claude_client.client.messages, "create") continuam cobrindo
    tambem estas chamadas (nenhuma chamada real escapa). Em producao e
    equivalente (mesma ANTHROPIC_API_KEY)."""
    try:
        from ia.adapters.anthropic import AdapterAnthropic
    except ImportError:
        return
    with core._TRAVA:
        ja_registrado = "anthropic" in core._FABRICAS_REGISTRADAS
    if not ja_registrado:
        core.registrar_adapter("anthropic", lambda: AdapterAnthropic(client=legado.client))


MAX_TOKENS_JSON_PADRAO = 600  # limite antigo, se a config estiver quebrada


def _chamar_json(funcao: str, conteudo: str) -> tuple[dict, dict]:
    """Chamada sem tools que devolve JSON (decisao, mensagem dificil).

    - config `ativo: true` -> ia.core.chamar_ia (alvo + fallback, teto e
      medicao em uso_ia pelo proprio nucleo).
    - config `ativo: false` (padrao) -> o MESMO caminho de hoje (SDK direto
      no modelo_atual), so que com o limite de saida da config (700/500).
      Motivo: chamar_ia sempre consulta o teto e grava uso_ia no banco de
      db.DB_PATH; os testes antigos que chamam estas funcoes com o cliente
      mockado (tests/test_claude_client.py) nao isolam o banco - pelo nucleo
      eles quebrariam (tabela ausente) ou, rodados no checkout principal,
      gravariam uso falso no banco real. Ver progress.txt/APRENDIZADOS."""
    config = _config_ia(funcao)
    if not (config and config["ativo"]):
        # Fase 7 (C1): o caminho direto tambem respeita o teto unico
        # (ia/teto.py) e grava em uso_ia - sem isso estas 2 funcoes ficavam
        # fora do gasto do mes (fonte unica = ia.medicao.gasto_mes_atual).
        if not _teto_permite(funcao):
            raise core.TetoEstourado(f"{funcao}: {core.ERRO_TETO}")
        atual = config["modelo_atual"] if config else {"provedor": "anthropic", "modelo": SONNET}
        modelo = atual["modelo"] if atual["provedor"] == "anthropic" else SONNET
        inicio = time.monotonic()
        response = client.messages.create(
            model=modelo,
            max_tokens=config["max_tokens_saida"] if config else MAX_TOKENS_JSON_PADRAO,
            messages=[{"role": "user", "content": conteudo}],
        )
        uso = _uso_da_resposta(response, modelo, "5m")
        _registrar_uso(funcao, uso["model"], uso, int((time.monotonic() - inicio) * 1000))
        return _extract_json(response.content[0].text), _usage(response)

    _garantir_adapter_anthropic_legado()
    resp = core.chamar_ia(funcao, [{"role": "user", "content": conteudo}])
    if not resp.ok:
        # C1: teto -> core.TetoEstourado; rede/provedor -> core.ErroProvedor
        # (app._call_claude traduz em TETO_IA_MSG/CLAUDE_ERROR_MSG).
        raise core.excecao_de_resposta(funcao, resp)
    dados = _extract_json(resp.texto or "")
    return dados, {
        "model": resp.modelo,
        "input_tokens": resp.tokens_in,
        "output_tokens": resp.tokens_out,
        "cost_usd": resp.custo_usd,
    }


DECISAO_PROMPT = """Ajude a decidir rapido se vale a pena. A pessoa tem TDAH e quer clareza, nao
um texto longo. Seja honesto: se a informacao e pouca, diga o que falta saber em vez de inventar.
Termine sempre com uma inclinacao direta e explicita (nunca deixe em aberto sem se posicionar).

Se envolver a construtora dele: nunca invente nem repita valor em R$ especifico (faturamento,
caixa, conta a pagar) - esses numeros moram so no financeiro-construtora, sistema separado; fale
em termos qualitativos (etapa, prazo, decisao). Se for decisao de negocio relevante (nao
operacional do dia a dia), pode mencionar que normalmente passa por alinhamento com o pai e o
socio dele na empresa - so quando isso realmente pesar na resposta, sem repetir sempre.

Coisas que voce sabe sobre a pessoa (use so se ajudar):
{memorias}

Decisao: {pergunta}

Responda SO com JSON, sem markdown:
{{"resumo": "<1 frase reformulando a decisao>",
  "pros": ["<ate 4, curtos>"],
  "contras": ["<ate 4, curtos>"],
  "perguntas_chave": ["<ate 3 perguntas que mudariam a resposta>"],
  "inclinacao": "<'vale', 'nao_vale' ou 'depende'>",
  "porque": "<1 frase>"}}"""


def analisar_decisao(pergunta: str, memorias: list[str] | None = None) -> tuple[dict, dict]:
    """Card "vale a pena?". Fase 7 (A6): config em
    ia/config.d/analisar_decisao.json (limite 700; ver _chamar_json)."""
    conteudo = DECISAO_PROMPT.format(pergunta=pergunta, memorias=_texto_memorias(memorias, "nenhuma"))
    return _chamar_json(FUNCAO_DECISAO, conteudo)


MENSAGEM_DIFICIL_PROMPT = """Ajude a escrever uma mensagem dificil (cobrar alguem, dizer nao, pedir
desculpa, resolver conflito). A pessoa tem TDAH e trava pra comecar - entregue a mensagem pronta
pra copiar, em portugues do Brasil, curta, respeitosa e clara. Nada de formalidade excessiva.

Pra quem: {para_quem}
Situacao: {situacao}

Responda SO com JSON, sem markdown:
{{"direta": "<versao objetiva>", "gentil": "<versao mais suave, mesma mensagem>"}}"""


def redigir_mensagem_dificil(situacao: str, para_quem: str | None) -> tuple[dict, dict]:
    """Fase 7 (A6): config em ia/config.d/redigir_mensagem_dificil.json
    (limite 500; ver _chamar_json)."""
    conteudo = MENSAGEM_DIFICIL_PROMPT.format(situacao=situacao, para_quem=para_quem or "nao informado")
    return _chamar_json(FUNCAO_MENSAGEM_DIFICIL, conteudo)


# ---------------------------------------------------------------------------
# Data relativa -> data absoluta EM CODIGO (docs/calculos.md, secao 1.2/1.3)
# ---------------------------------------------------------------------------
#
# Hoje o modelo preenche `quando_data` de `registrar_tarefa` fazendo a conta
# de calendario sozinho ("amanha", "sexta", "daqui 6 meses"). O certo e o
# modelo devolver so a pista em texto (`quando`) e o codigo resolver a data.
# `resolver_data_relativa` e esse resolvedor; `resolver_quando_data` e o que o
# executor do app.py deve chamar (ver scripts/ralph-a6-chat/progress.txt).
#
# Regras (texto normalizado: minusculo, sem acento, sem "-feira"):
#   AAAA-MM-DD, DD/MM, DD/MM/AA(AA), "15 de outubro [de 2026]"  -> data dita
#       (sem ano: este ano, ou o proximo se ja passou)
#   "hoje"/"hj"/"agora" -> hoje | "amanha" -> +1 | "depois de amanha" -> +2
#   "daqui a/em/dentro de N dia(s)|semana(s)|mes(es)|ano(s)" (N em numero ou
#       por extenso: um, dois, ..., dez, quinze, vinte, trinta) -> soma;
#       mes/ano somam no calendario (31/01 + 1 mes = 28 ou 29/02)
#   "dia 15" -> dia 15 deste mes, ou do proximo se ja passou
#   "fim/final do mes" -> ultimo dia do mes | "fim/final do ano" -> 31/12
#   dia da semana ("sexta", "proxima sexta", "sexta que vem") -> a PROXIMA
#       ocorrencia depois de hoje (1 a 7 dias; "sexta" dito numa sexta = a
#       sexta seguinte - pra hoje o Alex diz "hoje");
#       "<dia> da semana que vem"/"<dia> da proxima semana" -> aquele dia na
#       semana seguinte (segunda a domingo)
#   Vago ("essa semana", "semana que vem" sozinho, "mes que vem", "quando
#   der", "algum dia", "fim de semana") ou data impossivel (31/02) -> None.

_DIAS_SEMANA = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
_NUMEROS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "quinze": 15,
    "vinte": 20, "trinta": 30,
}
# Nada alem de ~10 anos pra frente (evita overflow e data absurda vinda de "em 99999 dias").
_LIMITE_DIAS = 3660
_LIMITE_TEXTO = 300
_INVALIDA = object()

_RE_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_RE_BARRA = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?\b")
_RE_MES_EXTENSO = re.compile(r"\b(\d{1,2}) de (" + "|".join(_MESES) + r")(?: de (\d{4}))?\b")
_RE_QUANTIDADE = re.compile(
    r"\b(?:daqui a|daqui|em|dentro de)\s+(\d{1,4}|" + "|".join(_NUMEROS) + r")\s+"
    r"(dias?|semanas?|mes|meses|anos?)\b"
)
_RE_DIA_SOLTO = re.compile(r"\bdia (\d{1,2})\b")
_RE_DIA_SEMANA = re.compile(r"\b(" + "|".join(_DIAS_SEMANA) + r")\b")
_RE_SEMANA_QUE_VEM = re.compile(r"\b(?:semana que vem|proxima semana)\b")


def _normalizar_data_texto(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    t = sem_acento.lower().replace("-feira", "").replace(" feira", "")
    return re.sub(r"\s+", " ", t).strip()


def _como_hoje(hoje) -> date:
    if isinstance(hoje, datetime):
        return hoje.date()
    if isinstance(hoje, date):
        return hoje
    if isinstance(hoje, str):
        return date.fromisoformat(hoje.strip())
    raise ValueError(f"hoje invalido: {hoje!r}")


def _data_ou_invalida(ano: int, mes: int, dia: int):
    try:
        return date(ano, mes, dia)
    except ValueError:
        return _INVALIDA


def _somar_meses(base: date, meses: int) -> date:
    total = base.month - 1 + meses
    ano, mes = base.year + total // 12, total % 12 + 1
    return date(ano, mes, min(base.day, monthrange(ano, mes)[1]))


def _regra_data_explicita(t: str, hoje: date):
    m = _RE_ISO.search(t)
    if m:
        return _data_ou_invalida(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _RE_BARRA.search(t)
    if m:
        dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
        if ano:
            ano_int = int(ano) + (2000 if len(ano) == 2 else 0)
            return _data_ou_invalida(ano_int, mes, dia)
        d = _data_ou_invalida(hoje.year, mes, dia)
        if d is not _INVALIDA and d < hoje:
            d = _data_ou_invalida(hoje.year + 1, mes, dia)
        return d
    m = _RE_MES_EXTENSO.search(t)
    if m:
        dia, mes = int(m.group(1)), _MESES[m.group(2)]
        if m.group(3):
            return _data_ou_invalida(int(m.group(3)), mes, dia)
        d = _data_ou_invalida(hoje.year, mes, dia)
        if d is not _INVALIDA and d < hoje:
            d = _data_ou_invalida(hoje.year + 1, mes, dia)
        return d
    return None


def _regra_palavra(t: str, hoje: date):
    if re.search(r"\bdepois de amanha\b", t):
        return hoje + timedelta(days=2)
    if re.search(r"\bamanha\b", t):
        return hoje + timedelta(days=1)
    if re.search(r"\b(?:hoje|hj|agora)\b", t):
        return hoje
    return None


def _regra_quantidade(t: str, hoje: date):
    m = _RE_QUANTIDADE.search(t)
    if not m:
        return None
    bruto, unidade = m.group(1), m.group(2)
    n = int(bruto) if bruto.isdigit() else _NUMEROS[bruto]
    if unidade.startswith("dia"):
        dias = n
    elif unidade.startswith("semana"):
        dias = 7 * n
    else:
        meses = n if unidade.startswith("mes") else 12 * n
        if meses * 31 > _LIMITE_DIAS:
            return _INVALIDA
        return _somar_meses(hoje, meses)
    if dias > _LIMITE_DIAS:
        return _INVALIDA
    return hoje + timedelta(days=dias)


def _regra_dia_solto(t: str, hoje: date):
    m = _RE_DIA_SOLTO.search(t)
    if not m:
        return None
    dia = int(m.group(1))
    d = _data_ou_invalida(hoje.year, hoje.month, dia)
    if d is not _INVALIDA and d >= hoje:
        return d
    proximo = _somar_meses(hoje.replace(day=1), 1)
    return _data_ou_invalida(proximo.year, proximo.month, dia)


def _regra_fim(t: str, hoje: date):
    if re.search(r"\b(?:fim|final) do mes\b", t):
        return hoje.replace(day=monthrange(hoje.year, hoje.month)[1])
    if re.search(r"\b(?:fim|final) do ano\b", t):
        return date(hoje.year, 12, 31)
    return None


def _regra_dia_semana(t: str, hoje: date):
    m = _RE_DIA_SEMANA.search(t)
    if not m:
        return None
    alvo = _DIAS_SEMANA[m.group(1)]
    if _RE_SEMANA_QUE_VEM.search(t):
        segunda_que_vem = hoje + timedelta(days=7 - hoje.weekday())
        return segunda_que_vem + timedelta(days=alvo)
    return hoje + timedelta(days=(alvo - hoje.weekday() - 1) % 7 + 1)


_REGRAS_DATA = (
    _regra_data_explicita,
    _regra_palavra,
    _regra_quantidade,
    _regra_dia_solto,
    _regra_fim,
    _regra_dia_semana,
)


def resolver_data_relativa(texto, hoje) -> date | None:
    """Resolve a pista de prazo em texto livre ("amanha", "sexta que vem",
    "daqui 6 meses", "15/10") pra uma data absoluta, a partir de `hoje`
    (date, datetime ou "AAAA-MM-DD"). Vago, impossivel ou nao reconhecido ->
    None (nunca chuta). Deterministico: mesma entrada, mesma saida. `hoje`
    invalido levanta ValueError (erro de programacao)."""
    hoje = _como_hoje(hoje)
    if not isinstance(texto, str):
        return None
    t = _normalizar_data_texto(texto)
    if not t or len(t) > _LIMITE_TEXTO:
        return None
    for regra in _REGRAS_DATA:
        try:
            resultado = regra(t, hoje)
        except (ValueError, OverflowError):
            return None
        if resultado is _INVALIDA:
            return None
        if resultado is not None:
            return resultado
    return None


def resolver_quando_data(entrada, hoje=None) -> str | None:
    """`due_date` (AAAA-MM-DD) de uma tarefa do tool `registrar_tarefa`,
    resolvida em codigo. Ordem: (1) pista `quando` resolvida por
    resolver_data_relativa; (2) transicao: `quando_data` que o modelo ainda
    manda, se for uma data valida; (3) regra do tool: `hora` sem nenhuma
    referencia de dia = hoje. Nada disso -> None (tarefa sem data)."""
    if not isinstance(entrada, dict):
        return None
    hoje = _como_hoje(hoje or date.today())
    quando = entrada.get("quando")
    if isinstance(quando, str) and quando.strip():
        resolvida = resolver_data_relativa(quando, hoje)
        if resolvida is not None:
            return resolvida.isoformat()
    do_modelo = entrada.get("quando_data")
    if isinstance(do_modelo, str):
        try:
            return date.fromisoformat(do_modelo.strip()).isoformat()
        except ValueError:
            pass
    if not (isinstance(quando, str) and quando.strip()) and entrada.get("hora"):
        return hoje.isoformat()
    return None
