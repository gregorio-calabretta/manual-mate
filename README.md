# Assistente per gli avvisi sul cruscotto

Manual Mate cerca nel testo dei manuali di **Ford Focus (CEW)**, edizione 09/2014 per veicoli prodotti dal 08/09/2014 al 15/02/2015, **Honda Civic Type R**, manuale `3LT40600`, **Audi A3 8V** modello 2019, manuale `8V2012721B` in inglese per il Nord America, e **SEAT Leon 5D / Sportstourer**, manuale `5FA012750BT`, edizione italiana 11/2021. Mostra il passaggio originale e cita il numero stampato, quando disponibile, e la posizione nel PDF.

## Avvio su Windows

Da PowerShell, dentro `Progetto FNC`, con Python 3.10–3.13:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 main.py --verifica-manuali
```

I PDF vanno nella cartella `manuali uso e manutenzione auto` accanto a `Progetto FNC`. Per usare un’altra cartella, imposta `MANUALI_DIR` oppure passa `--manuali 'C:\percorso\manuali'`. I nomi dei file attesi sono in `catalogo.py`.

Per avviare l’agente, copia `.env.example` in `.env` e inserisci la tua chiave in `OPENAI_API_KEY`. Puoi anche impostare la variabile d’ambiente direttamente. L’agente usa `gpt-6-luna` per impostazione predefinita. Se hai un `.env` da una versione precedente, aggiorna `OPENAI_MODEL=gpt-6-luna` per usare lo stesso modello. Le richieste al modello e gli embedding usano l’API OpenAI e possono avere un costo. L’API riceve le domande e gli estratti indicizzati dei manuali.

Se hai già la chiave nel file locale `apikey per openai.txt`, puoi caricarla nella sessione PowerShell corrente:

```powershell
$env:OPENAI_API_KEY = (Get-Content -Raw -LiteralPath 'apikey per openai.txt').Trim()
```

Avvia Docker Desktop. La prima volta prepara l’indice, poi avvia l’assistente:

```powershell
docker compose -f osservabilita/compose.yaml up -d --wait qdrant
.\.venv\Scripts\python.exe -X utf8 main.py --indicizza
.\.venv\Scripts\python.exe -X utf8 main.py
```

Qdrant salva testo e vettori nel volume Docker `qdrant_data`. Puoi chiudere l’app o fermare lo stack con `docker compose -f osservabilita/compose.yaml down` e riavviarlo senza rifare gli embedding dei PDF. Per consultare l’indice apri la [dashboard Qdrant](http://localhost:16333/dashboard).

Rilancia `--indicizza` quando cambia il PDF, il modello di embedding o la configurazione dei chunk. A contenuto invariato vedrai `indice riusato, nessun embedding dei manuali`. Per aggiornare una sola auto usa, per esempio, `--indicizza --veicolo civic`. Qdrant conserva le versioni precedenti nel volume. Il nome stabile `manuali_civic` punta alla versione attiva e cambia solo quando il caricamento di quella nuova è riuscito.

L’estrazione legge lo strato testuale dei PDF. L’indicizzazione segnala le eventuali pagine senza testo estraibile. Per simboli, tabelle impaginate e illustrazioni consulta la pagina originale riportata nella risposta.

Il catalogo definisce anche `estrattore_pdf` e `strategia_chunk` per ogni libretto. Gli estrattori disponibili sono `pypdf`, `pdfium` e `docling`; le strategie sono `sottosezioni`, `pagina` e `ricorsivo`. La Leon usa Docling e il RecursiveSplitter di Datapizza, con dimensione 1.024 caratteri e overlap 0. Cambiare questi valori richiede una nuova indicizzazione. Docling conserva il documento strutturato nella cartella locale `.cache_ingestione`, esclusa da Git. I riferimenti mantengono la pagina stampata e la posizione nel PDF.

Per ripetere il confronto sperimentale della Leon, con Qdrant già avviato:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 confronta_ingestione.py
```

Il confronto prepara collezioni distinte e salva `report_confronto_ingestione.json`. La preparazione di un indice è separata dalla sua attivazione nell’app. Il diario `SPERIMENTAZIONE_RAG.md` riporta i risultati e il profilo scelto.

Inizia con una domanda o indica il modello dell’auto. Controlla che l’edizione indicata sia quella del tuo manuale. Usa `:auto` per iniziare una conversazione su un altro veicolo e `:esci` per terminare. Per provare una singola domanda con il manuale già selezionato:

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py --veicolo civic --domanda 'Pressione olio motore bassa'
```

## Interfaccia Streamlit

Con la chiave configurata e i manuali già indicizzati in Qdrant, avvia l’interfaccia dalla cartella del progetto:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app_streamlit.py
```

