# Manual Mate

Manual Mate è un assistente conversazionale che cerca informazioni nei libretti di uso e manutenzione delle auto. L'utente descrive un problema o fa una domanda; l'assistente individua il manuale, chiede eventuali chiarimenti e risponde indicando le pagine utilizzate. Se i passaggi consultati non bastano, comunica il limite senza inventare il dato.

L'interfaccia è realizzata con Streamlit. L'agente e la ricerca documentale usano Datapizza, OpenAI e Qdrant; Phoenix, Prometheus e Grafana permettono di osservare il funzionamento dell'applicazione.

## Manuali disponibili

| Identificativo | Veicolo | Edizione | File PDF atteso |
| --- | --- | --- | --- |
| `focus` | Ford Focus (CEW) | 09/2014, produzione 08/09/2014–15/02/2015 | `ITITA_CG3630_Focus_og_201409.pdf` |
| `civic` | Honda Civic Type R | 2023, `3LT40600`, italiano | `23 CIVIC TYPE R JSS (KE KG)-3LT40600_IT_web.pdf` |
| `audi` | Audi A3 8V | 2019, `8V2012721B`, Nord America, inglese | `audi a3 8v 2019.pdf` |
| `leon` | SEAT Leon 5D / Sportstourer | 11/2021, `5FA012750BT`, italiano | `SEAT_LEON_11_21_IT.pdf` |

I PDF si forniscono localmente. La corrispondenza tra modello, edizione e file è definita in `catalogo.py`; una risposta del manuale nordamericano, per esempio, non garantisce l'applicabilità a una variante di un altro mercato.

## Installazione

Servono Python 3.10–3.13, Docker Desktop con Docker Compose e una chiave API OpenAI. Dalla cartella del repository, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

La copia di `.env.example` serve alla prima configurazione; se `.env` esiste già, usa quello. Imposta al suo interno:

```dotenv
OPENAI_API_KEY=la_tua_chiave
OPENAI_MODEL=gpt-6-luna
MANUALI_DIR=C:/percorso/manuali
```

`OPENAI_MODEL` deve indicare un modello disponibile al proprio account e compatibile con tool e output strutturati. Il valore predefinito del progetto è `gpt-6-luna`. Gli embedding usano `text-embedding-3-small`.

Metti nella cartella indicata i PDF con i nomi della tabella. Se `MANUALI_DIR` è vuoto, l'app cerca una cartella chiamata `manuali uso e manutenzione auto` accanto alla cartella del repository. La CLI accetta anche `--manuali "C:\percorso\manuali"`.

La chiave resta nel file locale `.env`, escluso da Git. Le chiamate a OpenAI richiedono una connessione e consumano API: durante l'indicizzazione vengono inviati i testi da convertire in vettori; durante le domande vengono inviati query, contesto conversazionale e passaggi recuperati.

## Prima indicizzazione

Avvia Docker Desktop, poi esegui:

```powershell
docker compose -f osservabilita/compose.yaml up -d --wait
.\.venv\Scripts\python.exe -X utf8 main.py --verifica-manuali
.\.venv\Scripts\python.exe -X utf8 main.py --indicizza
```

`--verifica-manuali` controlla che i file configurati siano PDF leggibili e non vuoti, senza chiamare OpenAI; non certifica automaticamente che il contenuto corrisponda all’edizione dichiarata. `--indicizza` estrae i testi, crea i chunk, calcola gli embedding e carica i dati in Qdrant. La prima estrazione con Docling può richiedere tempo e scaricare i modelli necessari; il documento strutturato viene riusato dalla cache locale `.cache_ingestione`.

Qdrant conserva i dati nel volume Docker `qdrant_data`. Le domande successive riusano gli embedding dei documenti: viene calcolato solo il vettore della query. L'indice è versionato in base a testo, metadati, configurazione e modello di embedding; l'alias del manuale viene aggiornato solo dopo aver verificato il caricamento completo.

