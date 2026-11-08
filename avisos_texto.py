"""avisos_texto.py - catalogo de textos dos avisos (leva 07/11/2026, frente C,
docs/briefings/2026-11-07-lugar-certo-e-avisos.md).

Estilo C "Amigo" (voto do Alex em 06/11): "tu", leve, sem cobranca, 1 emoji por assunto no titulo
(o emoji entra na hora de mandar, `notificacoes.com_emoji`; aqui o texto vem SEM emoji). Titulo cabe em
1 linha da tela bloqueada (TITULO_LIM) e o corpo em 2 (CORPO_LIM).

NUNCA reduz a quantidade de avisos (TDAH, eles ajudam): este modulo so troca o JEITO de falar, pra o aviso
nao virar paisagem. Cada assunto tem de 4 a 8 variacoes; a escolha:
  - so variacao cujos dados existem (template com {trajeto} so quando tem trajeto) e que cabe nos limites;
  - condicao de contexto: as "fortes" (chuva, atrasado, sequencia...) ganham prioridade quando valem; as de
    hora do dia (manha/tarde/noite/fim_de_semana) so filtram;
  - nunca a mesma da ultima vez que aquele assunto saiu (memoria em `configuracoes`, chave MEMORIA);
  - o MESMO aviso (mesma `chave`, ex. "tarefa_horario-12-2026-11-07") sempre ganha o mesmo texto - o app
    sincroniza a cada poucos minutos e o servidor manda o mesmo aviso pelo navegador, o texto nao pode
    mudar a cada sincronizada;
  - a 1a vez de um assunto (sem memoria nenhuma) e o texto classico (variacao 0) - o que ja era antes.
Sem `conn` (teste antigo, chamada pura) = sempre a variacao 0, igual ao texto de antes desta leva.

Frente D (07/11, "ta aberto?"): `lugar_fechado(conn, lugar, chegada, fecha=..., abre=..., temporario=...)`
devolve (titulo, corpo) do aviso `lugar_fechado`; quem entrega e `avisos_pendentes.entregar(...)`.
"""
from __future__ import annotations

import json
import random
import string
from datetime import datetime

MEMORIA = "avisos_texto_memoria"
TITULO_LIM = 40  # sem o emoji; ~1 linha da tela bloqueada
CORPO_LIM = 90  # ~2 linhas da tela bloqueada
CHAVES_POR_ASSUNTO = 40
NOME_LIM = 26  # nome de tarefa/lugar dentro do texto

# condicoes: as fortes ganham prioridade; as de hora so filtram
FORTES = {"chuva", "sequencia", "repeticao", "pouco_tempo"}


def _v(corpo=None, titulo=None, se=None):
    return {"corpo": corpo, "titulo": titulo, "se": se}


