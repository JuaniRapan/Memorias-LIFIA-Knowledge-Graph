"""Capa de transformación: arma el grafo RDF a partir de los CSV que deja
extract.py."""

import os
import re
import unicodedata

import pandas as pd
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import FOAF, OWL, RDF, RDFS

from extract import load_interim


# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------

LIFIA = Namespace("http://lifia.info.unlp.edu.ar/resource/")
VIVO = Namespace("http://vivoweb.org/ontology/core#")
BIBO = Namespace("http://purl.org/ontology/bibo/")
DCTERMS = Namespace("http://purl.org/dc/terms/")


# ---------------------------------------------------------------------------
# Helpers base
# ---------------------------------------------------------------------------

def has_value(value):
    """True si `value` es un dato real (no None ni NaN de pandas)."""
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    return True


def slugify(texto):
    """Normaliza texto para usarlo como identificador de una URI."""
    if not has_value(texto):
        return ""
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    return texto.strip("-")


def make_uri(tipo_recurso, identificador_local):
    """Arma la URI final: {LIFIA}/{tipo_recurso}/{identificador_local}."""
    return LIFIA[f"{tipo_recurso}/{identificador_local}"]


URL_RE = re.compile(r"^https?://\S+$")


def add_literal(graph, subject, predicate, value, as_uri=False):
    """Agrega (subject, predicate, value) solo si value tiene contenido real."""
    if not has_value(value):
        return
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return
        # as_uri pide una URL (webPage, avatarUrl, etc), pero algunos campos
        # "de url" en realidad son una oración con un link adentro, por eso
        # solo se arma URIRef si tiene pinta de URL de verdad; si no, Literal
        # para no romper el Turtle
        if as_uri and URL_RE.match(value):
            graph.add((subject, predicate, URIRef(value)))
        else:
            graph.add((subject, predicate, Literal(value)))
    else:
        graph.add((subject, predicate, Literal(value)))


def add_interval(graph, subject, start, end):
    """Arma un blank node vivo:DateTimeInterval con start/end."""
    if not has_value(start) and not has_value(end):
        return
    interval = BNode()
    graph.add((subject, VIVO.dateTimeInterval, interval))
    graph.add((interval, RDF.type, VIVO.DateTimeInterval))
    if has_value(start):
        graph.add((interval, VIVO.start, Literal(start)))
    if has_value(end):
        graph.add((interval, VIVO.end, Literal(end)))


def clean_orcid(value):
    """Limpia el campo orcid (a veces trae el prefijo de URL) y devuelve solo el id, o ""."""
    if not has_value(value) or not str(value).strip():
        return ""
    text = str(value).strip()
    text = re.sub(r"^https?://orcid\.org/\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


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
        add_literal(graph, uri, FOAF.homepage, row["webPage"], as_uri=True)
        add_literal(graph, uri, FOAF.depiction, row["avatarUrl"], as_uri=True)
        add_literal(graph, uri, VIVO.hrJobTitle, row["positionAtLab"])
        add_literal(graph, uri, RDFS.comment, row["category"])
        add_literal(graph, uri, VIVO.overview, row["shortCvInSpanish"])
        add_interval(graph, uri, row["startDate"], row["endDate"])

        orcid_id = clean_orcid(row["orcid"])
        if orcid_id:
            graph.add((uri, OWL.sameAs, URIRef(f"https://orcid.org/{orcid_id}")))
        add_literal(graph, uri, OWL.sameAs, row["dblpProfile"], as_uri=True)
        add_literal(graph, uri, RDFS.seeAlso, row["googleResearchProfile"], as_uri=True)
        add_literal(graph, uri, RDFS.seeAlso, row["researchGateProfile"], as_uri=True)

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
# Venues: no tienen tabla propia en la base, salen del bibtexData de cada
# Publication
# ---------------------------------------------------------------------------

def get_entry_tags(bibtex_data):
    """Devuelve el dict entryTags de bibtexData, o {} si no hay nada usable."""
    # hay publicaciones "raw" sin entryTags, solo un `reference` de texto
    # libre con toda la cita, por eso siempre hay que devolver un dict
    if not isinstance(bibtex_data, dict):
        return {}
    entry_tags = bibtex_data.get("entryTags")
    return entry_tags if isinstance(entry_tags, dict) else {}


def transform_venues(graph, df_publication):
    """Arma bibo:Journal/Conference a partir de bibtexData, dedupeados. Devuelve {slug: uri}."""
    venue_uris = {}

    for _, row in df_publication.iterrows():
        entry_tags = get_entry_tags(row["bibtexData"])
        journal = entry_tags.get("journal")
        booktitle = entry_tags.get("booktitle")
        name = (journal or booktitle or "").strip()
        if not name:
            continue

        slug = slugify(name)
        if not slug or slug in venue_uris:
            continue

        uri = make_uri("venue", slug)
        graph.add((uri, RDF.type, BIBO.Journal if journal else BIBO.Conference))
        graph.add((uri, RDFS.label, Literal(name)))
        add_literal(graph, uri, BIBO.issn, entry_tags.get("issn"))
        add_literal(graph, uri, BIBO.isbn, entry_tags.get("isbn"))
        venue_uris[slug] = uri

    return venue_uris


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------

def transformation(dataframes=None):
    """Orquesta el ETL: arma los nodos de Member y Project, y los Venues."""
    if dataframes is None:
        dataframes = load_interim()

    graph = Graph()
    graph.bind("lifia", LIFIA)
    graph.bind("vivo", VIVO)
    graph.bind("bibo", BIBO)
    graph.bind("foaf", FOAF)
    graph.bind("dcterms", DCTERMS)

    venue_uris = transform_venues(graph, dataframes["Publication"])
    print(f"Venues encontrados: {len(venue_uris)}")

    transform_members(graph, dataframes["Member"])
    transform_projects(graph, dataframes["Project"])

    return graph


if __name__ == "__main__":
    graph = transformation()
    print(f"Triples generados: {len(graph)}")

    os.makedirs("data/processed", exist_ok=True)
    graph.serialize(destination="data/processed/lifia_graph.ttl", format="turtle")
