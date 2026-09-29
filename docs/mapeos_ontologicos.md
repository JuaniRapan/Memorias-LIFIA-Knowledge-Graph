# Mapeo Ontológico

Mapeo del dump `data/raw/new_memorias_para_kgsw.dump` a **VIVO**, **CSO** y **DBLP**, con **BIBO**, **FOAF**, **Dublin Core** y **SKOS** para cubrir lo que no alcanzan.

- **5 tablas base:** `Member`, `Project`, `Publication`, `Scholarship`, `Thesis`.
- **9 tablas de join N:M:** se traducen en propiedades de objeto, no en clases.
- **2 entidades sin tabla propia:** Topic (sale de `tags`/`keywords`) y Venue (sale de `bibtexData`).

---

## 1. Resumen de clases

| Entidad     | Origen                    | Clase(s) RDF                                                                 | Ontología        |
| ----------- | ------------------------- | ---------------------------------------------------------------------------- | ---------------- |
| Miembro     | `Member`                  | `vivo:FacultyMember` + `foaf:Person`                                         | VIVO / FOAF      |
| Publicación | `Publication`             | `bibo:Document` + clase DBLP según `type` (\*)                               | DBLP / BIBO / DC |
| Proyecto    | `Project`                 | `vivo:Project`                                                               | VIVO             |
| Beca        | `Scholarship`             | `vivo:Grant`                                                                 | VIVO             |
| Tesis       | `Thesis`                  | `bibo:Thesis`                                                                | BIBO / VIVO      |
| Topic       | `tags`, `Thesis.keywords` | IRI de CSO si matchea; si no, `cso:Topic` + `skos:Concept` propio            | CSO / SKOS       |
| Venue       | `Publication.bibtexData`  | `bibo:Journal` (si trae `journal`) o `bibo:Conference` (si trae `booktitle`) | BIBO             |

(\*) `article` → `dblp:Article` · `inproceedings` → `dblp:Inproceedings` · `inbook` → `dblp:Incollection` · `book` → `dblp:Book`. Cualquier otro valor: solo `bibo:Document`.

---

## 2. Propiedades por entidad

### Comunes a varias tablas

| Columna SQL            | Propiedad RDF                                                                     | Aplica a                                          |
| ---------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------- |
| `id`                   | `dcterms:identifier`                                                              | Todas las tablas base                             |
| `startDate`, `endDate` | `vivo:dateTimeInterval` (nodo con `vivo:start` / `vivo:end`)                      | Todas menos `Publication`                         |
| `tags`                 | → `cso:Topic` vía `vivo:hasResearchArea` (Member) o `vivo:hasSubjectArea` (resto) | Member, Project, Publication, Scholarship, Thesis |
| `slug`                 | No se mapea: arma la IRI (`lifia:persona/{slug}`)                                 | Todas las tablas base                             |

Los campos que contienen URLs se guardan como IRI **solo si tienen forma de URL**.

### Member

| Columna SQL                                                             | Propiedad RDF                           |
| ----------------------------------------------------------------------- | --------------------------------------- |
| `firstName` / `lastName`                                                | `foaf:firstName` / `foaf:lastName`      |
| `personalEmail`, `institutionalEmail`                                   | `foaf:mbox`                             |
| `phone`                                                                 | `foaf:phone`                            |
| `webPage`                                                               | `foaf:homepage`                         |
| `avatarUrl`                                                             | `foaf:depiction`                        |
| `highestDegree`                                                         | `lifia-ontology:highestDegree`          |
| `positionAtLab`, `positionAtUnlp`, `positionAtCIC`, `positionAtCONICET` | `lifia-ontology:jobTitle`               |
| `category`, `sicadiCategory`, `affiliations`                            | `rdfs:comment`                          |
| `shortCvIn{Spanish,English}`                                            | `lifia-ontology:shortCv` (`@es`/`@en`)  |
| `interestsIn{Spanish,English}`                                          | `lifia-ontology:researchInterests` (`@es`/`@en`) |
| `orcid`                                                                 | `owl:sameAs` → `https://orcid.org/{id}` |
| `dblpProfile`                                                           | `owl:sameAs` → URL de DBLP              |
| `googleResearchProfile`, `researchGateProfile`                          | `rdfs:seeAlso`                          |

