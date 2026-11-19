import re
from pathlib import Path
from textwrap import wrap

from catalogo import Veicolo, normalizza
from config import CHUNK_MAX_CHAR, CHUNK_OVERLAP
from estrazione import estrai_pagine


def leggi_pagina(testo: str, veicolo: Veicolo, posizione: int | None = None) -> tuple[int | None, str, list[str]]:
    righe = [riga.strip() for riga in testo.splitlines() if riga.strip()]
    layout = veicolo.layout
    if layout.stile == "numero_tra_colonne" and posizione is not None:
        # L'OCR può inserire il piè di pagina nel mezzo delle due colonne.
        numero_atteso = posizione - layout.scarto_pagine
        pagina = numero_atteso if str(numero_atteso) in righe else None
        corpo = [riga for riga in righe if riga not in {str(pagina), *layout.righe_da_escludere}]
        if layout.pagine_indice[0] <= posizione <= layout.pagine_indice[1]:
            return pagina, "Indice analitico", corpo
        if layout.pagine_sommario[0] <= posizione <= layout.pagine_sommario[1]:
            return pagina, "Sommario", corpo
        if layout.pagine_corpo[0] <= posizione <= layout.pagine_corpo[1] and corpo:
            return pagina, corpo[0], corpo[1:]
        return pagina, "Manuale d’uso", corpo
    for i in range(len(righe) - 1, -1, -1):
        riga = righe[i]
        if layout.stile == "maiuscole" and layout.marcatore_footer in riga:
            pagina = int(righe[i - 1]) if i > 0 and righe[i - 1].isdigit() else None
            sezione = righe[i + 1] if i + 1 < len(righe) else "Manuale d’uso"
            fine = i - 1 if pagina is not None else i
            return pagina, sezione, righe[:fine]
        if layout.stile == "simboli" and riga.startswith(layout.marcatore_footer):
            numero = re.search(r"\bPage (\d+)\b", riga)
            pagina = int(numero[1]) if numero else None
            corpo = [r for r in righe[:i] if not re.fullmatch(rf"(?:SEGUE\s*)?{pagina}(?:\s*SEGUE)?|SEGUE", r)]
            intestazione = next((r for r in corpo[:5] if r.startswith("uu")), None)
            sezione = " / ".join(re.split(r"u(?=[A-Z])", intestazione[2:])) if intestazione else next(
                iter(corpo), "Manuale d’uso",
            )
            return pagina, sezione, [r for r in corpo if r != intestazione]
    # Alcuni libretti riportano il numero stampato come ultima riga autonoma.
    if righe and re.fullmatch(r"\d{1,4}", righe[-1]):
        pagina = int(righe[-1])
        corpo = righe[:-1]
        sezione = corpo[0] if corpo else "Manuale d’uso"
        return pagina, sezione, corpo[1:]
    return None, "Manuale d’uso", righe


def titolo_sottosezione(riga: str, successiva: str, precedente: str, veicolo: Veicolo) -> str | None:
    markdown = re.fullmatch(r"#{1,6}\s+(.+)", riga)
    if markdown:
        return markdown[1]
    titolo = normalizza(riga)
    if not titolo or len(riga) > 175 or titolo in {
        "warning", "warnings", "avvertenze", "avvertenza", "pericolo", "caution", "note", "tips", "attention", "nota",
    }:
        return None
    if veicolo.layout.stile == "maiuscole":
        lettere = [lettera for lettera in riga if lettera.isalpha()]
        if len(lettere) >= 4 and riga.isupper() and len(riga) <= 105 and not re.search(r"\d|[.?!:]", riga):
            return riga
    elif veicolo.layout.stile == "simboli":
        if riga.startswith(("■", "●")):
            return re.sub(r"\s+1[A-Z].*$", "", riga.lstrip("■● ")).strip()
        # Il PDF a due colonne ripete alcuni titoli dopo il numero della nota.
        if 3 <= len(riga) <= 82 and re.match(r"^\d+[A-Z]", successiva):
            if normalizza(re.sub(r"^\d+", "", successiva)) == titolo:
                return riga
    else:
        # Quando l'OCR perde lo stile del titolo, una riga breve prima di un nuovo blocco
        # è più indicativa delle maiuscole, usate anche nelle normali frasi.
        if not (1 <= len(riga.split()) <= 7 and 4 <= len(riga) <= 67 and riga[0].isupper()
                and re.fullmatch(r"[\w /–-]+", riga)):
            return None
        inizio_frase = re.match(
            r"^(?:A|An|The|If|When|To|Have|Press|Push|Pull|Hold|Apply|After|Before|Driving|"
            r"Always|Check|Only|For|Your|This|With|See|At|In|On|Some|It|Once|Make|Do|Note|Tips|"
            r"WARNING|CAUTION|Fig|Applies)\b", riga,
        )
        if inizio_frase and not re.fullmatch(r"\w+ (?:with|without) [\w -]+", riga, re.I):
            return None
        if (successiva and (successiva[0].isupper() or successiva.startswith((">", "@", "»", "■")))
                and (not precedente or precedente.endswith((".", "?", "!", ")", ":")) or precedente[0].isupper())):
            return riga
    return None


def sottosezioni(righe: list[str], veicolo: Veicolo, titolo_iniziale: str) -> list[tuple[str, list[str]]]:
    risultati = []
    titolo = titolo_iniziale
    corpo = []
    for i, riga in enumerate(righe):
        nuovo = titolo_sottosezione(
            riga, righe[i + 1] if i + 1 < len(righe) else "", righe[i - 1] if i else "", veicolo,
        )
        if nuovo:
            if corpo and (sum(map(len, corpo)) >= 75 or titolo != titolo_iniziale):
                if veicolo.layout.stile == "maiuscole" and len(corpo) <= 2 and all(t.isupper() for t in corpo):
                    # Conserva tutte le righe di un titolo, comprese le condizioni intermedie.
                    nuovo = " ".join([*corpo, nuovo])
                else:
                    risultati.append((titolo, corpo))
                    corpo = []
            titolo = nuovo
        corpo.append(riga)
    risultati.append((titolo, corpo))
    return risultati


