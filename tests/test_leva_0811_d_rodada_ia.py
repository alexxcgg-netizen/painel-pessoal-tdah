"""08/11/2026 - o que a rodada de conversa com a IA de verdade (cenarios no jeito do Alex, numa copia do banco)
mostrou. Cada teste e um erro visto na resposta real; claude_client.chat e dublado, nenhuma rede."""
import unittest
from datetime import date, timedelta

from tests.test_assistente_vida import _Base

import classificador_local
from classificador_local.regras import p4_regra, p5_replanejar
from ia import revisor_chat
from ia import roteador_chat

HOJE = date.today().isoformat()
ONTEM = (date.today() - timedelta(days=1)).isoformat()


class MontaDiaTrazAtrasadaTestCase(_Base):
    def test_planejar_dia_traz_a_tarefa_de_ontem_em_vez_de_duplicar(self):
        """"monta meu dia" criava "Limpar meu quarto" de novo com a de ontem ainda aberta."""
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Limpar meu quarto', ?, '15:30')", (ONTEM,))
        self.chat([("planejar_dia", {"data": HOJE, "blocos": [
            {"titulo": "Limpar meu quarto", "hora": "14:30"}, {"titulo": "Banco", "hora": "09:00"}]})])
        quartos = self.sql("SELECT due_date, hora FROM tasks WHERE title = 'Limpar meu quarto'")
        self.assertEqual(len(quartos), 1)
        self.assertEqual((quartos[0]["due_date"], quartos[0]["hora"]), (HOJE, "14:30"))
        self.assertEqual(len(self.sql("SELECT id FROM tasks WHERE title = 'Banco'")), 1)

    def test_tarefa_feita_ou_arquivada_de_ontem_nao_e_reaproveitada(self):
        self.sql("INSERT INTO tasks (title, due_date, completed_at) VALUES ('Banco', ?, datetime('now'))", (ONTEM,))
        self.sql("INSERT INTO tasks (title, due_date, arquivada_em) VALUES ('Farmacia', ?, datetime('now'))", (ONTEM,))
        self.chat([("planejar_dia", {"data": HOJE, "blocos": [
            {"titulo": "Banco", "hora": "09:00"}, {"titulo": "Farmacia", "hora": "10:00"}]})])
        self.assertEqual(self.sql("SELECT COUNT(*) n FROM tasks WHERE due_date = ? AND completed_at IS NULL "
                                  "AND arquivada_em IS NULL", (HOJE,))[0]["n"], 2)


class ApagarSoNaAbertaTestCase(_Base):
    def test_apagar_nao_leva_junto_tarefa_ja_feita(self):
        """"tira a do quartinho" apagou tambem uma tarefa feita em outubro (historico)."""
        self.sql("INSERT INTO tasks (title, due_date, completed_at) VALUES "
                 "('Ver formas de organizar o quartinho', ?, datetime('now', '-10 days'))", (ONTEM,))
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Comecar arrumar o quartinho', ?)", (ONTEM,))
        _, res = self.chat([("apagar_tarefa", {"titulo": "quartinho"})])
        self.assertTrue(res[0].get("ok"), res[0])
        self.assertEqual(res[0]["apagada"], "Comecar arrumar o quartinho")
        self.assertEqual(len(self.sql("SELECT id FROM tasks WHERE title LIKE 'Ver formas%'")), 1)

    def test_tarefa_feita_ainda_pode_ser_apagada_se_for_a_unica_com_o_nome(self):
        self.sql("INSERT INTO tasks (title, due_date, completed_at) VALUES ('Lavar o tapete', ?, datetime('now'))",
                 (ONTEM,))
        _, res = self.chat([("apagar_tarefa", {"titulo": "lavar o tapete"})])
        self.assertTrue(res[0].get("ok"), res[0])
        self.assertEqual(self.sql("SELECT COUNT(*) n FROM tasks")[0]["n"], 0)


