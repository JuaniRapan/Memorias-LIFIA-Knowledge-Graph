#!/bin/bash
# Registra (POST) el connector de Debezium contra la API REST de Kafka
# Connect. Lee las credenciales del .env de la raíz.
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a
source "$REPO_ROOT/.env"
set +a

curl -i -X POST -H "Accept:application/json" -H "Content-Type:application/json" \
  http://localhost:8083/connectors/ -d @- <<EOF
{
  "name": "lifia-postgres-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "${DB_USER}",
    "database.password": "${DB_PASSWORD}",
    "database.dbname": "${DB_NAME}",
    "topic.prefix": "lifia",
    "plugin.name": "pgoutput",
    "slot.name": "lifia_slot",
    "publication.name": "lifia_publication",
    "publication.autocreate.mode": "filtered",
    "snapshot.mode": "no_data",
    "tombstones.on.delete": "false",
    "table.include.list": "public.Member,public.Project,public.Publication,public.Scholarship,public.Thesis,public._ProjectMembers,public._ProjectPublications,public._ProjectScholarships,public._ProjectTheses,public._PublicationMembers,public._ScholarshipMembers,public._ThesisMembers,public._ThesisPublications,public._ThesisScholarships"
  }
}
EOF