# Cada assunto: tipo (o aviso de verdade, pro emoji), nome (pra tela de veto), exemplo (dados inventados pro
# artefato/teste) e as variacoes. titulo None = fica o titulo que veio (nome da tarefa); corpo None = fica o
# corpo que veio (montado em outro lugar, ex. voo).
CATALOGO: dict[str, dict] = {
    # ------------------------------------------------------------ tarefa com hora (titulo = a tarefa)
    "tarefa_preparo": {
        "tipo": "tarefa_preparo", "nome": "Tarefa daqui a ~30 min",
        "exemplo": {"titulo_padrao": "Pagar a fatura", "hora": "15:00", "falta": 30},
        "variacoes": [
            _v("Às {hora}, faltam {falta} min. Dá pra fechar o que tá fazendo com calma."),
            _v("Faltam {falta} min pras {hora}. Vai encerrando aos poucos."),
            _v("{hora} tá chegando, {falta} min ainda. Sem pressa, só vai se ajeitando."),
            _v("Às {hora} é essa. Ainda tem {falta} min pra terminar o que tá fazendo."),
            _v("Manhã andando: às {hora} vem essa, faltam {falta} min.", se="manha"),
            _v("Faltam {falta} min pras {hora}. Fecha essa e a noite fica leve.", se="noite"),
            _v("Tu tá numa boa sequência hoje. Às {hora} vem essa, faltam {falta} min.", se="sequencia"),
        ],
    },
    "tarefa_horario": {
        "tipo": "tarefa_horario", "nome": "Tarefa daqui a pouco (~10 min)",
        "exemplo": {"titulo_padrao": "Pagar a fatura", "hora": "15:00"},
        "variacoes": [
            _v("Daqui a pouco, às {hora}. Vai fechando o que tá fazendo, sem correr."),
            _v("Às {hora} é essa. Termina a frase, salva e vai."),
            _v("{hora} tá logo ali. Bora deixar o resto pra depois."),
            _v("Quase {hora}. Respira, levanta e começa."),
            _v("Às {hora}. Dá tempo de um gole d'água antes de começar."),
            _v("Mais uma pra tua sequência: às {hora}. Tá indo bem.", se="sequencia"),
        ],
    },
    "tarefa_na_hora": {
        "tipo": "tarefa_horario", "nome": "Tarefa: chegou/passou da hora (servidor)",
        "exemplo": {"titulo_padrao": "Pagar a fatura", "hora": "15:00"},
        "variacoes": [
            _v("Combinamos {hora}. Quando fizer, toca em Feito."),
            _v("Era às {hora}. Ainda dá, e quando terminar toca em Feito."),
            _v("Passou um pouquinho das {hora}. Começa pelo primeiro passo."),
            _v("{hora} já foi, mas sem drama. Faz agora e marca Feito."),
        ],
    },
    "tarefa_agora": {
        "tipo": "tarefa_agora", "nome": "Tarefa na hora exata (app)",
        "exemplo": {"titulo_padrao": "Pagar a fatura", "hora": "15:00"},
        "variacoes": [
            _v("Deu {hora}, é agora. Quando terminar, toca em Feito."),
            _v("{hora} em ponto. Bora começar, nem que seja 2 minutos."),
            _v("É agora. Começa pelo mais fácil e toca em Feito no fim."),
            _v("Chegou a hora ({hora}). Tu consegue, é só o primeiro passo."),
            _v("Deu {hora}. Mais um Feito e o dia fica redondo.", se="sequencia"),
            _v("Deu {hora}. Faz essa e depois é só descanso.", se="noite"),
        ],
    },
    # 08/11 (frente A, A6): o aviso da hora saiu mais de 1 h atrasado (servidor voltou de parada)
    "tarefa_atrasada": {
        "tipo": "tarefa_horario", "nome": "Tarefa: o aviso saiu bem atrasado",
        "exemplo": {"titulo_padrao": "Pagar a fatura", "hora": "15:00", "atraso": "1 h 20 min"},
        "variacoes": [
            _v("Era às {hora}, já faz {atraso}. Ainda vale fazer hoje?"),
            _v("Ficou pra trás: era {hora}, faz {atraso}. Faz agora ou empurra?"),
            _v("{hora} passou faz {atraso}. Se ainda vale, bora agora."),
            _v("Atrasou {atraso} (era {hora}). Faz agora ou muda a hora?"),
        ],
    },
    # 08/11 (frente A, A1): compromisso de SAIR depois da hora - nada de "toca em Feito" nem "primeiro passo"
    "saida_depois": {
        "tipo": "tarefa_horario", "nome": "Compromisso de sair: passou da hora",
        "exemplo": {"titulo_padrao": "Date", "hora": "20:00", "chega": "20:15"},
        "variacoes": [
            _v("Ainda em casa? Saindo agora tu chega às {chega}."),
            _v("Era {hora}. Se ainda não saiu, saindo agora chega às {chega}."),
            _v("Já saiu? Se não, pega a chave: tu chega às {chega}."),
            _v("{hora} já foi, sem drama. Saindo agora, chega às {chega}."),
            _v("Chave, carteira, celular: saindo agora chega às {chega}."),
            _v("A noite te espera: saindo agora tu chega às {chega}.", se="noite"),
        ],
    },
    "saida_agora": {
        "tipo": "tarefa_agora", "nome": "Compromisso de sair: na hora exata (app)",
        "exemplo": {"titulo_padrao": "Buscar a Bia", "hora": "18:00"},
        "variacoes": [
            _v("Deu {hora}. Hora de ir: chave, carteira, celular."),
            _v("{hora} em ponto. Pega as coisas e vai, sem correr."),
            _v("É agora ({hora}). Se ainda não saiu, bora."),
            _v("Deu {hora}. Tem alguém te esperando, bora?", se="pessoa"),  # 08/11: so com gente esperando
        ],
    },
    "saida_atrasada": {
        "tipo": "tarefa_horario", "nome": "Compromisso de sair: passou bem da hora",
        "exemplo": {"titulo_padrao": "Date", "hora": "20:00", "atraso": "1 h 20 min", "chega": "21:35"},
        "variacoes": [
            _v("Era às {hora}, já faz {atraso}. Se ainda vai, chega às {chega}."),
            _v("Passou {atraso} das {hora}. Saindo agora, tu chega às {chega}."),
            _v("{hora} foi faz {atraso}. Ainda vai? Saindo já, chega às {chega}."),
            _v("Faz {atraso} que era {hora}. Se ainda rola, chega às {chega}."),
        ],
    },
    "saida_indo": {
        "tipo": "tarefa_horario", "nome": "Compromisso de sair: já tá a caminho (GPS)",
        "exemplo": {"titulo_padrao": "Date", "hora": "20:00", "chega": "20:10"},
        "variacoes": [
            _v("Tá a caminho, né? Vai tranquilo, sem correr."),
            _v("Vi que tu saiu. Vai com calma, chega às {chega}."),
            _v("Já tá indo. Respira e aproveita o caminho."),
            _v("Pé na estrada. Sem pressa, o importante é chegar bem."),
        ],
    },
    "saida_chegou": {
        "tipo": "tarefa_horario", "nome": "Compromisso de sair: já chegou (GPS)",
        "exemplo": {"titulo_padrao": "Date", "hora": "20:00"},
        "variacoes": [
            _v("Chegou bem. Aproveita!"),
            _v("Tu já tá lá. Curte o momento."),
            _v("Chegou. Agora é só aproveitar."),
            _v("Já tá no lugar. O resto espera, aproveita."),
        ],
    },
    "saida_passou": {
        "tipo": "tarefa_horario_passou", "nome": "Compromisso de sair: 2o aviso depois da hora",
        "exemplo": {"titulo_padrao": "Passou da hora", "nome": "Date", "hora": "20:00", "chega": "20:45"},
        "variacoes": [
            _v("{nome} era {hora}. Ainda em casa? Saindo agora chega às {chega}."),
            _v("{nome}: era {hora}. Se ainda vai, saindo agora chega às {chega}."),
            _v("Era {hora} ({nome}). Se ainda vai, tu chega às {chega}."),
            _v("{nome} era {hora}. Saindo já, tu chega às {chega}."),
        ],
    },
    # ------------------------------------------------------------ compromisso de sair (date, festa)
    "se_arrumar": {
        "tipo": "se_arrumar", "nome": "Começa a se arrumar",
        "exemplo": {"nome": "Date", "hora": "20:00", "min": 40, "sai": "19:45"},
        "variacoes": [
            _v("{nome} às {hora}. Começando agora, {min} min e tu sai às {sai} sem correr.", "Começa a se arrumar"),
            _v("{min} min pra ficar pronto e sair às {sai}. {nome} às {hora}.", "Hora de se arrumar"),
            _v("{nome} às {hora}. Começa agora e às {sai} tu tá na porta.", "Bora pro banho?"),
            _v("{nome} às {hora}. Com {min} min tu sai às {sai} tranquilo.", "Tá na hora do capricho"),
            _v("Noite boa pela frente: {nome} às {hora}. Tu sai às {sai}.", "Começa a se arrumar", se="noite"),
            _v("{nome} às {hora}, sai às {sai}. Vai chover: separa o guarda-chuva.", "Se arruma sem pressa", se="chuva"),
        ],
    },
    "se_arrumar_tarde": {
        "tipo": "se_arrumar", "nome": "Começa a se arrumar (já passou um pouco)",
        "exemplo": {"nome": "Date", "hora": "20:00", "sai": "19:45"},
        "variacoes": [
            _v("{nome} às {hora}. Já passou um pouco da hora, mas dá: tu sai às {sai}.", "Começa a se arrumar"),
            _v("Ainda dá tempo: {nome} às {hora}, saída às {sai}. Começa pelo banho.", "Bora se arrumar"),
            _v("{nome} às {hora}. Versão rápida hoje e tu sai às {sai}.", "Ainda dá tempo"),
            _v("Atrasou um pouco, sem stress. Tu sai às {sai} e chega às {hora}.", "Começa a se arrumar"),
        ],
    },
    "hora_de_sair": {
        "tipo": "hora_de_sair", "nome": "Hora de sair (com trajeto)",
        "exemplo": {"nome": "Date", "hora": "20:00", "trajeto": 12},
        "variacoes": [
            _v("Saindo agora tu chega certinho: {nome} às {hora}, {trajeto} min até lá.", "Bora, hora de sair"),
            _v("{trajeto} min até lá e {nome} às {hora}. Pega a chave e vai.", "Hora de ir"),
            _v("Saindo agora: {trajeto} min de caminho, chega pras {hora}.", "Partiu?"),
            _v("E a porta. {trajeto} min até lá, {nome} às {hora}.", "Chave, carteira, celular"),
            _v("Noite começando: {trajeto} min até lá, {nome} às {hora}.", "Hora de sair", se="noite"),
            _v("Com chuva, sai já: {trajeto} min até lá, {nome} às {hora}.", "Bora, hora de sair", se="chuva"),
        ],
    },
    "hora_de_sair_parada": {
        "tipo": "hora_de_sair", "nome": "Hora de sair (com parada no caminho)",
        "exemplo": {"nome": "Date", "hora": "19:00", "parada": "casa do guri", "parada_min": 10},
        "variacoes": [
            _v("{parada_min} min até {parada}. Depois {nome} às {hora}.", "Bora, hora de sair"),
            _v("Primeiro {parada} ({parada_min} min), depois {nome} às {hora}.", "Hora de ir"),
            _v("Saindo agora: {parada} em {parada_min} min e {nome} às {hora}.", "Partiu?"),
            _v("Primeira parada: {parada}, {parada_min} min. {nome} às {hora}.", "Chave, carteira, celular"),
        ],
    },
    "hora_de_sair_folga": {
        "tipo": "hora_de_sair", "nome": "Hora de sair (sem trajeto do Maps)",
        "exemplo": {"nome": "Date", "hora": "20:00"},
        "variacoes": [
            _v("{nome} às {hora}. Saindo agora tu chega com folga.", "Bora, hora de sair"),
            _v("Sai agora e chega tranquilo: {nome} às {hora}.", "Hora de ir"),
            _v("{nome} às {hora}. Pega as coisas e vai, sobra tempo.", "Partiu?"),
            _v("E a porta. {nome} às {hora}, saindo agora dá folga.", "Chave, carteira, celular"),
        ],
    },
    # ------------------------------------------------------------ so o titulo varia (corpo vem pronto)
    "voo_sair": {
        "tipo": "voo_sair", "nome": "Hora de ir pro voo",
        "exemplo": {"corpo_padrao": "Sai até 14:00 pra pegar o briefing."},
        "variacoes": [
            _v(titulo="Bora pro voo"),
            _v(titulo="Hora de ir pro aeroclube"),
            _v(titulo="O avião te espera"),
            _v(titulo="Partiu voar?"),
            _v(titulo="Céu te chamando", se="manha"),
        ],
    },
    "agua_pausa": {
        "tipo": "agua_pausa", "nome": "Água / pausa",
        "exemplo": {"corpo_padrao": "Um copo agora e uma esticada de 1 min."},
        "variacoes": [
            _v(titulo="Bora uma água?"),
            _v(titulo="Um gole d'água?"),
            _v(titulo="Pausa pra água"),
            _v(titulo="Água rapidinho?"),
            _v(titulo="Teu corpo pediu água"),
            _v(titulo="Pausa da tarde: água", se="tarde"),
        ],
    },
    "rotina_manha": {
        "tipo": "rotina_manha", "nome": "Bom dia (rotina da manhã)",
        "exemplo": {"corpo_padrao": "Rotina da manhã: remédio, café. Começa leve."},
        "variacoes": [
            _v(titulo="Bom dia"),
            _v(titulo="Bom dia, bora começar"),
            _v(titulo="Dia novo"),
            _v(titulo="Bom dia, sem pressa"),
            _v(titulo="Bom dia de chuva", se="chuva"),
            _v(titulo="Bom dia, sábado ou domingo?", se="fim_de_semana"),
        ],
    },
    "fechamento_noturno": {
        "tipo": "fechamento_noturno", "nome": "Fecha o dia (noite)",
        "exemplo": {"corpo_padrao": "Hoje: 4 feitas, R$ 38 gastos. Bora ver amanhã?"},
        "variacoes": [
            _v(titulo="Fecha o dia comigo?"),
            _v(titulo="Bora fechar o dia?"),
            _v(titulo="Como foi hoje?"),
            _v(titulo="Um minutinho pro dia de hoje?"),
            _v(titulo="Hora de pousar o dia"),
        ],
    },
    "tarefa_horario_passou": {
        "tipo": "tarefa_horario_passou", "nome": "Passou da hora da tarefa",
        "exemplo": {"corpo_padrao": "\"Ligar pro banco\" era às 14:00. Ainda dá hoje?"},
        "variacoes": [
            _v(titulo="Passou da hora"),
            _v(titulo="Ficou pra trás?"),
            _v(titulo="Ainda dá tempo"),
            _v(titulo="Bora retomar?"),
        ],
    },
    "tarefa_inegociavel": {
        "tipo": "tarefa_inegociavel", "nome": "Tarefa inegociável",
        "exemplo": {"corpo_padrao": "Remédio às 21:00, daqui 5 min."},
        "variacoes": [
            _v(titulo="Não pode falhar"),
            _v(titulo="Essa é importante"),
            _v(titulo="Essa não dá pra pular"),
            _v(titulo="Prioridade do dia"),
        ],
    },
    "casa_tarefa": {
        "tipo": "casa_tarefa", "nome": "Chegou em casa com tarefa aberta",
        "exemplo": {"corpo_padrao": "Ainda falta \"Lavar a louça\" hoje. Dá 15 min."},
        "variacoes": [
            _v(titulo="Chegou em casa"),
            _v(titulo="Em casa já?"),
            _v(titulo="De volta em casa"),
            _v(titulo="Chegou, boa", se="noite"),
        ],
    },
    "saida_previsao": {
        "tipo": "saida_previsao", "nome": "Chuva antes de sair (previsão piorou)",
        "exemplo": {"corpo_padrao": "Chuva às 19h: adiantei a saída 10 min, sai às 19:35."},
        "variacoes": [
            _v(titulo="A previsão piorou"),
            _v(titulo="Vai chover na saída"),
            _v(titulo="Leva o guarda-chuva"),
            _v(titulo="Chuva no caminho"),
        ],
    },
    # ------------------------------------------------------------ assuntos novos (07/11)
    "lugar_fechado": {
        "tipo": "lugar_fechado", "nome": "Lugar fechado na hora que tu chega",
        "exemplo": {"lugar": "Shopping", "chegada": "21:40", "abre": "10:00"},
        "variacoes": [
            _v("Tu chegaria às {chegada} e ele tá fechado. Abre às {abre}.", "Ó, {lugar} tá fechado"),
            _v("Às {chegada} não abre. Que tal ir depois das {abre}?", "{lugar} fechado nessa hora"),
            _v("{lugar} tá fechado às {chegada}. Abre às {abre}.", "Confere antes de ir"),
            _v("{lugar} não abre às {chegada}. Abre às {abre}, quer trocar a hora?", "Melhor mudar a hora"),
        ],
    },
    "lugar_fechado_sem_hora": {
        "tipo": "lugar_fechado", "nome": "Lugar fechado (sem hora de abrir)",
        "exemplo": {"lugar": "Cartório", "chegada": "18:30"},
        "variacoes": [
            _v("Pelo Google, ele tá fechado às {chegada}. Vale conferir antes de ir.", "Ó, {lugar} tá fechado"),
            _v("{lugar} aparece fechado às {chegada}. Melhor trocar o dia?", "Confere antes de ir"),
            _v("Às {chegada} o Google diz que tá fechado. Tem outro horário?", "{lugar} fechado nessa hora"),
            _v("{lugar} fechado às {chegada}, pelo Google. Quer que eu mude a tarefa?", "Melhor mudar a hora"),
        ],
    },
    "lugar_fechando": {
        "tipo": "lugar_fechado", "nome": "Lugar fecha logo depois que tu chega",
        "exemplo": {"lugar": "Banco", "chegada": "15:40", "fecha": "16:00"},
        "variacoes": [
            _v("Tu chega às {chegada} e ele fecha às {fecha}. Dá, mas sem enrolar.", "{lugar} fecha cedo"),
            _v("{lugar} fecha às {fecha}. Chegando às {chegada}, o tempo fica curto.", "Olho no relógio"),
            _v("{lugar}: tu chega às {chegada}, sobra pouco tempo lá dentro.", "Fecha às {fecha}"),
            _v("{lugar} fecha às {fecha}. Saindo antes tu fica mais tranquilo.", "Vai mais cedo?"),
        ],
    },
    "lugar_fechado_temp": {
        "tipo": "lugar_fechado", "nome": "Lugar fechado temporariamente",
        "exemplo": {"lugar": "Padaria do Zé"},
        "variacoes": [
            _v("O Google diz que tá fechado temporariamente. Melhor nem ir hoje.", "{lugar} tá fechado"),
            _v("{lugar} aparece como fechado por enquanto. Tem outro parecido?", "Confere antes de ir"),
            _v("Fechado temporariamente, segundo o Google. Quer que eu ache outro?", "{lugar} parou por ora"),
            _v("{lugar} tá fechado por um tempo. Liga antes, se precisar mesmo.", "Ó, deu ruim"),
        ],
    },
    "transito_piorou": {
        "tipo": "transito_piorou", "nome": "Trânsito piorou antes de sair",
        "exemplo": {"hora": "20:00", "mais": 12, "sai": "19:33"},
        "variacoes": [
            _v("+{mais} min no caminho. Sai às {sai} pra chegar às {hora}.", "Trânsito piorou"),
            _v("O trânsito tá pior. Melhor sair às {sai}, chega às {hora}.", "Caminho mais lento"),
            _v("Mais {mais} min de trânsito agora. Saindo às {sai} tu chega certo.", "Adianta a saída?"),
            _v("Deu uma travada no caminho (+{mais} min). Sai às {sai}, chega às {hora}.", "Rua cheia"),
            _v("Com a chuva o caminho ficou +{mais} min. Sai às {sai}.", "Chuva e trânsito", se="chuva"),
        ],
    },
    "chegou_casa": {
        "tipo": "chegou_casa", "nome": "Chegou em casa: marca o que fez",
        "exemplo": {},
        "variacoes": [
            _v("Fez alguma coisa na rua? Toca aqui e marca o que já foi.", "Chegou em casa"),
            _v("Bem-vindo de volta. O que tu resolveu fora? Marca rapidinho.", "De volta"),
            _v("Antes de largar o celular: marca o que tu fez na rua.", "Em casa já?"),
            _v("Noite em casa. Marca o que rolou hoje e descansa.", "Chegou, boa", se="noite"),
        ],
    },
    "meta_batida": {
        "tipo": "meta_batida", "nome": "Bateu uma meta",
        "exemplo": {"meta": "50 horas de voo"},
        "variacoes": [
            _v("{meta}: fechou. Mandou bem.", "Meta batida!"),
            _v("{meta} tá completa. Guarda essa sensação.", "Bateu a meta"),
            _v("{meta}: feito. Mais uma pra conta.", "Olha tu"),
            _v("{meta} fechada. Pode comemorar um pouquinho.", "Conseguiu"),
        ],
    },
    "sequencia": {
        "tipo": "sequencia", "nome": "Sequência de dias",
        "exemplo": {"n": 5, "coisa": "Treino"},
        "variacoes": [
            _v("{coisa}: {n} dias sem falhar. Tá virando hábito.", "{n} dias seguidos"),
            _v("{coisa} todo dia há {n} dias. Bora manter amanhã?", "Sequência de {n}"),
            _v("{n} dias seguidos de {coisa}. Não precisa ser perfeito, só aparecer.", "Tá embalado"),
            _v("{coisa}: {n} dias. Amanhã é só repetir.", "Olha a sequência"),
        ],
    },
}

