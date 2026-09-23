"""Regressao dos achados da revisao independente da Fase 2 (BRIEFING.md)."""

import os
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from test_vida_rotas import VidaBaseTestCase

import aprendizado
import app
import caldav_client
import db
import vida


class LogicaRevisaoTestCase(unittest.TestCase):
    def test_ficha_casa_palavra_inteira(self):
        fichas = [{"id": 1, "grupo": "Braço"}, {"id": 2, "grupo": "Perna"}, {"id": 3, "grupo": "Treino A"}]
        grupos = lambda titulo: [f["grupo"] for f in vida.ficha_para_titulo(fichas, titulo)]  # noqa: E731
        self.assertEqual(grupos("Dar um abraço na mãe"), [])
        self.assertEqual(grupos("Ligar pra Pernambucanas"), [])
        self.assertEqual(grupos("Treino academia"), ["Braço", "Perna", "Treino A"])
        self.assertEqual(grupos("Treino A"), ["Treino A"])
        self.assertEqual(grupos("treino de braço e perna"), ["Braço", "Perna"])
        self.assertEqual(grupos("Treino de pouso"), [])
        self.assertEqual(grupos(None), [])

    def test_academia_nao_e_treino_de_voo(self):
        self.assertFalse(vida.eh_dia_de_academia(["Treino de voo no aeroclube"]))
        self.assertFalse(vida.eh_dia_de_academia(["Estreino do filme"]))
        self.assertTrue(vida.eh_dia_de_academia(["Academia 18h"]))
        self.assertTrue(vida.eh_dia_de_academia(["Treino peito"]))

    def test_mesma_cidade(self):
        self.assertTrue(vida.mesma_cidade("Floripa", "Floripa, SC"))
        self.assertTrue(vida.mesma_cidade("Sao Paulo", "São Paulo"))
        self.assertFalse(vida.mesma_cidade("Sal", "Salvador"))
        self.assertFalse(vida.mesma_cidade("😀", "Floripa"))
        self.assertFalse(vida.mesma_cidade(None, "Floripa"))

    def test_compra_so_prefixo_vira_vazio(self):
        for texto in ["acabou o", "Acabou.", "acabaram as", "   "]:
            self.assertEqual(vida.normalizar_item_compra(texto), "", msg=texto)
        self.assertEqual(vida.normalizar_item_compra("Acabou o Café."), "cafe")
        self.assertEqual(vida.normalizar_item_compra("Acabamento"), "acabamento")

    def test_sequencia_de_sono_ancorada_na_primeira_noite(self):
        hoje = date(2026, 9, 23)
        sono = {(hoje - timedelta(days=d)).isoformat(): 5.0 for d in (1, 2, 3)}
        antes = vida.sequencia_noites_ruins(sono, {}, hoje)
        sono[hoje.isoformat()] = 4.0
        depois = vida.sequencia_noites_ruins(sono, {}, hoje)
        self.assertEqual(antes, (3, hoje - timedelta(days=3)))
        self.assertEqual(depois, (4, hoje - timedelta(days=3)))
        self.assertEqual(vida.sequencia_noites_ruins({}, {}, hoje), (0, None))

    def test_evento_icloud_com_fuso_vira_hora_local(self):
        inicio = datetime(2026, 9, 23, 18, 0, tzinfo=timezone.utc)
        comp = {"DTSTART": SimpleNamespace(dt=inicio), "DTEND": SimpleNamespace(dt=inicio + timedelta(hours=1))}
        comp_obj = SimpleNamespace(icalendar_component=_Componente(comp))
        evento = caldav_client._extrair_evento(comp_obj)
        local = inicio.astimezone().replace(tzinfo=None)
        self.assertEqual(evento["inicio"], local.isoformat())
        self.assertIsNone(datetime.fromisoformat(evento["inicio"]).tzinfo)

    def test_inteiro_no_intervalo_infinito(self):
        for valor in (float("inf"), float("-inf"), float("nan"), 1e308, "1e999"):
            self.assertIsNone(app._inteiro_no_intervalo(valor, 0, 100), msg=repr(valor))


class _Componente(dict):
    def get(self, chave, padrao=None):
        return super().get(chave, padrao)


