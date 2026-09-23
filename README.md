# Memorias-LIFIA-Knowledge-Graph

Trabajo final de la matera Web Semántica y Grafos de Conocimiento.
La página de Memorias@LIFIA tiene su información guardada en una base de datos **relacional**, la cual cumple el fin de la página que es listar y modificar los registros. Este trabajo hace una migración de esta base de datos a un **Grafo de Conocimiento**, mediante el cual podemos sacar provecho de las características del mismo, como consultas semánticas, conectividad con la Linked Open Data, modelado de entidades de la vida real, entre otras.

En este proyecto se migran los datos existentes en la base relacional, y se reutilizan ontologías ya publicadas con significados específicos de las temáticas relacionadas (VIVO para dominio académico, CSO para temas de ciencia de la computación, DBLP para publicaciones, etc). Esto es la idea central de **Linked Data**: los datos del LIFIA se pueden combinar con el resto de la web semántica usando el mismo lenguaje que ya se usa en otros sisemas.

No solo se hace una migración inicial, sino que se mantiene la sincronización en tiempo real (cuando se hacen las modificaciones en la base de datos relacional). Se usa **Change Data Capture** con Debezium y Kafka para publicar las modificaciones a GraphDB, donde reside nuestro grafo de conocimiento.

---

## Arquitectura General

Dos caminos de ingesta que comparten la misma lógica de transformación:

```
 CARGA HISTÓRICA
PostgreSQL ──extract.py──> CSV en data/interim/ ──transform.py──> lifia_graph.ttl ──load_to_graphdb.py──> GraphDB

 STREAMING
PostgreSQL ──(WAL)──> Debezium ──> Kafka (tópicos lifia.public.*) ──stream_consumer.py──> GraphDB
```

La lógica de transformación (transform\_\*\_row) se reutiliza tanto en la carga batch como en el streaming. Cada fila pasa se procesa igual; lo que cambia es el origen de la misma (dataframe de pandas, o payload de Debezium) y que se hace con la tripleta resultante (escribir .ttl o mandar un INSERT/DELETE a GraphDB).

---

## Como funciona el pipeline

### Carga batch (ETL)

1. **`extract.py`**: lee las tablas de Postgres con pandas y las vuelca como CSV en `data/interim/` (staging, para no pegarle a la base en cada iteración del mapeo).
2. **`transform.py`**: arma un grafo RDF en memoria. Resuelve primero los temas (contra el vocabulario CSO) y los venues (del BibTeX de cada); después convierte las 5 entidades principales; después las relaciones de las tablas de join; y por último resuelve contra Member los campos de texto libre (director, student, etc.) por nombre. Serializa todo a `data/processed/lifia_graph.ttl`.
3. **`load_to_graphdb.py`**: postea ese .ttl (mas la ontología VIVO y la jerarquía CSO) a GraphDB, una sola vez, antes de arrancar el streaming.

El detalle campo por campo de este mapeo está en mapeos_ontologicos.md.

### Streaming (CDC)

Debezium lee el WAL de Postgres y publica cada INSERT/UPDATE/DELETE como un mensaje en un tópico de Kafka (uno por tabla). `stream_consumer.py` escucha esos tópicos y, por cada evento, llama a la misma función de `transform.py` que usa el batch. Se deja corriendo en una terminal aparte; mientras esté activo, cualquier cambio en Postgres se refleja en GraphDB.

---

## Pasos para ejecución

Lista de comandos que se deben ejecutar para poner en funcionamiento el proyecto (todos desde la raíz del proyecto):

### Setup inicial (o cada vez que se borran los volúmenes de Docker)

```
# 1) Entorno Python
pip install -r requirements.txt

# 2) Crear .env en la raíz con con:
#      DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
#    y opcionalmente KAFKA_BOOTSTRAP_SERVERS / GRAPHDB_URL / GRAPHDB_REPOSITORY

# 3) Levantar la infraestructura (Postgres restaura el dump solo, la
#    primera vez que se crea su volumen; Kafka, Zookeeper, Connect y
#    GraphDB arrancan vacíos)
docker compose --env-file .env -f docker/docker-compose.yml up -d

# 4) Crear el repositorio de GraphDB, con el ruleset OWL2-RL ya activado
bash docker/create-repository.sh

# 5) Registrar el connector de Debezium contra Kafka Connect
bash docker/register-connector.sh
# verificar que quedó RUNNING antes de seguir:
curl -s http://localhost:8083/connectors/lifia-postgres-connector/status | python3 -m json.tool

# 6) Carga histórica (batch): Postgres -> CSV -> RDF -> GraphDB
python src/etl/extract.py
python src/etl/transform.py
python src/etl/load_to_graphdb.py
```

### Uso normal (levantar y arrancar stream consumer)

```
# 1) Levantar la infraestructura si no está corriendo
docker compose --env-file .env -f docker/docker-compose.yml up -d

# 2) Arrancar el sincronizador en tiempo real (queda corriendo, escuchando Kafka)
python src/streaming/stream_consumer.py
```

Mientras el consumer esté corriendo, los cambios que se hagan en Postgres se ven reflejados en GraphDB. GraphDB Workbench (para correr SPARQL a mano, revisar el repositorio,  
etc.): `http://localhost:7200`

### Otros comandos

```
# Correr los tests
python -m unittest tests.test_lifia_graph -v
python -m unittest tests.test_stream_consumer -v
python -m unittest tests.test_load_to_graphdb -v
python -m unittest tests.test_e2e_streaming -v      # necesita el stack completo + el consumer corriendo
python -m unittest discover -s tests -v             # los cuatro juntos

# Apagar (mantiene los volúmenes)
docker compose -f docker/docker-compose.yml down

# Apagar y borrar también los volúmenes (vuelve todo al estado inicial:
# el próximo "up" restaura el dump de nuevo y hay que repetir el setup inicial entero)
docker compose -f docker/docker-compose.yml down -v
```
