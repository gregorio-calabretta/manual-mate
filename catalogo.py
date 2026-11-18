import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Avviso:
    id: str
    titolo: str
    # La citazione usa la pagina stampata, mentre l'estrazione usa la posizione nel PDF.
    pagina: int
    pagina_pdf: int
    # Questi marcatori delimitano la sezione da conservare nel singolo chunk.
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
    lingua: str = "italiano"
    pattern_nome: str = ""
    anni_edizione: tuple[str, ...] = ()
    pattern_modelli_diversi: str = ""
    estrattore_pdf: str = "pypdf"
    strategia_chunk: str = "sottosezioni"


FOCUS = Veicolo(
    "focus", "Ford Focus (CEW)",
    "CG3630itITA, ed. 09/2014 (produzione 08/09/2014–15/02/2015)",
    "ITITA_CG3630_Focus_og_201409.pdf",
    (Avviso("focus-olio", "Spia olio motore", 80, 82, "Spia olio motore", "Spie motore",
            r"\bspia (?:rossa )?(?:dell )?olio(?: motore)?\b"),),
    pattern_nome=r"(?:ford )?focus(?: cew)?", anni_edizione=("2014", "2015"),
)

CIVIC = Veicolo(
    "civic", "Honda Civic Type R", "23 CIVIC TYPE R, 3LT40600",
    "23 CIVIC TYPE R JSS (KE KG)-3LT40600_IT_web.pdf",
    (
        Avviso("civic-pressione", "Pressione olio motore bassa", 623, 624,
               "■ Cause della visualizzazione", "23 CIVIC TYPE R JSS",
               r"\b(?:pressione (?:dell )?olio(?: motore)? (?:e )?(?:troppo )?"
               r"(?:bassa|basso|insufficiente|sotto il minimo)|bassa pressione (?:dell )?olio)\b"),
        Avviso("civic-livello", "Livello olio motore basso", 629, 630,
               "■ Cause della visualizzazione", "23 CIVIC TYPE R JSS",
               r"\b(?:livello (?:dell )?olio(?: motore)? (?:e )?(?:troppo )?"
               r"(?:basso|insufficiente|sotto il minimo)|basso livello (?:dell )?olio)\b"),
    ),
    pattern_nome=r"(?:honda )?civic(?: type r)?", anni_edizione=("2023",),
    pattern_modelli_diversi=r"\bcivic (?:non type r|type s|sport|e hev|hybrid)\b",
)

AUDI = Veicolo(
    "audi", "Audi A3 8V", "2019, 8V2012721B (Nord America, inglese)",
    "audi a3 8v 2019.pdf", (), lingua="inglese",
    pattern_nome=r"(?:audi )?a3(?: 8 ?v)?", anni_edizione=("2019",),
    pattern_modelli_diversi=r"\ba3 (?:8 ?[lpys]|non 8 ?v)\b",
)

LEON = Veicolo(
    "leon", "SEAT Leon", "5D / Sportstourer, 5FA012750BT, ed. 11/2021",
    "SEAT_LEON_11_21_IT.pdf", (),
    pattern_nome=r"(?:seat )?leon(?: (?:5d|sportstourer))?", anni_edizione=("2021",),
    estrattore_pdf="docling", strategia_chunk="ricorsivo",
)

CATALOGO = {veicolo.id: veicolo for veicolo in (FOCUS, CIVIC, AUDI, LEON)}


def normalizza(testo: str) -> str:
    # I pattern lavorano su parole minuscole, senza accenti e con la punteggiatura separata.
    lettere = unicodedata.normalize("NFKD", testo.casefold())
    lettere = "".join(c for c in lettere if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", lettere))


def anni_del_modello(testo: str, veicolo: Veicolo) -> set[str]:
    # Un codice come CR 2032 non è l'anno del veicolo.
    espliciti = re.findall(r"\b(?:del|anno|my|immatricolazione) ((?:19|20)\d{2})\b", testo)
    accanto_al_nome = re.findall(rf"\b{veicolo.pattern_nome} ((?:19|20)\d{2})\b", testo)
    return set(espliciti + accanto_al_nome)


def riconosci_avviso(veicolo: Veicolo, domanda: str, contesto: tuple[str, ...] = ()) -> Avviso | None:
    testo = normalizza(domanda)
    # Se la domanda confronta pressione e livello, chiedi quale compare sul quadro.
    if veicolo == CIVIC and {"pressione", "livello"} <= set(testo.split()):
        return None
    corrispondenze = [avviso for avviso in veicolo.avvisi if re.search(avviso.pattern, testo)]
    if veicolo == CIVIC and not corrispondenze and any("olio" in normalizza(turno).split() for turno in contesto):
        # Dopo un chiarimento sull'olio, una risposta breve come «quella della pressione» basta.
        scelta = re.fullmatch(
            r"(?:(?:e|era|quella|quello|la|il|della|del|di|bassa|basso) )*"
            r"(pressione|livello)(?: (?:dell olio|olio(?: motore)?))?(?: (?:bassa|basso))?",
            testo,
        )
        if scelta:
            identificativo = f"civic-{scelta[1]}"
            return next(avviso for avviso in veicolo.avvisi if avviso.id == identificativo)
    return corrispondenze[0] if len(corrispondenze) == 1 else None


def leggi_passaggi(cartella: Path, veicolo: Veicolo) -> dict[str, str]:
    from pypdf import PdfReader

    passaggi = {}
    with (cartella / veicolo.file).open("rb") as documento:
        pdf = PdfReader(documento)
        if veicolo == AUDI:
            copertina = pdf.pages[0].extract_text() or ""
            retro = pdf.pages[-1].extract_text() or ""
            if "2019 A3" not in copertina or "8V2012721B" not in retro or "Englisch Nordamerika" not in retro:
                raise ValueError(f"Edizione non riconosciuta nel manuale {veicolo.file}.")
        for avviso in veicolo.avvisi:
            if avviso.pagina_pdf > len(pdf.pages):
                raise ValueError(f"Pagina PDF assente nel manuale {veicolo.file}.")
            testo = pdf.pages[avviso.pagina_pdf - 1].extract_text()
            prima, trovato, dopo = testo.partition(avviso.inizio)
            corpo, fine, _ = dopo.partition(avviso.fine)
            # Titolo e marcatori aiutano a rilevare un PDF di un'edizione diversa da quella attesa.
            if not trovato or not fine or not corpo.strip() or (
                normalizza(avviso.titolo) not in normalizza(prima + trovato)
            ):
                raise ValueError(f"Sezione non riconosciuta nel manuale {veicolo.file}, pagina {avviso.pagina}.")
            # Per la Focus il marcatore iniziale è il titolo, che l'indice aggiunge già al chunk.
            estratto = corpo.strip() if veicolo == FOCUS else (trovato + corpo).strip()
            passaggi[avviso.id] = estratto
    return passaggi
