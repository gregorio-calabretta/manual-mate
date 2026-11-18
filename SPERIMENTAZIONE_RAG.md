# Sperimentazione del recupero nei libretti

Manual Mate risponde a domande sui libretti della Ford Focus CEW, della Honda Civic Type R e dell’Audi A3 8V. Il libretto Audi in uso è l’edizione nordamericana in inglese. L’obiettivo delle prove era aumentare le risposte complete e documentate, comprese quelle a domande colloquiali, composte o distribuite su più turni. Se un dato dipende dallo stato effettivo dell’auto o da un’informazione esterna al libretto, la risposta attesa esplicita quel limite.

## Metodo di valutazione

- **Recupero.** Si confronta l’ordine dei chunk restituiti da Qdrant con pagine e passaggi attesi, a query uguale tra le configurazioni. Le prime griglie misuravano la presenza della pagina. La griglia da 36 combinazioni e il confronto sul nuovo chunking hanno controllato anche le frasi attese dove erano già indicate. Per le domande composte si sono cercate entrambe le fonti richieste.
- **Risposta.** Si verifica il contenuto che vede l’utente, incluse le condizioni di allestimento, le unità e le citazioni. Sinonimi e riferimenti alternativi equivalenti sono accettati. Le risposte possono essere complete, parziali o fallite. Nelle ultime griglie un valutatore ha esaminato le risposte senza conoscere la configurazione. I giudizi incoerenti con i criteri sono stati corretti rileggendo le risposte.
- **Conversazioni.** Alcune prove passano da Streamlit e altre richiamano direttamente la stessa logica di agente e conversazione. Si verifica anche che l’assistente riprenda l’argomento dopo un chiarimento. Un’esecuzione diretta dell’agente non costituisce una prova della UI.
- **Confrontabilità.** Le prove a query fissa isolano meglio i parametri di Qdrant. Nelle prove con l’agente, il modello può riformulare la query o citare un altro estratto. I risultati misurano i campioni e le esecuzioni riportate. Le ripetizioni dei casi difficili sono lo stesso campione ripetuto.

Il modello conversazionale delle prove recenti era `gpt-6-luna`, con embedding `text-embedding-3-small`. Gli indici sperimentali erano separati da quelli dell’app. Le misure di recupero e le risposte complete hanno denominatori distinti.

## Riscontri iniziali nella chat

Nel giro di 30 domande in Streamlit, 25 casi sono risultati completi, uno parziale e quattro falliti. Sono state ripetute tre richieste perché la prima trascrizione non conteneva il testo visibile. I casi sono stati verificati confrontando le risposte con le pagine dei libretti.

| Caso | Riscontro e seguito |
|---|---|
| Ford, MyKey | L’app ha detto di non trovare la risposta. Il libretto indica la chiave amministratore a p. 38. In prove successive la chiave è stata citata correttamente anche con `k=5`. |
| Audi, persone nel rimorchio | Il divieto è esplicito a p. 124. Alcune risposte lo hanno omesso anche quando la pagina era nei risultati. Nel confronto successivo tra tecniche di chunking, tutte e quattro le esecuzioni hanno riportato il divieto correttamente. Il risultato era variabile nelle prove precedenti. |
| Audi, MMI e batteria | P. 166 descrive lo spegnimento automatico a motore fermo e batteria scarica. Una risposta successiva sulla percentuale in tempo reale ha spostato il riferimento alla batteria ad alta tensione. Il valore attuale richiede una lettura dell’auto ed eventuali istruzioni per la versione ibrida vanno presentate come condizionali. |
| Audi, ruotino | P. 377 specifica l’uso temporaneo e p. 347 contiene un’indicazione equivalente sull’uso della ruota di scorta. Nel confronto tra tecniche di chunking, tutte e quattro le esecuzioni hanno ricevuto p. 377 tra le prime tre e hanno comunque risposto di non aver trovato l’indicazione. |
| Civic, attrezzi | P. 588 indica il bagagliaio per la versione senza ruotino e p. 589 indica la cassetta sul lato sinistro per quella con ruotino. In una ricerca la pagina 588 era all’ottavo posto. La nuova strategia a `k=10` è riuscita a citare entrambe le pagine nel primo confronto. |
| Ford, rotazione pneumatici | L’intervallo è a p. 247. In un giro nessuna delle tre configurazioni ha recuperato la pagina. Riformulando la domanda, il caso è passato sia con il metodo precedente sia con le sottosezioni. |
| Civic, maniglia interna | P. 168 era arrivata all’agente in tre prove in cui ha comunque risposto «Non ho trovato». La nuova formulazione del caso è passata con tutti i metodi nel confronto successivo. |

Il giro ha confermato anche comportamenti utili. La Focus ha mantenuto il contesto tra la domanda sulla durata di alimentazione della presa da 12 V e quella sulla corrente massima. L’app ha riconosciuto che il chilometraggio attuale e quello dell’ultimo cambio d’olio sono dati della vettura specifica.

## Esperimenti su dimensione, sovrapposizione e risultati

Nella prima diagnosi, i passaggi decisivi erano già interi nei chunk esistenti. Nei casi mirati `k=8` ha migliorato il recupero di alcune fonti, mentre le risposte complete sono passate da 6/8 a 5/8. In particolare, la pagina utile sui sensori Audi era al secondo posto in entrambe le prove e l’agente l’ha usata solo a `k=5`.

### Prime cinque configurazioni

Passaggi attesi recuperati su 37 casi, usando la pagina prevista come riferimento.

| Chunk | Overlap | k=3 | k=5 | k=8 | k=12 |
|---:|---:|---:|---:|---:|---:|
| 1024 | 128 | 31 | 31 | 34 | 34 |
| 768 | 128 | 30 | 31 | 32 | 33 |
| 1536 | 128 | 30 | 32 | 33 | 33 |
| 1024 | 64 | 31 | 32 | 34 | 34 |
| 1024 | 256 | 30 | 32 | 33 | 34 |

Sulle risposte finali, `1024/128/k=5` e `1024/128/k=8` hanno ottenuto 8/12 ciascuno e `1024/64/k=5` ha ottenuto 9/12. I chunk da 768 caratteri erano circa il 31% più numerosi rispetto al riferimento. Quelli da 1536 caratteri erano circa il 27% meno numerosi, con un guadagno di un recupero a `k=5` e una perdita di un recupero a `k=8`.

### Secondo confronto e domande diverse

La ricerca è stata ripetuta su 68 casi con gruppi da 37 e 31 domande. Con `1024/128` si è passati da 58/68 a `k=5` a 64/68 a `k=8`. Il massimo della prova era 65/68 con `896/64/k=10`, misurato solo sul recupero. Sui due giri con l’agente, da 10 domande ciascuno, i risultati sono stati i seguenti.

| Configurazione | Giro 1 | Giro 2 | Totale |
|---|---:|---:|---:|
| 1024 / 128 / k=5 | 7/10 | 8/10 | 15/20 |
| 1024 / 64 / k=5 | 7/10 | 7/10 | 14/20 |
| 896 / 64 / k=8 | 8/10 | 6/10 | 14/20 |

Il vantaggio dell’overlap a 64 del primo test non si è ripetuto. Il passaggio a `k=8` ha migliorato il recupero, con risultati alterni sulle risposte. Per questo motivo, per il giro seguente sono state fissate le domande e i criteri prima di valutare le risposte finali.

### Griglia da 36 combinazioni

Nove combinazioni di chunk e overlap per quattro valori di `k`. Il recupero su 68 casi controllava anche le frasi attese quando disponibili.

| Chunk | Overlap | k=5 | k=6 | k=8 | k=10 |
|---:|---:|---:|---:|---:|---:|
| 1024 | 128 | 58 | 59 | 62 | 63 |
| 896 | 0 | 58 | 58 | 61 | 64 |
| 896 | 64 | 57 | 60 | 63 | 64 |
| 896 | 128 | 59 | 60 | 62 | 62 |
| 1024 | 0 | 59 | 60 | 62 | 62 |
| 1024 | 64 | 58 | 59 | 61 | 62 |
| 1280 | 0 | 57 | 60 | 61 | 61 |
| 1280 | 64 | 58 | 60 | 61 | 62 |
| 1280 | 128 | 57 | 59 | 60 | 61 |

