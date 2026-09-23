"""US-F12 (Fase 6 F3): status de voo comercial por numero (atraso, portao,
terminal, horarios reais) - depois que o Alex ja COMPROU a passagem. Isso e
DIFERENTE do voo do aeroclube (aba Aviacao, `voos.py`/tabela `voos`) - aqui e
voo de companhia aerea, associado a uma viagem (`viagens.numero_voo`).

Escolha de API (pesquisada em 2026-09-23 via WebSearch, ver
tasks/fase6/progress-f3.txt pra comparacao completa e o que NAO foi
confirmado): AviationStack (https://aviationstack.com), plano gratuito.
- Sem cartao de credito pro cadastro gratuito (so email) - o unico dos
  pesquisados assim; e o motivo principal da escolha, ja que o Alex tem que
  criar a conta sozinho.
- 100 requisicoes gratis por mes (~3/dia). O cache local (CACHE_TTL abaixo)
  existe justamente pra nao estourar isso.
- LIMITACAO IMPORTANTE: o plano gratuito so aceita HTTP, nao HTTPS (a API
  devolve erro se tentar https:// sem plano pago) - a chave viaja sem
  criptografia na consulta. Aceitavel pra um app pessoal de baixo risco (nao
  e senha nem dado financeiro de empresa), mas o Alex precisa saber disso
  antes de colar a chave aqui - documentado tambem no .env.example.

Alternativas descartadas (ver progress-f3.txt pro raciocinio completo):
AeroDataBox (RapidAPI) tem limite maior (600 unidades/mes) e HTTPS de
verdade, mas o RapidAPI pede cartao de credito mesmo no plano gratuito
(trava de "eu, Claude, nao consigo criar conta por ele" do briefing - cartao
e uma decisao financeira que so o Alex toma). FlightAware AeroAPI (Personal,
$5 gratis/mes) e Amadeus Self-Service (encerrado em 2026-07-17, sem plano
gratuito mais) tambem descartados - ver o arquivo de progresso.

Sem AVIATIONSTACK_API_KEY no .env: `configurado()` volta False, e o
app.py devolve o card no modo manual ("status em tempo real: configurar
chave") sem chamar rede nenhuma."""

import json
import os
from datetime import datetime, timedelta

import requests

AVIATIONSTACK_URL = "http://api.aviationstack.com/v1/flights"  # HTTP mesmo (ver docstring do modulo)

# Cache por (numero_voo, data) - 100 req/mes gratis da AviationStack e
# ~3.3/dia; 3h de cache deixa consultar de novo algumas vezes no dia (ex: de
# manha e perto da hora do voo) sem estourar o limite mensal.
CACHE_TTL = timedelta(hours=3)

# flight_status da AviationStack -> chave interna (CSS/rotulo) + texto pt-BR.
_STATUS = {
    "scheduled": ("agendado", "Agendado"),
    "active": ("em_voo", "Em voo"),
    "landed": ("pousou", "Pousou"),
    "cancelled": ("cancelado", "Cancelado"),
    "incident": ("incidente", "Incidente"),
    "diverted": ("desviado", "Desviado"),
}


def configurado() -> bool:
    return bool(os.environ.get("AVIATIONSTACK_API_KEY"))


def _mapear_resposta(bruto: dict) -> dict:
    """AviationStack -> formato interno estavel (o card/front nunca le o
    JSON bruto da API direto, so isso aqui - se a API mudar campo, so muda
    esta funcao)."""
    voo = (bruto.get("data") or [{}])[0] if bruto.get("data") else {}
    partida = voo.get("departure") or {}
    chave, texto = _STATUS.get(voo.get("flight_status"), ("desconhecido", "Sem dado"))
    atraso = partida.get("delay")
    return {
        "status": chave,
        "status_texto": texto,
        "atraso_min": int(atraso) if isinstance(atraso, (int, float)) else None,
        "portao": partida.get("gate"),
        "terminal": partida.get("terminal"),
        "horario_partida_previsto": partida.get("scheduled"),
        "horario_partida_real": partida.get("actual"),
    }


def _buscar_na_api(numero_voo: str, data: str) -> dict:
    resp = requests.get(
        AVIATIONSTACK_URL,
        params={"access_key": os.environ["AVIATIONSTACK_API_KEY"], "flight_iata": numero_voo, "flight_date": data},
        timeout=10,
    )
    resp.raise_for_status()
    corpo = resp.json()
    if isinstance(corpo, dict) and corpo.get("error"):
        raise ValueError(corpo["error"].get("info") or "erro da API de status de voo")
    return _mapear_resposta(corpo if isinstance(corpo, dict) else {})


def status_voo(numero_voo: str, data: str, obter_cache, salvar_cache, agora: datetime | None = None) -> dict:
    """Cache-first: `obter_cache(numero_voo, data)` e `salvar_cache(numero_voo,
    data, json_str)` sao injetados (db.obter_status_voo_cache/salvar_status_voo_cache)
    pra este modulo nunca importar db.py nem tocar sqlite direto - so decide
    quando o cache esta velho e chama a API quando precisa. Sem chave
    configurada, nem tenta - devolve so `configurado: False` (modo manual)."""
    if not configurado():
        return {"configurado": False}

    numero_voo = (numero_voo or "").strip().upper()
    if not numero_voo:
        return {"configurado": True, "erro": "informe o numero do voo"}

    agora = agora or datetime.now()
    cache = obter_cache(numero_voo, data)
    if cache:
        buscado_em = datetime.fromisoformat(cache["buscado_em"])
        if agora - buscado_em < CACHE_TTL:
            resultado = json.loads(cache["resposta_json"])
            resultado["configurado"] = True
            resultado["cache"] = True
            resultado["buscado_em_texto"] = buscado_em.strftime("%H:%M")
            return resultado

    try:
        resultado = _buscar_na_api(numero_voo, data)
    except (requests.RequestException, ValueError, KeyError):
        if cache:  # rede falhou agora mas tinha algo salvo antes - melhor um dado velho que nada
            resultado = json.loads(cache["resposta_json"])
            resultado["configurado"] = True
            resultado["cache"] = True
            resultado["buscado_em_texto"] = datetime.fromisoformat(cache["buscado_em"]).strftime("%H:%M") + " (rede falhou agora)"
            return resultado
        return {"configurado": True, "erro": "nao consegui consultar o status do voo agora"}

    salvar_cache(numero_voo, data, json.dumps(resultado))
    resultado["configurado"] = True
    resultado["cache"] = False
    return resultado
