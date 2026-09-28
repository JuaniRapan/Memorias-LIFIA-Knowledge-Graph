"""Cliente HTTP minimo para el endpoint SPARQL de GraphDB."""

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

GRAPHDB_URL = os.getenv("GRAPHDB_URL", "http://localhost:7200")
GRAPHDB_REPOSITORY = os.getenv("GRAPHDB_REPOSITORY", "memorias-lifia")

# cantidad de reintentos ante una caída transitoria y segundos de espera
# base para el backoff exponencial (2s, 4s, 8s)
MAX_REINTENTOS = 3
ESPERA_BASE_SEGUNDOS = 2


def _abrir_con_reintentos(request):
    """Manda el request a GraphDB reintentando con backoff exponencial ante
    timeouts, desconexiones o errores."""
    ultimo_error = None
    for intento in range(MAX_REINTENTOS):
        try:
            return urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as error:
            if error.code < 500:
                raise
            ultimo_error = error
        except urllib.error.URLError as error:
            ultimo_error = error
        time.sleep(ESPERA_BASE_SEGUNDOS * (2 ** intento))
    raise ultimo_error


def run_update(sparql_update):
    """Ejecuta un SPARQL Update (INSERT DATA / DELETE DATA) contra el repositorio."""
    url = f"{GRAPHDB_URL}/repositories/{GRAPHDB_REPOSITORY}/statements"
    request = urllib.request.Request(
        url,
        data=sparql_update.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/sparql-update; charset=utf-8"},
    )
    with _abrir_con_reintentos(request) as response:
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
    with _abrir_con_reintentos(request) as response:
        return json.load(response)["results"]["bindings"]