L’agente è stato provato con i tre profili su 36 domande e nuovamente su 12 casi difficili, per 144 risposte.

| Configurazione | Risposte complete su 36 | Ripetizione dei 12 casi |
|---|---:|---:|
| 1024 / 128 / k=5 | 28 | 8 |
| 896 / 0 / k=10 | 29 | 9 |
| 896 / 64 / k=10 | 29 | 10 |

Con la configurazione di riferimento, una risposta sulle modalità di guida della Civic è fallita durante il riesame perché il modello ha restituito JSON incompleto. L’errore conta nel denominatore. Il metodo di chunking in questa griglia era ancora quello per pagina.

## Chunk per sottosezione

La variante sperimentata identifica i titoli di sottosezione nel testo del libretto. Per la Focus sfrutta le intestazioni in maiuscolo, per la Civic i marcatori di sottosezione e per l’Audi righe che hanno la forma di un titolo anche dopo l’OCR. Le sottosezioni lunghe vengono divise privilegiando un confine di frase, con un corpo di circa 1024 caratteri e senza overlap. Ogni chunk mantiene numero di pagina, posizione nel PDF, veicolo ed edizione.

Il recupero può inserire entro il limite `k` un chunk pertinente di una pagina adiacente quando condivide un titolo specifico con uno dei primi risultati. Il passaggio conserva i propri riferimenti. Restano disponibili il completamento delle prime tre pagine distinte e la verifica letterale delle citazioni. La ricerca sugli avvisi dell’olio continua a usare i passaggi verificati del catalogo.

### Primo confronto

Quattro profili, 68 domande per il recupero e 36 per la risposta. Sono state valutate 144 risposte complessive.

| Metodo | k | Recupero | Complete | Parziali | Fallite |
|---|---:|---:|---:|---:|---:|
| Per pagina | 5 | 58/68 | 29 | 0 | 7 |
| Per pagina | 10 | 63/68 | 31 | 2 | 3 |
| Per sottosezione | 5 | 61/68 | 28 | 1 | 7 |
| Per sottosezione | 10 | 63/68 | 33 | 1 | 2 |

Le sottosezioni a `k=10` hanno migliorato i casi su spegnimento dell’MMI, sensori di parcheggio Audi e attrezzi Civic con e senza ruotino. A `k=5` hanno recuperato tre passaggi attesi in più, ma hanno prodotto una risposta completa in meno rispetto al metodo per pagina. La ricerca a query fissa ha guadagnato, tra gli altri, il filtro antipolline Audi e la capacità del serbatoio quattro; ha perso il collare della retromarcia Focus nel relativo caso di recupero. In un altro giro, entrambe le strategie hanno risposto correttamente alla domanda sul collare.

Nel primo confronto, gli errori rimasti con le sottosezioni a `k=10` riguardavano il filtro antipolline e il ruotino Audi. La risposta alla domanda sulla carica in tempo reale era parziale. Anche il precedente metodo a `k=5` ha avuto un errore di JSON incompleto nel riesame, questa volta alla domanda sul clima automatico della Focus.

### Conferma a k=10

Il secondo campione conteneva 36 domande diverse da quelle del primo confronto, 12 per libretto. Il recupero separato usava 27 domande documentali a un turno. Le richieste su dati della singola auto e quelle che dipendevano dai turni precedenti sono state misurate sulle risposte.

| Metodo | Recupero | Complete | Parziali | Fallite |
|---|---:|---:|---:|---:|
| Per pagina | 26/27 | 33 | 1 | 2 |
| Per sottosezione | 25/27 | 35 | 0 | 1 |

- La risposta Audi su presa e tetto ha citato sia il limite della presa sia quello di carico con le sottosezioni. Il metodo per pagina aveva citato solo il tetto.
- La leva fluorescente del portellone Audi è stata spiegata correttamente con le sottosezioni. Con il metodo precedente, l’agente aveva ricevuto p. 368 ma aveva rinunciato a rispondere.
- Sui punti di ancoraggio dei bagagli Audi entrambi i metodi avevano ricevuto p. 64 tra le prime tre pagine e hanno risposto «Non ho trovato». Questo caso rimane aperto.

Le sottosezioni hanno ottenuto due risposte complete in più a parità di `k` in entrambi i confronti. Il numero di chunk dei tre libretti è salito da 3423 a circa 4680, pari al 37% in più. L’aumento si riflette in spazio e lavoro di indicizzazione. I test non hanno misurato separatamente il costo in token e la latenza in produzione. Il 35/36 è il risultato del campione di conferma, con un margine ridotto tra i due metodi.

## Adozione e funzionamento

- `corpus.py` costruisce i chunk per sottosezione conservando i metadati della pagina.
- `indice.py` aggiunge, quando pertinente, una fonte della pagina contigua entro il limite di ricerca. Le collezioni già presenti conservano riferimenti validi. La loro ricerca continua a funzionare anche quando i vecchi chunk non hanno i metadati della sottosezione.
- `config.py` e `.env.example` impostano come valori di partenza `CHUNK_MAX_CHAR=1024`, `CHUNK_OVERLAP=0` e `TOP_K=10`. Una configurazione `RAG_TOP_K` già impostata nell’ambiente prevale sul valore predefinito.
- `main.py --indicizza` costruisce una nuova collezione versionata per libretto. Ciascun alias stabile passa alla nuova collezione a caricamento completo. Le collezioni precedenti restano disponibili. Avviando una seconda volta l’indicizzazione a contenuto invariato si può riusare la stessa versione.

L’indicizzazione persistente è stata completata. Da un nuovo processo è stato verificato che tutti e tre gli alias puntano alle nuove collezioni e che il valore effettivo di `k` è 10. Un confronto fra prototipo e implementazione ha confermato gli stessi testi e riferimenti di pagina per i tre libretti.

| Libretto | Chunk attivi | Pagine PDF con testo | Pagine PDF senza testo estraibile |
|---|---:|---:|---|
| Ford Focus CEW | 1119 | 442/444 | 430, 443 |
| Honda Civic Type R | 1647 | 697/701 | 35, 237, 519, 641 |
| Audi A3 8V | 1914 | 413/414 | 2 |
| Totale | 4680 | 1552/1559 | 7 pagine |

Qdrant ha segnalato una differenza tra la versione del client Python (1.20.0) e il server (1.11.0). In questa esecuzione gli aggiornamenti e la verifica degli alias sono riusciti.

### Verifica dopo l’attivazione

La suite automatica ha passato 35 test, inclusi quelli aggiunti per i confini delle sottosezioni e per il recupero della pagina adiacente. Sono state eseguite anche tre richieste dal test harness di Streamlit con Qdrant e OpenAI reali.

| Domanda | Risposta verificata | Pagine del libretto |
|---|---|---|
| Ford Focus, quale chiave serve per togliere le limitazioni MyKey | Chiave amministratore | 38–40 |
| Honda Civic Type R, dove sono gli attrezzi con e senza ruotino | Bagagliaio in entrambe le versioni, con cassetta sul lato sinistro nella versione con ruotino | 588–589 |
| Audi A3 8V, limite della presa da 12 V e carico sul tetto | 120 W e 75 kg, associati ai componenti corretti | 62, 395 |

Le tre prove hanno verificato le citazioni mostrate in Streamlit. La telemetria era disattivata nel processo di prova, quindi queste richieste non verificano la raccolta su Phoenix e Grafana. Se Streamlit era già aperto prima dell’aggiornamento, riavvialo per ricaricare il codice e la configurazione; le collezioni sono già indicizzate.

## Problemi ancora aperti

