"""
Create the OLAP database, tables, and insert all transformed data.
"""
from config import olap_engine, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from sqlalchemy import create_engine, text
from transform_facts import build_fct_order_transaction
from create_indexes import create_basic_indexes  # ← Import only basic


def create_olap_database():
    """Create ecommerce_olap if it does not exist."""
    admin_engine = create_engine(
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres",
        isolation_level="AUTOCOMMIT"
    )
    with admin_engine.connect() as conn:
        result = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = 'ecommerce_olap'"))
        if result.fetchone() is None:
            conn.execute(text("CREATE DATABASE ecommerce_olap"))
            print("Database ecommerce_olap created.")
        else:
            print("Database ecommerce_olap already exists.")


def load_all():
    """Create OLAP database, tables, load all data, and create basic indexes."""
    create_olap_database()

    fact, all_data = build_fct_order_transaction()

    tables = {
        "dim_date": all_data["dim_date"],
        "dim_time": all_data["dim_time"],
        "dim_currency": all_data["dim_currency"],
        "dim_brand": all_data["dim_brand"],
        "dim_category": all_data["dim_category"],
        "dim_branch": all_data["dim_branch"],
        "dim_user": all_data["dim_user"],
        "dim_payment_method": all_data["dim_payment_method"],
        "dim_product": all_data["dim_product"],
        "dim_status": all_data["dim_status"],
        "fct_order_transaction": fact,
    }

    for table_name, df in tables.items():
        df.to_sql(table_name, olap_engine, if_exists="replace", index=False)
        print(f"Loaded {table_name}: {len(df)} rows.")

    # Create basic indexes automatically
    print("Creating basic indexes...")
    create_basic_indexes()

    print("\nAll tables loaded and indexed successfully!\n")
    print("Tip: To enable advanced indexes, edit create_indexes.py and uncomment the lines.\n")


if __name__ == "__main__":
    load_all()