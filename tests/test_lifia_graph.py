"""Tests de la capa de transformación RDF (src/etl/transform.py).

Dos grupos:
  - TestNameResolution: la lógica de resolver texto libre (director/coDirector/
    student/otherAdvisors) contra Member. Corre siempre, con datos inventados,
    no toca la base ni ningún archivo.
  - TestGeneratedGraph: valida el grafo ya generado (data/processed/lifia_graph.ttl)
    contra los CSV de data/interim/. Necesita haber corrido extract.py y
    transform.py antes (requieren la base levantada); si no encuentra esos
    archivos, se salta con un mensaje claro en vez de fallar.

Correr con: python -m unittest tests.test_lifia_graph -v
"""

import os
import sys
import unittest

import pandas as pd
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "etl"))
import transform 

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
TTL_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "lifia_graph.ttl")
INTERIM_DIR = os.path.join(PROJECT_ROOT, "data", "interim")

FOAF = Namespace("http://xmlns.com/foaf/0.1/")
BIBO = Namespace("http://purl.org/ontology/bibo/")
DBLP = Namespace("https://dblp.org/rdf/schema#")


# ---------------------------------------------------------------------------
# Grupo 1: resolución de nombres, con un mini-dataset inventado
# ---------------------------------------------------------------------------

def _member_index():
    """Un Member inventado, con los casos límite que generaron problemas en el desarrollo."""
    df_member = pd.DataFrame([
        {"id": "m1", "firstName": "Alejandra", "lastName": "Lliteras"},
        {"id": "m2", "firstName": "Andrés", "lastName": "Rodríguez"},
        {"id": "m3", "firstName": "Matías", "lastName": "Urbieta"},
        {"id": "m4", "firstName": "Martín", "lastName": "Urbieta"},
        {"id": "m5", "firstName": "Cecilia", "lastName": "Challiol"},
    ])
    uri_lookup = {row["id"]: f"uri:{row['id']}" for _, row in df_member.iterrows()}
    return transform.build_member_name_index(df_member, uri_lookup), uri_lookup


class TestNameResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.name_index, cls.uri_lookup = _member_index()

    def test_nombre_exacto(self):
        self.assertEqual(
            transform.resolve_person("Alejandra Lliteras", self.name_index),
            self.uri_lookup["m1"],
        )

    def test_orden_invertido_apellido_nombre(self):
        # el mismo bug que encontramos en el dato real: "Rodríguez, Andrés"
        self.assertEqual(
            transform.resolve_person("Lliteras Alejandra", self.name_index),
            self.uri_lookup["m1"],
        )

    def test_nombre_del_medio_que_el_member_no_tiene(self):
        # "Alejandra Beatriz Lliteras" en el dato real: Beatriz no está en la base
        self.assertEqual(
            transform.resolve_person("Alejandra Beatriz Lliteras", self.name_index),
            self.uri_lookup["m1"],
        )

    def test_titulo_academico_y_punto_final(self):
        self.assertEqual(
            transform.resolve_person("Dr. Andrés Rodríguez.", self.name_index),
            self.uri_lookup["m2"],
        )

    def test_texto_pegado_tipo_afiliacion(self):
        # caso real: "Gustavo Rossi (UNLP)"
        self.assertEqual(
            transform.resolve_person("Andrés Rodríguez (UNLP)", self.name_index),
            self.uri_lookup["m2"],
        )

    def test_apellido_solo_si_es_unico(self):
        self.assertEqual(
            transform.resolve_person("Challiol", self.name_index),
            self.uri_lookup["m5"],
        )

    def test_nombre_o_apellido_ambiguo_no_adivina(self):
        # hay dos Urbieta en el mini-dataset (a propósito, como en el real)
        self.assertIsNone(transform.resolve_person("Urbieta", self.name_index))

    def test_persona_que_no_existe_no_matchea_cualquier_cosa(self):
        self.assertIsNone(
            transform.resolve_person("Alguien Totalmente Distinto", self.name_index)
        )

    def test_resolve_exact_no_usa_subconjunto(self):
        # resolve_exact es más estricto que resolve_person a propósito: lo usa
        # transform_text_relations para decidir si un campo con coma es UNA
        # persona en formato "Apellido, Nombre" y no dos personas juntas
        self.assertIsNone(
            transform.resolve_exact("Andrés Rodríguez (UNLP)", self.name_index)
        )

    def test_coma_como_apellido_nombre_de_una_sola_persona(self):
        self.assertEqual(
            transform.resolve_exact("Rodríguez, Andrés", self.name_index),
            self.uri_lookup["m2"],
        )


