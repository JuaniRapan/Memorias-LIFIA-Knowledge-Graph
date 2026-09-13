"""Consumidor CDC: escucha los tópicos de Kafka que arma Debezium y traduce
cada evento a triples RDF, reusando las funciones de transform.py, para
mantener sincronizado el repositorio real de GraphDB (vía SPARQL Update)."""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

from confluent_kafka import Consumer
from dotenv import load_dotenv
from rdflib import Graph, Literal, URIRef

import graphdb_client

# transform.py hace "from extract import ..." asumiendo que está en el mismo
# directorio de sys.path; al correr este script, Python solo agrega
# src/streaming/ automáticamente, así que hay que sumar src/etl/ a mano

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "etl"))
from extract import clean_member_na_row  # noqa: E402
from transform import (  # noqa: E402
    make_uri, slugify, get_entry_tags, load_cso_lookup,
    resolve_topic_uri, resolve_venue_uri,
    transform_member_row, transform_project_row, transform_scholarship_row,
    transform_thesis_row, transform_publication_row,
    JOIN_SPEC, add_authorship,
)

load_dotenv()

# tabla de Postgres -> segmento de URI que usa make_uri para esa entidad
# (tiene que coincidir con lo que usa cada transform_*_row en transform.py)
RESOURCE_TYPE_BY_TABLE = {
    "Member": "persona",
    "Project": "proyecto",
    "Scholarship": "beca",
    "Thesis": "tesis",
    "Publication": "publicacion",
}

# función de transform.py que convierte una fila de esta tabla en triples.
# Publication queda afuera porque necesita un tercer argumento (venue_uris)
ROW_TRANSFORMS = {
    "Member": transform_member_row,
    "Project": transform_project_row,
    "Scholarship": transform_scholarship_row,
    "Thesis": transform_thesis_row,
}

# tablas de join: JOIN_SPEC (de transform.py) ya tiene 8 de las 9 con su
# propiedad directa; _PublicationMembers queda afuera de JOIN_SPEC porque
# arma un nodo vivo:Authorship en vez de una propiedad directa (ver
# add_authorship en transform.py)
JOIN_TABLES = list(JOIN_SPEC) + ["_PublicationMembers"]

TOPICS = [
    f"lifia.public.{tabla}"
    for tabla in list(RESOURCE_TYPE_BY_TABLE) + JOIN_TABLES
]

EPOCH = date(1970, 1, 1)


def _decode_logical_type(value, field_schema):
    """Traduce un valor codificado por Debezium a su tipo Python real, según
    el nombre del tipo lógico que trae el propio schema del mensaje."""
    if value is None:
        return None

    logical_name = field_schema.get("name")
    if logical_name == "io.debezium.time.Date":
        return EPOCH + timedelta(days=value)
    if logical_name == "io.debezium.time.Timestamp":
        # se arma en UTC y se le saca el tzinfo a propósito: transform.py
        # recibe datetimes "naive" desde el batch (pandas también los deja
        # así), y así el Literal que arma rdflib queda igual en los dos casos
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).replace(tzinfo=None)

    # bibtexData es un jsonb de Postgres: Debezium lo manda como un string
    # con el JSON adentro en vez de como objeto. Se detecta igual que en 
    # _jsonify_cell/_dejsonify_cell en extract.py.
    if isinstance(value, str) and value[:1] in "[{":
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    return value


def decode_row(payload_row, envelope_schema, field_name):
    """Traduce un before/after completo (columna por columna) usando el
    schema del struct correspondiente ("before" o "after" del envelope)."""
    if payload_row is None:
        return None

    struct_schema = next(f for f in envelope_schema["fields"] if f["field"] == field_name)
    schema_by_column = {f["field"]: f for f in struct_schema["fields"]}
    return {
        column: _decode_logical_type(value, schema_by_column.get(column, {}))
        for column, value in payload_row.items()
    }


def transform_row(graph, table, row, cso_lookup):
    """Arma los topic_uris/venue_uris que necesita la fila y llama a la
    función de transform.py correspondiente. Devuelve la URI generada."""
    if table == "Member":
        row = clean_member_na_row(row)

    topic_uris = {
        tag: resolve_topic_uri(graph, tag, cso_lookup)
        for tag in (row.get("tags") or [])
    }

    if table == "Publication":
        entry_tags = get_entry_tags(row.get("bibtexData"))
        venue_uri = resolve_venue_uri(graph, entry_tags)
        venue_name = (entry_tags.get("journal") or entry_tags.get("booktitle") or "").strip()
        venue_uris = {slugify(venue_name): venue_uri} if venue_uri else {}
        return transform_publication_row(graph, row, topic_uris, venue_uris)

    return ROW_TRANSFORMS[table](graph, row, topic_uris)


