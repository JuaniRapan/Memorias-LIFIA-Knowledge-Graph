"""Tests del consumer de streaming (src/streaming/stream_consumer.py): la
decodificación de eventos Debezium y el SPARQL Update que arma para
sincronizar GraphDB. No necesitan Kafka/Postgres/GraphDB corriendo: se
mockea graphdb_client.run_update y se valida la sintaxis con el parser de
SPARQL de rdflib.

Correr con: python -m unittest tests.test_stream_consumer -v
"""

import json
import os
import sys
import unittest
from datetime import date, timedelta

from rdflib.plugins.sparql import prepareUpdate

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "etl"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "streaming"))
import stream_consumer as sc  # noqa: E402
import graphdb_client  # noqa: E402
from extract import clean_member_na_row  # noqa: E402

TEMA_URI = "http://lifia.info.unlp.edu.ar/resource/tema/nlp"

# schema mínimo de un envelope de Debezium para Member: alcanza con marcar
# los campos que necesitan decodificación especial (fecha/timestamp), el
# resto queda como string implícito
_MEMBER_STRUCT_FIELDS = [
    {"field": "id"},
    {"field": "firstName"},
    {"field": "lastName"},
    {"field": "slug"},
    {"field": "startDate", "name": "io.debezium.time.Date"},
    {"field": "createdAt", "name": "io.debezium.time.Timestamp"},
    {"field": "positionAtCIC"},
    {"field": "bibtexData"},
    {"field": "tags"},
]
MEMBER_ENVELOPE_SCHEMA = {
    "fields": [
        {"field": "before", "fields": _MEMBER_STRUCT_FIELDS},
        {"field": "after", "fields": _MEMBER_STRUCT_FIELDS},
    ]
}


def _member_row(slug, first_name="Ana", tags=None, position_a_cic=None, start_date=None):
    # todos los campos que transform_member_row necesita leer, en None salvo
    # los que cada test quiere variar puntualmente
    return {
        "id": f"id-{slug}", "firstName": first_name, "lastName": "Lopez", "slug": slug,
        "startDate": start_date, "endDate": None, "createdAt": 1779291470886,
        "highestDegree": None, "positionAtLab": None, "positionAtUnlp": None,
        "positionAtCIC": position_a_cic, "positionAtCONICET": None,
        "category": None, "sicadiCategory": None,
        "personalEmail": None, "institutionalEmail": None, "phone": None,
        "webPage": None, "orcid": None, "dblpProfile": None,
        "googleResearchProfile": None, "researchGateProfile": None,
        "shortCvInSpanish": None, "shortCvInEnglish": None,
        "interestsInEnglish": None, "interestsInSpanish": None,
        "affiliations": None, "avatarUrl": None,
        "bibtexData": None, "tags": tags or [],
    }


def _member_event(op, before, after):
    return {"schema": MEMBER_ENVELOPE_SCHEMA, "payload": {"op": op, "before": before, "after": after}}


class TestDecodeRow(unittest.TestCase):
    def test_decodifica_fecha_debezium_a_date(self):
        decoded = sc.decode_row({"startDate": 16436}, MEMBER_ENVELOPE_SCHEMA, "before")
        self.assertEqual(decoded["startDate"], date(1970, 1, 1) + timedelta(days=16436))

    def test_decodifica_timestamp_debezium_naive_en_utc(self):
        decoded = sc.decode_row({"createdAt": 1779291470886}, MEMBER_ENVELOPE_SCHEMA, "before")
        self.assertIsNone(decoded["createdAt"].tzinfo)

    def test_decodifica_jsonb_serializado_como_string(self):
        raw = json.dumps({"entryTags": {"journal": "Revista X"}})
        decoded = sc.decode_row({"bibtexData": raw}, MEMBER_ENVELOPE_SCHEMA, "before")
        self.assertEqual(decoded["bibtexData"], {"entryTags": {"journal": "Revista X"}})

    def test_campo_sin_tipo_logico_pasa_tal_cual(self):
        decoded = sc.decode_row({"firstName": "Ana"}, MEMBER_ENVELOPE_SCHEMA, "before")
        self.assertEqual(decoded["firstName"], "Ana")

    def test_before_none_devuelve_none(self):
        self.assertIsNone(sc.decode_row(None, MEMBER_ENVELOPE_SCHEMA, "before"))


class TestCleanMemberNaRow(unittest.TestCase):
    def test_reemplaza_na_por_none(self):
        cleaned = clean_member_na_row({"positionAtCIC": "N/A", "firstName": "Juan"})
        self.assertIsNone(cleaned["positionAtCIC"])
        self.assertEqual(cleaned["firstName"], "Juan")