1. **La pagina utile arriva, ma la risposta manca.** La diagnosi qui sotto ha individuato e corretto il rifiuto delle citazioni nei casi del ruotino e dell’ancoraggio dei bagagli Audi. La correzione riguarda le differenze tipografiche verificate. Altri casi di rinuncia, come la mancata selezione di un passaggio, vanno diagnosticati separatamente.
2. **La query cambia il risultato.** Domande semanticamente equivalenti possono trovare pagine diverse. Nei casi in cui manca il passaggio, si può testare una seconda ricerca con una riformulazione controllata e confrontarla su parafrasi indipendenti.
3. **L’OCR e le edizioni sono variabili.** L’Audi ha parole unite o spezzate dal riconoscimento del testo. Titoli simili possono indicare versioni diverse dello stesso componente. Le condizioni dell’allestimento e le citazioni devono essere conservate.
4. **Il riesame strutturato può fallire.** È stato osservato JSON incompleto in due prove. Serve verificare come gestire in modo esplicito questo errore senza perdere una risposta già documentata. Il lavoro sul chunking non ha modificato il riesame.

### Diagnosi delle citazioni Audi

Sono state ripetute tre volte ciascuna le domande sul ruotino e sull’ancoraggio dei bagagli, usando l’indice persistente. Le tracce riportavano la query, gli estratti ricevuti dall’agente, gli argomenti di `cita_fonte` o `cita_fonti` e l’esito della verifica in `assistente.py`. In tutti e sei i tentativi, il modello ha provato a citare la fonte pertinente, la verifica l’ha rifiutata e la risposta finale è stata «Non ho trovato».

- **Ruotino, p. 377.** L’estratto divide `short-` e `term` su due righe. Il controllo rimuove il trattino di fine riga e confronta `shortterm` con `short-term`, che il modello restituisce come citazione. In alcune proposte il modello ha anche riunito frasi distanti in un’unica citazione.
- **Bagagli, p. 64.** L’OCR ha trascritto `Use straps` come `Usestraps`. Il modello ha restituito la forma con lo spazio. Alcune proposte aggiungevano virgolette o univano segmenti non consecutivi. Il confronto letterale ha respinto quelle citazioni.
- **Riesame.** Su due tentativi del ruotino, l’agente ha prodotto anche una citazione valida dalla p. 347, ma il riesame ha scartato l’intero gruppo perché un’altra citazione non passava. Fornire al riesame soltanto la pagina attesa non ha risolto il problema per nessuno dei due casi.

La correzione introdotta in `assistente.py` chiede estratti brevi e consecutivi. Il controllo gestisce un trattino a fine riga, le virgolette che racchiudono la citazione e un singolo spazio omesso dall’OCR fra parole alfabetiche. Numeri, segni, unità e ordine del testo continuano a essere verificati. Nel riesame l’agente conserva le frasi con citazioni valide e segnala se non ha verificato tutti i dettagli. Le modifiche non richiedono nuovi embedding o modifiche a Qdrant.

I test di regressione verificano che le differenze tipografiche passino, che citazioni con numeri o unità alterati e frasi non consecutive siano rifiutate, e che il riesame conservi la parte documentata. Nelle prime sei richieste dopo la correzione l’agente ha citato correttamente tutte le fonti attese, senza riesame. In due risposte sul ruotino ha comunque omesso «se necessario» da un’indicazione aggiuntiva sulla sostituzione dello pneumatico. Il prompt è stato quindi aggiornato per limitare i dettagli a quelli utili alla domanda e preservare le condizioni delle istruzioni citate.

Nell’ultimo giro della correzione delle citazioni, tutte e sei le richieste hanno di nuovo citato le pagine pertinenti. Le tre risposte sull’ancoraggio hanno indicato punti di fissaggio e cinghie adatte. Tutte e tre le risposte sul ruotino hanno indicato l’uso temporaneo, ma in due il suggerimento aggiuntivo di sostituire lo pneumatico danneggiato ometteva ancora «se necessario». I due controlli hanno conservato sia il limite di 120 W della presa sia il rifiuto di indicare una percentuale di carica attuale. La suite di quel giro ha passato 37 test automatici.

### Verifica delle sintesi

La verifica letterale conferma che la citazione si trova nella fonte. Una chiamata strutturata successiva confronta le affermazioni della sintesi con i soli estratti citati e produce un esito JSON. Lo schema Pydantic usa `confermata`, `corretta` e `non_verificabile`. In caso di errore della verifica o sintesi non verificabile, restano visibili gli estratti originali e i riferimenti. La chiamata aggiunge latenza alle risposte con sintesi generata. Non è stata misurata la differenza di costo o latenza su un campione ampio.

La prima versione ha lasciato passare una delle due vecchie sintesi del ruotino senza «se necessario». Dopo aver precisato il confronto tra le istruzioni e le loro condizioni, sono state rieseguite le due sintesi originali con le relative fonti, tre volte ciascuna. In cinque casi la condizione è stata ripristinata e in uno è stato rimosso il dettaglio extra. Nelle tre nuove risposte sul ruotino, due hanno conservato la condizione e la terza ha risposto direttamente sull’uso temporaneo. Le tre richieste sui bagagli hanno citato i passaggi pertinenti; i due controlli hanno conservato il limite di 120 W e il limite sulla conoscenza della carica attuale. Il campione misura questi casi, con un verificatore a modello. Sono passati 38 test automatici.

### Confronto a parità di sintesi e prova della confidenza

Sono state ripetute 24 domande del benchmark, otto per libretto. Per ciascun caso sono state confrontate la stessa sintesi in ingresso al verificatore e la risposta risultante, a fonti e ricerca uguali. Il verificatore ha confermato 14 sintesi e ne ha riscritte 7. Tre richieste non lo hanno attivato. Il tempo mediano della chiamata aggiuntiva è stato di 2,6 s, con un minimo di 2,0 s e un massimo di 6,2 s nelle 21 chiamate della prova.

Fra le sette riscritture, tre hanno ripristinato una condizione o un’avvertenza rilevante, relative al ruotino Audi, al traino della Civic e alla retromarcia della Focus. Una ha accorciato troppo la risposta sulle pastiglie della Civic, eliminando l’indicazione che serve una verifica sulla vettura per determinarne lo spessore. Le altre hanno riformulato la risposta. Il divieto di trasportare persone nel rimorchio è rimasto esplicito, anche se l’apertura «Sì» poteva creare ambiguità.

Nel laboratorio di triage della lezione 3, `confidenza` era un valore fra 0 e 1 dichiarato dal modello. È stato provato separatamente con le fonti reali di Manual Mate e 18 sintesi preparate in coppia. Ogni domanda aveva una sintesi completa e una con un errore di contenuto o un’omissione.

| Tipo di sintesi | Numero di casi | Valori osservati |
|---|---:|---|
| Complete e coerenti | 9 | da 0,96 a 1,00 |
| Con un errore introdotto | 6 | 0 in cinque casi e 0,55 per la condizione omessa sul ruotino |
| Parziali ma coerenti per ciò che dicono | 3 | 0,35, 0,45 e 0,55 |

Il punteggio ha separato le coppie in questo campione controllato. Le sintesi erano preparate e il risultato non misura la calibrazione del punteggio su richieste spontanee. Il campo numerico resta sperimentale. La chat usa ancora l’esito del confronto con gli estratti.

### Confidenza sulle risposte generate dall’agente

Sono state sottoposte all’agente 36 domande del benchmark, divise in anticipo in due gruppi da 18, ciascuno con sei domande per libretto. Un caso è stato recuperato da un altro file del benchmark dopo un errore nella selezione. Il modello ha assegnato un punteggio di `confidenza` alla sintesi precedente alla verifica, vedendo solo gli estratti citati e la domanda. Due richieste non hanno prodotto una sintesi generata da valutare. Sono state valutate quindi 34 sintesi, 16 nel gruppo di taratura e 18 nel gruppo di conferma. I giudizi sono stati attribuiti senza mostrare il punteggio al valutatore e riletti rispetto ai criteri fissati per ciascuna domanda.

