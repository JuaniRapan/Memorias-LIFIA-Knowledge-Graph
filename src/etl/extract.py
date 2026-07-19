import psycopg2, os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect()

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        print("Conectado a la base de datos")
        return conn
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        return None
    
def extraction():
    # Cursor para interactuar con la bd
    # cur = conn.cursor()

    tables = ['Member', 'Project', 'Publication', 'Scholarship', 'Thesis']
    fields = [
        'id, firstName, lastName, slug, startDate, endDate, highestDegree, coursesAtUNLP, positionAtLab, positionAtUnlp, category, sicadiCategory, positionAtCIC, positionAtCONICET, personalEmail, institutionalEmail, phone, webPage, orcid, dblpProfile, googleResearchProfile, researchGateProfile, shortCvInSpanish, shortCvInEnglish, interestsInEnglish, interestsInSpanish, affiliations, avatarUrl, tags, createdAt, updatedAt',
        'id, title, code, slug, startDate, endDate, director, coDirector, responsibleGroup, fundingAgency, amount, summary, website, tags, featured, createdAt, updatedAt',
        'id, slug, type, title, authors, year, ranking, selfArchivingUrl, bibtexData, tags, featured, createdAt, updatedAt',
        'id, title, slug, type, student, director, coDirector, fundingAgency, startDate, endDate, summary, tags, createdAt, updatedAt',
        'id, title, slug, career, level, student, director, coDirector, otherAdvisors, startDate, endDate, summary, reportUrl, progress, keywords, website, tags, featured, createdAt, updatedAt',
    ]

    for i in range (1, len(tables)):
        query = f"SELECT {fields[i]} FROM {tables[i]}"
        pd.read_sql(query, conn)

    # Manejar N/A en tabla Members

    cur.execute("""

                """)

    # Cierro cursor y conexión a la bd
    cur.close()
    conn.close()