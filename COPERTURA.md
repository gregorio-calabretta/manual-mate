# Copertura delle domande sui tre libretti

L’unità di copertura è l’argomento operativo. Le domande equivalenti contano una volta per argomento. La presenza di una prova indica che abbiamo formulato almeno una domanda con un riferimento verificabile. L’esito della prova si legge nel report di valutazione. I casi che verificano l’astensione o chiedono un dato esterno al libretto non aumentano il conteggio della copertura.

| Libretto | Argomenti con prove | Argomenti individuati | Copertura del campione |
| --- | ---: | ---: | ---: |
| Ford Focus (CEW) | 18 | 40 | 45% |
| Honda Civic Type R | 20 | 39 | 51% |
| Audi A3 8V | 18 | 39 | 46% |

Per la Focus la base sono i 40 capitoli operativi tra «La sicurezza dei bambini» e «SYNC 2» nei segnalibri del PDF. Per la Civic le voci del sommario alle pp. 4–5 e gli indici di capitolo sono raggruppati per funzione. Per l’Audi il sommario alle pp. 2–5 è raggruppato per funzione, tra guida, sicurezza, infotainment, manutenzione ed emergenze. Il conteggio esclude copyright, indici, dichiarazioni normative e altre voci senza una funzione d’uso da consultare. I raggruppamenti sono espliciti qui sotto, così l’obiettivo resta controllabile anche quando si aggiungono domande.

## Ford Focus (CEW)

**Con prove.** Sicurezza dei bambini, chiavi e telecomandi, MyKey, serrature, lava/tergicristalli, illuminazione, finestrini e specchietti, quadro strumenti, climatizzazione, prese ausiliarie, Start-Stop, cambio, traino, apparecchiatura di emergenza, fusibili, pulizia e cura, ruote e pneumatici, sistema audio.

**Da provare.** Cinture di sicurezza, airbag e protezione supplementare, antifurto, protezione bordo porta, volante, display informazioni, sedili, vani portaoggetti, avviamento, carburante e rifornimento, freni, controllo della trazione, controllo della stabilità, parcheggio a ultrasuoni, controllo di crociera, ausili di guida, trasporto di carichi, suggerimenti per la guida, manutenzione sotto il cofano, specifiche tecniche, SYNC, SYNC 2.

## Honda Civic Type R

**Con prove.** Orologio, chiavi e telecomandi, porte e chiusura di sicurezza per bambini, finestrini, luci, tergi e lavacristalli, volante, specchietti, climatizzazione, audio e connessioni, eCall, rimorchio, modalità di guida, retrocamera, manutenzione del cofano e olio, pneumatici, attrezzi, traino in caso di guasto, spie ed emergenze, fusibili.

**Da provare.** Seggiolini e protezione dei bambini, cinture, airbag e sistema di sollevamento cofano, portellone, antifurto, sedili, dotazioni e prese, Honda LogR, avviamento, cambio manuale, Honda Sensing e assistenza alla guida, frenata e parcheggio, rifornimento, promemoria e tabella di manutenzione, altri liquidi, batteria del veicolo, pulizia, gestione della foratura, posizione dei numeri identificativi.

## Audi A3 8V

**Con prove.** Chiusura centralizzata, finestrini e tetto, specchietti, fissaggio carichi, prese, climatizzazione, freno di parcheggio, rimorchio, ausili di parcheggio, stabilità ESC, gestione display MMI, telefono Bluetooth, navigazione, impostazione della data e dell’ora, sblocco del portellone in emergenza, ruotino, fusibili, dati tecnici e capacità.

**Da provare.** Quadro strumenti, sicure bambini sulle porte, illuminazione, tergi e lavacristalli, sedili e poggiatesta, avviamento e cambio, e-tron e ricarica, assistenza alla guida e cruise control, comandi vocali, Audi connect, radio e riproduzione media, posizione di guida, cinture, airbag, seggiolini, carburante e rifornimento, liquidi e manutenzione del motore, batteria e intervalli di servizio, ruote e pressione pneumatici, pulizia, traino in caso di guasto e altre procedure di emergenza.

## Come ripetere le prove

I set sono [benchmark generale](queries.json), [casi difficili](queries_stress.json) e [campione indipendente di copertura](queries_copertura.json). Il campione indipendente ha 14 domande per libretto, incluse richieste fuori dalla portata del manuale e una domanda a cui rispondere in parte. Le fonti attese vanno fissate prima dell’esecuzione. Se si usa un caso per modificare il sistema, va sostituito con una nuova domanda prima di una misura su un set tenuto da parte.

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py --copertura --lavoratori 4
```

Il comando produce `report_copertura.json`. L’accuratezza si misura separatamente dalla copertura: una risposta documentale deve contenere l’informazione chiesta e una citazione pertinente. Su dati esterni conta l’astensione esplicita. Se il manuale consente di rispondere a una parte, conta sia la risposta con fonte sia l’indicazione di ciò che resta indeterminato. Le motivazioni del valutatore automatico vanno controllate quando confliggono con il testo del PDF o con la risposta mostrata.

## Prima esecuzione del campione indipendente

Il [report](report_copertura.json) registra 26 esiti conformi su 42 usando GPT-6 Luna. Il conteggio automatico include sia problemi di risposta sia casi da rivedere. Per esempio, il test su USB e Bluetooth esigeva p. 238 della Civic, ma la risposta citava correttamente le due sezioni specifiche, pp. 279 e 283. Sul traino di un rimorchio con la Civic c’è un errore di recupero verificato: la chat ha trovato istruzioni sul traino di emergenza, mentre p. 376 risponde direttamente alla domanda.

Per arrivare ad almeno il 90% di copertura per libretto, partendo da questa mappa, servono prove documentali in altri 18 argomenti Focus, 16 Civic e 18 Audi. Questo conteggio riguarda l’ampliamento del campione. L’accuratezza andrà misurata di nuovo con domande tenute da parte.
