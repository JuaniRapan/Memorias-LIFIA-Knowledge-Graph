# Documentación de los tests

Hay cuatro archivos de test en `tests/`. Todos usan `unittest` y se corren con:

```bash
python -m unittest discover -s tests -v
```

| Archivo                   | Qué cubre                                                                   | Necesita infraestructura                                                       |
| ------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `test_lifia_graph.py`     | Cómo se reconocen nombres de personas y cómo queda armado el grafo          | Solo el segundo grupo necesita haber generado `data/processed/lifia_graph.ttl` |
| `test_stream_consumer.py` | Cómo se leen los eventos de Debezium y qué SPARQL Update se manda a GraphDB | No                                                                             |
| `test_load_to_graphdb.py` | Que la carga inicial mande los archivos correctos a GraphDB                 | No (se necesita el `.ttl` generado)                                            |
| `test_e2e_streaming.py`   | Que un cambio en Postgres llegue de verdad a GraphDB                        | Sí, todo el stack                                                              |

---

## 1. `test_lifia_graph.py`

Prueba `src/etl/transform.py`, que es la parte que convierte filas de la base en triples RDF.
Tiene dos partes: la primera usa datos inventados y siempre corre; la segunda revisa el grafo
ya generado y se salta sola si el archivo `lifia_graph.ttl` no existe.

### Reconocer personas escritas como texto libre (`TestNameResolution`)

Campos como `director`, `coDirector` o `student` vienen como texto escrito a mano. Estos tests
usan cinco `Member` inventados (incluidos dos Urbieta, a propósito) y comprueban que
`resolve_person` encuentre a la persona correcta.

- `test_nombre_exacto`: "Alejandra Lliteras" encuentra a Alejandra Lliteras.
- `test_orden_invertido_apellido_nombre`: "Lliteras Alejandra" también.
- `test_nombre_del_medio_que_el_member_no_tiene`: "Alejandra Beatriz Lliteras" encuentra a
  Alejandra aunque "Beatriz" no esté en la base.
- `test_titulo_academico_y_punto_final`: "Dr. Andrés Rodríguez." ignora el "Dr." y el punto.
- `test_texto_pegado_tipo_afiliacion`: "Andrés Rodríguez (UNLP)" ignora lo que está entre paréntesis.
- `test_apellido_solo_si_es_unico`: "Challiol" alcanza, porque hay una sola Challiol.

### No adivinar si no está claro

- `test_nombre_o_apellido_ambiguo_no_adivina`: "Urbieta" devuelve `None` porque hay dos.
- `test_persona_que_no_existe_no_matchea_cualquier_cosa`: un nombre que no está devuelve `None`.
- `test_resolve_exact_no_usa_subconjunto`: `resolve_exact` es más estricto que `resolve_person`.
  Con "Andrés Rodríguez (UNLP)" devuelve `None`.
- `test_coma_como_apellido_nombre_de_una_sola_persona`: "Rodríguez, Andrés" se reconoce como una
  sola persona escrita "Apellido, Nombre".

### Separar varios nombres en un mismo campo (`TestSplitNames`)

Prueba `split_names`, que parte un texto en una lista de personas.

- `test_separa_por_coma`: "A, B" da dos nombres.
- `test_separa_por_y_and`: separa con "y" y con "and".
- `test_separa_por_guion_y_barra`: separa con " - " y con " / ".
- `test_saca_etiqueta_con_dos_puntos`: "Asesor técnico: Alejandra Lliteras" queda solo con el nombre.

### Separar palabras clave (`TestSplitKeywords`)

Prueba `split_keywords`. `Thesis.keywords` es un único texto con varias keywords adentro.

- `test_separa_por_coma`: "machine learning, inteligencia artificial" da dos keywords.
- `test_separa_por_punto_y_coma_cuando_las_keywords_ya_tienen_coma_adentro`: si hay `;`, se usa
  ese separador.
- `test_una_sola_keyword_sin_separador`: una keyword sola queda como una lista de un elemento,
  sin espacios sobrantes.

### Distinguir un nombre de otro texto (`TestLooksLikeAName`)

Prueba `looks_like_a_name`.

- `test_nombre_largo_valido`: "Federico Ricardo Mozzon Corporaal" es un nombre.
- `test_nombre_compuesto_con_particulas`: "Maria de la Paz Diulio" es un nombre; "de la" no cuenta como palabra de contenido.
- `test_titulo_de_tesis_no_es_nombre`: "Requerimientos de calidad en lenguaje natural" no es un nombre.

### Autoría y rol de investigador principal (`TestAuthorshipYPiRole`)