Riesegui l'indicizzazione quando cambiano i PDF, il modello di embedding o il profilo di suddivisione. Puoi aggiornare un solo manuale:

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py --indicizza --veicolo leon
```

Se il contenuto non è cambiato, la collezione completa viene riusata senza nuovi embedding dei documenti.

## Avvio dell'interfaccia

Con i manuali indicizzati:

```powershell
docker compose -f osservabilita/compose.yaml up -d --wait
.\.venv\Scripts\python.exe -m streamlit run app_streamlit.py
```

Apri [Manual Mate](http://localhost:8501). Puoi iniziare con «Cosa sai fare?», indicare il modello nella domanda oppure rispondere al chiarimento sull'auto. Per esempio:

- «Nella Ford Focus, che cosa fa la modalità automatica del climatizzatore?»
- «Quanto consuma la Focus 1.0 EcoBoost nel ciclo combinato?»
- «Dove sono i fusibili nell'abitacolo della Seat Leon?»
- «E nella Honda Civic Type R?»

La chat mostra il libretto in uso, la risposta in italiano, gli estratti originali e i riferimenti alle pagine. Il numero stampato nel manuale e la posizione nel PDF sono distinti. Il pulsante **Nuova conversazione** azzera il contesto.

Per chiudere Streamlit usa `Ctrl+C`. Puoi fermare i servizi mantenendo i volumi con:

```powershell
docker compose -f osservabilita/compose.yaml stop
```

## Uso da terminale

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py
.\.venv\Scripts\python.exe -X utf8 main.py --veicolo focus --domanda "Che cosa fa MyKey?"
.\.venv\Scripts\python.exe -X utf8 main.py --help
```

Nella conversazione interattiva `:auto` azzera la selezione e `:esci` termina il programma. `--osservabilita` attiva tracce e metriche anche nella CLI.

## Come funziona

1. **Preparazione dei documenti.** L'estrattore legge il testo del PDF conservando provenienza e numerazione. I profili attuali usano pypdf per Focus, Civic e Audi; per la Leon usano Docling, che mantiene anche struttura e tabelle.
2. **Chunking ed embedding.** Il testo viene suddiviso per pagina e sottosezione; il profilo Leon usa il `RecursiveSplitter` di Datapizza sui paragrafi strutturati. Ogni chunk conserva veicolo, edizione, file e pagina. Gli embedding rappresentano il contenuto per la ricerca semantica in Qdrant.
3. **Conversazione.** Il programma riconosce modello ed edizione e mantiene un contesto limitato. Per un richiamo a un'altra auto ricostruisce la domanda generale, eliminando i dettagli propri della vettura precedente prima della nuova consultazione.
4. **Agente.** Un agente Datapizza decide se chiedere un chiarimento, cercare nel manuale, citare una o più fonti oppure segnalare un limite. Per domande composte può formulare fino a tre ricerche distinte.
5. **Verifica della risposta.** Il codice controlla l'appartenenza delle fonti al manuale e la presenza letterale delle citazioni. Una chiamata strutturata verifica poi la sintesi, le condizioni e i dati necessari. Un riesame limitato può correggere citazioni o recuperare una risposta dalle fonti disponibili. Se la verifica non riesce, il programma comunica il limite.

Questo approccio è una **RAG**, cioè una generazione preceduta dal recupero di documenti. L'agente sceglie gli strumenti; i controlli in Python vincolano le fonti e la costruzione della risposta. Tutte le domande documentali seguono lo stesso percorso: non ci sono risposte predefinite, pagine privilegiate o riconoscitori di argomenti legati a singoli modelli.

Il catalogo mantiene metadati e profili di lettura: lingua, nomi dei file, formato delle intestazioni e numerazione delle pagine. Queste impostazioni descrivono come leggere il PDF, senza contenere valori o istruzioni da restituire all’utente. I titoli su più righe vengono ricomposti conservando anche le condizioni intermedie.

I prompt sono centralizzati in `prompt.py`: istruzioni dell'agente, ricostruzione della domanda al cambio di auto, riesame e verifica della sintesi. Gli schemi Pydantic descrivono gli output strutturati. La verifica non è una garanzia assoluta: una citazione autentica può comunque essere interpretata male, perciò l'estratto originale resta consultabile.

## Configurazione

| Impostazione | Valore predefinito | Dove si configura |
| --- | --- | --- |
| Modello conversazionale | `gpt-6-luna` | `OPENAI_MODEL` in `.env` |
| Modello di embedding | `text-embedding-3-small` | `runtime.py` |
| Qdrant | `127.0.0.1:16333` | `QDRANT_HOST`, `QDRANT_PORT` in `.env` |
| Risultati per ricerca | `10` | `RAG_TOP_K` in `.env` |
| Dimensione di riferimento dei chunk | `1024` caratteri | `CHUNK_MAX_CHAR` in `config.py` |
| Sovrapposizione | `0` | `CHUNK_OVERLAP` in `config.py` |
| Query distinte per richiesta | Massimo `3` | `MAX_QUERY_RICERCA` in `config.py` |
| Contesto conversazionale | Fino a `4` elementi | `MAX_TURNI_CONTESTO` in `config.py` |
| Osservabilità Streamlit | Attiva | `MANUAL_MATE_OSSERVABILITA` in `.env` |

La dimensione effettiva dei chunk dipende dal profilo e dalla struttura del documento: 1024 caratteri non sono una garanzia di lunghezza identica per ogni tabella o blocco. Cambiare `RAG_TOP_K` riguarda il recupero e non richiede di ricreare gli embedding dei PDF.