Nel gruppo di taratura sono state confrontate le soglie da 0,50 a 1,00. Con 0,90 si ottiene la proporzione più alta di risposte complete tra quelle accettate, a pari merito con 0,95. È stata scelta la soglia inferiore tra le due e applicata senza cambiarla al gruppo di conferma.

| Gruppo | Sintesi con punteggio | Accettate a 0,90 | Complete tra le accettate | Accettate con omissioni o dettagli non verificati |
|---|---:|---:|---:|---:|
| Taratura | 16 | 13 | 11 | 2 |
| Conferma | 18 | 18 | 16 | 2 |

Nel gruppo di conferma, il modello ha assegnato 0,99 alla sintesi sul ruotino che ometteva «se necessario» e 1,00 alla risposta sulla retromarcia della Focus che ometteva la condizione del veicolo fermo. Il controllo con gli estratti ha ripristinato la condizione sul ruotino, mentre non ha intercettato l’omissione sulla Focus. Come confronto a posteriori, alzare la soglia a 1,00 avrebbe comunque lasciato passare quest’ultima risposta e mandato al riesame sei risposte complete del gruppo di conferma. Nel gruppo di taratura, la risposta sulla ricezione radio in galleria soddisfaceva il criterio pur ricevendo 0,38.

Il contrasto con il test delle sintesi preparate mostra il rischio di usare la confidenza da sola per decidere se pubblicare una risposta. Il punteggio rimane un possibile segnale diagnostico. La configurazione dell’app non è stata modificata durante questa prova.

### Checklist delle condizioni e delle avvertenze

Il confronto ha usato 24 domande del benchmark, otto per libretto, e sei coppie di controllo. In ogni coppia una sintesi conteneva tutti i dati richiesti e l’altra perdeva una condizione o parte della risposta. I verificatori hanno ricevuto la stessa sintesi iniziale, la stessa domanda e gli stessi estratti citati. La checklist era l’output strutturato di una sola chiamata, con riferimento alla fonte e stato `presente`, `omesso` o `alterato` per ogni requisito.

| Misura | Verifica attuale | Checklist ampia | Checklist selettiva |
|---|---:|---:|---:|
| Riscritture su 23 sintesi generate | 9 | 12 | 9 |
| Omissioni preparate corrette | 6/6 | 6/6 | 6/6 |
| Riscritture sulle 6 sintesi integre | 1 | 5 | 1 |
| Tempo mediano sulle 23 sintesi generate | 2,8 s | 6,3 s | 6,3 s |

Una delle 24 richieste ha ricevuto direttamente l’indicazione che il libretto non conosce il chilometraggio attuale. In quel caso il verificatore della sintesi non è stato chiamato.

- **Traino Civic.** La sintesi pubblicata con il verificatore attuale indicava la possibilità di sollevare le ruote anteriori e ometteva la condizione sul freno di stazionamento. Entrambe le checklist hanno ripristinato il vincolo del pianale se il freno non si può rilasciare. Quella selettiva ha conservato una risposta più breve.
- **Presa Focus.** La checklist ampia ha aggiunto il limite di 180 W quando la domanda riguardava gli ampere. La versione selettiva ha conservato i 20 A richiesti. Nella domanda composta ha conservato anche i 30 minuti di alimentazione dopo lo spegnimento.
- **Pneumatici Civic.** La checklist ampia ha cambiato «o» in «e». La checklist selettiva conserva la formulazione di p. 563. Il criterio in `queries.json` e `queries_chunking.json` ora accetta la frase del manuale, purché compaiano sia l’intervallo mensile sia il riferimento al viaggio lungo. I risultati storici sopra sono quelli osservati con i criteri in uso al momento.
- **Pastiglie Civic.** La checklist ampia ha recuperato un rinvio a un controllo collegato allo stridio dei freni. Il controllo per conoscere lo spessore attuale non è stato esplicitato con chiarezza come passaggio indipendente dal sintomo. La versione selettiva ha confermato la sintesi originale. Il caso resta aperto.

Un primo tentativo con la checklist selettiva restituiva spesso `confermata` con lista vuota. Il prototipo non mostrava allora la sintesi. L’ultima versione richiede un elenco anche quando conferma, e ha prodotto una sintesi utilizzabile in tutti i 35 confronti che l’hanno attivata. La prova conferma il vantaggio su alcune condizioni e mostra un costo in latenza. L’app continua a usare il verificatore attuale. I cinque test automatici del modulo di valutazione sono passati dopo la correzione del criterio.

## Test finale a configurazione fissa

Sono state fissate [60 domande e i relativi criteri](queries_finale.json) prima dell’esecuzione. Per ogni libretto il campione include 16 domande documentali a un turno, due conversazioni a più turni e due richieste su dati che il libretto non può conoscere. Nei 54 casi documentali è stata verificata nel PDF la pagina di riferimento. Una pagina alternativa era ammessa se sosteneva la risposta. Il confronto testuale con i benchmark precedenti ha escluso le domande già presenti, a parte le formule di chiarimento che identificano il modello. Alcuni argomenti sono rimasti comuni, con domande su aspetti diversi.

La prova ha usato il normale flusso di conversazione dell’agente, GPT-6 Luna, le collezioni Qdrant attive, il chunking per sottosezione, `k=10` e la verifica della sintesi. Sono state considerate complete le risposte con fonte pertinente e con tutti i dettagli richiesti dal criterio, incluse le condizioni. Per i dati della singola auto, la risposta completa esplicita il limite del libretto senza inventare un dato. Un valutatore ha esaminato le risposte e tre giudizi sono stati corretti rileggendo risposta, criterio e fonte. Il [report dei singoli casi](report_finale.json) riporta sia il giudizio automatico sia quello finale.

| Libretto | Complete | Parziali | Fallite |
|---|---:|---:|---:|
| Ford Focus | 17/20 | 1 | 2 |
| Honda Civic Type R | 19/20 | 1 | 0 |
| Audi A3 8V | 19/20 | 1 | 0 |
| **Totale** | **55/60 (91,7%)** | **3** | **2** |

L’obiettivo era 54 risposte complete. Sono state complete 49 risposte documentali su 54, cinque conversazioni su sei e tutte e sei le risposte sui dati non conoscibili. Il 91,7% riguarda il campione del test finale.

| Caso | Esito | Riscontro |
|---|---|---|
| Focus, getto sullo sportellino carburante | Fallita | La pagina 137, con la distanza minima richiesta, non era tra le pagine recuperate. |
| Focus, serbatoio del liquido freni e frizione | Fallita | Dopo aver chiesto il modello, la chat ha ricevuto «Ford Focus con cambio manuale» e ha chiesto di nuovo l’argomento. La ricerca non è partita. La risposta è a p. 232. |
| Focus, chiave smarrita | Parziale | La risposta rimanda alla concessionaria e parla di riprogrammazione generica. La pagina 49, che prescrive di far cancellare e ricodificare le chiavi rimanenti, non è stata recuperata. |
| Civic, benzina | Parziale | La risposta riporta E10 e i valori di 95 e 98 ottani, ma omette la conformità a EN 228, prevista dal criterio a p. 513. |
| Audi, kick-down | Parziale | La risposta spiega la scalata del cambio, ma omette il nome della funzione e il suo scopo, la massima accelerazione, indicati a p. 87. |

I casi distinguono due mancate acquisizioni della fonte (sportellino e chiavi), una perdita del contesto del dialogo (frizione) e due omissioni in sintesi con fonti già disponibili (benzina e kick-down). La configurazione è rimasta fissa per tutta la prova.

Tre verifiche separate con il test harness di Streamlit hanno confermato risposte e citazioni visibili sul serbatoio condiviso dei lavacristalli Focus (p. 232), sul tappo blu Civic (p. 539) e sui tre lampeggi dell’indicatore Audi (p. 49). Queste ripetizioni non entrano nel conteggio delle 60 domande.

## Correzioni dopo il test finale

