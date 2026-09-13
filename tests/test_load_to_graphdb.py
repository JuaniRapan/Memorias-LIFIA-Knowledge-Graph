"""Tests de src/etl/load_to_graphdb.py: que la carga inicial postee tanto
el grafo principal como la jerarquía de CSO, cada uno con su Content-Type
de turtle. No necesita GraphDB corriendo: se mockea urllib.request.urlopen.

Correr con: python -m unittest tests.test_load_to_graphdb -v
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "etl"))
import load_to_graphdb as ltg 

class FakeResponse:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class LoadTest(unittest.TestCase):
    def test_postea_el_tbox_de_vivo_el_grafo_y_la_jerarquia_de_cso(self):
        posted_urls = []
        posted_paths = []

        def fake_urlopen(request):
            posted_urls.append(request.full_url)
            posted_paths.append(request.data)
            return FakeResponse()

        with mock.patch.object(ltg.urllib.request, "urlopen", fake_urlopen):
            ltg.load()

        # tres POSTs, en orden: primero el TBox de VIVO, después el grafo
        # grande, y al final la jerarquía de CSO
        self.assertEqual(len(posted_urls), 3)
        expected_url = f"{ltg.GRAPHDB_URL}/repositories/{ltg.GRAPHDB_REPOSITORY}/statements"
        self.assertEqual(posted_urls, [expected_url, expected_url, expected_url])

        with open(ltg.VIVO_ONTOLOGY_PATH, "rb") as f:
            self.assertEqual(posted_paths[0], f.read())
        with open(ltg.TTL_PATH, "rb") as f:
            self.assertEqual(posted_paths[1], f.read())
        with open(ltg.CSO_HIERARCHY_PATH, "rb") as f:
            self.assertEqual(posted_paths[2], f.read())

    def test_manda_content_type_turtle(self):
        with mock.patch.object(ltg.urllib.request, "urlopen", return_value=FakeResponse()) as m:
            ltg._post_turtle(ltg.CSO_HIERARCHY_PATH)

        request = m.call_args[0][0]
        self.assertEqual(request.get_header("Content-type"), "text/turtle; charset=utf-8")

    def test_manda_content_type_rdf_xml_para_el_tbox_de_vivo(self):
        with mock.patch.object(ltg.urllib.request, "urlopen", return_value=FakeResponse()) as m:
            ltg._post_statements(ltg.VIVO_ONTOLOGY_PATH, "application/rdf+xml")

        request = m.call_args[0][0]
        self.assertEqual(request.get_header("Content-type"), "application/rdf+xml; charset=utf-8")


if __name__ == "__main__":
    unittest.main()
