"""
All indexes for the ecommerce_olap data warehouse.
Contains basic indexes (auto-applied) and advanced indexes (optional).
"""
from sqlalchemy import text
from config import olap_engine


def create_basic_indexes():
    """
    Create essential indexes for normal Star Schema operation.
    These run automatically on every load.
    """
    
    basic_indexes = [
        # === fct_order_transaction: Foreign Key Indexes ===
        "CREATE INDEX IF NOT EXISTS idx_fact_date ON fct_order_transaction USING BRIN (date_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_product ON fct_order_transaction (product_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_brand ON fct_order_transaction (brand_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_category ON fct_order_transaction (category_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_user ON fct_order_transaction (user_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_branch ON fct_order_transaction (branch_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_currency ON fct_order_transaction (currency_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_payment ON fct_order_transaction (payment_method_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_status ON fct_order_transaction (status_key);",
        
        # === fct_order_transaction: Composite Indexes ===
        "CREATE INDEX IF NOT EXISTS idx_fact_date_product ON fct_order_transaction (date_key, product_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_date_profit ON fct_order_transaction (date_key, profit);",
        
        # === dim_product: SCD Type 2 Lookups ===
        "CREATE INDEX IF NOT EXISTS idx_dim_product_current ON dim_product (is_current) WHERE is_current = TRUE;",
        "CREATE INDEX IF NOT EXISTS idx_dim_product_dates ON dim_product (start_date, end_date);",
        
        # === dim_user: SCD Type 2 Lookups ===
        "CREATE INDEX IF NOT EXISTS idx_dim_user_current ON dim_user (is_current) WHERE is_current = TRUE;",
        
        # === dim_payment_method: SCD Type 2 Lookups ===
        "CREATE INDEX IF NOT EXISTS idx_dim_payment_current ON dim_payment_method (is_current) WHERE is_current = TRUE;",
        
        # === dim_date: Common Filters ===
        "CREATE INDEX IF NOT EXISTS idx_dim_date_year ON dim_date (year);",
        "CREATE INDEX IF NOT EXISTS idx_dim_date_ramadan ON dim_date (is_ramadan) WHERE is_ramadan = TRUE;",
        "CREATE INDEX IF NOT EXISTS idx_dim_date_holiday ON dim_date (is_holiday) WHERE is_holiday = TRUE;",
        "CREATE INDEX IF NOT EXISTS idx_dim_date_weekend ON dim_date (is_weekend) WHERE is_weekend = TRUE;",
        "CREATE INDEX IF NOT EXISTS idx_dim_date_month_end ON dim_date (is_month_end) WHERE is_month_end = TRUE;",
        
        # === dim_time: Common Filters ===
        "CREATE INDEX IF NOT EXISTS idx_dim_time_daytime ON dim_time (daytime_name);",
        "CREATE INDEX IF NOT EXISTS idx_dim_time_daynight ON dim_time (day_night);",
        
        # === dim_status: Common Filters ===
        "CREATE INDEX IF NOT EXISTS idx_dim_status_category ON dim_status (status_category);",
    ]
    
    with olap_engine.connect() as conn:
        for idx_sql in basic_indexes:
            try:
                conn.execute(text(idx_sql))
            except Exception as e:
                print(f"Warning: {e}")
        conn.commit()
    
    print("Basic indexes created successfully.")


def create_advanced_indexes():
    """
    Create advanced performance indexes.
    
    ⚠️ UNCOMMENT THE LINES BELOW IF YOU NEED THESE INDEXES:
    - Covering indexes consume more disk space but speed up specific queries.
    - Partial indexes are smaller but only work for filtered queries.
    - Use them only if you notice slow query performance on specific reports.
    """
    
    advanced_indexes = [
        # --- Covering index for date-based sales reports ---
        # "CREATE INDEX IF NOT EXISTS idx_fact_date_sales ON fct_order_transaction (date_key, sales_amount, profit);",
        
        # --- Covering index for product performance reports ---
        # "CREATE INDEX IF NOT EXISTS idx_fact_product_sales ON fct_order_transaction (product_key, date_key, sales_amount);",
        
        # --- Covering index for customer analysis ---
        # "CREATE INDEX IF NOT EXISTS idx_fact_user_sales ON fct_order_transaction (user_key, date_key, sales_amount);",
        
        # --- Partial index: completed orders only ---
        # "CREATE INDEX IF NOT EXISTS idx_fact_completed ON fct_order_transaction (date_key, sales_amount) WHERE status_key IN (1, 2, 3);",
        
        # --- Partial index: high-value transactions ---
        # "CREATE INDEX IF NOT EXISTS idx_fact_high_value ON fct_order_transaction (date_key, sales_amount) WHERE sales_amount > 1000;",
    ]
    
    executed = 0
    with olap_engine.connect() as conn:
        for idx_sql in advanced_indexes:
            stripped = idx_sql.strip()
            if stripped and not stripped.startswith("--"):
                try:
                    conn.execute(text(idx_sql))
                    executed += 1
                except Exception as e:
                    print(f"Warning: {e}")
        conn.commit()
    
    if executed > 0:
        print(f"Advanced indexes created: {executed}")
    else:
        print("No advanced indexes executed. Uncomment lines in create_indexes.py to enable.")


def create_all_indexes():
    """Create all indexes. Basic run automatically. Advanced are optional."""
    create_basic_indexes()
    create_advanced_indexes()


if __name__ == "__main__":
    create_all_indexes()