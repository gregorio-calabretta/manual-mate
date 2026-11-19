"""Prove reali mirate: conserva risposta, fonti e decisioni dei controlli LLM."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv

ROOT = Path(os.getenv("MANUALMATE_CONFIG_DIR") or Path(__file__).resolve().parent)
load_dotenv(ROOT / ".env")
os.environ.setdefault("MANUALI_DIR", str(ROOT.parent / "manuali uso e manutenzione auto"))

from runtime import crea_assistente
from conversazione import Conversazione
import assistente as modulo

CASI = {
    "lavavetri": ["non esce acqua dallo spruzzino della mia ford focus", "parabrezza anteriore"],
    "lavavetri_variante": ["Sulla Ford Focus il lavaparabrezza non spruzza: cosa posso controllare secondo il libretto?"],
    "diagnosi_esatta": ["Nella Ford Focus non esce liquido dal lavaparabrezza anteriore. Puoi dirmi con certezza quale pezzo si e rotto?"],
    "colore_spia": ["Nella Ford Focus la spia degli pneumatici a ferro di cavallo con punto esclamativo e rossa: cosa significa e cosa devo fare?"],
    "dato_assente": ["Quanto costa sostituire la pompa lavaparabrezza della Ford Focus?"],
    "consumi": ["Quanto consuma la Ford Focus benzina 1.0 EcoBoost?"],
    "telecomando_civic": ["Il telecomando della Honda Civic Type R non funziona: il libretto indica qualche controllo da fare?"],
    "lavavetri_leon": ["Nella SEAT Leon il lavaparabrezza anteriore non spruzza liquido. Cosa posso controllare secondo il libretto?"],
}

def esegui(nomi, destinazione):
    originale = modulo.chiedi_strutturato
    tracce = []

    def osserva(*args, **kwargs):
        dati = originale(*args, **kwargs)
        tracce.append({"schema": kwargs["modello"].__name__,
                       "input": json.loads(kwargs["input"]),
                       "output": dati.model_dump() if dati else None})
        return dati

    modulo.chiedi_strutturato = osserva
    agente = crea_assistente(os.environ["OPENAI_API_KEY"])
    risultati = []
    for nome in nomi:
        chat = Conversazione()
        turni = []
        for domanda in CASI[nome]:
            tracce.clear()
            inizio = perf_counter()
            risposta = chat.rispondi(domanda, lambda v, d, c: agente.rispondi(v, d, contesto=c))
            turno = {"domanda": domanda, "esito": risposta.esito,
                     "testo": risposta.sintesi or risposta.testo,
                     "fonti": [f.__dict__ for f in risposta.fonti_recuperate],
                     "secondi": round(perf_counter() - inizio, 2), "controlli": list(tracce)}
            turni.append(turno)
            print(json.dumps({"caso": nome, **{k: turno[k] for k in ("esito", "testo", "secondi")}}, ensure_ascii=False), flush=True)
        risultati.append({"caso": nome, "turni": turni})
        Path(destinazione).write_text(json.dumps({"data": datetime.now(timezone.utc).isoformat(), "casi": risultati}, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    esegui(sys.argv[2:] or list(CASI), sys.argv[1])
