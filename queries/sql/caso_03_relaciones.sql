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

WITH persona AS (
    SELECT id, "firstName", "lastName"
    FROM "Member"
    WHERE slug = 'diego-torres'
)

SELECT p.title, 'publicacion' AS tipo
FROM "Publication" p
JOIN "_PublicationMembers" pm ON pm."B" = p.id
JOIN persona ON persona.id = pm."A"

UNION ALL

SELECT t.title, 'tesis (tabla de join)' AS tipo
FROM "Thesis" t
JOIN "_ThesisMembers" tm ON tm."B" = t.id
JOIN persona ON persona.id = tm."A"

UNION ALL

-- acá no hay FK: hay que buscar el nombre adentro de 4 columnas de texto
-- libre distintas, con un ILIKE por cada una
SELECT t.title, 'tesis (texto libre, frágil)' AS tipo
FROM "Thesis" t, persona
WHERE t.director ILIKE '%' || persona."firstName" || '%' || persona."lastName" || '%'
   OR t."coDirector" ILIKE '%' || persona."firstName" || '%' || persona."lastName" || '%'
   OR t.student ILIKE '%' || persona."firstName" || '%' || persona."lastName" || '%'
   OR t."otherAdvisors" ILIKE '%' || persona."firstName" || '%' || persona."lastName" || '%'

ORDER BY tipo, title;

