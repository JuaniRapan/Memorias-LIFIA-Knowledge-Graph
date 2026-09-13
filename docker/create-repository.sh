#!/bin/bash
# Crea el repositorio de GraphDB (memorias-lifia) con el ruleset OWL2-RL ya
# activado, a partir de docker/memorias-lifia-repository.ttl. Correr una sola
# vez, con GraphDB ya levantado y antes de load_to_graphdb.py: si el
# repositorio no existe, load_to_graphdb.py falla al postear el turtle.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a
source "$REPO_ROOT/.env"
set +a

GRAPHDB_URL="${GRAPHDB_URL:-http://localhost:7200}"
CONFIG_FILE="${REPO_ROOT}/docker/memorias-lifia-repository.ttl"

# para probar con otro repositorio, usar parametro
REPO_ID="${1:-memorias-lifia}"

BOUNDARY="lifia-boundary-$$"
BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT

{
  printf -- '--%s\r\n' "$BOUNDARY"
  printf 'Content-Disposition: form-data; name="config"; filename="memorias-lifia-repository.ttl"\r\n'
  printf 'Content-Type: text/turtle\r\n\r\n'
  # reemplazamos el repositoryID solo si se pidió uno distinto al default
  sed "s/rep:repositoryID \"memorias-lifia\"/rep:repositoryID \"${REPO_ID}\"/" "$CONFIG_FILE"
  printf -- '\r\n--%s--\r\n' "$BOUNDARY"
} > "$BODY_FILE"

# POST a la colección
curl -i -X POST "${GRAPHDB_URL}/rest/repositories" \
  -H "Content-Type: multipart/form-data; boundary=${BOUNDARY}" \
  --data-binary "@${BODY_FILE}"
