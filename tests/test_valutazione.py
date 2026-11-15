import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from assistente import Fonte, Risposta
from valutazione import valuta


class ValutazioneTest(unittest.TestCase):
    def test_distingue_ranking_citazione_e_ricerca_saltata(self):
        assistente = Mock()
        assistente.client.model_name = "agente-test"
        assistente.indice.embedder.model_name = "embedding-test"
        attesa = Fonte("civic-pressione", 623)
        altra = Fonte("civic-livello", 629)
        assistente.rispondi.side_effect = [
            Risposta("risposta", "", (altra, attesa), attesa, ricerca_eseguita=True),
            Risposta("chiarimento", ""),
            Risposta("chiarimento", ""),
        ]
        caso_documentale = {
            "veicolo": "civic", "domanda": "Pressione bassa", "esito_atteso": "risposta",
            "fonte_attesa": attesa.id, "pagina_attesa": attesa.pagina,
        }
        casi = [
            {"id": "arriva-seconda", **caso_documentale},
            {"id": "ricerca-saltata", **caso_documentale},
            {"id": "domanda-ambigua", "veicolo": "civic", "domanda": "Spia olio", "esito_atteso": "chiarimento"},
        ]
        with TemporaryDirectory() as cartella:
            domande = Path(cartella) / "queries.json"
            report = Path(cartella) / "report_valutazione.json"
            domande.write_text(json.dumps(casi), encoding="utf-8")
            with redirect_stdout(StringIO()):
                self.assertFalse(valuta(assistente, domande, report))
            dati = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(dati["metriche"]["ricerche_avviate"], {"corretti": 1, "totale": 2})
        self.assertEqual(dati["metriche"]["hit_at_1"], {"corretti": 0, "totale": 1})
        self.assertEqual(dati["metriche"]["citazioni_corrette"], {"corretti": 1, "totale": 2})
        self.assertEqual(dati["metriche"]["casi_passati"], {"corretti": 2, "totale": 3})
        self.assertIsNone(dati["risultati"][1]["hit_at_1"])
