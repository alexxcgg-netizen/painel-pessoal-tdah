"""Atividade ao vivo do iPhone: rota GET /api/ao-vivo (rotas/ao_vivo.py), leva "Cards ao vivo" de 04/11/2026.
Banco temporario, relogio injetado, sem rede (Maps/iCloud/clima nunca chamados de verdade)."""

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import tempo  # noqa: E402
from rotas import ao_vivo  # noqa: E402

TOKEN = {"Authorization": "Bearer token-de-teste"}
DIA = "2026-11-07"
TARDE = datetime(2026, 11, 7, 15, 0)


def _local(iso: str) -> datetime:
    """ISO com fuso -> hora local sem fuso (o mesmo relogio do servidor)."""
    return datetime.fromisoformat(iso).astimezone().replace(tzinfo=None)


class AoVivoBase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        tempo.limpar_cache()
        ao_vivo._CACHE_CLIMA.clear()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)
        env = patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": "token-de-teste"})
        env.start()
        self.addCleanup(env.stop)
        self.client = app.app.test_client()

    def tarefa(self, titulo, hora, estilo=None, local=None, data=DIA):
        c = self.conn.execute("INSERT INTO tasks (title, due_date, hora, local, estilo) VALUES (?, ?, ?, ?, ?)",
                              (titulo, data, hora, local, estilo))
        self.conn.commit()
        return c.lastrowid

    def voo(self, hora, data=DIA, origem="SSBL"):
        c = self.conn.execute("INSERT INTO voos (data, origem, destino, hora) VALUES (?, ?, 'SSBL', ?)",
                              (data, origem, hora))
        self.conn.commit()
        return c.lastrowid

    def get(self, agora=TARDE, headers=TOKEN):
        with patch.object(ao_vivo, "_agora", return_value=agora), patch.object(ao_vivo, "_rede", return_value=False):
            return self.client.get("/api/ao-vivo", headers=headers)


class TokenTest(AoVivoBase):
    def test_sem_token_e_401(self):
        r = self.get(headers={})
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("ativo", r.get_json())

    def test_token_errado_e_401(self):
        for cab in ({"Authorization": "Bearer errado"}, {"Authorization": "token-de-teste"},
                    {"Authorization": "Bearer "}):
            with self.subTest(cab=cab):
                self.assertEqual(self.get(headers=cab).status_code, 401)

    def test_token_na_url_nao_vale(self):
        with patch.object(ao_vivo, "_agora", return_value=TARDE), patch.object(ao_vivo, "_rede", return_value=False):
            self.assertEqual(self.client.get("/api/ao-vivo?token=token-de-teste").status_code, 401)

    def test_sem_token_configurado_no_servidor_e_401(self):
        with patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": ""}):
            self.assertEqual(self.get().status_code, 401)

    def test_erro_por_dentro_vira_500_curto(self):
        with patch.object(ao_vivo, "montar", side_effect=RuntimeError("segredo /c/projetos")):
            r = self.get()
        self.assertEqual(r.status_code, 500)
        corpo = r.get_data(as_text=True)
        self.assertNotIn("Traceback", corpo)
        self.assertNotIn("segredo", corpo)


