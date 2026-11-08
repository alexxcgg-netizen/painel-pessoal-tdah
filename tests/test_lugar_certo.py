"""Leva 07/11 frente A - lugar certo + atraso sem susto. A Geocoding do Google responde REQUEST_DENIED
(billing), entao nenhum lugar tinha coordenada e `visitas.lugar` ficava sempre NULL; o atraso tratava
tarefa sem lugar como "em casa" e lia a hora de SAIR (sai_na_hora) como hora de chegar.
Banco temporario; Maps/push dublados (nada sai pra rede)."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import maps_client  # noqa: E402
import onde_estou  # noqa: E402
import vida_assistente  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402

CASA = (-26.9000, -49.0000)
MECANICO = (-26.9100, -49.0600)
LONGE = (-27.5000, -48.5000)
HOJE = date.today()


def _em(hhmm: str, dia: date = HOJE) -> datetime:
    return datetime.combine(dia, time(*map(int, hhmm.split(":"))))


def _resp(dados):
    r = MagicMock()
    r.json.return_value = dados
    r.raise_for_status.return_value = None
    return r


class LocalizarTestCase(unittest.TestCase):
    def setUp(self):
        maps_client._cache_coords.clear()
        for p in (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "chave-falsa"}),
                  patch("maps_client.usar_cota", return_value=True)):
            p.start()
            self.addCleanup(p.stop)

    def test_places_com_location_sem_geocoding(self):
        resp = _resp({"places": [{"location": {"latitude": -26.91, "longitude": -49.06}}]})
        with patch("maps_client.requests.post", return_value=resp) as post, \
                patch("maps_client.geocodificar") as geo, patch("maps_client.usar_cota", return_value=True) as cota:
            self.assertEqual(maps_client.localizar("Mecânico do Zé, Brusque"), (-26.91, -49.06))
            self.assertEqual(maps_client.localizar("mecânico do zé, brusque "), (-26.91, -49.06))  # cache
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["url"] if "url" in post.call_args.kwargs else post.call_args.args[0],
                         maps_client.PLACES_TEXT_URL)
        self.assertEqual(post.call_args.kwargs["headers"]["X-Goog-FieldMask"], "places.location")
        cota.assert_called_with("lugar_busca")
        geo.assert_not_called()

    def test_places_vazio_ou_fora_cai_na_geocoding(self):
        with patch("maps_client.requests.post", return_value=_resp({"places": []})), \
                patch("maps_client.geocodificar", return_value=(-1.0, -2.0)) as geo:
            self.assertEqual(maps_client.localizar("Rua X, 1"), (-1.0, -2.0))
        geo.assert_called_once()
        with patch("maps_client.requests.post", side_effect=maps_client.requests.RequestException("fora")), \
                patch("maps_client.geocodificar", side_effect=ValueError("nao achei")):
            with self.assertRaises(ValueError):
                maps_client.localizar("Rua Y, 2")

    def test_coordenada_direta_nao_chama_nada(self):
        with patch("maps_client.requests.post") as post:
            self.assertEqual(maps_client.localizar("-26.9,-49.0"), (-26.9, -49.0))
        post.assert_not_called()

    def test_posto_no_meio_usa_localizar(self):
        resp = _resp({"places": [{"displayName": {"text": "Posto A"}, "formattedAddress": "Rua 1"}]})
        with patch("maps_client.localizar", side_effect=[(-27.0, -49.0), (-27.2, -49.2)]) as loc, \
                patch("maps_client.geocodificar") as geo, patch("maps_client.requests.post", return_value=resp):
            self.assertEqual(maps_client.posto_no_meio_do_caminho("A", "B")["nome"], "Posto A")
        self.assertEqual(loc.call_count, 2)
        geo.assert_not_called()


class _Base(unittest.TestCase):
    casa_env = f"{CASA[0]},{CASA[1]}"

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        onde_estou._cache_trajeto.clear()
        maps_client._cache_coords.clear()
        env = {"ENDERECO_CASA": self.casa_env, "GOOGLE_MAPS_API_KEY": "chave-falsa"}
        # o mecanico no ponto dele; qualquer outro endereco (grafica, shopping...) num ponto longe de tudo
        self.loc = MagicMock(side_effect=lambda e: MECANICO if "Mecânico" in e else (-26.95, -49.10))
        self.viagem = MagicMock(return_value={"duracao_minutos": 25})
        for p in (patch.object(onde_estou, "REAGIR_EM_THREAD", False), patch.dict(os.environ, env),
                  patch("maps_client.localizar", self.loc), patch("maps_client.tempo_de_viagem", self.viagem),
                  patch("maps_client.usar_cota", return_value=True),
                  patch.object(onde_estou, "_avisar", return_value=True),
                  patch("onde_vou.recado_parado", return_value=False)):
            p.start()
            self.addCleanup(p.stop)
        vida_assistente.salvar_apelido(self.conn, "o mecânico", "Rua do Mecânico, 100, Brusque")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def tarefa(self, titulo, hora=None, local=None, sai_na_hora=None, origem=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, local, sai_na_hora, recorrente_origem_id) VALUES (?, ?, ?, ?, ?, ?)",
            (titulo, HOJE.isoformat(), hora, local, sai_na_hora, origem),
        )
        self.conn.commit()
        return cur.lastrowid

    def visita(self, ponto, chegada, saida=None, agora=None):
        dados = {"lat": ponto[0], "lon": ponto[1], "precisao": 30.0, "chegada": chegada, "saida": saida}
        return onde_estou.registrar(self.conn, dados, agora or saida or chegada)[0]

    def hora(self, tid):
        return self.conn.execute("SELECT hora FROM tasks WHERE id = ?", (tid,)).fetchone()["hora"]

    def lugar_visita(self, vid):
        return self.conn.execute("SELECT lugar FROM visitas WHERE id = ?", (vid,)).fetchone()["lugar"]


class CasaPeloGpsTestCase(_Base):
    casa_env = "Rua Que O Google Nao Acha, 1"

    def setUp(self):
        super().setUp()
        self.loc.side_effect = lambda e: MECANICO if "Mecânico" in e else (_ for _ in ()).throw(ValueError("nao"))

    def noites(self, n, ponto=CASA):
        for i in range(n, 0, -1):
            dia = HOJE - timedelta(days=i)
            # dorme em casa: chega 22:30, sai 07:40 do dia seguinte (o ponto mexe uns metros)
            p = (ponto[0] + 0.0001 * (i % 3), ponto[1])
            self.conn.execute("INSERT INTO visitas (lat, lon, precisao, chegada, saida) VALUES (?, ?, 30, ?, ?)",
                              (p[0], p[1], _em("22:30", dia - timedelta(days=1)).isoformat(),
                               _em("07:40", dia).isoformat()))
        self.conn.commit()

    def casa(self):
        return next((x for x in onde_estou.lugares_com_coordenada(self.conn) if x["apelido"] == "casa"), None)

    def test_tres_noites_no_mesmo_ponto_vira_casa(self):
        self.noites(3)
        c = self.casa()["coord"]
        self.assertLess(onde_estou._metros(c, CASA), 30)
        guardado = json.loads(db.obter_configuracao(self.conn, onde_estou.CONFIG_COORDS))
        self.assertEqual(guardado["casa"]["origem"], "gps")
        self.assertEqual(guardado["casa"]["endereco"], self.casa_env)
        # visita nova em casa ja e reconhecida
        vid = self.visita(CASA, datetime.now() - timedelta(minutes=5))
        self.assertEqual(self.lugar_visita(vid), "casa")

    def test_duas_noites_ou_cochilo_de_tarde_nao_bastam(self):
        self.noites(2)
        for i in range(1, 5):  # tarde inteira no mesmo ponto: nao e dormir
            dia = HOJE - timedelta(days=i)
            self.conn.execute("INSERT INTO visitas (lat, lon, precisao, chegada, saida) VALUES (?, ?, 30, ?, ?)",
                              (LONGE[0], LONGE[1], _em("13:00", dia).isoformat(), _em("18:00", dia).isoformat()))
        self.conn.commit()
        self.assertIsNone(self.casa()["coord"])
        self.assertIsNone(onde_estou.casa_pelo_gps(self.conn))

    def test_sem_endereco_de_casa_a_casa_vem_so_do_gps(self):
        with patch.dict(os.environ, {"ENDERECO_CASA": ""}):
            self.assertIsNone(self.casa())
            self.noites(4)
            casa = self.casa()
            self.assertIsNotNone(casa)
            self.assertLess(onde_estou._metros(casa["coord"], CASA), 30)
            self.assertIsNotNone(maps_client.coordenada(casa["endereco"]))  # vira 'lat,lon' pro trajeto


class ReprocessarTestCase(_Base):
    def test_visita_sem_lugar_ganha_o_lugar_quando_a_coordenada_aparece(self):
        self.loc.side_effect = ValueError("REQUEST_DENIED")
        agora = datetime.now()
        vid = self.visita(MECANICO, agora - timedelta(minutes=20))
        self.assertIsNone(self.lugar_visita(vid))
        # outro dia (ou a falha do dia limpa): agora o Places responde
        self.loc.side_effect = lambda e: MECANICO
        db.definir_configuracao(self.conn, onde_estou.CONFIG_COORDS, "{}")
        onde_estou.lugares_com_coordenada(self.conn)
        self.assertEqual(self.lugar_visita(vid), "mecanico")

    def test_reagir_reconhece_a_aberta_e_avisa_a_chegada(self):
        self.tarefa("Levar o carro no mecânico")
        agora = datetime.now()
        self.conn.execute("INSERT INTO visitas (lat, lon, precisao, chegada) VALUES (?, ?, 30, ?)",
                          (MECANICO[0], MECANICO[1], (agora - timedelta(minutes=3)).isoformat(timespec="seconds")))
        self.conn.commit()
        vid = self.conn.execute("SELECT MAX(id) FROM visitas").fetchone()[0]
        self.assertIn("chegada", onde_estou.reagir(self.conn, vid, agora))
        self.assertEqual(self.lugar_visita(vid), "mecanico")

    def test_visita_velha_nao_e_reprocessada(self):
        velha = datetime.now() - timedelta(days=4)
        self.conn.execute("INSERT INTO visitas (lat, lon, precisao, chegada, saida) VALUES (?, ?, 30, ?, ?)",
                          (MECANICO[0], MECANICO[1], velha.isoformat(), (velha + timedelta(hours=1)).isoformat()))
        self.conn.commit()
        lugares = onde_estou.lugares_com_coordenada(self.conn)
        self.assertEqual(onde_estou.reconhecer_visitas(self.conn, lugares), 0)


class AtrasoSemSustoTestCase(_Base):
    def test_a_tarefa_sem_lugar_nunca_e_empurrada(self):
        solta = self.tarefa("Responder o e-mail do banco", "11:00")
        self.visita(MECANICO, _em("10:00"))
        onde_estou.verificar(self.conn, _em("10:50"))
        self.assertEqual(self.hora(solta), "11:00")
        self.viagem.assert_not_called()

    def test_a_sem_lugar_no_meio_nao_anda_junto(self):
        com = self.tarefa("Imprimir as contas", "11:00", local="Gráfica Central")
        solta = self.tarefa("Estudar meteorologia", "11:30")
        outra = self.tarefa("Pagar boleto", "12:00", local="Lotérica")
        self.visita(MECANICO, _em("10:00"))
        onde_estou.verificar(self.conn, _em("10:50"))
        self.assertEqual([self.hora(t) for t in (com, solta, outra)], ["11:15", "11:30", "12:15"])

    def test_b_remedio_nunca(self):
        rem = self.tarefa("Tomar remédio", "11:00", local="Farmácia")
        modelo = self.conn.execute("INSERT INTO tasks (title, hora, recorrencia) VALUES ('Tomar Zeta', '11:05', 'diaria')").lastrowid
        self.conn.execute("INSERT INTO medicamentos (nome, horario, tarefa_modelo_id) VALUES ('Zeta', '11:05', ?)", (modelo,))
        self.conn.commit()
        dose = self.tarefa("Tomar Zeta", "11:05", local="Farmácia", origem=modelo)
        self.visita(MECANICO, _em("10:00"))
        onde_estou.verificar(self.conn, _em("10:50"))
        self.assertEqual((self.hora(rem), self.hora(dose)), ("11:00", "11:05"))

    def test_c_sai_na_hora_e_hora_de_sair(self):
        buscar = self.tarefa("Buscar a Ana", "21:00", local="Shopping Vizinho", sai_na_hora=1)
        self.visita(CASA, _em("18:00"))
        onde_estou.verificar(self.conn, _em("20:23"))  # 20h23 em casa, sai 21h: nada (o bug empurrava pra 21h15)
        self.assertEqual(self.hora(buscar), "21:00")
        onde_estou.verificar(self.conn, _em("20:58"))  # 20:58 + 5 > 21:00 e ainda em casa: atrasado
        # leva 08/11 (A2): compromisso de sair (sai_na_hora, alguem esperando) e parede - avisa, nao empurra
        self.assertEqual(self.hora(buscar), "21:00")
        ultima = self.conn.execute("SELECT texto FROM chat_mensagens ORDER BY id DESC LIMIT 1").fetchone()["texto"]
        self.assertIn("Não mexi no horário", ultima)
        self.viagem.assert_not_called()  # hora de sair nao precisa de trajeto

    def test_c_sai_na_hora_ja_saiu_nao_empurra(self):
        buscar = self.tarefa("Buscar a Ana", "21:00", local="Shopping Vizinho", sai_na_hora=1)
        vid = self.visita(CASA, _em("18:00"), _em("21:02"))
        onde_estou.reagir(self.conn, vid, _em("21:03"))
        self.assertEqual(self.hora(buscar), "21:00")

    def test_d_sem_base_nao_chuta(self):
        t = self.tarefa("Imprimir as contas", "11:00", local="Gráfica Central")
        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Que Nao Existe"}):
            self.loc.side_effect = lambda e: MECANICO if "Mecânico" in e else (_ for _ in ()).throw(ValueError("x"))
            self.visita(LONGE, _em("10:00"))  # lugar desconhecido e casa sem coordenada
            onde_estou.verificar(self.conn, _em("10:50"))
            self.assertEqual(self.hora(t), "11:00")
        self.viagem.assert_not_called()

    def test_d_lugar_desconhecido_com_casa_conhecida_empurra(self):
        t = self.tarefa("Imprimir as contas", "11:00", local="Gráfica Central")
        self.visita(LONGE, _em("10:00"))
        onde_estou.verificar(self.conn, _em("10:50"))
        self.assertEqual(self.hora(t), "11:15")


class PromptBuscarTestCase(unittest.TestCase):
    def test_buscar_e_hora_de_estar_la(self):
        p = " ".join(chat_mod.CHAT_SYSTEM_PROMPT.split())
        self.assertIn("as 21 tenho que buscar", p)
        self.assertIn("hora de ESTAR la", p)
        regra = p[p.index("HORA DE SAIR OU DE CHEGAR"):p.index("HORA DE SAIR OU DE CHEGAR") + 700]
        # "busco ela as 19" nao pode mais aparecer como exemplo de sai_na_hora=true
        self.assertLess(regra.index("sai_na_hora=true"), regra.index("busco ela"))
        self.assertIn("falso", regra[regra.index("busco ela"):])

    def test_esquema_das_ferramentas(self):
        tools = {t["name"]: t for t in chat_mod.CHAT_TOOLS}
        for nome in ("registrar_tarefa", "ajustar_tarefa"):
            desc = tools[nome]["input_schema"]["properties"]["sai_na_hora"]["description"]
            self.assertNotIn("busco ela", desc)
            self.assertIn("buscar", desc)
            self.assertIn("ESTAR la (false)", desc)


class RelatorioLugaresTestCase(_Base):
    def test_relatorio_mostra_lugares_e_visitas_reconhecidas(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import relatorio_painel

        for i in range(5):
            self.conn.execute("INSERT INTO visitas (lat, lon, chegada) VALUES (1, 1, ?)",
                              ((datetime.now() - timedelta(days=1, minutes=i)).isoformat(),))
        db.definir_configuracao(self.conn, onde_estou.CONFIG_COORDS, json.dumps({"mecanico": {"endereco": "x", "falhou": "2026-11-07"}}))
        self.conn.commit()
        saida, achados = relatorio_painel.secao_dados(self.conn, HOJE - timedelta(days=7), HOJE, HOJE)
        self.assertIn("### Lugares: 0 de 1 com coordenada; visitas dos últimos 7 dias: 0 de 5 reconhecidas", "".join(saida))
        self.assertTrue(any("nenhuma das 5 visitas" in a.titulo for a in achados))


if __name__ == "__main__":
    unittest.main()