# emoji dos assuntos novos (os antigos ja estao em notificacoes.EMOJI_DO_AVISO)
EMOJI_NOVOS = {
    "lugar_fechado": "🚪",
    "transito_piorou": "🚦",
    "chegou_casa": "🏠",
    "meta_batida": "🎯",
    "sequencia": "🔥",
    "saida_previsao": "☔",
    "aviso_ia": "💬",
}

# assunto que a IA pode escolher em `agendar_aviso` -> emoji (1 so, no titulo)
EMOJI_DA_IA = {
    "lembrete": "💬", "tarefa": "⏰", "sair": "🚗", "agua": "💧", "comida": "🍽️", "remedio": "💊",
    "voo": "✈️", "treino": "💪", "casa": "🏠", "dinheiro": "💸", "conversa": "📱", "dormir": "🌙",
    "estudo": "📚", "festa": "🎉",
}

# tipo do aviso -> assunto de titulo variavel (o corpo vem pronto de outro lugar)
SO_TITULO = {a: c["tipo"] for a, c in CATALOGO.items()
             if all(v["corpo"] is None and v["titulo"] for v in c["variacoes"])}
_ASSUNTO_DO_TIPO_TITULO = {tipo: a for a, tipo in SO_TITULO.items()}


# ---------------------------------------------------------------- contexto

