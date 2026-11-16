# Assistente per gli avvisi sul cruscotto

Manual Mate cerca nel testo dei manuali di **Ford Focus (CEW)**, edizione 09/2014 per veicoli prodotti dal 08/09/2014 al 15/02/2015, e **Honda Civic Type R**, manuale `3LT40600`. Mostra il passaggio originale e cita il numero stampato, quando disponibile, e la posizione nel PDF.

## Avvio su Windows

Da PowerShell, dentro `Progetto FNC`, con Python 3.10–3.13:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 main.py --verifica-manuali
```

I due PDF vanno nella cartella `manuali uso e manutenzione auto` accanto a `Progetto FNC`. Per usare un’altra cartella, imposta `MANUALI_DIR` oppure passa `--manuali 'C:\percorso\manuali'`. I nomi dei due file attesi sono in `catalogo.py`.

Per avviare l’agente, copia `.env.example` in `.env` e inserisci la tua chiave in `OPENAI_API_KEY`. Puoi anche impostare la variabile d’ambiente direttamente. Le richieste al modello e gli embedding usano l’API OpenAI e possono avere un costo. L’API riceve le domande e gli estratti indicizzati dei manuali.

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

Seleziona `focus` o `civic` dopo aver verificato che l’edizione indicata sia quella del tuo manuale. Usa `:auto` per cambiare veicolo e `:esci` per terminare. Per provare una singola domanda:

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py --veicolo civic --domanda 'Pressione olio motore bassa'
```

## Interfaccia Streamlit

Con la chiave configurata e i manuali già indicizzati in Qdrant, avvia l’interfaccia dalla cartella del progetto:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app_streamlit.py
```

Apri [Manual Mate nel browser](http://localhost:8501) e fai subito la domanda. Se scrivi «Dove si trova la scatola dei fusibili?», la chat ti chiede di quale auto si tratta. Rispondi «Ford Focus» e riprende la domanda iniziale. Puoi anche indicare il modello nel primo messaggio. Il nome e l’edizione del libretto in uso sono visibili sopra la chat.

Per passare all’altro libretto, scrivi il nome del veicolo nella conversazione. I chiarimenti tecnici appartengono all’auto a cui si riferiscono. Quando trova una fonte pertinente, la chat la mostra con la pagina. Quando i passaggi recuperati non bastano, lo dice.

Per inviare anche le richieste web a Phoenix e Grafana, avvia lo stack della sezione **Osservabilità** e imposta `MANUAL_MATE_OSSERVABILITA=true` in `.env` prima di avviare Streamlit. Usa un solo processo con le metriche attive alla volta, perché sia la CLI sia Streamlit le espongono sulla porta `18000`.

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

Il comando usa l’API OpenAI e salva `report_valutazione.json` con l’esito, le fonti recuperate in ordine, la fonte citata e la latenza di ogni caso. Il report separa le ricerche avviate, `hit@1` sulle ricerche effettivamente eseguite, le citazioni esatte, i chiarimenti, i blocchi e le astensioni. La metrica `hit@1` riguarda la query effettivamente inviata a Qdrant dall’agente. Il comando restituisce codice `1` se almeno un caso fallisce e salva comunque il report della valutazione completata.

I parametri di partenza in `config.py` sono `CHUNK_MAX_CHAR=1024`, `CHUNK_OVERLAP=128` e `TOP_K=5`. Modificare i primi due richiede `--indicizza`. Nelle ricerche generali completiamo il primo risultato con il testo degli altri chunk della stessa pagina. Questa operazione riusa i dati Qdrant e conserva il ranking. Per provare solo il numero di risultati, imposta `$env:RAG_TOP_K = '3'` prima di eseguire `--valuta`. Conserva il report prima di passare alla configurazione successiva, perché ogni valutazione lo sostituisce.

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

- `catalogo.py` descrive le edizioni e mantiene i passaggi già verificati per gli avvisi dell’olio. `corpus.py` estrae il testo dei PDF pagina per pagina e usa `RecursiveSplitter` di Datapizza per creare i chunk con i riferimenti al manuale.
- `indice.py` usa il vector store Qdrant di Datapizza. L’ingestione salva i passaggi e i relativi embedding, mentre la ricerca calcola l’embedding della query e legge testo e metadati dalla collezione attiva del veicolo.
- `assistente.py` usa `datapizza-ai` 0.1.0 per l’agente. L’agente può chiedere un chiarimento, cercare nei documenti o selezionare una fonte recuperata.
- Il codice pubblica l’estratto solo da una fonte recuperata per il veicolo e l’edizione selezionati. Per gli avvisi riconosciuti verifica anche l’identificativo della sezione già controllata. Per le altre domande verifica che le parole citate dall’agente compaiano nel passaggio originale.
- I riferimenti del corso sono S07 per la RAG, S11 per i tool e l’osservabilità e S15 per il controllo di accesso alle fonti e la verifica dei risultati.
