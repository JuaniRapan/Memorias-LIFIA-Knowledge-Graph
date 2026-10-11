-- Caso 2 - Navegación N-saltos

-- Misma pregunta que caso_02_n_saltos.rq: colegas de colegas
-- que todavía no son coautores directos. La relación autor-publicación
-- sale de dos lugares, igual que en el grafo: la tabla de join
-- _PublicationMembers(A, B), A = Member.id, B = Publication.id, y el texto
-- libre de Publication.authors resuelto contra Member por nombre.
--
-- Para 1 salto (coautor directo) ya hacen falta 2 self-joins. Para 2 saltos,
-- 4. Cada nivel de profundidad que se quiera agregar duplica la cantidad de
-- joins de la consulta.

WITH persona AS (
    SELECT id FROM "Member" WHERE slug = 'diego-torres'
),
autores_fragmentos AS (
    -- Partimos Publication.authors en un fragmento por autor (separadores
    -- "and", "e", "y", "&" y ";"). Después sacamos tildes, puntos y comas
    -- y lo dejamos en minúscula, igual que normalize_name() en transform.py
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
    -- Un fragmento matchea con un Member si están todas las palabras de su
    -- nombre y apellido (en cualquier orden). Si matchea con más de un Member
    -- no adivinamos, mismo criterio que resolve_person()
    SELECT af.publication_id, mp.member_id,
           COUNT(*) OVER (PARTITION BY af.publication_id, af.fragmento) AS candidatos
    FROM autores_fragmentos af
    JOIN miembros_palabras mp ON mp.palabras <@ af.palabras
),
autorias AS (
    -- Une las dos fuentes con la forma de _PublicationMembers (A, B)
    SELECT "A", "B" FROM "_PublicationMembers"
    UNION
    SELECT member_id, publication_id FROM autoria_por_texto WHERE candidatos = 1
),
coautores_directos AS (
    -- persona -> publicación -> coautor (1 salto)
    SELECT DISTINCT pm2."A" AS member_id
    FROM autorias pm1
    JOIN persona           ON persona.id = pm1."A"
    JOIN autorias pm2 ON pm2."B" = pm1."B" AND pm2."A" != pm1."A"
),
coautores_indirectos AS (
    -- persona -> pub -> coautor_directo -> pub2 -> coautor_2do_grado (2 saltos)
    SELECT DISTINCT pm4."A" AS member_id
    FROM autorias pm1
    JOIN persona           ON persona.id = pm1."A"
    JOIN autorias pm2 ON pm2."B" = pm1."B" AND pm2."A" != pm1."A"
    JOIN autorias pm3 ON pm3."A" = pm2."A"
    JOIN autorias pm4 ON pm4."B" = pm3."B" AND pm4."A" != pm3."A"
)
SELECT m.slug, m."firstName", m."lastName"
FROM "Member" m
JOIN coautores_indirectos ci ON ci.member_id = m.id
JOIN persona p ON m.id != p.id
WHERE m.id NOT IN (SELECT member_id FROM coautores_directos)
ORDER BY m."lastName";