def _cond_ok(se: str | None, ctx: dict) -> bool:
    if not se:
        return True
    h = ctx.get("hora")
    if se == "manha":
        return h is not None and 5 <= h < 12
    if se == "tarde":
        return h is not None and 12 <= h < 18
    if se == "noite":
        return h is not None and (h >= 18 or h < 5)
    if se == "fim_de_semana":
        return bool(ctx.get("fim_de_semana"))
    if se == "chuva":
        return bool(ctx.get("chuva"))
    if se == "sequencia":
        return int(ctx.get("feitos_hoje") or 0) >= 3
    if se == "repeticao":
        return int(ctx.get("repeticao") or 0) >= 1
    if se == "pouco_tempo":
        f = ctx.get("falta_min")
        return f is not None and f <= 10
    if se == "pessoa":  # 08/11: "tem alguem te esperando" so quando tem (notificacoes.com_pessoa)
        return bool(ctx.get("pessoa"))
    return False


def contexto(conn=None, agora: datetime | None = None, **extra) -> dict:
    """hora do dia, fim de semana, feitos hoje (sequencia) + o que quem chama sabe (chuva, repeticao...)."""
    agora = agora or datetime.now()
    ctx = {"hora": agora.hour, "fim_de_semana": agora.weekday() >= 5}
    if conn is not None:
        try:
            # leva 08/11: completed_at e UTC - a tarefa feita as 22h ja e "amanha" em UTC e o aviso das 07:00
            # de amanha contava ela como feita no dia dele ("boa sequencia hoje"). Dia de Brasilia do db.py.
            import db  # aqui dentro: o modulo fica sem dependencia no import (testes puros do catalogo)
            ctx["feitos_hoje"] = conn.execute(
                f"SELECT COUNT(*) FROM tasks WHERE completed_at IS NOT NULL AND {db.dia_local_sql('completed_at')} = ?",
                (agora.date().isoformat(),)).fetchone()[0]
        except Exception:  # noqa: BLE001 - contexto e extra
            pass
    ctx.update({k: v for k, v in extra.items() if v is not None})
    return ctx


