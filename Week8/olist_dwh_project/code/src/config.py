# src/config.py
# Centralized configuration - loads environment variables and provides DB connections

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Load environment variables from .env file
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# ---------------------------------------------------------------------------
# Database connection parameters
# ---------------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
OLTP_DB = os.getenv("OLTP_DB", "olist_oltp")
OLAP_DB = os.getenv("OLAP_DB", "olist_olap")
SQLITE_PATH = os.getenv("SQLITE_PATH", str(BASE_DIR / "data" / "olist.sqlite"))

# ---------------------------------------------------------------------------
# Connection strings
# ---------------------------------------------------------------------------
POSTGRES_BASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}"


def get_postgres_engine(db_name: str = None):
    """
    Return a SQLAlchemy engine connected to a PostgreSQL database.

    Parameters
    ----------
    db_name : str, optional
        Target database name. If None, connects to default 'postgres' database.

    Returns
    -------
    sqlalchemy.engine.Engine
    """
    if db_name:
        url = f"{POSTGRES_BASE_URL}/{db_name}"
    else:
        url = f"{POSTGRES_BASE_URL}/postgres"

    return create_engine(url, isolation_level="AUTOCOMMIT")


def get_oltp_engine():
    """Return engine connected to the OLTP database."""
    return get_postgres_engine(OLTP_DB)


def get_olap_engine():
    """Return engine connected to the OLAP database."""
    return get_postgres_engine(OLAP_DB)


def create_database(db_name: str):
    """
    Create a PostgreSQL database if it does not exist.

    Parameters
    ----------
    db_name : str
        Name of the database to create.
    """
    engine = get_postgres_engine()  # connect to default 'postgres' database
    with engine.connect() as conn:
        # Check if database already exists
        result = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db"),
            {"db": db_name},
        )
        exists = result.fetchone()

        if not exists:
            # CREATE DATABASE cannot run inside a transaction
            conn.execute(text("COMMIT"))
            conn.execute(text(f"CREATE DATABASE {db_name}"))
            print(f"  ✓ Database '{db_name}' created successfully")
        else:
            print(f"  → Database '{db_name}' already exists, skipping creation")


def create_schema(engine, schema_name: str):
    """
    Create a PostgreSQL schema if it does not exist.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
        Connected engine to the target database.
    schema_name : str
        Name of the schema to create.
    """
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        conn.execute(text("COMMIT"))
    print(f"  ✓ Schema '{schema_name}' ready")