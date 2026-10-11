-- Caso 3 - Integración de relaciones explícitas y menciones textuales
--
-- Misma pregunta que caso_03_relaciones.rq: toda la producción
-- de una persona (publicaciones + tesis). El problema es que "quién trabajó
-- en una tesis" está modelado de DOS formas distintas en el mismo dump:
--   1) _ThesisMembers(A, B): una tabla de join de verdad (FK).
--   2) Thesis.director / coDirector / student / otherAdvisors: columnas de
--      texto libre, sin FK a Member.id.
--
-- La (1) se resuelve con un JOIN normal. La (2) no tiene mejor una forma robusta de resolverlo, 
-- lo implemento con un ILIKE

-- Un mismo trabajo puede estar en las dos fuentes a la vez (FK y texto libre),
-- por eso cada rama devuelve (id, titulo, tipo, fuente) y al final se agrupa:
-- queda una fila por trabajo y las fuentes se juntan en una sola columna.

WITH persona AS (
    SELECT id, "firstName", "lastName"
    FROM "Member"
    WHERE slug = 'diego-torres'
),
autores_fragmentos AS (
    -- Las publicaciones también tienen autoría en el texto de Publication.authors,
    -- no solo en _PublicationMembers. Lo partimos en un fragmento por autor y
    -- lo normalizamos (tildes, puntos, comas) como normalize_name() en transform.py
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
),
produccion AS (
    SELECT p.id::text AS id, p.title, 'publicacion' AS tipo, 'tabla de join' AS fuente
    FROM "Publication" p
    JOIN autorias pm ON pm."B" = p.id
    JOIN persona ON persona.id = pm."A"

    UNION ALL

    SELECT t.id::text, t.title, 'tesis', 'tabla de join'
    FROM "Thesis" t
    JOIN "_ThesisMembers" tm ON tm."B" = t.id
    JOIN persona ON persona.id = tm."A"

    UNION ALL

    -- acá no hay FK: hay que buscar el nombre adentro de 4 columnas de texto
    -- libre distintas, con un ILIKE por cada una
    SELECT t.id::text, t.title, 'tesis', 'texto libre (frágil)'
    FROM "Thesis" t, persona
    WHERE t.director ILIKE '%' || persona."firstName" || '%' || persona."lastName" || '%'
       OR t."coDirector" ILIKE '%' || persona."firstName" || '%' || persona."lastName" || '%'
       OR t.student ILIKE '%' || persona."firstName" || '%' || persona."lastName" || '%'
       OR t."otherAdvisors" ILIKE '%' || persona."firstName" || '%' || persona."lastName" || '%'
)
SELECT title, tipo, string_agg(DISTINCT fuente, ' + ' ORDER BY fuente) AS fuentes
FROM produccion
GROUP BY id, title, tipo
ORDER BY tipo, title;
