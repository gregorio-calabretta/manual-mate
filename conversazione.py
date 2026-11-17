import re
from collections.abc import Callable
from dataclasses import dataclass

from assistente import Risposta
from catalogo import CATALOGO, normalizza
from osservabilita import richiesta


NOMI_AUTO = {
    "focus": r"(?:ford )?focus(?: cew)?",
    "civic": r"(?:honda )?civic(?: type r)?",
    "audi": r"(?:audi )?a3(?: 8 ?v)?",
}
ANNI_MANUALI = {"focus": {"2014", "2015"}, "civic": {"2023"}, "audi": {"2019"}}
MODELLI_DIVERSI = {
    "civic": r"\bcivic (?:non type r|type s|sport|e hev|hybrid)\b",
    "audi": r"\ba3 (?:8 ?[lpys]|non 8 ?v)\b",
}
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
    r"|(?:che|quali) (?:libretti|manuali|auto|modelli) (?:hai|conosci|supporti|puoi consultare|sono disponibili)(?: in catalogo)?)"
)


@dataclass
class Conversazione:
    veicolo_id: str | None = None
    domanda_in_attesa: str | None = None
    chiarimenti: tuple[str, ...] = ()
    turni_documentati: tuple[str, ...] = ()

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

        corrispondenze = [codice for codice, pattern in NOMI_AUTO.items() if re.search(rf"\b{pattern}\b", testo)]
        if len(corrispondenze) > 1:
            self.veicolo_id = None
            self.chiarimenti = ()
            self.turni_documentati = ()
            self.domanda_in_attesa = messaggio
            return Risposta("veicolo_da_chiarire", "Quale manuale vuoi consultare per questa domanda?")

        domanda = messaggio
        if corrispondenze:
            codice = corrispondenze[0]
            anni = set(re.findall(r"\b(?:19|20)\d{2}\b", testo))
            modello_diverso = codice in MODELLI_DIVERSI and re.search(MODELLI_DIVERSI[codice], testo)
            if modello_diverso or (anni and not anni <= ANNI_MANUALI[codice]):
                self.veicolo_id = None
                self.chiarimenti = ()
                self.turni_documentati = ()
                veicolo = CATALOGO[codice]
                return Risposta("veicolo_da_chiarire", f"Il libretto disponibile è per {veicolo.nome}, {veicolo.edizione}. Per il modello o l’anno che hai scritto serve il suo libretto. Quale auto vuoi consultare?")
            if codice != self.veicolo_id:
                self.chiarimenti = ()
                self.turni_documentati = ()
            self.veicolo_id = codice
            solo_auto = re.fullmatch(
                rf"(?:(?:si|e|ho|guido|intendo|per|sulla|sull|un|una|la|mia|invece) )*{NOMI_AUTO[codice]}"
                r"(?: (?:del |anno )?(?:19|20)\d{2})?(?: grazie)?",
                testo,
            )
            if solo_auto:
                if self.domanda_in_attesa is None:
                    return Risposta("veicolo_selezionato", f"Userò il libretto di {CATALOGO[codice].nome}. Cosa vuoi sapere?")
                domanda = self.domanda_in_attesa
        elif re.match(r"^(?:e |invece |e invece )sull[ae] (?!mia\b|stessa\b)|^guido un[ao] |^ho cambiato auto\b", testo):
            self.veicolo_id = None
            self.chiarimenti = ()
            self.turni_documentati = ()

        if self.veicolo_id is None:
            gia_in_attesa = self.domanda_in_attesa is not None
            self.domanda_in_attesa = self.domanda_in_attesa or messaggio
            testo_risposta = (
                f"Non ho riconosciuto il modello. I libretti disponibili sono {NOMI_CATALOGO}."
                if gia_in_attesa else RICHIESTA_AUTO
            )
            return Risposta("veicolo_da_chiarire", testo_risposta)

        # La domanda originale riparte appena arriva il modello. I chiarimenti tecnici restano legati all'auto.
        contesto = self.chiarimenti
        if not contesto and re.match(r"^(?:e\b|quell[ao]\b|in quel caso\b|perche\b)", testo):
            contesto = self.turni_documentati
        risposta = consulta(self.veicolo_id, domanda, contesto)
        self.domanda_in_attesa = domanda if risposta.esito in {"errore", "indice_assente"} else None
        self.chiarimenti = (*contesto, domanda)[-2:] if risposta.esito == "chiarimento" else ()
        if risposta.esito == "risposta":
            self.turni_documentati = (*contesto, domanda)[-2:]
        return risposta