Verifican el patrón de nodo intermedio que se usa porque `vivo:authorOf` y
`vivo:hasPrincipalInvestigatorRole` no existen en VIVO.

- `test_add_authorship_arma_el_nodo_con_las_cuatro_aristas`: `add_authorship` crea un nodo
  `vivo:Authorship` con su URI, conectado a la persona y a la publicación con `vivo:relatedBy` y `vivo:relates`.
- `test_transform_authorships_ignora_ids_sin_uri`: si los ids no tienen URI conocida, no se agrega nada al grafo.
- `test_add_pi_role_arma_el_nodo_con_relatedby_y_contributingrole`: `add_pi_role` crea un
  `vivo:PrincipalInvestigatorRole` conectado a la persona y al proyecto, con las propiedades de ida y de vuelta.

### Revisar el grafo ya generado (`TestGeneratedGraph`)

Lee `data/processed/lifia_graph.ttl` y lo compara con los CSV de `data/interim/`. Si faltan
esos archivos, todo el grupo se salta con un mensaje.

**Que el archivo esté completo y bien formado**

- `test_ttl_parsea_sin_errores`: el archivo se puede leer y tiene triples.
- `test_cantidad_de_nodos_coincide_con_las_filas_de_la_base`: para `Member`, `Project`,
  `Scholarship`, `Thesis` y `Publication`, la cantidad de nodos del grafo es igual a la cantidad de filas del CSV.
  Si dos filas generaran la misma URI, el conteo no coincidiría.
- `test_sin_mojibake_en_los_literales`: no hay textos con caracteres rotos como "Ã" o "�".

**Que las referencias apunten a algo**

- `test_bibo_presentedAt_no_apunta_a_nada_huerfano`: todo lugar al que apunta `bibo:presentedAt` existe como nodo.
- `test_mayoria_de_publications_tiene_subclase_dblp_especifica`: al menos el 90% de las
  publicaciones tiene una clase DBLP (`Article`, `Inproceedings`, `Incollection` o `Book`).

**Personas externas**

- `test_personas_externas_no_tienen_dos_nombres_distintos_en_la_misma_uri`: ninguna URI de
  `persona-externa` tiene más de un `foaf:name`.
- `test_personas_externas_no_son_faculty_member`: ninguna persona externa está marcada como `vivo:FacultyMember`.

**Errores que ya ocurrieron y no deben volver**

- `test_progress_de_thesis_no_esta_en_rdfs_comment`: el avance de la tesis no va como número dentro de `rdfs:comment`.
- `test_completion_percentage_es_entero_entre_0_y_100`: `lifia-ontology:completionPercentage` existe y es un entero entre 0 y 100.
- `test_keywords_de_thesis_se_separan_individualmente`: hay tesis conectadas al tema real de `machine_learning` de CSO.
- `test_no_quedan_terminos_vivo_inventados`: no se usa ninguno de los seis términos que no existen en VIVO (`authorOf`,
  `hasPrincipalInvestigatorRole`, `ResearchProject`, `Thesis`, `highestDegree`, `webpage`).

---

## 2. `test_stream_consumer.py`

Prueba `src/streaming/stream_consumer.py`, que recibe los eventos de Debezium y los convierte
en SPARQL Update. No necesita Kafka, Postgres ni GraphDB: `graphdb_client.run_update` se reemplaza
por una función que solo guarda el texto, y para validar el SPARQL se usa `prepareUpdate` de `rdflib`.

### Leer los valores del evento (`TestDecodeRow`)

Debezium manda fechas y timestamps como números y los campos jsonb como texto. `decode_row` los convierte.

- `test_decodifica_fecha_debezium_a_date`: un número de días se vuelve una fecha.
- `test_decodifica_timestamp_debezium_naive_en_utc`: un timestamp en milisegundos se vuelve un datetime sin zona horaria.
- `test_decodifica_jsonb_serializado_como_string`: el texto de `bibtexData` se vuelve un diccionario.
- `test_campo_sin_tipo_logico_pasa_tal_cual`: un campo común no se modifica.
- `test_before_none_devuelve_none`: si no hay fila (por ejemplo en un INSERT no hay `before`), devuelve `None`.

### Limpiar valores "N/A" (`TestCleanMemberNaRow`)

- `test_reemplaza_na_por_none`: `clean_member_na_row` cambia "N/A" por `None` y deja el resto igual.

### El SPARQL que se arma por cada tipo de evento (`TestProcessEvent`)

