"""Cliente HTTP minimo para el endpoint SPARQL de GraphDB."""

import json
import os
import urllib.request

from dotenv import load_dotenv

load_dotenv()

GRAPHDB_URL = os.getenv("GRAPHDB_URL", "http://localhost:7200")
GRAPHDB_REPOSITORY = os.getenv("GRAPHDB_REPOSITORY", "memorias-lifia")


def run_update(sparql_update):
    """Ejecuta un SPARQL Update (INSERT DATA / DELETE DATA) contra el repositorio."""
    url = f"{GRAPHDB_URL}/repositories/{GRAPHDB_REPOSITORY}/statements"
    request = urllib.request.Request(
        url,
        data=sparql_update.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/sparql-update; charset=utf-8"},
    )
    with urllib.request.urlopen(request) as response:
        return response.status


def run_query(sparql_select):
    """Ejecuta un SPARQL SELECT contra el repositorio. Devuelve la lista de
    bindings tal cual viene en el formato JSON estándar de resultados SPARQL."""
    url = f"{GRAPHDB_URL}/repositories/{GRAPHDB_REPOSITORY}"
    request = urllib.request.Request(
        url,
        data=sparql_select.encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/sparql-query; charset=utf-8",
            "Accept": "application/sparql-results+json",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)["results"]["bindings"]
