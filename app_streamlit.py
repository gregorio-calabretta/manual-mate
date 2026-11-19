import os

import streamlit as st
from openai import APIError
from qdrant_client.http.exceptions import ApiException

from assistente import Risposta
from catalogo import CATALOGO, Veicolo
from conversazione import Conversazione
from osservabilita import avvia_osservabilita
from runtime import carica_configurazione, crea_assistente


@st.cache_resource(show_spinner=False)
def assistente_web(chiave: str):
    return crea_assistente(chiave)


@st.cache_resource(show_spinner=False)
def osservabilita_web():
    # Streamlit riesegue la pagina a ogni interazione. Porta e provider si avviano una volta per processo.
    return avvia_osservabilita(18000, "http://127.0.0.1:16006/v1/traces")


def consulta(veicolo_id: str, domanda: str, chiave: str, contesto: tuple[str, ...]) -> Risposta:
    try:
        return assistente_web(chiave).rispondi(veicolo_id, domanda, contesto=contesto)
    except ApiException:
        return Risposta("errore", "Qdrant non è raggiungibile. Verifica che il servizio Docker `qdrant` sia avviato.")
    except APIError:
        return Risposta("errore", "La chiamata a OpenAI è fallita. Verifica la connessione, la chiave API e la quota.")
    except (OSError, ValueError):
        return Risposta("errore", "Impossibile completare la richiesta. Controlla la configurazione e riprova.")


def mostra_risposta(risposta: Risposta, veicolo: Veicolo | None) -> None:
    with st.chat_message("assistant"):
        if risposta.esito in {"errore", "indice_assente"}:
            st.error(risposta.testo)
        elif risposta.fonte_citata:
            titolo, _, estratto = risposta.testo.partition("\n\n")
            corpo, _, riferimento = estratto.rpartition("\n\nFonte: ")
            if risposta.sintesi:
                st.text(risposta.sintesi)
                etichetta = "Estratti originali del manuale" if risposta.fonti_aggiuntive else "Estratto originale del manuale"
                with st.expander(etichetta):
                    st.text(f"{titolo}\n\n{corpo}" if risposta.fonti_aggiuntive else corpo)
            else:
                st.markdown(f"**{titolo}**")
                st.text(corpo)
            st.caption(f"Fonte · {riferimento}")
        else:
            st.write(risposta.testo)

        if risposta.fonti_recuperate:
            with st.expander("Passaggi recuperati da Qdrant"):
                for numero, fonte in enumerate(risposta.fonti_recuperate, 1):
                    pagina = f"p. {fonte.pagina}" if fonte.pagina is not None else f"PDF p. {fonte.pagina_pdf}"
                    st.write(f"{numero}. Passaggio del manuale · {pagina}")


def main() -> None:
    st.set_page_config(page_title="Manual Mate", page_icon=":material/menu_book:")
    carica_configurazione()
    chiave = os.getenv("OPENAI_API_KEY", "").strip()

    st.title("Manual Mate")
    st.write("Ti aiuto a trovare le informazioni nel libretto della tua auto.")

    with st.sidebar:
        st.subheader("Strumenti della demo")
        st.markdown("[Tracce · Phoenix](http://localhost:16006)\n\n"
                    "[Metriche · Grafana](http://localhost:13000/d/manuali-auto)\n\n"
                    "[Indice · Qdrant](http://localhost:16333/dashboard)")

    if os.getenv("MANUAL_MATE_OSSERVABILITA", "true").casefold().strip() in {"1", "true"}:
        try:
            osservabilita_web()
        except OSError:
            st.warning("Impossibile avviare le metriche sulla porta 18000. Verifica se è già usata dalla CLI.")

    if not chiave:
        st.warning("Imposta `OPENAI_API_KEY` nel file `.env` o nel terminale e riavvia Streamlit per fare domande.")

    scheda_manuale = st.empty()
    controllo_conversazione = st.empty()
    cronologia = st.session_state.setdefault("cronologia_manual_mate", [])
    conversazione = st.session_state.setdefault("conversazione_manual_mate", Conversazione())

    for domanda, risposta, codice in cronologia:
        with st.chat_message("user"):
            st.text(domanda)
        mostra_risposta(risposta, CATALOGO.get(codice))

    domanda = (st.chat_input("Scrivi una domanda o un chiarimento", key="domanda", disabled=not chiave) or "").strip()
    if domanda and chiave:
        with st.chat_message("user"):
            st.text(domanda)
        with st.spinner("Un momento…"):
            risposta = conversazione.rispondi(domanda, lambda codice, testo, contesto: consulta(codice, testo, chiave, contesto))
        veicolo = CATALOGO.get(conversazione.veicolo_id)
        cronologia.append((domanda, risposta, conversazione.veicolo_id))
        mostra_risposta(risposta, veicolo)

    if cronologia and controllo_conversazione.button("Nuova conversazione", key="azzera-conversazione"):
        cronologia.clear()
        st.session_state["conversazione_manual_mate"] = Conversazione()
        st.rerun()

    veicolo = CATALOGO.get(conversazione.veicolo_id)
    if veicolo:
        with scheda_manuale.container(border=True):
            st.markdown(f"**Libretto in uso · {veicolo.nome}**")
            st.caption(veicolo.edizione)
    elif not cronologia:
        scheda_manuale.caption("Prova «Dove si trova la scatola dei fusibili?»")


if __name__ == "__main__":
    main()
