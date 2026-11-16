import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from datapizza.clients.openai import OpenAIClient
from datapizza.embedders.openai import OpenAIEmbedder
from datapizza.vectorstores.qdrant import QdrantVectorstore

from assistente import Assistente, Fonte
from catalogo import CATALOGO, leggi_passaggi
from corpus import leggi_pagina
from indice import IndiceManuali


class AssistenteTest(unittest.TestCase):
    def setUp(self):
        ambiente = patch.dict(os.environ, {"DATAPIZZA_AGENT_LOG_LEVEL": "WARNING"})
        ambiente.start()
        self.addCleanup(ambiente.stop)
        cartella_default = Path(__file__).resolve().parents[2] / "manuali uso e manutenzione auto"
        self.cartella = Path(os.getenv("MANUALI_DIR") or cartella_default)
        self.chiamate = []
        self.input_embedding = []
        self.azioni = iter(())
        http = httpx.Client(transport=httpx.MockTransport(self.api_simulata))
        self.addCleanup(http.close)
        client = OpenAIClient(api_key="test", http_client=http, max_retries=0)
        self.embedder = OpenAIEmbedder(api_key="test", model_name="text-embedding-3-small")
        self.embedder.client = client.client
        self.indice = IndiceManuali(self.embedder, QdrantVectorstore(location=":memory:"))
        self.assistente = Assistente(self.indice, client)
        # I test usano le sezioni olio reali e un passaggio generale sintetico, così non rielaborano tutti i PDF a ogni run.
        estrazione = patch("indice.estrai_documenti", side_effect=self.documenti_test)
        estrazione.start()
        self.addCleanup(estrazione.stop)

    @staticmethod
    def documenti_test(cartella, veicolo):
        passaggi = leggi_passaggi(cartella, veicolo)
        base = {"veicolo": veicolo.id, "edizione": veicolo.edizione, "source_file": veicolo.file}
        documenti = [(f"{a.titolo}\n\n{passaggi[a.id]}", {
            **base, "fonte": a.id, "pagina": a.pagina, "pagina_pdf": a.pagina_pdf,
            "sezione": a.titolo, "avviso_curato": True,
        }) for a in veicolo.avvisi]
        if veicolo.id == "civic":
            documenti.append(("Telecomando\n\nIl tipo di batteria indicato è CR2032.", {
                **base, "fonte": "civic-pdf576-1", "pagina": 575, "pagina_pdf": 576, "sezione": "Telecomando",
            }))
        return documenti, 3, []

    def api_simulata(self, request):
        self.chiamate.append(request.url.path)
        body = json.loads(request.content)
        if request.url.path.endswith("/embeddings"):
            self.input_embedding.append(body["input"])
            embeddings = []
            for i, testo in enumerate(body["input"]):
                titolo = testo.splitlines()[0].casefold()
                vettore = [1.0, 0.0] if "pressione" in titolo else [0.0, 1.0]
                embeddings.append({"object": "embedding", "index": i, "embedding": vettore})
            return httpx.Response(200, json={"object": "list", "data": embeddings, "model": body["model"]})

        nome, argomenti = next(self.azioni)
        chiamata = f"call_{len(self.chiamate)}"
        return httpx.Response(200, json={
            "id": "resp_test", "object": "response", "created_at": 0, "model": body["model"],
            "status": "completed", "output": [{
                "type": "function_call", "id": chiamata, "call_id": chiamata, "name": nome,
                "arguments": json.dumps(argomenti), "status": "completed",
            }],
        })

    def test_recupera_le_tre_pagine(self):
        for veicolo in CATALOGO.values():
            self.indice.indicizza(self.cartella, veicolo)
        for veicolo, domanda, fonte, pagina in (
            ("focus", "Mi si è accesa la spia dell’olio", "focus-olio", 80),
            ("civic", "Pressione olio motore bassa", "civic-pressione", 623),
            ("civic", "Livello olio motore basso", "civic-livello", 629),
            ("civic", "Il display dice che la pressione dell’olio è troppo bassa", "civic-pressione", 623),
            ("civic", "Il livello dell’olio è troppo basso", "civic-livello", 629),
        ):
            with self.subTest(fonte=fonte):
                self.azioni = iter((("cerca_manuale", {"query": domanda}), ("cita_fonte", {"fonte_id": fonte})))
                risposta = self.assistente.rispondi(veicolo, domanda)
                self.assertEqual(risposta.esito, "risposta")
                self.assertIn(f"p. {pagina} (PDF", risposta.testo)
                self.assertEqual(risposta.fonte_citata, Fonte(fonte, pagina))
                self.assertTrue(risposta.ricerca_eseguita)
                self.assertIn(risposta.fonte_citata, risposta.fonti_recuperate)

    def test_chiede_chiarimento_senza_ricerca(self):
        self.azioni = iter((("chiedi_chiarimento", {}),))
        risposta = self.assistente.rispondi("civic", "Spia dell'olio")
        self.assertEqual(risposta.esito, "chiarimento")
        self.assertEqual(self.chiamate, ["/v1/responses"])

    def test_chiarimento_risolto_con_una_risposta_breve(self):
        self.indice.indicizza(self.cartella, CATALOGO["civic"])
        prima_domanda = "Mi si è accesa la spia dell’olio"
        self.azioni = iter((("chiedi_chiarimento", {}),))
        prima = self.assistente.rispondi("civic", prima_domanda)
        self.assertIn("pressione", prima.testo)
        self.assertIn("livello", prima.testo)
        self.assertFalse(prima.ricerca_eseguita)

        self.azioni = iter((("cerca_manuale", {"query": "pressione"}), ("cita_fonte", {"fonte_id": "civic-pressione"})))
        seconda = self.assistente.rispondi("civic", "Quella della pressione", contesto=(prima_domanda,))
        self.assertEqual(seconda.fonte_citata, Fonte("civic-pressione", 623))

    def test_comunica_limite_del_libretto_per_problema_non_coperto(self):
        self.azioni = iter((("segnala_limite", {}),))
        risposta = self.assistente.rispondi("civic", "Qual è la ricetta della carbonara?")
        self.assertEqual(risposta.esito, "fonte_assente")
        self.assertIn("Non ho trovato indicazioni pertinenti", risposta.testo)
        self.assertIsNone(risposta.fonte_citata)
        self.assertEqual(self.chiamate, ["/v1/responses"])

    def test_domanda_libera_richiede_un_estratto_letterale(self):
        self.indice.indicizza(self.cartella, CATALOGO["civic"])
        domanda = "Che batteria usa la chiave?"
        for citazione, esito in (
            ("Il tipo di batteria indicato è CR2032.", "risposta"),
            ("Il tipo di batteria indicato è CR2025.", "fonte_assente"),
        ):
            with self.subTest(citazione=citazione):
                self.azioni = iter((("cerca_manuale", {"query": domanda}), ("cita_fonte", {
                    "fonte_id": "civic-pdf576-1", "citazione": citazione,
                })))
                risposta = self.assistente.rispondi("civic", domanda)
                self.assertEqual(risposta.esito, esito)
                self.assertTrue(risposta.ricerca_eseguita)

    def test_conserva_numerazione_stampata_e_sezione(self):
        civic = "575SEGUE\nManutenzione\nTipo di batteria: CR2032\n23 CIVIC TYPE R JSS (KE KG)-3LT406000.book Page 575 Wednesday"
        pagina, sezione, righe = leggi_pagina(civic, CATALOGO["civic"])
        self.assertEqual((pagina, sezione, righe[-1]), (575, "Manutenzione", "Tipo di batteria: CR2032"))

    def test_ubicazione_fusibili_usa_la_sezione_verificata(self):
        focus = CATALOGO["focus"]
        base = {"veicolo": focus.id, "edizione": focus.edizione, "source_file": focus.file,
                "sezione": "Fusibili", "avviso_curato": False}
        documenti = [
            ("Fusibili\n\nUbicazione scatola portafusibili\nScatola dei fusibili nel vano motore", {
                **base, "fonte": "focus-pdf207-1", "pagina": 205, "pagina_pdf": 207,
            }),
            ("Fusibili\n\nTabella fusibili e valori nominali", {
                **base, "fonte": "focus-pdf208-1", "pagina": 206, "pagina_pdf": 208,
            }),
        ]
        with patch("indice.estrai_documenti", return_value=(documenti, 2, [])):
            self.indice.indicizza(self.cartella, focus)
        self.azioni = iter((("cerca_manuale", {"query": "scatola dei fusibili"}), ("segnala_limite", {})))
        risposta = self.assistente.rispondi("focus", "Dove si trova la scatola dei fusibili?")
        self.assertEqual(risposta.fonte_citata, Fonte("focus-pdf207-1", 205))

    def test_civic_distingue_le_due_scatole_dei_fusibili(self):
        domanda = "Dove si trova la scatola dei fusibili nella Civic Type R?"
        chiarimento = self.assistente.rispondi("civic", domanda)
        self.assertEqual(chiarimento.esito, "chiarimento")
        self.assertIn("vano motore o quella nell’abitacolo", chiarimento.testo)
        self.assertEqual(self.chiamate, [])

        civic = CATALOGO["civic"]
        documenti = [("Fusibili\n\nScatola fusibili interna\nTesto della sezione.", {
            "veicolo": civic.id, "edizione": civic.edizione, "source_file": civic.file,
            "sezione": "Fusibili", "avviso_curato": False, "fonte": "civic-pdf633-1", "pagina": 632, "pagina_pdf": 633,
        })]
        with patch("indice.estrai_documenti", return_value=(documenti, 1, [])):
            self.indice.indicizza(self.cartella, civic)
        self.azioni = iter((("cerca_manuale", {"query": "fusibili abitacolo"}), ("segnala_limite", {})))
        risposta = self.assistente.rispondi("civic", "Quella nell’abitacolo", contesto=(domanda,))
        self.assertEqual(risposta.fonte_citata, Fonte("civic-pdf633-1", 632))

    def test_completa_la_pagina_senza_ripetere_overlap(self):
        civic = CATALOGO["civic"]
        documenti, pagine, senza_testo = self.documenti_test(self.cartella, civic)
        _, metadati = documenti[-1]
        condivisa = "Procedure ordinarie sul telecomando"
        base = {**metadati, "avviso_curato": False}
        documenti[-1] = (f"Telecomando\n\n{condivisa}", base)
        documenti.append((f"Telecomando\n\n{condivisa}\nTipo di batteria: CR2032", {**base, "fonte": "civic-pdf576-2"}))
        with patch("indice.estrai_documenti", return_value=(documenti, pagine, senza_testo)):
            self.indice.indicizza(self.cartella, civic)
        collezione = self.indice.collezione_attiva(civic)
        risultati = self.indice.cerca(civic, collezione, "Che batteria usa il telecomando?")
        prima = next(hit for hit in risultati if hit.metadata["fonte"] == base["fonte"])
        completa = self.indice.completa_pagina(collezione, prima)
        self.assertEqual(completa.id, prima.id)
        self.assertEqual(completa.text.count(condivisa), 1)
        self.assertIn("Tipo di batteria: CR2032", completa.text)

    def test_veicolo_fuori_catalogo_senza_chiamate(self):
        risposta = self.assistente.rispondi("jazz", "Spia dell'olio")
        self.assertEqual(risposta.esito, "bloccato")
        self.assertEqual(self.chiamate, [])

    def test_rifiuta_fonte_di_altro_veicolo(self):
        self.indice.indicizza(self.cartella, CATALOGO["civic"])
        self.azioni = iter((("cerca_manuale", {"query": "pressione"}), ("cita_fonte", {"fonte_id": "focus-olio"})))
        risposta = self.assistente.rispondi("civic", "Pressione olio motore bassa")
        self.assertEqual(risposta.esito, "fonte_assente")
        self.assertNotIn("Ford", risposta.testo)

    def test_indice_assente_non_avvia_ingestione(self):
        risposta = self.assistente.rispondi("civic", "Pressione olio motore bassa")
        self.assertEqual(risposta.esito, "indice_assente")
        self.assertEqual(self.chiamate, [])

    def test_riusa_indice_persistente_e_invia_solo_query(self):
        civic = CATALOGO["civic"]
        query = "Pressione olio motore bassa"
        with TemporaryDirectory() as volume:
            primo_store = QdrantVectorstore(location=None, path=volume)
            primo_indice = IndiceManuali(self.embedder, primo_store)
            try:
                self.assertEqual(primo_indice.indicizza(self.cartella, civic), 3)
                collezione = primo_indice.collezione_attiva(civic)
                self.assertIsNotNone(collezione)
            finally:
                primo_store.get_client().close()

            self.input_embedding.clear()
            secondo_store = QdrantVectorstore(location=None, path=volume)
            secondo_indice = IndiceManuali(self.embedder, secondo_store)
            try:
                self.assertEqual(secondo_indice.indicizza(self.cartella, civic), 0)
                self.assertEqual(secondo_indice.collezione_attiva(civic), collezione)
                self.assertEqual(self.input_embedding, [])
                risultati = secondo_indice.cerca(civic, collezione, query, solo_avvisi=True)
                self.assertEqual(risultati[0].metadata["pagina"], 623)
                self.assertEqual(self.input_embedding, [[query]])
            finally:
                secondo_store.get_client().close()

    def test_nuova_versione_diventa_attiva_dopo_ingestione(self):
        focus = CATALOGO["focus"]
        primo, _, _ = self.documenti_test(self.cartella, focus)
        aggiornati = [("Versione aggiornata", primo[0][1])]
        with patch("indice.estrai_documenti", return_value=(primo, 1, [])):
            self.indice.indicizza(self.cartella, focus)
        precedente = self.indice.collezione_attiva(focus)
        with patch("indice.estrai_documenti", return_value=(aggiornati, 1, [])):
            self.indice.indicizza(self.cartella, focus)
        attiva = self.indice.collezione_attiva(focus)
        self.assertNotEqual(attiva, precedente)
        risultati = self.indice.cerca(focus, attiva, "Spia olio motore")
        self.assertIn("Versione aggiornata", risultati[0].text)


if __name__ == "__main__":
    unittest.main()
