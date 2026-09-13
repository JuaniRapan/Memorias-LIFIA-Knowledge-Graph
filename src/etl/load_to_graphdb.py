"""Sube el grafo ya armado por transform.py (data/processed/lifia_graph.ttl)
a GraphDB de una sola vez, como carga inicial. Correr una sola vez, antes de
arrancar stream_consumer.py (que después mantiene el grafo tras cada actualización, no vuelve a tocar la carga histórica)."""

import os
import urllib.request

from dotenv import load_dotenv

load_dotenv()

GRAPHDB_URL = os.getenv("GRAPHDB_URL", "http://localhost:7200")
GRAPHDB_REPOSITORY = os.getenv("GRAPHDB_REPOSITORY", "memorias-lifia")
TTL_PATH = "data/processed/lifia_graph.ttl"
# jerarquía de CSO hecha a mano (subconjunto con datos que están en el grafo de LIFIA y sus superclases)
CSO_HIERARCHY_PATH = "data/external/cso_jerarquia.ttl"

VIVO_ONTOLOGY_PATH = "ontologias/vivo.owl"


def _post_statements(path, content_type):
    """Postea un archivo RDF entero (Turtle o RDF/XML) al repo de GraphDB."""
    with open(path, "rb") as f:
        rdf_data = f.read()

    url = f"{GRAPHDB_URL}/repositories/{GRAPHDB_REPOSITORY}/statements"
    request = urllib.request.Request(
        url,
        data=rdf_data,
        method="POST",
        headers={"Content-Type": f"{content_type}; charset=utf-8"},
    )
    with urllib.request.urlopen(request) as response:
        print(f"{path} subido a GraphDB (status {response.status})")


def _post_turtle(path):
    """Postea un archivo .ttl entero al repo de GraphDB."""
    _post_statements(path, "text/turtle")


def load():
    _post_statements(VIVO_ONTOLOGY_PATH, "application/rdf+xml")
    _post_turtle(TTL_PATH)
    _post_turtle(CSO_HIERARCHY_PATH)


if __name__ == "__main__":
    load()
