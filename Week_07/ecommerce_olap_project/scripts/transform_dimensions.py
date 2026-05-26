"""
Transform extracted OLTP tables into dimension tables for the OLAP schema.
"""
import pandas as pd
import numpy as np
from hijridate import Gregorian
from extract import extract_all


def build_dim_date():
    """Generate date dimension at daily granularity."""
    dates = pd.date_range(start="2020-01-01", end="2030-12-31", freq="D")

    df = pd.DataFrame({
        "date_key": dates.strftime('%Y%m%d').astype(int),
        "date_actual": dates.date,
        "year": dates.year,
        "month": dates.month,
        "day": dates.day,
        "quarter": dates.quarter,
        "day_name": dates.strftime("%A"),
        "month_name": dates.strftime("%B"),
        "day_of_week": dates.dayofweek,
        "week_of_year": dates.isocalendar().week.astype(int),
        "is_weekend": dates.dayofweek.isin([4, 5]),
        "is_weekday": ~dates.dayofweek.isin([4, 5]),
        "is_month_end": dates.is_month_end,
        "is_month_start": dates.is_month_start,
        "is_year_start": dates.is_year_start,
        "is_year_end": dates.is_year_end,
    })

    df["season"] = df["month"].map({
        12: "Winter", 1: "Winter", 2: "Winter",
        3: "Spring", 4: "Spring", 5: "Spring",
        6: "Summer", 7: "Summer", 8: "Summer",
        9: "Fall", 10: "Fall", 11: "Fall",
    })

    hijri_data = [Gregorian(d.year, d.month, d.day).to_hijri() for d in dates]

    df["hijri_year"] = [h.year for h in hijri_data]
    df["hijri_month"] = [h.month for h in hijri_data]
    df["hijri_day"] = [h.day for h in hijri_data]
    df["hijri_month_name"] = [h.month_name() for h in hijri_data]

    df["is_ramadan"] = df["hijri_month"] == 9
    df["is_eid_al_fitr"] = (df["hijri_month"] == 10) & (df["hijri_day"].isin([1, 2, 3]))
    df["is_eid_al_adha"] = (df["hijri_month"] == 12) & (df["hijri_day"].isin([10, 11, 12, 13]))
    df["is_eid"] = df["is_eid_al_fitr"] | df["is_eid_al_adha"]

    national_holidays = [(5, 22), (9, 26), (10, 14), (11, 30)]
    df["is_national_holiday"] = df.apply(
        lambda row: (row["month"], row["day"]) in national_holidays, axis=1
    )   

    df["is_holiday"] = df["is_eid"] | df["is_national_holiday"]

    print(f"Success: dim_date built with {len(df)} rows.")
    return df


def build_dim_time():
    """Generate time dimension at minute granularity."""
    times = pd.date_range("2024-01-01", "2024-01-02", freq="min", inclusive="left")

    df = pd.DataFrame({
        "time_key": times.strftime('%H%M%S').astype(int),
        "time_of_day": times.strftime("%H:%M:%S"),
        "hour": times.hour,
        "minute": times.minute,
    })

    conditions = [
        (df["hour"] < 12),
        (df["hour"] < 17),
        (df["hour"] >= 17)
    ]
    choices = ["Morning", "Afternoon", "Evening"]
    df["daytime_name"] = np.select(conditions, choices, default="Night")

    df["day_night"] = np.where((df["hour"] >= 6) & (df["hour"] < 18), "Day", "Night")

    print(f"Success: dim_time built with {len(df)} rows.")
    return df


def build_dim_currency(currencies):
    """Build currency dimension."""
    df = pd.DataFrame()
    df["currency_id"] = currencies["currency_id"]
    df["currency_code"] = currencies["currency_code"]
    df["currency_name"] = currencies["currency_name"]
    df["exchange_rate_to_sar"] = currencies["exchange_rate_to_sar"]
    df.reset_index(drop=True, inplace=True)
    df.index += 1
    df["currency_key"] = df.index
    df = df[["currency_key", "currency_id", "currency_code", "currency_name", "exchange_rate_to_sar"]]

    print("dim_currency built:", len(df), "rows")
    return df


def build_dim_brand(brands):
    """Build brand dimension."""
    df = pd.DataFrame()
    df["brand_id"] = brands["brand_id"]
    df["brand_name"] = brands["brand_name"]
    df["country"] = brands.get("country_of_origin", "Unknown")
    df.reset_index(drop=True, inplace=True)
    df.index += 1
    df["brand_key"] = df.index
    df = df[["brand_key", "brand_id", "brand_name", "country"]]

    print("dim_brand built:", len(df), "rows")
    return df


def build_dim_category(categories):
    """Build category dimension."""
    df = pd.DataFrame()
    df["category_id"] = categories["category_id"]
    df["category_name"] = categories["category_name"]
    df.reset_index(drop=True, inplace=True)
    df.index += 1
    df["category_key"] = df.index
    df = df[["category_key", "category_id", "category_name"]]

    print("dim_category built:", len(df), "rows")
    return df


