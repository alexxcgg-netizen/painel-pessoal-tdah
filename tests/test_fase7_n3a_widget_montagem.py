"""Fase 7, faixa N3a - testes da funcao PURA que monta o JSON do widget
(`rotas.n3a_widget.montar_widget`/`estado_erro`). Sem banco, sem Flask, sem
token - so a montagem do dict a partir de dados ja coletados. Ver
tests/test_fase7_n3a_widget_api.py pros testes de token/rota/pagina."""

import os
import unittest
from datetime import datetime, timezone

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from rotas.n3a_widget import estado_erro, montar_widget

AGORA_UTC = datetime(2026, 9, 23, 20, 10, 0, tzinfo=timezone.utc)


class FormatoBaseTestCase(unittest.TestCase):
    """Toda resposta - normal, vazia ou erro - tem SEMPRE as mesmas 10
    chaves de topo (campo ausente vira null, nunca some), pro Widgy nunca
    quebrar um caminho JSON fixo tipo `foco.titulo`."""

    CHAVES_ESPERADAS = {
        "versao",
        "atualizado_em",
        "estado",
        "foco",
        "proxima_conta",
        "habitos",
        "custo_ia",
        "comida",
        "agenda",
        "agua",
        "horas_voo",
        "hoje",
        "voo",
        "linhas",
    }

    def test_chaves_de_topo_sempre_presentes_vazio(self):
        r = montar_widget(agora_utc=AGORA_UTC)
        self.assertEqual(set(r.keys()), self.CHAVES_ESPERADAS)

    def test_chaves_de_topo_sempre_presentes_erro(self):
        r = estado_erro(AGORA_UTC)
        self.assertEqual(set(r.keys()), self.CHAVES_ESPERADAS)

    def test_chaves_de_topo_sempre_presentes_tudo_preenchido(self):
        r = montar_widget(
            agora_utc=AGORA_UTC,
            foco={"titulo": "Revisar contrato", "em_minutos": 19},
            proxima_conta={"nome": "Cartao", "em_dias": 3, "valor": 450.0, "origem": "pessoal"},
            habitos={"feitos": 3, "total": 5},
            custo_ia_percentual=42,
        )
        self.assertEqual(set(r.keys()), self.CHAVES_ESPERADAS)

    def test_versao_e_sempre_1(self):
        self.assertEqual(montar_widget(agora_utc=AGORA_UTC)["versao"], 1)
        self.assertEqual(estado_erro(AGORA_UTC)["versao"], 1)

    def test_atualizado_em_formato_iso_z(self):
        r = montar_widget(agora_utc=AGORA_UTC)
        self.assertEqual(r["atualizado_em"], "2026-09-23T20:10:00Z")


class ExemploDoContratoTestCase(unittest.TestCase):
    """Reproduz EXATAMENTE o exemplo do enunciado/docs/widget-widgy.md."""

    def setUp(self):
        self.r = montar_widget(
            agora_utc=AGORA_UTC,
            foco={"titulo": "Revisar contrato", "em_minutos": 19},
            proxima_conta={"nome": "Cartão", "em_dias": 3, "valor": 999.0, "origem": "pessoal"},
            habitos={"feitos": 3, "total": 5},
            custo_ia_percentual=42,
            mostrar_valores=False,
        )

    def test_estado_normal(self):
        self.assertEqual(self.r["estado"], "normal")

    def test_foco(self):
        self.assertEqual(self.r["foco"], {"titulo": "Revisar contrato", "em_minutos": 19})

    def test_proxima_conta_sem_valor_por_padrao(self):
        self.assertEqual(self.r["proxima_conta"], {"nome": "Cartão", "em_dias": 3})
        self.assertNotIn("valor", self.r["proxima_conta"])

    def test_habitos(self):
        self.assertEqual(self.r["habitos"], {"feitos": 3, "total": 5})

    def test_custo_ia(self):
        self.assertEqual(self.r["custo_ia"], {"percentual_teto": 42})

    def test_linhas_no_formato_e_ordem_exatos(self):
        self.assertEqual(
            self.r["linhas"],
            [
                "Foco: Revisar contrato em 19 min",
                "Conta: Cartão em 3 dias",
                "Hábitos: 3/5",
                "IA: 42% do teto",
            ],
        )


