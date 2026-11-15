import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from datapizza.core.vectorstore import VectorConfig
from datapizza.type import Chunk, DenseEmbedding
from datapizza.vectorstores.qdrant import QdrantVectorstore
from qdrant_client import models

from catalogo import Veicolo, leggi_passaggi
from osservabilita import span


VETTORE = "content_embedding"
TOP_K = 2


class IndiceManuali:
    def __init__(self, embedder, store: QdrantVectorstore):
        self.embedder = embedder
        self.store = store

    def collezione_attiva(self, veicolo: Veicolo) -> str | None:
        # Un alias stabile per veicolo punta alla versione dell'indice pronta per la ricerca.
        alias = f"manuali_{veicolo.id}"
        return next((
            voce.collection_name for voce in self.store.get_client().get_aliases().aliases
            if voce.alias_name == alias
        ), None)

    def indicizza(self, cartella: Path, veicolo: Veicolo) -> int:
        passaggi = leggi_passaggi(cartella, veicolo)
        # Qdrant conserva insieme vettore, testo originale e metadati utili per la citazione.
        documenti = [
            (f"{avviso.titolo}\n\n{passaggi[avviso.id]}", {
                "fonte": avviso.id, "veicolo": veicolo.id, "pagina": avviso.pagina,
                "pagina_pdf": avviso.pagina_pdf, "source_file": veicolo.file,
            })
            for avviso in veicolo.avvisi
        ]
        # Testi, metadati e modello identificano una versione precisa dell'indice.
        firma = json.dumps([VETTORE, self.embedder.model_name, veicolo.edizione, documenti], ensure_ascii=False)
        versione = hashlib.sha256(firma.encode("utf-8")).hexdigest()[:20]
        alias = f"manuali_{veicolo.id}"
        collezione = f"{alias}_{versione}"
        client = self.store.get_client()
        aggiunti = 0
        # Una versione completa si riusa. Se una scrittura è rimasta a metà, gli ID stabili consentono di ripeterla.
        if not client.collection_exists(collezione) or client.count(collezione, exact=True).count != len(documenti):
            vettori = self.embedder.embed([testo for testo, _ in documenti])
            chunks = [
                Chunk(
                    id=str(uuid5(NAMESPACE_URL, metadata["fonte"])), text=testo,
                    embeddings=[DenseEmbedding(name=VETTORE, vector=vettore)], metadata=metadata,
                )
                for (testo, metadata), vettore in zip(documenti, vettori, strict=True)
            ]
            self.store.create_collection(collezione, [VectorConfig(name=VETTORE, dimensions=len(vettori[0]))])
            self.store.add(chunks, collection_name=collezione)
            aggiunti = len(chunks)

        attiva = self.collezione_attiva(veicolo)
        if attiva != collezione:
            # L'alias cambia solo quando tutti i passaggi della nuova versione sono pronti.
            operazioni = []
            if attiva is not None:
                operazioni.append(models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=alias)))
            operazioni.append(models.CreateAliasOperation(create_alias=models.CreateAlias(
                collection_name=collezione, alias_name=alias,
            )))
            client.update_collection_aliases(operazioni)
        return aggiunti

    def cerca(self, veicolo: Veicolo, collezione: str, query: str) -> list[Chunk]:
        with span("ricerca-manuale", "RETRIEVER", veicolo=veicolo.id, collezione=collezione) as traccia:
            # I vettori dei manuali sono già sul volume. Qui si calcola solo quello della domanda.
            vettore = self.embedder.embed(query)
            risultati = self.store.search(collezione, vettore, k=TOP_K, vector_name=VETTORE)
            traccia.set_attribute("fonti", [hit.metadata["fonte"] for hit in risultati])
            return risultati
