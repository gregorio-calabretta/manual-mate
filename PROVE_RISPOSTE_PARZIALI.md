# Risposte parziali documentate — 19 novembre 2026

## Problema e modifica proposta

Il dialogo segnalato dall'utente sul lavaparabrezza della Focus aveva prodotto un rifiuto,
pur avendo recuperato pagine pertinenti. Nella ripetizione iniziale con il codice invariato
il problema non si è riprodotto: è arrivata una risposta documentata. Non abbiamo quindi
dimostrato che il verificatore fosse la causa di quello specifico rifiuto originale.
Le risposte LLM possono cambiare tra esecuzioni.

La formulazione del verificatore era però ambigua: escludeva le avvertenze generali senza
distinguere quelle direttamente applicabili al malfunzionamento. La proposta in `prompt.py`
aggiunge un criterio condiviso da agente, riesame e verifica: fornire le indicazioni pratiche
documentate sul componente, dichiarando quando non consentono una diagnosi. Vietati cause,
riparazioni certe, prezzi e valori non sostenuti dalle fonti. Nessun caso speciale per il
lavavetri, nessun cambiamento a retrieval, chunk, indice o embedding.

## Prove reali e criteri di lettura

| Scenario | Risultato osservato | Valutazione manuale |
|---|---|---|
| Focus, spruzzino e successivo chiarimento «parabrezza anteriore» | Avvertenza sul serbatoio vuoto, indicazioni di rabbocco, limite sulla causa | Utile e limitata alle fonti |
| Focus, variante «non spruzza, cosa controllare?» | Liquido, comando e fusibile F82 da 20 A; nessuna diagnosi certa | Risposta pratica con riferimenti; non promette una soluzione |
| Focus, richiesta del pezzo certamente rotto | Controllo del livello e dichiarazione di impossibilità della diagnosi | Non inventa un componente guasto |
| Focus, colore rosso della spia pneumatici | Non conferma il colore; la verifica introduce una sequenza controversa di lampeggio | Da approfondire, non conteggiato come superato |
| Focus, costo di sostituzione pompa | Dichiara che il costo non è nei passaggi consultati | Limite corretto |
| Focus, consumi 1.0 EcoBoost | Intervalli combinato/urbano/extraurbano corretti | Dato recuperato; la frase finale sui limiti degli estratti è superflua |
| Civic Type R, telecomando che non funziona | Interferenze, condizioni operative, LED/batteria e concessionaria | Indicazioni documentate, causa non attribuita |
| SEAT Leon, lavaparabrezza che non spruzza | Livello, rabbocco, prodotto raccomandato e antigelo | Indicazioni documentate, nessuna diagnosi o pulizia inventata |

Sono otto scenari mirati, con nove messaggi complessivi dopo la modifica, non una misura
di affidabilità generale. Sono passati anche i 71 test locali già esistenti; questi non
dimostrano da soli la qualità delle risposte reali del modello.

## Punto aperto: sequenza della spia Ford

Nel medesimo input del verificatore compaiono due testi diversi:

- p. 249 (PDF 251): «lampeggia per un minuto circa, quindi resta accesa»;
- p. 251 (PDF 253), testo della tabella: «Inizialmente spia fissa seguita da una spia lampeggiante».

Il verificatore ha scelto la seconda formulazione, senza segnalare il conflitto con la prima.
Occorre controllare la pagina originale e l'estrazione della tabella prima di stabilire se
si tratta di un'incoerenza del manuale, di un problema di estrazione o di interpretazione.
Non è stata eseguita una verifica visiva del PDF in questa prova. Non correggere la sequenza
con una regola specifica per Ford o con conoscenze esterne al libretto.

Come richiesto dall'utente in caso di difficoltà importanti, il lavoro si ferma qui per
discutere questo punto. La proposta resta nel worktree di `dev`; `main` non è modificato.

## Riproduzione

`prova_risposte_parziali.py` usa il modello configurato nel `.env`, Qdrant persistente e
la classe `Conversazione`, senza la UI Streamlit. Le tracce salvano input e output dei
controlli strutturati. Per usare un `.env` esterno al worktree, impostare
`MANUALMATE_CONFIG_DIR` alla cartella del progetto principale. Il percorso dei manuali
è letto da `MANUALI_DIR`, se presente, altrimenti dalla cartella sorella del progetto.

Esempio dalla cartella contenente lo script:

```powershell
$env:MANUALMATE_CONFIG_DIR = 'C:/Users/grego/Desktop/Progetto FNC'
& 'C:/Users/grego/Desktop/Progetto FNC/.venv/Scripts/python.exe' -B -X utf8 prova_risposte_parziali.py report_parziali_dopo.json
```

Report: `report_parziali_prima.json`, `report_parziali_dopo.json` e
`report_parziali_altri_manuali.json`. Le tracce contengono testo delle fonti e risposte,
non la chiave API. La proposta e i risultati sono conservati sul branch `dev`;
non sono integrati in `main`.