def build_dim_branch(branches):
    """Build branch dimension."""
    df = pd.DataFrame()
    df["branch_id"] = branches["branch_id"]
    df["branch_name"] = branches["branch_name"]
    df["branch_city"] = branches["city"]
    df["branch_manager"] = branches["manager_name"]
    df["branch_location"] = branches.get("location_details", "")
    df.reset_index(drop=True, inplace=True)
    df.index += 1
    df["branch_key"] = df.index
    df = df[["branch_key", "branch_id", "branch_name", "branch_city", "branch_manager", "branch_location"]]

    print("dim_branch built:", len(df), "rows")
    return df


def build_dim_user(users, currencies):
    """Build user dimension (SCD Type 2)."""
    df = users.merge(
        currencies[["currency_key", "currency_id", "currency_code"]],
        left_on="preferred_currency_id",
        right_on="currency_id",
        how="left"
    )

    df_out = pd.DataFrame()
    df_out["user_id"] = df["user_id"]
    df_out["user_name"] = df["full_name"]
    df_out["user_email"] = df["email"]
    df_out["user_phone"] = df["phone"]
    df_out["currency_key"] = df["currency_key"].fillna(1)  # Default to SAR
    df_out["currency_code"] = df["currency_code"].fillna("SAR")
    df_out["user_address"] = df["address"].fillna("Unknown")
    df_out["start_date"] = pd.Timestamp("2024-01-01").date()
    df_out["end_date"] = pd.NaT
    df_out["is_current"] = True

    df_out.reset_index(drop=True, inplace=True)
    df_out.index += 1
    df_out["user_key"] = df_out.index
    df_out = df_out[[
        "user_key", "user_id", "user_name", "user_email", "user_phone",
        "currency_key", "currency_code", "user_address",
        "start_date", "end_date", "is_current"
    ]]

    print("dim_user built:", len(df_out), "rows")
    return df_out


def build_dim_payment_method(payment_methods):
    """Build payment method dimension (SCD Type 2)."""
    df = pd.DataFrame()
    df["payment_method_id"] = payment_methods["method_id"]
    df["payment_method_name"] = payment_methods["method_name"]
    df["is_active"] = payment_methods["is_active"]
    df["start_date"] = pd.Timestamp("2024-01-01").date()
    df["end_date"] = pd.NaT
    df["is_current"] = True

    df.reset_index(drop=True, inplace=True)
    df.index += 1
    df["payment_method_key"] = df.index
    df = df[[
        "payment_method_key", "payment_method_id", "payment_method_name",
        "is_active", "start_date", "end_date", "is_current"
    ]]

    print("dim_payment_method built:", len(df), "rows")
    return df


def build_dim_product(products):
    """Build product dimension (SCD Type 2)."""
    df = pd.DataFrame()
    df["product_id"] = products["product_id"]
    df["product_name"] = products["product_name"]
    df["purchase_price"] = products["purchase_price"]
    df["sale_price"] = products["sale_price"]
    df["brand_id"] = products["brand_id"]
    df["category_id"] = products["category_id"]
    df["start_date"] = pd.Timestamp("2024-01-01").date()
    df["end_date"] = pd.NaT
    df["is_current"] = True

    df.reset_index(drop=True, inplace=True)
    df.index += 1
    df["product_key"] = df.index
    df = df[[
        "product_key", "product_id", "product_name", "brand_id", "category_id",
        "purchase_price", "sale_price", "start_date", "end_date", "is_current"
    ]]

    print("dim_product built:", len(df), "rows")
    return df


def build_dim_status(orders):
    """Build status dimension from unique order statuses."""
    unique = orders["status"].dropna().unique()
    df = pd.DataFrame({"status_name": sorted(unique)})

    completed = {"paid", "shipped", "delivered"}
    cancelled = {"cancelled"}
    pending = {"pending"}

    def map_category(name):
        if name in completed:
            return "Completed"
        elif name in cancelled:
            return "Cancelled"
        elif name in pending:
            return "Pending"
        return "Other"

    df["status_category"] = df["status_name"].apply(map_category)
    df.reset_index(drop=True, inplace=True)
    df.index += 1
    df["status_key"] = df.index
    df["status_id"] = df["status_key"]
    df = df[["status_key", "status_id", "status_name", "status_category"]]

    print("dim_status built:", len(df), "rows")
    return df


def build_all_dimensions():
    """Extract and build all 10 dimension tables."""
    data = extract_all()

    dim_date = build_dim_date()
    dim_time = build_dim_time()
    dim_currency = build_dim_currency(data["currencies"])
    dim_brand = build_dim_brand(data["brands"])
    dim_category = build_dim_category(data["categories"])
    dim_branch = build_dim_branch(data["branches"])
    dim_user = build_dim_user(data["users"], dim_currency)
    dim_payment_method = build_dim_payment_method(data["payment_methods"])
    dim_product = build_dim_product(data["products"])
    dim_status = build_dim_status(data["orders"])

    return {
        "dim_date": dim_date,
        "dim_time": dim_time,
        "dim_currency": dim_currency,
        "dim_brand": dim_brand,
        "dim_category": dim_category,
        "dim_branch": dim_branch,
        "dim_user": dim_user,
        "dim_payment_method": dim_payment_method,
        "dim_product": dim_product,
        "dim_status": dim_status,
        "_raw": data,
    }