import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from datapizza.core.vectorstore import VectorConfig
from datapizza.type import Chunk
from datapizza.vectorstores.qdrant import QdrantVectorstore
from qdrant_client import models

from catalogo import Veicolo
from config import CHUNK_MAX_CHAR, CHUNK_OVERLAP, EMBEDDING_BATCH_SIZE, TOP_K
from corpus import estrai_documenti
from osservabilita import span


VETTORE = "content_embedding"


class IndiceManuali:
    def __init__(self, embedder, store: QdrantVectorstore, top_k: int = TOP_K):
        if top_k < 1:
            raise ValueError("RAG_TOP_K deve essere un numero positivo.")
        self.embedder = embedder
        self.store = store
        self.top_k = top_k

    def collezione_attiva(self, veicolo: Veicolo) -> str | None:
        collezione = self._risolvi_alias(veicolo)
        return collezione if collezione and collezione.startswith(f"manuali_{veicolo.id}_completo_") else None

    def _risolvi_alias(self, veicolo: Veicolo) -> str | None:
        alias = f"manuali_{veicolo.id}"
        return next((
            voce.collection_name for voce in self.store.get_client().get_aliases().aliases
            if voce.alias_name == alias
        ), None)

    def indicizza(self, cartella: Path, veicolo: Veicolo) -> int:
        documenti, pagine, senza_testo = estrai_documenti(cartella, veicolo)
        # Testi, metadati e modello identificano una versione precisa dell'indice.
        firma = json.dumps([VETTORE, self.embedder.model_name, CHUNK_MAX_CHAR, CHUNK_OVERLAP, documenti], ensure_ascii=False)
        versione = hashlib.sha256(firma.encode("utf-8")).hexdigest()[:20]
        alias = f"manuali_{veicolo.id}"
        collezione = f"{alias}_completo_{versione}"
        client = self.store.get_client()
        aggiunti = 0
        # Una versione completa si riusa. Se una scrittura è rimasta a metà, gli ID stabili consentono di ripeterla.
        esiste = client.collection_exists(collezione)
        presenti = client.count(collezione, exact=True).count if esiste else 0
        if presenti != len(documenti):
            print(f"{veicolo.nome}: {pagine - len(senza_testo)}/{pagine} pagine con testo, {len(documenti)} passaggi.", flush=True)
            if senza_testo:
                print(f"Pagine PDF prive di testo estraibile: {', '.join(map(str, senza_testo))}.", flush=True)
            for inizio in range(0, len(documenti), EMBEDDING_BATCH_SIZE):
                batch = [(str(uuid5(NAMESPACE_URL, meta["fonte"])), testo, meta)
                         for testo, meta in documenti[inizio:inizio + EMBEDDING_BATCH_SIZE]]
                if esiste and presenti:
                    ids = [identificativo for identificativo, _, _ in batch]
                    salvati = {punto.id for punto in client.retrieve(collezione, ids, with_payload=False)}
                    batch = [punto for punto in batch if punto[0] not in salvati]
                if not batch:
                    continue
                vettori = self.embedder.embed([testo for _, testo, _ in batch])
                if not esiste:
                    self.store.create_collection(collezione, [VectorConfig(name=VETTORE, dimensions=len(vettori[0]))])
                    esiste = True
                # Stesso payload di QdrantVectorstore.add, inviato in blocco per le centinaia di pagine dei PDF.
                punti = [models.PointStruct(id=identificativo, payload={"text": testo, **meta}, vector={VETTORE: vettore})
                         for (identificativo, testo, meta), vettore in zip(batch, vettori, strict=True)]
                client.upsert(collezione, points=punti, wait=True)
                aggiunti += len(punti)
            if client.count(collezione, exact=True).count != len(documenti):
                raise ValueError(f"Indice incompleto per {veicolo.nome}.")

        attiva = self._risolvi_alias(veicolo)
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

    def cerca(self, veicolo: Veicolo, collezione: str, query: str, *, solo_avvisi: bool = False) -> list[Chunk]:
        with span("ricerca-manuale", "RETRIEVER", veicolo=veicolo.id, collezione=collezione) as traccia:
            # I vettori dei manuali sono già sul volume. Qui si calcola solo quello della domanda.
            vettore = self.embedder.embed(query)
            campo = "avviso_curato" if solo_avvisi else "indice_analitico"
            condizione = models.FieldCondition(key=campo, match=models.MatchValue(value=True))
            filtro = models.Filter(must=[condizione]) if solo_avvisi else models.Filter(must_not=[condizione])
            risultati = self.store.search(collezione, vettore, k=self.top_k, vector_name=VETTORE, query_filter=filtro)
            traccia.set_attribute("fonti", [hit.metadata["fonte"] for hit in risultati])
            return risultati

    def completa_pagina(self, collezione: str, risultato: Chunk) -> Chunk:
        if risultato.metadata.get("avviso_curato"):
            return risultato
        condizioni = [
            models.FieldCondition(key="pagina_pdf", match=models.MatchValue(value=risultato.metadata["pagina_pdf"])),
            models.FieldCondition(key="avviso_curato", match=models.MatchValue(value=False)),
        ]
        punti, _ = self.store.get_client().scroll(
            collezione, scroll_filter=models.Filter(must=condizioni), limit=32, with_vectors=False,
        )
        if len(punti) < 2:
            return risultato
        ordinati = sorted((punto.payload for punto in punti), key=lambda meta: int(meta["fonte"].rsplit("-", 1)[1]))
        righe = []
        for meta in ordinati:
            parte = meta["text"].partition("\n\n")[2].splitlines()
            # La fine di un chunk può coincidere con l'inizio del seguente a causa dell'overlap.
            doppie = next((n for n in range(min(len(righe), len(parte)), 0, -1) if righe[-n:] == parte[:n]), 0)
            righe.extend(parte[doppie:])
        titolo = risultato.metadata["sezione"]
        return Chunk(id=risultato.id, text=f"{titolo}\n\n" + "\n".join(righe), metadata=risultato.metadata)
