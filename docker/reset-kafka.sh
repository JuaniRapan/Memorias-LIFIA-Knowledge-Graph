#!/bin/bash
# Reset para cuando Kafka no arranca por un desacuerdo de
# cluster.id con Zookeeper. Solo tira la data de Kafka/Zookeeper/Connect 
# ejecutar con bash docker/reset-kafka.sh
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker/docker-compose.yml"
ENV_FILE="$REPO_ROOT/.env"

# mismo criterio que register-connector.sh: se carga el .env de la raíz para
# no repetir credenciales hardcodeadas acá
set -a
source "$ENV_FILE"
set +a

echo "Parando y borrando zookeeper, kafka y connect..."
docker compose -f "$COMPOSE_FILE" stop zookeeper kafka connect
docker compose -f "$COMPOSE_FILE" rm -f zookeeper kafka connect

echo "Borrando sus volúmenes (Postgres y GraphDB no se tocan)..."
docker volume rm docker_kafka_data docker_zk_data docker_zk_log 2>/dev/null || true

echo "Levantando el stack de nuevo..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d

# el replication slot vive en Postgres, no en Kafka, así que un reset de
# Kafka no lo toca - pero el connector nuevo va a arrancar sin el registro
# de "hasta dónde ya leí" que antes vivía en el tópico lifia_connect_offsets
# (que sí se borró). Si dejamos el slot viejo, las dos partes quedan en
# desacuerdo y algunos eventos se pierden en el limbo. Lo borramos para que
# el connector, al registrarse de nuevo, arranque uno nuevo y las dos partes
# empiecen de cero de acuerdo entre sí.
echo "Borrando el replication slot viejo (Postgres queda intacto, solo se resetea el punto de partida del CDC)..."
docker exec lifia-postgres psql -U "${DB_USER:-postgres}" -d "${DB_NAME:-lifia_db}" \
    -c "SELECT pg_drop_replication_slot('lifia_slot');" 2>/dev/null || true

echo "Esperando a que Kafka Connect esté listo para recibir la config del connector..."
connect_listo=false
for intento in $(seq 1 30); do
    if curl -s -o /dev/null http://localhost:8083/connectors; then
        connect_listo=true
        break
    fi
    sleep 2
done

if [ "$connect_listo" = false ]; then
    echo "Connect no respondió a tiempo. Esperar un poco y correr a mano:"
    echo "  bash docker/register-connector.sh"
    exit 1
fi

echo "Registrando el connector de Debezium (reusa el lifia_slot/lifia_publication que ya están en Postgres)..."
bash "$REPO_ROOT/docker/register-connector.sh"

echo
echo "Listo. Ejecutar:"
echo "  curl -s http://localhost:8083/connectors/lifia-postgres-connector/status | python3 -m json.tool"
echo "para confirmar estado."