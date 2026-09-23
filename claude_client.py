import base64
import json
import os
from datetime import date, datetime

from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-5"

# USD por 1M tokens (input, output)
PRICING = {
    HAIKU: (1.00, 5.00),
    SONNET: (2.00, 10.00),
}

CAPTURE_PROMPT = """Hoje e {hoje}. Classifique o texto do usuario como "tarefa", "gasto" ou "meta"
(meta financeira, tipo "quero juntar X ate Y" ou "economizar pra comprar Z") e extraia os campos.
Responda so com JSON, sem markdown, no formato:
{{"tipo": "tarefa" ou "gasto" ou "meta", "titulo": "...", "valor": numero ou null, "categoria": "..." ou null, "status": "real" ou "planejado" ou null, "quando": "..." ou null, "quando_data": "AAAA-MM-DD" ou null, "hora": "HH:MM" ou null, "prazo": "AAAA-MM-DD" ou null, "duvida": "..." ou null, "memoria": "..." ou null}}

Categorias de gasto: mercado, transporte, lazer, contas, saude, outros.

Se tipo="gasto": "status" e "real" quando o gasto ja aconteceu (ex: "gastei", "paguei",
"comprei", verbo no passado) e "planejado" quando e so uma possibilidade/intencao futura ainda
nao decidida (ex: "penso em comprar", "quero gastar", "talvez eu compre", "tô pensando em").
Na duvida, use "real" (e o caso mais comum). Deixe null se tipo nao for "gasto".

Se tipo="tarefa": "quando" e o prazo em texto livre, do jeito que a pessoa escreveu (ex:
"amanha", "sexta que vem"). "quando_data" e a MESMA informacao convertida pra AAAA-MM-DD, so
quando der pra calcular uma data concreta a partir de hoje ({hoje}) - se o texto nao tiver prazo
nenhum ou for vago demais pra virar data (tipo "quando der", "algum dia"), deixe "quando_data"
como null mesmo que "quando" tenha texto.

"hora" e o horario do compromisso em HH:MM (24h), SO quando o texto disser um horario especifico
tipo "as 14h", "as 22 horas", "9 da manha", "2 da tarde" - converta pra 24h (2 da tarde = 14:00).
Se houver "hora" mas nenhuma referencia de dia no texto (nem "hoje" nem outra data), assuma que
e hoje e preencha "quando_data" com {hoje} mesmo assim - uma pessoa que diz "tenho consulta as
14h" sem mais contexto normalmente esta falando de hoje. Se o texto nao mencionar horario
nenhum, deixe "hora" como null.

Se tipo="meta": "valor" e o valor total que a pessoa quer juntar, e "prazo" e a data limite no
formato AAAA-MM-DD - calcule a partir de hoje ({hoje}) se o texto disser algo relativo tipo
"ate dezembro" ou "em 6 meses". Se nao houver prazo claro no texto, deixe "prazo" como null.

Preencha "duvida" APENAS se o texto for realmente ambiguo demais pra classificar com confianca
(ex: nao da pra saber se e tarefa, gasto ou meta, ou um gasto/meta sem valor nenhum). Nesse caso
"duvida" deve ser uma pergunta curta e direta pra esclarecer, e os outros campos podem vir com o
melhor palpite. Se o texto for razoavelmente claro, deixe "duvida" como null - nao pergunte por
excesso de zelo.

Preencha "memoria" APENAS se o texto revelar um fato duravel sobre a pessoa que vale lembrar em
conversas futuras e que NAO e so o proprio item classificado - por exemplo uma preferencia
("prefere economizar pra viagem mais que pra moto"), rotina ("trabalha home office as quartas"),
relacao ("esposa se chama Ana") ou contexto recorrente. Escreva em terceira pessoa, uma frase
curta. Se o texto for so uma tarefa/gasto/meta pontual sem nada duravel por tras, deixe "memoria"
como null - a grande maioria dos textos nao tem nada pra lembrar aqui.

Aprendizado de correcao anterior (o Alex ja corrigiu manualmente uma captura parecida com essa no
passado, porque a classificacao automatica saiu errada) - use como pista forte de qual e o tipo/
categoria certos, mas ainda julgue pelo texto atual, o padrao pode nao se repetir sempre:
{contexto_correcao}

Texto: {text}"""

