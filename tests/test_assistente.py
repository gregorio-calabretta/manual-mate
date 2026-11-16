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
from catalogo import CATALOGO
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
        risposta = self.assistente.rispondi("civic", "Quando freno sento uno stridio")
        self.assertEqual(risposta.esito, "fonte_assente")
        self.assertIn("Nei passaggi del libretto", risposta.testo)
        self.assertIsNone(risposta.fonte_citata)
        self.assertEqual(self.chiamate, ["/v1/responses"])

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
                self.assertEqual(primo_indice.indicizza(self.cartella, civic), 2)
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
                risultati = secondo_indice.cerca(civic, collezione, query)
                self.assertEqual(risultati[0].metadata["pagina"], 623)
                self.assertEqual(self.input_embedding, [[query]])
            finally:
                secondo_store.get_client().close()

    def test_nuova_versione_diventa_attiva_dopo_ingestione(self):
        focus = CATALOGO["focus"]
        with patch("indice.leggi_passaggi", return_value={"focus-olio": "Versione iniziale"}):
            self.indice.indicizza(self.cartella, focus)
        precedente = self.indice.collezione_attiva(focus)
        with patch("indice.leggi_passaggi", return_value={"focus-olio": "Versione aggiornata"}):
            self.indice.indicizza(self.cartella, focus)
        attiva = self.indice.collezione_attiva(focus)
        self.assertNotEqual(attiva, precedente)
        risultati = self.indice.cerca(focus, attiva, "Spia olio motore")
        self.assertIn("Versione aggiornata", risultati[0].text)


if __name__ == "__main__":
    unittest.main()
