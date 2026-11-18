"""Confronta gli estrattori sullo stesso campione, preparando collezioni separate."""

import argparse
import json
import os
from pathlib import Path
from time import perf_counter

from catalogo import CATALOGO
from fonti import _citazione_valida
from runtime import ROOT, carica_configurazione, crea_assistente
from valutazione import carica_casi


PROFILI = {
    "pypdf_sottosezioni": ("pypdf", "sottosezioni"),
    "pdfium_sottosezioni": ("pdfium", "sottosezioni"),
    "pdfium_pagina": ("pdfium", "pagina"),
    "docling_sottosezioni": ("docling", "sottosezioni"),
    "docling_ricorsivo": ("docling", "ricorsivo"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profili", nargs="+", choices=PROFILI, default=list(PROFILI))
    args = parser.parse_args()
    carica_configurazione()
    assistente = crea_assistente(os.environ["OPENAI_API_KEY"])
    veicolo = CATALOGO["leon"]
    cartella = Path(os.getenv("MANUALI_DIR") or ROOT.parent / "manuali uso e manutenzione auto")
    casi = [caso for caso in carica_casi(ROOT / "queries_leon.json") if caso.esito_atteso == "risposta"]
    # Queste citazioni provengono dalle pagine verificate prima della prova Leon.
    citazioni = {
        108: "Sostituire sempre la batteria scarica con un’altra di uguale voltaggio, dimensioni e specifiche.",
        363: "Se non è reperibile, utilizzare esclusivamente un liquido dei freni di alta qualità",
        375: "gli pneumatici sono freddi",
    }
    destinazione = ROOT / "report_confronto_ingestione.json"
    report = json.loads(destinazione.read_text(encoding="utf-8")) if destinazione.exists() else {}
    for nome in args.profili:
        inizio = perf_counter()
        estrattore, strategia = PROFILI[nome]
        print(f"Preparazione {nome}", flush=True)
        collezione, aggiunti = assistente.indice.prepara(
            cartella, veicolo, estrattore=estrattore, strategia=strategia,
        )
        preparazione = round(perf_counter() - inizio, 2)
        risultati = []
        for caso in casi:
            query = caso.turni[0].messaggio if caso.turni else caso.domanda
            hits = assistente.indice.cerca(veicolo, collezione, query)
            pagine = [hit.metadata["pagina"] for hit in hits]
            rango = pagine.index(caso.pagina_attesa) + 1 if caso.pagina_attesa in pagine else None
            risultati.append({"id": caso.id, "query": query, "pagine": pagine, "rango_atteso": rango})
        fedelta = []
        for pagina_pdf, citazione in citazioni.items():
            hit = assistente.indice.cerca_pagina(veicolo, collezione, pagina_pdf)
            fedelta.append({"pagina_pdf": pagina_pdf, "citazione": citazione,
                            "presente": _citazione_valida(hit, citazione)})
        report[nome] = {
            "estrattore": estrattore, "strategia": strategia, "collezione": collezione,
            "nuovi_embedding": aggiunti, "preparazione_secondi": preparazione,
            "chunk": assistente.indice.store.get_client().count(collezione, exact=True).count,
            "casi": len(casi),
            "hit_at_1": sum(r["rango_atteso"] == 1 for r in risultati),
            "hit_at_3": sum(r["rango_atteso"] is not None and r["rango_atteso"] <= 3 for r in risultati),
            "hit_at_10": sum(r["rango_atteso"] is not None for r in risultati),
            "citazioni_fedeli": sum(r["presente"] for r in fedelta),
            "verifiche_testo": fedelta, "risultati": risultati,
            "metodo": "Query utente senza riscrittura, stessi k e domande. Le metriche misurano il recupero, non la risposta dell'agente.",
        }
        destinazione.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{nome}: hit@3 {report[nome]['hit_at_3']}/{len(casi)}, "
              f"hit@10 {report[nome]['hit_at_10']}/{len(casi)}, citazioni {report[nome]['citazioni_fedeli']}/3", flush=True)


if __name__ == "__main__":
    main()
