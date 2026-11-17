import unittest
from unittest.mock import Mock

from prometheus_client import REGISTRY

from assistente import Risposta
from conversazione import Conversazione
from osservabilita import richiesta


class OsservabilitaTest(unittest.TestCase):
    def test_misura_anche_i_turni_che_non_chiamano_l_agente(self):
        etichette = {"esito": "conversazione"}
        prima = REGISTRY.get_sample_value("manuali_richieste_total", etichette) or 0
        consulta = Mock()
        risposta = Conversazione().rispondi("Cosa sai fare?", consulta)
        self.assertEqual(risposta.esito, "conversazione")
        consulta.assert_not_called()
        self.assertEqual(REGISTRY.get_sample_value("manuali_richieste_total", etichette), prima + 1)

    def test_chat_e_agente_contano_la_richiesta_una_sola_volta(self):
        etichette = {"esito": "risposta"}
        prima = REGISTRY.get_sample_value("manuali_richieste_total", etichette) or 0

        def consulta(*_):
            with richiesta() as misura:
                misura["valore"] = "risposta"
                return Risposta("risposta", "Estratto di prova")

        Conversazione(veicolo_id="audi").rispondi("Dove sono i fusibili?", consulta)
        self.assertEqual(REGISTRY.get_sample_value("manuali_richieste_total", etichette), prima + 1)
