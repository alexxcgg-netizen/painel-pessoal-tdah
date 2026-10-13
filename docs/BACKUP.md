# Backup e exportação de dados

Guia rápido: o que cada formato de export contém, quando usar cada um, e como restaurar a
partir de um backup.

## Os três formatos de export

Todos ficam atrás do botão de backup no cabeçalho do painel (ícone de seta pra cima, ao lado do
sino de horário silencioso) - clique nele pra abrir o menu com as três opções, ou acesse os
endpoints diretamente (autenticados, exigem estar logado):

| Formato | Endpoint | Quando usar |
| --- | --- | --- |
| **Banco `.db` bruto** | `GET /api/backup/exportar` | Restaurar o painel inteiro de forma mais direta - é o próprio SQLite, você só troca o arquivo (ver "Restaurar" abaixo). Não abre numa planilha. |
| **JSON completo** | `GET /api/backup/exportar-json` | Restaurar tudo (todas as ~49 tabelas do schema) de um jeito legível/portável, ou migrar dado pra outro lugar. Estrutura: `{"versao": N, "exportado_em": "...", "tabelas": {"tasks": [...], "expenses": [...], ...}}` - uma chave por tabela, gerada dinamicamente a partir do schema atual (nunca fica desatualizado quando uma tabela nova é criada). |
| **CSV completo (.zip)** | `GET /api/backup/exportar-csv-completo` | Abrir em planilha (Excel, Google Sheets, Numbers). Como o dado é relacional (múltiplas tabelas), vem um `.zip` com um `.csv` por tabela em vez de um CSV único achatado - juntar tudo num CSV só perderia a relação entre as tabelas. |

Além desses três, `GET /api/expenses/exportar-csv` já existia antes e continua só pra gastos
(pensado pra abrir rápido numa planilha, sem baixar o resto do banco junto).

### Criptografia em repouso e os exports (leia se você tem `ENCRYPTION_KEY` configurada)

Se você ligou a criptografia em repouso (ver `docs/SEGURANCA.md`), os dois formatos se
comportam diferente nesse ponto - decisão deliberada, achada e ajustada numa revisão
independente:

- **JSON completo e CSV completo saem legíveis** (saldo, extrato, dado de saúde já
  descriptografados) - são pensados como "legível"/"pra abrir em planilha", e você já está
  autenticado no painel pra pedir esses exports (o mesmo acesso que já mostra esse dado
  descriptografado nas telas de Bancos/Saúde), então isso não é uma exposição nova.
- **O backup `.db` bruto continua cifrado** - é o formato pensado pra restaurar sem passar pela
  aplicação (só trocando o arquivo, ver "Restaurar" abaixo), então ele preserva o mesmo nível de
  proteção do banco em produção. Restaurar esse arquivo com o `ENCRYPTION_KEY` certo no `.env`
  volta a mostrar tudo normalmente pela interface.

Ou seja: se você for mandar o JSON/CSV completo pra algum lugar fora do seu controle (nuvem sem
criptografia própria, por exemplo), trate esses arquivos com o mesmo cuidado que trataria a tela
do painel aberta - eles têm o dado sensível em texto plano.

## Restaurar a partir de um backup `.db`

O jeito mais direto de voltar o painel inteiro pro estado de um backup:

1. **Pare o servidor** (`Ctrl+C` no processo do `python app.py`/gunicorn, ou pare o serviço se
   estiver rodando como daemon).
2. **Antes de sobrescrever nada, tire um backup do banco atual** (mesmo que ele pareça
   quebrado/desatualizado) - baixe `/api/backup/exportar` com o servidor ainda de pé, ou copie
   `data/painel.db` pra outro lugar. **Nunca sobrescreva um banco em uso sem essa cópia de
   segurança primeiro** - se o backup que você está restaurando tiver algum problema, essa é a
   única forma de não perder o que tinha antes.