Nel caso Focus sulla frizione, «È una Ford Focus con cambio manuale» selezionava il libretto ma sostituiva la domanda che aveva aperto la conversazione. Ora, se la chat è in attesa del modello, una risposta con modello e dettagli come cambio o allestimento riprende la domanda originale e passa il dettaglio all’agente. Una nuova domanda esplicita continua a prendere il posto di quella in sospeso.

Per lo sportellino, la prima ricerca del test finale non aveva recuperato la pagina 137. La stessa collezione l’ha restituita al primo posto usando la domanda così come scritta. Il nuovo tentativo parte solo se c’è già stata una ricerca, il riesame dei passaggi disponibili non ha confermato una fonte e non serve un chiarimento. Usa il testo dell’utente e gli eventuali turni precedenti. Se la query è diversa da quelle già usate, la app invia un solo embedding aggiuntivo, completa al massimo tre pagine nuove dello stesso libretto e sottopone le citazioni ai controlli già previsti. Il test usa le collezioni esistenti, con sottosezioni, dimensione 1024, overlap 0 e `k=10`.

| Prova mirata con OpenAI e Qdrant | Risultato osservato |
|---|---|
| Focus, serbatoio freni e frizione | 3/3 complete. Il chiarimento sul cambio ha mantenuto la domanda e la risposta ha citato p. 232. |
| Focus, getto sullo sportellino | 3/3 complete. Le risposte hanno citato p. 137, con distanza minima di 200 mm e getto solo per breve tempo. |
| Focus, chiavi smarrite | 1/1 completa. Ha citato p. 49 con cancellazione e ricodifica delle chiavi rimanenti insieme a quella sostitutiva. |
| Civic, livello nel serbatoio freni e frizione | 1/1 completa, con i riferimenti MIN e MAX a p. 549. |
| Audi, VIN nel sistema MMI dopo il chiarimento | 1/1 completa, con percorso e riferimento a p. 394. |
| Civic, litri di benzina presenti in quel momento | 1/1 completa. Ha spiegato il ruolo dell’indicatore e ha dichiarato che il valore attuale non si ricava dal libretto. |

Due nuove formulazioni sul lavaggio («idropulitrice» e «lancia dell’autolavaggio») hanno restituito la stessa indicazione a p. 137. «Guido una Focus con cambio manuale» ha risolto la domanda sulla vaschetta, mentre «Ford Focus con cambio manuale, dove sono i fusibili?» ha avviato correttamente la nuova ricerca sui fusibili (p. 205). Per la Civic, il chiarimento «È una Civic Type R del 2023 con cambio manuale» ha mantenuto la domanda sull’indicatore del turbo (p. 149). La suite automatica ha superato 41 test, inclusi il rifiuto di una citazione non presente, la selezione del libretto corretto nella ricerca di riserva e il mantenimento del contesto in Streamlit.

Queste verifiche mirate non aggiornano il risultato del test finale da 60 domande. I casi Civic sulla benzina conforme a EN 228 e Audi sul kick-down restano quelli descritti nel report finale.

## Completezza delle sintesi, benzina Civic e kick-down Audi

Le due pagine citate nel report finale contengono i dettagli omessi. A p. 513 Civic, il requisito EN 228 accompagna E10 e la soglia minima di 95 ottani. La stessa pagina consiglia almeno 98 ottani per ottimizzare le prestazioni. A p. 87 Audi, il testo nomina il kick-down e lo descrive come funzione per la massima accelerazione prima di spiegare la scalata in funzione di velocità e regime.

Una nuova misura con i prompt precedenti ha usato dieci esecuzioni. Le due domande originali sono state ripetute due volte ciascuna, affiancate da una variante per domanda e quattro controlli su presa Civic, retronebbia Audi, VIN Audi e benzina residua Civic. Sul carburante una delle due risposte originali e la variante hanno omesso EN 228. Sul kick-down una delle due risposte originali ha omesso nome e scopo. I quattro controlli hanno risposto correttamente. La completezza sui sei casi bersaglio era quindi 3/6.

Il primo aggiornamento ha introdotto criteri condivisi fra agente, riesame e verificatore. Per le specifiche chiede di conservare soglie, unità e norme che determinano la validità. Per le funzioni richiede nome, scopo e comportamento pertinente. Ha portato a 5/6 risposte complete sui casi bersaglio, ma una risposta sul kick-down ometteva ancora lo scopo. Un controllo VIN ha restituito fonte assente. Due ripetizioni diagnostiche successive hanno trovato p. 394 e risposto con il percorso MMI. Questo mostra una variabilità del recupero ancora presente.

Il verificatore, provato direttamente sulle due risposte incomplete del report, le aveva confermate anche dopo il primo aggiornamento. Lo schema `VerificaSintesi` include ora `omissioni_rilevanti`, da compilare prima dell’esito. Il programma accetta `confermata` soltanto se questa lista e la sintesi corretta sono vuote. Se il modello dichiara omissioni senza correggerle, la risposta mostra l’estratto originale. Un nuovo test automatico controlla questo comportamento con un limite di potenza e corrente, su un argomento diverso dai due casi bersaglio.

Con lo schema aggiornato, due prove dirette sulle risposte incomplete originali hanno prodotto sintesi corrette: EN 228 è stato aggiunto per la Civic e nome e massima accelerazione per il kick-down Audi. I prompt e lo schema sono descritti anche in `MANUALE_MANUAL_MATE.md`. Le modifiche riguardano la generazione e la verifica della risposta. L’indice e i parametri di retrieval restano quelli del test precedente.

La ripetizione conclusiva delle dieci esecuzioni ha dato 6/6 risposte complete sui casi bersaglio, incluse le due varianti. Tre controlli sono completi. Il controllo VIN ha recuperato p. 394 e indicato il percorso MMI, ma ha omesso il passaggio del pulsante di controllo sinistro: lo registro come parziale. Il bilancio del campione conclusivo è quindi 9/10 complete e una parziale. Il controllo sulla benzina residua ha mantenuto il limite sui dati attuali. La suite automatica ha superato 42 test. Il report finale da 60 domande conserva la misura precedente del 91,7%; queste prove di sviluppo non costituiscono una nuova misura complessiva.

## Ripetizione completa delle 60 domande

Il benchmark è stato ripetuto sullo stesso insieme `queries_finale.json`, con tre lavoratori, i prompt aggiornati e i parametri attivi. Il nuovo file `report_finale_ripetizione.json` conserva il risultato automatico di ogni caso e la revisione della risposta visibile. I criteri e le domande del campione sono quelli della prova precedente.

| Libretto | Complete prima | Complete nella ripetizione | Parziali nella ripetizione | Fallite nella ripetizione |
|---|---:|---:|---:|---:|
| Focus | 17/20 | 19/20 | 1 | 0 |
| Civic | 19/20 | 20/20 | 0 | 0 |
| Audi | 19/20 | 16/20 | 1 | 3 |
| Totale | 55/60 | 55/60 (91,7%) | 2 | 3 |

Tutti e sei i dialoghi hanno mantenuto il tema e tutti e sei i casi sui dati reali della vettura hanno dichiarato il limite senza inventare valori. La benzina Civic include EN 228, E10, almeno 95 ottani e almeno 98 per le prestazioni. Il kick-down Audi include nome, massima accelerazione e scalata in funzione di velocità e regime. Il VIN Audi include anche il pulsante di controllo sinistro.

Il controllo automatico ha contato 48/60. Cinque KO dipendono dall’esito `risposta` al posto di `fonte_assente`: il testo dichiara correttamente il limite e aggiunge informazioni documentate. Un caso Civic cita la capienza di 47,0 L dalla tabella tecnica a p. 642, verificata sul PDF, mentre il test ammetteva solo p. 513. Due giudizi strutturati sono mancanti, sullo stesso caso della capienza e sulle catene Audi. La risposta sulle catene contiene ruote anteriori e massimo 50 km/h. La revisione registra questi motivi senza sovrascrivere gli esiti automatici.

