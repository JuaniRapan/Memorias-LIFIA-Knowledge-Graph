"""Test de punta a punta del pipeline CDC completo: hace un INSERT, un
UPDATE y un DELETE de verdad sobre Postgres y verifica, consultando
GraphDB por SPARQL, que cada cambio se haya reflejado.

A diferencia de tests/test_stream_consumer.py (que mockea todo), este SÍ
necesita la infra real levantada:
  - docker compose --env-file .env -f docker/docker-compose.yml up -d
  - el connector de Debezium registrado y RUNNING
  - python src/streaming/stream_consumer.py corriendo en otra terminal
    (este test no lo arranca solo: sin el consumer escuchando, los cambios
    nunca le llegarían a GraphDB y el test se cae por timeout)

Si algún prerrequisito no está, el test se salta con un mensaje. C
orrer con: python -m unittest tests.test_e2e_streaming -v
"""

import os
import sys
import time
import unittest
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "etl"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "streaming"))
from extract import get_db_connection  # noqa: E402
import graphdb_client  # noqa: E402

FOAF_FIRST_NAME = "http://xmlns.com/foaf/0.1/firstName"
CONNECTOR_STATUS_URL = "http://localhost:8083/connectors/lifia-postgres-connector/status"

POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 60


def _connector_esta_running():
    try:
        with urllib.request.urlopen(CONNECTOR_STATUS_URL, timeout=5) as response:
            import json
            status = json.load(response)
        return status.get("connector", {}).get("state") == "RUNNING"
    except (urllib.error.URLError, OSError):
        return False


def _member_first_names(uri):
    """Devuelve los valores de foaf:firstName que tiene guardados esa URI en GraphDB ahora mismo."""
    query = f'SELECT ?nombre WHERE {{ <{uri}> <{FOAF_FIRST_NAME}> ?nombre }}'
    bindings = graphdb_client.run_query(query)
    return [b["nombre"]["value"] for b in bindings]


def _wait_until(condition, timeout=POLL_TIMEOUT_SECONDS, interval=POLL_INTERVAL_SECONDS):
    """Reintenta condition() (una función sin argumentos) hasta que dé un
    resultado verdadero o se cumpla el timeout. Devuelve el último resultado"""
    deadline = time.time() + timeout
    result = condition()
    while not result and time.time() < deadline:
        time.sleep(interval)
        result = condition()
    return result


class TestEndToEndStreaming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = get_db_connection()
        if conn is None:
            raise unittest.SkipTest(
                "No se pudo conectar a Postgres. Levantá el stack con "
                "'docker compose --env-file .env -f docker/docker-compose.yml up -d'."
            )
        conn.close()

        try:
            graphdb_client.run_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")
        except (urllib.error.URLError, OSError) as e:
            raise unittest.SkipTest(f"No se pudo conectar a GraphDB en {graphdb_client.GRAPHDB_URL}: {e}")

        if not _connector_esta_running():
            raise unittest.SkipTest(
                "El connector de Debezium no está RUNNING. Registralo con "
                "'bash docker/register-connector.sh' y confirmalo contra "
                "http://localhost:8083/connectors/lifia-postgres-connector/status."
            )

        print(
            "\nste test asume que 'python src/streaming/stream_consumer.py' "
            "ya está corriendo en otra terminal. Si no, va a fallar por timeout."
        )

    def test_insert_update_delete_se_reflejan_en_graphdb(self):
        slug = f"test-e2e-cdc-{uuid.uuid4().hex[:8]}"
        uri = f"http://lifia.info.unlp.edu.ar/resource/persona/{slug}"
        member_id = str(uuid.uuid4())

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # seteamos createdAt/updatedAt a mano
            cur.execute(
                'INSERT INTO "Member" (id, "firstName", "lastName", slug, "createdAt", "updatedAt") '
                'VALUES (%s, %s, %s, %s, NOW(), NOW())',
                (member_id, "Test", "E2E", slug),
            )
            conn.commit()

            encontrado = _wait_until(lambda: _member_first_names(uri))
            self.assertEqual(
                encontrado, ["Test"],
                "El INSERT no llegó a GraphDB a tiempo (chequear si está corriendo stream_consumer.py)",
            )

            # UPDATE
            cur.execute('UPDATE "Member" SET "firstName" = %s WHERE id = %s', ("Test Actualizado", member_id))
            conn.commit()

            actualizado = _wait_until(lambda: _member_first_names(uri) == ["Test Actualizado"])
            self.assertTrue(actualizado, "El UPDATE no llegó a GraphDB a tiempo")

            # DELETE
            cur.execute('DELETE FROM "Member" WHERE id = %s', (member_id,))
            conn.commit()

            borrado = _wait_until(lambda: _member_first_names(uri) == [])
            self.assertTrue(borrado, "El DELETE no se reflejó en GraphDB a tiempo")
        finally:
            # si algo falló a mitad de camino, nos aseguramos de no dejar
            # datos de prueba en la bd
            cur.execute('DELETE FROM "Member" WHERE id = %s', (member_id,))
            conn.commit()
            cur.close()
            conn.close()


if __name__ == "__main__":
    unittest.main()
