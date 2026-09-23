# Hospedar o painel numa VPS (pra push funcionar no iPhone de verdade)

`http://localhost:5001` só serve pra testar no seu próprio computador. Pro iPhone
instalar como app de verdade e receber notificação push, o painel precisa estar
num domínio com HTTPS, sempre ligado - ver a seção "Notificações" e "Calendário"
do `README.md` pra entender por quê. Isso aqui é o passo a passo.

Leva uns 30-40min a primeira vez. Depois de pronto, atualizar é só `git pull` +
reiniciar o serviço (passo final).

## 0. Antes de começar - segurança

O painel agora tem login próprio por PIN de 6 dígitos (ver `auth.py`) - na
primeira vez que você abrir o site ele pede pra você escolher o PIN, fica
travado depois de 5 tentativas erradas (5min de bloqueio), e o cookie de
sessão é assinado e `HttpOnly` (inspecionar/console do navegador não dá
acesso). Isso já é suficiente pra proteger o painel sozinho.

O `Caddyfile` deste diretório também tem uma segunda camada (HTTP Basic
Auth) - opcional agora, mas ainda vale a pena como defesa extra (bloqueia
antes mesmo de chegar na página de login). Se não quiser essa camada a
mais, pode remover o bloco `basicauth` do Caddyfile depois do passo 6.

**Não esquece do passo 5**: seta `SECURE_COOKIES=true` no `.env` assim que
o domínio com HTTPS estiver no ar, senão o cookie de sessão não é marcado
como seguro.

## 1. Escolhe uma VPS

Qualquer uma serve - o painel é leve (Flask + SQLite, um processo só). Não precisa
de nada além do plano mais barato:

- **Hetzner Cloud** - o mais barato (~€4/mês), servidores na Europa
- **DigitalOcean** - bem documentado, muito tutorial em português (~$6/mês)
- **Vultr / Linode** - equivalentes ao DigitalOcean

Escolhe a imagem **Ubuntu 22.04** (ou mais nova) em qualquer um deles. Anota o
endereço IP que ele te dá.

## 2. Domínio

Precisa de um domínio (ou subdomínio) apontando pro IP da VPS - é o que permite o
HTTPS automático. Se já tem um domínio (registro.br, Namecheap, etc.), cria um
registro **A** tipo:

```
painel.seudominio.com  ->  (IP da VPS)
```

Se não tem domínio nenhum, um subdomínio de um serviço gratuito tipo DuckDNS
também funciona pro Caddy gerar HTTPS.

## 3. Conecta na VPS e instala o basico

```bash
ssh root@SEU_IP

adduser painel               # usuario proprio pro app, nao roda como root
usermod -aG sudo painel
su - painel

sudo apt update
sudo apt install -y python3-venv python3-pip git
```

## 4. Clona o projeto e instala as dependencias

```bash
cd ~
git clone https://github.com/alexxcgg-netizen/painel-pessoal-tdah
cd painel-pessoal-tdah

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 5. Configura o `.env` e a chave do push

```bash
cp .env.example .env
nano .env   # preenche ANTHROPIC_API_KEY e as outras chaves que voce ja usa
```

Preenche **`SAUDE_WEBHOOK_TOKEN`** com alguma string aleatoria longa - o próprio
`.env.example` já avisa que isso é obrigatório assim que o painel fica público
(protege o endpoint que recebe dados de Saúde do Atalho do iPhone).

Preenche também **`PAINEL_ATRAS_DE_PROXY=1`** - o Caddy (passo 6) fica na
frente do app como proxy reverso, e sem isso o bloqueio de 5 PINs errados
seria pelo IP do próprio Caddy (qualquer pessoa errando o PIN trancaria você
junto). Só vale ligar com o Caddy na frente - rodando direto sem proxy,
deixa comentada.

Deixa **`SECURE_COOKIES=true`** já preenchido (assim que o domínio com HTTPS
estiver no ar no passo 8, o cookie de sessão do login passa a exigir HTTPS -
correto pra produção, só ficaria `false` se você estivesse testando local em
`http://`).

