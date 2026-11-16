import re
from collections.abc import Callable
from dataclasses import dataclass

from assistente import Risposta
from catalogo import CATALOGO, normalizza


NOMI_AUTO = {
    "focus": r"(?:ford )?focus(?: cew)?",
    "civic": r"(?:honda )?civic(?: type r)?",
}
ANNI_MANUALI = {"focus": {"2014", "2015"}, "civic": {"2023"}}
RICHIESTA_AUTO = "Di quale auto si tratta? Ho i libretti di Ford Focus (CEW) e Honda Civic Type R."


@dataclass
class Conversazione:
    veicolo_id: str | None = None
    domanda_in_attesa: str | None = None
    chiarimenti: tuple[str, ...] = ()

    def rispondi(self, messaggio: str, consulta: Callable[[str, str, tuple[str, ...]], Risposta]) -> Risposta:
        testo = normalizza(messaggio)
        corrispondenze = [codice for codice, pattern in NOMI_AUTO.items() if re.search(rf"\b{pattern}\b", testo)]
        if len(corrispondenze) > 1:
            self.veicolo_id = None
            self.chiarimenti = ()
            self.domanda_in_attesa = messaggio
            return Risposta("veicolo_da_chiarire", "Quale dei due manuali vuoi consultare per questa domanda?")

        domanda = messaggio
        if corrispondenze:
            codice = corrispondenze[0]
            anni = set(re.findall(r"\b(?:19|20)\d{2}\b", testo))
            civic_diversa = codice == "civic" and re.search(r"\bcivic (?:non type r|type s|sport|e hev|hybrid)\b", testo)
            if civic_diversa or (anni and not anni <= ANNI_MANUALI[codice]):
                self.veicolo_id = None
                self.chiarimenti = ()
                veicolo = CATALOGO[codice]
                return Risposta("veicolo_da_chiarire", f"Per {veicolo.nome} ho questo libretto: {veicolo.edizione}. Quale auto vuoi consultare?")
            if codice != self.veicolo_id:
                self.chiarimenti = ()
            self.veicolo_id = codice
            solo_auto = re.fullmatch(
                rf"(?:(?:si|e|ho|guido|intendo|per|sulla|sull|una|la|mia|invece) )*{NOMI_AUTO[codice]}"
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

        if self.veicolo_id is None:
            gia_in_attesa = self.domanda_in_attesa is not None
            self.domanda_in_attesa = self.domanda_in_attesa or messaggio
            testo_risposta = (
                "Non ho riconosciuto il modello. I libretti disponibili sono Ford Focus (CEW) e Honda Civic Type R."
                if gia_in_attesa else RICHIESTA_AUTO
            )
            return Risposta("veicolo_da_chiarire", testo_risposta)

        # La domanda originale riparte appena arriva il modello. I chiarimenti tecnici restano legati all'auto.
        risposta = consulta(self.veicolo_id, domanda, self.chiarimenti)
        self.domanda_in_attesa = domanda if risposta.esito in {"errore", "indice_assente"} else None
        self.chiarimenti = (*self.chiarimenti, domanda)[-2:] if risposta.esito == "chiarimento" else ()
        return risposta
