import json
import re
from dataclasses import replace

from datapizza.agents import Agent
from datapizza.tools import tool
from datapizza.type import Chunk

from catalogo import CATALOGO, CIVIC, Veicolo, normalizza, riconosci_avviso
from config import MAX_TURNI_CONTESTO, MAX_QUERY_RICERCA
from fonti import (
    Fonte, PassaggioVerificabile, Riesame, Risposta, VerificaSintesi,
    _aggiungi_limite, _citazione_valida,
)
from indice import IndiceManuali
from intenti import leggi_cambio_auto, trasferisci_domanda
from osservabilita import richiesta, span, strumento
from prompt import CRITERI_COMPLETEZZA, PROMPT, PROMPT_RIESAME, PROMPT_VERIFICA_SINTESI
from recupero import FontiRichiesta
from strutturati import chiedi_strutturato


class Assistente:
    def __init__(self, indice: IndiceManuali, client):
        self.indice = indice
        self.client = client

    def rispondi(self, veicolo_id: str, domanda: str, *, contesto: tuple[str, ...] = ()) -> Risposta:
        with richiesta() as misura:
            veicolo = CATALOGO.get(veicolo_id)
            if veicolo is None:
                risposta = Risposta("bloccato", "Veicolo o edizione fuori catalogo. Controlla il manuale del tuo veicolo.")
            else:
                cambio = leggi_cambio_auto(contesto)
                if cambio is not None:
                    domanda_trasferita = trasferisci_domanda(self.client, cambio, veicolo, domanda)
                    if domanda_trasferita:
                        risposta = replace(self._consulta(veicolo, domanda_trasferita, ()),
                                           domanda_interpretata=domanda_trasferita)
                    else:
                        risposta = Risposta("chiarimento", f"Quale informazione vuoi cercare nel libretto di {veicolo.nome}?")
                else:
                    risposta = self._consulta(veicolo, domanda, contesto[-MAX_TURNI_CONTESTO:])
            misura["valore"] = risposta.esito
            return risposta

    def _consulta(self, veicolo: Veicolo, domanda: str, contesto: tuple[str, ...]) -> Risposta:
        atteso = riconosci_avviso(veicolo, domanda, contesto)
        testo = normalizza(domanda)
        parole = set(testo.split())
        olio_ambiguo = veicolo == CIVIC and atteso is None and "olio" in parole and (
            "spia" in parole or {"pressione", "livello"} <= parole
        )
        chiede_ubicazione = re.search(r"\b(?:dove|dov e|in quali punti)\b", testo)
        ubicazione_fusibili = "fusibili" in parole and (
            bool(chiede_ubicazione and {"scatola", "scatole"} & parole)
            or bool(re.fullmatch(r"dove (?:sono|si trovano|trovo) i fusibili", testo))
        )
        pagina_fusibili = None
        titolo_fusibili = None
        pagine_verificate = ()
        pila_telecomando = bool({"pila", "batteria"} & parole and ("telecomando" in parole or {"pila", "chiave"} <= parole))
        if veicolo.id == "focus" and pila_telecomando and (
            {"polo", "positivo", "orientato", "orientare", "monto"} & parole or "segno piu" in testo
        ):
            esclude_keyless = "senza apertura senza chiave" in testo or "senza keyless" in testo
            classica = bool({"classica", "classico", "tradizionale", "pieghevole"} & parole) or esclude_keyless
            keyless = not esclude_keyless and ("apertura senza chiave" in testo or "keyless" in parole)
            if not (classica or keyless):
                return Risposta("chiarimento", "Hai la chiave con telecomando classico o la versione con apertura senza chiave? Il verso della pila cambia.")
            classiche = (
                (36, "bottone al litio da tre volt cr2032", "La chiave con telecomando classico usa una pila CR2032 da 3 V."),
                (37, "simbolo rivolto verso l alto", "Monta la pila con il segno + rivolto verso l’alto."),
            ) if classica else ()
            senza_chiave = (
                (39, "3v cr 2032 con il polo positivo rivolto verso il basso", "Per l’apertura senza chiave serve una CR2032 da 3 V, con il polo positivo verso il basso."),
            ) if keyless else ()
            pagine_verificate = classiche + senza_chiave
        if ubicazione_fusibili and veicolo.id == "focus":
            pagina_fusibili, titolo_fusibili = 207, "ubicazione scatola portafusibili"
        elif ubicazione_fusibili and veicolo.id == "audi":
            pagina_fusibili, titolo_fusibili = 381, "the fuses are located behind a cover"
        elif veicolo == CIVIC:
            seguito = bool(parole) and any("fusibili" in normalizza(turno).split() for turno in contesto) and parole <= {
                "quella", "la", "nel", "in", "nella", "nell", "del", "dell", "vano", "motore", "abitacolo", "interna", "e", "invece", "davanti",
            }
            if ubicazione_fusibili or seguito or {"entrambe", "fusibili"} <= parole:
                motore = "vano motore" in testo or "cofano" in parole or (seguito and "motore" in parole)
                interna = bool({"abitacolo", "interna", "cruscotto"} & parole)
                if not (motore or interna):
                    return Risposta("chiarimento", "Intendi la scatola dei fusibili nel vano motore o quella nell’abitacolo?")
                if motore != interna:
                    pagina_fusibili, titolo_fusibili = (
                        (631, "scatola fusibili vano motore") if motore else (633, "scatola fusibili interna")
                    )
                else:
                    pagine_verificate = (
                        (631, "situata accanto alla batteria", "Quella nel vano motore è accanto alla batteria."),
                        (633, "situata sotto il cruscotto", "Quella nell’abitacolo è sotto il cruscotto."),
                    )
        if pagine_verificate:
            return self._risposta_verificata(veicolo, pagine_verificate)
        # L'app sceglie il manuale prima che il modello possa proporre una ricerca.
        collezione = self.indice.collezione_attiva(veicolo) if atteso is not None else None
        if atteso is not None and collezione is None:
            return Risposta("indice_assente", f"Manuale di {veicolo.nome} da indicizzare. Avvia main.py --indicizza.")
        recupero = FontiRichiesta(self.indice, veicolo)
        fonti_recuperate = recupero.fonti
        fonti_confermate: tuple[Chunk, ...] = ()
        sintesi_confermata = None
        ricerca_eseguita = False
        query_eseguite: set[str] = set()
        citazioni_rifiutate: list[dict[str, str]] = []
        chiarimento = None
        limite = None
        indice_assente = False

        # I tool condividono solo le fonti recuperate durante questa richiesta.
        @tool
        def cerca_manuale(query: str, query_complementare: str = "", altre_query: list[str] | None = None) -> str:
            """Cerca nel libretto quando il componente è identificato. Se è ambiguo, usa prima chiedi_chiarimento. Per richieste composte usa query_complementare e altre_query, fino a tre ricerche distinte."""
            nonlocal ricerca_eseguita, indice_assente, collezione
            with strumento("cerca_manuale") as traccia:
                if olio_ambiguo:
                    traccia.set_attribute("guardrail", "avviso_ambiguo")
                    return "Chiarisci se l'avviso indica pressione o livello dell'olio."
                if ricerca_eseguita:
                    return "La ricerca è già stata eseguita. Usa cita_fonte o cita_fonti con gli identificativi pertinenti."
                if collezione is None:
                    collezione = self.indice.collezione_attiva(veicolo)
                if collezione is None:
                    indice_assente = True
                    return "Il manuale non è ancora indicizzato."
                testo_query = query[:500].strip() or domanda[:500]
                if atteso:
                    testo_query = f"{atteso.titolo}\n{testo_query}"
                elif titolo_fusibili:
                    # La ricerca include la dicitura del costruttore per la posizione richiesta.
                    testo_query = f"{titolo_fusibili}\n{testo_query}"
                query_eseguite.add(normalizza(testo_query))
                ricerche = [self.indice.cerca(veicolo, collezione, testo_query, solo_avvisi=atteso is not None)]
                if atteso is None:
                    for proposta in (query_complementare, *(altre_query or [])):
                        complemento = proposta[:500].strip()
                        if not complemento or normalizza(complemento) in query_eseguite:
                            continue
                        if len(query_eseguite) >= MAX_QUERY_RICERCA:
                            break
                        query_eseguite.add(normalizza(complemento))
                        ricerche.append(self.indice.cerca(veicolo, collezione, complemento))
                ricerca_eseguita = True
                recupero.aggiungi(collezione, ricerche, completa_prime=0 if atteso else 3)
                # L'output del tool diventa contesto per la successiva chiamata al modello.
                return json.dumps([
                    {"id": hit.metadata["fonte"], "pagina": hit.metadata["pagina"],
                     "sezione": hit.metadata["sezione"], "testo": hit.text}
                    for hit in fonti_recuperate.values()
                ], ensure_ascii=False)

        @tool(end=True)
        def chiedi_chiarimento(tipo: str = "sintomo", domanda: str = "") -> str:
            """Prima della ricerca chiarisci il componente se il nome può indicarne diversi. Fai una sola domanda breve in italiano sul dettaglio mancante. Tipo: spia, versione, condizioni o sintomo."""
            nonlocal chiarimento
            with strumento("chiedi_chiarimento"):
                domande = {
                    "spia": "Che cosa compare sul quadro? Puoi descrivere il simbolo o riportare il messaggio.",
                    "versione": "Quale versione o allestimento della tua auto indica il libretto?",
                    "condizioni": "Quando succede il problema? Descrivi cosa stavi facendo e in quali condizioni.",
                    "sintomo": "Che cosa noti di preciso e quando succede?",
                }
                domanda = " ".join(domanda.split())
                # Conserva le domande con più frasi o esempi, normalizzando gli spazi.
                chiarimento = domanda if 8 <= len(domanda) <= 400 and "?" in domanda else domande.get(tipo, domande["sintomo"])
                return "Richiesta di chiarimento registrata."

        @tool(end=True)
        def segnala_limite(motivo: str = "") -> str:
            """Spiega con una frase breve in italiano quale dato della domanda non hai trovato nel libretto, senza inventarlo."""
            nonlocal limite
            with strumento("segnala_limite"):
                motivo = motivo.strip()
                if 0 < len(motivo) <= 280:
                    limite = motivo
                return "Nessuna indicazione documentata per questa richiesta."

        @tool(end=True)
        def cita_fonte(fonte_id: str, citazione: str = "", sintesi: str = "", parte_non_documentata: str = "") -> str:
            """Allega la citazione letterale del passaggio e una breve risposta in italiano basata solo su di esso."""
            nonlocal fonti_confermate, sintesi_confermata
            with strumento("cita_fonte") as traccia:
                hit = fonti_recuperate.get(fonte_id)
                if hit and (fonte_id == atteso.id if atteso else _citazione_valida(hit, citazione)):
                    fonti_confermate = (hit,)
                    sintesi = sintesi.strip()
                    if atteso is None and 0 < len(sintesi) <= 800:
                        sintesi_confermata = _aggiungi_limite(sintesi, parte_non_documentata)
                    else:
                        sintesi_confermata = None
                    traccia.set_attribute("fonte", fonte_id)
                    return "Fonte verificata."
                traccia.set_attribute("guardrail", "fonte_non_coerente")
                if hit is not None:
                    citazioni_rifiutate.append({
                        "fonte_id": fonte_id, "citazione": citazione,
                        "motivo": "Serve un estratto letterale di almeno quattro parole e 18 caratteri, oppure l'intera riga numerica con etichetta di almeno 18 caratteri. Una cella isolata non basta.",
                    })
                return "Fonte rifiutata."

        @tool(end=True)
        def cita_fonti(fonti_id: list[str], citazioni: list[str], frasi: list[str], parte_non_documentata: str = "") -> str:
            """Combina 2 o 3 passaggi. Ogni ID ha, nello stesso ordine, la sua citazione letterale e la sua frase in italiano."""
            nonlocal fonti_confermate, sintesi_confermata
            with strumento("cita_fonti") as traccia:
                hits = [fonti_recuperate.get(identificativo) for identificativo in fonti_id]
                if (atteso is not None or not 2 <= len(set(fonti_id)) == len(hits) <= 3
                        or len(hits) != len(citazioni) or len(hits) != len(frasi)
                        or not all(_citazione_valida(hit, citazione) and 0 < len(frase.strip()) <= 700
                                   for hit, citazione, frase in zip(hits, citazioni, frasi))):
                    traccia.set_attribute("guardrail", "fonti_non_coerenti")
                    return "Fonti rifiutate."
                fonti_confermate = tuple(hits)
                sintesi = "\n\n".join(
                    f"{frase.strip()} ({Fonte.da_chunk(hit).riferimento})" for hit, frase in zip(hits, frasi, strict=True)
                )
                sintesi_confermata = _aggiungi_limite(sintesi, parte_non_documentata)
                traccia.set_attribute("fonti", fonti_id)
                return "Fonti verificate."

        agente = Agent(
            name="assistente_manualistica", client=self.client, system_prompt=PROMPT,
            tools=[cerca_manuale, chiedi_chiarimento, segnala_limite, cita_fonte, cita_fonti], max_steps=4, stream=False,
        )
        with span("agente", "AGENT", veicolo=veicolo.id) as traccia:
            traccia.set_attribute("avviso", atteso.id if atteso else "non_identificato")
            # Datapizza passa il JSON come turno utente e gestisce il ciclo di chiamate ai tool.
            agente.run(json.dumps({
                "veicolo": veicolo.nome, "edizione": veicolo.edizione, "lingua_manuale": veicolo.lingua,
                "domanda": domanda, "avviso_riconosciuto": atteso.titolo if atteso else None,
                "turni_precedenti": contesto, "sezione_riconosciuta": titolo_fusibili,
            }, ensure_ascii=False), tool_choice="required_first")

        if olio_ambiguo:
            return Risposta("chiarimento", "Sul quadro compare un avviso di bassa pressione dell’olio o di basso livello?")
        if indice_assente:
            return Risposta("indice_assente", f"Manuale di {veicolo.nome} da indicizzare. Avvia main.py --indicizza.")
        if pagina_fusibili is not None and titolo_fusibili:
            # La sezione verificata riunisce le ubicazioni. Le tabelle dei singoli fusibili sono pagine diverse.
            ubicazione = next((hit for hit in fonti_recuperate.values()
                               if hit.metadata["pagina_pdf"] == pagina_fusibili
                               and titolo_fusibili in normalizza(hit.text)), None)
            if ubicazione is None or ubicazione not in fonti_confermate:
                sintesi_confermata = None
                fonti_confermate = (ubicazione,) if ubicazione else ()
        elif not fonti_confermate and atteso is None and not chiarimento and ricerca_eseguita:
            riesame = None
            if len(fonti_recuperate) >= 3:
                with span("riesame-fonti", "CHAIN", veicolo=veicolo.id):
                    riesame = self._riesamina(domanda, contesto, fonti_recuperate, citazioni_rifiutate)
            # Le parole originali possono contenere il dettaglio perso nella query dell'agente.
            query_originale = "\n".join((domanda, *contesto))[:500].strip()
            if riesame is None and collezione is not None and normalizza(query_originale) not in query_eseguite:
                with span("ricerca-di-riserva", "CHAIN", veicolo=veicolo.id) as traccia:
                    nuove = recupero.cerca_nuove(collezione, query_originale)
                    traccia.set_attribute("pagine_nuove", len(nuove))
                    if nuove:
                        riesame = self._riesamina(domanda, contesto, nuove)
            if riesame is not None:
                fonti_confermate, sintesi_confermata = riesame
        fonti = tuple(Fonte.da_chunk(hit) for hit in fonti_recuperate.values())
        if not fonti_confermate:
            if chiarimento:
                return Risposta(
                    "chiarimento", chiarimento,
                    fonti_recuperate=fonti, ricerca_eseguita=ricerca_eseguita,
                )
            return Risposta(
                "fonte_assente",
                limite or "Non ho trovato nel libretto un passaggio che risponda alla tua domanda.",
                fonti_recuperate=fonti, ricerca_eseguita=ricerca_eseguita,
            )
        # Anche una fonte scelta oltre le prime tre deve portare alla verifica tutta la pagina.
        if atteso is None and collezione is not None:
            fonti_confermate = recupero.completa_citate(collezione, fonti_confermate)
        # La risposta mostra la formulazione del costruttore e aggiunge il riferimento verificato.
        estratti = "\n\n".join(hit.text for hit in fonti_confermate)
        sintesi = sintesi_confermata
        if veicolo.id == "audi" and len(fonti_confermate) == 1 and pagina_fusibili == fonti_confermate[0].metadata["pagina_pdf"]:
            # Ricomponi le parole spezzate dall'OCR prima di verificare entrambe le posizioni.
            estratto = normalizza(estratti.replace("-\n", ""))
            if all(posizione in estratto for posizione in (
                "behind a cover in the steering column area",
                "under a cover on the left side of the engine compartment",
            )):
                sintesi = (
                    "Il libretto dell’Audi A3 8V indica due posizioni per i fusibili:\n"
                    "- Nell’abitacolo, dietro un coperchio nella zona del piantone dello sterzo (fig. 296).\n"
                    "- Nel vano motore, sotto un coperchio sul lato sinistro (fig. 297)."
                )
                return self._documentata(veicolo, fonti_confermate, fonti, sintesi)
        if atteso is None:
            verifica = self._verifica_sintesi(domanda, contesto, fonti_confermate, sintesi or "")
            if verifica.esito in {"fonte_non_pertinente", "fonte_insufficiente", "non_verificabile"}:
                # Una citazione autentica non prova che la pagina risponda alla domanda.
                # Un solo recupero della risposta usa le altre fonti già disponibili.
                escluse = {hit.metadata["pagina_pdf"] for hit in fonti_confermate}
                candidate = {
                    identificativo: hit for identificativo, hit in fonti_recuperate.items()
                    if verifica.esito == "non_verificabile" or hit.metadata["pagina_pdf"] not in escluse
                }
                if candidate:
                    with span("riesame-risposta", "CHAIN", motivo=verifica.esito) as traccia:
                        traccia.set_attribute("pagine_scelte", sorted(escluse))
                        traccia.set_attribute("pagine_candidate", sorted({hit.metadata["pagina_pdf"] for hit in candidate.values()}))
                        proposta = self._riesamina(domanda, contesto, candidate)
                        traccia.set_attribute("proposta_recuperata", proposta is not None)
                        if proposta is not None:
                            nuove_fonti, nuova_sintesi = proposta
                            if collezione is not None:
                                nuove_fonti = recupero.completa_citate(collezione, nuove_fonti)
                            nuova_verifica = self._verifica_sintesi(domanda, contesto, nuove_fonti, nuova_sintesi)
                            fonti_confermate, verifica = nuove_fonti, nuova_verifica
            if verifica.esito not in {"confermata", "corretta"}:
                return Risposta(
                    "fonte_assente", "Non sono riuscito a verificare una risposta alla tua domanda nei passaggi consultati.",
                    fonti_recuperate=fonti, ricerca_eseguita=ricerca_eseguita,
                )
            sintesi = verifica.sintesi or None
        return self._documentata(veicolo, fonti_confermate, fonti, sintesi)

    def _verifica_sintesi(
        self, domanda: str, contesto: tuple[str, ...], fonti: tuple[Chunk, ...], sintesi: str,
    ) -> VerificaSintesi:
        with span("verifica-sintesi", "CHAIN") as traccia:
            verifica = chiedi_strutturato(
                self.client,
                input=json.dumps({
                    "domanda": domanda, "turni_precedenti": contesto, "sintesi": sintesi,
                    "estratti": [{"id": hit.metadata["fonte"], "riferimento": Fonte.da_chunk(hit).riferimento, "testo": hit.text} for hit in fonti],
                }, ensure_ascii=False),
                modello=VerificaSintesi, prompt=PROMPT_VERIFICA_SINTESI, max_tokens=1500,
            )
            if isinstance(verifica, VerificaSintesi):
                if verifica.esito == "confermata" and not verifica.omissioni_rilevanti and not verifica.sintesi.strip():
                    traccia.set_attribute("esito", "confermata")
                    return verifica.model_copy(update={"sintesi": sintesi})
                if verifica.esito == "corretta" and 0 < len(verifica.sintesi.strip()) <= 2400:
                    traccia.set_attribute("esito", "corretta")
                    return verifica.model_copy(update={"sintesi": verifica.sintesi.strip()})
                if verifica.esito in {"fonte_non_pertinente", "fonte_insufficiente"}:
                    traccia.set_attribute("esito", verifica.esito)
                    return verifica.model_copy(update={"sintesi": ""})
            # L'assenza di verifica non deve trasformarsi in una risposta documentata.
            traccia.set_attribute("esito", "non_verificabile")
            return VerificaSintesi(omissioni_rilevanti=[], esito="non_verificabile", sintesi="")

    def _riesamina(self, domanda: str, contesto: tuple[str, ...], recuperate: dict[str, Chunk],
                   citazioni_rifiutate: list[dict[str, str]] | None = None):
        dati = self._richiedi_riesame(domanda, contesto, recuperate, citazioni_rifiutate or [])
        if not isinstance(dati, Riesame) or not 1 <= len(dati.risposte) <= 3:
            return None
        rifiutate = [
            {"fonte_id": riga.fonte_id, "citazione": riga.citazione,
             "motivo": "Serve una sequenza letterale di almeno quattro parole e 18 caratteri, oppure un'intera riga con etichetta e dato numerico di almeno 18 caratteri."}
            for riga in dati.risposte if not _citazione_valida(recuperate.get(riga.fonte_id), riga.citazione)
        ]
        if len(rifiutate) == len(dati.risposte):
            # Un solo tentativo di riparazione con gli stessi passaggi e il motivo del rifiuto.
            with span("correzione-citazioni", "CHAIN"):
                dati = self._richiedi_riesame(domanda, contesto, recuperate, rifiutate)
        if not isinstance(dati, Riesame) or not 1 <= len(dati.risposte) <= 3:
            return None
        fonti = {}
        frasi = []
        for riga in dati.risposte:
            hit = recuperate.get(riga.fonte_id)
            if not _citazione_valida(hit, riga.citazione) or not 0 < len(riga.frase.strip()) <= 700:
                continue
            fonti[riga.fonte_id] = hit
            frasi.append(f"{riga.frase.strip()} ({Fonte.da_chunk(hit).riferimento})")
        if not fonti:
            return None
        sintesi = _aggiungi_limite("\n\n".join(frasi), dati.parte_non_documentata)
        if len(frasi) < len(dati.risposte):
            sintesi += "\n\nAlcuni dettagli non sono stati verificati nel libretto."
        return tuple(fonti.values()), sintesi

    def _richiedi_riesame(
        self, domanda: str, contesto: tuple[str, ...], recuperate: dict[str, Chunk],
        citazioni_rifiutate: list[dict[str, str]],
    ) -> Riesame | None:
        return chiedi_strutturato(
            self.client,
            input=json.dumps({"domanda": domanda, "turni_precedenti": contesto, "passaggi": [
                {"id": id_fonte, "testo": hit.text} for id_fonte, hit in recuperate.items()
            ], "citazioni_rifiutate": citazioni_rifiutate}, ensure_ascii=False),
            modello=Riesame, prompt=PROMPT_RIESAME, max_tokens=1600,
        )

    def _risposta_verificata(self, veicolo: Veicolo, pagine: tuple[tuple[int, str, str], ...]) -> Risposta:
        collezione = self.indice.collezione_attiva(veicolo)
        if collezione is None:
            return Risposta("indice_assente", f"Manuale di {veicolo.nome} da indicizzare. Avvia main.py --indicizza.")
        hits = []
        righe = []
        with strumento("cerca_manuale"):
            for pagina_pdf, evidenza, frase in pagine:
                hit = self.indice.cerca_pagina(veicolo, collezione, pagina_pdf)
                if hit is None or evidenza not in normalizza(hit.text):
                    return Risposta("fonte_assente", "Non ho trovato nel libretto tutti i dettagli richiesti.", ricerca_eseguita=True)
                hits.append(hit)
                righe.append(f"{frase} ({Fonte.da_chunk(hit).riferimento})")
        return self._documentata(veicolo, tuple(hits), tuple(map(Fonte.da_chunk, hits)), "\n\n".join(righe))

    @staticmethod
    def _documentata(veicolo: Veicolo, hits: tuple[Chunk, ...], fonti: tuple[Fonte, ...], sintesi: str | None) -> Risposta:
        citate = tuple(map(Fonte.da_chunk, hits))
        riferimenti = ", ".join(dict.fromkeys(fonte.riferimento for fonte in citate))
        estratti = "\n\n".join(hit.text for hit in hits)
        risposta = f"{estratti}\n\nFonte: {veicolo.nome}, {veicolo.edizione}, {riferimenti}."
        return Risposta(
            "risposta", risposta, fonti_recuperate=fonti,
            fonte_citata=citate[0], fonti_aggiuntive=citate[1:],
            ricerca_eseguita=True, sintesi=sintesi,
        )