class LugarQueOGoogleTrocouTestCase(_Base):
    def _salvar(self, endereco, achado):
        from unittest.mock import patch

        with patch("maps_client.configurado", return_value=True), \
                patch("maps_client.coordenada", return_value=None), \
                patch("maps_client.resolver_lugar", return_value=achado), \
                patch("onde_estou.garantir_coordenada", return_value=True):
            _, res = self.chat([("salvar_lugar_apelido", {"apelido": "luar beach", "endereco": endereco})])
        return res[0]

    def test_nome_que_nao_aparece_no_achado_nao_e_guardado(self):
        """"Luar Beach, Cidade" achou "Luar Sport Academia" e guardou: toda rota pra balada ia pra academia."""
        res = self._salvar("Luar Beach, Cidade - SC",
                           {"nome": "Luar Sport Academia", "endereco": "R. Teste, 10 - Centro, Cidade - SC"})
        self.assertIn("erro", res)
        self.assertIn("Luar Sport Academia", res["achado"])
        import vida_assistente
        import db
        conn = db.get_db()
        self.assertNotIn("luar beach", vida_assistente.apelidos(conn))
        conn.close()

    def test_nome_que_aparece_no_achado_continua_guardando(self):
        res = self._salvar("Luar Beach", {"nome": "Luar Beach Club", "endereco": "Av. Teste, 10 - Centro, Cidade - SC"})
        self.assertTrue(res.get("ok"), res)
        self.assertIn("Luar Beach Club", res["endereco"])


class CompromissoDeHojeGanhaDoDeOntemTestCase(_Base):
    def test_ajustar_pega_o_date_de_hoje_e_nao_mostra_o_de_ontem(self):
        """O erro "mais de um combina" listava o date de ontem e a IA misturava os dois na resposta."""
        self.sql("INSERT INTO tasks (title, due_date, hora, estilo) VALUES "
                 "('Date com a Ana - shopping e cinema', ?, '18:15', 'date')", (ONTEM,))
        self.sql("INSERT INTO tasks (title, due_date, hora, estilo) VALUES "
                 "('Date com a Ana - buscar na casa dela', ?, '20:00', 'date')", (HOJE,))
        _, res = self.chat([("ajustar_tarefa", {"titulo": "Date com a Ana", "hora": "20:20"})])
        self.assertTrue(res[0].get("ok"), res[0])
        horas = {r["due_date"]: r["hora"] for r in self.sql("SELECT due_date, hora FROM tasks")}
        self.assertEqual(horas, {ONTEM: "18:15", HOJE: "20:20"})

    def test_duas_de_hoje_continua_perguntando(self):
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Ligar pro banco', ?), ('Ligar pro banco do carro', ?)",
                 (HOJE, HOJE))
        _, res = self.chat([("ajustar_tarefa", {"titulo": "ligar pro banco", "hora": "10:00"})])
        self.assertTrue(res[0].get("ok") or "candidatas" in res[0], res[0])


class OfertaGenericaNoFimTestCase(unittest.TestCase):
    def test_quer_que_eu_generico_sai_e_o_concreto_fica(self):
        self.assertEqual(revisor_chat.limpar("Anotei amanhã às 6h. Quer que eu mexa em mais alguma coisa do dia?"),
                         "Anotei amanhã às 6h.")
        self.assertEqual(revisor_chat.limpar("Tem as placas e o quarto. Quer que eu encaixe alguma delas?"),
                         "Tem as placas e o quarto.")
        concreto = "Não tem hábito de leitura. Quer que eu crie o hábito agora e marque hoje?"
        self.assertEqual(revisor_chat.limpar(concreto), concreto)


