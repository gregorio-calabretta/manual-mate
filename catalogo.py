import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Avviso:
    id: str
    titolo: str
    pagina: int
    pagina_pdf: int
    inizio: str
    fine: str
    pattern: str


@dataclass(frozen=True)
class Veicolo:
    id: str
    nome: str
    edizione: str
    file: str
    avvisi: tuple[Avviso, ...]


FOCUS = Veicolo(
    "focus", "Ford Focus (CEW)",
    "CG3630itITA, ed. 09/2014 (produzione 08/09/2014–15/02/2015)",
    "ITITA_CG3630_Focus_og_201409.pdf",
    (Avviso("focus-olio", "Spia olio motore", 80, 82, "Spia olio motore", "Spie motore",
            r"\bspia (?:rossa )?(?:dell )?olio(?: motore)?\b"),),
)

CIVIC = Veicolo(
    "civic", "Honda Civic Type R", "23 CIVIC TYPE R, 3LT40600",
    "23 CIVIC TYPE R JSS (KE KG)-3LT40600_IT_web.pdf",
    (
        Avviso("civic-pressione", "Pressione olio motore bassa", 623, 624,
               "■ Cause della visualizzazione", "23 CIVIC TYPE R JSS",
               r"\b(?:pressione (?:dell )?olio(?: motore)? (?:bassa|basso)|bassa pressione (?:dell )?olio)\b"),
        Avviso("civic-livello", "Livello olio motore basso", 629, 630,
               "■ Cause della visualizzazione", "23 CIVIC TYPE R JSS",
               r"\b(?:livello (?:dell )?olio(?: motore)? basso|basso livello (?:dell )?olio)\b"),
    ),
)

CATALOGO = {veicolo.id: veicolo for veicolo in (FOCUS, CIVIC)}


def normalizza(testo: str) -> str:
    lettere = unicodedata.normalize("NFKD", testo.casefold())
    lettere = "".join(c for c in lettere if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", lettere))


def riconosci_avviso(veicolo: Veicolo, domanda: str) -> Avviso | None:
    testo = normalizza(domanda)
    # Se la domanda confronta pressione e livello, chiedi quale compare sul quadro.
    if veicolo == CIVIC and {"pressione", "livello"} <= set(testo.split()):
        return None
    corrispondenze = [avviso for avviso in veicolo.avvisi if re.search(avviso.pattern, testo)]
    return corrispondenze[0] if len(corrispondenze) == 1 else None


def leggi_passaggi(cartella: Path, veicolo: Veicolo) -> dict[str, str]:
    from pypdf import PdfReader

    passaggi = {}
    with (cartella / veicolo.file).open("rb") as documento:
        pdf = PdfReader(documento)
        for avviso in veicolo.avvisi:
            if avviso.pagina_pdf > len(pdf.pages):
                raise ValueError(f"Pagina PDF assente nel manuale {veicolo.file}.")
            testo = pdf.pages[avviso.pagina_pdf - 1].extract_text()
            prima, trovato, dopo = testo.partition(avviso.inizio)
            corpo, fine, _ = dopo.partition(avviso.fine)
            if not trovato or not fine or not corpo.strip() or (
                normalizza(avviso.titolo) not in normalizza(prima + trovato)
            ):
                raise ValueError(f"Sezione non riconosciuta nel manuale {veicolo.file}, pagina {avviso.pagina}.")
            estratto = corpo.strip() if veicolo == FOCUS else (trovato + corpo).strip()
            passaggi[avviso.id] = estratto
    return passaggi
