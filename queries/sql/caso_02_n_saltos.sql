-- Caso 2 - Navegación N-saltos

-- Misma pregunta que caso_02_n_saltos.rq: colegas de colegas 
-- que todavía no son coautores directos. La única
-- fuente de la relación autor-publicación es la tabla de join
-- _PublicationMembers(A, B), A = Member.id, B = Publication.id.
--
-- Para 1 salto (coautor directo) ya hacen falta 2 self-joins. Para 2 saltos,
-- 4. Cada nivel de profundidad que se quiera agregar duplica la cantidad de
-- joins de la consulta.

WITH persona AS (
    SELECT id FROM "Member" WHERE slug = 'diego-torres'
),
coautores_directos AS (
    -- persona -> publicación -> coautor (1 salto)
    SELECT DISTINCT pm2."A" AS member_id
    FROM "_PublicationMembers" pm1
    JOIN persona           ON persona.id = pm1."A"
    JOIN "_PublicationMembers" pm2 ON pm2."B" = pm1."B" AND pm2."A" != pm1."A"
),
coautores_indirectos AS (
    -- persona -> pub -> coautor_directo -> pub2 -> coautor_2do_grado (2 saltos)
    SELECT DISTINCT pm4."A" AS member_id
    FROM "_PublicationMembers" pm1
    JOIN persona           ON persona.id = pm1."A"
    JOIN "_PublicationMembers" pm2 ON pm2."B" = pm1."B" AND pm2."A" != pm1."A"
    JOIN "_PublicationMembers" pm3 ON pm3."A" = pm2."A"
    JOIN "_PublicationMembers" pm4 ON pm4."B" = pm3."B" AND pm4."A" != pm3."A"
)
SELECT m.slug, m."firstName", m."lastName"
FROM "Member" m
JOIN coautores_indirectos ci ON ci.member_id = m.id
JOIN persona p ON m.id != p.id
WHERE m.id NOT IN (SELECT member_id FROM coautores_directos)
ORDER BY m."lastName";