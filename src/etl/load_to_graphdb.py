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


def load():
    with open(TTL_PATH, "rb") as f:
        turtle_data = f.read()

    url = f"{GRAPHDB_URL}/repositories/{GRAPHDB_REPOSITORY}/statements"
    request = urllib.request.Request(
        url,
        data=turtle_data,
        method="POST",
        headers={"Content-Type": "text/turtle; charset=utf-8"},
    )
    with urllib.request.urlopen(request) as response:
        print(f"Carga inicial subida a GraphDB (status {response.status})")


if __name__ == "__main__":
    load()
