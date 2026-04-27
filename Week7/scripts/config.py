"""
Configuration settings for the ETL pipeline.
"""
from sqlalchemy import create_engine

# Database connection parameters
DB_USER = "postgres" # Replace with your actual username
DB_PASSWORD = "postgres" # Replace with your actual password
DB_HOST = "localhost"
DB_PORT = "5432"

# Source (OLTP) and Target (OLAP) databases
OLTP_DB = "ecommerce_oltp"
OLAP_DB = "ecommerce_olap"

# Create connection engines
oltp_engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{OLTP_DB}")
olap_engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{OLAP_DB}")