import re
from pathlib import Path
from textwrap import wrap

from datapizza.modules.splitters import RecursiveSplitter
from datapizza.type import Node, NodeType
from pypdf import PdfReader

from catalogo import Veicolo, leggi_passaggi
from config import CHUNK_MAX_CHAR, CHUNK_OVERLAP


def leggi_pagina(testo: str, veicolo: Veicolo) -> tuple[int | None, str, list[str]]:
    righe = [riga.strip() for riga in testo.splitlines() if riga.strip()]
    for i in range(len(righe) - 1, -1, -1):
        riga = righe[i]
        if veicolo.id == "focus" and "Vehicles Built From:" in riga:
            pagina = int(righe[i - 1]) if i > 0 and righe[i - 1].isdigit() else None
            sezione = righe[i + 1] if i + 1 < len(righe) else "Manuale d’uso"
            fine = i - 1 if pagina is not None else i
            return pagina, sezione, righe[:fine]
        if veicolo.id == "civic" and riga.startswith("23 CIVIC TYPE R JSS"):
            numero = re.search(r"\bPage (\d+)\b", riga)
            pagina = int(numero[1]) if numero else None
            corpo = [r for r in righe[:i] if not re.fullmatch(rf"(?:SEGUE\s*)?{pagina}(?:\s*SEGUE)?|SEGUE", r)]
            intestazione = next((r for r in corpo[:5] if r.startswith("uu")), None)
            sezione = " / ".join(re.split(r"u(?=[A-Z])", intestazione[2:])) if intestazione else next(
                iter(corpo), "Manuale d’uso",
            )
            return pagina, sezione, [r for r in corpo if r != intestazione]
    return None, "Manuale d’uso", righe


def estrai_documenti(cartella: Path, veicolo: Veicolo) -> tuple[list[tuple[str, dict]], int, list[int]]:
    passaggi = leggi_passaggi(cartella, veicolo)
    base = {"veicolo": veicolo.id, "edizione": veicolo.edizione, "source_file": veicolo.file}
    # I tre passaggi già verificati restano disponibili come blocchi completi per gli avvisi dell'olio.
    documenti = [
        (f"{avviso.titolo}\n\n{passaggi[avviso.id]}", {
            **base, "fonte": avviso.id, "pagina": avviso.pagina, "pagina_pdf": avviso.pagina_pdf,
            "sezione": avviso.titolo, "avviso_curato": True,
        })
        for avviso in veicolo.avvisi
    ]
    splitter = RecursiveSplitter(max_char=CHUNK_MAX_CHAR, overlap=CHUNK_OVERLAP)
    senza_testo = []
    with (cartella / veicolo.file).open("rb") as file:
        pdf = PdfReader(file)
        for posizione, pagina_pdf in enumerate(pdf.pages, 1):
            pagina, sezione, righe = leggi_pagina(pagina_pdf.extract_text() or "", veicolo)
            if not righe:
                senza_testo.append(posizione)
                continue
            # Ogni nodo resta dentro una pagina, così anche il passaggio a cavallo di due chunk ha una citazione precisa.
            foglie = [Node(content=f"{parte}\n", node_type=NodeType.PARAGRAPH) for riga in righe
                      for parte in wrap(riga, width=CHUNK_MAX_CHAR - CHUNK_OVERLAP - 1, replace_whitespace=False)]
            if not foglie:
                senza_testo.append(posizione)
                continue
            for i, chunk in enumerate(splitter.split(Node(children=foglie, node_type=NodeType.PAGE)), 1):
                testo = "\n".join(riga.strip() for riga in chunk.text.splitlines()).strip()
                documenti.append((f"{sezione}\n\n{testo}", {
                    **base, "fonte": f"{veicolo.id}-pdf{posizione}-{i}", "pagina": pagina,
                    "pagina_pdf": posizione, "sezione": sezione, "avviso_curato": False,
                    "indice_analitico": sezione.casefold().startswith(("indice", "sommario")),
                }))
        return documenti, len(pdf.pages), senza_testo