## Domande di prova e valutazione

`queries.json` contiene il campione di verifica: **50 scenari, espansi in 75 casi** includendo le formulazioni alternative. Ogni scenario indica domanda, veicolo, esito atteso e, quando applicabile, pagine, evidenze e criterio semantico. Può contenere anche i turni precedenti di una conversazione.

Con chiave configurata, Qdrant avviato e manuali indicizzati:

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py --valuta
```

Per eseguire più casi contemporaneamente:

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py --valuta --lavoratori 2
```

Il comando stampa i casi superati e il totale e salva `report_valutazione.json` localmente. Il report è escluso da Git. La valutazione controlla veicolo, esiti, pagine citate, evidenze e, per i casi dotati di criterio, il significato della risposta mostrata. Il valutatore usa OpenAI e ammette sinonimi e formulazioni equivalenti. Il suo giudizio va riesaminato quando appare dubbio.

Le metriche distinguono la presenza della fonte al primo posto (`hit@1`), la correttezza della citazione e la coerenza della risposta. Il comando termina con codice `0` se tutti i casi passano, `1` se almeno uno fallisce. La valutazione riguarda il campione elencato e non misura la copertura totale dei libretti o un'affidabilità generale garantita.

## Osservabilità

| Servizio | Interfaccia | Utilizzo |
| --- | --- | --- |
| Phoenix | [localhost:16006](http://localhost:16006) | Tracce dei turni, agente, strumenti, recupero e verifiche |
| Grafana | [Dashboard Manual Mate](http://localhost:13000/d/manuali-auto) | Richieste per esito, latenza e utilizzo degli strumenti |
| Prometheus | [Target di raccolta](http://localhost:19090/targets) | Stato della raccolta delle metriche |
| Qdrant | [Dashboard](http://localhost:16333/dashboard) | Collezioni, alias e punti indicizzati |

Streamlit pubblica le metriche sulla porta `18000`; Prometheus le raccoglie ogni cinque secondi. Le tracce sono inviate a Phoenix via OpenTelemetry. Per vedere le metriche invia alcuni messaggi e lascia trascorrere più raccolte. Streamlit e la CLI con `--osservabilita` condividono la porta `18000`: avviane una sola con l'osservabilità attiva.

## Struttura del codice

| File | Responsabilità |
| --- | --- |
| `app_streamlit.py`, `main.py` | Interfaccia web e CLI |
| `runtime.py`, `config.py` | Configurazione e costruzione dei componenti |
| `catalogo.py` | Veicoli, edizioni, file e profili tipografici dei PDF |
| `estrazione.py`, `corpus.py` | Lettura dei documenti, metadati e suddivisione |
| `indice.py`, `recupero.py` | Persistenza, ricerca e completamento delle pagine |
| `conversazione.py`, `intenti.py` | Stato della chat e richiami tra veicoli |
| `assistente.py`, `prompt.py` | Agente, strumenti, istruzioni e controlli |
| `fonti.py`, `strutturati.py` | Modelli di risposta, citazioni e output strutturati |
| `valutazione.py`, `queries.json` | Campione di domande e valutazione dei risultati |
| `osservabilita.py`, `osservabilita/` | Tracing, metriche e servizi Docker |

Il JSON in `osservabilita/grafana/dashboards/` configura la dashboard ed è necessario per il suo caricamento automatico.

## Limiti

Il sistema usa i testi estratti e non interpreta direttamente tutte le illustrazioni. Tabelle complesse, testo OCR, condizioni di applicabilità e richieste con più parti possono portare a risposte incomplete. Alcune informazioni si trovano in documenti separati o dipendono da dati che deve fornire l'utente. «Non trovato nei passaggi consultati» non dimostra che il dato manchi nell'intero manuale.

Le richieste complesse possono richiedere più chiamate al modello e avere tempi di risposta elevati. La pagina originale permette di verificare contenuto e applicabilità delle istruzioni; l'assistente fornisce informazioni documentali, non una diagnosi certa del veicolo.

## Branch del repository

- **`main`** contiene l'applicazione, le configurazioni dei servizi, questo README e il campione `queries.json` con il relativo comando di valutazione.
- **[`dev`](https://github.com/gregorio-calabretta/manual-mate/tree/dev)** conserva la versione completa di sviluppo: test automatici, dataset aggiuntivi, report, confronti e documentazione delle sperimentazioni. Per lavorare con quei materiali, usa `git switch dev` con una cartella di lavoro pulita.

I report generati localmente su `main` restano esclusi dal versionamento. Le modifiche sviluppate su `dev` vengono integrate in `main` insieme alle configurazioni e ai dati di verifica necessari.
