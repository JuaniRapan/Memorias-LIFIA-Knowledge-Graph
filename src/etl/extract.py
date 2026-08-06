import json
import os

import psycopg2
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

# Carpeta de staging donde quedan los CSV crudos, para no tener que pegarle
# a la base cada vez que se corre transform.py mientras se itera el mapeo.
INTERIM_DIR = 'data/interim'

# Un CSV no tiene tipo de columna, entonces las fechas vuelven como texto
# plano si no se guarda aparte qué columna era `date` y cuál `timestamp`
# (ver _cast_date_column). Se cachea junto con los CSV.
DATE_COLUMN_TYPES = {"date", "timestamp without time zone", "timestamp with time zone"}
DATE_COLUMNS_PATH = f"{INTERIM_DIR}/_date_columns.json"


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


def get_table_columns(cur, table, exclude=NON_DOMAIN_FIELDS):
    """Trae (nombre, tipo_postgres) de las columnas reales de `table`, salteando `exclude`."""
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,)
    )
    return [(name, dtype) for name, dtype in cur.fetchall() if name not in exclude]


def _jsonify_cell(value):
    """psycopg2 trae `tags` como lista y `bibtexData` como dict; un CSV no
    puede guardar eso tal cual, así que se pasa a JSON antes de escribir."""
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return value


def _dejsonify_cell(value):
    """Inverso de _jsonify_cell: si la celda pinta de lista/dict en JSON,
    la parsea; si no, la deja como vino (string, número, NaN, etc)."""
    if not isinstance(value, str) or not value or value[0] not in "[{":
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def extraction():
    """Trae las tablas principales y las de join desde Postgres y las
    deja como CSV en INTERIM_DIR, listas para que transform.py las lea."""
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError(
            "No se pudo conectar a la base de datos"
        )

    cur = conn.cursor()
    dataframes = {}
    date_columns = {}

    try:
        all_tables = TABLES + JOIN_TABLES

        for table in all_tables:
            columns = get_table_columns(cur, table)
            fields = ', '.join(f'"{name}"' for name, _ in columns)
            query = f'SELECT {fields} FROM public."{table}"'
            dataframes[table] = pd.read_sql(query, conn)
            # se guarda aparte qué columnas son date/timestamp: un CSV no
            # tiene tipos, así que load_interim() necesita esto para poder
            # reconstruir esos valores como fecha y no como texto plano
            date_columns[table] = {
                name: dtype for name, dtype in columns if dtype in DATE_COLUMN_TYPES
            }

        # En Member, algunos campos de texto usan "N/A" a mano en vez de un
        # NULL real (es la única tabla que lo hace). Se normaliza todo a NULL
        # para que el "sin dato" sea siempre lo mismo en todo el dataset.
        dataframes['Member'] = dataframes['Member'].replace('N/A', None)
    finally:
        # Cierro conexion
        cur.close()
        conn.close()

    os.makedirs(INTERIM_DIR, exist_ok=True)
    for table, df in dataframes.items():
        df.map(_jsonify_cell).to_csv(f"{INTERIM_DIR}/{table}.csv", index=False)
    with open(DATE_COLUMNS_PATH, "w", encoding="utf-8") as f:
        json.dump(date_columns, f)
    print(f"{len(dataframes)} tablas guardadas como CSV en {INTERIM_DIR}/")


def _cast_date_column(series, pg_type):
    """Reconstruye una columna date/timestamp desde el texto plano del CSV,
    tal como la devolvía psycopg2 antes de pasar por el CSV."""
    parsed = pd.to_datetime(series, errors="coerce")
    if pg_type == "date":
        values = parsed.dt.date
    else:
        values = pd.Series(parsed.dt.to_pydatetime(), index=series.index)
    # .dt.date/.dt.to_pydatetime() dejan pd.NaT en los faltantes, y NaT no
    # entra en el chequeo de has_value() (no es instancia de float); se
    # pasa a None acá para que siga contando como "sin dato" más adelante
    return values.where(parsed.notna(), None)


def load_interim():
    """Lee los CSV que dejó extraction() en INTERIM_DIR y devuelve el
    mismo dict {tabla: dataframe} que antes armaba extraction() en memoria."""
    with open(DATE_COLUMNS_PATH, encoding="utf-8") as f:
        date_columns = json.load(f)

    dataframes = {}
    for table in TABLES + JOIN_TABLES:
        df = pd.read_csv(f"{INTERIM_DIR}/{table}.csv")
        df = df.map(_dejsonify_cell)
        for column, pg_type in date_columns.get(table, {}).items():
            if column in df.columns:
                df[column] = _cast_date_column(df[column], pg_type)
        dataframes[table] = df
    return dataframes


if __name__ == "__main__":
    extraction()
