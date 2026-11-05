"""Widgets nativos do iPhone (leva 05/11/2026): pareamento por codigo, toque na tarefa e na agua, dados novos
do /api/widget (rotas/widget_ios.py)."""

import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)

from rotas import n3a_widget, widget_ios  # noqa: E402

TOKEN = "token-de-teste-widget"
CAB = {"Authorization": f"Bearer {TOKEN}"}
ID = "8F2C1D9A-4B7E-4C11-9A3B-2D5E6F708192"


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self._env = patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": TOKEN})
        self._env.start()
        self.addCleanup(self._env.stop)
        log = patch.object(n3a_widget, "_LOG_WIDGET", str(Path(_tmp_dir.name) / "widget.log"))
        log.start()
        self.addCleanup(log.stop)
        widget_ios.zerar_pareamentos()
        self.addCleanup(widget_ios.zerar_pareamentos)
        self.client = app.app.test_client()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)


class PareamentoTestCase(_Base):
    def pedir(self, ident=ID):
        return self.client.post("/api/widget/parear", json={"id": ident})

    def test_fluxo_inteiro_entrega_o_token_uma_vez(self):
        r = self.pedir()
        self.assertEqual(r.status_code, 200)
        codigo = r.get_json()["codigo"]
        self.assertRegex(codigo, r"^\d{4}$")
        # mesmo widget pedindo de novo: mesmo codigo
        self.assertEqual(self.pedir().get_json()["codigo"], codigo)
        self.assertEqual(self.client.get(f"/api/widget/parear/{ID}").get_json(), {"estado": "esperando", "codigo": codigo})
        pend = self.client.get("/api/widget/parear/pendentes", headers=CAB).get_json()["pendentes"]
        self.assertEqual([p["codigo"] for p in pend], [codigo])
        self.assertEqual(self.client.post("/api/widget/parear/liberar", headers=CAB, json={"codigo": codigo}).status_code, 200)
        r = self.client.get(f"/api/widget/parear/{ID}").get_json()
        self.assertEqual(r, {"estado": "liberado", "token": TOKEN})
        # depois de entregue some: ninguem pega de novo
        self.assertEqual(self.client.get(f"/api/widget/parear/{ID}").get_json(), {"estado": "expirado"})

    def test_liberar_e_pendentes_pedem_o_token(self):
        codigo = self.pedir().get_json()["codigo"]
        self.assertEqual(self.client.get("/api/widget/parear/pendentes").status_code, 401)
        self.assertEqual(self.client.post("/api/widget/parear/liberar", json={"codigo": codigo}).status_code, 401)
        ruim = {"Authorization": "Bearer errado"}
        self.assertEqual(self.client.post("/api/widget/parear/liberar", headers=ruim, json={"codigo": codigo}).status_code, 401)
        self.assertEqual(self.client.get(f"/api/widget/parear/{ID}").get_json()["estado"], "esperando")

    def test_codigo_errado_nao_libera(self):
        codigo = self.pedir().get_json()["codigo"]
        outro = "0000" if codigo != "0000" else "1111"
        self.assertEqual(self.client.post("/api/widget/parear/liberar", headers=CAB, json={"codigo": outro}).status_code, 404)
        for ruim in ("12", "abcd", 1234, None, "12345"):
            with self.subTest(ruim=ruim):
                self.assertEqual(self.client.post("/api/widget/parear/liberar", headers=CAB, json={"codigo": ruim}).status_code, 400)

    def test_id_invalido(self):
        for ruim in (None, "", "curto", "x" * 65, "../../etc/passwd-aaaaaaaa", 123, ["a"]):
            with self.subTest(ruim=ruim):
                self.assertEqual(self.client.post("/api/widget/parear", json={"id": ruim}).status_code, 400)
        self.assertEqual(self.client.get("/api/widget/parear/curto").status_code, 400)

    def test_limite_de_abertos_e_por_hora(self):
        for n in range(widget_ios.PAR_MAX_ABERTOS):
            self.assertEqual(self.pedir(f"widget-{n:02d}-aaaaaaaaaaaa").status_code, 200)
        self.assertEqual(self.pedir("widget-xx-aaaaaaaaaaaa").status_code, 429)

    def test_expira(self):
        self.pedir()
        with patch.object(widget_ios.time, "monotonic", return_value=widget_ios.time.monotonic() + 601):
            self.assertEqual(self.client.get(f"/api/widget/parear/{ID}").get_json(), {"estado": "expirado"})

    def test_sem_token_no_servidor_nao_entrega_nada(self):
        codigo = self.pedir().get_json()["codigo"]
        self.client.post("/api/widget/parear/liberar", headers=CAB, json={"codigo": codigo})
        with patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": ""}):
            self.assertEqual(self.client.get(f"/api/widget/parear/{ID}").get_json(), {"estado": "sem_token"})

    def test_rotas_abertas_sem_sessao(self):
        """O widget nao tem a sessao do PIN: o pedido e a pergunta passam do login (cada rota cuida de si)."""
        import rotas

        for caminho in ("/api/widget/parear", f"/api/widget/parear/{ID}", "/api/widget/tarefa/3", "/api/widget/agua"):
            self.assertTrue(rotas.rota_com_token(caminho), caminho)
        self.assertFalse(rotas.rota_com_token("/api/widget/instalacao"))