class CoposPelaVozTestCase(unittest.TestCase):
    def test_resposta_local_da_saude_diz_o_numero_de_copos(self):
        """"quantos copos de agua eu tomei hoje" pela voz ouvia so "Tua saude hoje." (o numero so no card)."""
        import app

        def frase(n):
            return app._frase_local({"tool": "consultar_saude_dia", "resultado": {"agua_copos_hoje": n}})

        self.assertEqual(frase(3), "Hoje tu tomou 3 copos de água.")
        self.assertEqual(frase(1), "Hoje tu tomou 1 copo de água.")
        self.assertEqual(frase(0), "Hoje ainda não tem copo de água anotado.")
        self.assertEqual(app._frase_local({"tool": "consultar_saude_dia", "resultado": {}}), "Tua saúde hoje.")


class OfertaSemFraseQuebradaTestCase(unittest.TestCase):
    def test_nao_sobra_so_a_oracao_de_condicao(self):
        casos = {
            "Deixei o IPVA pro dia 15, domingo. Como cai num domingo, se quiser outro dia é só falar.":
                "Deixei o IPVA pro dia 15, domingo.",
            "Meta criada: 5 mil até março. Se for pra algo específico (carro, viagem...), me fala que eu ajusto.":
                "Meta criada: 5 mil até março.",
            "Marquei às 9h. Como tu pediu, deixei de manhã, se quiser outro é só falar.":
                "Marquei às 9h. Como tu pediu, deixei de manhã.",
            "O total ficou R$ 1.250, se quiser outro valor me fala que eu ajusto.": "O total ficou R$ 1.250.",
            "Passei o date pras 20h20. Se os 20 minutos eram do Venvanse, que era às 7h30, me avisa que eu ajeito.":
                "Passei o date pras 20h20.",
            "Choveu. Se chover de novo, leva guarda-chuva, e se quiser outro horário é só falar.":
                "Choveu. Se chover de novo, leva guarda-chuva.",
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(revisor_chat.limpar(texto), esperado)


class HoraSemZeroTestCase(unittest.TestCase):
    def test_hora_com_zero_na_frente_vira_o_jeito_dele(self):
        self.assertEqual(revisor_chat.limpar("Agendado pras 07h31, aviso no iPhone."),
                         "Agendado pras 7h31, aviso no iPhone.")
        self.assertEqual(revisor_chat.limpar("Sai 09h e chega 10h15."), "Sai 9h e chega 10h15.")
        self.assertEqual(revisor_chat.limpar("Voo de 1h05, decola 10h00."), "Voo de 1h05, decola 10h00.")

    def test_ta_sem_acento_e_frase_de_nao_duplicou(self):
        self.assertEqual(revisor_chat.limpar("Por enquanto ta quase limpo. Ta bom?"), "Por enquanto tá quase limpo. Tá bom?")
        self.assertEqual(
            revisor_chat.limpar("Já tá aí: ração amanhã às 8h45. Não precisei criar de novo, então não duplicou nada."),
            "Já tá aí: ração amanhã às 8h45.")
        self.assertEqual(revisor_chat.limpar("Não duplicou nada."), "Não duplicou nada.")  # sobraria nada: fica


class RegraFalaTuTestCase(unittest.TestCase):
    def test_resumo_da_regra_de_lugar_com_tu_e_preposicao(self):
        from assistente import regras

        def frase(tipo, lugar):
            return regras.montar_resumo_regra({"gatilho": "sinal_iphone", "condicao": {"tipo": tipo, "lugar": lugar}})

        self.assertEqual(frase("cheguei", "mercado"), "Vou te avisar quando tu chegar no mercado.")
        self.assertEqual(frase("cheguei", "obra"), "Vou te avisar quando tu chegar na obra.")
        self.assertEqual(frase("sai", "casa"), "Vou te avisar quando tu sair de casa.")
        self.assertNotIn("você", frase("acordei", None))


class LembreteDeUmaVezTestCase(unittest.TestCase):
    def test_me_lembra_sem_repeticao_fica_com_a_ia(self):
        """"me lembra de tomar o remedio as 7" virava regra de "todo dia as 07:00"."""
        for frase in ("me lembra de tomar o remedio as 7", "me lembra de ligar pro contador amanha",
                      "me lembra dia 15 de pagar o ipva"):
            with self.subTest(frase=frase):
                self.assertIsNone(p4_regra.casar(frase))

    def test_com_repeticao_ou_condicao_continua_regra(self):
        for frase in ("todo dia as 7 me lembra de tomar o remedio", "me lembra toda manha de alongar",
                      "me lembra de comprar pao quando eu passar no mercado", "me lembra sempre de beber agua",
                      "me avisa se eu gastar mais de 100 com uber"):
            with self.subTest(frase=frase):
                self.assertIsNotNone(p4_regra.casar(frase))


class AtrasoVaiProChatTestCase(unittest.TestCase):
    def test_atraso_dito_nao_cai_no_replanejar_local(self):
        """"atrasei uns 20 minutos" virava "Reorganizei o resto do teu dia" e pulava a conta do compromisso."""
        for frase in ("atrasei uns 20 minutos", "atrasei", "me atrasei de novo", "to atrasado"):
            with self.subTest(frase=frase):
                self.assertIsNone(p5_replanejar.casar(frase))
                r = classificador_local.casar(frase)
                self.assertTrue(r is None or r["regra"] != "p5_replanejar", r)
                self.assertTrue(roteador_chat.precisa_pensar(frase))

    def test_replanejar_de_verdade_continua_local(self):
        for frase in ("baguncou meu dia", "replaneja meu dia", "perdi a manha"):
            with self.subTest(frase=frase):
                self.assertIsNotNone(p5_replanejar.casar(frase))


AMANHA = (date.today() + timedelta(days=1)).isoformat()


class CompromissoDeOntemNaoMudaDeDiaTestCase(_Base):
    """4a rodada: "date hoje as 20h" MUDOU o date de ontem (ainda aberto) pra hoje - o de ontem sumiu."""

    def setUp(self):
        super().setUp()
        self.sql("INSERT INTO tasks (title, due_date, hora, estilo, local) VALUES "
                 "('Date com a Ana - shopping e cinema', ?, '18:15', 'date', 'Shopping Teste')", (ONTEM,))

    def test_ajustar_pro_dia_de_hoje_recusa_e_manda_criar_outro(self):
        _, res = self.chat([("ajustar_tarefa", {"titulo": "Date com a Ana", "quando_data": HOJE, "hora": "20:00"})])
        self.assertIn("erro", res[0])
        self.assertIn("registrar_tarefa", res[0]["erro"])
        self.assertEqual(res[0]["compromisso_antigo"]["dia"], ONTEM)
        self.assertEqual([(r["due_date"], r["hora"]) for r in self.sql("SELECT due_date, hora FROM tasks")],
                         [(ONTEM, "18:15")])

    def test_mesmo_compromisso_remarcado_ainda_muda(self):
        _, res = self.chat([("ajustar_tarefa", {"titulo": "Date com a Ana", "quando_data": HOJE, "hora": "20:00",
                                                "mesmo_compromisso": True})])
        self.assertTrue(res[0].get("ok"), res[0])
        self.assertEqual(self.sql("SELECT due_date FROM tasks")[0]["due_date"], HOJE)

    def test_tarefa_comum_atrasada_continua_sendo_adiada(self):
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Limpar meu quarto', ?)", (ONTEM,))
        _, res = self.chat([("ajustar_tarefa", {"titulo": "Limpar meu quarto", "quando_data": HOJE})])
        self.assertTrue(res[0].get("ok"), res[0])
        self.assertEqual(self.sql("SELECT due_date FROM tasks WHERE title = 'Limpar meu quarto'")[0]["due_date"],
                         HOJE)

    def test_concluir_o_de_ontem_continua_valendo(self):
        _, res = self.chat([("ajustar_tarefa", {"titulo": "Date com a Ana", "status": "concluir"})])
        self.assertTrue(res[0].get("ok"), res[0])

    def test_schema_tem_a_saida_pro_remarcado(self):
        from ia.funcoes import chat as funcoes_chat

        ajustar = next(f for f in funcoes_chat.CHAT_TOOLS if f["name"] == "ajustar_tarefa")
        self.assertIn("mesmo_compromisso", ajustar["input_schema"]["properties"])


class AdiaTudoDeHojeLevaAtrasadaTestCase(_Base):
    """4a rodada: "adia tudo de hoje pra amanha" respondia "nada pendente" com tarefa atrasada aberta."""

    def setUp(self):
        super().setUp()
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Banco', ?)", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Limpar meu quarto', ?)", (ONTEM,))
        self.sql("INSERT INTO tasks (title, due_date, hora, estilo) VALUES ('Date com a Ana', ?, '18:15', 'date')",
                 (ONTEM,))

    def test_hoje_pra_amanha_leva_a_atrasada_e_deixa_o_compromisso_passado(self):
        _, res = self.chat([("mover_tarefas", {"de_data": HOJE, "para_data": AMANHA})])
        self.assertTrue(res[0].get("ok"), res[0])
        self.assertEqual(set(res[0]["movidas"]), {"Banco", "Limpar meu quarto"})
        self.assertEqual(res[0]["atrasadas_junto"], ["Limpar meu quarto"])
        dias = {r["title"]: r["due_date"] for r in self.sql("SELECT title, due_date FROM tasks")}
        self.assertEqual(dias, {"Banco": AMANHA, "Limpar meu quarto": AMANHA, "Date com a Ana": ONTEM})
        adiadas = {r["de"] for r in self.sql("SELECT de FROM tarefas_adiadas")}
        self.assertEqual(adiadas, {HOJE, ONTEM})

    def test_outro_dia_nao_puxa_atrasada(self):
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Dentista', ?)", (AMANHA,))
        depois = (date.today() + timedelta(days=2)).isoformat()
        _, res = self.chat([("mover_tarefas", {"de_data": AMANHA, "para_data": depois})])
        self.assertEqual(res[0]["movidas"], ["Dentista"])
        self.assertNotIn("atrasadas_junto", res[0])


