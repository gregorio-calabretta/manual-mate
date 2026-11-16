import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from assistente import Assistente, Fonte
from config import CHUNK_MAX_CHAR, CHUNK_OVERLAP


class Caso(BaseModel):
    # Il gold set fissa l'esito atteso prima di eseguire la prova.
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    veicolo: str = Field(min_length=1)
    domanda: str = Field(min_length=1)
    esito_atteso: Literal["risposta", "chiarimento", "bloccato", "fonte_assente"]
    fonte_attesa: str | None = Field(default=None, min_length=1)
    pagina_attesa: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def verifica_fonte_attesa(self):
        if self.esito_atteso == "risposta":
            if self.pagina_attesa is None:
                raise ValueError("Una risposta documentale richiede la pagina attesa.")
        elif self.fonte_attesa is not None or self.pagina_attesa is not None:
            raise ValueError("Un chiarimento o un blocco non ha una fonte attesa.")
        return self


def corrisponde(fonte: Fonte | None, caso: Caso) -> bool:
    # Una pagina può avere più chunk pertinenti. Gli avvisi già verificati mantengono un ID preciso.
    return bool(fonte and fonte.pagina == caso.pagina_attesa
                and (caso.fonte_attesa is None or fonte.id == caso.fonte_attesa))


def valuta(assistente: Assistente, percorso: Path, destinazione: Path) -> bool:
    casi = TypeAdapter(list[Caso]).validate_json(percorso.read_text(encoding="utf-8"))
    if not casi or len({caso.id for caso in casi}) != len(casi):
        raise ValueError("Il file delle domande deve contenere almeno un caso e ID univoci.")

    risultati = []
    for caso in casi:
        inizio = perf_counter()
        risposta = assistente.rispondi(caso.veicolo, caso.domanda)
        latenza_ms = round((perf_counter() - inizio) * 1000)
        documentale = caso.esito_atteso == "risposta"
        prima = next(iter(risposta.fonti_recuperate), None)
        # Hit@1 misura il ranking quando Qdrant è stato interrogato. La citazione valuta la risposta finale.
        hit_1 = corrisponde(prima, caso) if documentale and risposta.ricerca_eseguita else None
        citazione_corretta = corrisponde(risposta.fonte_citata, caso) if documentale else None
        esito_corretto = risposta.esito == caso.esito_atteso
        if not documentale:
            # Un chiarimento o un blocco deve anche evitare una ricerca documentale.
            passato = esito_corretto and (caso.esito_atteso == "fonte_assente" or not risposta.ricerca_eseguita)
        else:
            passato = esito_corretto and citazione_corretta is True

        risultati.append({
            **caso.model_dump(),
            "esito": risposta.esito,
            "ricerca_eseguita": risposta.ricerca_eseguita,
            "fonti_recuperate": [asdict(fonte) for fonte in risposta.fonti_recuperate],
            "fonte_citata": asdict(risposta.fonte_citata) if risposta.fonte_citata else None,
            "hit_at_1": hit_1,
            "citazione_corretta": citazione_corretta,
            "passato": passato,
            "latenza_ms": latenza_ms,
        })
        stato = "OK" if passato else "KO"
        print(f"{stato} | {caso.id} | atteso {caso.esito_atteso}, ottenuto {risposta.esito} | {latenza_ms} ms", flush=True)

    documentali = [r for r in risultati if r["esito_atteso"] == "risposta"]
    prime_fonti = [r["hit_at_1"] for r in documentali if r["hit_at_1"] is not None]
    controlli = [r for r in risultati if r["esito_atteso"] in {"chiarimento", "bloccato"}]
    astensioni = [r for r in risultati if r["esito_atteso"] == "fonte_assente"]
    passati = sum(r["passato"] for r in risultati)
    report = {
        "eseguito_il": datetime.now(timezone.utc).isoformat(),
        "modello_agente": assistente.client.model_name,
        "modello_embedding": assistente.indice.embedder.model_name,
        "top_k": assistente.indice.top_k,
        "max_char": CHUNK_MAX_CHAR,
        "overlap": CHUNK_OVERLAP,
        "metriche": {
            "casi_passati": {"corretti": passati, "totale": len(risultati)},
            "ricerche_avviate": {"corretti": len(prime_fonti), "totale": len(documentali)},
            "hit_at_1": {"corretti": sum(prime_fonti), "totale": len(prime_fonti)},
            "citazioni_corrette": {"corretti": sum(r["citazione_corretta"] for r in documentali), "totale": len(documentali)},
            "chiarimenti_e_blocchi": {"corretti": sum(r["passato"] for r in controlli), "totale": len(controlli)},
            "astensioni": {"corretti": sum(r["passato"] for r in astensioni), "totale": len(astensioni)},
        },
        "risultati": risultati,
    }
    # Sostituisci il report precedente solo quando il nuovo JSON è completo.
    file = NamedTemporaryFile(mode="w", encoding="utf-8", dir=destinazione.parent, delete=False)
    temporaneo = Path(file.name)
    try:
        with file:
            json.dump(report, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temporaneo.replace(destinazione)
    finally:
        temporaneo.unlink(missing_ok=True)
    print(f"\nCasi passati: {passati}/{len(risultati)}. Report: {destinazione.name}")
    return passati == len(risultati)