3. **Troque o arquivo**: substitua `data/painel.db` pelo arquivo `.db` do backup (renomeie o
   backup pra `painel.db` exatamente, mesmo nome).
4. **Reinicie o servidor** (`python app.py` ou o serviço configurado).

Não tem passo de "importar" - o SQLite lê o arquivo direto, então trocar o arquivo já é a
restauração completa.

### Restaurar a partir do JSON

O export JSON é pensado como cópia de leitura/portabilidade, não tem endpoint de "importar" de
volta hoje. Pra restaurar a partir dele seria preciso escrever os dados de volta tabela por
tabela (schema em `db.py`) - na prática, prefira sempre restaurar pelo `.db` bruto quando
disponível; o JSON serve de rede de segurança adicional (por exemplo, se só o backup automático
mais recente sobreviveu e ele por algum motivo não abre como SQLite válido).

## Backup automático semanal

Além dos exports manuais, o painel tira uma cópia do banco sozinho **todo domingo às 3h da
manhã** (horário de baixo uso), via o scheduler que já roda em `app.py`
(`rodar_backup_automatico_semanal`, registrado em `iniciar_scheduler()`).

- **Onde ficam**: `BACKUP_DIR` (variável de ambiente, opcional). Sem configurar, o padrão é
  `data/backups/` dentro do projeto - já coberto pelo `.gitignore` (a pasta `data/` inteira
  já é ignorada).
- **Como mudar o diretório**: defina `BACKUP_DIR=/algum/caminho` no `.env` e reinicie o
  servidor. Útil pra apontar pra um disco separado, pasta sincronizada (Dropbox/iCloud Drive
  local), etc.
- **Retenção**: mantém só os últimos **8** backups (~2 meses de histórico semanal) - os mais
  antigos são apagados automaticamente a cada rodada nova.
- **Como restaurar a partir de um backup automático**: mesmo passo a passo da seção anterior -
  escolha o arquivo mais recente (ou o que quiser) em `BACKUP_DIR`, renomeie pra `painel.db` e
  siga os passos 1-4 acima.
- **Resiliência**: se o backup falhar por qualquer motivo (disco cheio, permissão negada, etc.),
  o erro só é registrado no log do servidor (`app.logger`) - o scheduler continua rodando
  normalmente e tenta de novo na semana seguinte. Um backup automático que falha nunca derruba
  o resto do painel.

### Backup automático também no Telegram

Se `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` já estiverem configurados no `.env` (ver seção
"Bot do Telegram" do `README.md`), cada backup semanal também é enviado como documento pro seu
chat do Telegram automaticamente, logo depois de salvo em `BACKUP_DIR` - uma cópia fora do disco
do servidor, então se o disco morrer o Telegram ainda tem uma cópia recente.

Não precisa fazer nada além de já ter o bot configurado - se não estiver, o backup local no
`BACKUP_DIR` continua acontecendo normalmente, só o envio pro Telegram é pulado.

## Backup automático diário

Além do semanal, o painel tira um snapshot **todo dia às 3h30** (`backup_diario.py`, registrado
em `iniciar_scheduler()`) e **também ao subir o app, se o último backup diário tiver mais de
24 h** (o PC nem sempre está ligado de madrugada).

- **Onde ficam**: `data/backups/painel-AAAA-MM-DD.db` (a pasta `backups/` irmã do banco; ou
  `BACKUP_DIR`, se configurado). `data/` é gitignored.
- **Retenção**: os **14** mais recentes; os mais antigos são apagados a cada rodada. Não mexe nos
  arquivos `painel-backup-*.db` do semanal.
- **Restaurar**: mesmo passo a passo de cima - pare o servidor, copie o `painel-AAAA-MM-DD.db`
  escolhido por cima de `data/painel.db` e suba de novo.
- **Resiliência**: erro de qualquer tipo só vai pro log, nunca derruba o app. O arquivo é
  escrito como temporário e só então trocado pelo definitivo.