BREAKDOWN_PROMPT = """Quebre esta tarefa em 3 a 6 passos pequenos e concretos, cada um algo que da pra fazer de uma vez.
Responda so com um JSON de lista de strings, sem markdown.

Tarefa: {title}"""

SUMMARY_PROMPT = """Escreva um resumo do dia em 2 a 3 frases. Tom neutro e factual, sem cobranca e sem elogio vazio.
Se houver compromissos na agenda, mencione quantos tem e se o dia esta cheio ou tranquilo -
sem repetir cada horario, so o suficiente pra dar uma nocao geral.

Coisas duraveis que voce sabe sobre a pessoa (use so se for relevante pro resumo, nao force):
{memorias}

Contexto de saude de hoje (mencione so se for notavel, tipo bem abaixo/acima da media - senao ignore):
{saude}

Resumo financeiro da construtora do Alex (mencione so se fizer sentido, nao force - isso e o
negocio dele, nao gasto pessoal):
{construtora}

Previsao de chuva hoje (mencione so se houver risco de chuva e parecer relevante pro dia - por
exemplo se tiver compromisso que pode ser afetado por chuva; se nao houver risco, ignore):
{clima}

Tarefas concluidas: {done}
Tarefas pendentes: {pending}
Gastos de hoje: {expenses}
Compromissos na agenda hoje: {eventos}"""

CHAT_SYSTEM_PROMPT = """Voce e o assistente pessoal do Alex, dentro do painel pessoal dele
(um app que so ele usa). Hoje e {hoje}. Ele tem TDAH - seja direto e curto, sem enrolacao, tom
de colega que ajuda e nao de atendente corporativo. Sem emoji em excesso.

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

Quando o Alex perguntar se "vale a pena" algo (compra, negociacao, escolha), responda em formato
curto e organizado: uma linha com a decisao, "Pros:" e "Contras:" em listas de ate 4 itens, as
perguntas que mudariam a resposta (se faltar informacao importante), e uma inclinacao honesta
(vale / nao vale / depende de X). Nada de texto longo.

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
academia hoje?"), chame `sugerir_horario_livre` em vez de adivinhar - ela olha o que ja esta
marcado no dia de verdade e acha o maior espaco livre.

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

Contexto de agora:
{contexto}

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
]


def chat(
    historico: list[dict], contexto: str, memorias: list[str], executores: dict
) -> tuple[str, list[str], dict]:
    """Roda o loop de tool-use: manda o historico + ferramentas, se a IA
    pedir pra usar uma ferramenta, chama o executor correspondente (que
    mexe no banco, em app.py) e devolve o resultado pra IA continuar, ate
    ela responder so com texto (ou ate um limite de rodadas, pra nunca
    ficar preso num loop)."""
    system = CHAT_SYSTEM_PROMPT.format(
        hoje=date.today().isoformat(),
        contexto=contexto,
        memorias="\n".join(f"- {m}" for m in memorias) or "nenhuma ainda",
    )
    mensagens = list(historico)
    acoes: list[str] = []
    usage_total = {"model": SONNET, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    for _ in range(4):
        response = client.messages.create(
            model=SONNET,
            max_tokens=600,
            system=system,
            tools=CHAT_TOOLS,
            messages=mensagens,
        )
        u = _usage(response)
        usage_total["input_tokens"] += u["input_tokens"]
        usage_total["output_tokens"] += u["output_tokens"]
        usage_total["cost_usd"] += u["cost_usd"]

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

    return (
        "Isso ficou complicado demais pra eu processar de uma vez - tenta pedir uma coisa por vez.",
        acoes,
        usage_total,
    )


PLANO_PROMPT = """Voce ajuda uma pessoa com TDAH a organizar o resto do dia. Agora sao {agora}.

Os compromissos da agenda abaixo tem horario FIXO e nao podem mudar - use como ancoras.
As tarefas pendentes NAO tem horario marcado - sugira em que ordem encaixa-las ao longo do
dia (antes, entre ou depois dos compromissos), pensando em coisas como: tarefa rapida
antes de sair de casa, tarefa que depende de estar em algum lugar perto de um compromisso
que ja leva pra la, tarefa urgente primeiro se nao houver pista de prioridade.