Restano due risposte parziali: il bloccasterzo Focus indica la posizione I ma omette l’inserimento della chiave previsto dal criterio; l’autolavaggio Audi indica lo spegnimento dei tergi ma omette il motivo dell’attivazione involontaria. Tre risposte Audi si astengono, pur avendo recuperato le pagine pertinenti: sensore pioggia a p. 54, bracciolo a p. 60 e disattivazione del cruise control con il freno a p. 127.

Il risultato complessivo è uguale alla misura precedente. Le correzioni dei casi bersaglio hanno funzionato, mentre sono emerse altre rinunce. Il campione è stato già usato durante lo sviluppo e una singola ripetizione mostra anche la variabilità delle chiamate generative. Il 91,7% misura le risposte di questo campione e non la copertura dell’intero contenuto dei libretti.

### Diagnostica successiva sulle rinunce Audi

La ripetizione diagnostica del sensore pioggia ha dato la risposta corretta, con p. 54 e circa 4 km/h. Sul bracciolo il controllo ha rifiutato la citazione «starting po- sition» perché la fonte conteneva `po-` seguito da un a capo e `sition`. Il riesame ha poi trovato una citazione più breve valida e risposto correttamente. Anche la ripetizione sul cruise control ha risposto correttamente con p. 127, conservando attivazione del sistema e memorizzazione della velocità. Le tre ripetizioni diagnostiche sono quindi riuscite. Questo dimostra un rifiuto tipografico concreto sul bracciolo, mentre per le altre rinunce resta il comportamento variabile dell’agente da approfondire.

Dopo la misura da 60 domande, la normalizzazione è stata estesa alle parole alfabetiche sillabate con un trattino seguito da spazio. Il test include sia la parola inglese composta `short-term` sia `po- sition`, mantenendo i controlli che respingono modifiche di numeri, unità e frasi. La suite ha superato tutti i 42 test dopo la correzione. Il report del benchmark descrive l’esecuzione precedente a questa correzione.

## Stabilità con formulazioni diverse e domande aggiuntive

Dopo la correzione tipografica è stato eseguito `queries_stabilita.json`, con risultati in `report_stabilita.json`. Il campione comprende cinque formulazioni di ciascuno dei tre casi Audi intermittenti e nove domande aggiuntive, tre per libretto. Per le domande aggiuntive, pagine e criteri sono stati verificati sul testo dei PDF prima delle chiamate all’agente. Il giro ha usato i parametri e i prompt del progetto, con tre lavoratori. Le 24 risposte sono state lette e confrontate con i criteri.

| Gruppo | Complete | Parziali | Fallite |
|---|---:|---:|---:|
| Sensore pioggia Audi, cinque formulazioni | 4 | 0 | 1 |
| Bracciolo Audi, cinque formulazioni | 5 | 0 | 0 |
| Freno e cruise control Audi, cinque formulazioni | 4 | 0 | 1 |
| Domande aggiuntive Focus | 3 | 0 | 0 |
| Domande aggiuntive Civic | 3 | 0 | 0 |
| Domande aggiuntive Audi | 2 | 1 | 0 |
| Totale | 21/24 (87,5%) | 1 | 2 |

Le domande aggiuntive Focus riguardano la pompa del lavaparabrezza a serbatoio vuoto (p. 61), l’orario programmato del riscaldatore di parcheggio (p. 104) e il contatto con il vetro delle lampadine alogene (p. 235). Quelle Civic riguardano la regolazione in altezza del sedile (p. 204), i pesi sulla copertura bagagliaio (p. 217) e l’ordine di scollegamento e ricollegamento dei cavi della batteria (p. 570). Quelle Audi riguardano l’aggancio dello schienale posteriore (p. 66), la temperatura per sbrinare il parabrezza (p. 70) e la portiera chiusa per il rilascio automatico del freno di stazionamento (p. 80).

Il sensore pioggia fallisce con «la soglia ... è circa 4 o 40 km/h?». La pagina 54 non compare tra i risultati. Il cruise control fallisce con «Quando il cruise control è attivo, premere il freno disattiva la velocità impostata?», pur avendo la pagina 127 al primo posto. Il report distingue quindi un recupero mancato da una mancata risposta con fonte disponibile. Le informazioni registrate nel benchmark non identificano quale passaggio interno abbia scartato la seconda risposta.

Sul bracciolo tutte e cinque le formulazioni hanno indicato di sollevarlo oltre l’ultima tacca e ripiegarlo in basso. È un riscontro positivo dopo la correzione dell’OCR, senza un confronto controllato sufficiente ad attribuirle da sola il miglioramento.

La risposta sullo schienale Audi cita il controllo per trazione di p. 64, ma omette il segno rosso sul perno a p. 66 previsto dal criterio. La registro come parziale rispetto al criterio prefissato, conservando la fonte alternativa indicata dalla risposta. Il campione mirato mostra ancora due astensioni intermittenti e un’omissione. Il risultato da 60 domande resta 55/60; queste 24 prove hanno una distribuzione diversa degli argomenti e non vanno sommate per stimare l’accuratezza generale.

## Diagnostica delle due rinunce e correzione del riesame

I due casi rimasti sono stati ripetuti tre volte ciascuno, registrando query, pagine, citazioni, esiti delle chiamate e risposte strutturate in `report_diagnostica.json`. Le tre ripetizioni sulla pioggia sono riuscite. Sul cruise control due sono riuscite e una ha riprodotto il rifiuto, con p. 127 disponibile. Le risposte strutturate osservate erano complete; non risultano interrotte per il limite di token.

Il rifiuto del cruise control è riproducibile nel controllo letterale. Il modello ha scritto «To deactivate the cruise control speed, press the brake pedal.» come citazione. La fonte presenta una frase sull’azionamento della leva e, separatamente, «Press the brake pedal.». La frase ricostruita contiene un significato pertinente, ma non è una sequenza letterale del passaggio. In una ripetizione anche il riesame ha riproposto la stessa frase e il programma l’ha rifiutata di nuovo. La ricerca di riserva ha aggiunto altre pagine senza fornire una citazione accettabile.

Il riesame riceve ora il motivo del rifiuto quando tutte le citazioni proposte sono invalide. Può correggerle una sola volta usando gli stessi passaggi, con una chiamata strutturata aggiuntiva. Anche la correzione deve superare i controlli su ID e testo. Il prompt chiarisce che, per un elenco, è possibile citare una singola voce consecutiva e usare il titolo per comprenderne il significato, senza inserirlo artificiosamente nella citazione. La traccia di questa chiamata è `correzione-citazioni`. Un nuovo test riproduce la citazione composta e verifica sia la riparazione sia l’arresto dopo il secondo rifiuto. La suite aggiornata supera 43 test.

Per la pioggia, due ricerche controllate sulla stessa collezione mostrano l’effetto dei valori ipotizzati nella query. «Rain sensor automatic wiper activation vehicle speed 4 km/h 40 km/h» non restituisce p. 54 nei primi dieci risultati; togliendo solo «4 km/h 40 km/h», p. 54 compare al quinto posto. È un riscontro sull’effetto della formulazione nel ranking. Il prompt di ricerca ora chiede query brevi nella lingua del libretto, senza modello e anno già fissati dalla collezione, ed esclude i valori alternativi proposti dall’utente da verificare. Codici e caratteristiche che identificano il componente restano pertinenti alla query. La domanda originale completa resta disponibile per formulare la risposta.

La ripetizione di `queries_stabilita.json` dopo entrambe le correzioni ha prodotto 24/24 casi passati. La lettura delle risposte visibili conferma i criteri: 5/5 sulla pioggia, 5/5 sul bracciolo, 5/5 sul cruise control e 9/9 sulle domande aggiuntive. La risposta sullo schienale include il segno rosso di p. 66 e il controllo per trazione di p. 64. Il report `report_stabilita_correzione.json` conserva il risultato automatico e la revisione. Il confronto sullo stesso campione passa quindi da 21/24 complete, una parziale e due fallite a 24/24 complete.

È una ripetizione di sviluppo dopo due modifiche congiunte e comprende la variabilità generativa. Non isola l’effetto delle singole correzioni e non aggiorna il risultato sulle 60 domande. La prova controllata delle query e la citazione respinta nella diagnostica documentano separatamente i due meccanismi osservati. I 43 test automatici passano con il codice aggiornato.

