import psycopg2, os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Columnas que están en todas las tablas pero no son dato de dominio (son
# metadata del CMS/auditoría, no forman parte del mapeo ontológico) - se
# excluyen de todos los SELECT.
NON_DOMAIN_FIELDS = {'createdAt', 'updatedAt', 'featured'}

# Tablas principales, tienen su propia entidad en el mapeo ontológico
TABLES = ['Member', 'Project', 'Publication', 'Scholarship', 'Thesis']

# Tablas de join N:M que arma Prisma, cada una solo tiene las columnas A y B
# (las FK). No tienen entidad propia, pero son la fuente de las propiedades
# de objeto (vivo:authorOf, vivo:relatedBy, etc.) del mapeo ontológico.
JOIN_TABLES = [
    '_ProjectMembers',
    '_ProjectPublications',
    '_ProjectScholarships',
    '_ProjectTheses',
    '_PublicationMembers',
    '_ScholarshipMembers',
    '_ThesisMembers',
    '_ThesisPublications',
    '_ThesisScholarships',
]

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

def get_table_fields(cur, table, exclude=NON_DOMAIN_FIELDS):
    """Trae los nombres de columna reales de `table` desde information_schema
    y los devuelve como un string separado por comas y entre comillas dobles,
    listo para usar en un SELECT, salteando las columnas de `exclude`."""
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,)
    )
    columns = [row[0] for row in cur.fetchall()]
    return ', '.join(f'"{column}"' for column in columns if column not in exclude)

def extraction():
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError(
            "No se pudo conectar a la base de datos"
        )

    cur = conn.cursor()
    dataframes = {}

    try:
        all_tables = TABLES + JOIN_TABLES
        fields = [get_table_fields(cur, table) for table in all_tables]

        for table, table_fields in zip(all_tables, fields):
            query = f'SELECT {table_fields} FROM public."{table}"'
            dataframes[table] = pd.read_sql(query, conn)

        # En Member, algunos campos de texto usan "N/A" a mano en vez de un
        # NULL real (es la única tabla que lo hace). Se normaliza todo a NULL
        # para que el "sin dato" sea siempre lo mismo en todo el dataset.
        dataframes['Member'] = dataframes['Member'].replace('N/A', None)
    finally:
        # Cierro conexion
        cur.close()
        conn.close()

    return dataframes