class RotasRevisaoTestCase(VidaBaseTestCase):
    def test_numero_gigante_nao_da_500(self):
        casos = [
            ("/api/manutencoes", {"item": "x", "intervalo_meses": 1e999}),
            ("/api/treino", {"duracao_min": 1e999}),
            ("/api/treino", {"duracao_min": -1e999}),
        ]
        for rota, corpo in casos:
            self.assertEqual(self.client.post(rota, json=corpo).status_code, 400, msg=rota)
        r = self.client.post("/api/atalho/local", json={"evento": "saiu", "lugar": "casa", "bateria": 1e999})
        self.assertEqual(r.status_code, 200)

    def test_bateria_quebrada_ou_texto(self):
        def mensagem(bateria):
            with patch("app.datetime") as dt:
                dt.now.return_value = datetime.combine(date.today(), datetime.min.time()).replace(hour=8)
                dt.fromisoformat = datetime.fromisoformat
                app.definir_configuracao(self._conn(), "local_casa_saiu", "")
                corpo = {"evento": "saiu", "lugar": "casa", "bateria": bateria}
                return self.client.post("/api/atalho/local", json=corpo).get_json()["mensagem"]

        self.assertIn("carregador (bateria em 48%)", mensagem(47.5))
        self.assertIn("carregador (bateria em 30%)", mensagem("30"))
        self.assertNotIn("carregador", mensagem("80"))
        self.assertNotIn("carregador", mensagem("abc"))

    def test_chegou_em_casa_com_evento_com_fuso(self):
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=12)
        evento = {
            "titulo": "Dentista",
            "inicio": (agora + timedelta(hours=3)).astimezone(timezone.utc).isoformat(),
            "dia_inteiro": False,
        }
        with patch("app._eventos_de_hoje_com_seguranca", return_value=[evento]), patch("app.datetime") as dt:
            dt.now.return_value = agora
            dt.fromisoformat = datetime.fromisoformat
            r = self.client.post("/api/atalho/local", json={"evento": "chegou", "lugar": "casa"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Dentista", r.get_json()["mensagem"])

    def test_rotas_de_localizacao_e_apps_nao_ficam_abertas(self):
        anonimo = app.app.test_client()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PAINEL_ATALHOS_TOKEN", None)
            self.assertEqual(
                anonimo.post("/api/atalho/local", json={"evento": "chegou", "lugar": "mercado"}).status_code, 401
            )
            self.assertEqual(anonimo.post("/api/atalho/app", json={"app": "X", "evento": "abriu"}).status_code, 401)
            self.assertEqual(
                self.client.post("/api/atalho/app", json={"app": "X", "evento": "abriu"}).status_code, 200
            )

    def test_adiado_leve_respeita_silencio(self):
        conn = self._conn()
        with patch("app.date") as d:
            d.today.return_value = date.today()
            app._adiar_aviso(conn, "fechamento_noturno", "Fechando o dia", "x")
            app._adiar_aviso(conn, "rotina_manha", "Bom dia", "y")
        tipos = [t for t, *_ in app._liberar_avisos_adiados(conn, date.today())]
        self.assertEqual(tipos, ["adiado_hiperfoco_leve", "adiado_hiperfoco"])
        self.assertNotIn("adiado_hiperfoco_leve", app.NOTIFICACOES_URGENTES)
        self.assertIn("adiado_hiperfoco_leve", vida.CRITICOS_HIPERFOCO)

    def test_pessoa_mesmo_nome_nao_duplica(self):
        self.assertEqual(self.client.post("/api/pessoas", json={"nome": "Mãe", "frequencia_dias": 7}).status_code, 201)
        r = self.client.post("/api/pessoas", json={"nome": "mae", "frequencia_dias": 3})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["atualizada"])
        pessoas = self.client.get("/api/pessoas").get_json()
        self.assertEqual([(p["nome"], p["frequencia_dias"]) for p in pessoas], [("Mãe", 3)])

    def test_criado_em_convertido_pra_hora_local(self):
        conn = self._conn()
        conn.execute("INSERT INTO responder (quem, criado_em) VALUES ('Ana', '2026-09-23 01:30:00')")
        conn.commit()
        esperado = (
            datetime(2026, 9, 23, 1, 30, tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
            .isoformat(sep=" ", timespec="seconds")
        )
        self.assertEqual(db.list_responder_pendentes(conn)[0]["criado_em"], esperado)

    def test_dica_sono_humor_sem_rotulo_repetido(self):
        medias = {"7h ou mais": 2.4, "menos de 6h": 1.6}
        with patch("aprendizado.media_checkin_por_faixa_sono", return_value=medias):
            dica = aprendizado.dica_sono_humor(self._conn())
        self.assertIn("fica melhor depois de 7h ou mais de sono do que depois de menos de 6h", dica)
        self.assertNotIn("'ok' depois de 7h ou mais de sono e mais pra 'ok'", dica)


if __name__ == "__main__":
    unittest.main()
