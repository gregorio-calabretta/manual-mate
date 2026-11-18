import unittest
from unittest.mock import Mock

from conversazione import Conversazione
from fonti import Risposta


class ConversazioneTest(unittest.TestCase):
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
