# Briefing: Assistente de Vida Pessoal

## Contexto

Projeto pessoal, só pra meu uso (não é produto comercial). Objetivo: reduzir carga mental do dia a dia, considerando que tenho TDAH e funciono melhor com as coisas regradas, organizadas e com baixa fricção pra registrar qualquer coisa.

**Importante: isso é separado do painel financeiro da minha construtora.** Este projeto é só vida pessoal — rotina, finanças pessoais, relacionamento, saúde, decisão do dia a dia. Não é dashboard de empresa.

Vai rodar como PWA (Progressive Web App) acessado pelo navegador do iPhone, adicionado à tela de início — não é app nativo da App Store, porque isso sairia caro. O PWA já suporta notificação push real no iOS (desde 16.4+), então a experiência deve ser o mais próxima possível de um app nativo.

---

## REGRAS DE TRABALHO (leia antes de começar)

1. **Não pare até terminar tudo que está descrito aqui.** Trabalhe de forma contínua e autônoma.
2. **Se você perder o contexto da conversa ou esquecer o que estava fazendo, releia este arquivo (que deve estar versionado no git do projeto) para retomar de onde parou.** Mantenha o progresso registrado (ex: um CHANGELOG.md ou TODO.md no repositório) pra você mesmo conseguir se re-orientar depois de uma interrupção.
3. **Faça todas as perguntas de esclarecimento ANTES de começar a construir, não durante.** Depois que eu responder e você começar a trabalhar, não pare para me perguntar mais nada — resolva com o melhor julgamento possível e documente a decisão tomada.
4. **Não peça chave de API, senha, token ou credencial durante a construção.** Monte toda a estrutura do código já preparada para receber essas credenciais (variáveis de ambiente, arquivo `.env.example`, etc.), e só no final, quando tudo estiver pronto, me diga exatamente quais credenciais você precisa que eu forneça.
5. Priorize simplicidade e terminar de verdade, ao invés de arquitetura perfeita e incompleta.

---

## Arquitetura geral

- Backend simples, banco de dados leve (SQLite ou equivalente)
- Frontend web (PWA) com notificação push
- Integração com API da Anthropic (Claude) para processar linguagem natural — usar modelo mais barato (Haiku) para tarefas simples de classificação/registro, modelo mais capaz (Sonnet) só quando precisar de mais raciocínio
- Campo único de entrada (texto e, futuramente, voz) — tudo que eu jogar ali deve ser classificado automaticamente (tarefa, gasto, lembrete, nota, ideia) sem eu escolher categoria manualmente

---

## Funcionalidades — Fase 1 (essencial, construir primeiro)

### Captura universal
- Campo único de "joga aqui" — texto solto vira tarefa, gasto, lembrete ou nota automaticamente
- Quebra automática de tarefa grande em passos pequenos

### Rotina e cabeça no lugar (núcleo TDAH)
- Resumo do dia sem tom de cobrança — só fato ("hoje você tinha 3 coisas, fez 2")
- Modo "só o essencial" — em dia corrido, mostra só 1-3 coisas mais importantes
- Modo "hiperfoco protegido" — quando eu marcar que estou em tarefa importante, silencia notificação não-crítica
- Check-in rápido de energia/sono/humor, 1 toque
- Rotina matinal e noturna guiada — checklist curto disparado nos horários certos
- Detecção de tarefa "empacada" — se algo fica dias parado, sugere quebrar diferente

### Financeiro pessoal
- Registro de gasto solto — "gastei 50 no mercado" categorizado sozinho
- Visão simples de gasto por categoria no mês, sem gráfico complicado
- Lembrete de conta recorrente antes de vencer
- Alerta de assinatura que não uso mais

### Vida social e relacionamento
- Lembrete de data importante (aniversário, evento) com sugestão de ação ("já pensou em mandar algo?")
- Nota leve de conversa — "falei com X sobre Y", sem virar CRM chato
- Sugestão de "faz tempo que você não fala com X"

### Assistente de decisão rápida
- Framework de "vale a pena?" pra qualquer decisão (compra, negociação, escolha)
- Prós e contras organizados rápido

---

## Funcionalidades — Fase 2 (depois que a Fase 1 estiver rodando bem)

