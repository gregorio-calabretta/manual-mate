import os

import streamlit as st
from openai import APIError
from qdrant_client.http.exceptions import ApiException

from assistente import Risposta
from catalogo import CATALOGO, Veicolo
from osservabilita import avvia_osservabilita
from runtime import carica_configurazione, crea_assistente


@st.cache_resource(show_spinner=False)
def assistente_web(chiave: str):
    return crea_assistente(chiave)


@st.cache_resource(show_spinner=False)
def osservabilita_web():
    # Streamlit riesegue la pagina a ogni interazione. Porta e provider si avviano una volta per processo.
    return avvia_osservabilita(18000, "http://localhost:16006/v1/traces")


def consulta(veicolo: Veicolo, domanda: str, chiave: str, contesto: tuple[str, ...]) -> Risposta:
    try:
        return assistente_web(chiave).rispondi(veicolo.id, domanda, contesto=contesto)
    except ApiException:
        return Risposta("errore", "Qdrant non è raggiungibile. Verifica che il servizio Docker `qdrant` sia avviato.")
    except APIError:
        return Risposta("errore", "La chiamata a OpenAI è fallita. Verifica la connessione, la chiave API e la quota.")
    except (OSError, ValueError):
        return Risposta("errore", "Impossibile completare la richiesta. Controlla la configurazione e riprova.")


def mostra_risposta(risposta: Risposta, veicolo: Veicolo) -> None:
    with st.chat_message("assistant"):
        if risposta.esito in {"errore", "indice_assente"}:
            st.error(risposta.testo)
        elif risposta.fonte_citata:
            titolo, _, estratto = risposta.testo.partition("\n\n")
            corpo, _, riferimento = estratto.rpartition("\n\nFonte: ")
            st.markdown(f"**{titolo}**")
            st.text(corpo)
            st.caption(f"Fonte · {riferimento}")
        else:
            st.write(risposta.testo)

        if risposta.fonti_recuperate:
            titoli = {avviso.id: avviso.titolo for avviso in veicolo.avvisi}
            with st.expander("Passaggi recuperati da Qdrant"):
                for numero, fonte in enumerate(risposta.fonti_recuperate, 1):
                    st.write(f"{numero}. {titoli.get(fonte.id, fonte.id)} · p. {fonte.pagina}")


def main() -> None:
    st.set_page_config(page_title="Manual Mate", page_icon=":material/menu_book:")
    carica_configurazione()
    chiave = os.getenv("OPENAI_API_KEY", "").strip()

    st.title("Manual Mate")
    st.write("Descrivi cosa succede alla tua auto. Se serve un dettaglio, te lo chiedo.")

    with st.sidebar:
        st.subheader("Strumenti della demo")
        st.markdown("[Tracce · Phoenix](http://localhost:16006)\n\n"
                    "[Metriche · Grafana](http://localhost:13000/d/manuali-auto)\n\n"
                    "[Indice · Qdrant](http://localhost:16333/dashboard)")

    if os.getenv("MANUAL_MATE_OSSERVABILITA", "").casefold().strip() in {"1", "true"}:
        try:
            osservabilita_web()
        except OSError:
            st.warning("Impossibile avviare le metriche sulla porta 18000. Verifica se è già usata dalla CLI.")

    if not chiave:
        st.warning("Imposta `OPENAI_API_KEY` nel file `.env` o nel terminale e riavvia Streamlit per fare domande.")

    with st.container(border=True):
        codice = st.selectbox(
            "Veicolo", list(CATALOGO), index=None, placeholder="Seleziona marca e modello",
            format_func=lambda voce: CATALOGO[voce].nome, key="veicolo",
        )
        veicolo = CATALOGO.get(codice)
        if veicolo is not None:
            st.caption(f"Edizione del manuale · {veicolo.edizione}")
            st.caption("Sezioni indicizzate · avvisi sull’olio motore")

    if veicolo is None:
        st.chat_input("Seleziona prima il veicolo", disabled=True, key="senza-veicolo")
        return

    # Lo storico e il contesto dei chiarimenti restano separati per veicolo.
    conversazioni = st.session_state.setdefault("conversazioni", {})
    cronologia = conversazioni.setdefault(veicolo.id, [])
    if cronologia and st.button("Nuova conversazione", key=f"azzera-{veicolo.id}"):
        cronologia.clear()

    esempio = None
    with st.expander("Esempi di domande"):
        for avviso in veicolo.avvisi:
            if st.button(avviso.titolo, key=avviso.id, disabled=not chiave):
                esempio = avviso.titolo

    for domanda, risposta in cronologia:
        with st.chat_message("user"):
            st.text(domanda)
        mostra_risposta(risposta, veicolo)

    digitata = st.chat_input("Descrivi il problema o rispondi al chiarimento", key=f"domanda-{veicolo.id}", disabled=not chiave)
    domanda = (digitata or esempio or "").strip()
    if domanda and chiave:
        precedenti = []
        for turno, esito in reversed(cronologia[-2:]):
            if esito.esito != "chiarimento":
                break
            precedenti.append(turno)
        with st.chat_message("user"):
            st.text(domanda)
        with st.spinner("Verifico cosa dice il libretto…"):
            risposta = consulta(veicolo, domanda, chiave, tuple(reversed(precedenti)))
        cronologia.append((domanda, risposta))
        mostra_risposta(risposta, veicolo)


if __name__ == "__main__":
    main()