def _entity_triples(graph, entity_uri):
    """Devuelve los triples "propios" de una entidad: los suyos y los de su
    nodo de intervalo de fechas (el único sub-recurso exclusivo que arma
    transform.py). Los temas y venues quedan afuera a
    porque son recursos compartidos entre entidades, no hay que
    borrarlos solo porque esta entidad dejó de referenciarlos."""
    interval_uri = URIRef(f"{entity_uri}/intervalo")
    return (
        list(graph.triples((entity_uri, None, None)))
        + list(graph.triples((interval_uri, None, None)))
    )


def _to_data_block(triples):
    """Serializa triples como N-Triples (URIs completas, sin prefijos), la
    sintaxis que aceptan los bloques INSERT DATA/DELETE DATA de SPARQL."""
    block_graph = Graph()
    for triple in triples:
        block_graph.add(triple)
    return block_graph.serialize(format="nt").strip()


def _binding_to_term(binding):
    """Convierte un binding del JSON de resultados SPARQL (uri o literal) a
    su término real de rdflib."""
    if binding["type"] == "uri":
        return URIRef(binding["value"])
    return Literal(binding["value"], datatype=binding.get("datatype"), lang=binding.get("xml:lang") or None)


def resolve_uri_by_id(entity_id):
    """Busca en GraphDB la URI cuyo dcterms:identifier sea `entity_id`. Hace
    falta para las tablas de join: solo traen el id (UUID) de cada lado, no
    el slug con el que se arma la URI, y acá (a diferencia de la carga
    batch) no hay un uri_lookup aramdo en memoria."""
    query = f'SELECT ?uri WHERE {{ ?uri <http://purl.org/dc/terms/identifier> "{entity_id}" }} LIMIT 1'
    bindings = graphdb_client.run_query(query)
    if not bindings:
        return None
    return URIRef(bindings[0]["uri"]["value"])


def _resolve_join_pair(row):
    """Resuelve las columnas A/B de una fila de tabla de join a sus URIs
    reales en GraphDB. None si no se pudo resolver algún lado (por ejemplo,
    si el evento de la relación llega antes que el de la entidad)."""
    uri_a = resolve_uri_by_id(row["A"])
    uri_b = resolve_uri_by_id(row["B"])
    if uri_a is None or uri_b is None:
        return None
    return uri_a, uri_b


def _add_join_triples(graph, table, uri_a, uri_b):
    """Agrega el triple (o el nodo de vivo:Authorship) correspondiente a una
    fila de tabla de join, con la misma lógica que usa la carga batch."""
    if table == "_PublicationMembers":
        add_authorship(graph, uri_a, uri_b)
    else:
        graph.add((uri_a, JOIN_SPEC[table], uri_b))


def process_join_event(table, msg_value):
    """Aplica un evento Debezium de una tabla de join (alta/baja de relación
    N:M, ej. agregar un integrante a un proyecto) sobre GraphDB."""
    payload = msg_value["payload"]
    op = payload["op"]

    updates = []
    old_pair = None
    old_triples = []

    before = payload["before"]
    if before is not None:
        old_pair = _resolve_join_pair(before)
        if old_pair is not None:
            scratch = Graph()
            _add_join_triples(scratch, table, *old_pair)
            old_triples = list(scratch.triples((None, None, None)))
            if old_triples:
                updates.append(f"DELETE DATA {{\n{_to_data_block(old_triples)}\n}}")

    after = payload["after"]
    if after is None:
        if updates:
            graphdb_client.run_update(" ;\n".join(updates))
        print(f"[{table}] DELETE -> {old_pair} (-{len(old_triples)} triples)")
        return

    new_pair = _resolve_join_pair(after)
    if new_pair is None:
        print(
            f"[{table}] {op}: no se pudo resolver A={after['A']} o B={after['B']} "
            "contra GraphDB (¿todavía no llegó el evento de esa entidad?), se ignora"
        )
        return

    scratch = Graph()
    _add_join_triples(scratch, table, *new_pair)
    new_triples = list(scratch.triples((None, None, None)))
    updates.append(f"INSERT DATA {{\n{_to_data_block(new_triples)}\n}}")

    graphdb_client.run_update(" ;\n".join(updates))
    print(f"[{table}] {op} -> {new_pair} (+{len(new_triples)} triples, -{len(old_triples)} triples)")


