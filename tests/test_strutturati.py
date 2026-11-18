import unittest
from unittest.mock import Mock

from fonti import Riesame
from strutturati import chiedi_strutturato


class StrutturatiTest(unittest.TestCase):
    def test_riprova_json_interrotto_e_limita_i_tentativi(self):
        dati = Riesame(risposte=[], parte_non_documentata="")
        for finale, atteso in ((Mock(structured_data=[dati]), dati), (ValueError("EOF"), None)):
            with self.subTest(atteso=atteso):
                client = Mock()
                client.structured_response.side_effect = [ValueError("EOF nel JSON"), finale]
                risultato = chiedi_strutturato(
                    client, modello=Riesame, input="documenti", prompt="istruzioni", max_tokens=1100,
                )
                self.assertEqual(risultato, atteso)
                self.assertEqual([c.kwargs["max_tokens"] for c in client.structured_response.call_args_list], [1100, 2200])

    def test_riprova_output_assente_senza_ripetere_un_output_valido(self):
        dati = Riesame(risposte=[], parte_non_documentata="")
        client = Mock()
        client.structured_response.side_effect = [Mock(structured_data=[]), Mock(structured_data=[dati])]
        self.assertEqual(chiedi_strutturato(
            client, modello=Riesame, input="documenti", prompt="istruzioni", max_tokens=1100,
        ), dati)
        self.assertEqual(client.structured_response.call_count, 2)
