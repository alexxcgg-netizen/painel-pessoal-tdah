"""Voz premium (ElevenLabs): frases curtas, sintetizar (cache/limite/erros) e
rotas /api/voz/*. Nenhuma chamada real: requests.post e mockado; banco
temporario; a chave/voz vem so do os.environ do teste (nunca do .env)."""

import os
import random
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import voz_premium  # noqa: E402

PIN = "123456"
HOJE = date(2026, 9, 28)
AMANHA = HOJE + timedelta(days=1)
ENV_OK = {"ELEVENLABS_API_KEY": "chave-fake", "ELEVENLABS_VOICE_ID": "voz-fake"}


class _Resp:
    def __init__(self, status=200, content=b"MP3DATA"):
        self.status_code = status
        self.content = content


def _limpar_env():
    for k in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "ELEVENLABS_MODELO", "ELEVENLABS_LIMITE_MES"):
        os.environ.pop(k, None)


class _Base(unittest.TestCase):
    def setUp(self):
        _limpar_env()
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN, PIN)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        _limpar_env()

    def tarefa(self, titulo, due=None, hora=None, feita=None):
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES (?, ?, ?, ?)",
            (titulo, due.isoformat() if due else None, hora, feita),
        )
        self.conn.commit()


class TestFrases(_Base):
    def test_manha_zero(self):
        self.assertEqual(
            voz_premium.frase_curta_manha(self.conn, HOJE),
            "Bom dia, Alex. Nada marcado pra hoje. Dá uma olhada no painel.",
        )

    def test_manha_uma_singular(self):
        self.tarefa("ligar pro fornecedor", HOJE, "09:00")
        f = voz_premium.frase_curta_manha(self.conn, HOJE)
        self.assertIn("só 1 tarefa", f)
        self.assertIn("ligar pro fornecedor às 9h", f)

    def test_manha_varias_ordenadas_por_hora(self):
        self.tarefa("sem hora", HOJE)
        self.tarefa("tarde", HOJE, "14:30")
        self.tarefa("ligar pro fornecedor", HOJE, "09:00")
        self.tarefa("outro dia", AMANHA, "08:00")
        self.tarefa("ja feita", HOJE, "07:00", feita="2026-09-28 06:00:00")
        f = voz_premium.frase_curta_manha(self.conn, HOJE)
        self.assertEqual(
            f,
            "Bom dia, Alex. Hoje são 3 tarefas, a primeira é ligar pro fornecedor às 9h. O resto tá no painel.",
        )
        self.assertLessEqual(len(f), 130)

    def test_manha_hora_com_minutos_e_sem_hora(self):
        self.tarefa("reuniao", HOJE, "14:05")
        self.assertIn("às 14h05", voz_premium.frase_curta_manha(self.conn, HOJE))
        self.tarefa("x", HOJE)
        self.conn.execute("DELETE FROM tasks WHERE title='reuniao'")
        self.conn.commit()
        self.assertNotIn(" às ", voz_premium.frase_curta_manha(self.conn, HOJE))

    def test_manha_titulo_longo_cortado(self):
        self.tarefa("a" * 200, HOJE)
        f = voz_premium.frase_curta_manha(self.conn, HOJE)
        self.assertIn("a" * 60, f)
        self.assertNotIn("a" * 61, f)

    def test_manha_ignora_modelo_recorrente_e_hora_invalida(self):
        self.conn.execute("INSERT INTO tasks (title, recorrencia) VALUES ('modelo', 'seg')")
        self.tarefa("t", HOJE, "lixo")
        f = voz_premium.frase_curta_manha(self.conn, HOJE)
        self.assertIn("só 1 tarefa: t.", f)

    def test_noite(self):
        for i in range(4):
            self.tarefa(f"c{i}", HOJE, feita="2026-09-28 10:00:00")
        self.tarefa("p1", HOJE)
        self.tarefa("p2", HOJE)
        self.tarefa("revisar orçamento", AMANHA, "08:00")
        self.tarefa("depois", AMANHA)
        f = voz_premium.frase_curta_noite(self.conn, HOJE)
        self.assertEqual(
            f, "Fechou 4 de 6 hoje. Amanhã começa com revisar orçamento. O resto tá no painel."
        )

    def test_noite_sem_amanha_e_sem_nada(self):
        self.assertEqual(
            voz_premium.frase_curta_noite(self.conn, HOJE),
            "Hoje não tinha nada marcado. O resto tá no painel.",
        )
        self.tarefa("p", HOJE)
        f = voz_premium.frase_curta_noite(self.conn, HOJE)
        self.assertEqual(f, "Fechou 0 de 1 hoje. O resto tá no painel.")
        self.assertNotIn("Amanhã", f)