### Publication

| Columna SQL                        | Propiedad RDF                                                   |
| ---------------------------------- | --------------------------------------------------------------- |
| `title`                            | `dc:title`                                                      |
| `year`                             | `vivo:dateIssued` → nodo `vivo:DateTimeValue` (ver §4)          |
| `selfArchivingUrl`                 | `bibo:uri`                                                      |
| `ranking`                          | `rdfs:comment`                                                  |
| `authors`                          | `dc:creator` (texto libre, split por " and "; incluye externos) |
| `bibtexData.doi`                   | `bibo:doi`                                                      |
| `bibtexData.pages`                 | `bibo:pageStart` / `bibo:pageEnd`                               |
| `bibtexData.journal` / `booktitle` | `bibo:presentedAt` → Venue                                      |

### Project

| Columna SQL                         | Propiedad RDF                                                            |
| ----------------------------------- | ------------------------------------------------------------------------ |
| `title`                             | `rdfs:label`                                                             |
| `code`                              | `vivo:localAwardId`                                                      |
| `amount`                            | `vivo:totalAwardAmount`                                                  |
| `summary`                           | `vivo:description`                                                       |
| `website`                           | `foaf:homepage`                                                          |
| `fundingAgency`, `responsibleGroup` | `rdfs:comment`                                                           |
| `director`, `coDirector`            | `vivo:contributingRole` → nodo `vivo:PrincipalInvestigatorRole` (ver §4) |

### Scholarship

| Columna SQL                         | Propiedad RDF                     |
| ----------------------------------- | --------------------------------- |
| `title`                             | `rdfs:label`                      |
| `summary`                           | `vivo:description`                |
| `type`, `fundingAgency`             | `rdfs:comment`                    |
| `student`, `director`, `coDirector` | `vivo:relates` → persona (ver §4) |

### Thesis

| Columna SQL                                          | Propiedad RDF                                                                                                              |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `title`                                              | `dc:title`                                                                                                                 |
| `level`                                              | `bibo:degree` vía `LEVEL_TO_DEGREE` (Undergraduate→Grado, Masters→Maestría, PhD→Doctorado, Specialization→Especialización) |
| `career`                                             | `rdfs:comment`                                                                                                             |
| `progress`                                           | `lifia-ontology:completionPercentage` (entero 0-100)                                                                       |
| `summary`                                            | `vivo:description`                                                                                                         |
| `reportUrl`, `website`                               | `bibo:uri`                                                                                                                 |
| `keywords`                                           | `vivo:hasSubjectArea` → `cso:Topic` (solo si matchea un tema conocido)                                                     |
| `student`, `director`, `coDirector`, `otherAdvisors` | `vivo:relates` → persona                                                                                                   |

### Topic y Venue

| Entidad                      | Propiedades                                                               |
| ---------------------------- | ------------------------------------------------------------------------- |
| Topic (no matcheado con CSO) | `rdfs:label` / `skos:prefLabel` = tag original, sin traducir              |
| Venue                        | `rdfs:label` (nombre), `bibo:issn` / `bibo:isbn` (si vienen en el BibTeX) |

Ambos son siempre **objeto** de un triple, nunca sujeto.

---

## 3. Tablas de join

El triple es siempre `A → B`, donde `A` es el modelo que va primero alfabéticamente (convención de Prisma, verificada contra los UUID reales).

| Tabla                  | Triple generado                                                   |
| ---------------------- | ----------------------------------------------------------------- |
| `_ProjectMembers`      | Member `vivo:relatedBy` **MemberRole** `vivo:roleContributesTo` Project (ver §4) |
| `_PublicationMembers`  | Member `vivo:relatedBy` **Authorship** `vivo:relates` Publication |
| `_ScholarshipMembers`  | Member `vivo:relatedBy` **Relationship** `vivo:relates` Scholarship (ver §4) |
| `_ThesisMembers`       | Member `vivo:relatedBy` **Relationship** `vivo:relates` Thesis (ver §4) |
| `_ProjectPublications` | Project `vivo:relatedBy` Publication                              |
| `_ProjectScholarships` | Project `vivo:relatedBy` Scholarship                              |
| `_ProjectTheses`       | Project `vivo:relatedBy` Thesis                                   |
| `_ThesisPublications`  | Publication `vivo:relatedBy` Thesis                               |
| `_ThesisScholarships`  | Scholarship `vivo:relatedBy` Thesis                               |

