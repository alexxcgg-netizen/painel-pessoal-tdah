"""Sobe o app da worktree num banco TEMPORARIO (nunca o real) pra verificacao visual da C3a
(polimento da aba Vida). Mesmo padrao de scripts/ralph-v4-vida/servidor.py, com a trava de
rede pedida pelo integrador: NENHUMA chamada pode sair pra provedor de IA (nem com chave falsa).

Tres camadas:
1. Env: ANTHROPIC_BASE_URL/OPENAI_BASE_URL apontam pra 127.0.0.1:9 (porta descartada) e as
   chaves viram "teste-fake"; tokens de integracao (Telegram, Pluggy, Uber, Maps) sao apagados.
2. Proxy + socket: as variaveis *_proxy sao apagadas e qualquer connect() AF_INET/AF_INET6 pra
   fora do loopback (ou pra porta do proxy de saida do sandbox, que fica no loopback) e
   RECUSADO e registrado em stderr com o prefixo "SAIDA-BLOQUEADA" (auditar/fuzz contam).
3. No Playwright (comum.py), /api/summary/today e respondido por duble e toda requisicao do
   navegador pra fora de 127.0.0.1 e abortada.

Uso: PORTA=5131 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-c3a-vida/servidor.py <repo>
"""
import os
import socket
import sys
import tempfile
from pathlib import Path

repo = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2])
sys.path.insert(0, repo)
os.chdir(repo)

# ---- 1. env: provedores de IA apontando pra lugar nenhum, chaves falsas ----
for k in ("TELEGRAM_BOT_TOKEN", "RENDER", "PAINEL_PIN_INICIAL", "PLUGGY_CLIENT_ID", "PLUGGY_CLIENT_SECRET",
          "UBER_CLIENT_ID", "UBER_CLIENT_SECRET", "GOOGLE_MAPS_API_KEY", "MAPS_API_KEY"):
    os.environ.pop(k, None)
os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:9"
os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:9"
os.environ["ANTHROPIC_API_KEY"] = "teste-fake"
os.environ["OPENAI_API_KEY"] = "teste-fake"
os.environ["GEMINI_API_KEY"] = "teste-fake"

# O sandbox tem um proxy de saida NO LOOPBACK (HTTPS_PROXY=http://127.0.0.1:<porta>): liberar
# "so loopback" deixaria a chamada sair via proxy. Guarda as portas dos proxies, apaga as
# variaveis (o SDK nao usa proxy nenhum) e a trava abaixo recusa essas portas mesmo no loopback.
import re as _re  # noqa: E402

_PORTAS_PROXY = set()
for _k in list(os.environ):
    if "proxy" in _k.lower():
        _m = _re.search(r":(\d+)", os.environ[_k].split("//")[-1])
        if _m and "no_proxy" not in _k.lower():
            _PORTAS_PROXY.add(int(_m.group(1)))
        os.environ.pop(_k, None)

# ---- 2. socket: so loopback, e nunca a porta do proxy ----
_connect_original = socket.socket.connect
_connect_ex_original = socket.socket.connect_ex


def _checar(sock, endereco):
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return  # socket unix etc.
    host = endereco[0] if isinstance(endereco, tuple) else str(endereco)
    porta = endereco[1] if isinstance(endereco, tuple) and len(endereco) > 1 else None
    if (host in ("::1", "localhost") or host.startswith("127.")) and porta not in _PORTAS_PROXY:
        return
    print(f"SAIDA-BLOQUEADA {endereco!r}", file=sys.stderr, flush=True)
    raise ConnectionRefusedError(f"C3a: saida de rede bloqueada no servidor de teste ({endereco!r})")


def _connect(self, endereco):
    _checar(self, endereco)
    return _connect_original(self, endereco)


def _connect_ex(self, endereco):
    _checar(self, endereco)
    return _connect_ex_original(self, endereco)


socket.socket.connect = _connect
socket.socket.connect_ex = _connect_ex

import db  # noqa: E402

db.DB_PATH = Path(tempfile.mkdtemp(prefix="c3a-vida-db-")) / "painel.db"
db.garantir_banco_nao_producao()
import app  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

srv = make_server("127.0.0.1", int(os.environ.get("PORTA", "5131")), app.app, threaded=True)
print("rodando", db.DB_PATH, flush=True)
srv.serve_forever()
