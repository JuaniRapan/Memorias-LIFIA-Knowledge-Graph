-- Se pone en modo FULL para que muestre todos los campos (incluido el slug, que es el que usamos para 
--identificar en el KG). En modo default solo muestra la primary key.
ALTER TABLE "Member" REPLICA IDENTITY FULL;
ALTER TABLE "Project" REPLICA IDENTITY FULL;
ALTER TABLE "Publication" REPLICA IDENTITY FULL;
ALTER TABLE "Scholarship" REPLICA IDENTITY FULL;
ALTER TABLE "Thesis" REPLICA IDENTITY FULL;
ALTER TABLE "_ProjectMembers" REPLICA IDENTITY FULL;
ALTER TABLE "_ProjectPublications" REPLICA IDENTITY FULL;
ALTER TABLE "_ProjectScholarships" REPLICA IDENTITY FULL;
ALTER TABLE "_ProjectTheses" REPLICA IDENTITY FULL;
ALTER TABLE "_PublicationMembers" REPLICA IDENTITY FULL;
ALTER TABLE "_ScholarshipMembers" REPLICA IDENTITY FULL;
ALTER TABLE "_ThesisMembers" REPLICA IDENTITY FULL;
ALTER TABLE "_ThesisPublications" REPLICA IDENTITY FULL;
ALTER TABLE "_ThesisScholarships" REPLICA IDENTITY FULL;