def _rename_uri_updates(old_uri, new_uri, triples_ya_manejados):
    """Ante un UPDATE que cambia el slug (y por lo tanto la URI) de una
    entidad, busca en GraphDB si había relaciones cargadas por OTRO evento
    que todavía apunten a la URI vieja, y arma los bloques para migrarlas a
    la URI nueva."""
    ya_manejados = set(triples_ya_manejados)

    salientes = graphdb_client.run_query(f"SELECT ?p ?o WHERE {{ <{old_uri}> ?p ?o }}")
    entrantes = graphdb_client.run_query(f"SELECT ?s ?p WHERE {{ ?s ?p <{old_uri}> }}")

    viejos = Graph()
    nuevos = Graph()
    for binding in salientes:
        p, o = URIRef(binding["p"]["value"]), _binding_to_term(binding["o"])
        if (old_uri, p, o) in ya_manejados:
            continue
        viejos.add((old_uri, p, o))
        nuevos.add((new_uri, p, o))
    for binding in entrantes:
        s, p = URIRef(binding["s"]["value"]), URIRef(binding["p"]["value"])
        viejos.add((s, p, old_uri))
        nuevos.add((s, p, new_uri))

    if len(viejos) == 0:
        return []

    print(f"[rename] {old_uri} -> {new_uri}: migrando {len(viejos)} triples de otras tablas")
    return [
        f"DELETE DATA {{\n{_to_data_block(list(viejos))}\n}}",
        f"INSERT DATA {{\n{_to_data_block(list(nuevos))}\n}}",
    ]


def process_event(table, msg_value, cso_lookup):
    """Aplica un evento Debezium (create/update/delete) sobre GraphDB."""
    envelope_schema = msg_value["schema"]
    payload = msg_value["payload"]
    op = payload["op"]
    resource_type = RESOURCE_TYPE_BY_TABLE[table]

    updates = []
    old_uri = None
    old_triples = []

    # los triples viejos se recalculan corriendo el mismo transform_row sobre 
    # "before" en un grafo descartable. Como la transformación es determinística, 
    # da lo mismo que ya está guardado y ahorramos la consulta a GraphDB
    before = payload["before"]
    if before is not None:
        old_uri = make_uri(resource_type, before["slug"])
        scratch = Graph()
        transform_row(scratch, table, decode_row(before, envelope_schema, "before"), cso_lookup)
        old_triples = _entity_triples(scratch, old_uri)
        if old_triples:
            updates.append(f"DELETE DATA {{\n{_to_data_block(old_triples)}\n}}")

    after = payload["after"]
    if after is None:
        if updates:
            graphdb_client.run_update(" ;\n".join(updates))
        print(f"[{table}] DELETE -> se borró {old_uri} (-{len(old_triples)} triples)")
        return

    row = decode_row(after, envelope_schema, "after")
    scratch = Graph()
    new_uri = transform_row(scratch, table, row, cso_lookup)
    # acá sí van TODOS los triples que generó el evento, no solo los de la
    # entidad: puede haber creado además un tema/venue nuevo que no existía
    new_triples = list(scratch.triples((None, None, None)))
    updates.append(f"INSERT DATA {{\n{_to_data_block(new_triples)}\n}}")

    # si además de los datos propios cambió el slug (osea la URI), hay que
    # migrar las relaciones que ya estuvieran cargadas por otro evento apuntando a la
    # URI vieja, para que no queden relacionadas a un recurso que ya no existe
    if old_uri is not None and old_uri != new_uri:
        updates.extend(_rename_uri_updates(old_uri, new_uri, old_triples))

    graphdb_client.run_update(" ;\n".join(updates))
    print(f"[{table}] {op} -> {new_uri} (+{len(new_triples)} triples, -{len(old_triples)} triples)")


def main():
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    consumer = Consumer({
        "bootstrap.servers": bootstrap_servers,
        "group.id": "lifia-stream-consumer",
        "auto.offset.reset": "earliest",
        # tiempo en el cual se fija si un topico suscripto "inexistente" apareció
        "topic.metadata.refresh.interval.ms": 5000,
    })
    consumer.subscribe(TOPICS)

    print("Cargando el vocabulario de CSO (para resolver temas)...")
    cso_lookup = load_cso_lookup()

    print(f"Escuchando {', '.join(TOPICS)}... (Ctrl+C para cortar)")
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Error de Kafka: {msg.error()}")
                continue
            if msg.value() is None:
                continue

            table = msg.topic().rsplit(".", 1)[-1]
            msg_value = json.loads(msg.value())
            if table in JOIN_TABLES:
                process_join_event(table, msg_value)
            else:
                process_event(table, msg_value, cso_lookup)
    except KeyboardInterrupt:
        print("\nCortando.")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
