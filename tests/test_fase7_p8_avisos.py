"""Fase 7, faixa P8: assistente/avisos.py - catalogo, liga/desliga por tipo,
canal, horario de silencio (global e por tipo, cruzando meia-noite) e tipo
desconhecido. Nao registra nenhuma rota nem app - so o modulo, com banco
temporario (mesmo padrao leve de tests/test_ia_teto.py: db.init_db() com
DB_PATH trocado, sem importar app.py)."""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db
from assistente import avisos


class _BaseAvisosTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()


class CatalogoTestCase(_BaseAvisosTestCase):
    def test_seis_proatividades_da_fase_6_estao_no_catalogo(self):
        for tipo in (
            "habito_passou_batido",
            "tarefa_horario_passou",
            "cartao_limite",
            "renda_comprometida",
            "projeto_poeira",
            "mes_seguinte_apertado",
        ):
            self.assertIn(tipo, avisos.TIPOS)

    def test_tipos_novos_do_prompt_estao_no_catalogo(self):
        for tipo in (
            "pergunta_conta",
            "reuniao",
            "tarefa_vencida",
            "lembrete",
            "espera",
            "briefing_manha",
            "briefing_noite",
            "regra",
            "sinal",
            "memoria_viva",
            "replanejar",
        ):
            self.assertIn(tipo, avisos.TIPOS)

    def test_tipos_existentes_de_notificacoes_py_estao_no_catalogo(self):
        # Mesmo texto de tipo que app.py:verificar_e_notificar ja usa em
        # avisos.append((tipo, ...)) - ver progress.txt pro arquivo:linha.
        for tipo in (
            "tarefas_atrasadas",
            "tarefa_parada",
            "espera_parada",
            "orcamento",
            "teto_ia",
            "cartao_limite",
            "conta_a_vencer",
            "garantia_vencendo",
        ):
            self.assertIn(tipo, avisos.TIPOS)

    def test_cada_tipo_tem_label_e_padroes(self):
        for tipo, info in avisos.TIPOS.items():
            self.assertTrue(info["label"], tipo)
            self.assertIsInstance(info["ligado_padrao"], bool)
            self.assertIn(info["canal_padrao"], avisos.CANAIS)

    def test_todo_tipo_comeca_ligado_por_padrao(self):
        # Contrato: "O padrao e ligado" (fase7-assistente.md, secao Flags,
        # mesmo espirito aplicado aqui por tipo).
        for tipo in avisos.TIPOS:
            self.assertTrue(avisos.esta_ligado(tipo, conn=self.conn), tipo)


class LigaDesligaTestCase(_BaseAvisosTestCase):
    # `agora` sempre injetado (meio-dia, bem longe do silencio padrao
    # 22:00-07:00) pra estes testes nao dependerem da hora real em que
    # rodam - so test_fase7_p8_avisos::SilencioGlobalTestCase testa timing.
    MEIO_DIA = datetime(2026, 9, 24, 12, 0)

    def test_desligar_tipo_bloqueia_aviso_permitido(self):
        self.assertTrue(avisos.aviso_permitido("cartao_limite", agora=self.MEIO_DIA, conn=self.conn))
        avisos.definir_tipo("cartao_limite", ligado=False, conn=self.conn)
        self.assertFalse(avisos.esta_ligado("cartao_limite", conn=self.conn))
        self.assertFalse(avisos.aviso_permitido("cartao_limite", agora=self.MEIO_DIA, conn=self.conn))

    def test_religar_tipo_volta_a_permitir(self):
        avisos.definir_tipo("cartao_limite", ligado=False, conn=self.conn)
        avisos.definir_tipo("cartao_limite", ligado=True, conn=self.conn)
        self.assertTrue(avisos.esta_ligado("cartao_limite", conn=self.conn))

    def test_desligar_um_tipo_nao_afeta_outro(self):
        avisos.definir_tipo("cartao_limite", ligado=False, conn=self.conn)
        self.assertTrue(avisos.esta_ligado("renda_comprometida", conn=self.conn))

    def test_tipo_desconhecido_e_permitido_por_padrao(self):
        # Decisao documentada em assistente/avisos.py: tipo fora do
        # catalogo nao fica mudo por omissao.
        self.assertNotIn("tipo_bem_inexistente_xyz", avisos.TIPOS)
        self.assertTrue(avisos.esta_ligado("tipo_bem_inexistente_xyz", conn=self.conn))
        self.assertTrue(
            avisos.aviso_permitido("tipo_bem_inexistente_xyz", agora=self.MEIO_DIA, conn=self.conn)
        )

    def test_definir_tipo_desconhecido_leva_excecao(self):
        with self.assertRaises(avisos.TipoDesconhecido):
            avisos.definir_tipo("tipo_bem_inexistente_xyz", ligado=False, conn=self.conn)


