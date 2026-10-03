# Consultas de evaluación (SPARQL vs SQL)

Consultas analíticas que se usan para comparar el Knowledge Graph contra el
modelo relacional de origen. Cada caso tiene un par de archivos con el mismo
nombre y su explicación en [`../docs/evaluacion_sparql_vs_sql.md`](../docs/evaluacion_sparql_vs_sql.md).

## Estructura

```
queries/
├── sparql/   consultas SPARQL (.rq) para el repositorio de GraphDB
└── sql/      consultas SQL equivalentes para la base de origen
```

## Cómo correrlas

- **SPARQL:** GraphDB Workbench (`http://localhost:7200`), repositorio
  `memorias-lifia`, solapa _SPARQL_. Pegar el contenido del `.rq` y ejecutar.
- **SQL:** pgAdmin (o `psql`) conectado a la base `lifia_db`.
  El `docker-compose.yml` expone el puerto 5432 al host, así que cualquier
  cliente gráfico instalado localmente (pgAdmin, DBeaver, TablePlus,
  DataGrip, la extensión de Postgres de VS Code, etc.) se puede conectar
  directo sin tocar la infra. Datos de conexión (default de `.env.example`,
  ver [`../.env.example`](../.env.example)):

  | Campo    | Valor       |
  |----------|-------------|
  | Host     | `localhost` |
  | Puerto   | `5432`      |
  | Base     | `lifia_db`  |
  | Usuario  | `postgres`  |
  | Password | `secret`    |

  Con el stack levantado (`docker compose --env-file ../.env up -d` desde
  `docker/`), crear la conexión con esos datos y correr los `.sql` de
  [`./sql/`](./sql/) desde el query tool de la interfaz.