class TestSplitNames(unittest.TestCase):
    def test_separa_por_coma(self):
        self.assertEqual(
            transform.split_names("Andrés Rodríguez, Cecilia Challiol"),
            ["Andrés Rodríguez", "Cecilia Challiol"],
        )

    def test_separa_por_y_and(self):
        self.assertEqual(
            transform.split_names("Andrés Rodríguez y Cecilia Challiol"),
            ["Andrés Rodríguez", "Cecilia Challiol"],
        )
        self.assertEqual(
            transform.split_names("Andrés Rodríguez and Cecilia Challiol"),
            ["Andrés Rodríguez", "Cecilia Challiol"],
        )

    def test_separa_por_guion_y_barra(self):
        self.assertEqual(
            transform.split_names("Gustavo Rossi - Julián Grigera"),
            ["Gustavo Rossi", "Julián Grigera"],
        )
        self.assertEqual(
            transform.split_names("Pablo Pizio / Nicolás Ferella"),
            ["Pablo Pizio", "Nicolás Ferella"],
        )

    def test_saca_etiqueta_con_dos_puntos(self):
        self.assertEqual(
            transform.split_names("Asesor técnico: Alejandra Lliteras"),
            ["Alejandra Lliteras"],
        )


class TestLooksLikeAName(unittest.TestCase):
    def test_nombre_largo_valido(self):
        self.assertTrue(transform.looks_like_a_name("Federico Ricardo Mozzon Corporaal"))

    def test_nombre_compuesto_con_particulas(self):
        # "de la" no debería contar como palabras de contenido
        self.assertTrue(transform.looks_like_a_name("Maria de la Paz Diulio"))

    def test_titulo_de_tesis_no_es_nombre(self):
        self.assertFalse(
            transform.looks_like_a_name("Requerimientos de calidad en lenguaje natural")
        )


class TestAuthorshipYPiRole(unittest.TestCase):
    """vivo:authorOf y vivo:hasPrincipalInvestigatorRole no existen en la
    ontología real de VIVO (verificado contra ontologias/vivo.owl); estos
    tests validan el patrón de nodo intermedio que los reemplaza."""

    def test_add_authorship_arma_el_nodo_con_las_cuatro_aristas(self):
        graph = Graph()
        member_uri = transform.make_uri("persona", "ana-lopez")
        pub_uri = transform.make_uri("publicacion", "paper-1")

        autoria_uri = transform.add_authorship(graph, member_uri, pub_uri)

        self.assertEqual(autoria_uri, transform.make_uri("autoria", "ana-lopez--paper-1"))
        self.assertIn((autoria_uri, RDF.type, transform.VIVO.Authorship), graph)
        self.assertIn((member_uri, transform.VIVO.relatedBy, autoria_uri), graph)
        self.assertIn((pub_uri, transform.VIVO.relatedBy, autoria_uri), graph)
        self.assertIn((autoria_uri, transform.VIVO.relates, member_uri), graph)
        self.assertIn((autoria_uri, transform.VIVO.relates, pub_uri), graph)

    def test_transform_authorships_ignora_ids_sin_uri(self):
        graph = Graph()
        df = pd.DataFrame([{"A": "id-desconocido", "B": "id-desconocido-2"}])

        transform.transform_authorships(graph, df, uri_lookup={})

        self.assertEqual(len(graph), 0)

    def test_add_pi_role_arma_el_nodo_con_relatedby_y_contributingrole(self):
        graph = Graph()
        person_uri = transform.make_uri("persona", "diego-torres")
        project_uri = transform.make_uri("proyecto", "proyecto-x")

        transform.add_pi_role(graph, project_uri, person_uri)

        rol_uri = transform.make_uri("rol-pi", "diego-torres--proyecto-x")
        self.assertIn((rol_uri, RDF.type, transform.VIVO.PrincipalInvestigatorRole), graph)
        self.assertIn((person_uri, transform.VIVO.relatedBy, rol_uri), graph)
        self.assertIn((rol_uri, transform.VIVO.relates, person_uri), graph)
        self.assertIn((rol_uri, transform.VIVO.roleContributesTo, project_uri), graph)
        self.assertIn((project_uri, transform.VIVO.contributingRole, rol_uri), graph)


# ---------------------------------------------------------------------------
# Grupo 2: el grafo ya generado (necesita extract.py + transform.py corridos)
# ---------------------------------------------------------------------------

class TestGeneratedGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(TTL_PATH) or not os.path.isdir(INTERIM_DIR):
            raise unittest.SkipTest(
                f"No encontré {TTL_PATH} ni {INTERIM_DIR}/. Corré "
                "'python src/etl/extract.py && python src/etl/transform.py' "
                "primero (necesita la base levantada) para poder validar el grafo."
            )
        cls.graph = Graph()
        cls.graph.parse(TTL_PATH, format="turtle")

    def _contar_filas_csv(self, tabla):
        df = pd.read_csv(os.path.join(INTERIM_DIR, f"{tabla}.csv"))
        return len(df)

    def test_ttl_parsea_sin_errores(self):
        # si llegamos acá, setUpClass ya lo parseó sin tirar excepción
        self.assertGreater(len(self.graph), 0)

    def test_cantidad_de_nodos_coincide_con_las_filas_de_la_base(self):
        # si un slug se repitiera entre dos filas, dos filas colapsarían en
        # una sola URI y este conteo daría distinto
        casos = [
            (transform.VIVO.FacultyMember, "Member"),
            (transform.VIVO.Project, "Project"),
            (transform.VIVO.Grant, "Scholarship"),
            (BIBO.Thesis, "Thesis"),
            (BIBO.Document, "Publication"),
        ]
        for rdf_class, tabla in casos:
            with self.subTest(tabla=tabla):
                nodos = len(list(self.graph.subjects(RDF.type, rdf_class)))
                filas = self._contar_filas_csv(tabla)
                self.assertEqual(nodos, filas, f"{tabla}: {nodos} nodos vs {filas} filas")

    def test_bibo_presentedAt_no_apunta_a_nada_huerfano(self):
        targets = set(self.graph.objects(None, BIBO.presentedAt))
        sujetos = set(self.graph.subjects())
        huerfanos = targets - sujetos
        self.assertEqual(huerfanos, set(), f"Venues referenciados que no existen: {huerfanos}")

    def test_mayoria_de_publications_tiene_subclase_dblp_especifica(self):
        pubs = set(self.graph.subjects(RDF.type, BIBO.Document))
        con_dblp = set()
        for clase in (DBLP.Article, DBLP.Inproceedings, DBLP.Incollection, DBLP.Book):
            con_dblp.update(self.graph.subjects(RDF.type, clase))
        # no exigimos el 100%: hay publicaciones con type "misc" que caen al
        # genérico bibo:Document a propósito (ver TYPE_TO_CLASS)
        proporcion = len(con_dblp) / len(pubs)
        self.assertGreaterEqual(proporcion, 0.9, f"Solo {proporcion:.0%} tiene subclase DBLP")

    def test_sin_mojibake_en_los_literales(self):
        from rdflib import Literal

        sospechosos = [
            str(o) for _, _, o in self.graph
            if isinstance(o, Literal) and any(ch in str(o) for ch in ("Ã", "Â", "�"))
        ]
        self.assertEqual(sospechosos, [], f"Literales con posible mojibake: {sospechosos[:5]}")

    def test_personas_externas_no_tienen_dos_nombres_distintos_en_la_misma_uri(self):
        # si esto fallara significaría que get_or_create_external_person
        # dedupeó mal y mezcló a dos personas distintas en un solo nodo
        nombres_por_uri = {}
        for s in self.graph.subjects(RDF.type, FOAF.Person):
            if "persona-externa" not in str(s):
                continue
            nombres = {str(n) for n in self.graph.objects(s, FOAF.name)}
            nombres_por_uri[str(s)] = nombres

        colisiones = {uri: n for uri, n in nombres_por_uri.items() if len(n) > 1}
        self.assertEqual(colisiones, {}, f"Personas externas con nombres mezclados: {colisiones}")

    def test_personas_externas_no_son_faculty_member(self):
        # la marca que las distingue del personal real del LIFIA
        externos = {
            s for s in self.graph.subjects(RDF.type, FOAF.Person)
            if "persona-externa" in str(s)
        }
        con_faculty = {s for s in externos if (s, RDF.type, transform.VIVO.FacultyMember) in self.graph}
        self.assertEqual(con_faculty, set(), "Hay personas externas marcadas como vivo:FacultyMember")

    def test_progress_de_thesis_no_esta_en_rdfs_comment(self):
        # regresión del bug que encontramos en la revisión final: progress
        # (0-100) estaba yendo como rdfs:comment en vez de una propiedad numérica
        from rdflib import Literal

        for s in self.graph.subjects(RDF.type, BIBO.Thesis):
            for comment in self.graph.objects(s, RDFS.comment):
                if isinstance(comment, Literal) and comment.datatype is not None:
                    self.assertNotIn(
                        "double", str(comment.datatype),
                        f"{s} tiene un número en rdfs:comment: {comment!r}",
                    )

    def test_completion_percentage_es_entero_entre_0_y_100(self):
        valores = list(self.graph.objects(None, transform.LIFIA_ONTOLOGY.completionPercentage))
        self.assertGreater(len(valores), 0, "No se generó ningún completionPercentage")
        for v in valores:
            entero = int(v)
            self.assertTrue(0 <= entero <= 100, f"completionPercentage fuera de rango: {v!r}")

    def test_no_quedan_terminos_vivo_inventados(self):
        # regresión: estos 6 términos no existen en ontologias/vivo.owl (se
        # verificó contra el archivo real), no deberían volver a aparecer
        inventados = [
            transform.VIVO.authorOf,
            transform.VIVO.hasPrincipalInvestigatorRole,
            transform.VIVO.ResearchProject,
            transform.VIVO.Thesis,
            transform.VIVO.highestDegree,
            transform.VIVO.webpage,
        ]
        for termino in inventados:
            with self.subTest(termino=termino):
                usado = (
                    (None, termino, None) in self.graph
                    or (None, RDF.type, termino) in self.graph
                )
                self.assertFalse(usado, f"{termino} no existe en VIVO real y no debería usarse")


if __name__ == "__main__":
    unittest.main()
