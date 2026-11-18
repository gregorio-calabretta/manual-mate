import unittest
from unittest.mock import Mock

from datapizza.type import Chunk

from catalogo import LEON
from recupero import FontiRichiesta


class RecuperoTest(unittest.TestCase):
    def test_completa_anche_una_fonte_scelta_oltre_le_prime_tre_pagine(self):
        indice = Mock()
        fonti = [Chunk(id=f"fonte-{n}", text="Ruote\n\nEtichetta pressione.", metadata={
            "veicolo": LEON.id, "edizione": LEON.edizione, "source_file": LEON.file,
            "fonte": f"fonte-{n}", "pagina": n, "pagina_pdf": n + 2,
        }) for n in range(1, 7)]

        def completa(_, hit):
            return Chunk(id=hit.id, text=f"Ruote\n\nEtichetta pressione.\nControllare a freddo.", metadata=hit.metadata)

        indice.completa_pagina.side_effect = completa
        recupero = FontiRichiesta(indice, LEON)
        recupero.aggiungi("collezione", [fonti])
        self.assertEqual(indice.completa_pagina.call_count, 3)
        self.assertNotIn("a freddo", recupero.fonti["fonte-6"].text)
        citate = recupero.completa_citate("collezione", (fonti[5],))
        self.assertEqual(citate[0].metadata["fonte"], "fonte-6")
        self.assertIn("a freddo", citate[0].text)
        recupero.completa_citate("collezione", citate)
        self.assertEqual(indice.completa_pagina.call_count, 4)
