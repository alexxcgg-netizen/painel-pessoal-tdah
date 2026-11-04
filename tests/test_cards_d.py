"""Linguagem D "ao vivo" dos cards (04/11/2026, docs/briefings/2026-11-04-cards-ao-vivo.md).

O servidor manda SEGUNDOS ate cada passo (`*_s`) + `gerado_ts` (o front conta sem ler hora de
parede), o tempo hora a hora da saida (7 colunas, chegada/volta marcadas), o que levar (com o
motivo), a parada no caminho (contrato com a Frente 2), os aerodromos do voo (pista so a conferida),
a lista do dia da tarefa concluida e o type novo lugar_salvo. Banco temporario; nada de rede."""
import json
import os
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import cards  # noqa: E402

AGORA = datetime(2026, 11, 6, 16, 30)  # sexta


def _horas(dia: str, de: int, ate: int, frio_em=None, chuva_em=None):
    """Previsao horaria no formato de clima.previsao_horaria (com temp)."""
    out = []
    for h in range(de, ate + 1):
        hh = h % 24
        d = dia if h < 24 else (date.fromisoformat(dia) + timedelta(days=1)).isoformat()
        out.append({
            "quando": f"{d}T{hh:02d}:00",
            "chuva_pct": 60 if chuva_em == hh else 10,
            "codigo": 61 if chuva_em == hh else 1,
            "temp": 15.4 if frio_em == hh else 20.0,
        })
    return out


class CadeiaSaidaTest(unittest.TestCase):
    def test_segundos_ate_cada_passo_e_hora_so_pra_mostrar(self):
        c = cards.cadeia_saida("2026-11-06", "19:00", "17:30", "18:30", None, agora=AGORA)
        self.assertEqual([p["rotulo"] for p in c], ["Se arrumar", "Sair", "Chegar"])
        self.assertEqual([p["hora"] for p in c], ["17:30", "18:30", "19:00"])
        self.assertEqual([p["em_s"] for p in c], [3600, 7200, 9000])

    def test_passa_da_meia_noite(self):
        c = cards.cadeia_saida("2026-11-07", "00:10", "23:00", "23:40", None, agora=AGORA)
        self.assertEqual(c[1]["hora"], "23:40")
        self.assertEqual(c[2]["em_s"] - c[1]["em_s"], 30 * 60)  # sair 23:40 da noite anterior

    def test_parada_no_caminho_entra_entre_sair_e_chegar(self):
        parada = cards._parada_valida({"nome": "Casa do guri", "min_ate": 10})
        c = cards.cadeia_saida("2026-11-06", "19:00", "17:30", "18:30", parada, agora=AGORA)
        self.assertEqual([p["rotulo"] for p in c], ["Se arrumar", "Sair", "Casa do guri", "Chegar"])
        self.assertTrue(c[2]["parada"])
        self.assertEqual(c[2]["hora"], "18:40")

    def test_parada_invalida_e_ignorada(self):
        for ruim in (None, "x", {"nome": "", "min_ate": 5}, {"nome": "A", "min_ate": True},
                     {"nome": "A", "min_ate": 0}, {"nome": "A", "min_ate": 999}, {"nome": "A", "min_ate": "10"}):
            self.assertIsNone(cards._parada_valida(ruim), ruim)

    def test_sem_hora_nao_tem_cadeia(self):
        self.assertIsNone(cards.cadeia_saida("2026-11-06", None, None, None, None, agora=AGORA))


