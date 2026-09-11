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


def _post_turtle(path):
    """Postea un archivo .ttl entero al repo de GraphDB."""
    with open(path, "rb") as f:
        turtle_data = f.read()

    url = f"{GRAPHDB_URL}/repositories/{GRAPHDB_REPOSITORY}/statements"
    request = urllib.request.Request(
        url,
        data=turtle_data,
        method="POST",
        headers={"Content-Type": "text/turtle; charset=utf-8"},
    )
    with urllib.request.urlopen(request) as response:
        print(f"{path} subido a GraphDB (status {response.status})")


def load():
    _post_turtle(TTL_PATH)
    _post_turtle(CSO_HIERARCHY_PATH)


if __name__ == "__main__":
    load()
