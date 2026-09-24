"""Faixa P9 (Fase 7, memoria viva) - deteccao de fatos (code-only) e a
chamada de IA que so redige (ia.core.chamar_ia mockado - nenhuma chamada
real). Relogio sempre injetado (nunca datetime.now() dentro da logica).
Segue o padrao de tests/test_aprendizado.py (db.DB_PATH temporario, sem
importar app.py)."""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db
from assistente import memoria_viva
from ia.contrato import Resposta

AGORA = datetime(2026, 9, 27, 19, 5)  # domingo


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


# ---------------------------------------------------------------------------
# Filtro de assunto proibido
# ---------------------------------------------------------------------------

class ContemAssuntoProibidoTestCase(unittest.TestCase):
    def test_texto_neutro_passa(self):
        self.assertIsNone(memoria_viva.contem_assunto_proibido("Treina toda manha as 7h."))

    def test_vazio_ou_none_passa(self):
        self.assertIsNone(memoria_viva.contem_assunto_proibido(""))
        self.assertIsNone(memoria_viva.contem_assunto_proibido(None))

    def test_pega_namorada(self):
        self.assertEqual(memoria_viva.contem_assunto_proibido("Foi encontrar a namorada"), "vida_amorosa")

    def test_pega_relacionamento_com_acento(self):
        self.assertEqual(
            memoria_viva.contem_assunto_proibido("Conversa sobre o relacionamento deles"), "vida_amorosa"
        )

    def test_pega_variacoes_namoro(self):
        for texto in ("esta namorando", "marcou um date", "pediu em noivado", "fala do crush"):
            with self.subTest(texto=texto):
                self.assertEqual(memoria_viva.contem_assunto_proibido(texto), "vida_amorosa")

    def test_pega_construtora(self):
        self.assertEqual(
            memoria_viva.contem_assunto_proibido("Faturamento da construtora subiu 10%"),
            "financeiro_construtora",
        )

    def test_pega_vgv(self):
        self.assertEqual(memoria_viva.contem_assunto_proibido("VGV do proximo lancamento"), "financeiro_construtora")

    def test_nao_confunde_construtora_com_construir(self):
        # "constroi"/"construir" nao deve disparar o filtro - so "construtora" de fato.
        self.assertIsNone(memoria_viva.contem_assunto_proibido("Ele gosta de construir maquete"))

    def test_fuzzing_nunca_quebra(self):
        entradas = [
            "a" * 5000, "R$ 1.234.567,89 construtora obra", "", None, "   ",
            "namoro" * 50, "😀 texto com emoji e namorada", "\n\t\r",
            "linha\ncom\nquebra namorando", "CONSTRUTORA EM MAIUSCULO",
            "NaMoRaDa mix de caixa", "texto normal sem nada de especial",
        ]
        for entrada in entradas:
            with self.subTest(entrada=entrada):
                memoria_viva.contem_assunto_proibido(entrada)  # so nao pode levantar


# ---------------------------------------------------------------------------
# Deteccao de fatos - treino
# ---------------------------------------------------------------------------

