"""Capa de transformación: arma el grafo RDF a partir de los CSV que deja
extract.py."""

import re
import unicodedata

from rdflib import Graph, Literal, Namespace
from rdflib.namespace import FOAF, RDF, RDFS


# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------

LIFIA = Namespace("http://lifia.info.unlp.edu.ar/resource/")
VIVO = Namespace("http://vivoweb.org/ontology/core#")


# ---------------------------------------------------------------------------
# Helpers base
# ---------------------------------------------------------------------------

def slugify(texto):
    """Normaliza texto para usarlo como identificador de una URI."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    return texto.strip("-")


def make_uri(tipo_recurso, identificador_local):
    """Arma la URI final: {LIFIA}/{tipo_recurso}/{identificador_local}."""
    return LIFIA[f"{tipo_recurso}/{identificador_local}"]


def add_literal(graph, subject, predicate, value):
    """Agrega (subject, predicate, value) si value tiene algo cargado."""
    # Por ahora alcanza con esto para probar los primeros mappings, después
    # hay que ver bien el tema de los NaN de pandas y los campos que son URL
    if value is None or value == "":
        return
    graph.add((subject, predicate, Literal(value)))


# ---------------------------------------------------------------------------
# Prueba helpers
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    graph = Graph()
    graph.bind("lifia", LIFIA)
    graph.bind("vivo", VIVO)
    graph.bind("foaf", FOAF)

    uri = make_uri("persona", slugify("Juan Pérez"))
    graph.add((uri, RDF.type, FOAF.Person))
    add_literal(graph, uri, FOAF.firstName, "Juan")
    add_literal(graph, uri, FOAF.lastName, "Pérez")

    print(graph.serialize(format="turtle"))
