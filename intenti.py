"""Trasferisce il tema di una domanda a un altro libretto, senza i dettagli dell'auto."""

import json
import re

from pydantic import BaseModel, ValidationError

from catalogo import CATALOGO, Veicolo, normalizza
from osservabilita import span
from prompt import PROMPT_CAMBIO_AUTO
from strutturati import chiedi_strutturato


PREFISSO_CAMBIO_AUTO = "Cambio di veicolo (solo domande): "


class CambioVeicolo(BaseModel):
    veicolo_precedente: str
    domande: list[str]


class DomandaTrasferita(BaseModel):
    domanda_generale: str


def contesto_cambio_auto(veicolo: str, domande: tuple[str, ...]) -> str:
    return PREFISSO_CAMBIO_AUTO + CambioVeicolo(
        veicolo_precedente=veicolo, domande=list(domande),
    ).model_dump_json()


def leggi_cambio_auto(contesto: tuple[str, ...]) -> CambioVeicolo | None:
    if len(contesto) != 1 or not contesto[0].startswith(PREFISSO_CAMBIO_AUTO):
        return None
    try:
        return CambioVeicolo.model_validate_json(contesto[0][len(PREFISSO_CAMBIO_AUTO):])
    except ValidationError:
        return None


def trasferisci_domanda(client, cambio: CambioVeicolo, veicolo: Veicolo, messaggio: str) -> str | None:
    with span("ricostruzione-domanda-cambio-auto", "CHAIN", veicolo=veicolo.id):
        dati = chiedi_strutturato(
            client, modello=DomandaTrasferita, prompt=PROMPT_CAMBIO_AUTO, max_tokens=600,
            input=json.dumps({
                "auto_precedente": cambio.veicolo_precedente,
                "domande_precedenti": cambio.domande,
                "nuova_auto": veicolo.nome, "messaggio_attuale": messaggio,
            }, ensure_ascii=False),
        )
    if not isinstance(dati, DomandaTrasferita):
        return None
    domanda = " ".join(dati.domanda_generale.split())
    if not 8 <= len(domanda) <= 500:
        return None
    # Un nome di un altro modello nel risultato segnala un trasferimento non riuscito.
    if any(re.search(rf"\b{altro.pattern_nome}\b", normalizza(domanda))
           for altro in CATALOGO.values() if altro.id != veicolo.id):
        return None
    return domanda
