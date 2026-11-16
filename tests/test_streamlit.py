import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from assistente import Fonte, Risposta


APP = Path(__file__).resolve().parents[1] / "app_streamlit.py"


class StreamlitTest(unittest.TestCase):
    def test_chat_uses_selected_vehicle_and_preserves_source(self):
        assistente = Mock()
        prima_fonte = Fonte("civic-pressione", 623)
        assistente.rispondi.return_value = Risposta(
            "risposta", "Pressione olio motore bassa\n\nEstratto di prova.\n\nFonte: Honda Civic Type R, p. 623 (PDF p. 624).",
            (prima_fonte,), prima_fonte, ricerca_eseguita=True,
        )
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-chat", "MANUAL_MATE_OSSERVABILITA": "false"}),
            patch("runtime.crea_assistente", return_value=assistente),
        ):
            app = AppTest.from_file(str(APP), default_timeout=10).run()
            self.assertFalse(app.exception)
            self.assertTrue(app.chat_input[0].proto.disabled)

            app.selectbox(key="veicolo").set_value("civic").run()
            app.button(key="civic-pressione").click().run()
            self.assertFalse(app.exception)
            assistente.rispondi.assert_called_once_with("civic", "Pressione olio motore bassa", contesto=())
            self.assertEqual(len(app.chat_message), 2)
            self.assertTrue(any("p. 623" in testo.value for testo in app.caption))

            app.selectbox(key="veicolo").set_value("focus").run()
            self.assertEqual(len(app.chat_message), 0)
            app.selectbox(key="veicolo").set_value("civic").run()
            self.assertEqual(len(app.chat_message), 2)
            app.button(key="azzera-civic").click().run()
            self.assertEqual(len(app.chat_message), 0)
            assistente.rispondi.assert_called_once()

    def test_follow_up_riceve_il_contesto_dello_stesso_veicolo(self):
        assistente = Mock()
        assistente.rispondi.side_effect = [Risposta("chiarimento", "Pressione o livello?"), Risposta("fonte_assente", "Nessuna fonte")]
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-follow-up", "MANUAL_MATE_OSSERVABILITA": "false"}),
            patch("runtime.crea_assistente", return_value=assistente),
        ):
            app = AppTest.from_file(str(APP), default_timeout=10).run()
            app.selectbox(key="veicolo").set_value("civic").run()
            app.chat_input[0].set_value("Spia dell'olio").run()
            app.chat_input[0].set_value("Quella della pressione").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 4)
            assistente.rispondi.assert_called_with("civic", "Quella della pressione", contesto=("Spia dell'olio",))

    def test_missing_key_blocks_questions(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "", "MANUAL_MATE_OSSERVABILITA": "false"}),
            patch("runtime.crea_assistente") as factory,
        ):
            app = AppTest.from_file(str(APP), default_timeout=10).run()
            app.selectbox(key="veicolo").set_value("focus").run()
            self.assertFalse(app.exception)
            self.assertTrue(app.chat_input[0].proto.disabled)
            self.assertTrue(any("OPENAI_API_KEY" in elemento.value for elemento in app.warning))
            factory.assert_not_called()