Apri [Manual Mate nel browser](http://localhost:8501) e fai subito la domanda. Se scrivi «Dove si trova la scatola dei fusibili?», la chat ti chiede di quale auto si tratta. Rispondi «Ford Focus» e riprende la domanda iniziale. Puoi anche indicare il modello nel primo messaggio. Il nome e l’edizione del libretto in uso sono visibili sopra la chat.

Puoi iniziare con «Cosa sai fare?» e vedere quali libretti puoi consultare. Per cambiare libretto, scrivi il nome del veicolo nella conversazione. I chiarimenti tecnici appartengono all’auto a cui si riferiscono. Quando può riassumere l’informazione, la chat risponde in italiano e rende disponibile l’estratto originale sotto la risposta, anche se il libretto dell’Audi A3 8V è in inglese. La chat indica la pagina della fonte o segnala quando i passaggi recuperati non bastano.

Streamlit pubblica le metriche per Prometheus e invia le tracce a Phoenix. Avvia tutti i servizi Docker della sezione **Osservabilità**, poi apri la chat e invia un messaggio. Anche i saluti e i chiarimenti sul modello producono una traccia del turno. Le chiamate agli strumenti compaiono quando l’agente consulta un manuale. Puoi disattivare la pubblicazione nel frontend con `MANUAL_MATE_OSSERVABILITA=false` in `.env`. Streamlit e la CLI con `--osservabilita` usano la stessa porta `18000`, quindi avviali con le metriche una modalità alla volta.

## Prove per la demo

Le pagine nella tabella sono quelle stampate nei manuali.

| Veicolo | Domanda o messaggio | Esito atteso |
| --- | --- | --- |
| `focus` | Mi si è accesa la spia dell’olio | Estratto «Spia olio motore», p. 80 |
| `civic` | Mi si è accesa la spia dell’olio | Domanda di chiarimento, senza ricerca |
| `civic` | Pressione olio motore bassa | Estratto sulla pressione, p. 623 |
| `civic` | Livello olio motore basso | Estratto sul livello, p. 629 |
| `jazz` | Mi si è accesa la spia dell’olio | Veicolo fuori catalogo, senza chiamate al modello o ricerca |

I test usano i PDF e Qdrant locale con risposte dell’API simulate. Uno dei test riapre un indice su disco e verifica che la ricerca invii al modello di embedding solo la query. Per eseguirli:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

## Valutazione con OpenAI e Qdrant

`queries.json` è il *gold set*, cioè il file con le domande e gli esiti attesi. Dopo aver avviato Qdrant e indicizzato i manuali, esegui:

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py --valuta
```

Il comando usa l’API OpenAI ed esegue i 75 casi definiti in `queries.json`. Verifica 24 gruppi di domande con formulazioni diverse. Include conversazioni di più turni, per esempio una domanda sui fusibili seguita dal modello dell’auto. I test locali verificano che le evidenze attese compaiano nelle pagine originali dei PDF.

Per i casi con `criterio_risposta`, una chiamata separata al modello valuta il significato della risposta effettivamente mostrata. Tiene conto della domanda e accetta sinonimi come «pila» e «batteria». Per «che pila serve?» deve comparire la sigla corretta. Per «va a batteria?» è sufficiente una conferma chiara. Il programma controlla separatamente la pagina citata e l’esito dei turni. Il giudizio del modello è indicativo e il report salva la motivazione per poterla riesaminare.

Il file `report_valutazione.json` registra il testo visibile, le fonti recuperate, la citazione, il giudizio sul contenuto e i risultati per gruppo di domande. Un gruppo è completo quando ogni formulazione supera la prova. La metrica `hit@1` indica quante volte la fonte attesa è il primo risultato della ricerca inviata a Qdrant. Il comando restituisce codice `1` se almeno un caso fallisce e salva comunque il report della valutazione completata. Puoi aggiungere `--lavoratori 4` per eseguire più casi insieme. Per confrontare la latenza usa lo stesso numero di lavoratori in entrambi i giri.

I parametri di partenza in `config.py` sono `CHUNK_MAX_CHAR=1024`, `CHUNK_OVERLAP=0` e `TOP_K=10`. La suddivisione segue il profilo del libretto nel catalogo. Ogni chunk conserva il riferimento alla propria pagina PDF. Modificare il metodo di chunking o i primi due parametri richiede `--indicizza`. La ricerca generale può includere un passaggio pertinente di una pagina contigua, quando condivide la stessa sottosezione. Può inoltre completare le prime tre pagine distinte con gli altri chunk già in Qdrant. Per le domande composte l’agente può lanciare due ricerche e usare fino a tre fonti nella stessa risposta. Il programma associa ogni frase al suo riferimento dopo avere verificato la citazione letterale.

Per ripetere le prove più difficili con 5 e 8 risultati per ricerca:

```powershell
$env:RAG_TOP_K = '5'
.\.venv\Scripts\python.exe -X utf8 main.py --stress --lavoratori 3
$env:RAG_TOP_K = '10'
.\.venv\Scripts\python.exe -X utf8 main.py --stress --lavoratori 3
Remove-Item Env:RAG_TOP_K
```

I risultati di questi comandi finiscono in `report_stress_k5.json` e `report_stress_k10.json`. I due giri usano gli stessi casi in `queries_stress.json` e riusano gli embedding. Un codice di uscita `1` indica che almeno un caso è fallito. I report registrano il modello usato. Nei report storici, il confronto salvato in `report_stress_luna_k5.json` usa lo stesso indice e lo stesso valutatore (`gpt-4o-mini`) del giro `report_stress_k5.json`.

Per alcune richieste verificate, come il verso della pila delle due chiavi Focus e la posizione di entrambe le scatole dei fusibili Civic, la risposta consulta direttamente le pagine corrispondenti nell’indice e controlla che contengano i dettagli attesi. Se sulla Focus manca la versione della chiave, chiede quale sia prima di indicare l’orientamento.

La [mappa di copertura](COPERTURA.md) elenca gli argomenti con almeno una prova e quelli da verificare. `--copertura` esegue il campione indipendente e salva `report_copertura.json`. Quando il primo tentativo non produce una citazione verificabile, l’agente può riesaminare i passaggi già recuperati e correggere una volta le citazioni respinte. Gli output strutturati assenti o invalidi hanno un solo tentativo aggiuntivo con più spazio. Se il libretto sostiene solo una parte della risposta, indica anche quale dato resta indeterminato. I casi che attendono un limite vengono valutati sul contenuto anche quando la risposta include una fonte documentale.

La [sperimentazione del recupero](SPERIMENTAZIONE_RAG.md) raccoglie i confronti dei parametri, il passaggio alle sottosezioni e i casi ancora aperti. Le 72 domande dei due confronti sul chunking sono in [queries_chunking.json](queries_chunking.json). Il test finale ha un campione separato di [60 domande](queries_finale.json) e il relativo [report](report_finale.json).

## Osservabilità

Avvia Docker Desktop. Completa l’indicizzazione iniziale seguendo la sezione **Avvio su Windows**, quindi esegui:

```powershell
docker compose -f osservabilita/compose.yaml up -d
.\.venv\Scripts\python.exe -X utf8 main.py --osservabilita
```

Tieni aperto il terminale dell’assistente durante la demo. [Phoenix](http://localhost:16006) mostra gli span dell’agente, dei tool e del retrieval. [Grafana](http://localhost:13000/d/manuali-auto) mostra richieste per esito, latenza e chiamate agli strumenti. [Prometheus](http://localhost:19090/targets) raccoglie le metriche ogni cinque secondi. Per vedere la latenza media in Grafana, manda più richieste lasciando passare almeno due rilevazioni. Per fermare lo stack:

```powershell
docker compose -f osservabilita/compose.yaml down
```

## Come funziona

- `catalogo.py` descrive le edizioni e mantiene i passaggi già verificati per gli avvisi dell’olio. `corpus.py` estrae il testo dei PDF e crea i chunk a partire dai titoli delle sottosezioni, conservando i riferimenti alla pagina.
- `indice.py` usa il vector store Qdrant di Datapizza. L’ingestione salva i passaggi e i relativi embedding, mentre la ricerca calcola l’embedding della query e legge testo e metadati dalla collezione attiva del veicolo.
- `assistente.py` usa `datapizza-ai` 0.1.0 per l’agente. L’agente può chiedere un chiarimento, cercare nei documenti o selezionare una fonte recuperata.
- Il codice pubblica l’estratto solo da una fonte recuperata per il veicolo e l’edizione selezionati. Per gli avvisi riconosciuti verifica anche l’identificativo della sezione già controllata. Per le altre domande verifica che le parole citate dall’agente compaiano nel passaggio originale.
- I riferimenti del corso sono S07 per la RAG, S11 per i tool e l’osservabilità e S15 per il controllo di accesso alle fonti e la verifica dei risultati.