class ToqueTestCase(_Base):
    def tarefa(self, titulo="Banco", due=None, hora="09:00"):
        cur = self.conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
                                (titulo, due or date.today().isoformat(), hora))
        self.conn.commit()
        return cur.lastrowid

    def feita(self, tid):
        return self.conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (tid,)).fetchone()["completed_at"]

    def test_marca_e_desmarca(self):
        tid = self.tarefa()
        r = self.client.post(f"/api/widget/tarefa/{tid}", headers=CAB, json={"feita": True})
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(self.feita(tid))
        self.client.post(f"/api/widget/tarefa/{tid}", headers=CAB, json={"feita": False})
        self.assertIsNone(self.feita(tid))

    def test_tarefa_sem_token_ou_corpo_ruim(self):
        tid = self.tarefa()
        self.assertEqual(self.client.post(f"/api/widget/tarefa/{tid}", json={"feita": True}).status_code, 401)
        for corpo in ({}, {"feita": "sim"}, {"feita": 1}, [True]):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.client.post(f"/api/widget/tarefa/{tid}", headers=CAB, json=corpo).status_code, 400)
        self.assertEqual(self.client.post("/api/widget/tarefa/99999", headers=CAB, json={"feita": True}).status_code, 404)
        self.assertIsNone(self.feita(tid))

    def test_agua_soma_um_copo(self):
        self.assertEqual(self.client.post("/api/widget/agua").status_code, 401)
        r1 = self.client.post("/api/widget/agua", headers=CAB).get_json()
        r2 = self.client.post("/api/widget/agua", headers=CAB).get_json()
        self.assertEqual((r1["copos"], r2["copos"], r2["meta"]), (1, 2, 8))