## Primo test su un quarto libretto, SEAT Leon

È stato aggiunto il manuale italiano SEAT Leon 5D / Sportstourer, codice 5FA012750BT, edizione 11/2021. Il PDF ha 432 pagine. L’estrazione trova testo in 429 pagine, con le pagine PDF 6, 429 e 430 prive di testo estraibile, e produce 1.940 passaggi. Il nuovo indice è stato creato in Qdrant con i parametri 1024 caratteri, overlap 0 e `k=10`.

Prima della prima richiesta all’agente, sono stati letti i passaggi del PDF e fissati 24 casi in `queries_leon.json`. La prova usa i prompt esistenti e il percorso generativo generale. L’integrazione ha richiesto una voce nel catalogo, il riconoscimento di Leon nella conversazione e un riconoscimento generico del numero stampato come ultima riga della pagina. Le regole specifiche per olio, chiavi o fusibili degli altri tre veicoli non sono state estese alla Leon. La lettura del nuovo PDF e i metadati di catalogo sono adattamenti preliminari da considerare nel valutare la generalizzazione.

Il report `report_leon.json` conserva 17/24 casi passati automaticamente e la revisione delle 24 risposte. Il caso sul carburante attuale dichiara correttamente il limite, pur avendo esito `risposta` al posto di `fonte_assente`. La revisione conta quindi 18/24 complete (75%), cinque parziali e una fallita.

| Risultato | Riscontri |
|---|---|
| Informazioni del nuovo libretto riportate correttamente | Coppia bulloni 140 Nm, sincronizzazione della chiave, pressione olio rossa, posizione dell’etichetta pneumatici, serbatoio lavavetri condiviso, AdBlue, Start/Stop, gamma del regolatore, cassetto, attesa per l’astina e fari per viaggi temporanei all’estero. |
| Dati attuali non conoscibili | Limite dichiarato per carburante attuale, telefono collegato in passato e costo attuale di un’officina. |
| Fusibili, due risposte parziali | La localizzazione è corretta e il dialogo mantiene la domanda. Manca l’apertura abbassando la copertura, richiesta dal criterio anche se le domande chiedono solo la posizione. |
| Pila del telecomando, parziale | Dichiara di non trovare una risposta e non inventa un codice. Non spiega che il passaggio richiede le stesse caratteristiche della pila originale senza indicarne il codice preciso. |
| Catene, parziale | Riporta ruote anteriori anche con trazione integrale e massimo 50 km/h. Omette che sono ammesse solo determinate combinazioni cerchi/pneumatici. |
| Pressione pneumatici dopo il chiarimento, parziale | Trova l’etichetta e mantiene il tema, ma omette il controllo a freddo e il carico. La pagina 373 compare al sesto posto e il passaggio citato non comprende tutte le istruzioni. |
| Liquido freni, fallita | La pagina 361 è al primo posto, ma la risposta si astiene invece di riportare le specifiche VW 501 14 e le alternative previste. |

Questa misura è stata conservata prima di qualsiasi intervento sui suoi errori. Mostra che molte informazioni di un nuovo manuale vengono già gestite dal percorso generale, mentre restano problemi di completezza del contesto e rinunce con la fonte presente. Il risultato non dimostra un’accuratezza del 90% sul nuovo libretto. Il codice aggiornato supera 45 test automatici, inclusi riconoscimento della Leon in Streamlit e lettura del numero stampato dal nuovo formato. Il controllo delle evidenze del vecchio benchmark è stato allineato ai veicoli effettivamente presenti in quel campione, che continua a verificare i tre libretti precedenti.

## Refactoring, riconoscimento dei modelli e confronto degli estrattori

Il refactoring mantiene l’ingresso `Assistente.rispondi` e gli import precedenti dei tipi delle risposte. I contenuti dei prompt sono stati inizialmente spostati senza modificarli; i 45 test esistenti passavano dopo questa prima separazione.

| Modulo | Responsabilità |
|---|---|
| `prompt.py` | Prompt dell’agente, del riesame e della verifica, con criteri di completezza condivisi. |
| `fonti.py` | Tipi delle risposte e degli output strutturati, riferimenti e controllo letterale delle citazioni. |
| `recupero.py` | Fonti della singola richiesta, controllo del libretto, unione delle ricerche, cache delle pagine complete e completamento delle fonti effettivamente citate. |
| `strutturati.py` | Chiamate strutturate con un solo tentativo aggiuntivo se il JSON è invalido o assente, usando un limite di output doppio nel secondo tentativo. Gli errori API producono un esito esplicito nella traccia. |
| `estrazione.py` | Estrazione per pagina con pypdf, PDFium o Docling, mantenendo la numerazione stampata verificata nel PDF. Docling usa l’adattatore Datapizza e conserva il documento strutturato in una cache locale esclusa da Git. |
| `corpus.py` | Interpretazione delle intestazioni e costruzione dei chunk per sottosezione o per pagina. |
| `indice.py` | Preparazione, verifica e attivazione separata delle collezioni persistenti. Le prove possono preparare indici alternativi lasciando invariato l’alias dell’app. |
| `catalogo.py` | Edizioni, pattern dei nomi, anni e varianti incompatibili: i dati per riconoscere un veicolo sono definiti insieme al suo manuale. |

Il riconoscimento del modello perdeva la domanda in attesa se una risposta conteneva qualificazioni fuori dalla piccola lista prevista. Ora una risposta al chiarimento con un solo modello riconosciuto e senza una nuova domanda esplicita conserva il tema e passa i dettagli all’agente. I test comprendono Leon FR 1.5 eTSI DSG, Focus Titanium, Civic Type R GT e Audi Sportback, oltre a una nuova domanda autonoma e a un anno incompatibile.

È stato corretto anche un falso anno: nella domanda «Honda Civic Type R, pila CR 2032» il numero 2032 poteva essere trattato come anno del veicolo. Ora gli anni sono associati al nome del modello o a marcatori espliciti come «del» e «anno». Il test mantiene anche il rifiuto di un anno incompatibile dichiarato per il veicolo. Le domande nuove introdotte con «che», anche prive del punto interrogativo, non vengono assorbite come dettagli del modello.

### Cause riprodotte sulla Leon

La diagnostica `report_diagnostica_leon.json` ha registrato un output API incompleto sul liquido freni: limite di 1.100 token, 1.079 token usati dal ragionamento e JSON interrotto all’inizio. Il parser sollevava un errore di validazione. Il nuovo gestore permette un solo recupero con più spazio e restituisce un limite controllato se fallisce anche questo tentativo.

L’estrazione pypdf spezza alcune parole all’interno delle frasi: le citazioni corrette del manuale possono quindi fallire il confronto con il testo estratto. Tre citazioni campione su pila, liquido freni e controllo a freddo risultano tutte non riconosciute nell’indice pypdf e tutte riconosciute nei due profili PDFium. Il controllo sulle citazioni conserva i vincoli precedenti su numeri e unità.

Una fonte citata oltre le prime tre pagine del ranking poteva arrivare alla verifica solo come frammento. Ora anche la pagina effettivamente citata viene completata, riusando la cache della richiesta. Un test verifica il caso della sesta pagina senza ricompletare le prime tre.

La pila della chiave ha inoltre mostrato una confusione fra componenti: una risposta usava il telecomando del riscaldatore. La verifica considera ora titoli e funzione del dispositivo e può restituire `fonte_non_pertinente`. Questo esito produce un’astensione, anche quando la citazione è letteralmente valida. I percorsi con evidenze specifiche già verificate restano esplicitamente riconoscibili nel codice.

### Confronto preliminare sul recupero

`confronta_ingestione.py` esegue le stesse 21 domande documentali Leon, usando il testo dell’utente senza riscrittura LLM e `k=10`. La misura valuta posizione della pagina attesa e fedeltà delle tre citazioni campione. Il risultato delle risposte dell’agente richiede una prova separata.

