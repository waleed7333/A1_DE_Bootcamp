"""
Extract all tables from the OLTP database into pandas DataFrames.
"""
import pandas as pd
from config import oltp_engine


def extract_all():
    """Read all required tables from ecommerce_oltp."""

    users = pd.read_sql_table("users", oltp_engine)
    orders = pd.read_sql_table("orders", oltp_engine)
    order_items = pd.read_sql_table("order_items", oltp_engine)
    products = pd.read_sql_table("products", oltp_engine)
    brands = pd.read_sql_table("brands", oltp_engine)
    categories = pd.read_sql_table("categories", oltp_engine)
    branches = pd.read_sql_table("branches", oltp_engine)
    currencies = pd.read_sql_table("currencies", oltp_engine)
    payment_methods = pd.read_sql_table("payment_methods", oltp_engine)
    payments = pd.read_sql_table("payments", oltp_engine)

    print("Extraction complete.")

    return {
        "users": users,
        "orders": orders,
        "order_items": order_items,
        "products": products,
        "brands": brands,
        "categories": categories,
        "branches": branches,
        "currencies": currencies,
        "payment_methods": payment_methods,
        "payments": payments,
    }