- `test_insert_no_genera_delete_data`: un evento `c` genera solo `INSERT DATA`.
- `test_delete_no_genera_insert_data`: un evento `d` genera solo `DELETE DATA`.
- `test_update_genera_delete_e_insert_sintacticamente_validos`: un evento `u` genera ambos y contiene el valor nuevo.
- `test_n_a_de_member_se_limpia_antes_de_mandar_a_graphdb`: un "N/A" no llega a GraphDB.
- `test_intervalo_usa_uri_estable_no_blank_node`: el nodo de intervalo tiene URI propia
  (`/persona/ana-lopez/intervalo>`) y no aparece ningún `_:`.
- `test_delete_no_borra_temas_compartidos`: el `DELETE` no toca los triples propios de un tema (`tema/nlp`),
  porque otras entidades pueden usarlo.

### Caso especial: publicaciones (`TestProcessEventPublication`)

- `test_bibtex_string_se_parsea_y_arma_el_venue`: con un `bibtexData` en texto, se crea el venue
  `/venue/journal-of-testing>`, aparece el título nuevo y el SPARQL es válido.

### Directores y codirectores en texto libre (`TestTextRelations`)

Mockea `run_update` y usa un índice de nombres con una sola persona (Ana Lopez).

- `test_director_que_es_member_arma_el_rol_pi`: si el director es un `Member`, se crea el rol `/rol-pi/` con su URI y no se crea persona externa.
- `test_director_desconocido_se_crea_como_persona_externa`: si no se encuentra, se crea `/persona-externa/juan-prueba>` y su rol.
- `test_update_borra_el_rol_viejo_pero_no_la_persona`: al cambiar de director se borra el rol anterior pero no el nombre de la persona externa.
- `test_sin_name_index_no_se_resuelve_texto_libre`: si no se pasa el índice, no se genera ningún `/rol-pi/`.

### Cargar el índice de nombres desde Postgres (`TestLoadNameIndex`)

Mockea la conexión y la consulta.

- `test_arma_el_indice_con_la_uri_del_slug`: con un `Member` de ejemplo, `Ana Lopez` se resuelve a `/persona/ana-lopez`, y la conexión se cierra una vez.
- `test_sin_conexion_tira_error`: si no hay conexión, `load_name_index` lanza `RuntimeError`.

---

## 3. `test_load_to_graphdb.py`

Prueba `src/etl/load_to_graphdb.py`. Se reemplaza `urllib.request.urlopen` por una respuesta falsa,
así que no necesita GraphDB.

### Qué se manda y en qué orden (`LoadTest`)

- `test_postea_el_tbox_de_vivo_el_grafo_y_la_jerarquia_de_cso`: `load()` hace tres POST a
  `/repositories/<repositorio>/statements`, en este orden: la ontología VIVO, el grafo (`lifia_graph.ttl`) y la jerarquía de CSO.
  Cada cuerpo coincide con el contenido del archivo. Si falta el `.ttl`, el test se salta.

### Cómo se manda (`Content-Type`)

- `test_manda_content_type_turtle`: `_post_turtle` usa `text/turtle; charset=utf-8`.
- `test_manda_content_type_rdf_xml_para_el_tbox_de_vivo`: la ontología VIVO se manda como `application/rdf+xml; charset=utf-8`.

---

## 4. `test_e2e_streaming.py`

Es el único test que usa todo el sistema real: Postgres, Kafka, Debezium, el consumer y GraphDB.

### Requisitos previos

Antes de correr, `setUpClass` revisa y salta el test con un mensaje si falta algo:

- que se pueda conectar a Postgres;
- que GraphDB responda;
- que el connector `lifia-postgres-connector` esté `RUNNING`.

El test no arranca `stream_consumer.py`: tiene que estar corriendo en otra terminal.

### Recorrido completo de un `Member` (`test_insert_update_delete_se_reflejan_en_graphdb`)

1. **INSERT:** crea un `Member` con un slug único (`test-e2e-cdc-<8 caracteres>`) y espera hasta que
   GraphDB tenga `foaf:firstName` igual a `"Test"`.
2. **UPDATE:** cambia el nombre a `"Test Actualizado"` y espera a que GraphDB lo refleje.
3. **DELETE:** borra la fila y espera a que GraphDB no tenga ningún `foaf:firstName` para esa URI.
4. **Limpieza:** el bloque `finally` borra la fila de prueba aunque algo haya fallado.

### Cómo espera (`_wait_until`)

Repite la consulta cada 2 segundos (`POLL_INTERVAL_SECONDS`) hasta un máximo de 60 (`POLL_TIMEOUT_SECONDS`).
Si se cumple el tiempo sin resultado, el test falla con un mensaje que indica qué paso no llegó.