---

## 4. Decisiones de modelado

### Patrones con nodo intermedio

- **Autoría:** un nodo `vivo:Authorship` por cada par `(Member, Publication)`. `Persona ⇄ Authorship ⇄ Publicación` con `vivo:relatedBy` (hacia el nodo) y `vivo:relates` (desde el nodo).
- **Director de proyecto:** un nodo `vivo:PrincipalInvestigatorRole` por director/codirector. Persona ⇄ Rol con `vivo:relatedBy` / `vivo:relates`. Rol ⇄ Proyecto con `vivo:roleContributesTo` / `vivo:contributingRole`. En Scholarship y Thesis se usa `vivo:relates` directo, porque VIVO no define un rol específico para ese caso.
- **Integrante de proyecto (`_ProjectMembers`):** mismo patrón que el director, pero con un nodo `vivo:MemberRole` en vez de `vivo:PrincipalInvestigatorRole`.
- **Integrante de tesis/beca (`_ThesisMembers`, `_ScholarshipMembers`):** un nodo `vivo:Relationship` genérico por cada par, con `vivo:relatedBy` / `vivo:relates` de los dos lados. Hace falta el nodo (y no un `vivo:relatedBy` directo Member→Thesis/Scholarship) porque `foaf:Agent` restringe todo lo que se le cuelgue de `vivo:relatedBy` a ser un `vivo:Relationship`; sin el nodo intermedio, el razonador clasificaría mal la tesis o la beca.
- **`vivo:dateIssued` (Publication):** un nodo `vivo:DateTimeValue` propio con `vivo:dateTime` (1ro de enero del año, único dato que trae el dataset), igual que se hace con `vivo:dateTimeInterval`.

### Resolución de nombres en texto libre

Los campos `director`, `coDirector`, `student` y `otherAdvisors` son texto, no FK. Se resuelven contra `Member` probando, en orden:

1. Nombre tal cual.
2. Invertido ("Apellido, Nombre").
3. Sin nombres del medio.
4. Por subconjunto de palabras.
5. Fuzzy matching (`difflib`, umbral 0.85).

(En caso de que no matchee, se descarta y queda en el log).

Todos los casos quedan registrados en `data/processed/relaciones_sin_resolver.csv`.

### Otras notas

- **`id` vs. `slug`:** el `slug` arma la IRI. El id se guarda como `dcterms:identifier` para trazar cada nodo hasta su fila de la bd relacional, aunque cambie el slug.
- **`authors` vs. `_PublicationMembers`:** `dc:creator` guarda todos los autores como texto (también los externos). `Authorship` enlaza solo a los autores internos.
- **Topics:** cada tag o keyword se normaliza y se compara contra `data/external/cso.csv`. `Thesis.keywords` es un string, no un array: `split_keywords()` decide si separar por `,` o `;`.
- **Venues:** se deduplican por slug del nombre.
- **Namespaces propios:** `lifia:` (`http://lifia.info.unlp.edu.ar/resource/`) es solo para instancias. `lifia-ontology:` es para propiedades sin equivalente externo que respete el dominio/rango real de VIVO: `completionPercentage`, `highestDegree`, `jobTitle` (VIVO pediría un nodo `Position` por cargo), `shortCv` y `researchInterests` (VIVO tiene `overview`, pero es `owl:FunctionalProperty` y acá hay hasta 4 valores por persona).
- **Fuera del mapeo:** el enum `Role` (permisos del CMS) y `createdAt`, `updatedAt` y `featured` (filtrados en `extract.py`, ver `NON_DOMAIN_FIELDS`).
