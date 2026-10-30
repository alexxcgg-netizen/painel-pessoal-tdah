# Lab v4, Grupo F: Aviação (30/10/2026)

Seis ideias aprovadas, todas em `aviacao_lab.py` (conta) + `rotas/aviacao_lab.py` (API) + `static/js/cards-aviacao-lab.js` (cards). Os mesmos cards aparecem no chat e na aba Aviação (seção "painel de voo"). Dados sempre reais: diário de bordo (`voos`), quiz de estudo, METAR do briefing.

## O que entrou

| Ideia | O que faz | Onde |
| :--- | :--- | :--- |
| radar-validades | Régua + lista de prazos (CMA, habilitação, endosso, inscrição FGV, 2ª época, provisória) e voos a confirmar na CIV (janela de 14 dias, botão "Confirmei"). Aviso proativo em 60/30/7 dias. | `radar`, `civ_pendentes`, `avisos_prazos` |
| previsao-cheque | Data do cheque no ritmo das últimas 4 semanas, gargalo por requisito, simulador de noturno por mês, custo mínimo na hora/voo que ele digita. | `previsao_cheque` |
| banca | 5 cadernos, % dos últimos simulados, registro manual de acertos em 20, revisão do dia (Leitner do quiz, só leitura). | `banca`, tabela `banca_simulados` |
| chair-flying | Voo de cadeira passo a passo, fala o passo (ElevenLabs, fallback iPhone), "onde travou". Lembrete na véspera depois das 21h. | `chair_flying`, tabela `chair_flying` |
| vento-pista | Componentes proa/través com METAR real, sliders de simulação, com/sem correção magnética, veredito contra o limite pessoal. Linha de vento na saudação "manhã do voo". | `vento_pista`, `linha_vento` |
| passaporte | Um carimbo por aeródromo (destino e escalas dos voos reais), capa que abre, 6 por página. | `passaporte` |

Migração: `migracoes/202610301200_av_lab_v4_aviacao.sql` (`voos.civ_confirmada`, `banca_simulados`, `chair_flying`).

## Regra de ouro: nada de fato de aviação inventado

Tudo que não foi conferido é configurável e aparece como "não conferido":
- Validade do CMA: não é calculada, o Alex digita a data que está no documento.
- Pista 18/36 e declinação 20,6 W de SSBL: valores padrão marcados "não conferido". Mudar qualquer número desmarca a conferência; o botão "Conferi" confirma.
- Limite de través de 10 kt: configuração pessoal, não norma.
- Tempo de prova: só Navegação (100 min) está conferido; os outros cadernos o Alex digita.
- Passos do voo de cadeira: só "fala/faz", sem afirmar procedimento. Roteiro próprio via `POST /api/aviacao/chair/roteiro`.
- Rumo ao cheque: "em comando" não é projetado (o painel não sabe a função a bordo). Base: RBAC 61.101 Em.16, curso homologado.
- Nomes dos cadernos vêm do protótipo, não foram rechecados contra a IS 00-003.

## Decisões

- Custo do cheque é campo sensível (`CAMPOS_SENSIVEIS`): mascarado no modo visitante. Escritas recusam modo visitante.
- Vento reutiliza o METAR do briefing na saudação (sem chamada de rede nova); o card tem cache de 10 min.
- Bug do protótipo corrigido: a seta do vento gira `rotate(dm)`, não `dm+180`.
- Sem ferramenta nova no chat (`app.py`/`ia/funcoes/chat.py`) pra não colidir com os outros grupos; os cards saem pelo painel e pelo proativo.

## Ficou de fora

- Ferramenta de chat "mostra meu passaporte" e similares (conflito de arquivo com outros grupos; integrador adiciona).
- Monitor da página de agendamento da ANAC (scrape frágil).
- Simulado cronometrado na banca (só registro manual).
- Cadernos da banca ligados aos temas do quiz (quiz tem 3 temas; `estudo.TEMAS` intocado).
- Editor de roteiro do chair-flying na interface (só endpoint).

## Passos do Alex

1. Radar: digitar as datas (CMA, habilitação, endosso, FGV).
2. Vento: conferir pista e declinação de SSBL no AISWEB/ROTAER e tocar "Conferi".
3. Cheque: digitar o valor da hora de voo.
4. Opcional: tempos de prova por caderno e roteiro próprio do voo de cadeira.

## Para o integrador

Subir o `CACHE_NAME` do service worker (ASSETS já têm os arquivos novos), CHANGELOG, suíte completa. Testes da área: `tests/test_aviacao_lab.py` (33) e `tests/js/cards_aviacao_lab.test.js` (19). Capturas 390 px conferidas: sem rolagem horizontal.