# ---------------------------------------------------------------- render

def _campos(t: str | None) -> set[str]:
    if not t:
        return set()
    return {nome for _, nome, _, _ in string.Formatter().parse(t) if nome}


def _curto(v, lim: int = NOME_LIM):
    if not isinstance(v, str):
        return v
    v = " ".join(v.split())
    if len(v) <= lim:
        return v
    corte = v[: lim - 1].rsplit(" ", 1)[0] if " " in v[: lim - 1] else v[: lim - 1]
    return corte.rstrip(" ,.;:-") + "…"


def _dados_limpos(dados: dict) -> dict:
    return {k: (_curto(v) if k in ("nome", "lugar", "parada", "coisa", "meta") else v) for k, v in dados.items()}


# assuntos que ja existiam antes desta leva: a variacao 0 deles e o texto de antes, sem encurtar nada
LEGADO = frozenset({"tarefa_preparo", "tarefa_horario", "tarefa_na_hora", "tarefa_agora", "se_arrumar",
                    "se_arrumar_tarde", "hora_de_sair", "hora_de_sair_parada", "hora_de_sair_folga"})


def _classica(assunto: str, i: int) -> bool:
    return i == 0 and assunto in LEGADO


def _render(v: dict, dados: dict, padrao: tuple[str, str], classica: bool = False) -> tuple[str, str] | None:
    """(titulo, corpo) ou None se falta dado pro template. A classica (variacao 0) nao encurta nome nenhum:
    e exatamente o texto de antes desta leva."""
    precisa = _campos(v["titulo"]) | _campos(v["corpo"])
    if any(dados.get(c) is None for c in precisa):
        return None
    d = dados if classica else _dados_limpos(dados)
    titulo = v["titulo"].format(**d) if v["titulo"] else padrao[0]
    corpo = v["corpo"].format(**d) if v["corpo"] else padrao[1]
    return titulo, corpo