Coisas duraveis que voce sabe sobre a pessoa (use so se ajudar a ordenar melhor, nao force):
{memorias}

Responda em lista numerada curta (maximo 6 itens), cada item uma linha, direto ao ponto.
Tom neutro, sem cobranca. Se nao houver tarefa nem compromisso nenhum, diga isso em uma frase.

Compromissos de hoje (hora fixa): {eventos}
Tarefas pendentes (sem hora fixa): {tarefas}"""


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def _usage(response) -> dict:
    input_price, output_price = PRICING[response.model]
    cost = (response.usage.input_tokens / 1_000_000) * input_price + (
        response.usage.output_tokens / 1_000_000
    ) * output_price
    return {
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd": cost,
    }


def classify_capture(text: str, contexto_correcao: str | None = None) -> tuple[dict, dict]:
    response = client.messages.create(
        model=HAIKU,
        max_tokens=250,
        messages=[
            {
                "role": "user",
                "content": CAPTURE_PROMPT.format(
                    text=text,
                    hoje=date.today().isoformat(),
                    contexto_correcao=contexto_correcao or "nenhuma correcao parecida no historico",
                ),
            }
        ],
    )
    return _extract_json(response.content[0].text), _usage(response)


def break_down_task(title: str) -> tuple[list[str], dict]:
    response = client.messages.create(
        model=SONNET,
        max_tokens=300,
        messages=[{"role": "user", "content": BREAKDOWN_PROMPT.format(title=title)}],
    )
    return _extract_json(response.content[0].text), _usage(response)


COTACAO_PDF_PROMPT = """Leia esse PDF de orcamento/cotacao de um fornecedor de material de
construcao e extraia em JSON:
{"fornecedor": nome da empresa/fornecedor (texto curto) ou null se nao identificar,
 "valor": valor TOTAL do orcamento em reais (numero puro, sem "R$" nem separador de milhar) ou
 null se nao achar um valor total claro, "prazo_texto": prazo de entrega mencionado, em texto
 livre (ex: "15 dias uteis") ou null, "observacao": um detalhe curto relevante (frete incluso,
 validade da proposta, forma de pagamento) ou null}

So extraia o que estiver escrito no documento - nunca estime ou arredonde um valor que nao
esteja explicito. Responda SO com o JSON, sem explicacao, sem markdown."""


def extrair_item_cotacao_pdf(pdf_bytes: bytes) -> tuple[dict, dict]:
    """Le um PDF de cotacao/orcamento de fornecedor e extrai fornecedor/valor/prazo -
    extracao pura (mesmo espirito de classify_capture: a IA so le e devolve estruturado,
    nunca decide nada sozinho, quem compara os valores depois e o Python)."""
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    response = client.messages.create(
        model=SONNET,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                    },
                    {"type": "text", "text": COTACAO_PDF_PROMPT},
                ],
            }
        ],
    )
    texto = "".join(b.text for b in response.content if b.type == "text")
    return _extract_json(texto), _usage(response)


NOTA_FISCAL_PROMPT = """Leia essa foto de nota fiscal/cupom fiscal e extraia em JSON:
{"valor": valor TOTAL da compra em reais (numero puro, sem "R$" nem separador de milhar) ou null
 se nao achar um valor total claro, "estabelecimento": nome do estabelecimento/loja (texto curto)
 ou null se nao identificar, "data": data da compra no formato "AAAA-MM-DD" ou null se nao achar
 uma data legivel}

