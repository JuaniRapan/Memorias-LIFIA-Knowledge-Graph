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
- **SQL:** pgAdmin (o `psql`) conectado a la base `new_memorias`.
