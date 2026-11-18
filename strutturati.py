from openai import OpenAIError
from pydantic import BaseModel

from osservabilita import span


def chiedi_strutturato(client, *, modello: type[BaseModel], input: str, prompt: str, max_tokens: int):
    """Riprova una volta un output assente o non valido, con un limite più ampio."""
    with span("risposta-strutturata", "CHAIN", schema=modello.__name__) as traccia:
        for tentativo in range(2):
            limite = max_tokens * (tentativo + 1)
            traccia.set_attribute("tentativi", tentativo + 1)
            traccia.set_attribute("limite_token", limite)
            try:
                risposta = client.structured_response(
                    input=input, output_cls=modello, system_prompt=prompt, max_tokens=limite,
                )
            except ValueError:
                traccia.set_attribute("esito", "formato_non_valido")
                continue
            except OpenAIError:
                traccia.set_attribute("esito", "errore_api")
                return None
            dati = next(iter(risposta.structured_data or ()), None)
            if isinstance(dati, modello):
                traccia.set_attribute("esito", "valido")
                return dati
            traccia.set_attribute("esito", "output_assente")
        return None
