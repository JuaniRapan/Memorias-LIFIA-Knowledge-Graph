-- Caso 1 - Jerarquía (equivalente relacional)
--
-- Misma pregunta que caso_01_jerarquia_cso.rq: "publicaciones sobre IA,
-- incluyendo sus subtemas". El problema es que en el dump NO hay taxonomía:
-- Publication.tags es un text[] de strings sueltos, sin tabla de temas ni
-- relación padre/hijo. Así que la única forma de traer "todo lo que sea IA"
-- es enumerar a mano cada subtema conocido y mantener esa lista al día.

SELECT p.slug  AS publicacion,
       p.title AS titulo,
       lower(t.tag) AS tema
FROM "Publication" p
CROSS JOIN LATERAL unnest(p.tags) AS t(tag)
WHERE lower(t.tag) = ANY (ARRAY[
    'artificial intelligence',
    'machine learning',
    'deep learning',
    'natural language processing',
    'computer vision',
    'neural networks',
    'reinforcement learning',
    'supervised learning',
    'unsupervised learning',
    'recommender systems',
    'knowledge representation',
    'semantic web'
])
ORDER BY titulo;