class CorteSemConectorSoltoTestCase(unittest.TestCase):
    def test_entao_solto_sai_junto_com_a_oferta(self):
        texto = ('Tirei o quartinho dessa semana. O "Limpar meu quarto" continua onde estava, então se for esse '
                 'que tu quis dizer, me fala que eu ajusto.')
        self.assertTrue(revisor_chat.limpar(texto).endswith("continua onde estava."))

    def test_se_quiser_eu_mudo_tambem_e_oferta(self):
        self.assertEqual(revisor_chat.limpar("Anotado pras 7h. O resto ficou igual, se quiser eu mudo o horário."),
                         "Anotado pras 7h. O resto ficou igual.")

    def test_entao_de_fecho_dele_fica(self):
        for texto in ("Beleza, fica pra amanhã então.", "O carro tá aí. Se quiser eu te lembro de buscar."):
            with self.subTest(texto=texto):
                self.assertEqual(revisor_chat.limpar(texto), texto)

    def test_me_fala_que_eu_recalculo_e_oferta(self):
        """5a rodada: "Se mudar a hora do date, me fala que eu recalculo." passou no fim da resposta."""
        self.assertEqual(revisor_chat.limpar("Tu sai 19h38. Se mudar a hora do date, me fala que eu recalculo."),
                         "Tu sai 19h38.")


class DateNovoNaoHerdaOLugarDeOntemTestCase(unittest.TestCase):
    def test_prompt_diz_que_o_programa_de_ontem_nao_passa(self):
        """5a rodada: date novo hoje e a IA repetiu o lugar do date de ontem."""
        from ia.funcoes import chat as funcoes_chat

        texto = " ".join(funcoes_chat.CHAT_SYSTEM_PROMPT.split())
        self.assertIn("lugar, parada e programa do de ontem NAO passam pro de hoje", texto)


if __name__ == "__main__":
    unittest.main()