class TestProcessEvent(unittest.TestCase):
    """Valida el SPARQL Update que process_event() manda a GraphDB, sin
    conectarse a ningún GraphDB real: se reemplaza graphdb_client.run_update
    por una función que solo guarda el texto para inspeccionarlo."""

    def setUp(self):
        self.captured = []
        self._original_run_update = graphdb_client.run_update
        graphdb_client.run_update = self.captured.append

    def tearDown(self):
        graphdb_client.run_update = self._original_run_update

    def test_insert_no_genera_delete_data(self):
        after = _member_row("ana-lopez")
        sc.process_event("Member", _member_event("c", None, after), {})

        self.assertEqual(len(self.captured), 1)
        self.assertNotIn("DELETE DATA", self.captured[0])
        self.assertIn("INSERT DATA", self.captured[0])
        prepareUpdate(self.captured[0])  # no debe tirar: sintaxis SPARQL válida

    def test_delete_no_genera_insert_data(self):
        before = _member_row("ana-lopez")
        sc.process_event("Member", _member_event("d", before, None), {})

        sparql = self.captured[0]
        self.assertIn("DELETE DATA", sparql)
        self.assertNotIn("INSERT DATA", sparql)
        prepareUpdate(sparql)

    def test_update_genera_delete_e_insert_sintacticamente_validos(self):
        before = _member_row("ana-lopez", first_name="Ana Vieja")
        after = _member_row("ana-lopez", first_name="Ana Nueva")
        sc.process_event("Member", _member_event("u", before, after), {})

        sparql = self.captured[0]
        self.assertIn("DELETE DATA", sparql)
        self.assertIn("INSERT DATA", sparql)
        self.assertIn('"Ana Nueva"', sparql)
        prepareUpdate(sparql)

    def test_n_a_de_member_se_limpia_antes_de_mandar_a_graphdb(self):
        after = _member_row("ana-lopez", position_a_cic="N/A")
        sc.process_event("Member", _member_event("c", None, after), {})
        self.assertNotIn('"N/A"', self.captured[0])

    def test_intervalo_usa_uri_estable_no_blank_node(self):
        # antes y después con distinto startDate: el DELETE y el INSERT
        # tienen que referenciar el mismo nodo de intervalo (misma URI
        # derivada de la entidad), nunca un blank node nuevo por evento
        before = _member_row("ana-lopez", start_date=16436)
        after = _member_row("ana-lopez", start_date=16500)
        sc.process_event("Member", _member_event("u", before, after), {})

        sparql = self.captured[0]
        self.assertIn("/persona/ana-lopez/intervalo>", sparql)
        self.assertNotIn("_:", sparql)

    def test_delete_no_borra_temas_compartidos(self):
        # Member antes y después referencian el mismo tema: el bloque
        # DELETE no debe tocar los triples PROPIOS del tema (solo el link
        # de la entidad hacia él), porque otras entidades podrían usarlo
        before = _member_row("ana-lopez", tags=["nlp"])
        after = _member_row("ana-lopez", tags=["nlp"])
        sc.process_event("Member", _member_event("u", before, after), {})

        delete_block = self.captured[0].split("INSERT DATA")[0]
        delete_lines = delete_block.splitlines()
        self.assertFalse(any(line.startswith(f"<{TEMA_URI}>") for line in delete_lines))


class TestProcessEventPublication(unittest.TestCase):
    """Publication tiene el camino más particular: bibtexData (jsonb) y la
    resolución de venue, así que se prueba aparte con su propio schema."""

    STRUCT_FIELDS = [
        {"field": "id"}, {"field": "slug"}, {"field": "title"}, {"field": "type"},
        {"field": "year"}, {"field": "selfArchivingUrl"}, {"field": "ranking"},
        {"field": "bibtexData"}, {"field": "authors"}, {"field": "tags"},
    ]
    ENVELOPE_SCHEMA = {"fields": [
        {"field": "before", "fields": STRUCT_FIELDS},
        {"field": "after", "fields": STRUCT_FIELDS},
    ]}

    def setUp(self):
        self.captured = []
        self._original_run_update = graphdb_client.run_update
        graphdb_client.run_update = self.captured.append

    def tearDown(self):
        graphdb_client.run_update = self._original_run_update

    def _pub_row(self, title):
        bibtex = json.dumps({"entryTags": {"journal": "Journal of Testing", "doi": "10.1234/test"}})
        return {
            "id": "p1", "slug": "test-pub", "title": title, "type": "article", "year": "2024",
            "selfArchivingUrl": None, "ranking": None, "bibtexData": bibtex,
            "authors": "Fulano and Mengano", "tags": ["nlp"],
        }

    def test_bibtex_string_se_parsea_y_arma_el_venue(self):
        after = self._pub_row("Titulo Nuevo")
        msg = {"schema": self.ENVELOPE_SCHEMA, "payload": {"op": "c", "before": None, "after": after}}
        sc.process_event("Publication", msg, {})

        sparql = self.captured[0]
        self.assertIn("/venue/journal-of-testing>", sparql)
        self.assertIn('"Titulo Nuevo"', sparql)
        prepareUpdate(sparql)


if __name__ == "__main__":
    unittest.main()