So extraia o que estiver escrito na foto - nunca estime ou arredonde um valor que nao esteja
explicito, e nunca invente estabelecimento ou data que a foto nao mostre com clareza. Responda SO
com o JSON, sem explicacao, sem markdown."""

MEDIA_TYPES_IMAGEM_VALIDOS = {"image/jpeg", "image/png", "image/webp", "image/heic"}


def extrair_nota_fiscal_foto(image_bytes: bytes, media_type: str) -> tuple[dict, dict]:
    """Le uma foto de nota fiscal e extrai valor/estabelecimento/data - mesmo
    espirito de extrair_item_cotacao_pdf (extracao pura via API de visao da
    Anthropic, decisao ja tomada com o Alex pra nao usar OCR local/Tesseract):
    a IA so le a foto e devolve estruturado, nunca decide categoria nem
    grava nada sozinha - quem confirma e categoriza e o fluxo de gasto
    existente (US-C9)."""
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = client.messages.create(
        model=SONNET,
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                    },
                    {"type": "text", "text": NOTA_FISCAL_PROMPT},
                ],
            }
        ],
    )
    texto = "".join(b.text for b in response.content if b.type == "text")
    return _extract_json(texto), _usage(response)


def summarize_day(
    done: list[str],
    pending: list[str],
    expenses: list[dict],
    eventos: list[str] | None = None,
    memorias: list[str] | None = None,
    saude: str | None = None,
    construtora: str | None = None,
    clima: str | None = None,
) -> tuple[str, dict]:
    response = client.messages.create(
        model=HAIKU,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": SUMMARY_PROMPT.format(
                    done=done or "nenhuma",
                    pending=pending or "nenhuma",
                    expenses=expenses or "nenhum",
                    eventos=eventos or "nenhum (ou agenda nao conectada)",
                    memorias=memorias or "nenhuma ainda",
                    saude=saude or "sem dados de saude hoje",
                    construtora=construtora or "nao conectado",
                    clima=clima or "sem risco de chuva relevante (ou cidade padrao nao configurada)",
                ),
            }
        ],
    )
    return response.content[0].text.strip(), _usage(response)


def plano_do_dia(
    tarefas: list[str], eventos: list[dict], memorias: list[str] | None = None
) -> tuple[str, dict]:
    eventos_fmt = [
        f"{e['titulo']} as {e['inicio'][11:16]}" for e in eventos if not e.get("dia_inteiro")
    ]
    response = client.messages.create(
        model=SONNET,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": PLANO_PROMPT.format(
                    agora=datetime.now().strftime("%H:%M"),
                    eventos=eventos_fmt or "nenhum",
                    tarefas=tarefas or "nenhuma",
                    memorias=memorias or "nenhuma ainda",
                ),
            }
        ],
    )
    return response.content[0].text.strip(), _usage(response)


ESSENCIAL_PROMPT = """Voce ajuda uma pessoa com TDAH num dia corrido: das tarefas abaixo, escolha
as 1 a 3 MAIS importantes pra hoje (menos e melhor - se so uma importa de verdade, escolha uma).
Criterio: o que tem consequencia real se nao for feito hoje (prazo vencido ou vencendo, hora
marcada, algo que trava outra coisa). Rotina repetitiva (remedio, academia) raramente e a escolha,
ela ja tem lembrete proprio. Hoje e {hoje}.

Tarefas (id | titulo | prazo | hora):
{tarefas}

Responda SO com JSON, sem markdown: [{{"id": <id>, "motivo": "<ate 8 palavras, sem cobranca>"}}]"""


def escolher_essencial(tarefas: list[dict]) -> tuple[list[dict], dict]:
    linhas = "\n".join(
        f"{t['id']} | {t['title']} | {t.get('due_date') or 'sem prazo'} | {t.get('hora') or '-'}"
        for t in tarefas
    )
    response = client.messages.create(
        model=HAIKU,
        max_tokens=250,
        messages=[
            {
                "role": "user",
                "content": ESSENCIAL_PROMPT.format(hoje=date.today().isoformat(), tarefas=linhas),
            }
        ],
    )
    return _extract_json(response.content[0].text), _usage(response)


REQUEBRAR_PROMPT = """A tarefa abaixo esta travada ha {dias} dias - a pessoa tem TDAH e o jeito
que ela estava quebrada nao funcionou. Proponha um jeito DIFERENTE de atacar, em 3 a 5 passos.
O primeiro passo tem que ser ridiculamente facil, de 2 a 5 minutos (abrir o arquivo, mandar uma
mensagem de uma linha, separar o material) - o objetivo e so comecar. Sem repetir os passos
antigos do mesmo jeito.

