# SPARQL vs SQL

En esta parte se muestra con **consultas concretas** (puede encontrarlas en /queries) los casos donde es mas simple o mejor el knowledge graph que la bd relacional. Esto no quiere decir que siempre sea mejor, simplemente es una forma de mostrar las fortalezas de esta decision, en que puntos concretos es conveniente usarlo, ya sea por simplicidad en la consulta o por performance.

---

## Caso 1 - Jerarquía (CSO)

**La consulta:** Traer todas las publicaciones sobre Inteligencia Artificial
Deberíamos traer no solo las publicaciones que tengan la etiqueta "Inteligencia Artificial", sino también las que están por debajo en la jerarquía (machine learning, deep learning, NLP, etc). Queremos consultar un area, no el tag exacto.
En el grafo, cada tag está matcheado con el vocabulario de CSO, y con su jerarquía correspondiente. Por eso se sumó un subconjunto del vocabulario de CSO para poder aprovechar de estas relaciones (se carga en el grafo en el mismo `load_to_graphdb.py`.

### Queries

`quieries/sparql/caso_01_jerarquia_cso.rq` y `queries/sql/caso_01_jerarquia_cso.sql`

|                                 | SPARQL                                  | SQL                                                  |
| ------------------------------- | --------------------------------------- | ---------------------------------------------------- |
| **De dónde sale la jerarquía**  | De CSO cargado como datos               | No existe (hay que inventarla)                       |
| **Recursión / profundidad**     | Implícita (superTopicOf\*)              | Explícita (WITH RECURSIVE) y sólo si existe la tabla |
| **Cambiar de área a consultar** | Una línea (BIND)                        | Reescribir toda la lista de términos                 |
| **Se carga un nuevo tema**      | Entra solo si CSO lo tiene como subtema | Queda afuera hasta editar la consulta                |
| **Legibilidad**                 | 6 líneas                                | unnest + LATERAL + lista embebida                    |

En este caso se muestra tanto la reutilización de vocabularios publicados (Linked Data), y que en un grafo el esquema y los datos son lo mismo (la jerarquía solo significa mas tripletas). En el modelo relacional, esto mismo exige diseñar una estructura nueva, o reflejar esta logica en las queries (poco mantenible).

---

## Caso 2 - N saltos

**La consulta**: Dado un investigador del LIFIA, ¿quiénes son sus colegas de colegas con los que todavía NO publicó directamente?
Podría servir para recomendaciones de posibles colaboraciones dentro del centro.
La fuente de "quién escribió qué" en ambos modelos es la relación autor-publicación. En Postgres es la tabla de join \_PublicationMembers, en el grafo este dato quedó como vivo:authorOf entre el nodo de la persona y el nodo de la investigación.

### Queries

`queries/sparql/caso_02_n_saltos.rq` y `quereis/sql/caso_02_n_saltos.sql`

|                          | SPARQL                                                                    | SQL                                                      |
| ------------------------ | ------------------------------------------------------------------------- | -------------------------------------------------------- |
| **1 salto de coautoría** | Un patrón de 2 pasos                                                      | 2 self-joins                                             |
| **2 saltos**             | Se encadena el mismo patrón una vez más                                   | 4 self-joins + una CTE extra para excluir a los directos |
| **N saltos**             | Se ajusta la cantidad de segmentos del path                               | WITH RECURSIVE con ajuste manual de ciclos               |
| **Legibilidad**          | El camino se lee como se recorre: persona → pub → coautor → pub → coautor | Cadena de joins con alias (pm1..pm4)                     |

Este caso muestra la fortaleza del grafo en las consultas de alcance N (relaciones a mas de un salto de distancia), la estructura de datos es la misma que la pregunta. En la parte relacional, cada salto extra es un JOIN mas que se agrega a mano.

---

## Caso 3 - Integración de relaciones explícitas y menciones textuales resueltas

**La consulta**: traer toda la producción de una persona del LIFIA (publicaciones y tesis), sin que importe si esa relación viene de una tabla de join de verdad o de un campo de texto libre (director/coDirector/student) resuelto contra Member por nombre.
En la base de datos relacional, "quién trabajó en una tesis"está modelado de dos formas distintas al mismo tiempo: la tabla join \_ThesisMembers (la fk entre Member y Thesis) y las columnas en Thesis: director, coDirector,student, otherAdvisors (no fk). El segundo caso se maneja en `transform.py`.

### Queries

`queries/sparql/caso_03_relaciones.rq` y `queries/sql/caso_03_relaciones.rq`

|                                                    | SPARQL                                                                | SQL                                                                 |
| -------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Fuentes heterogéneas**                           | Ya unificadas en triples; se combinan con UNION de patrones simples   | UNION ALL de SELECTs con columnas y joins distintos por cada fuente |
| **Texto libre → persona**                          | Resuelto una vez en el ETL, queda como arista normal                  | Hay que resolverlo en cada query con ILIKE                          |
| **Agregar una entidad más (Project, Scholarship)** | Una rama de UNION más, mismo patrón                                   | Repetir el mismo problema (FK + texto libre) para cada tabla nueva  |
| **Confiabilidad del match**                        | La de resolve_person() (exacto, subconjunto o fuzzy match con umbral) | La de un ILIKE de substring, sin normalización                      |

En este caso se muestra la integración de datos y mejora del modelo que se hace con el ETL. Mas allá de las ventajas del grafo, tambien se mejoraron cuestiones de la base de datos relacional como este tipo de información que no está resuelta.

---

## Caso 4 - Linked Data

**La consulta**: dado el ORCID público de un investigador, encontrar suspublicaciones en el grafo del LIFIA sin saber de antemano cuál es su URI interna.
Este caso no es sobre performance, se muestra la capacidad de relacionar el grafo con los datos exteriores.
En la base relacional, Member.orcid y Member.dblpProfile son columnas de texto (no es algo que defina identidad, ni que relacione con sistemas externos). En el grafo, el ETL genera ambos campos como owl:sameAs (declara que las dos IRIs identifican a la misma identidad del mundo real) desde el IRI de la persona hasta el IRI externo (orcid en este caso).

### Queries

`queries/sparql/caso_04_linked_data.rq` y `queries/sql/caso_04_linked_data.sql`

|                               | SPARQL                                            | SQL                                                |
| ----------------------------- | ------------------------------------------------- | -------------------------------------------------- |
| **Qué es el dato**?           | Una afirmación de identidad estándar (owl:sameAs) | Un string en una columna de texto, sin tipo        |
| **Formato garantizado**       | Sí: IRI limpia, normalizada una vez en el ETL     | No: URL completa o solo el id, según cómo se cargó |
| **Reusable por otro sistema** | Sí, es vocabulario público (OWL)                  | No, es una convención interna del proyecto         |

En este caso, no suma valor que la consulta sea mas corta o mas eficiente, se busca mostrar un ejemplo que represente la idea de **Linked Data**. El grafo puede usar como punto de entrada un identificador que no controlamos nosotros, y tratarlo con el mismo vocabulario estándar que el resto de la Web de Datos.
