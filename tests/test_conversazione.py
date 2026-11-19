import unittest
from unittest.mock import Mock

from conversazione import Conversazione
from fonti import Risposta, _aggiungi_limite


class ConversazioneTest(unittest.TestCase):
    def test_aiuto_conversazionale_non_richiede_auto_e_non_diventa_domanda_in_attesa(self):
        for domanda in ("ciao che domande posso farti?", "Quali informazioni posso chiederti?",
                        "Mi fai esempi di domande?", "Che domande ti posso fare?"):
            with self.subTest(domanda=domanda):
                consulta = Mock()
                chat = Conversazione()
                self.assertEqual(chat.rispondi(domanda, consulta).esito, "conversazione")
                self.assertIsNone(chat.domanda_in_attesa)
                self.assertEqual(chat.rispondi("ad esempio sulla ford focus", consulta).esito, "veicolo_selezionato")
                consulta.assert_not_called()

    def test_risposta_parziale_al_chiarimento_riceve_la_domanda_dell_assistente(self):
        richiesta = "Quale motore hai? Benzina o diesel, e quale cilindrata?"
        consulta = Mock(side_effect=[Risposta("chiarimento", richiesta), Risposta("chiarimento", "Quale cilindrata?"), Risposta("risposta", "Dato documentato")])
        chat = Conversazione(veicolo_id="focus")
        domanda = "Quanti km al litro fa?"
        chat.rispondi(domanda, consulta)
        chat.rispondi("benzina", consulta)
        consulta.assert_called_with("focus", "benzina", (domanda, "Chiarimento precedente dell'assistente: " + richiesta))
        chat.rispondi("1.0 EcoBoost", consulta)
        consulta.assert_called_with("focus", "1.0 EcoBoost", (domanda, "benzina", "Chiarimento precedente dell'assistente: Quale cilindrata?"))
        self.assertIsNone(chat.ultimo_chiarimento)

    def test_cambio_auto_o_argomento_cancella_anche_la_domanda_di_chiarimento(self):
        for nuova in ("Dove sono i fusibili della Seat Leon?", "Altra domanda: dove sono i fusibili?"):
            with self.subTest(nuova=nuova):
                consulta = Mock(side_effect=[Risposta("chiarimento", "Che cilindrata?"), Risposta("risposta", "Dato documentato")])
                chat = Conversazione(veicolo_id="focus")
                chat.rispondi("Quanti km al litro fa?", consulta)
                chat.rispondi(nuova, consulta)
                self.assertEqual(consulta.call_args.args[2], ())

    def test_richiami_liberi_ricevono_il_tema_per_ogni_manuale(self):
        for codice, domanda in (
            ("audi", "Dove si trova il filtro antipolline?"),
            ("focus", "Quali misure hanno le spazzole?"),
            ("civic", "Che pila usa la chiave?"),
            ("leon", "Dove sono i fusibili?"),
        ):
            for seguito in ("Sicuro che non dice dove si trova?", "Puoi verificare meglio?", "Davvero?", "Mi spieghi meglio?"):
                with self.subTest(codice=codice, seguito=seguito):
                    consulta = Mock(return_value=Risposta("risposta", "Risposta documentata parziale"))
                    chat = Conversazione(veicolo_id=codice)
                    chat.rispondi(domanda, consulta)
                    chat.rispondi("Grazie", consulta)
                    chat.rispondi(seguito, consulta)
                    consulta.assert_called_with(codice, seguito, (domanda,))

    def test_contesto_recente_limitato_e_azzerato_al_cambio_auto_o_argomento(self):
        consulta = Mock(return_value=Risposta("risposta", "Risposta documentata"))
        chat = Conversazione(veicolo_id="audi")
        domande = ("Dove sono i fusibili?", "Dove nel vano motore?", "Come apro il coperchio?", "Puoi spiegare meglio?", "Mi fai un riepilogo?")
        for domanda in domande:
            chat.rispondi(domanda, consulta)
        chat.rispondi("Puoi controllare?", consulta)
        consulta.assert_called_with("audi", "Puoi controllare?", domande[-4:])
        chat.rispondi("Altra domanda: che pila usa la chiave?", consulta)
        consulta.assert_called_with("audi", "Altra domanda: che pila usa la chiave?", ())
        chat.rispondi("Che pila usa la chiave della Ford Focus?", consulta)
        consulta.assert_called_with("focus", "Che pila usa la chiave della Ford Focus?", ())

    def test_nuova_domanda_autonoma_arriva_intatta_con_il_contesto_recente(self):
        consulta = Mock(return_value=Risposta("risposta", "Risposta documentata"))
        chat = Conversazione(veicolo_id="audi")
        prima = "Dove sono i fusibili?"
        nuova = "Che pila usa la chiave?"
        chat.rispondi(prima, consulta)
        chat.rispondi(nuova, consulta)
        consulta.assert_called_with("audi", nuova, (prima,))

    def test_limite_accetta_un_nome_o_una_frase_senza_concatenarli_a_un_verbo(self):
        for parte in ("il prezzo del ricambio", "Non sono indicate le misure delle spazzole.",
                      "La posizione non è specificata nei passaggi forniti."):
            with self.subTest(parte=parte):
                risultato = _aggiungi_limite("Dato documentato.", parte)
                self.assertEqual(risultato, "Dato documentato.\n\nInformazione non ricavata dai passaggi consultati: " + parte.rstrip(".") + ".")
        self.assertEqual(_aggiungi_limite("Dato documentato.", "  "), "Dato documentato.")

    def test_un_codice_di_pila_non_diventa_l_anno_della_vettura(self):
        consulta = Mock(return_value=Risposta("risposta", "Fonte documentata"))
        chat = Conversazione()
        domanda = "La Honda Civic Type R usa una pila CR 2032?"
        chat.rispondi(domanda, consulta)
        consulta.assert_called_once_with("civic", domanda, ())
        chat.rispondi("Honda Civic Type R 2022", consulta)
        self.assertIsNone(chat.veicolo_id)
        self.assertEqual(consulta.call_count, 1)

    def test_una_nuova_domanda_con_che_non_diventa_un_dettaglio_del_modello(self):
        consulta = Mock(return_value=Risposta("risposta", "Fonte documentata"))
        chat = Conversazione()
        chat.rispondi("Dove trovo la pressione delle gomme?", consulta)
        nuova = "Seat Leon FR che batteria usa la chiave"
        chat.rispondi(nuova, consulta)
        consulta.assert_called_once_with("leon", nuova, ())

    def test_allestimenti_e_motori_non_sostituiscono_la_domanda_in_attesa(self):
        domanda = "Dove trovo la pressione delle gomme?"
        for codice, risposta in (
            ("leon", "Seat Leon FR 1.5 eTSI DSG del 2021"),
            ("focus", "Ford Focus Titanium con cambio manuale"),
            ("civic", "Honda Civic Type R GT"),
            ("audi", "Audi A3 8V Sportback 1.6 TDI del 2019"),
        ):
            with self.subTest(codice=codice):
                consulta = Mock(return_value=Risposta("risposta", "Fonte documentata"))
                chat = Conversazione()
                self.assertEqual(chat.rispondi(domanda, consulta).esito, "veicolo_da_chiarire")
                chat.rispondi(risposta, consulta)
                consulta.assert_called_once_with(codice, domanda, (risposta,))

    def test_domanda_autonoma_e_anno_incompatibile_seguono_i_propri_controlli(self):
        consulta = Mock(return_value=Risposta("risposta", "Fonte documentata"))
        chat = Conversazione()
        chat.rispondi("Dove trovo la pressione delle gomme?", consulta)
        domanda = "Seat Leon FR, dove sono i fusibili"
        chat.rispondi(domanda, consulta)
        consulta.assert_called_once_with("leon", domanda, ())
        chat.rispondi("Seat Leon del 2010", consulta)
        self.assertIsNone(chat.veicolo_id)
        self.assertEqual(consulta.call_count, 1)
