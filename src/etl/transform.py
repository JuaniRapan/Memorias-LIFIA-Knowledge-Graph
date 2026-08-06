"""Capa de transformación: arma el grafo RDF a partir de los CSV que deja
extract.py."""

import os
import re
import unicodedata

from rdflib import BNode, Graph, Literal, Namespace
from rdflib.namespace import FOAF, RDF, RDFS

from extract import load_interim


# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------

LIFIA = Namespace("http://lifia.info.unlp.edu.ar/resource/")
VIVO = Namespace("http://vivoweb.org/ontology/core#")
DCTERMS = Namespace("http://purl.org/dc/terms/")


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


def add_interval(graph, subject, start, end):
    """Arma un blank node vivo:DateTimeInterval con start/end."""
    if start is None and end is None:
        return
    interval = BNode()
    graph.add((subject, VIVO.dateTimeInterval, interval))
    graph.add((interval, RDF.type, VIVO.DateTimeInterval))
    if start is not None:
        graph.add((interval, VIVO.start, Literal(start)))
    if end is not None:
        graph.add((interval, VIVO.end, Literal(end)))


# ---------------------------------------------------------------------------
# Transformación de entidades
# ---------------------------------------------------------------------------

def transform_members(graph, df_member):
    """Convierte cada fila de Member en un vivo:FacultyMember/foaf:Person."""
    uri_lookup = {}

    for _, row in df_member.iterrows():
        uri = make_uri("persona", row["slug"])
        uri_lookup[row["id"]] = uri

        graph.add((uri, RDF.type, VIVO.FacultyMember))
        graph.add((uri, RDF.type, FOAF.Person))

        add_literal(graph, uri, FOAF.firstName, row["firstName"])
        add_literal(graph, uri, FOAF.lastName, row["lastName"])
        add_literal(graph, uri, FOAF.mbox, row["personalEmail"])
        add_literal(graph, uri, FOAF.mbox, row["institutionalEmail"])
        add_literal(graph, uri, FOAF.phone, row["phone"])
        add_literal(graph, uri, FOAF.homepage, row["webPage"])
        add_literal(graph, uri, VIVO.hrJobTitle, row["positionAtLab"])
        add_literal(graph, uri, RDFS.comment, row["category"])
        add_literal(graph, uri, VIVO.overview, row["shortCvInSpanish"])
        add_interval(graph, uri, row["startDate"], row["endDate"])

        graph.add((uri, DCTERMS.identifier, Literal(row["id"])))

    return uri_lookup


def transform_projects(graph, df_project):
    """Convierte cada fila de Project en un vivo:ResearchProject."""
    uri_lookup = {}

    for _, row in df_project.iterrows():
        uri = make_uri("proyecto", row["slug"])
        uri_lookup[row["id"]] = uri

        graph.add((uri, RDF.type, VIVO.ResearchProject))
        add_literal(graph, uri, RDFS.label, row["title"])
        add_literal(graph, uri, VIVO.localAwardId, row["code"])
        add_literal(graph, uri, RDFS.comment, row["fundingAgency"])
        add_literal(graph, uri, VIVO.description, row["summary"])
        add_interval(graph, uri, row["startDate"], row["endDate"])

        graph.add((uri, DCTERMS.identifier, Literal(row["id"])))

    return uri_lookup


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------

def transformation(dataframes=None):
    """Orquesta el ETL: arma los nodos de Member y Project."""
    if dataframes is None:
        dataframes = load_interim()

    graph = Graph()
    graph.bind("lifia", LIFIA)
    graph.bind("vivo", VIVO)
    graph.bind("foaf", FOAF)
    graph.bind("dcterms", DCTERMS)

    transform_members(graph, dataframes["Member"])
    transform_projects(graph, dataframes["Project"])

    return graph


if __name__ == "__main__":
    graph = transformation()
    print(f"Triples generados: {len(graph)}")

    os.makedirs("data/processed", exist_ok=True)
    graph.serialize(destination="data/processed/lifia_graph.ttl", format="turtle")
