import re
from collections.abc import Callable
from dataclasses import dataclass

from assistente import Risposta
from catalogo import CATALOGO, anni_del_modello, normalizza
from config import MAX_TURNI_CONTESTO
from intenti import contesto_cambio_auto
from osservabilita import richiesta


NOMI_AUTO = {codice: veicolo.pattern_nome for codice, veicolo in CATALOGO.items()}
ANNI_MANUALI = {codice: set(veicolo.anni_edizione) for codice, veicolo in CATALOGO.items()}
MODELLI_DIVERSI = {codice: veicolo.pattern_modelli_diversi for codice, veicolo in CATALOGO.items()
                   if veicolo.pattern_modelli_diversi}
NOMI_CATALOGO = ", ".join(veicolo.nome for veicolo in CATALOGO.values())
RICHIESTA_AUTO = f"Di quale auto si tratta? Ho questi libretti: {NOMI_CATALOGO}."
PRESENTAZIONE = (
    "Posso aiutarti a orientarti nel libretto della tua auto. Puoi chiedermi cosa significa una spia, "
    "dove si trovano i fusibili o come usare un comando. Ti indico anche la pagina da consultare. "
    f"Ho i libretti di {NOMI_CATALOGO}."
)
SALUTI = r"ciao|salve|buongiorno|buonasera|ehi|hey"
DOMANDE_SULL_ASSISTENTE = (
    r"(?:(?:mi dici|vorrei sapere|vorrei capire) )?(?:chi sei|come funzioni|come funziona(?: (?:l app|questa chat|manual mate))?"
    r"|(?:che )?cosa (?:sai|puoi) fare(?: per me)?|(?:come|in che modo) puoi aiutarmi|come mi puoi aiutare"
    r"|(?:come|in che modo) mi aiuti|come posso usarti|puoi aiutarmi|mi puoi aiutare|mi aiuti|mi dai una mano"
    r"|(?:che|quali) (?:domande|informazioni) (?:posso (?:farti|chiederti)|ti posso (?:fare|chiedere))"
    r"|(?:mi (?:fai|dai) )?(?:degli |alcuni )?esempi di domande(?: che posso farti)?"
    r"|(?:che|quali) (?:libretti|manuali|auto|modelli) (?:hai|conosci|supporti|puoi consultare|sono disponibili)(?: in catalogo)?)"
)


