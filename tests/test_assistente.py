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
        for codice in ("focus", "civic"):
            self.indice.indicizza(self.cartella, CATALOGO[codice])
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
        self.assertIn("Non ho trovato nel libretto", risposta.testo)
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
                    "sintesi": "Per il telecomando ti serve una pila CR2032.",
                })))
                risposta = self.assistente.rispondi("civic", domanda)
                self.assertEqual(risposta.esito, esito)
                self.assertTrue(risposta.ricerca_eseguita)
                if esito == "risposta":
                    self.assertIn("Per il telecomando ti serve", risposta.testo_cli)
                    self.assertIn("p. 575", risposta.testo_cli)
                    self.assertIn(citazione, risposta.testo)
                else:
                    self.assertIsNone(risposta.sintesi)

    def test_conserva_numerazione_stampata_e_sezione(self):
        civic = "575SEGUE\nManutenzione\nTipo di batteria: CR2032\n23 CIVIC TYPE R JSS (KE KG)-3LT406000.book Page 575 Wednesday"
        pagina, sezione, righe = leggi_pagina(civic, CATALOGO["civic"])
        self.assertEqual((pagina, sezione, righe[-1]), (575, "Manutenzione", "Tipo di batteria: CR2032"))

    def test_domanda_composta_verifica_entrambi_i_passaggi(self):
        focus = CATALOGO["focus"]
        estratti = ("Il telecomando usa una pila a bottone CR2032.",
                    "Montare una nuova pila con il simbolo + rivolto verso l'alto.")
        documenti = [(f"Chiavi e telecomandi\n\n{estratto}", {
            "veicolo": focus.id, "edizione": focus.edizione, "source_file": focus.file,
            "fonte": f"focus-pdf{pdf}-1", "pagina": pdf - 2, "pagina_pdf": pdf,
            "sezione": "Chiavi e telecomandi", "avviso_curato": False,
        }) for pdf, estratto in zip((36, 37), estratti)]
        with patch("indice.estrai_documenti", return_value=(documenti, 2, [])):
            self.indice.indicizza(self.cartella, focus)

        for fonti_id, esito in ((["focus-pdf36-1", "focus-pdf37-1"], "risposta"),
                               (["focus-pdf36-1", "civic-pdf576-1"], "fonte_assente")):
            with self.subTest(esito=esito):
                self.azioni = iter((("cerca_manuale", {"query": "pila telecomando", "query_complementare": "orientamento polo"}),
                                    ("cita_fonti", {"fonti_id": fonti_id, "citazioni": list(estratti),
                                                   "frasi": ["Serve una CR2032.", "Metti il positivo verso l'alto."]})))
                risposta = self.assistente.rispondi("focus", "Che pila serve e come la monto?")
                self.assertEqual(risposta.esito, esito)
                self.assertEqual(self.input_embedding[-2:], [["pila telecomando"], ["orientamento polo"]])
                if esito == "risposta":
                    self.assertEqual([fonte.pagina for fonte in risposta.fonti_citate], [34, 35])
                    self.assertIn("Serve una CR2032. (p. 34", risposta.testo_cli)
                    self.assertIn("Metti il positivo verso l'alto. (p. 35", risposta.testo_cli)
                else:
                    self.assertEqual(risposta.fonti_citate, ())

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

    def test_audi_riassume_le_due_posizioni_dei_fusibili_in_italiano(self):
        audi = CATALOGO["audi"]
        originale = (
            "Fuses and bulbs\n\nThe fuses are located behind a cover in the steer-\n"
            "ing column area or under a cover on\nthe left side of the engine compartment."
        )
        documenti = [(originale, {
            "veicolo": audi.id, "edizione": audi.edizione, "source_file": audi.file,
            "sezione": "Fuses and bulbs", "avviso_curato": False,
            "fonte": "audi-pdf381-1", "pagina": 379, "pagina_pdf": 381,
        })]
        with patch("indice.estrai_documenti", return_value=(documenti, 1, [])):
            self.indice.indicizza(self.cartella, audi)
        self.azioni = iter((("cerca_manuale", {"query": "location of fuses"}), ("segnala_limite", {})))
        risposta = self.assistente.rispondi("audi", "Dove si trova la scatola dei fusibili?")
        self.assertEqual(risposta.fonte_citata, Fonte("audi-pdf381-1", 379, 381))
        self.assertIn("piantone dello sterzo", risposta.testo_cli)
        self.assertIn("vano motore, sotto un coperchio sul lato sinistro", risposta.testo_cli)
        self.assertIn("p. 379 (PDF p. 381)", risposta.testo_cli)
        self.assertNotIn("Fuses and bulbs", risposta.testo_cli)
        self.assertIn(originale, risposta.testo)

    def test_audi_legge_la_pagina_stampata_tra_le_colonne(self):
        testo = "Fuses and bulbs\nEngine compartment\n379\nAudi recommends using original fuses."
        pagina, sezione, righe = leggi_pagina(testo, CATALOGO["audi"], 381)
        self.assertEqual(pagina, 379)
        self.assertEqual(sezione, "Fuses and bulbs")
        self.assertEqual(righe, ["Engine compartment", "Audi recommends using original fuses."])
        self.assertIsNone(leggi_pagina(testo, CATALOGO["audi"], 382)[0])

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