def cabe(titulo: str, corpo: str) -> bool:
    return len(titulo or "") <= TITULO_LIM and len(corpo or "") <= CORPO_LIM


def escolher(assunto: str, dados: dict | None = None, ctx: dict | None = None, ultima: int | None = None,
             primeira: bool = False, rng=None, padrao: tuple[str, str] = ("", "")) -> int:
    """Indice da variacao. Puro (sem banco): quem guarda a memoria e `texto`."""
    vs = CATALOGO[assunto]["variacoes"]
    dados, ctx = dados or {}, ctx or {}
    elegiveis = []
    for i, v in enumerate(vs):
        if not _cond_ok(v["se"], ctx):
            continue
        r = _render(v, dados, padrao, classica=_classica(assunto, i))
        if r is None or (not _classica(assunto, i) and not cabe(*r)):  # a classica do legado e o texto de antes
            continue
        elegiveis.append(i)
    if not elegiveis:
        return 0
    if primeira and 0 in elegiveis:
        return 0
    fortes = [i for i in elegiveis if vs[i]["se"] in FORTES]
    pool = [i for i in (fortes or elegiveis) if i != ultima]
    if not pool:
        pool = [i for i in elegiveis if i != ultima] or elegiveis
    return (rng or random).choice(pool)


# ---------------------------------------------------------------- memoria (configuracoes)

