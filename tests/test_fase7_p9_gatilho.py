"""Faixa P9 (Fase 7, memoria viva) - assistente/gatilhos/p9_memoria.py:
executar (idempotente por semana ISO, so roda domingo a noite) e ao_resolver
(aceitar aplica a memoria, recusar so registra por 8 semanas). IA e Caixa
sempre mockadas, relogio sempre injetado."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db
from assistente.gatilhos import p9_memoria
from ia.contrato import Resposta

DOMINGO_A_NOITE = datetime(2026, 9, 27, 19, 5)  # domingo, 27/09/2026
DOMINGO_DE_TARDE = datetime(2026, 9, 27, 14, 0)
SEGUNDA = datetime(2026, 9, 28, 10, 0)


class _DbTestCase(unittest.TestCase):
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

    def _criar_habito_treino_consistente(self, agora):
        habito_id = db.create_habito(self.conn, "Treino", None, "diario", None, None, None)
        for i in range(8):
            dia = (agora.date() - timedelta(days=i)).isoformat()
            self.conn.execute(
                "INSERT INTO habito_marcacoes (data, habito_id, marcado_em) VALUES (?, ?, ?)",
                (dia, habito_id, f"{dia} 07:00:00"),
            )
        self.conn.commit()
        return habito_id


# ---------------------------------------------------------------------------
# executar: janela, idempotencia, flag
# ---------------------------------------------------------------------------

class ExecutarJanelaTestCase(_DbTestCase):
    def test_fora_da_janela_de_domingo_a_noite_nao_faz_nada(self):
        with patch.object(p9_memoria, "_caixa") as mock_caixa:
            p9_memoria.executar(self.conn, DOMINGO_DE_TARDE)
        mock_caixa.assert_not_called()

    def test_segunda_de_manha_nao_faz_nada(self):
        with patch.object(p9_memoria, "_caixa") as mock_caixa:
            p9_memoria.executar(self.conn, SEGUNDA)
        mock_caixa.assert_not_called()

    def test_flag_desligada_nao_faz_nada(self):
        db.definir_configuracao(self.conn, p9_memoria.FLAG_ATIVO, "0")
        with patch.object(p9_memoria, "_caixa") as mock_caixa:
            p9_memoria.executar(self.conn, DOMINGO_A_NOITE)
        mock_caixa.assert_not_called()

    def test_domingo_a_noite_sem_fato_nao_chama_caixa(self):
        with patch.object(p9_memoria, "_caixa") as mock_caixa:
            p9_memoria.executar(self.conn, DOMINGO_A_NOITE)
        mock_caixa.assert_not_called()
        # mas marca que rodou essa semana, pra nao tentar de novo (economiza IA)
        semana = p9_memoria._semana_iso(DOMINGO_A_NOITE)
        self.assertTrue(p9_memoria._ja_rodou_essa_semana(self.conn, semana))

    def test_segunda_chamada_na_mesma_semana_nao_gera_de_novo(self):
        self._criar_habito_treino_consistente(DOMINGO_A_NOITE)
        resposta = Resposta(ok=True, dados={
            "propostas": [{"acao": "adicionar", "memoria_id": None,
                           "texto": "Treina por volta das 7h.", "motivo": "padrao"}]
        })
        fake_caixa = MagicMock()
        fake_caixa.enfileirar.return_value = "item-1"
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta), \
             patch.object(p9_memoria, "_caixa", return_value=fake_caixa):
            p9_memoria.executar(self.conn, DOMINGO_A_NOITE)
            chamadas_primeira_vez = fake_caixa.enfileirar.call_count
            p9_memoria.executar(self.conn, DOMINGO_A_NOITE + timedelta(minutes=10))
        self.assertGreaterEqual(chamadas_primeira_vez, 1)
        # a segunda chamada, mesma semana, nao enfileira de novo
        self.assertEqual(fake_caixa.enfileirar.call_count, chamadas_primeira_vez)

    def test_fato_gera_proposta_e_enfileira_com_chave_unica_por_semana(self):
        self._criar_habito_treino_consistente(DOMINGO_A_NOITE)
        resposta = Resposta(ok=True, dados={
            "propostas": [{"acao": "adicionar", "memoria_id": None,
                           "texto": "Treina por volta das 7h.", "motivo": "padrao"}]
        })
        fake_caixa = MagicMock()
        fake_caixa.enfileirar.return_value = "item-1"
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta), \
             patch.object(p9_memoria, "_caixa", return_value=fake_caixa):
            p9_memoria.executar(self.conn, DOMINGO_A_NOITE)
        fake_caixa.enfileirar.assert_called_once()
        kwargs = fake_caixa.enfileirar.call_args.kwargs
        self.assertEqual(kwargs["tipo"], "proposta_memoria")
        semana = p9_memoria._semana_iso(DOMINGO_A_NOITE)
        self.assertTrue(kwargs["chave_unica"].startswith(f"p9:{semana}:"))
        self.assertTrue(kwargs["origem"].startswith("p9_memoria:"))
        self.assertIn("aceitar", kwargs["opcoes"])
        self.assertIn("recusar", kwargs["opcoes"])
        # a proposta pendente fica guardada, pronta pro ao_resolver aplicar
        row = self.conn.execute("SELECT * FROM p9_memoria_propostas").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["acao"], "adicionar")

    def test_fato_recusado_ha_2_semanas_nao_repropoe(self):
        habito_id = self._criar_habito_treino_consistente(DOMINGO_A_NOITE)
        chave = f"treino_horario:{habito_id}"
        p9_memoria._garantir_tabelas(self.conn)
        ha_2_semanas = (DOMINGO_A_NOITE - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "INSERT INTO p9_memoria_recusas (chave, texto, recusado_em) VALUES (?, '', ?)",
            (chave, ha_2_semanas),
        )
        self.conn.commit()
        with patch("assistente.memoria_viva.ia_core.chamar_ia") as mock_chamar, \
             patch.object(p9_memoria, "_caixa") as mock_caixa:
            p9_memoria.executar(self.conn, DOMINGO_A_NOITE)
        mock_chamar.assert_not_called()
        mock_caixa.assert_not_called()

    def test_fato_recusado_ha_10_semanas_pode_repropor(self):
        habito_id = self._criar_habito_treino_consistente(DOMINGO_A_NOITE)
        chave = f"treino_horario:{habito_id}"
        p9_memoria._garantir_tabelas(self.conn)
        ha_10_semanas = (DOMINGO_A_NOITE - timedelta(days=70)).strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "INSERT INTO p9_memoria_recusas (chave, texto, recusado_em) VALUES (?, '', ?)",
            (chave, ha_10_semanas),
        )
        self.conn.commit()
        resposta = Resposta(ok=True, dados={
            "propostas": [{"acao": "adicionar", "memoria_id": None,
                           "texto": "Treina por volta das 7h.", "motivo": "padrao"}]
        })
        fake_caixa = MagicMock()
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta), \
             patch.object(p9_memoria, "_caixa", return_value=fake_caixa):
            p9_memoria.executar(self.conn, DOMINGO_A_NOITE)
        fake_caixa.enfileirar.assert_called_once()


# ---------------------------------------------------------------------------
# ao_resolver: aceitar aplica, recusar so registra
# ---------------------------------------------------------------------------

class AoResolverTestCase(_DbTestCase):
    def _guardar_proposta(self, chave, acao, memoria_id, texto, categoria="sua_rotina"):
        p9_memoria._garantir_tabelas(self.conn)
        self.conn.execute(
            "INSERT INTO p9_memoria_propostas (chave, acao, memoria_id, texto, categoria) "
            "VALUES (?, ?, ?, ?, ?)",
            (chave, acao, memoria_id, texto, categoria),
        )
        self.conn.commit()

    def test_aceitar_adicionar_cria_memoria(self):
        self._guardar_proposta("sono_medio", "adicionar", None, "Dorme em media 6.5h por noite.")
        antes = len(db.list_memorias(self.conn, limit=1000))
        item = {"origem": "p9_memoria:sono_medio"}
        p9_memoria.ao_resolver(self.conn, item, "aceitar")
        depois = db.list_memorias(self.conn, limit=1000)
        self.assertEqual(len(depois), antes + 1)
        self.assertTrue(any(m["texto"] == "Dorme em media 6.5h por noite." for m in depois))
        # a proposta pendente foi consumida
        self.assertIsNone(
            self.conn.execute("SELECT 1 FROM p9_memoria_propostas WHERE chave = ?", ("sono_medio",)).fetchone()
        )

    def test_aceitar_alterar_atualiza_memoria_existente(self):
        memoria_id = db.create_memoria(self.conn, "Sono irregular, em ajuste.")
        self._guardar_proposta("sono_medio", "alterar", memoria_id, "Sono regularizou, media 6.5h.")
        item = {"origem": "p9_memoria:sono_medio"}
        p9_memoria.ao_resolver(self.conn, item, "aceitar")
        rows = db.list_memorias(self.conn, limit=1000)
        alvo = next(m for m in rows if m["id"] == memoria_id)
        self.assertEqual(alvo["texto"], "Sono regularizou, media 6.5h.")

    def test_aceitar_remover_apaga_memoria(self):
        memoria_id = db.create_memoria(self.conn, "Fato que deixou de ser verdade.")
        self._guardar_proposta("gasto_recorrente:x", "remover", memoria_id, "Fato que deixou de ser verdade.")
        item = {"origem": "p9_memoria:gasto_recorrente:x"}
        p9_memoria.ao_resolver(self.conn, item, "aceitar")
        self.assertIsNone(
            self.conn.execute("SELECT 1 FROM memorias WHERE id = ?", (memoria_id,)).fetchone()
        )

    def test_recusar_nao_cria_memoria_e_registra_recusa(self):
        self._guardar_proposta("sono_medio", "adicionar", None, "Dorme em media 6.5h por noite.")
        antes = len(db.list_memorias(self.conn, limit=1000))
        item = {"origem": "p9_memoria:sono_medio"}
        p9_memoria.ao_resolver(self.conn, item, "recusar")
        depois = db.list_memorias(self.conn, limit=1000)
        self.assertEqual(len(depois), antes)
        row = self.conn.execute(
            "SELECT * FROM p9_memoria_recusas WHERE chave = ?", ("sono_medio",)
        ).fetchone()
        self.assertIsNotNone(row)

    def test_recusar_e_depois_gerar_de_novo_pula_o_fato(self):
        self._guardar_proposta("treino_horario:1", "adicionar", None, "Treina as 7h.")
        item = {"origem": "p9_memoria:treino_horario:1"}
        p9_memoria.ao_resolver(self.conn, item, "recusar")
        recentes = p9_memoria._recusas_recentes(self.conn, DOMINGO_A_NOITE)
        self.assertIn("treino_horario:1", recentes)

    def test_origem_de_outra_faixa_e_ignorada(self):
        item = {"origem": "p2_conta:123"}
        # nao deve levantar, so nao faz nada (nao e uma proposta desta faixa)
        p9_memoria.ao_resolver(self.conn, item, "aceitar")

    def test_origem_ausente_e_ignorada(self):
        p9_memoria.ao_resolver(self.conn, {}, "aceitar")
        p9_memoria.ao_resolver(self.conn, None, "aceitar")

    def test_resposta_diferente_de_aceitar_ou_recusar_nao_aplica_nem_registra(self):
        self._guardar_proposta("sono_medio", "adicionar", None, "Dorme em media 6.5h por noite.")
        antes = len(db.list_memorias(self.conn, limit=1000))
        item = {"origem": "p9_memoria:sono_medio"}
        p9_memoria.ao_resolver(self.conn, item, "adiar")
        self.assertEqual(len(db.list_memorias(self.conn, limit=1000)), antes)
        self.assertIsNone(
            self.conn.execute("SELECT 1 FROM p9_memoria_recusas WHERE chave = ?", ("sono_medio",)).fetchone()
        )

    def test_aceitar_sem_proposta_guardada_nao_quebra(self):
        item = {"origem": "p9_memoria:chave-que-nao-existe"}
        p9_memoria.ao_resolver(self.conn, item, "aceitar")  # so nao pode levantar

    def test_fuzzing_origem_e_resposta(self):
        entradas = [
            {"origem": ""}, {"origem": None}, {"origem": "p9_memoria:"},
            {"origem": "p9_memoria:" + "x" * 500}, {"origem": 12345}, {},
        ]
        for item in entradas:
            for resposta in ("aceitar", "recusar", "adiar", "", None, "lixo"):
                with self.subTest(item=item, resposta=resposta):
                    p9_memoria.ao_resolver(self.conn, item, resposta)  # so nao pode levantar


if __name__ == "__main__":
    unittest.main()
