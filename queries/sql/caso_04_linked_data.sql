-- Caso 4 - "Linked Data"
--
-- Misma pregunta que caso_04_linked_data.rq: dado el ORCID público de un
-- investigador, encontrar sus publicaciones. 
-- Limitación del modelo relacional:
-- 1. Para la base de datos relacional, 'orcid' es simplemente una 
--    columna VARCHAR sin valor semántico ni garantías de formato. El esquema 
--    no explicita que se trata de un identificador global.
-- 2. Hay que normalizar el formato en la consulta misma.
-- 3. Falta de interoperabilidad: Integrar otras fuentes académicas exige definir nuevas 
-- columnas y  nuevas reglas por tabla.
-- 4. La autoría de una publicación sale de dos lugares: _PublicationMembers y
--    el texto de Publication.authors. Para ver lo mismo que el grafo hay que
--    resolver el segundo por nombre dentro de la consulta (CTE autorias).

WITH autores_fragmentos AS (
    -- un fragmento por autor de Publication.authors, normalizado (tildes,
    -- puntos, comas) como normalize_name() en transform.py
    SELECT p.id AS publication_id,
           f.ord AS fragmento,
           string_to_array(
               trim(regexp_replace(
                   translate(lower(f.texto), 'áéíóúüñ', 'aeiouun'),
                   '[.,\s]+', ' ', 'g'
               )),
               ' '
           ) AS palabras
    FROM "Publication" p
    CROSS JOIN LATERAL regexp_split_to_table(
        p.authors, '\s+(?:and|e|y|&)\s+|;'
    ) WITH ORDINALITY AS f(texto, ord)
    WHERE p.authors IS NOT NULL
      AND lower(trim(p.authors)) NOT IN ('raw reference', 'unknown')
),
miembros_palabras AS (
    SELECT m.id AS member_id,
           string_to_array(
               trim(regexp_replace(
                   translate(lower(m."firstName" || ' ' || m."lastName"), 'áéíóúüñ', 'aeiouun'),
                   '[.,\s]+', ' ', 'g'
               )),
               ' '
           ) AS palabras
    FROM "Member" m
),
autoria_por_texto AS (
    -- el fragmento matchea si están todas las palabras del nombre del Member;
    -- si matchea con más de uno no adivinamos (igual que resolve_person)
    SELECT af.publication_id, mp.member_id,
           COUNT(*) OVER (PARTITION BY af.publication_id, af.fragmento) AS candidatos
    FROM autores_fragmentos af
    JOIN miembros_palabras mp ON mp.palabras <@ af.palabras
),
autorias AS (
    SELECT "A", "B" FROM "_PublicationMembers"
    UNION
    SELECT member_id, publication_id FROM autoria_por_texto WHERE candidatos = 1
)
SELECT DISTINCT p.title
FROM "Member" m
JOIN autorias pm ON pm."A" = m.id
JOIN "Publication" p ON p.id = pm."B"
WHERE regexp_replace(m.orcid, '^https?://orcid\.org/', '', 'i') = '0000-0001-7533-0133'
ORDER BY p.title;