class ColetaTestCase(_Base):
    def test_hoje_filtra_e_ordena(self):
        hoje = date(2026, 11, 5)
        ins = self.conn.execute
        ins("INSERT INTO tasks (title, due_date, hora) VALUES ('Dentista', '2026-11-05', '14:30')")
        ins("INSERT INTO tasks (title, due_date, hora) VALUES ('Banco', '2026-11-05', '09:00')")
        ins("INSERT INTO tasks (title, due_date) VALUES ('Sem hora', '2026-11-05')")
        ins("INSERT INTO tasks (title, due_date) VALUES ('Atrasada', '2026-11-03')")
        ins("INSERT INTO tasks (title, due_date, completed_at) VALUES ('Feita ontem', '2026-11-03', '2026-11-04 12:00:00')")
        ins("INSERT INTO tasks (title, due_date) VALUES ('Amanha', '2026-11-06')")
        ins("INSERT INTO tasks (title, due_date, recorrencia) VALUES ('Modelo', '2026-11-05', 'diaria')")
        ins("INSERT INTO tasks (title, due_date, arquivada_em) VALUES ('Arquivada', '2026-11-05', '2026-11-05')")
        ins("INSERT INTO tasks (title, due_date, hora, completed_at) VALUES ('Almoco', '2026-11-05', '12:00', '2026-11-05 15:10:00')")
        self.conn.commit()
        itens = widget_ios.coletar_hoje(self.conn, hoje)
        self.assertEqual([i["titulo"] for i in itens], ["Atrasada", "Banco", "Almoco", "Dentista", "Sem hora"])
        self.assertTrue(itens[2]["feita"])
        self.assertTrue(itens[0]["atrasada"])
        self.assertIsNone(itens[4]["hora"])

    def test_hoje_corta_feitas_primeiro(self):
        for n in range(6):
            self.conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES (?, '2026-11-05', ?)", (f"aberta {n}", f"1{n}:00"))
        for n in range(4):
            self.conn.execute("INSERT INTO tasks (title, due_date, hora, completed_at) VALUES (?, '2026-11-05', '08:00', '2026-11-05 12:00:00')", (f"feita {n}",))
        self.conn.commit()
        itens = widget_ios.coletar_hoje(self.conn, date(2026, 11, 5))
        self.assertEqual(len(itens), widget_ios.HOJE_MAX_ITENS)
        self.assertEqual(sum(1 for i in itens if not i["feita"]), 6)

    def test_horas_voo(self):
        self.assertIsNone(widget_ios.coletar_horas_voo(self.conn, date(2026, 11, 5)))
        self.conn.execute("INSERT INTO voos (data, origem, destino, horas) VALUES ('2026-11-01', 'SSBL', 'SBJV', 1.5)")
        self.conn.execute("INSERT INTO voos (data, origem, destino, horas, tipo) VALUES ('2026-11-02', 'SSBL', 'SSBL', 2, 'simulador')")
        self.conn.commit()
        self.assertEqual(widget_ios.coletar_horas_voo(self.conn, date(2026, 11, 5)), {"total": 1.5, "meta": 150})

    def test_voo_com_vento(self):
        self.conn.execute("INSERT INTO voos (data, hora, origem, destino) VALUES ('2026-11-07', '07:30', 'SSBL', 'SBJV')")
        self.conn.commit()
        horas = [{"quando": f"2026-11-07T{h:02d}:00", "codigo": 0 if h < 9 else 3, "vento_kt": h, "vento_dir": 23}
                 for h in range(24)]
        chamado = {}

        def buscar(lat, lon, dias):
            chamado.update(lat=lat, dias=dias)
            return horas

        voo = widget_ios.coletar_voo(self.conn, datetime(2026, 11, 5, 16, 0), buscar_vento=buscar)
        self.assertEqual(voo["dia"], "sábado")
        self.assertEqual((voo["origem"], voo["destino"], voo["hora"]), ("SSBL", "SBJV", "07:30"))
        self.assertEqual(voo["condicao"], "céu limpo")
        self.assertEqual(voo["vento"], "020° 7 kt")
        self.assertEqual(voo["codigo"], 0)
        self.assertEqual([h["hora"] for h in voo["horas"]], ["6h", "7h", "8h", "9h", "10h", "11h"])
        self.assertEqual(chamado["dias"], 3)

    def test_voo_longe_sem_previsao(self):
        self.conn.execute("INSERT INTO voos (data, hora, origem, destino) VALUES ('2026-11-10', '07:30', 'SSBL', 'SSBL')")
        self.conn.commit()

        def nao_chama(*a, **k):
            raise AssertionError("nao era pra buscar previsao")

        voo = widget_ios.coletar_voo(self.conn, datetime(2026, 11, 5, 16, 0), buscar_vento=nao_chama)
        self.assertEqual((voo["dia"], voo["destino"], voo["horas"]), ("terça", None, []))
        self.assertIsNone(widget_ios.coletar_voo(self.conn, datetime(2026, 11, 20, 16, 0), buscar_vento=nao_chama))

    def test_voo_sem_rede(self):
        self.conn.execute("INSERT INTO voos (data, hora, origem, destino) VALUES ('2026-11-05', '18:00', 'SBNF', 'SBNF')")
        self.conn.commit()
        voo = widget_ios.coletar_voo(self.conn, datetime(2026, 11, 5, 16, 0), buscar_vento=lambda *a, **k: None)
        self.assertEqual((voo["dia"], voo["condicao"], voo["horas"]), ("hoje", None, []))

    def test_api_widget_traz_os_campos_novos(self):
        tid = self.conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES ('Banco', date('now', '-3 hours'), '09:00')").lastrowid
        self.conn.commit()
        with patch("caldav_client.configurado", return_value=False):
            d = self.client.get("/api/widget", headers=CAB).get_json()
        self.assertEqual(d["agua"], {"copos": 0, "meta": 8})
        self.assertIsNone(d["horas_voo"])
        self.assertIn(tid, [i["id"] for i in d["hoje"]])
        self.assertIsNone(d["voo"])

    def test_agua_sozinha_nao_e_dado(self):
        r = n3a_widget.montar_widget(agora_utc=datetime(2026, 11, 5), agua={"copos": 0, "meta": 8})
        self.assertEqual(r["estado"], "vazio")


class VentoHorarioTestCase(unittest.TestCase):
    def test_guarda_30_min(self):
        import clima

        clima._CACHE_VENTO.clear()
        chamadas = []

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"hourly": {"time": ["2026-11-05T10:00"], "weathercode": [1],
                                   "wind_speed_10m": [7.6], "wind_direction_10m": [212.4]}}

        def buscar(url, params, timeout):
            chamadas.append(params)
            return Resp()

        a = clima.vento_horario(-26.8, -49.1, buscar=buscar)
        b = clima.vento_horario(-26.8, -49.1, buscar=buscar)
        self.assertEqual(a, [{"quando": "2026-11-05T10:00", "codigo": 1, "vento_kt": 8, "vento_dir": 212}])
        self.assertEqual(a, b)
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0]["wind_speed_unit"], "kn")
        clima._CACHE_VENTO.clear()


if __name__ == "__main__":
    unittest.main()