class FatoTreinoHorarioTestCase(_DbTestCase):
    def _criar_habito_treino(self, nome="Treino"):
        return db.create_habito(self.conn, nome, None, "diario", None, None, None)

    def _marcar(self, habito_id, data_str, hora_str):
        self.conn.execute(
            "INSERT INTO habito_marcacoes (data, habito_id, marcado_em) VALUES (?, ?, ?)",
            (data_str, habito_id, f"{data_str} {hora_str}"),
        )
        self.conn.commit()

    def test_sem_habito_de_treino_nao_gera_fato(self):
        db.create_habito(self.conn, "Beber agua", None, "diario", None, None, None)
        self.assertIsNone(memoria_viva._fato_treino_horario(self.conn, AGORA))

    def test_poucas_marcacoes_nao_gera_fato(self):
        habito_id = self._criar_habito_treino()
        for i in range(3):
            dia = (AGORA.date() - timedelta(days=i)).isoformat()
            self._marcar(habito_id, dia, "07:00:00")
        self.assertIsNone(memoria_viva._fato_treino_horario(self.conn, AGORA))

    def test_horario_consistente_gera_fato_com_media_certa(self):
        habito_id = self._criar_habito_treino("Academia")
        horarios = ["07:00:00", "07:05:00", "06:55:00", "07:10:00", "07:00:00", "06:50:00", "07:05:00", "07:00:00"]
        for i, hora in enumerate(horarios):
            dia = (AGORA.date() - timedelta(days=i * 2)).isoformat()
            self._marcar(habito_id, dia, hora)
        fato = memoria_viva._fato_treino_horario(self.conn, AGORA)
        self.assertIsNotNone(fato)
        self.assertEqual(fato["chave"], f"treino_horario:{habito_id}")
        self.assertIn("07:0", fato["contexto_ia"])

    def test_horario_muito_espalhado_nao_gera_fato(self):
        habito_id = self._criar_habito_treino()
        horarios = ["06:00:00", "12:00:00", "20:00:00", "07:00:00", "18:00:00", "09:00:00", "23:00:00", "05:00:00"]
        for i, hora in enumerate(horarios):
            dia = (AGORA.date() - timedelta(days=i * 2)).isoformat()
            self._marcar(habito_id, dia, hora)
        self.assertIsNone(memoria_viva._fato_treino_horario(self.conn, AGORA))

    def test_habito_de_treino_com_nome_amoroso_nunca_gera_fato(self):
        # nome extremo de fuzzing: habito nomeado de um jeito que bate no filtro.
        habito_id = self._criar_habito_treino("Treino - date com a namorada")
        for i in range(8):
            dia = (AGORA.date() - timedelta(days=i)).isoformat()
            self._marcar(habito_id, dia, "07:00:00")
        self.assertIsNone(memoria_viva._fato_treino_horario(self.conn, AGORA))

    def test_marcado_em_corrompido_e_ignorado_sem_quebrar(self):
        habito_id = self._criar_habito_treino()
        for i in range(6):
            dia = (AGORA.date() - timedelta(days=i)).isoformat()
            self._marcar(habito_id, dia, "07:00:00")
        self.conn.execute(
            "INSERT INTO habito_marcacoes (data, habito_id, marcado_em) VALUES (?, ?, ?)",
            ((AGORA.date() - timedelta(days=50)).isoformat(), habito_id, "lixo-sem-formato"),
        )
        self.conn.commit()
        # nao deve levantar excecao por causa da linha corrompida
        memoria_viva._fato_treino_horario(self.conn, AGORA)


# ---------------------------------------------------------------------------
# Deteccao de fatos - sono
# ---------------------------------------------------------------------------

class FatoSonoMedioTestCase(_DbTestCase):
    def _salvar_sono(self, dias_atras, horas):
        dia = (AGORA.date() - timedelta(days=dias_atras)).isoformat()
        db.upsert_saude_dia(self.conn, dia, {"sono_horas": horas})

    def test_poucas_amostras_nao_gera_fato(self):
        for i in range(3):
            self._salvar_sono(i, 7.0)
        self.assertIsNone(memoria_viva._fato_sono_medio(self.conn, AGORA))

    def test_amostras_suficientes_gera_fato(self):
        for i in range(10):
            self._salvar_sono(i, 6.5)
        fato = memoria_viva._fato_sono_medio(self.conn, AGORA)
        self.assertIsNotNone(fato)
        self.assertEqual(fato["chave"], "sono_medio")
        self.assertIn("6.5", fato["contexto_ia"])

    def test_dias_sem_sono_registrado_nao_conta(self):
        for i in range(10):
            dia = (AGORA.date() - timedelta(days=i)).isoformat()
            db.upsert_saude_dia(self.conn, dia, {"passos": 1000})  # sem sono_horas
        self.assertIsNone(memoria_viva._fato_sono_medio(self.conn, AGORA))


# ---------------------------------------------------------------------------
# Deteccao de fatos - gastos recorrentes
# ---------------------------------------------------------------------------

class FatosGastosRecorrentesTestCase(_DbTestCase):
    def _inserir_gasto(self, descricao, valor, categoria, quando: date):
        self.conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo, created_at) "
            "VALUES (?, ?, ?, 'real', ?)",
            (valor, categoria, descricao, quando.isoformat() + " 12:00:00"),
        )
        self.conn.commit()

    def test_assinatura_recorrente_vira_fato(self):
        for meses_atras in (0, 1, 2):
            quando = date(2026, 9, 24) - timedelta(days=30 * meses_atras)
            self._inserir_gasto("Netflix", 39.90, "streaming", quando)
        fatos = memoria_viva._fatos_gastos_recorrentes(self.conn, AGORA)
        self.assertEqual(len(fatos), 1)
        self.assertTrue(fatos[0]["chave"].startswith("gasto_recorrente:"))
        self.assertIn("39.9", fatos[0]["contexto_ia"])

    def test_gasto_avulso_nao_vira_fato(self):
        self._inserir_gasto("Compra unica", 500.0, "outros", date(2026, 9, 20))
        fatos = memoria_viva._fatos_gastos_recorrentes(self.conn, AGORA)
        self.assertEqual(fatos, [])

    def test_gasto_com_descricao_construtora_nunca_vira_fato(self):
        for meses_atras in (0, 1, 2):
            quando = date(2026, 9, 24) - timedelta(days=30 * meses_atras)
            self._inserir_gasto("Material de obra da construtora", 1000.0, "construtora", quando)
        fatos = memoria_viva._fatos_gastos_recorrentes(self.conn, AGORA)
        self.assertEqual(fatos, [])

    def test_respeita_limite(self):
        for n in range(5):
            for meses_atras in (0, 1, 2):
                quando = date(2026, 9, 24) - timedelta(days=30 * meses_atras)
                self._inserir_gasto(f"Assinatura {n}", 20.0 + n, "streaming", quando)
        fatos = memoria_viva._fatos_gastos_recorrentes(self.conn, AGORA, limite=2)
        self.assertEqual(len(fatos), 2)


