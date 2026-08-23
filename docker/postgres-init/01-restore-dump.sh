#!/bin/bash
# Se ejecuta solo, una vez, la primera vez que se crea el volumen de datos
# de Postgres (docker-entrypoint-initdb.d corre estos scripts únicamente
# contra una base recién inicializada, vacía). Restaura el dump binario
# (formato PGDMP) que dejó pg_dump sobre new_memorias.
set -e

echo "Restaurando new_memorias_para_kgsw.dump en la base $POSTGRES_DB..."
pg_restore --no-owner --no-privileges \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  /docker-entrypoint-initdb.d/new_memorias_para_kgsw.dump
echo "Dump restaurado."
