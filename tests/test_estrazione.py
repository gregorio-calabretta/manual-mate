import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from estrazione import pagine_docling


class EstrazioneTest(unittest.TestCase):
    def test_un_paragrafo_multipagina_conserva_le_provenienze_del_testo(self):
        testo = "Prima pagina. Seconda pagina."
        elemento = SimpleNamespace(
            text=testo, label=SimpleNamespace(value="text"),
            prov=[SimpleNamespace(page_no=1, charspan=(0, 13)),
                  SimpleNamespace(page_no=2, charspan=(14, len(testo)))],
        )
        footer = SimpleNamespace(label=SimpleNamespace(value="page_footer"), prov=elemento.prov)
        documento = Mock()
        documento.iterate_items.return_value = [(elemento, 0), (footer, 0)]
        with patch("docling_core.transforms.serializer.markdown.MarkdownDocSerializer") as serializzatore:
            pagine = pagine_docling(documento)
        self.assertEqual(pagine, {1: "Prima pagina.", 2: "Seconda pagina."})
        serializzatore.assert_called_once_with(doc=documento)
        documento.iterate_items.assert_called_once_with(traverse_pictures=True)
        documento.export_to_markdown.assert_not_called()
