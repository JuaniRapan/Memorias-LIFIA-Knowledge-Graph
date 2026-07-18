# Estrategia de URIs (Identificadores del Grafo)

Antes de generar los triples hace falta definir cómo se va a identificar cada recurso dentro del grafo. Acá se define la URI base y el patrón que se usa para armar las IRIs de cada entidad del dump (`data/raw/new_memorias_para_kgsw.dump`), siguiendo lo ya definido en [mapeos_ontologicos.md](mapeos_ontologicos.md).

## 1. URI base

```
http://lifia.info.unlp.edu.ar/resource/
```

Esta URI se usa únicamente para las instancias de datos (una persona puntual, una publicación puntual, etc). Las clases y propiedades de las ontologías (`vivo:FacultyMember`, `bibo:doi`, `cso:Topic`) no se tocan ni se redefinen, ahí se siguen usando los namespaces originales de VIVO, BIBO, FOAF, DBLP, DC y CSO.

Prefijo a usar en Turtle/SPARQL:

```turtle
@prefix lifia: <http://lifia.info.unlp.edu.ar/resource/> .
```

## 2. Patrón general

```
{URI_BASE}/{tipo_de_recurso}/{identificador_local}
```

`{tipo_de_recurso}` es un sustantivo fijo, en español y en minúscula (`persona`, `publicacion`, `proyecto`, `beca`, `tesis`, `tema`, `venue`). Cumple la función de evitar que dos entidades distintas terminen compartiendo el mismo identificador local por casualidad. El `{identificador_local}` cambia según la entidad y se explica en el punto siguiente.

## 3. Campo identificador

En las 5 tablas principales del dump (`Member`, `Publication`, `Project`, `Scholarship`, `Thesis`) hay dos campos candidatos a identificador:

| Campo             | Ejemplo real del dump                  | Comentario                                                         |
| ----------------- | -------------------------------------- | ------------------------------------------------------------------ |
| `id` (PK, UUID)   | `9d0a5af7-b064-4962-ac33-d332d22549cf` | único y estable, pero es un UUID de Prisma, no dice nada           |
| `slug` (`UNIQUE`) | `matias-urbieta`                       | único, legible, y ya se usa en las URLs del sitio actual del LIFIA |

Se optó por usar el `slug`. Una URI como `.../resource/persona/matias-urbieta` resulta mucho más práctica a la hora de debuggear o de escribir consultas SPARQL a mano que una con un UUID en el medio, y de paso queda consistente con las URLs que ya tiene el sitio del laboratorio.

El costo de esta decisión es que el `slug` se puede editar desde el CMS de origen, entonces si en algún momento lo cambian, la URI de ese recurso cambia también en la próxima corrida del ETL. Para no perder la trazabilidad en ese caso, se guarda el `id` (UUID) original como `dcterms:identifier` sobre el mismo recurso, de forma que quede una manera de reconciliar el dato aunque el slug haya cambiado. Se descartó meter directamente el UUID en la URI porque es un caso borde poco frecuente y no justifica perder legibilidad.

## 4. Patrón de URI por entidad

| Entidad Relacional                                                              | Identificador SQL                | Patrón de URI                                                                                                                                                        |
| ------------------------------------------------------------------------------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Investigador / Miembro (`Member`)                                               | `slug`                           | `.../resource/persona/{slug}`                                                                                                                                        |
| Publicación (`Publication`)                                                     | `slug`                           | `.../resource/publicacion/{slug}`                                                                                                                                    |
| Proyecto (`Project`)                                                            | `slug`                           | `.../resource/proyecto/{slug}`                                                                                                                                       |
| Beca / Subsidio individual (`Scholarship`)                                      | `slug`                           | `.../resource/beca/{slug}`                                                                                                                                           |
| Tesis (`Thesis`)                                                                | `slug`                           | `.../resource/tesis/{slug}`                                                                                                                                          |
| Tema / Línea I+D (`tags`/`keywords`, sin tabla propia)                          | no tiene, se normaliza el string | `.../resource/tema/{tag-normalizado}`, y se usa solo si el tag no matchea con nada en CSO. Si matchea, se reusa directamente la IRI de CSO (`cso:relatedEquivalent`) |
| Venue / Congreso / Revista (sale de `Publication.bibtexData`, sin tabla propia) | no tiene, se normaliza el nombre | `.../resource/venue/{nombre-normalizado}`                                                                                                                            |

## 5. Normalización de lo que no tiene slug propio (tema, venue)

Los tags, los keywords y los venues que se sacan del `bibtexData` no vienen con un slug ya calculado, así que hay que armarlo a mano durante el ETL, tomando el nombre o el tag tal como está en la base y transformándolo en un texto apto para ir en una URL.

Reglas que sigue esta normalización:

1. Todo en minúscula.
2. Sin tildes ni diacríticos (la base ya tiene instalada la extensión `unaccent`, que hace algo parecido, sirve como referencia de comportamiento).
3. Los espacios y símbolos raros se reemplazan por un guion, sin guiones repetidos ni al principio o al final.
4. Tiene que ser determinística: el mismo texto de entrada siempre da el mismo slug. Esto es clave porque si un tema aparece mencionado en varias publicaciones, tiene que colapsar siempre a la misma URI y no generar nodos duplicados en el grafo.

Por ejemplo, un tag como "Web Engineering" quedaría normalizado como "web-engineering", y un venue como "ICWE 2019" quedaría como "icwe-2019".