class TempoHoraAHoraTest(unittest.TestCase):
    def test_sete_colunas_da_hora_antes_da_chegada_ate_a_volta(self):
        prev = _horas("2026-11-06", 0, 30, frio_em=23, chuva_em=19)
        r = cards.clima_horas_saida("2026-11-06", "19:00", "23:00", buscar=lambda: prev)
        hs = r["horas"]
        self.assertEqual([h["hora"] for h in hs], [18, 19, 20, 21, 22, 23, 0])
        self.assertEqual(hs[1]["marca"], "chegada")
        self.assertEqual(hs[5]["marca"], "volta")
        self.assertEqual(hs[1]["chuva_pct"], 60)
        self.assertEqual(hs[5]["temp"], 15)

    def test_sem_previsao_da_hora_da_chegada_nao_mostra_nada(self):
        self.assertIsNone(cards.clima_horas_saida("2026-11-06", "19:00", None, buscar=lambda: []))
        self.assertIsNone(cards.clima_horas_saida("2026-11-06", "19:00", None, buscar=lambda: _horas("2026-11-06", 0, 10)))

    def test_sem_cidade_nao_busca_rede(self):
        with patch.dict(os.environ, {"CIDADE_PADRAO": ""}), patch("clima.previsao_horaria") as ph:
            self.assertIsNone(cards.clima_horas_saida("2026-11-06", "19:00", None))
            ph.assert_not_called()


class LevarTest(unittest.TestCase):
    def test_guarda_chuva_e_casaco_com_o_motivo(self):
        prev = _horas("2026-11-06", 0, 30, frio_em=23, chuva_em=19)
        hs = cards.clima_horas_saida("2026-11-06", "19:00", "23:00", buscar=lambda: prev)["horas"]
        itens = cards.levar_saida(hs)
        self.assertEqual([i["item"] for i in itens], ["guarda_chuva", "casaco"])
        self.assertEqual(itens[0]["motivo"], "60% às 19h")
        self.assertEqual(itens[1]["motivo"], "15° na volta, 23h")

    def test_tempo_bom_nao_pede_nada(self):
        hs = cards.clima_horas_saida("2026-11-06", "19:00", "23:00", buscar=lambda: _horas("2026-11-06", 0, 30))["horas"]
        self.assertEqual(cards.levar_saida(hs), [])

    def test_sem_volta_usa_a_hora_mais_fria_dali_pra_frente(self):
        prev = _horas("2026-11-06", 0, 30, frio_em=22)
        hs = cards.clima_horas_saida("2026-11-06", "19:00", None, buscar=lambda: prev)["horas"]
        self.assertEqual(cards.levar_saida(hs), [{"item": "casaco", "titulo": "Casaco", "motivo": "15° às 22h"}])

    def test_sem_hora_a_hora_usa_o_clima_da_chegada(self):
        self.assertEqual(cards.levar_saida(None, {"temp": 14, "chuva_pct": 70})[0]["motivo"], "70% na chegada")
        self.assertEqual(cards.levar_saida(None, None), [])


class BancoTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()


class TarefaFeitaListaTest(BancoTestCase):
    def test_lista_do_dia_com_a_feita_agora_marcada(self):
        hoje = AGORA.date().isoformat()
        ids = []
        for titulo, hora, feita in (("Remédio", "07:30", True), ("Banco", "09:45", False), ("Academia", "18:00", False)):
            cur = self.conn.execute(
                "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES (?, ?, ?, ?)",
                (titulo, hoje, hora, "2026-11-06 07:31" if feita else None),
            )
            ids.append(cur.lastrowid)
        self.conn.execute("UPDATE tasks SET completed_at = '2026-11-06 16:30' WHERE id = ?", (ids[1],))
        self.conn.commit()
        c = cards.card_tarefa_feita(self.conn, ids[1], agora=AGORA)
        itens = c["data"]["dia_itens"]
        self.assertEqual([i["titulo"] for i in itens], ["Remédio", "Banco", "Academia"])
        self.assertEqual([i["feita"] for i in itens], [True, True, False])
        self.assertEqual([i["esta"] for i in itens], [False, True, False])


class ParadaDesfeitaTest(BancoTestCase):
    def _date(self, parada_col):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        extras = json.dumps({"parada": {"nome": "Casa do guri", "min_ate": 10}})
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, estilo, extras, parada) VALUES (?, ?, ?, ?, ?, ?)",
            ("Date", amanha, "19:00", "date", extras, parada_col))
        self.conn.commit()
        return cards.card_compromisso(self.conn, {"id": cur.lastrowid})

    def test_coluna_com_parada_usa_a_copia_de_extras(self):
        self.assertEqual(self._date("casa do guri")["data"].get("parada", {}).get("nome"), "Casa do guri")

    def test_coluna_limpa_pelo_desfazer_ignora_a_copia_velha(self):
        self.assertNotIn("parada", self._date(None)["data"])


