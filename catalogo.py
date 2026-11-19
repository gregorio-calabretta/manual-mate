import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LayoutPDF:
    """Metadati tipografici del documento, senza contenuti per le risposte."""
    stile: str = "generico"
    marcatore_footer: str = ""
    scarto_pagine: int = 0
    pagine_corpo: tuple[int, int] = (0, 0)
    pagine_sommario: tuple[int, int] = (0, 0)
    pagine_indice: tuple[int, int] = (0, 0)
    righe_da_escludere: tuple[str, ...] = ()


@dataclass(frozen=True)
class Veicolo:
    id: str
    nome: str
    edizione: str
    file: str
    lingua: str = "italiano"
    pattern_nome: str = ""
    anni_edizione: tuple[str, ...] = ()
    pattern_modelli_diversi: str = ""
    estrattore_pdf: str = "pypdf"
    strategia_chunk: str = "sottosezioni"
    layout: LayoutPDF = LayoutPDF()


FOCUS = Veicolo(
    "focus", "Ford Focus (CEW)",
    "CG3630itITA, ed. 09/2014 (produzione 08/09/2014–15/02/2015)",
    "ITITA_CG3630_Focus_og_201409.pdf",
    pattern_nome=r"(?:ford )?focus(?: cew)?", anni_edizione=("2014", "2015"),
    layout=LayoutPDF(stile="maiuscole", marcatore_footer="Vehicles Built From:"),
)

CIVIC = Veicolo(
    "civic", "Honda Civic Type R", "23 CIVIC TYPE R, 3LT40600",
    "23 CIVIC TYPE R JSS (KE KG)-3LT40600_IT_web.pdf",
    pattern_nome=r"(?:honda )?civic(?: type r)?", anni_edizione=("2023",),
    pattern_modelli_diversi=r"\bcivic (?:non type r|type s|sport|e hev|hybrid)\b",
    layout=LayoutPDF(stile="simboli", marcatore_footer="23 CIVIC TYPE R JSS"),
)

AUDI = Veicolo(
    "audi", "Audi A3 8V", "2019, 8V2012721B (Nord America, inglese)",
    "audi a3 8v 2019.pdf", lingua="inglese",
    pattern_nome=r"(?:audi )?a3(?: 8 ?v)?", anni_edizione=("2019",),
    pattern_modelli_diversi=r"\ba3 (?:8 ?[lpys]|non 8 ?v)\b",
    layout=LayoutPDF(stile="numero_tra_colonne", scarto_pagine=2,
                     pagine_corpo=(10, 397), pagine_sommario=(4, 7),
                     pagine_indice=(398, 412), righe_da_escludere=("8V2012721B)",)),
)

LEON = Veicolo(
    "leon", "SEAT Leon", "5D / Sportstourer, 5FA012750BT, ed. 11/2021",
    "SEAT_LEON_11_21_IT.pdf",
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


def verifica_manuale(cartella: Path, veicolo: Veicolo) -> int:
    """Controlla che il file configurato sia un PDF leggibile, senza sezioni predefinite."""
    from pypdf import PdfReader

    with (cartella / veicolo.file).open("rb") as documento:
        pdf = PdfReader(documento)
        if pdf.is_encrypted and not pdf.decrypt(""):
            raise ValueError(f"Il manuale {veicolo.file} richiede una password.")
        pagine = len(pdf.pages)
        if not pagine:
            raise ValueError(f"Il manuale {veicolo.file} non contiene pagine.")
        return pagine
