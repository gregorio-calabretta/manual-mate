import re
from dataclasses import dataclass, field
from typing import Literal

from datapizza.type import Chunk
from pydantic import BaseModel


class PassaggioVerificabile(BaseModel):
    fonte_id: str
    citazione: str
    frase: str


class Riesame(BaseModel):
    risposte: list[PassaggioVerificabile]
    parte_non_documentata: str


class VerificaSintesi(BaseModel):
    omissioni_rilevanti: list[str]
    esito: Literal["confermata", "corretta", "non_verificabile", "fonte_non_pertinente"]
    sintesi: str


def _testo_citazione(testo: str, *, conserva_trattino: bool = False) -> str:
    # L'a capo può diventare uno spazio nella citazione di una parola sillabata o composta.
    testo = re.sub(r"(?<=[^\W\d_])-(?:[ \t]*\n\s*|[ \t]+)(?=[^\W\d_])",
                   "-" if conserva_trattino else "", testo.replace("\u00ad", ""))
    return " ".join(testo.replace("’", "'").split())


def _estratto_contiene(frase: str, estratti: tuple[str, str]) -> bool:
    inizio = r"(?<!\w)" if frase[0].isalnum() else ""
    fine = r"(?!\w)" if frase[-1].isalnum() else ""
    if frase[0].isdigit():
        inizio += r"(?<![+−-])(?<!\d[.,])"
    if re.search(r"\d[.,]?$", frase):
        fine += r"(?![.,]?\d)"
    pattern = re.compile(inizio + re.escape(frase) + fine)
    return any(pattern.search(estratto) for estratto in estratti)


def _citazione_valida(hit: Chunk | None, citazione: str) -> bool:
    if hit is None:
        return False
    citazione = citazione.strip()
    if (citazione[:1], citazione[-1:]) in {('"', '"'), ("“", "”"), ("«", "»")}:
        citazione = citazione[1:-1]
    corpo = hit.text.partition("\n\n")[2]
    estratti = (_testo_citazione(corpo), _testo_citazione(corpo, conserva_trattino=True))
    for frase in dict.fromkeys((_testo_citazione(citazione), _testo_citazione(citazione, conserva_trattino=True))):
        if len(frase.split()) < 4 or len(frase) < 18:
            continue
        if _estratto_contiene(frase, estratti):
            return True
        # Ammette un solo spazio omesso dall'OCR fra parole alfabetiche di almeno due lettere.
        # Il risultato deve comunque comparire come sequenza consecutiva nella fonte.
        for spazio in re.finditer(r"(?<=[^\W\d_]{2}) (?=[^\W\d_]{2})", frase):
            compatta = frase[:spazio.start()] + frase[spazio.end():]
            if _estratto_contiene(compatta, estratti):
                return True
    return False


def _aggiungi_limite(sintesi: str, parte: str) -> str:
    parte = " ".join(parte.split()).strip(". ")
    if not 0 < len(parte) <= 180:
        return sintesi
    return f"{sintesi}\n\nDal libretto non posso determinare {parte}.".strip()


@dataclass(frozen=True)
class Fonte:
    id: str
    pagina: int | None
    pagina_pdf: int | None = field(default=None, compare=False)

    @classmethod
    def da_chunk(cls, hit: Chunk):
        return cls(hit.metadata["fonte"], hit.metadata["pagina"], hit.metadata["pagina_pdf"])

    @property
    def riferimento(self) -> str:
        pdf = f"PDF p. {self.pagina_pdf}"
        return f"p. {self.pagina} ({pdf})" if self.pagina is not None else pdf


@dataclass(frozen=True)
class Risposta:
    esito: str
    testo: str
    # La valutazione usa l'ordine delle fonti recuperate e la citazione finale come misure distinte.
    fonti_recuperate: tuple[Fonte, ...] = ()
    fonte_citata: Fonte | None = None
    ricerca_eseguita: bool = False
    sintesi: str | None = None
    fonti_aggiuntive: tuple[Fonte, ...] = ()

    @property
    def fonti_citate(self) -> tuple[Fonte, ...]:
        return (self.fonte_citata, *self.fonti_aggiuntive) if self.fonte_citata else ()

    @property
    def testo_cli(self) -> str:
        if self.sintesi is None:
            return self.testo
        _, separatore, riferimento = self.testo.rpartition("\n\nFonte: ")
        return f"{self.sintesi}{separatore}{riferimento}"