class MontagemTest(AoVivoBase):
    def test_sem_compromisso_fica_inativo(self):
        self.assertEqual(self.get().get_json(), {"ativo": False})

    def test_tarefa_solta_e_habito_nao_viram_atividade(self):
        self.tarefa("Academia", "16:00")  # trava o dia, mas sem saida
        self.tarefa("Tomar remédio", "15:30")
        self.assertEqual(self.get().get_json(), {"ativo": False})

    def test_date_com_passos_cor_e_icone(self):
        ref = self.tarefa("Date", "19:00", estilo="date", local="Viva Beach")
        d = self.get().get_json()
        self.assertTrue(d["ativo"])
        self.assertEqual(d["id"], f"tarefa-{ref}-{DIA}")
        self.assertEqual((d["titulo"], d["kind"], d["cor"], d["icone"], d["lugar"]),
                         ("Date", "tarefa", "#f5a3b8", "heart.fill", "Viva Beach"))
        self.assertEqual([p["chave"] for p in d["passos"]], ["arrumar", "sair", "chegar"])
        # sem rede: 15 min de folga; 40 min pra se arrumar (padrao)
        self.assertEqual([_local(p["em"]).strftime("%H:%M") for p in d["passos"]], ["18:05", "18:45", "19:00"])
        self.assertEqual(d["atual"], -1)
        self.assertIsNone(d["clima"])
        self.assertEqual(_local(d["fim_em"]), datetime(2026, 11, 7, 19, 10))
        self.assertRegex(d["passos"][0]["em"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")

    def test_balada_tem_a_cor_dela(self):
        self.tarefa("Balada", "20:30", estilo="balada", local="Viva Beach")
        d = self.get().get_json()
        self.assertEqual((d["cor"], d["icone"]), ("#c4a1ff", "music.note"))

    def test_passo_atual_anda_e_some_depois_de_chegar(self):
        self.tarefa("Date", "19:00", estilo="date", local="Viva Beach")
        self.assertEqual(self.get(datetime(2026, 11, 7, 18, 10)).get_json()["atual"], 0)
        self.assertEqual(self.get(datetime(2026, 11, 7, 18, 50)).get_json()["atual"], 1)
        self.assertEqual(self.get(datetime(2026, 11, 7, 19, 5)).get_json()["atual"], 2)
        self.assertEqual(self.get(datetime(2026, 11, 7, 19, 11)).get_json(), {"ativo": False})

    def test_longe_demais_nao_entra(self):
        self.tarefa("Date", "22:00", estilo="date", local="Viva Beach")
        self.assertEqual(self.get(datetime(2026, 11, 7, 15, 30)).get_json(), {"ativo": False})
        self.assertTrue(self.get(datetime(2026, 11, 7, 16, 0)).get_json()["ativo"])

    def test_voo_chega_pro_briefing_e_some_na_decolagem(self):
        ref = self.voo("17:00")
        d = self.get().get_json()
        self.assertEqual((d["id"], d["kind"], d["cor"], d["icone"], d["lugar"]),
                         (f"voo-{ref}-{DIA}", "voo", "#8fd0ff", "airplane", "SSBL"))
        # 17:00 - 30 briefing - 15 folga = sai 16:15; chega 16:30 pro briefing; arruma 40 antes
        self.assertEqual([(p["chave"], _local(p["em"]).strftime("%H:%M")) for p in d["passos"]],
                         [("arrumar", "15:35"), ("sair", "16:15"), ("chegar", "16:30")])
        self.assertEqual(_local(d["fim_em"]), datetime(2026, 11, 7, 17, 0))
        self.assertTrue(d["levar"])  # a mochila do voo
        self.assertLessEqual(len(d["levar"]), ao_vivo.LEVAR_MAX)

    def test_proximo_ganha_de_um_que_acabou_de_chegar(self):
        self.tarefa("Dentista", "15:00", local="Clínica Sorriso")
        self.tarefa("Date", "19:00", estilo="date", local="Viva Beach")
        self.assertEqual(self.get(datetime(2026, 11, 7, 15, 5)).get_json()["titulo"], "Date")

    def test_nunca_mostra_endereco(self):
        self.tarefa("Consulta", "17:00", local="Rua das Flores, 123 - Centro, Brusque - SC")
        d = self.get().get_json()
        self.assertTrue(d["ativo"])
        self.assertNotIn("Flores", json.dumps(d, ensure_ascii=False))
        self.assertNotIn("123", json.dumps(d))

    def test_apelido_do_lugar(self):
        self.assertEqual(ao_vivo.apelido_do_lugar(self.conn, "viva beach, Balneário Camboriú"), "Viva beach")
        self.assertIsNone(ao_vivo.apelido_do_lugar(self.conn, "Av. Beira Rio 500"))
        self.assertIsNone(ao_vivo.apelido_do_lugar(self.conn, "R. Teste, 10"))
        self.assertIsNone(ao_vivo.apelido_do_lugar(self.conn, ""))
        import vida_assistente

        vida_assistente.salvar_apelido(self.conn, "oficina", "Oficina Exemplo, R. Teste, 10 - Centro")
        self.conn.commit()
        self.assertEqual(ao_vivo.apelido_do_lugar(self.conn, "oficina"), "Oficina")


class ParadaEClimaTest(AoVivoBase):
    def _com_parada(self, parada):
        real = tempo.compromissos

        def falso(conn, agora, rede=True):
            itens = real(conn, agora, False)
            for i in itens:
                i["parada"] = parada
            return itens

        return patch.object(tempo, "compromissos", side_effect=falso)

    def test_com_parada_entra_entre_sair_e_chegar(self):
        self.tarefa("Balada", "23:00", estilo="balada", local="Viva Beach")
        with self._com_parada({"nome": "casa do guri", "min_ate": 10}):
            d = self.get(datetime(2026, 11, 7, 21, 0)).get_json()
        self.assertEqual([p["chave"] for p in d["passos"]], ["arrumar", "sair", "parada", "chegar"])
        self.assertEqual(d["passos"][2]["rotulo"], "Casa do guri")
        self.assertEqual(_local(d["passos"][2]["em"]).strftime("%H:%M"), "22:55")

    def test_parada_com_endereco_ou_invalida(self):
        self.tarefa("Balada", "23:00", estilo="balada", local="Viva Beach")
        with self._com_parada({"nome": "Rua X, 12", "min_ate": 5}):
            d = self.get(datetime(2026, 11, 7, 21, 0)).get_json()
        self.assertEqual(d["passos"][2]["rotulo"], "Parada")
        for ruim in ({"nome": "guri", "min_ate": "dez"}, {"nome": "guri", "min_ate": 99}, "guri", None):
            with self.subTest(ruim=ruim), self._com_parada(ruim):
                d = self.get(datetime(2026, 11, 7, 21, 0)).get_json()
                self.assertEqual([p["chave"] for p in d["passos"]], ["arrumar", "sair", "chegar"])

    def test_sem_rede_nao_chama_clima_nem_maps(self):
        self.tarefa("Date", "19:00", estilo="date", local="Viva Beach")

        def nao_pode(*_a, **_k):
            raise AssertionError("chamou rede")

        with patch.object(tempo, "_trajeto_local", side_effect=nao_pode), \
                patch.object(tempo, "_saida_voo", side_effect=nao_pode):
            d = ao_vivo.montar(self.conn, TARDE, rede=False, clima_fn=nao_pode)
        self.assertTrue(d["ativo"])
        self.assertIsNone(d["clima"])
        self.assertEqual(d["levar"], [])

    def test_clima_na_chegada_e_o_que_levar(self):
        self.tarefa("Date", "19:00", estilo="date", local="Viva Beach")
        visto = []

        def clima(chegar):
            visto.append(chegar)
            return {"temp": 15, "chuva": 70}

        real = tempo.compromissos
        with patch.object(tempo, "compromissos", side_effect=lambda c, a, rede=True: real(c, a, False)):
            d = ao_vivo.montar(self.conn, TARDE, rede=True, clima_fn=clima)
        self.assertEqual(visto, [datetime(2026, 11, 7, 19, 0)])
        self.assertEqual(d["clima"], {"temp": 15, "chuva": 70})
        self.assertEqual(d["levar"], ["Guarda-chuva", "Casaco"])


if __name__ == "__main__":
    unittest.main()