def _memoria(conn) -> dict:
    try:
        from db import obter_configuracao

        m = json.loads(obter_configuracao(conn, MEMORIA) or "{}")
        return m if isinstance(m, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _guardar(conn, mem: dict) -> None:
    try:
        from db import definir_configuracao

        definir_configuracao(conn, MEMORIA, json.dumps(mem, ensure_ascii=False))
        conn.commit()
    except Exception:  # noqa: BLE001 - memoria e extra, o aviso sai igual
        pass


def texto(assunto: str, dados: dict | None = None, *, conn=None, chave: str | None = None, ctx: dict | None = None,
          padrao: tuple[str, str] = ("", ""), rng=None) -> tuple[str, str]:
    """(titulo, corpo) do assunto. `padrao` = o que fica quando a variacao nao mexe no titulo/corpo.
    Sem conn: variacao 0 (texto classico). Com conn: escolhe por contexto, sem repetir a ultima, estavel por chave."""
    if assunto not in CATALOGO:
        return padrao
    dados = dict(dados or {})
    vs = CATALOGO[assunto]["variacoes"]
    if conn is None:
        return _render(vs[0], dados, padrao, classica=_classica(assunto, 0)) or padrao
    mem = _memoria(conn)
    m = mem.get(assunto) if isinstance(mem.get(assunto), dict) else {}
    chaves = m.get("chaves") if isinstance(m.get("chaves"), dict) else {}
    idx = chaves.get(chave) if chave else None
    if not isinstance(idx, int) or not 0 <= idx < len(vs) or _render(vs[idx], dados, padrao) is None:
        idx = escolher(assunto, dados, ctx, ultima=m.get("ultima"), primeira=not m, rng=rng, padrao=padrao)
        if chave:
            chaves.pop(chave, None)
            chaves[chave] = idx
            while len(chaves) > CHAVES_POR_ASSUNTO:
                chaves.pop(next(iter(chaves)))
        mem[assunto] = {"ultima": idx, "chaves": chaves}
        _guardar(conn, mem)
    return _render(vs[idx], dados, padrao, classica=_classica(assunto, idx)) or padrao


def par(assunto: str, dados: dict, *, conn=None, chave: str | None = None, agora: datetime | None = None,
        padrao: tuple[str, str] = ("", ""), **ctx_extra) -> tuple[str, str]:
    """Atalho pros geradores de notificacoes.py: contexto montado aqui (hora, sequencia + chuva etc. de quem chama)."""
    ctx = contexto(conn, agora, **ctx_extra) if conn is not None else None
    return texto(assunto, dados, conn=conn, chave=chave, ctx=ctx, padrao=padrao)


def variar_titulo(conn, tipo: str, titulo: str, corpo: str, chave: str | None = None,
                  ctx: dict | None = None) -> tuple[str, str]:
    """Pro despacho (tick do servidor / lista do app): tipo de titulo generico (agua, bom dia, voo...) ganha
    outro titulo do catalogo; o corpo fica. Titulo que nao e o generico (ja personalizado) fica como veio."""
    assunto = _ASSUNTO_DO_TIPO_TITULO.get(tipo)
    if not assunto or conn is None:
        return titulo, corpo
    titulos = {v["titulo"] for v in CATALOGO[assunto]["variacoes"]}
    if titulo not in titulos:  # "De novo · X", titulo montado com dado: nao mexe
        return titulo, corpo
    return texto(assunto, {}, conn=conn, chave=chave, ctx=ctx if ctx is not None else contexto(conn),
                 padrao=(titulo, corpo))


# ---------------------------------------------------------------- frente D: lugar fechado

def lugar_fechado(conn, lugar: str, chegada: str | None = None, *, fecha: str | None = None, abre: str | None = None,
                  temporario: bool = False, chave: str | None = None, agora: datetime | None = None) -> tuple[str, str]:
    """(titulo, corpo) do aviso `lugar_fechado` (frente D, "ta aberto?"). Sem emoji (com_emoji poe 🚪).
      - temporario=True: Google diz CLOSED_TEMPORARILY/PERMANENTLY;
      - fecha="16:00": aberto na chegada mas fecha logo depois;
      - senao: fechado na chegada (abre="10:00" quando se sabe)."""
    dados = {"lugar": (lugar or "").strip() or "O lugar", "chegada": chegada, "fecha": fecha, "abre": abre}
    if temporario:
        assunto = "lugar_fechado_temp"
    elif fecha:
        assunto = "lugar_fechando"
    elif abre:
        assunto = "lugar_fechado"
    else:
        assunto = "lugar_fechado_sem_hora"
    if not chegada:  # sem hora de chegada: vale a de agora (o temporario nem usa)
        dados["chegada"] = (agora or datetime.now()).strftime("%H:%M")
    ctx = contexto(conn, agora) if conn is not None else None
    return texto(assunto, dados, conn=conn, chave=chave, ctx=ctx, padrao=("Confere antes de ir", ""))


# ---------------------------------------------------------------- exportar (artefato de veto)

def emoji_do_tipo(tipo: str) -> str:
    import notificacoes

    return notificacoes.EMOJI_DO_AVISO.get(tipo) or EMOJI_NOVOS.get(tipo, "")


def exemplos() -> dict:
    """Todas as variacoes de todos os assuntos, com os dados de exemplo (inventados), prontas pra tela de veto."""
    saida = {}
    for assunto, c in CATALOGO.items():
        ex = c["exemplo"]
        padrao = (ex.get("titulo_padrao", ""), ex.get("corpo_padrao", ""))
        emoji = emoji_do_tipo(c["tipo"])
        lista = []
        for i, v in enumerate(c["variacoes"]):
            t, corpo = _render(v, ex, padrao, classica=_classica(assunto, i)) or padrao
            lista.append({"indice": i, "classica": i == 0, "quando": v["se"] or "sempre",
                          "titulo": f"{emoji} {t}".strip(), "corpo": corpo,
                          "titulo_chars": len(t), "corpo_chars": len(corpo)})
        saida[assunto] = {"tipo": c["tipo"], "nome": c["nome"], "emoji": emoji,
                          "titulo_fixo": "nome da tarefa" if "titulo_padrao" in ex else None,
                          "variacoes": lista}
    return saida