class SemValorPorPadraoTestCase(unittest.TestCase):
    def test_mostrar_valores_false_nao_inclui_valor(self):
        r = montar_widget(
            agora_utc=AGORA_UTC,
            proxima_conta={"nome": "Luz", "em_dias": 5, "valor": 210.5, "origem": "pessoal"},
            mostrar_valores=False,
        )
        self.assertNotIn("valor", r["proxima_conta"])

    def test_mostrar_valores_default_e_false(self):
        r = montar_widget(
            agora_utc=AGORA_UTC,
            proxima_conta={"nome": "Luz", "em_dias": 5, "valor": 210.5, "origem": "pessoal"},
        )
        self.assertNotIn("valor", r["proxima_conta"])

    def test_mostrar_valores_true_inclui_valor_de_conta_pessoal(self):
        r = montar_widget(
            agora_utc=AGORA_UTC,
            proxima_conta={"nome": "Luz", "em_dias": 5, "valor": 210.5, "origem": "pessoal"},
            mostrar_valores=True,
        )
        self.assertEqual(r["proxima_conta"]["valor"], 210.5)

    def test_mostrar_valores_true_NUNCA_inclui_valor_de_conta_da_construtora(self):
        """Regra de ouro: nenhum dado financeiro real da empresa sai por
        aqui, nem com mostrar_valores=1."""
        r = montar_widget(
            agora_utc=AGORA_UTC,
            proxima_conta={
                "nome": "Fornecedor X",
                "em_dias": 2,
                "valor": 15000.0,
                "origem": "construtora",
            },
            mostrar_valores=True,
        )
        self.assertNotIn("valor", r["proxima_conta"])
        self.assertEqual(r["proxima_conta"], {"nome": "Fornecedor X", "em_dias": 2})

    def test_mostrar_valores_true_mas_conta_pessoal_sem_valor_cadastrado(self):
        r = montar_widget(
            agora_utc=AGORA_UTC,
            proxima_conta={"nome": "Internet", "em_dias": 1, "valor": None, "origem": "pessoal"},
            mostrar_valores=True,
        )
        self.assertNotIn("valor", r["proxima_conta"])

    def test_origem_nunca_vaza_pro_json_de_saida(self):
        r = montar_widget(
            agora_utc=AGORA_UTC,
            proxima_conta={"nome": "Luz", "em_dias": 5, "valor": 210.5, "origem": "pessoal"},
            mostrar_valores=True,
        )
        self.assertNotIn("origem", r["proxima_conta"])


class EstadoTestCase(unittest.TestCase):
    def test_estado_vazio_sem_nenhum_dado(self):
        r = montar_widget(agora_utc=AGORA_UTC)
        self.assertEqual(r["estado"], "vazio")
        self.assertIsNone(r["foco"])
        self.assertIsNone(r["proxima_conta"])
        self.assertIsNone(r["habitos"])
        self.assertIsNone(r["custo_ia"])
        self.assertEqual(r["linhas"], [])

    def test_estado_normal_com_so_um_campo_preenchido(self):
        r = montar_widget(agora_utc=AGORA_UTC, custo_ia_percentual=10)
        self.assertEqual(r["estado"], "normal")

    def test_estado_normal_com_so_foco(self):
        r = montar_widget(agora_utc=AGORA_UTC, foco={"titulo": "X", "em_minutos": 1})
        self.assertEqual(r["estado"], "normal")

    def test_estado_erro_tem_tudo_null(self):
        r = estado_erro(AGORA_UTC)
        self.assertEqual(r["estado"], "erro")
        self.assertIsNone(r["foco"])
        self.assertIsNone(r["proxima_conta"])
        self.assertIsNone(r["habitos"])
        self.assertIsNone(r["custo_ia"])
        self.assertEqual(r["linhas"], [])

    def test_habitos_total_zero_vira_none_e_nao_conta_como_dado(self):
        """Dia sem nenhum habito devido: total=0 nao tem o que mostrar,
        entra como se habitos fosse None."""
        r = montar_widget(agora_utc=AGORA_UTC, habitos={"feitos": 0, "total": 0})
        self.assertIsNone(r["habitos"])
        self.assertEqual(r["estado"], "vazio")


