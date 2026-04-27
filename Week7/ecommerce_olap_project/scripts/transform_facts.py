"""
Build the fact table: fct_order_transaction.
"""
import pandas as pd
from transform_dimensions import build_all_dimensions


def build_fct_order_transaction():
    """Build the fact table linked to all dimensions."""
    all_data = build_all_dimensions()
    raw = all_data["_raw"]

    orders = raw["orders"]
    order_items = raw["order_items"]
    products = raw["products"]
    payments = raw.get("payments")

    # Merge order_items with orders
    fact = order_items.merge(
        orders[["order_id", "user_id", "branch_id", "currency_id", "order_date", "status"]],
        on="order_id",
        how="inner",
    )

    # Merge with products for brand_id and category_id
    fact = fact.merge(
        products[["product_id", "brand_id", "category_id"]],
        on="product_id",
        how="left",
    )

    # Lookup product_key from dim_product
    dim_product = all_data["dim_product"]
    fact = fact.merge(
        dim_product[["product_key", "product_id"]],
        on="product_id",
        how="left",
    )

    # Lookup user_key from dim_user
    dim_user = all_data["dim_user"]
    fact = fact.merge(
        dim_user[["user_key", "user_id"]],
        on="user_id",
        how="left",
    )

    # Lookup branch_key from dim_branch
    dim_branch = all_data["dim_branch"]
    fact = fact.merge(
        dim_branch[["branch_key", "branch_id"]],
        on="branch_id",
        how="left",
    )

    # Lookup brand_key from dim_brand
    dim_brand = all_data["dim_brand"]
    fact = fact.merge(
        dim_brand[["brand_key", "brand_id"]],
        on="brand_id",
        how="left",
    )

    # Lookup category_key from dim_category
    dim_category = all_data["dim_category"]
    fact = fact.merge(
        dim_category[["category_key", "category_id"]],
        on="category_id",
        how="left",
    )

    # Lookup currency_key from dim_currency (the currency used in the order)
    dim_currency = all_data["dim_currency"]
    fact = fact.merge(
        dim_currency[["currency_key", "currency_id"]],
        on="currency_id",
        how="left",
    )

    # Lookup status_key from dim_status
    dim_status = all_data["dim_status"]
    fact = fact.merge(
        dim_status[["status_key", "status_name"]],
        left_on="status",
        right_on="status_name",
        how="left",
    )

    # Payment method key from payments table
    if payments is not None:
        pay_map = payments[["order_id", "method_id"]].drop_duplicates()
        fact = fact.merge(pay_map, on="order_id", how="left")
        dim_pay = all_data["dim_payment_method"]
        fact = fact.merge(
            dim_pay[["payment_method_key", "payment_method_id"]],
            left_on="method_id",
            right_on="payment_method_id",
            how="left",
        )
    else:
        fact["payment_method_key"] = None

    # Date and time keys
    order_dt = pd.to_datetime(fact["order_date"])
    fact["date_key"] = order_dt.dt.strftime('%Y%m%d').astype(int)
    fact["time_key"] = order_dt.dt.strftime('%H%M%S').astype(int)

    # Measures
    fact["quantity"] = fact["quantity"]
    fact["unit_sale_price"] = fact["unit_sale_price"]
    fact["unit_purchase_price"] = fact["unit_purchase_price"]
    fact["sales_amount"] = fact["quantity"] * fact["unit_sale_price"]
    fact["profit"] = fact["sales_amount"] - (fact["quantity"] * fact["unit_purchase_price"])
    fact["profit_margin"] = fact["profit"] / fact["sales_amount"] * 100

    # Select and order final columns
    final_columns = [
        "date_key",
        "time_key",
        "product_key",
        "brand_key",
        "category_key",
        "user_key",
        "branch_key",
        "currency_key",
        "payment_method_key",
        "status_key",
        "quantity",
        "unit_sale_price",
        "unit_purchase_price",
        "sales_amount",
        "profit",
        "profit_margin",
    ]

    fact = fact[final_columns].copy()
    fact.reset_index(drop=True, inplace=True)
    fact.index += 1
    fact["transaction_key"] = fact.index

    # Reorder so transaction_key is first
    fact = fact[["transaction_key"] + [c for c in final_columns if c != "transaction_key"]]

    print("fct_order_transaction built:", len(fact), "rows")
    return fact, all_data