@dataclass
class Conversazione:
    veicolo_id: str | None = None
    domanda_in_attesa: str | None = None
    chiarimenti: tuple[str, ...] = ()
    turni_documentati: tuple[str, ...] = ()
    ultimo_chiarimento: str | None = None

    def rispondi(self, messaggio: str, consulta: Callable[[str, str, tuple[str, ...]], Risposta]) -> Risposta:
        with richiesta() as misura:
            risposta = self._rispondi(messaggio, consulta)
            misura["valore"] = risposta.esito
            return risposta

    def _rispondi(self, messaggio: str, consulta: Callable[[str, str, tuple[str, ...]], Risposta]) -> Risposta:
        testo = normalizza(messaggio)
        if re.fullmatch(SALUTI, testo):
            invito = "Dimmi pure cosa vuoi sapere sulla tua auto." if self.veicolo_id else PRESENTAZIONE
            return Risposta("conversazione", f"Ciao! {invito}")
        if re.fullmatch(rf"(?:(?:{SALUTI}) )?{DOMANDE_SULL_ASSISTENTE}(?: (?:grazie|per favore))?", testo):
            return Risposta("conversazione", PRESENTAZIONE)
        if re.fullmatch(r"(?:ok |va bene )?grazie(?: mille| davvero)?|perfetto|gentilissimo|a presto", testo):
            return Risposta("conversazione", "Di nulla! Se ti viene in mente un’altra domanda, chiedimi pure.")

        if re.match(r"^(?:cambio argomento|cambiamo argomento|altra domanda|un altra domanda|nuova domanda|a proposito d altro)\b", testo):
            self.domanda_in_attesa = None
            self.chiarimenti = ()
            self.turni_documentati = ()
            self.ultimo_chiarimento = None

        corrispondenze = [codice for codice, pattern in NOMI_AUTO.items() if re.search(rf"\b{pattern}\b", testo)]
        if len(corrispondenze) > 1:
            self.veicolo_id = None
            self.chiarimenti = ()
            self.turni_documentati = ()
            self.ultimo_chiarimento = None
            self.domanda_in_attesa = messaggio
            return Risposta("veicolo_da_chiarire", "Quale manuale vuoi consultare per questa domanda?")

        domanda = messaggio
        dettagli_veicolo = ()
        trasferimento = False
        if corrispondenze:
            codice = corrispondenze[0]
            anni = anni_del_modello(testo, CATALOGO[codice])
            modello_diverso = codice in MODELLI_DIVERSI and re.search(MODELLI_DIVERSI[codice], testo)
            if modello_diverso or (anni and not anni <= ANNI_MANUALI[codice]):
                if self.veicolo_id is not None:
                    self.domanda_in_attesa = None
                self.veicolo_id = None
                self.chiarimenti = ()
                self.turni_documentati = ()
                self.ultimo_chiarimento = None
                veicolo = CATALOGO[codice]
                return Risposta("veicolo_da_chiarire", f"Il libretto disponibile è per {veicolo.nome}, {veicolo.edizione}. Per il modello o l’anno che hai scritto serve il suo libretto. Quale auto vuoi consultare?")
            attende_modello = self.veicolo_id is None and self.domanda_in_attesa is not None
            auto_precedente = self.veicolo_id
            domande_precedenti = self.chiarimenti or self.turni_documentati
            if codice != self.veicolo_id:
                if self.veicolo_id is not None:
                    self.domanda_in_attesa = None
                self.chiarimenti = ()
                self.turni_documentati = ()
                self.ultimo_chiarimento = None
            self.veicolo_id = codice
            selezione_auto = re.fullmatch(
                rf"(?:(?:si|e|ho|guido|intendo|per|su|sul|sulla|sull|nel|nella|nell|un|una|la|mia|invece|anche|ad esempio|per esempio) )*{NOMI_AUTO[codice]}"
                r"(?: (?:del |anno )?(?:19|20)\d{2})?(?: grazie)?",
                testo,
            )
            aggiunge_dettagli = attende_modello and not selezione_auto and "?" not in messaggio and not re.search(
                r"\b(?:che|come|dove|quand[oi]|quant[oaie]|qual[ei]|cosa|perche|vorrei|mi (?:dici|spieghi|serve))\b", testo,
            )
            if selezione_auto or aggiunge_dettagli:
                trasferimento = bool(
                    selezione_auto and auto_precedente and codice != auto_precedente
                    and domande_precedenti and re.search(r"\b(?:invece|anche|e|per|su|sul|sulla|sull|nel|nella|nell)\b", testo)
                )
                if trasferimento:
                    dettagli_veicolo = (contesto_cambio_auto(auto_precedente, domande_precedenti),)
                elif self.domanda_in_attesa is None:
                    return Risposta("veicolo_selezionato", f"Userò il libretto di {CATALOGO[codice].nome}. Cosa vuoi sapere?")
                else:
                    domanda = self.domanda_in_attesa
                if aggiunge_dettagli:
                    dettagli_veicolo = (messaggio,)
        elif re.match(r"^(?:e |invece |e invece )sull[ae] (?!mia\b|stessa\b)|^guido un[ao] |^ho cambiato auto\b", testo):
            self.domanda_in_attesa = None
            self.veicolo_id = None
            self.chiarimenti = ()
            self.turni_documentati = ()
            self.ultimo_chiarimento = None

        if self.veicolo_id is None:
            gia_in_attesa = self.domanda_in_attesa is not None
            self.domanda_in_attesa = self.domanda_in_attesa or messaggio
            testo_risposta = (
                f"Non ho riconosciuto il modello. I libretti disponibili sono {NOMI_CATALOGO}."
                if gia_in_attesa else RICHIESTA_AUTO
            )
            return Risposta("veicolo_da_chiarire", testo_risposta)

        # La domanda originale riparte appena arriva il modello. I chiarimenti tecnici restano legati all'auto.
        # Anche una contestazione o un richiamo breve può dipendere dal tema precedente.
        # Il modello distingue i nuovi argomenti: non deduciamo questa relazione dal prefisso.
        contesto = self.chiarimenti or dettagli_veicolo or self.turni_documentati
        contesto_consulta = contesto
        if self.ultimo_chiarimento:
            # Conserva tema e dettagli recenti, riservando uno spazio alla domanda
            # dell'assistente cui l'utente sta rispondendo (es. «benzina»).
            recenti = contesto[:1] + contesto[1:][-(MAX_TURNI_CONTESTO - 2):]
            contesto_consulta = (*recenti, f"Chiarimento precedente dell'assistente: {self.ultimo_chiarimento}")
        risposta = consulta(self.veicolo_id, domanda, contesto_consulta)
        if trasferimento:
            # Dal prossimo turno resta solo la domanda ricostruita per la nuova auto.
            contesto = ()
            dettagli_veicolo = ()
            domanda = risposta.domanda_interpretata or messaggio
        self.ultimo_chiarimento = risposta.testo if risposta.esito == "chiarimento" else None
        self.domanda_in_attesa = domanda if risposta.esito in {"errore", "indice_assente"} else None
        if risposta.esito in {"chiarimento", "fonte_assente", "errore", "indice_assente"}:
            # Conserva il primo turno del tema e gli ultimi dettagli distinti anche dopo una ricerca a vuoto.
            if dettagli_veicolo:
                contesto = (domanda, *contesto)
            elif normalizza(domanda) not in {normalizza(turno) for turno in contesto}:
                contesto = (*contesto, domanda)
            self.chiarimenti = contesto[:1] + contesto[1:][-(MAX_TURNI_CONTESTO - 1):]
        else:
            self.chiarimenti = ()
        if risposta.esito == "risposta":
            self.turni_documentati = (*contesto, domanda)[-MAX_TURNI_CONTESTO:]
        return risposta