| Profilo | Chunk | Pagina nei primi 3 | Pagina nei primi 10 | Citazioni campione riconosciute |
|---|---:|---:|---:|---:|
| pypdf, sottosezioni | 1.940 | 16/21 | 20/21 | 0/3 |
| PDFium, sottosezioni | 2.098 | 18/21 | 20/21 | 3/3 |
| PDFium, blocchi per pagina | 1.358 | 16/21 | 20/21 | 3/3 |
| Docling, sottosezioni | 3.331 | 15/21 | 20/21 | 3/3 |
| Docling, RecursiveSplitter | 1.536 | 18/21 | 20/21 | 3/3 |

I profili alternativi vengono preparati in collezioni separate. Il report è `report_confronto_ingestione.json`. La prova Docling usa la versione 2.110.0 e l’adattatore Datapizza 0.0.9, presenti nei materiali del corso. Sul PDF nativo della Leon è stato disattivato l’OCR, mantenendo l’analisi della struttura e delle tabelle. La provenienza per pagina viene conservata esportando il documento strutturato una pagina alla volta.

Il profilo ricorsivo usa `RecursiveSplitter` di Datapizza con 1.024 caratteri e overlap 0, per confrontare il metodo a parità dei parametri attuali. I paragrafi e le tabelle Docling sono i nodi foglia del documento di pagina. Come previsto dal componente, un nodo indivisibile può superare il limite indicativo di caratteri. Le pagine restano distinguibili e la ricomposizione usa i riferimenti persistenti.

La prima esportazione Docling leggeva solo il corpo principale: alcuni testi nativi erano annidati nelle figure e venivano saltati. La versione incompleta aveva 3.134 chunk e 408 pagine con contenuto. La relativa misura è conservata in `report_confronto_ingestione_prima_figure.json`. L’attraversamento completo delle figure recupera tutte le 429 pagine testuali. Per i paragrafi che attraversano due pagine vengono usati gli intervalli di caratteri della provenienza, senza attribuire il testo intero alla prima pagina. Un test verifica questa separazione.

L’esportazione iniziale richiamava il serializzatore dell’intero documento per ogni pagina; anche l’esportazione delle tabelle ricreava il serializzatore. La versione corrente visita gli elementi una sola volta e riusa il serializzatore delle tabelle. La conversione strutturata iniziale, circa 19 minuti sul computer della prova, rimane in cache. È un costo di preparazione del nuovo PDF, distinto dalle chiamate OpenAI e dalla risposta della chat.

La prima ripetizione applicativa con l’indice pypdf, registrata in `report_refactor_leon_pypdf.json`, ha prodotto 14/24 esiti automatici conformi. Ha risposto sul liquido freni e recuperato il controllo a freddo nel dialogo, ma ha conservato omissioni e una fonte sul telecomando del riscaldatore. Questa misura intermedia non dimostra un aumento dell’accuratezza e precede la verifica conclusiva del refactoring.

Con l’indice PDFium la ripetizione ha dato 16/24 esiti automatici conformi (`report_refactor_leon_pdfium.json`). I due limiti sui dati attuali sono dichiarati correttamente e il caso del telecomando chiede se si intenda la chiave o il riscaldatore autonomo. Restano omissioni rispetto ai criteri, come l’adeguamento della pressione al carico. Il campione di regressione su dodici casi dei quattro libretti ha 9/12 esiti automatici, con tre risposte correttamente limitate ma etichettate `risposta` invece di `fonte_assente`. La lettura delle dodici risposte conferma i contenuti e il mantenimento del tema, incluso il percorso MMI completo e i dialoghi con allestimenti.

### Validazione e profilo attivato

La prova di Docling con RecursiveSplitter sulle stesse 24 domande ha prodotto 18/24 esiti automatici conformi, prima della correzione del valutatore dei limiti. La revisione manuale registra 19 complete, cinque parziali e nessuna rinuncia errata (`report_refactor_leon_docling.json`). Due risposte sui dati attuali dichiarano correttamente il limite con fonte. Una risposta classificata completa dal valutatore viene invece conservata come parziale: dopo aver indicato il controllo a freddo, la frase «quindi non appena terminato il viaggio» è ambigua e può essere letta come un controllo immediato a fine viaggio.

Le altre quattro parziali omettono l’apertura del coperchio dei fusibili, l’adeguamento al carico nelle due risposte sulla pressione e il vincolo sulle combinazioni cerchi/pneumatici per le catene. Alcuni dettagli sono aggiuntivi rispetto alle domande, ma il criterio prefissato è conservato per non riscrivere il risultato dopo la prova.

Tre domande aggiuntive, fissate in `queries_docling_tabelle.json`, passano tutte: la combinazione 225/45 R17 e 7,5Jx17 ET46 ammette una maglia massima di 9 mm; il ruotino 125/70 R16 richiede 4,2 bar; la nota del capitolo Start-Stop esclude i PHEV. I risultati sono in `report_docling_tabelle.json`. Questi casi verificano lettura di tabella, associazione di un valore alla variante corretta e conservazione delle note di applicabilità.

Per la Leon è stato scelto e attivato Docling con RecursiveSplitter: recupero nei primi tre uguale al miglior profilo PDFium, citazioni campione integre e risposte verificate anche sulle tabelle. L’alias Qdrant è stato controllato contro il nome della collezione del confronto e contiene 1.536 passaggi. Il comando ordinario `main.py --indicizza --veicolo leon` ha riusato l’indice completo senza nuovi embedding. Il profilo è dichiarato nel catalogo per rendere coerenti gli aggiornamenti successivi.

È stato corretto anche un problema generale del benchmark: quando il caso attende un limite e dispone di un criterio semantico, una risposta documentata viene ora sottoposta al giudice anche se il suo esito interno è `risposta`. Passa soltanto se dichiara il limite senza inventare il dato. Un test affianca un limite corretto a un livello attuale di carburante inventato e verifica il rifiuto di quest’ultimo. Le misure automatiche storiche nei report precedenti restano quelle eseguite prima di questa correzione.

Il risultato di sviluppo non raggiunge ancora il 90% di completezza su questo campione Leon. Le cause tecniche riprodotte sono state corrette, ma restano omissioni e formulazioni da migliorare e verificare su nuove domande. La scelta del parser e il refactoring non costituiscono da soli una garanzia di correttezza su tutti i contenuti dei libretti.

La verifica conclusiva supera 56 test automatici. Il controllo delle dipendenze non rileva incompatibilità. Dall’ingresso ordinario della CLI, «La Honda Civic Type R usa una pila CR 2032?» riconosce il veicolo e risponde CR2032 citando p. 575, confermando anche fuori dai mock la correzione del falso anno. L’alias Leon è stato confrontato con la collezione `docling_ricorsivo` del report e risulta coerente.

## Ripetere i controlli

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests
.\.venv\Scripts\python.exe -X utf8 main.py --indicizza
```

Le raccolte [queries.json](queries.json), [queries_stress.json](queries_stress.json), [queries_copertura.json](queries_copertura.json) e [queries_chunking.json](queries_chunking.json) conservano domande e criteri. L’ultima contiene i due campioni da 36 domande usati per confrontare il chunking per pagina con quello per sottosezione. Le griglie sono state eseguite su indici temporanei. I risultati qui riportati sono misure osservate e possono variare riavviando l’agente.

Per rieseguire le 72 domande sull’indice attivo con il valutatore del progetto, dalla cartella del repository:

```powershell
@'
import os
from pathlib import Path
from runtime import carica_configurazione, crea_assistente
from valutazione import valuta

carica_configurazione()
assistente = crea_assistente(os.environ["OPENAI_API_KEY"])
valuta(assistente, Path("queries_chunking.json"), Path("report_chunking.json"), lavoratori=3)
'@ | .\.venv\Scripts\python.exe -X utf8 -
```

Questo comando valuta il profilo attivo. Un confronto A/B richiede due collezioni distinte e gli stessi criteri per entrambi i profili.
