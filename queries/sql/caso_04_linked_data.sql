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


SELECT p.title
FROM "Member" m
JOIN "_PublicationMembers" pm ON pm."A" = m.id
JOIN "Publication" p ON p.id = pm."B"
WHERE regexp_replace(m.orcid, '^https?://orcid\.org/', '', 'i') = '0000-0001-7533-0133'
ORDER BY p.title;
