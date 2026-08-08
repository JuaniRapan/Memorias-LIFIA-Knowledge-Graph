"""Capa de transformación: arma el grafo RDF a partir de los CSV que deja
extract.py."""

import csv
import os
import re
import unicodedata
import urllib.request

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
CSO = Namespace("http://cso.kmi.open.ac.uk/schema/cso#")
CSO_TOPICS = Namespace("https://cso.kmi.open.ac.uk/topics/")
DBLP = Namespace("https://dblp.org/rdf/schema#")
DC = Namespace("http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


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


def add_topics(graph, subject, tags_value, topic_uris, predicate):
    """Por cada tag de tags_value que ya tenga URI en topic_uris, agrega subject -predicate-> topic_uri."""
    if not isinstance(tags_value, (list, tuple)):
        return
    for tag in tags_value:
        tag = str(tag).strip()
        if tag and tag in topic_uris:
            graph.add((subject, predicate, topic_uris[tag]))


# ---------------------------------------------------------------------------
# Temas (tags/keywords): no tienen tabla propia en la base, se arman antes
# que las entidades porque después se usan para vivo:hasSubjectArea
# ---------------------------------------------------------------------------

CSO_CSV_URL = "https://cso.kmi.open.ac.uk/download/version-3.5/cso_v3.5.csv"
CSO_CACHE_PATH = "data/external/cso.csv"


def normalize_topic_label(texto):
    """Normaliza un label para matchear contra CSO (minúscula, guion a espacio)."""
    # hace falta aparte de slugify() porque CSO tiene labels con guion y sin
    # guion apuntando al mismo tema (ej "human-computer interaction" vs
    # "human computer interaction"), y así las dos calzan la misma clave
    texto = texto.lower().strip()
    texto = texto.replace("-", " ")
    return re.sub(r"\s+", " ", texto)


def load_cso_lookup(cache_path=CSO_CACHE_PATH):
    """Arma {label_normalizado: uri_del_topic} bajando y parseando el CSV oficial de CSO (se cachea en disco)."""
    # el CSV es una lista de tripletas sujeto;predicado;objeto:
    #   - "sujeto;rdf:type;klink:Topic" -> "sujeto" es un topic válido
    #   - "sujeto;klink:primaryLabel;objeto" -> "sujeto" agrupa bajo el
    #     label canónico "objeto" (ej "web pages" bajo "web content")
    if not os.path.exists(cache_path):
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        print("Bajando el vocabulario de CSO (la primera vez nomás, después queda cacheado)...")
        urllib.request.urlretrieve(CSO_CSV_URL, cache_path)

    primary_label = {}
    topic_labels = set()
    with open(cache_path, encoding="utf-8") as f:
        for row in csv.reader(f, delimiter=";"):
            if len(row) != 3:
                continue
            subject, predicate, obj = row
            if predicate == "rdf:type" and obj == "klink:Topic":
                topic_labels.add(subject)
            elif predicate == "klink:primaryLabel":
                primary_label[subject] = obj

    lookup = {}
    for label in topic_labels:
        canonical = primary_label.get(label, label)
        topic_id = canonical.replace(" ", "_").replace("-", "_")
        lookup[normalize_topic_label(label)] = CSO_TOPICS[topic_id]

    return lookup


def transform_topics(graph, dataframes):
    """Junta todos los tags/keywords del dataset, los matchea contra CSO
    (reusando su URI) o crea un cso:Topic local. Devuelve {tag: uri}."""
    all_tags = set()

    for table in ("Member", "Project", "Publication", "Thesis"):
        for tags in dataframes[table]["tags"]:
            if isinstance(tags, (list, tuple)):
                all_tags.update(str(t).strip() for t in tags if str(t).strip())

    for keyword in dataframes["Thesis"]["keywords"]:
        if has_value(keyword) and str(keyword).strip():
            all_tags.add(str(keyword).strip())

    cso_lookup = load_cso_lookup()

    topic_uris = {}
    matcheados = 0
    for tag in sorted(all_tags):
        cso_uri = cso_lookup.get(normalize_topic_label(tag))
        if cso_uri is not None:
            topic_uris[tag] = cso_uri
            matcheados += 1
            continue

        slug = slugify(tag)
        if not slug:
            continue
        uri = make_uri("tema", slug)
        graph.add((uri, RDF.type, CSO.Topic))
        graph.add((uri, RDF.type, SKOS.Concept))
        graph.add((uri, RDFS.label, Literal(tag)))
        graph.add((uri, SKOS.prefLabel, Literal(tag)))
        topic_uris[tag] = uri

    print(f"Temas: {matcheados} de {len(topic_uris)} matchearon contra CSO, el resto quedó como recurso local")
    return topic_uris


# ---------------------------------------------------------------------------
# Transformación de entidades
# ---------------------------------------------------------------------------

def transform_members(graph, df_member, topic_uris):
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

        add_topics(graph, uri, row["tags"], topic_uris, VIVO.hasResearchArea)
        graph.add((uri, DCTERMS.identifier, Literal(row["id"])))

    return uri_lookup


def transform_projects(graph, df_project, topic_uris):
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

        add_topics(graph, uri, row["tags"], topic_uris, VIVO.hasSubjectArea)
        graph.add((uri, DCTERMS.identifier, Literal(row["id"])))

    return uri_lookup


def transform_scholarships(graph, df_scholarship, topic_uris):
    """Convierte cada fila de Scholarship en un vivo:Grant."""
    uri_lookup = {}

    for _, row in df_scholarship.iterrows():
        uri = make_uri("beca", row["slug"])
        uri_lookup[row["id"]] = uri

        graph.add((uri, RDF.type, VIVO.Grant))
        add_literal(graph, uri, RDFS.label, row["title"])
        add_literal(graph, uri, RDFS.comment, row["type"])
        add_literal(graph, uri, RDFS.comment, row["fundingAgency"])
        add_literal(graph, uri, VIVO.description, row["summary"])
        add_interval(graph, uri, row["startDate"], row["endDate"])
        add_topics(graph, uri, row["tags"], topic_uris, VIVO.hasSubjectArea)
        graph.add((uri, DCTERMS.identifier, Literal(row["id"])))

    return uri_lookup


# level viene limpio, son 4 valores fijos. career en cambio es texto libre,
#  así que se usa level para el bibo:degree y career
# se guarda nomás como comentario
LEVEL_TO_DEGREE = {
    "Undergraduate": "Grado",
    "Masters": "Maestría",
    "PhD": "Doctorado",
    "Specialization": "Especialización",
}


def transform_theses(graph, df_thesis, topic_uris):
    """Convierte cada fila de Thesis en bibo:Thesis/vivo:Thesis."""
    uri_lookup = {}

    for _, row in df_thesis.iterrows():
        uri = make_uri("tesis", row["slug"])
        uri_lookup[row["id"]] = uri

        graph.add((uri, RDF.type, BIBO.Thesis))
        graph.add((uri, RDF.type, VIVO.Thesis))
        add_literal(graph, uri, DC.title, row["title"])
        add_literal(graph, uri, BIBO.degree, LEVEL_TO_DEGREE.get(row["level"], row["level"]))
        add_literal(graph, uri, RDFS.comment, row["career"])
        add_literal(graph, uri, VIVO.description, row["summary"])
        add_literal(graph, uri, BIBO.uri, row["reportUrl"], as_uri=True)
        add_literal(graph, uri, BIBO.uri, row["website"], as_uri=True)
        add_literal(graph, uri, RDFS.comment, row["progress"])
        add_interval(graph, uri, row["startDate"], row["endDate"])
        add_topics(graph, uri, row["tags"], topic_uris, VIVO.hasSubjectArea)

        keyword = row["keywords"]
        if has_value(keyword) and str(keyword).strip() in topic_uris:
            graph.add((uri, VIVO.hasSubjectArea, topic_uris[str(keyword).strip()]))

        graph.add((uri, DCTERMS.identifier, Literal(row["id"])))

    return uri_lookup


# el campo type de Publication viene limpio desde el bibtex (article,
# inproceedings, inbook, book, misc) y matchea casi 1 a 1 con las clases
# del schema RDF de DBLP, por eso se arma como diccionario directo
TYPE_TO_CLASS = {
    "article": DBLP.Article,
    "inproceedings": DBLP.Inproceedings,
    "inbook": DBLP.Incollection,
    "book": DBLP.Book,
}


def transform_publications(graph, df_publication, topic_uris, venue_uris):
    """Convierte cada fila de Publication en su clase DBLP/BIBO correspondiente."""
    uri_lookup = {}

    for _, row in df_publication.iterrows():
        uri = make_uri("publicacion", row["slug"])
        uri_lookup[row["id"]] = uri

        graph.add((uri, RDF.type, TYPE_TO_CLASS.get(row["type"], BIBO.Document)))
        graph.add((uri, RDF.type, BIBO.Document))
        add_literal(graph, uri, DC.title, row["title"])
        add_literal(graph, uri, VIVO.dateIssued, row["year"])
        add_literal(graph, uri, BIBO.uri, row["selfArchivingUrl"], as_uri=True)
        ranking = row["ranking"]
        if has_value(ranking) and str(ranking).strip():
            add_literal(graph, uri, RDFS.comment, ranking)

        entry_tags = get_entry_tags(row["bibtexData"])

        doi = entry_tags.get("doi")
        if doi and str(doi).strip():
            # algunos DOI vienen con un escapado de LaTeX de más (\_ en vez de _)
            add_literal(graph, uri, BIBO.doi, str(doi).replace("\\_", "_").strip())

        pages = entry_tags.get("pages")
        if pages:
            parts = re.split(r"--|-", str(pages))
            if len(parts) == 2:
                add_literal(graph, uri, BIBO.pageStart, parts[0].strip())
                add_literal(graph, uri, BIBO.pageEnd, parts[1].strip())

        venue_name = (entry_tags.get("journal") or entry_tags.get("booktitle") or "").strip()
        venue_slug = slugify(venue_name) if venue_name else ""
        if venue_slug and venue_slug in venue_uris:
            graph.add((uri, BIBO.presentedAt, venue_uris[venue_slug]))

        # authors trae la lista completa de autores como un solo string
        # (incluye coautores que no son del LIFIA), así que se vuelca como
        # dc:creator en texto libre. La relación "real" con los Member del
        # lab se arma aparte, a partir de la tabla _PublicationMembers
        authors_raw = row["authors"]
        if has_value(authors_raw) and str(authors_raw).strip():
            for author in str(authors_raw).split(" and "):
                author = author.strip()
                if author:
                    graph.add((uri, DC.creator, Literal(author)))

        add_topics(graph, uri, row["tags"], topic_uris, VIVO.hasSubjectArea)
        graph.add((uri, DCTERMS.identifier, Literal(row["id"])))

    return uri_lookup


# ---------------------------------------------------------------------------
# Relaciones que salen directo de las tablas de join (FK real, ver
# extract.JOIN_TABLES)
# ---------------------------------------------------------------------------

# tabla de join -> propiedad RDF a usar entre A y B, según las FK reales
# del dump (A y B siempre son el id de dos de las 5 entidades principales)
JOIN_SPEC = {
    "_ProjectMembers": VIVO.contributingRole,
    "_PublicationMembers": VIVO.authorOf,
    "_ThesisMembers": VIVO.relatedBy,
    "_ScholarshipMembers": VIVO.relatedBy,
    "_ProjectPublications": VIVO.relatedBy,
    "_ProjectScholarships": VIVO.relatedBy,
    "_ProjectTheses": VIVO.relatedBy,
    "_ThesisPublications": VIVO.relatedBy,
    "_ThesisScholarships": VIVO.relatedBy,
}


def transform_relations(graph, dataframes, uri_lookup):
    """Agrega A -predicate-> B por cada fila de las tablas de join, según JOIN_SPEC."""
    # las tablas de join solo traen el id (UUID) de cada lado, no el slug
    # con el que se arma la URI, por eso hace falta uri_lookup (id -> uri)
    for join_table, predicate in JOIN_SPEC.items():
        for _, row in dataframes[join_table].iterrows():
            uri_a = uri_lookup.get(row["A"])
            uri_b = uri_lookup.get(row["B"])
            if uri_a is not None and uri_b is not None:
                graph.add((uri_a, predicate, uri_b))


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
    """Orquesta el ETL: arma temas y venues, después las 5 entidades y sus relaciones."""
    if dataframes is None:
        dataframes = load_interim()

    graph = Graph()
    graph.bind("lifia", LIFIA)
    graph.bind("vivo", VIVO)
    graph.bind("bibo", BIBO)
    graph.bind("cso", CSO)
    graph.bind("dblp", DBLP)
    graph.bind("foaf", FOAF)
    graph.bind("dc", DC)
    graph.bind("dcterms", DCTERMS)
    graph.bind("skos", SKOS)

    # temas y venues van primero: el resto de las funciones los necesitan
    topic_uris = transform_topics(graph, dataframes)
    venue_uris = transform_venues(graph, dataframes["Publication"])

    uri_lookup = {}
    uri_lookup.update(transform_members(graph, dataframes["Member"], topic_uris))
    uri_lookup.update(transform_projects(graph, dataframes["Project"], topic_uris))
    uri_lookup.update(transform_publications(graph, dataframes["Publication"], topic_uris, venue_uris))
    uri_lookup.update(transform_scholarships(graph, dataframes["Scholarship"], topic_uris))
    uri_lookup.update(transform_theses(graph, dataframes["Thesis"], topic_uris))

    transform_relations(graph, dataframes, uri_lookup)

    return graph


if __name__ == "__main__":
    graph = transformation()
    print(f"Triples generados: {len(graph)}")

    os.makedirs("data/processed", exist_ok=True)
    graph.serialize(destination="data/processed/lifia_graph.ttl", format="turtle")