class TestSintetizar(_Base):
    def setUp(self):
        super().setUp()
        os.environ.update(ENV_OK)

    def _post(self, resp=None, **kw):
        return mock.patch.object(voz_premium.requests, "post", return_value=resp or _Resp(), **kw)

    def test_sem_config_nao_chama(self):
        for faltando in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID"):
            _limpar_env()
            os.environ.update(ENV_OK)
            del os.environ[faltando]
            self.assertFalse(voz_premium.configurado())
            with self._post() as p:
                self.assertIsNone(voz_premium.sintetizar(self.conn, "oi"))
            p.assert_not_called()

    def test_payload(self):
        with self._post() as p:
            self.assertEqual(voz_premium.sintetizar(self.conn, "Bom dia, Alex."), b"MP3DATA")
        args, kw = p.call_args
        self.assertEqual(args[0], "https://api.elevenlabs.io/v1/text-to-dialogue")
        self.assertEqual(kw["params"], {"output_format": "mp3_44100_64"})
        self.assertEqual(kw["headers"], {"xi-api-key": "chave-fake"})
        self.assertEqual(
            kw["json"],
            {"inputs": [{"text": "Bom dia, Alex.", "voice_id": "voz-fake"}], "model_id": "eleven_v4_turbo"},
        )
        self.assertEqual(kw["timeout"], 15)

    def test_modelo_por_env(self):
        os.environ["ELEVENLABS_MODELO"] = "outro_modelo"
        with self._post() as p:
            voz_premium.sintetizar(self.conn, "oi")
        self.assertEqual(p.call_args.kwargs["json"]["model_id"], "outro_modelo")

    def test_cache_nao_chama_nem_soma(self):
        with self._post() as p:
            a = voz_premium.sintetizar(self.conn, "oi Alex")
            b = voz_premium.sintetizar(self.conn, "oi Alex")
        self.assertEqual(a, b)
        self.assertEqual(p.call_count, 1)
        self.assertEqual(voz_premium.uso_do_mes(self.conn), len("oi Alex"))

    def test_cache_separa_por_voz(self):
        with self._post() as p:
            voz_premium.sintetizar(self.conn, "oi")
            os.environ["ELEVENLABS_VOICE_ID"] = "outra"
            voz_premium.sintetizar(self.conn, "oi")
        self.assertEqual(p.call_count, 2)

    def test_limite_bloqueia_antes_de_chamar(self):
        os.environ["ELEVENLABS_LIMITE_MES"] = "10"
        with self._post() as p:
            self.assertIsNotNone(voz_premium.sintetizar(self.conn, "123456"))  # 6
            self.assertIsNone(voz_premium.sintetizar(self.conn, "abcde"))  # 6+5 > 10
            self.assertIsNotNone(voz_premium.sintetizar(self.conn, "abcd"))  # 6+4 = 10
        self.assertEqual(p.call_count, 2)
        self.assertEqual(voz_premium.uso_do_mes(self.conn), 10)

    def test_limite_cache_ainda_serve_com_limite_estourado(self):
        with self._post():
            voz_premium.sintetizar(self.conn, "oi")
        os.environ["ELEVENLABS_LIMITE_MES"] = "0"
        with self._post() as p:
            self.assertEqual(voz_premium.sintetizar(self.conn, "oi"), b"MP3DATA")
        p.assert_not_called()

    def test_limite_invalido_usa_padrao(self):
        os.environ["ELEVENLABS_LIMITE_MES"] = "abc"
        self.assertEqual(voz_premium.limite_mes(), 9000)

    def test_virada_de_mes_zera(self):
        os.environ["ELEVENLABS_LIMITE_MES"] = "5"
        with mock.patch.object(voz_premium, "mes_atual", return_value="2026-08"):
            with self._post():
                self.assertIsNotNone(voz_premium.sintetizar(self.conn, "12345"))
                self.assertIsNone(voz_premium.sintetizar(self.conn, "abcde"))
        with mock.patch.object(voz_premium, "mes_atual", return_value="2026-09"):
            with self._post():
                self.assertIsNotNone(voz_premium.sintetizar(self.conn, "abcde"))
            self.assertEqual(voz_premium.uso_do_mes(self.conn, "2026-09"), 5)

    def test_erros_devolvem_none_sem_somar(self):
        casos = [_Resp(400), _Resp(401), _Resp(429), _Resp(500), _Resp(200, b"")]
        for resp in casos:
            with self._post(resp):
                self.assertIsNone(voz_premium.sintetizar(self.conn, "oi"))
        with mock.patch.object(voz_premium.requests, "post", side_effect=ConnectionError("x")):
            self.assertIsNone(voz_premium.sintetizar(self.conn, "oi"))
        with mock.patch.object(voz_premium.requests, "post", side_effect=TimeoutError()):
            self.assertIsNone(voz_premium.sintetizar(self.conn, "oi"))
        self.assertEqual(voz_premium.uso_do_mes(self.conn), 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) n FROM voz_cache").fetchone()["n"], 0)

    def test_erro_nao_loga_chave(self):
        with self.assertLogs("voz_premium", level="WARNING") as cap:
            with self._post(_Resp(401)):
                voz_premium.sintetizar(self.conn, "oi")
        self.assertNotIn("chave-fake", "\n".join(cap.output))

    def test_texto_invalido(self):
        with self._post() as p:
            for t in ("", "   ", "x" * 301, None, 5, ["a"]):
                self.assertIsNone(voz_premium.sintetizar(self.conn, t))
            self.assertIsNotNone(voz_premium.sintetizar(self.conn, "x" * 300))
        self.assertEqual(p.call_count, 1)