class TarefaCriadaSegundosTest(BancoTestCase):
    def test_tarefa_com_dia_e_hora_ganha_segundos(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        cur = self.conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)", ("Oficina", amanha, "08:30"))
        self.conn.commit()
        antes = int(time.time())
        c = cards.card_tarefas_criadas(self.conn, [cur.lastrowid])
        self.assertIn("em_s", c["data"])
        self.assertGreater(c["data"]["em_s"], 0)
        self.assertGreaterEqual(c["data"]["gerado_ts"], antes)

    def test_sem_hora_nao_conta(self):
        cur = self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("Comprar pão", date.today().isoformat()))
        self.conn.commit()
        self.assertNotIn("em_s", cards.card_tarefas_criadas(self.conn, [cur.lastrowid])["data"])


class VooAoVivoTest(BancoTestCase):
    def test_aerodromos_sem_repetir_e_pista_so_no_ssbl(self):
        rota = {"paradas": [{"icao": "SSBL", "nome": "Blumenau"}, {"icao": "SBNF", "nome": "Navegantes"}, {"icao": "SSBL", "nome": "Blumenau"}]}
        amanha = (date.today() + timedelta(days=1)).isoformat()
        out = cards._voo_ao_vivo(self.conn, amanha, "09:00", rota, 45, "07:10")
        self.assertEqual([a["icao"] for a in out["aerodromos"]], ["SSBL", "SBNF"])
        self.assertEqual(out["aerodromos"][0]["pista"]["cabeceiras"], [1, 19])
        self.assertAlmostEqual(out["aerodromos"][0]["pista"]["decl_w"], 20.6)
        self.assertIsNone(out["aerodromos"][1]["pista"])  # nao conferida: nada de cabeceira inventada
        self.assertEqual(out["decola_s"] - out["chegar_s"], 45 * 60)
        self.assertEqual(out["chegar_s"] - out["sair_s"], 65 * 60)  # sair 07:10, chegar 08:15
        self.assertIn("gerado_ts", out)
        self.assertIsInstance(out["limite_kt"], int)


class LugarSalvoTest(unittest.TestCase):
    def test_card_e_mascara_no_modo_visitante(self):
        c = cards.card_lugar_salvo({"entidade": "lugar_salvo", "apelido": "oficina", "endereco": "R. das Palmeiras, 210, Brusque",
                                    "nome": "Mecânica Irmãos Rossi", "achado": True})
        self.assertEqual(c["type"], "lugar_salvo")
        d = c["data"]
        self.assertEqual(d["apelido"], "oficina")
        self.assertEqual(d["raio_m"], 150)
        self.assertIsNone(d["de_casa_min"])  # o executor ainda nao mede o trajeto: nao inventa
        self.assertTrue(d["maps_url"].startswith("https://www.google.com/maps/search/?api=1&query="))
        self.assertIn("lugar_salvo", cards.TIPOS_CARD)
        m = cards.mascarar_cards([c])[0]["data"]
        self.assertTrue(m["oculto"])
        for campo in ("nome", "endereco", "maps_url", "de_casa_min"):
            self.assertNotIn(campo, m)
        self.assertEqual(m["apelido"], "oficina")

    def test_sem_apelido_nao_tem_card(self):
        self.assertIsNone(cards.card_lugar_salvo({"endereco": "Rua A"}))

    def test_efeito_do_executor_vira_card(self):
        c = cards._card_de_efeito_modulo(None, {"entidade": "lugar_salvo", "apelido": "academia", "endereco": "Rua B"}, None)
        self.assertEqual(c["type"], "lugar_salvo")
        self.assertEqual(c["data"]["nome"], "Rua B")


if __name__ == "__main__":
    unittest.main()