class LinhaContaTestCase(unittest.TestCase):
    def test_conta_vence_hoje(self):
        r = montar_widget(
            agora_utc=AGORA_UTC,
            proxima_conta={"nome": "Cartao", "em_dias": 0, "valor": None, "origem": "pessoal"},
        )
        self.assertIn("Conta: Cartao vence hoje", r["linhas"])

    def test_conta_vencida(self):
        r = montar_widget(
            agora_utc=AGORA_UTC,
            proxima_conta={"nome": "Cartao", "em_dias": -2, "valor": None, "origem": "pessoal"},
        )
        self.assertIn("Conta: Cartao vencida há 2 dias", r["linhas"])

    def test_conta_em_dias_none(self):
        r = montar_widget(
            agora_utc=AGORA_UTC,
            proxima_conta={"nome": "Cartao", "em_dias": None, "valor": None, "origem": "construtora"},
        )
        self.assertEqual(r["proxima_conta"]["em_dias"], None)
        self.assertIn("Conta: Cartao", r["linhas"])


class PercentualTetoArredondamentoTestCase(unittest.TestCase):
    def test_arredonda_pra_inteiro(self):
        r = montar_widget(agora_utc=AGORA_UTC, custo_ia_percentual=41.6)
        self.assertEqual(r["custo_ia"]["percentual_teto"], 42)

    def test_aceita_acima_de_100_com_teto_estourado(self):
        r = montar_widget(agora_utc=AGORA_UTC, custo_ia_percentual=137.2)
        self.assertEqual(r["custo_ia"]["percentual_teto"], 137)

    def test_zero_por_cento_ainda_conta_como_dado_presente(self):
        r = montar_widget(agora_utc=AGORA_UTC, custo_ia_percentual=0)
        self.assertEqual(r["custo_ia"], {"percentual_teto": 0})
        self.assertEqual(r["estado"], "normal")
        self.assertIn("IA: 0% do teto", r["linhas"])


ITEM_AGENDA = {"hora": "14:30", "titulo": "Dentista", "em_minutos": 40, "tipo": "compromisso", "concluido": False}


class ComidaMacrosMontagemTestCase(unittest.TestCase):
    def test_carbo_e_gordura_passam_arredondados(self):
        r = montar_widget(
            agora_utc=AGORA_UTC,
            comida={
                "kcal": 415.4,
                "proteina_g": 83.2,
                "carbo_g": 52.6,
                "gordura_g": 12.4,
                "refeicoes": 2,
                "meta_kcal": 2550,
                "meta_proteina_g": 115,
            },
        )
        self.assertEqual(
            r["comida"],
            {
                "kcal": 415,
                "proteina_g": 83,
                "carbo_g": 53,
                "gordura_g": 12,
                "refeicoes": 2,
                "meta_kcal": 2550,
                "meta_proteina_g": 115,
            },
        )

    def test_carbo_e_gordura_default_zero_quando_ausentes(self):
        r = montar_widget(agora_utc=AGORA_UTC, comida={"kcal": 100, "refeicoes": 1})
        self.assertEqual(r["comida"]["carbo_g"], 0)
        self.assertEqual(r["comida"]["gordura_g"], 0)


class AgendaMontagemTestCase(unittest.TestCase):
    def test_vazio_sem_agenda_devolve_lista_vazia(self):
        r = montar_widget(agora_utc=AGORA_UTC)
        self.assertEqual(r["agenda"], [])
        self.assertEqual(r["estado"], "vazio")

    def test_agenda_none_na_montagem_vira_lista_vazia(self):
        r = montar_widget(agora_utc=AGORA_UTC, agenda=None)
        self.assertEqual(r["agenda"], [])

    def test_erro_tem_agenda_none(self):
        r = estado_erro(AGORA_UTC)
        self.assertIsNone(r["agenda"])

    def test_agenda_nao_vazia_conta_como_dado_e_estado_normal(self):
        r = montar_widget(agora_utc=AGORA_UTC, agenda=[ITEM_AGENDA])
        self.assertEqual(r["estado"], "normal")
        self.assertEqual(r["agenda"], [ITEM_AGENDA])

    def test_agenda_nao_entra_em_linhas(self):
        r = montar_widget(
            agora_utc=AGORA_UTC,
            foco={"titulo": "Revisar contrato", "em_minutos": 19},
            agenda=[ITEM_AGENDA],
        )
        self.assertEqual(r["linhas"], ["Foco: Revisar contrato em 19 min"])


if __name__ == "__main__":
    unittest.main()