class CanalTestCase(_BaseAvisosTestCase):
    def test_canal_padrao_e_ambos(self):
        self.assertEqual(avisos.canal("lembrete", conn=self.conn), "ambos")

    def test_definir_canal_so_push(self):
        avisos.definir_tipo("lembrete", canal="push", conn=self.conn)
        self.assertEqual(avisos.canal("lembrete", conn=self.conn), "push")

    def test_definir_canal_so_caixa(self):
        avisos.definir_tipo("lembrete", canal="caixa", conn=self.conn)
        self.assertEqual(avisos.canal("lembrete", conn=self.conn), "caixa")

    def test_canal_invalido_levanta_value_error(self):
        with self.assertRaises(ValueError):
            avisos.definir_tipo("lembrete", canal="sms", conn=self.conn)

    def test_canal_desconhecido_cai_no_padrao_ambos(self):
        self.assertEqual(avisos.canal("tipo_bem_inexistente_xyz", conn=self.conn), "ambos")


class SilencioGlobalTestCase(_BaseAvisosTestCase):
    def test_padrao_e_22h_as_7h(self):
        silencio = avisos.obter_silencio_global(conn=self.conn)
        self.assertEqual(silencio, {"inicio": "22:00", "fim": "07:00"})

    def test_23h_cai_no_silencio_padrao(self):
        agora = datetime(2026, 9, 24, 23, 0)
        self.assertFalse(avisos.aviso_permitido("lembrete", agora=agora, conn=self.conn))

    def test_meio_dia_nao_cai_no_silencio_padrao(self):
        agora = datetime(2026, 9, 24, 12, 0)
        self.assertTrue(avisos.aviso_permitido("lembrete", agora=agora, conn=self.conn))

    def test_janela_cruza_meia_noite_3h_da_manha_em_silencio(self):
        agora = datetime(2026, 9, 24, 3, 0)
        self.assertFalse(avisos.aviso_permitido("lembrete", agora=agora, conn=self.conn))

    def test_limite_inicio_e_silencio_fim_nao_e(self):
        # [inicio, fim) - 22:00 exato ja silencia, 07:00 exato ja nao silencia
        self.assertFalse(
            avisos.aviso_permitido("lembrete", agora=datetime(2026, 9, 24, 22, 0), conn=self.conn)
        )
        self.assertTrue(
            avisos.aviso_permitido("lembrete", agora=datetime(2026, 9, 24, 7, 0), conn=self.conn)
        )

    def test_definir_silencio_global_customizado(self):
        avisos.definir_silencio_global("20:00", "06:00", conn=self.conn)
        self.assertEqual(
            avisos.obter_silencio_global(conn=self.conn), {"inicio": "20:00", "fim": "06:00"}
        )
        self.assertFalse(
            avisos.aviso_permitido("lembrete", agora=datetime(2026, 9, 24, 20, 30), conn=self.conn)
        )
        # 22:30 nao silenciaria mais no padrao antigo, mas com o novo (20-6) sim
        self.assertFalse(
            avisos.aviso_permitido("lembrete", agora=datetime(2026, 9, 24, 22, 30), conn=self.conn)
        )

    def test_hora_invalida_levanta_value_error(self):
        with self.assertRaises(ValueError):
            avisos.definir_silencio_global("25:00", "07:00", conn=self.conn)
        with self.assertRaises(ValueError):
            avisos.definir_silencio_global("22:00", "7:00", conn=self.conn)
        with self.assertRaises(ValueError):
            avisos.definir_silencio_global("22:00", "not-a-time", conn=self.conn)