class TestRotas(_Base):
    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()
        r = self.client.post("/login", json={"pin": PIN})
        self.assertEqual(r.status_code, 200)

    def test_exige_login(self):
        c = app.app.test_client()
        for metodo, url in (("get", "/api/voz/frase?momento=manha"), ("post", "/api/voz/falar"), ("get", "/api/voz/uso")):
            r = getattr(c, metodo)(url, json={"texto": "oi"}) if metodo == "post" else c.get(url)
            self.assertIn(r.status_code, (401, 302, 403), (url, r.status_code))

    def test_frase(self):
        for m in ("manha", "noite"):
            r = self.client.get(f"/api/voz/frase?momento={m}")
            self.assertEqual(r.status_code, 200)
            j = r.get_json()
            self.assertIsInstance(j["texto"], str)
            self.assertFalse(j["premium"])
        os.environ.update(ENV_OK)
        self.assertTrue(self.client.get("/api/voz/frase?momento=manha").get_json()["premium"])

    def test_frase_momento_invalido(self):
        for q in ("", "?momento=tarde", "?momento=", "?momento=MANHA"):
            r = self.client.get("/api/voz/frase" + q)
            self.assertEqual(r.status_code, 400, q)
            self.assertIn("erro", r.get_json())

    def test_falar_200_audio(self):
        os.environ.update(ENV_OK)
        with mock.patch.object(voz_premium.requests, "post", return_value=_Resp()):
            r = self.client.post("/api/voz/falar", json={"texto": "Bom dia"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "audio/mpeg")
        self.assertEqual(r.data, b"MP3DATA")

    def test_falar_204(self):
        r = self.client.post("/api/voz/falar", json={"texto": "Bom dia"})  # sem config
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r.data, b"")
        os.environ.update(ENV_OK)
        with mock.patch.object(voz_premium.requests, "post", return_value=_Resp(500)):
            self.assertEqual(self.client.post("/api/voz/falar", json={"texto": "Bom dia"}).status_code, 204)
        os.environ["ELEVENLABS_LIMITE_MES"] = "1"
        with mock.patch.object(voz_premium.requests, "post") as p:
            self.assertEqual(self.client.post("/api/voz/falar", json={"texto": "Bom dia"}).status_code, 204)
        p.assert_not_called()

    def test_falar_400(self):
        casos = [
            dict(data="{nao json", content_type="application/json"),
            dict(data="", content_type="application/json"),
            dict(json={}),
            dict(json={"texto": 5}),
            dict(json={"texto": ["a"]}),
            dict(json={"texto": None}),
            dict(json={"texto": "   "}),
            dict(json={"texto": "x" * 301}),
            dict(json=[1, 2]),
            dict(json="texto solto"),
        ]
        for kw in casos:
            r = self.client.post("/api/voz/falar", **kw)
            self.assertEqual(r.status_code, 400, kw)

    def test_uso(self):
        os.environ.update(ENV_OK)
        with mock.patch.object(voz_premium.requests, "post", return_value=_Resp()):
            self.client.post("/api/voz/falar", json={"texto": "12345"})
        j = self.client.get("/api/voz/uso").get_json()
        self.assertEqual(j["caracteres"], 5)
        self.assertEqual(j["limite"], 9000)
        self.assertTrue(j["configurado"])
        self.assertRegex(j["mes"], r"^\d{4}-\d{2}$")

    def test_mini_fuzz_nunca_500(self):
        os.environ.update(ENV_OK)
        rnd = random.Random(7)
        entradas = [
            "😀" * 50, "   ", "\n\t", "a" * 10000, "ação çãõ é ü", "\x00\x01", "<script>alert(1)</script>",
            "'; DROP TABLE voz_cache;--", "日本語のテキスト", "‮​", "x" * 300, "x" * 299 + "😀",
            5, 3.14, -1, True, None, [], ["a"], {}, {"a": 1}, "", "0", "null",
        ]
        entradas += ["".join(chr(rnd.randint(1, 0x2FFF)) for _ in range(rnd.randint(1, 40))) for _ in range(8)]
        with mock.patch.object(voz_premium.requests, "post", return_value=_Resp()):
            for e in entradas:
                r = self.client.post("/api/voz/falar", json={"texto": e})
                self.assertIn(r.status_code, (200, 204, 400), repr(e)[:60])
            for raw in (b"\xff\xfe", b"[[[[", b'{"texto": "a"', b"null", b"123"):
                r = self.client.post("/api/voz/falar", data=raw, content_type="application/json")
                self.assertIn(r.status_code, (400,), raw)
            r = self.client.post("/api/voz/falar", data="texto=oi", content_type="application/x-www-form-urlencoded")
            self.assertEqual(r.status_code, 400)

    def test_falha_do_banco_nao_500(self):
        os.environ.update(ENV_OK)
        with mock.patch.object(voz_premium, "sintetizar", side_effect=RuntimeError("boom")):
            self.assertEqual(self.client.post("/api/voz/falar", json={"texto": "oi"}).status_code, 204)


if __name__ == "__main__":
    unittest.main()
