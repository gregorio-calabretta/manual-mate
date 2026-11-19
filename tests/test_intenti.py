import json
import unittest
from unittest.mock import Mock, patch

from assistente import Assistente
from catalogo import CATALOGO
from conversazione import Conversazione
from fonti import Risposta
from intenti import DomandaTrasferita, contesto_cambio_auto, leggi_cambio_auto, trasferisci_domanda


class IntentiTest(unittest.TestCase):
    def test_cambio_modello_riprende_solo_le_domande_e_memorizza_la_nuova(self):
        consulta = Mock(side_effect=[
            Risposta("risposta", "Intervalli della Leon"),
            Risposta("risposta", "Spiegazione dei codici"),
            Risposta("fonte_assente", "Dato non trovato", domanda_interpretata="Ogni quanto cambiare l'olio motore?"),
            Risposta("risposta", "Indicatore Audi", domanda_interpretata="Ogni quanto cambiare l'olio motore?"),
        ])
        chat = Conversazione()
        prima = "Ogni quanto cambiare l'olio della Seat Leon?"
        chat.rispondi(prima, consulta)
        chat.rispondi("QI1 e QI2 cosa sono?", consulta)
        chat.rispondi("invece nella Ford Focus?", consulta)
        chiamata = consulta.call_args
        self.assertEqual(chiamata.args[:2], ("focus", "invece nella Ford Focus?"))
        cambio = leggi_cambio_auto(chiamata.args[2])
        self.assertEqual(cambio.veicolo_precedente, "leon")
        self.assertEqual(cambio.domande, [prima, "QI1 e QI2 cosa sono?"])
        chat.rispondi("e nell'Audi A3?", consulta)
        nuovo = leggi_cambio_auto(consulta.call_args.args[2])
        self.assertEqual(nuovo.veicolo_precedente, "focus")
        self.assertEqual(nuovo.domande, ["Ogni quanto cambiare l'olio motore?"])

    def test_nuova_domanda_e_selezione_senza_richiamo_non_trasferiscono_il_tema(self):
        for messaggio in ("Ford Focus", "Dove sono i fusibili della Ford Focus?", "Altra domanda: e nella Ford Focus?"):
            with self.subTest(messaggio=messaggio):
                consulta = Mock(return_value=Risposta("risposta", "Documento"))
                chat = Conversazione()
                chat.rispondi("Ogni quanto cambiare l'olio della Seat Leon?", consulta)
                risposta = chat.rispondi(messaggio, consulta)
                if risposta.esito == "veicolo_selezionato":
                    self.assertEqual(consulta.call_count, 1)
                else:
                    self.assertEqual(consulta.call_args.args[2], ())

    def test_la_consultazione_nuova_non_riceve_dettagli_o_fonti_del_vecchio_veicolo(self):
        client = Mock()
        client.structured_response.return_value = Mock(structured_data=[DomandaTrasferita(
            domanda_generale="Qual è la velocità massima?",
        )])
        assistente = Assistente(Mock(), client)
        vecchio = ("Velocità massima della Leon 2.0 TSI DSG?", "benzina")
        contesto = (contesto_cambio_auto("leon", vecchio),)
        with patch.object(assistente, "_consulta", return_value=Risposta("chiarimento", "Quale motore?")) as consulta:
            risposta = assistente.rispondi("focus", "e nella Ford Focus?", contesto=contesto)
        consulta.assert_called_once_with(CATALOGO["focus"], "Qual è la velocità massima?", ())
        self.assertEqual(risposta.domanda_interpretata, "Qual è la velocità massima?")
        dati = json.loads(client.structured_response.call_args.kwargs["input"])
        self.assertEqual(dati["nuova_auto"], "Ford Focus (CEW)")

    def test_ricostruzione_vuota_o_con_altro_modello_viene_rifiutata(self):
        cambio = leggi_cambio_auto((contesto_cambio_auto("leon", ("Dove sono i fusibili?",)),))
        for domanda in ("", "Dove sono i fusibili della Seat Leon?"):
            with self.subTest(domanda=domanda):
                client = Mock()
                client.structured_response.return_value = Mock(structured_data=[DomandaTrasferita(domanda_generale=domanda)])
                self.assertIsNone(trasferisci_domanda(client, cambio, CATALOGO["focus"], "e nella Focus?"))
        self.assertIsNone(leggi_cambio_auto(("Messaggio ordinario",)))