class SilencioPorTipoTestCase(_BaseAvisosTestCase):
    def test_tipo_sem_override_segue_o_global(self):
        avisos.definir_silencio_global("21:00", "08:00", conn=self.conn)
        estado = avisos.estado_tipo("lembrete", conn=self.conn)
        self.assertEqual(estado["silencio_inicio"], "21:00")
        self.assertEqual(estado["silencio_fim"], "08:00")
        self.assertFalse(estado["silencio_customizado"])

    def test_override_por_tipo_sobrepoe_o_global(self):
        avisos.definir_silencio_global("22:00", "07:00", conn=self.conn)
        avisos.definir_tipo(
            "briefing_noite", silencio_inicio="23:00", silencio_fim="06:00", conn=self.conn
        )
        # 22:30 silenciaria no global, mas nao no override do tipo (23h-6h)
        self.assertTrue(
            avisos.aviso_permitido("briefing_noite", agora=datetime(2026, 9, 24, 22, 30), conn=self.conn)
        )
        self.assertFalse(
            avisos.aviso_permitido("briefing_noite", agora=datetime(2026, 9, 24, 23, 30), conn=self.conn)
        )
        # outro tipo, sem override, continua no global
        self.assertFalse(
            avisos.aviso_permitido("lembrete", agora=datetime(2026, 9, 24, 22, 30), conn=self.conn)
        )

    def test_override_parcial_e_ignorado(self):
        # So inicio, sem fim: nao forma janela valida - cai no global.
        avisos.definir_tipo("briefing_noite", silencio_inicio="23:00", conn=self.conn)
        estado = avisos.estado_tipo("briefing_noite", conn=self.conn)
        self.assertFalse(estado["silencio_customizado"])
        self.assertEqual(estado["silencio_inicio"], "22:00")

    def test_limpar_override_com_string_vazia(self):
        avisos.definir_tipo(
            "briefing_noite", silencio_inicio="23:00", silencio_fim="06:00", conn=self.conn
        )
        avisos.definir_tipo("briefing_noite", silencio_inicio="", silencio_fim="", conn=self.conn)
        estado = avisos.estado_tipo("briefing_noite", conn=self.conn)
        self.assertFalse(estado["silencio_customizado"])


class EstadoTestCase(_BaseAvisosTestCase):
    def test_listar_estado_cobre_todo_catalogo(self):
        estados = avisos.listar_estado(conn=self.conn)
        self.assertEqual(len(estados), len(avisos.TIPOS))
        tipos_listados = {e["tipo"] for e in estados}
        self.assertEqual(tipos_listados, set(avisos.TIPOS))

    def test_estado_tipo_desconhecido_marca_nao_conhecido(self):
        estado = avisos.estado_tipo("tipo_bem_inexistente_xyz", conn=self.conn)
        self.assertFalse(estado["conhecido"])
        self.assertTrue(estado["ligado"])

    def test_config_persiste_entre_conexoes(self):
        avisos.definir_tipo("cartao_limite", ligado=False, canal="push", conn=self.conn)
        outra_conexao = db.get_db()
        try:
            estado = avisos.estado_tipo("cartao_limite", conn=outra_conexao)
        finally:
            outra_conexao.close()
        self.assertFalse(estado["ligado"])
        self.assertEqual(estado["canal"], "push")


if __name__ == "__main__":
    unittest.main()