O arquivo `vapid_private.pem` (chave do push) **não vai pro git** - copia ele do
seu computador pra VPS direto:

```bash
# no SEU COMPUTADOR, nao na VPS:
scp vapid_private.pem painel@SEU_IP:~/painel-pessoal-tdah/
```

Se ainda não gerou as chaves de push, roda `python scripts/gerar_chaves_push.py`
direto na VPS (mais simples que gerar local e copiar).

### Testa antes de virar serviço

```bash
gunicorn -w 1 -b 127.0.0.1:5001 wsgi:app
```

Se aparecer erro, é mais fácil de ler rodando na mão do que procurando depois nos
logs do systemd. Só continua pro próximo passo quando isso subir sem erro
(`Ctrl+C` pra parar).

## 6. Instala o Caddy (HTTPS automatico)

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

Gera o hash da senha que vai proteger o painel (**guarda a senha em texto puro em
algum lugar seguro tipo um gerenciador de senhas** - o hash não dá pra reverter):

```bash
caddy hash-password
```

Copia esse `deploy/Caddyfile` pro lugar certo, troca `seu-dominio.com` pelo seu
domínio de verdade, `seu-usuario` por um usuário à sua escolha, e cola o hash que
o comando acima devolveu no lugar do hash de exemplo:

```bash
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile   # ajusta dominio, usuario e hash
sudo systemctl reload caddy
```

## 7. Instala o painel como servico (fica ligado sozinho, reinicia se cair)

```bash
sudo cp deploy/painel.service /etc/systemd/system/painel.service
sudo nano /etc/systemd/system/painel.service   # confere User= e WorkingDirectory=
sudo systemctl daemon-reload
sudo systemctl enable --now painel
sudo systemctl status painel   # deve aparecer "active (running)"
```

## 8. Confere que funcionou

Abre `https://SEU_DOMINIO` num navegador qualquer - se deixou o `basicauth` no
Caddyfile, pede usuário/senha primeiro; depois cai na tela "Primeiro acesso"
pra você escolher seu PIN de 6 dígitos (só essa primeira vez). Confirma que
apareceu o cadeado de HTTPS.

## 9. No iPhone

1. Abre `https://SEU_DOMINIO` no **Safari** (tem que ser Safari, não Chrome)
2. Se pedir usuário/senha do Basic Auth, entra; depois digita seu PIN de
   6 dígitos (ou escolhe um, se for a primeira vez)
3. Toca em Compartilhar → "Adicionar à Tela de Início"
4. Abre o painel **pelo ícone na tela de início** (não pela aba do Safari)
5. Dentro do app instalado, toca em "Ativar notificações" e aceita a permissão

## 10. Backup do banco

`data/painel.db` é o único dado que importa de verdade (o resto é código, já está
no git). Um jeito simples de não perder nada - roda isso periodicamente (cron) ou
manualmente de vez em quando:

```bash
# do SEU COMPUTADOR, baixa uma copia:
scp painel@SEU_IP:~/painel-pessoal-tdah/data/painel.db ~/backups/painel-$(date +%F).db
```

## Atualizando depois de mudanças no código

```bash
ssh painel@SEU_IP
cd painel-pessoal-tdah
git pull
source .venv/bin/activate
pip install -r requirements.txt   # so se mudou alguma dependencia
sudo systemctl restart painel
```

## Esqueci o PIN

Não tem "esqueci minha senha" pelo navegador de propósito (seria um jeito de
contornar o próprio login). Se esquecer, entra na VPS e roda:

```bash
ssh painel@SEU_IP
cd painel-pessoal-tdah
source .venv/bin/activate
python scripts/resetar_pin.py
```

Da próxima vez que abrir o painel, ele pede pra escolher um PIN novo.