# ---------------------------------------------------------------------------
# Deteccao de fatos - rotina consistente
# ---------------------------------------------------------------------------

class FatosRotinaConsistenteTestCase(_DbTestCase):
    def _marcar_item_em(self, item_id, dias_atras_lista):
        for dias_atras in dias_atras_lista:
            dia = (AGORA.date() - timedelta(days=dias_atras)).isoformat()
            self.conn.execute("INSERT INTO rotina_marcacoes (data, item_id) VALUES (?, ?)", (dia, item_id))
        self.conn.commit()

    def test_item_cumprido_quase_todo_dia_vira_fato(self):
        item_id = db.create_rotina_item(self.conn, "manha", "Beber agua")
        self._marcar_item_em(item_id, list(range(1, 14)))  # 13 de 14 dias fechados
        fatos = memoria_viva._fatos_rotina_consistente(self.conn, AGORA)
        chaves = [f["chave"] for f in fatos]
        self.assertIn(f"rotina_consistente:manha:{item_id}", chaves)

    def test_item_pouco_cumprido_nao_vira_fato(self):
        item_id = db.create_rotina_item(self.conn, "noite", "Ler um livro")
        self._marcar_item_em(item_id, [1, 3, 5])
        fatos = memoria_viva._fatos_rotina_consistente(self.conn, AGORA)
        chaves = [f["chave"] for f in fatos]
        self.assertNotIn(f"rotina_consistente:noite:{item_id}", chaves)

    def test_item_com_texto_proibido_nunca_vira_fato(self):
        item_id = db.create_rotina_item(self.conn, "noite", "Mandar mensagem pra namorada")
        self._marcar_item_em(item_id, list(range(1, 14)))
        fatos = memoria_viva._fatos_rotina_consistente(self.conn, AGORA)
        chaves = [f["chave"] for f in fatos]
        self.assertNotIn(f"rotina_consistente:noite:{item_id}", chaves)


# ---------------------------------------------------------------------------
# propor_para_fato / gerar_propostas_da_semana - IA sempre mockada
# ---------------------------------------------------------------------------

