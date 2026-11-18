from datapizza.type import Chunk

from catalogo import Veicolo
from indice import IndiceManuali


class FontiRichiesta:
    """Mantiene fonti e pagine del solo libretto consultato in un turno."""

    def __init__(self, indice: IndiceManuali, veicolo: Veicolo):
        self.indice = indice
        self.veicolo = veicolo
        self.fonti: dict[str, Chunk] = {}
        self.pagine_complete: dict[int, str] = {}

    def appartiene_al_manuale(self, hit: Chunk) -> bool:
        meta = hit.metadata
        return (meta["veicolo"] == self.veicolo.id and meta.get("edizione") == self.veicolo.edizione
                and meta.get("source_file") == self.veicolo.file)

    def completa(self, collezione: str, hit: Chunk) -> Chunk:
        pagina = hit.metadata["pagina_pdf"]
        if pagina not in self.pagine_complete:
            testo = self.indice.completa_pagina(collezione, hit).text
            self.pagine_complete[pagina] = testo.partition("\n\n")[2]
        # L'identificativo citato resta quello del risultato originale.
        titolo = hit.text.partition("\n\n")[0]
        return Chunk(id=hit.id, text=f"{titolo}\n\n{self.pagine_complete[pagina]}", metadata=hit.metadata)

    def aggiungi(self, collezione: str, ricerche: list[list[Chunk]], completa_prime: int = 3) -> None:
        pagine = set()
        for rango in range(max(map(len, ricerche), default=0)):
            for hits in ricerche:
                if rango >= len(hits):
                    continue
                hit = hits[rango]
                meta = hit.metadata
                if (not self.appartiene_al_manuale(hit) or meta["fonte"] in self.fonti
                        or meta["pagina_pdf"] in pagine):
                    continue
                if len(pagine) < completa_prime:
                    hit = self.completa(collezione, hit)
                    pagine.add(meta["pagina_pdf"])
                self.fonti[meta["fonte"]] = hit

    def cerca_nuove(self, collezione: str, query: str) -> dict[str, Chunk]:
        pagine = {hit.metadata["pagina_pdf"] for hit in self.fonti.values()}
        nuove = {}
        for hit in self.indice.cerca(self.veicolo, collezione, query):
            meta = hit.metadata
            if meta["pagina_pdf"] in pagine or not self.appartiene_al_manuale(hit):
                continue
            nuove[meta["fonte"]] = self.completa(collezione, hit)
            pagine.add(meta["pagina_pdf"])
            if len(nuove) == 3:
                break
        self.fonti.update(nuove)
        return nuove

    def completa_citate(self, collezione: str, citate: tuple[Chunk, ...]) -> tuple[Chunk, ...]:
        complete = tuple(self.completa(collezione, hit) for hit in citate)
        self.fonti.update({hit.metadata["fonte"]: hit for hit in complete})
        return complete
