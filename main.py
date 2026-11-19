import argparse
import os
from pathlib import Path

from runtime import ROOT, carica_configurazione, crea_assistente


def main() -> int:
    from catalogo import CATALOGO, verifica_manuale

    carica_configurazione()
    desktop = ROOT.parent / "manuali uso e manutenzione auto"
    codici = " / ".join(CATALOGO)
    parser = argparse.ArgumentParser(description="Consulta il manuale d'uso del veicolo selezionato.")
    parser.add_argument("--manuali", type=Path, default=Path(os.getenv("MANUALI_DIR") or desktop))
    parser.add_argument("--veicolo", help=f"Identificativo del manuale ({codici}).")
    modalita = parser.add_mutually_exclusive_group()
    modalita.add_argument("--domanda", help="Esegui una singola richiesta e termina.")
    modalita.add_argument("--verifica-manuali", action="store_true", help="Verifica i PDF localmente, senza API.")
    modalita.add_argument("--indicizza", action="store_true", help="Prepara o aggiorna l'indice Qdrant dei manuali.")
    modalita.add_argument("--valuta", action="store_true", help="Valuta le domande di queries.json e salva un report locale.")
    parser.add_argument("--lavoratori", type=int, metavar="N", help="Numero di casi di valutazione da eseguire insieme.")
    parser.add_argument("--osservabilita", action="store_true", help="Attiva trace OTLP e metriche su porta 18000.")
    args = parser.parse_args()

    veicolo_id = args.veicolo.strip().casefold() if args.veicolo else None
    if args.indicizza and veicolo_id is not None and veicolo_id not in CATALOGO:
        parser.error(f"Per indicizzare, scegli un valore valido per --veicolo ({codici}).")
    if args.valuta and veicolo_id is not None:
        parser.error("La valutazione usa i veicoli definiti nelle domande di prova.")
    if args.lavoratori is not None and (args.lavoratori < 1 or not args.valuta):
        parser.error("--lavoratori richiede --valuta e un intero positivo.")

    # La verifica dei PDF si può eseguire prima di configurare OpenAI e avviare Docker.
    if args.verifica_manuali:
        try:
            for veicolo in CATALOGO.values():
                pagine = verifica_manuale(args.manuali, veicolo)
                print(f"OK | {veicolo.nome} | {veicolo.edizione} | {pagine} pagine PDF")
        except (OSError, ValueError) as errore:
            parser.exit(1, f"Verifica manuali fallita: {errore}\n")
        return 0

    chiave = os.getenv("OPENAI_API_KEY", "").strip()
    if not chiave:
        parser.error("Imposta OPENAI_API_KEY nella variabile d'ambiente o nel file .env.")

    # Il provider di tracing deve essere pronto prima delle chiamate Datapizza.
    from osservabilita import avvia_osservabilita

    provider = None
    if args.osservabilita:
        provider = avvia_osservabilita(18000, "http://127.0.0.1:16006/v1/traces")

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

            return 0 if valuta(assistente, ROOT / "queries.json", ROOT / "report_valutazione.json",
                               lavoratori=args.lavoratori or 1) else 1

        from conversazione import Conversazione

        conversazione = Conversazione(veicolo_id=veicolo_id)

        def consulta(codice: str, domanda: str, contesto: tuple[str, ...]):
            return assistente.rispondi(codice, domanda, contesto=contesto)

        if args.domanda:
            risposta = conversazione.rispondi(args.domanda, consulta)
            print(risposta.testo_cli)
            if risposta.esito == "indice_assente":
                return 1
            return 0

        print("Ciao, sono Manual Mate. Cosa vuoi sapere?")
        print("Scrivi :auto per ricominciare con un altro veicolo o :esci per terminare.")
        while True:
            domanda = input("\nTu: ").strip()
            if domanda == ":esci":
                return 0
            if domanda == ":auto":
                conversazione = Conversazione()
                print("Dimmi pure quale libretto vuoi consultare.")
            elif domanda:
                risposta = conversazione.rispondi(domanda, consulta)
                print(f"\n{risposta.testo_cli}")
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
