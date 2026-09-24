"""Sobe o app da worktree num banco TEMPORARIO (nunca o real) pra auditoria/fuzz visual da
faixa C3b (Viagens, Lugares, Cotacoes, Aviacao).

Uso: PORTA=5132 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-c3b-viagens/servidor.py

Dubles (nenhuma chamada de rede real sai do servidor):
  - geocode_nominatim.geocodificar -> coordenada sintetica fixa (mapa Leaflet tem o que desenhar)
  - clima.previsao_para_cidade_e_data -> previsao sintetica
  - metar.requests -> METAR/TAF sinteticos (ICAO "ZZZZ" devolve vazio)
  - voo_status nao configurado (sem chave) -> a tela mostra "configurar chave"
"""
import os
import sys
import tempfile
from pathlib import Path

repo = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, repo)
os.chdir(repo)
for k in ("TELEGRAM_BOT_TOKEN", "RENDER", "PAINEL_PIN_INICIAL", "VOO_STATUS_API_KEY"):
    os.environ.pop(k, None)
os.environ["ANTHROPIC_API_KEY"] = "sk-teste-falso"  # duble: nenhuma chamada real
import db  # noqa: E402

db.DB_PATH = Path(tempfile.mkdtemp(prefix="c3b-viagens-db-")) / "painel.db"
db.garantir_banco_nao_producao()

import clima  # noqa: E402
import geocode_nominatim  # noqa: E402
import metar  # noqa: E402


def _geo_falso(nome, cidade):
    if "naoexiste" in (nome or "").lower():
        return {"status": "nao_encontrado"}
    return {"status": "ok", "lat": -26.9194, "lng": -49.0661}


def _previsao_falsa(cidade, data_iso):
    return {"chuva_pct": 30, "temp_min": 17, "temp_max": 26, "cidade": cidade or "Cidade",
            "alerta_chuva": False, "lat": -26.9, "lon": -49.0}


class _Resp:
    def __init__(self, texto):
        self.text = texto
        self.status_code = 200

    def raise_for_status(self):
        return None


class _RequestsFalso:
    RequestException = Exception

    @staticmethod
    def get(url, params=None, timeout=None):
        icao = (params or {}).get("ids", "")
        if icao == "ZZZZ":
            return _Resp("")
        if "taf" in url.lower():
            return _Resp(f"TAF {icao} 241100Z 2412/2512 09008KT 9999 SCT030 BECMG 2418/2420 18012G22KT 6000 BKN015")
        return _Resp(f"METAR {icao} 241200Z 09008KT 9999 FEW030 BKN045 24/17 Q1015")


geocode_nominatim.geocodificar = _geo_falso
clima.previsao_para_cidade_e_data = _previsao_falsa
metar.requests = _RequestsFalso

import app  # noqa: E402

app.geocode_nominatim.geocodificar = _geo_falso
if hasattr(app, "clima"):
    app.clima.previsao_para_cidade_e_data = _previsao_falsa
from werkzeug.serving import make_server  # noqa: E402

srv = make_server("127.0.0.1", int(os.environ.get("PORTA", "5132")), app.app, threaded=True)
print("rodando", db.DB_PATH, flush=True)
srv.serve_forever()