### Saúde e corpo
- Lembrete de água/pausa em dia de trabalho intenso
- Registro leve de treino
- Lembrete de consulta médica/dentista recorrente
- Alerta de sono ruim recorrente (3+ noites seguidas)
- Correlação entre sono ruim e humor/produtividade (cruzando dado do Health com check-in manual)

### Localização e contexto físico
- Detectar chegada em casa/trabalho e disparar rotina automática
- Lembrete baseado em local ("perto do mercado, lembra da lista")

### Clima e logística do dia
- Aviso de manhã se o clima vai atrapalhar compromisso do dia
- Sugestão de sair mais cedo se o trânsito pro compromisso estiver ruim

### Viagem e logística pessoal
- Checklist de mala automático baseado em destino/clima
- Lembrete de documento antes de viagem
- Registro de lugar que gostei, pra sugerir de novo depois

### Casa e manutenção
- Lembrete de manutenção recorrente (carro, casa, equipamento)
- Lista de compra doméstica que enche sozinha conforme eu falo "acabou o X"

### Comunicação assistida
- Ajuda a redigir mensagem difícil
- Lembrete de responder mensagem importante que ficou "pra depois"

---

## Funcionalidades — Fase 3 (expansão)

### Financeiro avançado
- Categorização automática puxando direto do extrato bancário (via Open Finance, ver seção de integrações)
- Projeção de quanto sobra no fim do mês, atualizada em tempo real
- Acompanhamento de meta de compra grande com projeção de quando bate

### Aprendizado e conteúdo
- Lista de "quero aprender sobre X" que lembra de retomar
- Resumo de artigo/vídeo salvo pra ver depois

### Metas e visão de longo prazo
- Painel de progresso pessoal (hábito, meta, disciplina — não financeiro empresa)
- Revisão mensal automática — "como foi esse mês", sem julgamento

### Burocracia e documentos
- Lembrete de imposto de renda, prazo de documento, renovação de CNH
- Cofre simples de informação importante (não senha, tipo "onde guardei tal documento")

### Aviação
- Lembrete de validade de documento/licença
- Nota rápida pós-voo, se eu quiser manter registro pessoal

### Comunicação e redes sociais
- Resumo semanal de tempo de uso de app (via Screen Time/Atalhos)

---

## Integrações técnicas necessárias

### Notificação push no iPhone
PWA adicionado à tela de início, usando Web Push API (suportado desde iOS 16.4+).

### Calendário e Contatos da Apple
Sincronizar via CalDAV/CardDAV (protocolo aberto, acessível direto pela web, sem precisar de app nativo).

### Lembretes e Saúde (Apple Health) da Apple
Essas não têm API web aberta — só acesso nativo. A ponte é o app **Atalhos (Shortcuts)**, nativo do iPhone: criar automações que rodam por horário ou gatilho e mandam o dado via webhook para o backend. Também considerar o app **Health Auto Export** (disponível na App Store) como ponte pronta para exportar dado de Saúde via webhook.

### Uber
Sem API pública fácil para histórico de corrida pessoal de terceiro pequeno. Usar Atalhos como ponte (registro manual ou semi-automático) ao invés de integração direta.

### Bancos (Nubank, Caixa, Viacredi/Sicredi e outros)
Usar **Open Finance** (sistema regulado pelo Banco Central) via um agregador como **Pluggy** ou **Belvo** — essas empresas são autorizadas como iniciadoras de transação (ITP) e oferecem API pronta que cobre a maioria dos bancos e cooperativas de crédito brasileiras, incluindo os mencionados. Verificar cobertura exata de cada instituição na documentação do agregador escolhido antes de implementar.

### Apps auxiliares recomendados (para eu baixar, servem de ponte)
- Atalhos (Shortcuts) — nativo, já instalado
- Health Auto Export — ponte de dados de Saúde
- IFTTT — automação entre apps diversos

---

## Perguntas que você deve me fazer AGORA, antes de começar

Se houver qualquer dúvida sobre escopo, prioridade, estrutura de dados, nome do projeto, hospedagem, ou qualquer outra decisão técnica que precise da minha opinião — pergunte tudo de uma vez, agora, antes de começar a construir. Depois que eu responder, comece e não pare até completar a Fase 1 por completo (ou o máximo que você conseguir avançar de forma contínua).
