import argparse
import os
from pathlib import Path

from runtime import ROOT, carica_configurazione, crea_assistente


def main() -> int:
    from catalogo import CATALOGO, leggi_passaggi

    carica_configurazione()
    desktop = ROOT.parent / "manuali uso e manutenzione auto"
    parser = argparse.ArgumentParser(description="Consulta il manuale per gli avvisi olio motore.")
    parser.add_argument("--manuali", type=Path, default=Path(os.getenv("MANUALI_DIR") or desktop))
    parser.add_argument("--veicolo", help="Identificativo del manuale: focus o civic.")
    modalita = parser.add_mutually_exclusive_group()
    modalita.add_argument("--domanda", help="Esegui una singola richiesta e termina.")
    modalita.add_argument("--verifica-manuali", action="store_true", help="Verifica i PDF localmente, senza API.")
    modalita.add_argument("--indicizza", action="store_true", help="Prepara o aggiorna l'indice Qdrant dei manuali.")
    modalita.add_argument("--valuta", action="store_true", help="Esegui queries.json e salva il report della valutazione.")
    parser.add_argument("--osservabilita", action="store_true", help="Attiva trace OTLP e metriche su porta 18000.")
    args = parser.parse_args()

    veicolo_id = args.veicolo.strip().casefold() if args.veicolo else None
    if args.indicizza and veicolo_id is not None and veicolo_id not in CATALOGO:
        parser.error("Per indicizzare, scegli --veicolo focus o --veicolo civic.")
    if args.valuta and veicolo_id is not None:
        parser.error("--valuta usa i veicoli definiti in queries.json.")

    # La verifica dei PDF si può eseguire prima di configurare OpenAI e avviare Docker.
    if args.verifica_manuali:
        try:
            for veicolo in CATALOGO.values():
                leggi_passaggi(args.manuali, veicolo)
                for avviso in veicolo.avvisi:
                    print(f"OK | {veicolo.nome} | {avviso.titolo} | p. {avviso.pagina} (PDF p. {avviso.pagina_pdf})")
        except (OSError, ValueError) as errore:
            parser.exit(1, f"Verifica manuali fallita: {errore}\n")
        return 0

    if args.domanda and not args.veicolo:
        parser.error("--domanda richiede --veicolo.")
    chiave = os.getenv("OPENAI_API_KEY", "").strip()
    if not chiave:
        parser.error("Imposta OPENAI_API_KEY nella variabile d'ambiente o nel file .env.")

    # Come in S11, prepara il provider OTel prima delle chiamate Datapizza.
    from osservabilita import avvia_osservabilita

    provider = None
    if args.osservabilita:
        provider = avvia_osservabilita(18000, "http://localhost:16006/v1/traces")

    from openai import APIError
    from qdrant_client.http.exceptions import ApiException

    try:
        assistente = crea_assistente(chiave)
        # L'indicizzazione si avvia esplicitamente. Le domande riusano la collezione già pronta.
        if args.indicizza:
            veicoli = CATALOGO.values() if veicolo_id is None else [CATALOGO[veicolo_id]]
            for veicolo in veicoli:
                aggiunti = assistente.indice.indicizza(args.manuali, veicolo)
                esito = f"{aggiunti} passaggi indicizzati" if aggiunti else "indice riusato, nessun embedding dei manuali"
                print(f"{veicolo.nome}: {esito}.")
            return 0

        if args.valuta:
            from valutazione import valuta

            return 0 if valuta(assistente, ROOT / "queries.json", ROOT / "report_valutazione.json") else 1

        if args.domanda:
            risposta = assistente.rispondi(veicolo_id or "", args.domanda)
            print(risposta.testo)
            if risposta.esito == "indice_assente":
                return 1
            return 0

        print("Manuali disponibili")
        for codice, veicolo in CATALOGO.items():
            print(f"  {codice}: {veicolo.nome} ({veicolo.edizione})")
        codice = (args.veicolo or input("Quale manuale si applica alla tua auto? ")).strip().casefold()
        print("Comandi disponibili: :auto per cambiare veicolo, :esci per terminare.")
        contesto = ()
        while True:
            domanda = input("\nDescrivi il problema o rispondi al chiarimento: ").strip()
            if domanda == ":esci":
                return 0
            if domanda == ":auto":
                codice = input("Identificativo del manuale (focus / civic): ").strip().casefold()
                contesto = ()
            elif domanda:
                risposta = assistente.rispondi(codice, domanda, contesto=contesto)
                print(f"\n{risposta.testo}")
                contesto = (*contesto, domanda)[-2:] if risposta.esito == "chiarimento" else ()
    except (EOFError, KeyboardInterrupt):
        return 0
    except APIError as errore:
        parser.exit(1, f"Chiamata OpenAI fallita ({type(errore).__name__}). Verifica rete, chiave e quota API.\n")
    except ApiException as errore:
        parser.exit(1, f"Errore Qdrant. Verifica Docker e il servizio qdrant: {errore}\n")
    except (OSError, ValueError) as errore:
        parser.exit(1, f"Impossibile completare la richiesta: {errore}\n")
    finally:
        if provider is not None:
            provider.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