class ProporParaFatoTestCase(unittest.TestCase):
    def setUp(self):
        self.fato = {
            "chave": "sono_medio",
            "tipo": "sono_medio",
            "contexto_ia": "Nos ultimos 30 dias, media de sono de 6.5h.",
            "categoria_sugerida": "sua_rotina",
        }
        self.memorias = [{"id": 1, "texto": "Sono ainda irregular."}]

    def test_resposta_ok_com_proposta_valida(self):
        resposta = Resposta(ok=True, dados={
            "propostas": [{"acao": "adicionar", "memoria_id": None,
                           "texto": "Dorme em media 6.5h por noite.", "motivo": "padrao dos ultimos 30 dias"}]
        })
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta) as mock_chamar:
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        mock_chamar.assert_called_once()
        self.assertEqual(mock_chamar.call_args.args[0], "propor_memoria")
        self.assertEqual(len(propostas), 1)
        self.assertEqual(propostas[0]["chave"], "sono_medio")
        self.assertEqual(propostas[0]["acao"], "adicionar")
        self.assertIsNone(propostas[0]["memoria_id"])

    def test_falha_de_ia_devolve_lista_vazia_sem_levantar(self):
        resposta = Resposta(ok=False, erro="teto_ia_estourado")
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta):
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        self.assertEqual(propostas, [])

    def test_lista_de_propostas_vazia_e_valida(self):
        resposta = Resposta(ok=True, dados={"propostas": []})
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta):
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        self.assertEqual(propostas, [])

    def test_alterar_com_memoria_id_valido_passa(self):
        resposta = Resposta(ok=True, dados={
            "propostas": [{"acao": "alterar", "memoria_id": 1,
                           "texto": "Sono regularizou, media 6.5h.", "motivo": "atualizado"}]
        })
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta):
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        self.assertEqual(len(propostas), 1)
        self.assertEqual(propostas[0]["memoria_id"], 1)

    def test_alterar_com_memoria_id_inexistente_e_descartada(self):
        resposta = Resposta(ok=True, dados={
            "propostas": [{"acao": "alterar", "memoria_id": 999,
                           "texto": "texto qualquer", "motivo": "motivo qualquer"}]
        })
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta):
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        self.assertEqual(propostas, [])

    def test_acao_invalida_e_descartada(self):
        resposta = Resposta(ok=True, dados={
            "propostas": [{"acao": "apagar_tudo", "memoria_id": None, "texto": "x", "motivo": "y"}]
        })
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta):
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        self.assertEqual(propostas, [])

    def test_proposta_com_texto_amoroso_e_descartada(self):
        resposta = Resposta(ok=True, dados={
            "propostas": [{"acao": "adicionar", "memoria_id": None,
                           "texto": "Costuma sair com a namorada aos sabados.", "motivo": "padrao observado"}]
        })
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta):
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        self.assertEqual(propostas, [])

    def test_proposta_com_valor_da_construtora_e_descartada(self):
        resposta = Resposta(ok=True, dados={
            "propostas": [{"acao": "adicionar", "memoria_id": None,
                           "texto": "Faturamento da construtora foi de R$ 50000 este mes.",
                           "motivo": "achado no dado"}]
        })
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta):
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        self.assertEqual(propostas, [])

    def test_dados_nao_dict_nao_quebra(self):
        resposta = Resposta(ok=True, dados=None, texto="nao era json")
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta):
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        self.assertEqual(propostas, [])

    def test_propostas_nao_e_lista_nao_quebra(self):
        resposta = Resposta(ok=True, dados={"propostas": "nao e uma lista"})
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta):
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        self.assertEqual(propostas, [])

    def test_item_da_lista_nao_dict_e_ignorado(self):
        resposta = Resposta(ok=True, dados={"propostas": ["so uma string", 123, None]})
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta):
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        self.assertEqual(propostas, [])

    def test_memoria_id_booleano_e_descartado(self):
        # bool e subclasse de int em Python - guarda explicita no codigo.
        resposta = Resposta(ok=True, dados={
            "propostas": [{"acao": "alterar", "memoria_id": True, "texto": "x", "motivo": "y"}]
        })
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta):
            propostas = memoria_viva.propor_para_fato(self.fato, self.memorias)
        self.assertEqual(propostas, [])


class GerarPropostasDaSemanaTestCase(_DbTestCase):
    def test_sem_fatos_nao_chama_ia(self):
        with patch("assistente.memoria_viva.ia_core.chamar_ia") as mock_chamar:
            propostas = memoria_viva.gerar_propostas_da_semana(self.conn, AGORA)
        mock_chamar.assert_not_called()
        self.assertEqual(propostas, [])

    def test_fato_recusado_recentemente_e_pulado(self):
        habito_id = db.create_habito(self.conn, "Treino", None, "diario", None, None, None)
        for i in range(8):
            dia = (AGORA.date() - timedelta(days=i)).isoformat()
            self.conn.execute(
                "INSERT INTO habito_marcacoes (data, habito_id, marcado_em) VALUES (?, ?, ?)",
                (dia, habito_id, f"{dia} 07:00:00"),
            )
        self.conn.commit()
        chave = f"treino_horario:{habito_id}"
        with patch("assistente.memoria_viva.ia_core.chamar_ia") as mock_chamar:
            propostas = memoria_viva.gerar_propostas_da_semana(
                self.conn, AGORA, recusas_recentes={chave}
            )
        mock_chamar.assert_not_called()
        self.assertEqual(propostas, [])

    def test_fato_nao_recusado_chama_ia_uma_vez_por_fato(self):
        habito_id = db.create_habito(self.conn, "Treino", None, "diario", None, None, None)
        for i in range(8):
            dia = (AGORA.date() - timedelta(days=i)).isoformat()
            self.conn.execute(
                "INSERT INTO habito_marcacoes (data, habito_id, marcado_em) VALUES (?, ?, ?)",
                (dia, habito_id, f"{dia} 07:00:00"),
            )
        self.conn.commit()
        resposta = Resposta(ok=True, dados={"propostas": []})
        with patch("assistente.memoria_viva.ia_core.chamar_ia", return_value=resposta) as mock_chamar:
            memoria_viva.gerar_propostas_da_semana(self.conn, AGORA)
        self.assertEqual(mock_chamar.call_count, 1)


if __name__ == "__main__":
    unittest.main()