def dividi_sottosezione(righe: list[str]) -> list[list[str]]:
    gruppi = []
    corrente = []
    caratteri = 0
    fine_frase = 0
    for riga in righe:
        for parte in wrap(riga, width=CHUNK_MAX_CHAR - 1, replace_whitespace=False) or [riga]:
            lunghezza = len(parte) + 1
            if corrente and caratteri + lunghezza > CHUNK_MAX_CHAR:
                taglio = len(corrente)
                if (fine_frase and sum(len(r) + 1 for r in corrente[:fine_frase]) >= CHUNK_MAX_CHAR / 2
                        and sum(len(r) + 1 for r in corrente[fine_frase:]) + lunghezza <= CHUNK_MAX_CHAR):
                    taglio = fine_frase
                gruppi.append(corrente[:taglio])
                rimanenti = corrente[taglio:]
                spazio = min(CHUNK_OVERLAP, CHUNK_MAX_CHAR - lunghezza - sum(len(r) + 1 for r in rimanenti))
                for riga_precedente in reversed(corrente[:taglio]):
                    if len(riga_precedente) + 1 > spazio:
                        break
                    rimanenti.insert(0, riga_precedente)
                    spazio -= len(riga_precedente) + 1
                corrente = rimanenti
                caratteri = sum(len(r) + 1 for r in corrente)
                fine_frase = 0
            corrente.append(parte)
            caratteri += lunghezza
            if parte.endswith((".", "!", "?", ":")):
                fine_frase = len(corrente)
    if corrente:
        gruppi.append(corrente)
    return gruppi


def estrai_documenti(
    cartella: Path, veicolo: Veicolo, *, estrattore: str | None = None, strategia: str | None = None,
) -> tuple[list[tuple[str, dict]], int, list[int]]:
    estrattore = estrattore or veicolo.estrattore_pdf
    strategia = strategia or veicolo.strategia_chunk
    if strategia not in {"sottosezioni", "pagina", "ricorsivo"}:
        raise ValueError(f"Strategia di chunking sconosciuta: {strategia}")
    base = {"veicolo": veicolo.id, "edizione": veicolo.edizione, "source_file": veicolo.file}
    documenti = []
    senza_testo = []
    sezione_precedente = titolo_precedente = None
    pagine = 0
    for posizione, originale, contenuto in estrai_pagine(cartella / veicolo.file, estrattore):
        pagine = posizione
        pagina, sezione, righe = leggi_pagina(originale, veicolo, posizione)
        if estrattore != "pypdf":
            righe = [riga.strip() for riga in contenuto.splitlines() if riga.strip()]
            if righe and righe[0] == sezione:
                righe = righe[1:]
            if righe and pagina is not None and righe[-1] == str(pagina):
                righe = righe[:-1]
        if not righe:
            senza_testo.append(posizione)
            sezione_precedente = titolo_precedente = None
            continue
        esclusa = sezione.casefold().startswith(("indice", "sommario"))
        ultimo_livello = sezione.split(" / ")[-1]
        titolo_iniziale = ultimo_livello
        if titolo_precedente and sezione == sezione_precedente and re.match(r"^(?:[a-zàèé]|[0-9]+\.)", righe[0]):
            titolo_iniziale = titolo_precedente
        blocchi = ([(titolo_iniziale, righe)] if esclusa or strategia in {"pagina", "ricorsivo"}
                   else sottosezioni(righe, veicolo, titolo_iniziale))
        i = 0
        sezione_precedente = sezione
        for titolo, corpo in blocchi:
            titolo_precedente = titolo
            tema = normalizza(titolo)
            intestazione = sezione if tema in {normalizza(sezione), normalizza(ultimo_livello)} else f"{sezione} / {titolo}"
            # Ogni fonte mantiene una singola pagina, anche se il tema continua in quella successiva.
            if strategia == "ricorsivo" and not esclusa:
                from datapizza.modules.splitters import RecursiveSplitter
                from datapizza.type import Node, NodeType

                # I paragrafi Docling arrivano separati da righe vuote; conserva anche le tabelle.
                paragrafi = [parte.strip() for parte in contenuto.split("\n\n") if parte.strip()]
                nodo = Node(node_type=NodeType.PAGE, children=[
                    Node(node_type=NodeType.PARAGRAPH, content=parte) for parte in paragrafi
                ])
                splitter = RecursiveSplitter(max_char=CHUNK_MAX_CHAR, overlap=CHUNK_OVERLAP)
                gruppi = [chunk.text.splitlines() for chunk in splitter.split(nodo)]
            else:
                gruppi = dividi_sottosezione(corpo)
            for righe_chunk in gruppi:
                i += 1
                testo = "\n".join(righe_chunk)
                documenti.append((f"{intestazione}\n\n{testo}", {
                    **base, "fonte": f"{veicolo.id}-pdf{posizione}-{i}", "pagina": pagina,
                    "pagina_pdf": posizione, "sezione": intestazione, "avviso_curato": False,
                    "indice_analitico": esclusa, "tema": tema,
                    "tema_specifico": len(tema) >= 10 and (tema != normalizza(sezione) or " / " in sezione),
                }))
    return documenti, pagine, senza_testo
