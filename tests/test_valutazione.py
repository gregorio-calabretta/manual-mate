import json
import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, call

from pydantic import TypeAdapter
from pypdf import PdfReader

from assistente import Fonte, Risposta
from catalogo import CATALOGO
from corpus import leggi_pagina
from valutazione import Caso, Giudizio, corrisponde, esegui_caso, evidenze_mancanti, valuta


class ValutazioneTest(unittest.TestCase):
    def test_distingue_ranking_citazione_e_ricerca_saltata(self):
        assistente = Mock()
        assistente.client.model_name = "agente-test"
        assistente.indice.embedder.model_name = "embedding-test"
        assistente.indice.top_k = 5
        attesa = Fonte("civic-pressione", 623)
        altra = Fonte("civic-livello", 629)
        assistente.rispondi.side_effect = [
            Risposta("risposta", "Pressione\nolio insufficiente", (altra, attesa), attesa, ricerca_eseguita=True),
            Risposta("risposta", "Estratto senza il dato.\n\nFonte: Pressione olio", (attesa,), attesa, ricerca_eseguita=True),
            Risposta("chiarimento", ""),
            Risposta("chiarimento", ""),
        ]
        caso_documentale = {
            "veicolo": "civic", "domanda": "Pressione bassa", "esito_atteso": "risposta",
            "fonte_attesa": attesa.id, "pagina_attesa": attesa.pagina,
            "evidenze_attese": ["pressione olio"],
        }
        casi = [
            {"id": "arriva-seconda", **caso_documentale},
            {"id": "pagina-giusta-estratto-sbagliato", **caso_documentale},
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

        self.assertEqual(dati["metriche"]["ricerche_avviate"], {"corretti": 2, "totale": 3})
        self.assertEqual(dati["metriche"]["hit_at_1"], {"corretti": 1, "totale": 2})
        self.assertEqual(dati["metriche"]["citazioni_corrette"], {"corretti": 2, "totale": 3})
        self.assertEqual(dati["metriche"]["estratti_con_evidenze"], {"corretti": 1, "totale": 3})
        self.assertEqual(dati["metriche"]["casi_passati"], {"corretti": 2, "totale": 4})
        self.assertEqual(dati["risultati"][1]["evidenze_mancanti"], ["pressione olio"])
        self.assertIsNone(dati["risultati"][2]["hit_at_1"])

    def test_accetta_una_seconda_pagina_verificata(self):
        caso = Caso(id="velocita", veicolo="audi", domanda="A quale velocità?",
                    esito_atteso="risposta", pagina_attesa=34, pagine_alternative=(30,))
        self.assertTrue(corrisponde(Fonte("audi-pdf32-1", 30), caso))
        self.assertFalse(corrisponde(Fonte("audi-pdf33-1", 31), caso))

    def test_il_giudice_valuta_la_risposta_visibile_e_registra_le_varianti(self):
        assistente = Mock()
        assistente.client.model_name = "modello-di-prova"
        assistente.indice.embedder.model_name = "embedding-di-prova"
        assistente.indice.top_k = 5
        fonte = Fonte("focus-pdf36-1", 34, 36)
        estratto = "Pile\n\nBatteria al litio da tre volt CR2032."
        base = f"{estratto}\n\nFonte: Focus, p. 34 (PDF p. 36)."
        assistente.rispondi.side_effect = [
            Risposta("risposta", base, (fonte,), fonte, True, sintesi="Per il telecomando serve una pila CR2032."),
            Risposta("risposta", base, (fonte,), fonte, True, sintesi="Il telecomando usa una pila."),
        ]
        assistente.client.structured_response.side_effect = [
            Mock(structured_data=[Giudizio(coerente=True, motivo="Indica il codice corretto.")]),
            Mock(structured_data=[Giudizio(coerente=False, motivo="Nella risposta manca il codice.")]),
        ]
        caso = {"veicolo": "focus", "esito_atteso": "risposta", "pagina_attesa": 34, "evidenze_attese": ["CR2032"],
                "criterio_risposta": "Indicare CR2032.", "gruppo": "telecomando"}
        casi = [{**caso, "id": "batteria", "domanda": "Che batteria usa il telecomando?",
                 "varianti": ["Che pila serve per il telecomando?"]}]
        with TemporaryDirectory() as cartella:
            domande = Path(cartella) / "queries.json"
            report = Path(cartella) / "report.json"
            domande.write_text(json.dumps(casi), encoding="utf-8")
            with redirect_stdout(StringIO()):
                self.assertFalse(valuta(assistente, domande, report))
            dati = json.loads(report.read_text(encoding="utf-8"))

        giudice_input = json.loads(assistente.client.structured_response.call_args.kwargs["input"])
        self.assertEqual(giudice_input["risposta_visibile"], "Il telecomando usa una pila.")
        self.assertEqual(giudice_input["estratto_del_libretto"], estratto)
        self.assertEqual(dati["gruppi"]["telecomando"], {"corretti": 1, "totale": 2})
        risultato = dati["risultati"][1]
        self.assertEqual(risultato["id"], "batteria-v1")
        self.assertEqual(risultato["criterio_risposta"], caso["criterio_risposta"])
        self.assertTrue(risultato["citazione_corretta"])
        self.assertEqual(risultato["evidenze_mancanti"], [])
        self.assertFalse(risultato["risposta_coerente"])
        self.assertFalse(risultato["passato"])

    def test_il_benchmark_riprende_la_domanda_dopo_la_scelta_del_veicolo(self):
        caso = Caso.model_validate({
            "id": "fusibili", "veicolo": "audi", "domanda": "Audi A3 8V", "esito_atteso": "risposta",
            "pagina_attesa": 379, "turni": ({"messaggio": "Dove sono i fusibili?", "esito_atteso": "veicolo_da_chiarire"},),
        })
        assistente = Mock()
        assistente.rispondi.return_value = Risposta("risposta", "Posizioni documentate")
        risposta, veicolo, turni = esegui_caso(assistente, caso)
        self.assertEqual(veicolo, "audi")
        self.assertEqual(risposta.esito, "risposta")
        self.assertEqual(assistente.rispondi.call_args_list, [call("audi", "Dove sono i fusibili?", contesto=())])
        self.assertTrue(turni[0]["passato"])

    def test_le_evidenze_del_benchmark_sono_nelle_pagine_dei_tre_pdf(self):
        progetto = Path(__file__).resolve().parents[1]
        cartella = Path(os.getenv("MANUALI_DIR") or (progetto.parent / "manuali uso e manutenzione auto"))
        casi = TypeAdapter(list[Caso]).validate_json((progetto / "queries.json").read_text(encoding="utf-8"))
        scarti_pdf = {"focus": 2, "civic": 1, "audi": 2}
        for codice, veicolo in CATALOGO.items():
            casi_con_evidenze = [caso for caso in casi if caso.veicolo == codice and caso.evidenze_attese]
            self.assertTrue(casi_con_evidenze, codice)
            with (cartella / veicolo.file).open("rb") as file:
                pdf = PdfReader(file)
                for caso in casi_con_evidenze:
                    for pagina in (caso.pagina_attesa, *caso.pagine_alternative):
                        with self.subTest(caso=caso.id, pagina=pagina):
                            posizione = pagina + scarti_pdf[codice]
                            testo = pdf.pages[posizione - 1].extract_text() or ""
                            numero, sezione, corpo = leggi_pagina(testo, veicolo, posizione)
                            self.assertEqual(numero, pagina)
                            self.assertEqual(evidenze_mancanti("\n".join([sezione, *corpo]), caso), [])
