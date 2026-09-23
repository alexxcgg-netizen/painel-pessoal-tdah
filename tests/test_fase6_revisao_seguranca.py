"""Revisao independente da Fase 6 - achados 4, 7, 8, 10 e 11 (teto de IA,
limites de tamanho, ProxyFix, Nominatim com backoff, cache de erro da
AviationStack, boot no Render sem PIN).

IA/Nominatim/AviationStack sempre mockados - nunca API real. Padrao de
tests/test_pin_inicial.py: db.DB_PATH temporario + garantir_banco_nao_producao()
ANTES de importar app."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db
import geocode_nominatim
import voo_status

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"
USO = {"model": "claude-sonnet", "input_tokens": 10, "output_tokens": 10, "cost_usd": 0.001}
RAIZ = Path(__file__).resolve().parent.parent


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    def estourar_teto(self):
        conn = db.get_db()
        db.definir_teto_mensal_ia(conn, 1.0)
        db.record_usage(conn, "x", 1, 1, 50.0, "chat")
        conn.commit()
        conn.close()


# ---- achado 4: teto de IA + limites de tamanho ------------------------------

class TetoIAChatTestCase(_Base):
    def test_chat_com_teto_estourado_nao_chama_ia(self):
        self.estourar_teto()
        with patch("claude_client.chat", side_effect=AssertionError("IA nao pode ser chamada")):
            res = self.client.post("/api/chat", json={"mensagem": "me conta uma piada"})
        self.assertEqual(res.status_code, 402)
        self.assertIn("teto", res.get_json()["error"])

    def test_chat_com_teto_estourado_ainda_responde_consulta_local(self):
        self.estourar_teto()
        with patch("claude_client.chat", side_effect=AssertionError("caminho local, sem IA")):
            res = self.client.post("/api/chat", json={"mensagem": "me mostra meus habitos"})
        self.assertEqual(res.status_code, 200)

    def test_brain_dump_assistente_com_teto_estourado_nao_chama_ia_e_item_volta_pendente(self):
        res = self.client.post("/api/brain-dump", json={"texto": "tudo misturado"})
        item_id = res.get_json()["id"]
        self.estourar_teto()
        with patch("claude_client.chat", side_effect=AssertionError("IA nao pode ser chamada")):
            res = self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "assistente"})
        self.assertEqual(res.status_code, 402)
        conn = db.get_db()
        self.assertFalse(db.obter_brain_dump(conn, item_id)["processado"])
        conn.close()

    def test_telegram_com_teto_estourado_devolve_aviso_sem_chamar_ia(self):
        self.estourar_teto()
        with patch("claude_client.chat", side_effect=AssertionError("IA nao pode ser chamada")):
            resposta = app._telegram_chat_fn("me conta uma piada")
        self.assertIn("teto", resposta)

    def test_abaixo_do_teto_chat_continua_normal(self):
        with patch("claude_client.chat", return_value=("oi!", [], USO)) as mock_chat:
            res = self.client.post("/api/chat", json={"mensagem": "me conta uma piada"})
        self.assertEqual(res.status_code, 200)
        mock_chat.assert_called_once()


class TamanhoTextoTestCase(_Base):
    def test_chat_acima_do_limite_e_400_sem_chamar_ia(self):
        texto = "x" * (app.TAMANHO_MAX_TEXTO_CHAT + 1)
        with patch("claude_client.chat", side_effect=AssertionError("IA nao pode ser chamada")):
            res = self.client.post("/api/chat", json={"mensagem": texto})
        self.assertEqual(res.status_code, 400)
        self.assertIn(str(app.TAMANHO_MAX_TEXTO_CHAT), res.get_json()["error"])

    def test_chat_no_limite_exato_passa(self):
        texto = "y" * app.TAMANHO_MAX_TEXTO_CHAT
        with patch("claude_client.chat", return_value=("ok", [], USO)):
            res = self.client.post("/api/chat", json={"mensagem": texto})
        self.assertEqual(res.status_code, 200)

    def test_brain_dump_acima_do_limite_e_400_e_nao_grava(self):
        res = self.client.post("/api/brain-dump", json={"texto": "z" * (app.TAMANHO_MAX_TEXTO_CHAT + 1)})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.get("/api/brain-dump").get_json(), [])

    def test_telegram_acima_do_limite_nao_chama_ia(self):
        with patch("claude_client.chat", side_effect=AssertionError("IA nao pode ser chamada")):
            resposta = app._telegram_chat_fn("w" * (app.TAMANHO_MAX_TEXTO_CHAT + 1))
        self.assertIn(str(app.TAMANHO_MAX_TEXTO_CHAT), resposta)

    def test_max_content_length_barra_corpo_gigante_com_413_json(self):
        self.assertEqual(app.app.config["MAX_CONTENT_LENGTH"], 20 * 1024 * 1024)
        corpo = json.dumps({"mensagem": "a" * (21 * 1024 * 1024)})
        res = self.client.post("/api/chat", data=corpo, content_type="application/json")
        self.assertEqual(res.status_code, 413)
        self.assertIn("error", res.get_json())

    def test_foto_de_nota_fiscal_de_10mb_em_base64_ainda_cabe(self):
        # maior upload legitimo em JSON: 10MB de imagem em base64 (~13,4MB)
        import base64

        imagem = base64.b64encode(b"\xff" * (10 * 1024 * 1024)).decode("ascii")
        dados = {"valor": 10.0, "estabelecimento": "x", "data": None}
        with patch("claude_client.extrair_nota_fiscal_foto", return_value=(dados, USO)):
            res = self.client.post(
                "/api/notas-fiscais/extrair", json={"imagem_base64": imagem, "media_type": "image/jpeg"}
            )
        self.assertEqual(res.status_code, 200, res.get_json())

    def test_pdf_de_15mb_multipart_ainda_cabe(self):
        import io

        conn = db.get_db()
        cotacao_id = db.criar_cotacao(conn, "portas")
        conn.commit()
        conn.close()
        dados = {"fornecedor": "x", "valor": 10.0, "prazo": None, "observacao": None}
        with patch("claude_client.extrair_item_cotacao_pdf", return_value=(dados, USO)):
            res = self.client.post(
                f"/api/cotacoes/{cotacao_id}/itens/pdf",
                data={"arquivo": (io.BytesIO(b"%PDF" + b"0" * (15 * 1024 * 1024 - 8)), "orc.pdf")},
                content_type="multipart/form-data",
            )
        self.assertNotEqual(res.status_code, 413)


# ---- achado 7: ProxyFix so com PAINEL_ATRAS_DE_PROXY ------------------------

class ProxyFixTestCase(_Base):
    def setUp(self):
        super().setUp()
        self._wsgi_original = app.app.wsgi_app

    def tearDown(self):
        app.app.wsgi_app = self._wsgi_original

    def _errar_5_vezes(self, cliente, ip):
        for _ in range(5):
            cliente.post("/login", json={"pin": "000000"}, headers={"X-Forwarded-For": ip})

    def test_atras_de_proxy_bloqueio_e_por_ip_real_do_cliente(self):
        app.app.wsgi_app = app._configurar_proxy(self._wsgi_original, {"PAINEL_ATRAS_DE_PROXY": "1"})
        atacante = app.app.test_client()
        self._errar_5_vezes(atacante, "203.0.113.9")
        bloqueado = atacante.post("/login", json={"pin": PIN_TESTE}, headers={"X-Forwarded-For": "203.0.113.9"})
        self.assertEqual(bloqueado.status_code, 429)
        alex = app.app.test_client()
        res = alex.post("/login", json={"pin": PIN_TESTE}, headers={"X-Forwarded-For": "198.51.100.7"})
        self.assertEqual(res.status_code, 200)  # o Alex (outro IP) nao ficou trancado

    def test_sem_a_variavel_x_forwarded_for_e_ignorado(self):
        app.app.wsgi_app = app._configurar_proxy(self._wsgi_original, {})
        self.assertIs(app.app.wsgi_app, self._wsgi_original)
        atacante = app.app.test_client()
        self._errar_5_vezes(atacante, "203.0.113.9")
        # trocar o cabecalho nao foge do bloqueio quando nao ha proxy confiavel
        res = atacante.post("/login", json={"pin": PIN_TESTE}, headers={"X-Forwarded-For": "198.51.100.7"})
        self.assertEqual(res.status_code, 429)

    def test_valores_da_variavel(self):
        for ligado in ("1", "true", "TRUE", "sim", "yes"):
            self.assertIsNot(app._configurar_proxy(self._wsgi_original, {"PAINEL_ATRAS_DE_PROXY": ligado}), self._wsgi_original)
        for desligado in ("", "0", "false", "nao"):
            self.assertIs(app._configurar_proxy(self._wsgi_original, {"PAINEL_ATRAS_DE_PROXY": desligado}), self._wsgi_original)

    def test_render_yaml_e_env_example_documentam_a_variavel(self):
        self.assertIn("PAINEL_ATRAS_DE_PROXY", (RAIZ / "render.yaml").read_text())
        self.assertIn("PAINEL_ATRAS_DE_PROXY", (RAIZ / ".env.example").read_text())
        self.assertIn("PAINEL_ATRAS_DE_PROXY", (RAIZ / "deploy" / "DEPLOY.md").read_text())


# ---- achado 11: Render sem PIN nao sobe --------------------------------------

class RenderSemPinTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_render_sem_pin_derruba(self):
        with self.assertRaises(RuntimeError) as ctx:
            app._exigir_pin_em_hospedagem_publica(self.conn, {"RENDER": "true"})
        self.assertIn("PAINEL_PIN_INICIAL", str(ctx.exception))

    def test_render_com_pin_sobe(self):
        auth.definir_pin(self.conn, PIN_TESTE, PIN_TESTE)
        self.conn.commit()
        app._exigir_pin_em_hospedagem_publica(self.conn, {"RENDER": "true"})

    def test_fora_do_render_sem_pin_sobe_normal(self):
        app._exigir_pin_em_hospedagem_publica(self.conn, {})

    def _importar_app_num_processo(self, env_extra):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        codigo = (
            "import db; from pathlib import Path; "
            f"db.DB_PATH = Path({str(Path(tmp.name) / 'painel.db')!r}); "
            "db.garantir_banco_nao_producao(); import app"
        )
        env = {k: v for k, v in os.environ.items() if k not in ("RENDER", "PAINEL_PIN_INICIAL")}
        env.update({"ANTHROPIC_API_KEY": "teste-fake", **env_extra})
        return subprocess.run(
            [sys.executable, "-c", codigo], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=120
        )

    def test_boot_real_no_render_sem_pin_falha_com_erro_claro(self):
        r = self._importar_app_num_processo({"RENDER": "true"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("PAINEL_PIN_INICIAL", r.stderr)

    def test_boot_real_no_render_com_pin_inicial_sobe(self):
        r = self._importar_app_num_processo({"RENDER": "true", "PAINEL_PIN_INICIAL": "482913"})
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])


# ---- achado 8: Nominatim com backoff ----------------------------------------

class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self._payload


class GeocodeStatusHTTPTestCase(unittest.TestCase):
    def setUp(self):
        geocode_nominatim._ultima_chamada = 0.0

    def test_403_e_400_sao_recusa_definitiva(self):
        for status in (400, 403, 404):
            with patch("geocode_nominatim.requests.get", return_value=FakeResp({}, status)):
                self.assertEqual(geocode_nominatim.geocodificar("X", "Y")["status"], "recusado", status)

    def test_429_e_5xx_sao_erro_temporario(self):
        for status in (429, 500, 503):
            with patch("geocode_nominatim.requests.get", return_value=FakeResp({}, status)):
                self.assertEqual(geocode_nominatim.geocodificar("X", "Y")["status"], "erro", status)

    def test_timeout_curto(self):
        with patch("geocode_nominatim.requests.get", return_value=FakeResp([])) as mock_get:
            geocode_nominatim.geocodificar("X", "Y")
        self.assertLessEqual(mock_get.call_args.kwargs["timeout"], 4)


class LugaresBackoffTestCase(_Base):
    def _criar(self, nome):
        conn = db.get_db()
        lugar_id = db.create_lugar(conn, nome, "Cidade", None, None)
        conn.close()
        return lugar_id

    def _lugar(self, lugar_id):
        conn = db.get_db()
        row = conn.execute("SELECT * FROM lugares WHERE id = ?", (lugar_id,)).fetchone()
        conn.close()
        return dict(row)

    def test_erro_de_rede_grava_e_nao_repete_a_cada_get(self):
        lugar_id = self._criar("Cafe")
        with patch("app.geocode_nominatim.geocodificar", return_value={"status": "erro"}) as mock_geo:
            for _ in range(5):
                self.assertEqual(self.client.get("/api/lugares").status_code, 200)
        self.assertEqual(mock_geo.call_count, 1)  # antes: 5 chamadas (1 por GET)
        lugar = self._lugar(lugar_id)
        self.assertEqual(lugar["geocode_status"], "erro")
        self.assertTrue(lugar["geocode_tentar_depois"])

    def test_depois_da_janela_tenta_de_novo(self):
        lugar_id = self._criar("Cafe")
        with patch("app.geocode_nominatim.geocodificar", return_value={"status": "erro"}):
            self.client.get("/api/lugares")
        depois = datetime.utcnow() + app.GEOCODE_ESPERA_APOS_ERRO + timedelta(minutes=1)
        with patch("app._agora_utc", return_value=depois), \
             patch("app.geocode_nominatim.geocodificar", return_value={"status": "ok", "lat": 1.0, "lng": 2.0}) as mock_geo:
            lugares = self.client.get("/api/lugares").get_json()
        mock_geo.assert_called_once()
        self.assertEqual(next(l for l in lugares if l["id"] == lugar_id)["geocode_status"], "ok")

    def test_recusa_4xx_e_definitiva(self):
        lugar_id = self._criar("Cafe")
        with patch("app.geocode_nominatim.geocodificar", return_value={"status": "recusado"}):
            self.client.get("/api/lugares")
        depois = datetime.utcnow() + timedelta(days=30)
        with patch("app._agora_utc", return_value=depois), patch("app.geocode_nominatim.geocodificar") as mock_geo:
            self.client.get("/api/lugares")
        mock_geo.assert_not_called()
        self.assertEqual(self._lugar(lugar_id)["geocode_status"], "recusado")

    def test_no_maximo_1_geocode_por_get_mesmo_com_varios_pendentes(self):
        for i in range(4):
            self._criar(f"Lugar {i}")
        with patch("app.geocode_nominatim.geocodificar", return_value={"status": "erro"}) as mock_geo:
            self.client.get("/api/lugares")
        self.assertEqual(mock_geo.call_count, 1)


# ---- achado 10: AviationStack cacheia erro -----------------------------------

class VooStatusErroCacheTestCase(unittest.TestCase):
    def _cache_mem(self):
        armazenado = {}

        def obter(numero_voo, data):
            return armazenado.get((numero_voo, data))

        def salvar(numero_voo, data, resposta_json):
            armazenado[(numero_voo, data)] = {"resposta_json": resposta_json, "buscado_em": datetime.now().isoformat()}

        return obter, salvar

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_erro_fica_em_cache_e_nao_gasta_cota_de_novo(self):
        import requests

        obter, salvar = self._cache_mem()
        agora = datetime.now()
        with patch("voo_status.requests.get", side_effect=requests.RequestException("timeout")) as mock_get:
            r1 = voo_status.status_voo("LA3251", "2026-12-25", obter, salvar, agora=agora)
            r2 = voo_status.status_voo("LA3251", "2026-12-25", obter, salvar, agora=agora + timedelta(minutes=10))
        self.assertEqual(mock_get.call_count, 1)  # antes: 2 (cada visita gastava cota)
        self.assertIn("erro", r1)
        self.assertIn("erro", r2)

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_depois_de_30_min_tenta_de_novo(self):
        import requests

        obter, salvar = self._cache_mem()
        agora = datetime.now()
        with patch("voo_status.requests.get", side_effect=requests.RequestException("timeout")):
            voo_status.status_voo("LA3251", "2026-12-25", obter, salvar, agora=agora)
        payload = {"data": [{"flight_status": "scheduled", "departure": {}}]}
        with patch("voo_status.requests.get", return_value=FakeResp(payload)) as mock_get:
            r = voo_status.status_voo(
                "LA3251", "2026-12-25", obter, salvar, agora=agora + voo_status.CACHE_TTL_ERRO + timedelta(minutes=1)
            )
        mock_get.assert_called_once()
        self.assertEqual(r["status"], "agendado")

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_erro_com_dado_bom_anterior_mostra_o_anterior_sem_perder(self):
        import requests

        obter, salvar = self._cache_mem()
        agora = datetime.now()
        payload = {"data": [{"flight_status": "active", "departure": {"gate": "12"}}]}
        with patch("voo_status.requests.get", return_value=FakeResp(payload)):
            voo_status.status_voo("LA3251", "2026-12-25", obter, salvar, agora=agora)
        depois = agora + voo_status.CACHE_TTL + timedelta(minutes=1)
        with patch("voo_status.requests.get", side_effect=requests.RequestException("timeout")) as mock_get:
            r1 = voo_status.status_voo("LA3251", "2026-12-25", obter, salvar, agora=depois)
            r2 = voo_status.status_voo("LA3251", "2026-12-25", obter, salvar, agora=depois + timedelta(minutes=5))
        self.assertEqual(mock_get.call_count, 1)
        for r in (r1, r2):
            self.assertEqual(r["status"], "em_voo")
            self.assertEqual(r["portao"], "12")
            self.assertTrue(r["cache"])
            self.assertIn("rede falhou", r["buscado_em_texto"])
            self.assertFalse(any(k.startswith("_") for k in r))


if __name__ == "__main__":
    unittest.main()
