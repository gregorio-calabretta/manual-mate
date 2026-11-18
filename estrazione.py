from pathlib import Path
from hashlib import sha256
from importlib.metadata import version
from tempfile import NamedTemporaryFile

from pypdf import PdfReader


def documento_docling(percorso: Path):
    from docling_core.types.doc import DoclingDocument

    firma = sha256(percorso.read_bytes() + version("docling").encode()).hexdigest()
    cache = Path(__file__).resolve().parent / ".cache_ingestione" / "docling"
    cache.mkdir(parents=True, exist_ok=True)
    destinazione = cache / f"{firma}.json"
    if destinazione.exists():
        try:
            return DoclingDocument.model_validate_json(destinazione.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    from datapizza.modules.parsers.docling import DoclingParser
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    parser = DoclingParser()
    # L'adattatore Datapizza restituisce il documento con la provenienza delle pagine.
    opzioni = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    parser.converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opzioni)})
    documento = DoclingDocument.model_validate(parser.parse_to_json(str(percorso)))
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=cache, delete=False) as file:
        temporaneo = Path(file.name)
        file.write(documento.model_dump_json())
    try:
        temporaneo.replace(destinazione)
    finally:
        temporaneo.unlink(missing_ok=True)
    return documento


def estrai_pagine(percorso: Path, estrattore: str = "pypdf"):
    """Restituisce pagina PDF, testo per la numerazione e contenuto da indicizzare."""
    if estrattore not in {"pypdf", "pdfium", "docling"}:
        raise ValueError(f"Estrattore PDF sconosciuto: {estrattore}")
    if estrattore == "docling":
        documento = documento_docling(percorso)
        pagine = pagine_docling(documento)
        with percorso.open("rb") as file:
            pdf = PdfReader(file)
            for numero, pagina in enumerate(pdf.pages, 1):
                yield numero, pagina.extract_text() or "", pagine.get(numero, "")
        return
    if estrattore == "pdfium":
        import pypdfium2 as pdfium

        with percorso.open("rb") as file, pdfium.PdfDocument(str(percorso)) as documento:
            pdf = PdfReader(file)
            for numero, pagina in enumerate(pdf.pages, 1):
                pagina_pdfium = documento[numero - 1]
                try:
                    testo = pagina_pdfium.get_textpage()
                    try:
                        contenuto = testo.get_text_range().replace("\ufffe", "").replace("\r\n", "\n")
                    finally:
                        testo.close()
                finally:
                    pagina_pdfium.close()
                yield numero, pagina.extract_text() or "", contenuto
        return
    with percorso.open("rb") as file:
        for numero, pagina in enumerate(PdfReader(file).pages, 1):
            contenuto = pagina.extract_text() or ""
            yield numero, contenuto, contenuto


def pagine_docling(documento) -> dict[int, str]:
    """Legge una volta la struttura e mantiene ordine, titoli, tabelle e provenienza."""
    from docling_core.types.doc import PictureItem, TableItem
    from docling_core.transforms.serializer.markdown import MarkdownDocSerializer

    pagine: dict[int, list[str]] = {}
    multipagina = set()
    serializzatore = MarkdownDocSerializer(doc=documento)
    for elemento, _ in documento.iterate_items(traverse_pictures=True):
        provenienze = {prov.page_no for prov in getattr(elemento, "prov", ())}
        if not provenienze:
            continue
        etichetta = elemento.label.value
        if etichetta in {"page_header", "page_footer"}:
            continue
        if len(provenienze) > 1:
            if hasattr(elemento, "text"):
                for prov in elemento.prov:
                    inizio, fine = prov.charspan
                    testo = elemento.text[inizio:fine].strip()
                    if testo:
                        pagine.setdefault(prov.page_no, []).append(testo)
            else:
                multipagina.update(provenienze)
            continue
        if isinstance(elemento, TableItem):
            testo = elemento.caption_text(documento) + "\n" + serializzatore.serialize(item=elemento).text
        elif isinstance(elemento, PictureItem):
            testo = elemento.caption_text(documento)
        else:
            testo = getattr(elemento, "text", "")
            if etichetta in {"title", "section_header"}:
                testo = f"## {testo}"
        if testo.strip():
            pagina = next(iter(provenienze))
            pagine.setdefault(pagina, []).append(testo.strip())
    risultato = {numero: "\n\n".join(parti) for numero, parti in pagine.items()}
    # Per gli elementi che attraversano un confine usa il filtro di pagina del serializzatore.
    for numero in multipagina:
        risultato[numero] = documento.export_to_markdown(page_no=numero)
    return risultato