Tarefa: {titulo}
Passos antigos que nao andaram: {passos}

Responda so com um JSON de lista de strings, sem markdown."""


def requebrar_tarefa(titulo: str, dias: int, passos_antigos: list[str]) -> tuple[list[str], dict]:
    response = client.messages.create(
        model=SONNET,
        max_tokens=350,
        messages=[
            {
                "role": "user",
                "content": REQUEBRAR_PROMPT.format(
                    titulo=titulo, dias=dias, passos="; ".join(passos_antigos) or "nenhum"
                ),
            }
        ],
    )
    return _extract_json(response.content[0].text), _usage(response)


DECISAO_PROMPT = """Ajude a decidir rapido se vale a pena. A pessoa tem TDAH e quer clareza, nao
um texto longo. Seja honesto: se a informacao e pouca, diga o que falta saber em vez de inventar.

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
    response = client.messages.create(
        model=SONNET,
        max_tokens=600,
        messages=[
            {
                "role": "user",
                "content": DECISAO_PROMPT.format(
                    pergunta=pergunta, memorias="\n".join(f"- {m}" for m in memorias or []) or "nenhuma"
                ),
            }
        ],
    )
    return _extract_json(response.content[0].text), _usage(response)


MALA_PROMPT = """Monte um checklist de mala CURTO e pratico pra uma viagem. A pessoa tem TDAH:
itens concretos, sem obviedade tipo "roupas" solto - diga quantidade quando fizer sentido.
Maximo 15 itens. Inclua documento se for voo/viagem longa.

Destino: {destino}
Dias: {dias}
Motivo: {motivo}
Clima previsto: {clima}

Responda so com um JSON de lista de strings, sem markdown."""


def gerar_mala(destino: str, dias: int, motivo: str | None, clima_texto: str | None) -> tuple[list[str], dict]:
    response = client.messages.create(
        model=HAIKU,
        max_tokens=400,
        messages=[
            {
                "role": "user",
                "content": MALA_PROMPT.format(
                    destino=destino, dias=dias, motivo=motivo or "nao informado", clima=clima_texto or "sem previsao"
                ),
            }
        ],
    )
    return _extract_json(response.content[0].text), _usage(response)


MENSAGEM_DIFICIL_PROMPT = """Ajude a escrever uma mensagem dificil (cobrar alguem, dizer nao, pedir
desculpa, resolver conflito). A pessoa tem TDAH e trava pra comecar - entregue a mensagem pronta
pra copiar, em portugues do Brasil, curta, respeitosa e clara. Nada de formalidade excessiva.

Pra quem: {para_quem}
Situacao: {situacao}

Responda SO com JSON, sem markdown:
{{"direta": "<versao objetiva>", "gentil": "<versao mais suave, mesma mensagem>"}}"""


def redigir_mensagem_dificil(situacao: str, para_quem: str | None) -> tuple[dict, dict]:
    response = client.messages.create(
        model=SONNET,
        max_tokens=600,
        messages=[
            {
                "role": "user",
                "content": MENSAGEM_DIFICIL_PROMPT.format(
                    situacao=situacao, para_quem=para_quem or "nao informado"
                ),
            }
        ],
    )
    return _extract_json(response.content[0].text), _usage(response)


RESUMO_LINK_PROMPT = """Resuma pra uma pessoa com TDAH decidir se vale ler/ver agora: 3 a 5
pontos curtos com o que importa de verdade, em portugues do Brasil. Se o texto for so pagina de
login/cookie/erro sem conteudo, diga isso numa frase. Nao invente o que nao esta no texto.

Titulo: {titulo}
Texto (pode estar cortado):
{texto}

Responda so com o resumo em topicos comecando com "- ", sem introducao."""


def resumir_link(titulo: str | None, texto: str) -> tuple[str, dict]:
    response = client.messages.create(
        model=HAIKU,
        max_tokens=400,
        messages=[{"role": "user", "content": RESUMO_LINK_PROMPT.format(titulo=titulo or "sem titulo", texto=texto)}],
    )
    return response.content[0].text.strip(), _usage(response)
