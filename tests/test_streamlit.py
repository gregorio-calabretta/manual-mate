import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from assistente import Fonte, Risposta


APP = Path(__file__).resolve().parents[1] / "app_streamlit.py"


class StreamlitTest(unittest.TestCase):
    def test_presentazione_e_ringraziamento_non_interrompono_la_conversazione(self):
        assistente = Mock()
        fonte = Fonte("audi-pdf381-1", 379, 381)
        assistente.rispondi.return_value = Risposta(
            "risposta", "Fuses\n\nOriginal excerpt.\n\nFonte: Audi A3 8V, p. 379 (PDF p. 381).",
            fonte_citata=fonte, sintesi="I fusibili sono dietro un coperchio.",
        )
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-presentazione", "MANUAL_MATE_OSSERVABILITA": "false"}),
            patch("runtime.crea_assistente", return_value=assistente),
        ):
            app = AppTest.from_file(str(APP), default_timeout=10).run()
            app.chat_input[0].set_value("Ciao, cosa sai fare?").run()
            self.assertTrue(any("Posso aiutarti" in elemento.value for elemento in app.markdown))
            self.assertFalse(any("Di quale auto" in elemento.value for elemento in app.markdown))

            domanda = "Dove si trovano i fusibili?"
            app.chat_input[0].set_value(domanda).run()
            app.chat_input[0].set_value("Grazie mille!").run()
            assistente.rispondi.assert_not_called()

            app.chat_input[0].set_value("Audi A3 8V").run()
            assistente.rispondi.assert_called_once_with("audi", domanda, contesto=())
            self.assertTrue(any("i fusibili sono" in elemento.value.lower() for elemento in app.text))
            self.assertTrue(any(elemento.label == "Estratto originale del manuale" for elemento in app.expander))

            seguito = "E nel vano motore?"
            app.chat_input[0].set_value(seguito).run()
            assistente.rispondi.assert_called_with("audi", seguito, contesto=(domanda,))
            self.assertFalse(app.exception)

    def test_chiede_auto_e_riprende_la_domanda_originale(self):
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
            self.assertFalse(app.chat_input[0].proto.disabled)

            domanda = "Pressione olio motore bassa"
            app.chat_input[0].set_value(domanda).run()
            self.assertEqual(len(app.chat_message), 2)
            self.assertTrue(app.button(key="azzera-conversazione").label)
            self.assertTrue(any("Di quale auto" in elemento.value for elemento in app.markdown))
            assistente.rispondi.assert_not_called()

            app.chat_input[0].set_value("Honda Civic Type R").run()
            self.assertFalse(app.exception)
            assistente.rispondi.assert_called_once_with("civic", domanda, contesto=())
            self.assertEqual(len(app.chat_message), 4)
            self.assertTrue(any("p. 623" in testo.value for testo in app.caption))

            app.button(key="azzera-conversazione").click().run()
            self.assertEqual(len(app.chat_message), 0)
            assistente.rispondi.assert_called_once()

    def test_audi_nella_domanda_o_dopo_il_chiarimento(self):
        assistente = Mock()
        assistente.rispondi.return_value = Risposta("fonte_assente", "Nessuna fonte")
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-audi", "MANUAL_MATE_OSSERVABILITA": "false"}),
            patch("runtime.crea_assistente", return_value=assistente),
        ):
            app = AppTest.from_file(str(APP), default_timeout=10).run()
            domanda = "Dove si trova la scatola dei fusibili?"
            app.chat_input[0].set_value(domanda).run()
            app.chat_input[0].set_value("Audi A3 8Y").run()
            self.assertTrue(any("Il libretto disponibile è per Audi A3 8V" in elemento.value for elemento in app.markdown))
            assistente.rispondi.assert_not_called()
            app.chat_input[0].set_value("Audi A3 8V").run()
            assistente.rispondi.assert_called_once_with("audi", domanda, contesto=())

            app.button(key="azzera-conversazione").click().run()
            diretta = "Dove si trova la scatola dei fusibili dell'Audi A3 8V?"
            app.chat_input[0].set_value(diretta).run()
            assistente.rispondi.assert_called_with("audi", diretta, contesto=())
            self.assertEqual(assistente.rispondi.call_count, 2)
            self.assertFalse(app.exception)

    def test_follow_up_riceve_il_contesto_dello_stesso_veicolo(self):
        assistente = Mock()
        assistente.rispondi.side_effect = [Risposta("chiarimento", "Pressione o livello?"), Risposta("fonte_assente", "Nessuna fonte")]
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-follow-up", "MANUAL_MATE_OSSERVABILITA": "false"}),
            patch("runtime.crea_assistente", return_value=assistente),
        ):
            app = AppTest.from_file(str(APP), default_timeout=10).run()
            app.chat_input[0].set_value("Spia dell'olio sulla Honda Civic Type R").run()
            app.chat_input[0].set_value("Quella della pressione").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 4)
            assistente.rispondi.assert_called_with(
                "civic", "Quella della pressione", contesto=("Spia dell'olio sulla Honda Civic Type R",),
            )

    def test_cambio_auto_non_riusa_chiarimenti_del_manuale_precedente(self):
        assistente = Mock()
        assistente.rispondi.return_value = Risposta("chiarimento", "Quale avviso?")
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-cambio", "MANUAL_MATE_OSSERVABILITA": "false"}),
            patch("runtime.crea_assistente", return_value=assistente),
        ):
            app = AppTest.from_file(str(APP), default_timeout=10).run()
            app.chat_input[0].set_value("Ho una spia sulla Honda Civic Type R").run()
            app.chat_input[0].set_value("Dove sono i fusibili della Ford Focus?").run()
            self.assertFalse(app.exception)
            assistente.rispondi.assert_called_with("focus", "Dove sono i fusibili della Ford Focus?", contesto=())
            app.chat_input[0].set_value("Ford Focus del 2022").run()
            self.assertFalse(app.exception)
            self.assertEqual(assistente.rispondi.call_count, 2)
            self.assertTrue(any("ed. 09/2014" in elemento.value for elemento in app.markdown))

    def test_missing_key_blocks_questions(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "", "MANUAL_MATE_OSSERVABILITA": "false"}),
            patch("runtime.crea_assistente") as factory,
        ):
            app = AppTest.from_file(str(APP), default_timeout=10).run()
            self.assertFalse(app.exception)
            self.assertTrue(app.chat_input[0].proto.disabled)
            self.assertTrue(any("OPENAI_API_KEY" in elemento.value for elemento in app.warning))
            factory.assert_not_called()
