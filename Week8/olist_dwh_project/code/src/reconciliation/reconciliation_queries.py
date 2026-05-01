# src/reconciliation/reconciliation_queries.py
# Reconciliation query definitions
# Each check is a dictionary with: name, oltp_query, olap_query, compare_cols
# To add a new check: append a new dictionary to RECONCILIATION_CHECKS list

RECONCILIATION_CHECKS = [

    # =====================================================================
    # CATEGORY A: ROW COUNTS
    # =====================================================================
    {
        "category": "A - Row Counts",
        "name": "Total Orders Count",
        "oltp_query": "SELECT COUNT(DISTINCT oi.order_id) AS cnt FROM order_items oi",
        "olap_query": "SELECT COUNT(DISTINCT order_id) AS cnt FROM facts.fact_sales",
        "compare_cols": ["cnt"],
    },
    {
        "category": "A - Row Counts",
        "name": "Total Order Items Count",
        "oltp_query": "SELECT COUNT(*) AS cnt FROM order_items",
        "olap_query": "SELECT COUNT(*) AS cnt FROM facts.fact_sales",
        "compare_cols": ["cnt"],
    },
    {
        "category": "A - Row Counts",
        "name": "Total Customers Count",
        "oltp_query": "SELECT COUNT(*) AS cnt FROM customers",
        "olap_query": "SELECT COUNT(*) AS cnt FROM dimensions.dim_customer",
        "compare_cols": ["cnt"],
    },
    {
        "category": "A - Row Counts",
        "name": "Total Sellers Count",
        "oltp_query": "SELECT COUNT(*) AS cnt FROM sellers",
        "olap_query": "SELECT COUNT(*) AS cnt FROM dimensions.dim_seller",
        "compare_cols": ["cnt"],
    },
    {
        "category": "A - Row Counts",
        "name": "Total Products Count",
        "oltp_query": "SELECT COUNT(*) AS cnt FROM products",
        "olap_query": "SELECT COUNT(*) AS cnt FROM dimensions.dim_product",
        "compare_cols": ["cnt"],
    },
    {
        "category": "A - Row Counts",
        "name": "Total Reviews Count",
        "oltp_query": "SELECT COUNT(*) AS cnt FROM order_reviews",
        "olap_query": "SELECT COUNT(*) AS cnt FROM facts.fact_reviews",
        "compare_cols": ["cnt"],
    },

    # =====================================================================
    # CATEGORY B: FINANCIAL METRICS
    # =====================================================================
    {
        "category": "B - Financial Metrics",
        "name": "Total Revenue (All Items)",
        "oltp_query": "SELECT ROUND(SUM(price)::numeric, 2) AS total FROM order_items",
        "olap_query": "SELECT ROUND(SUM(item_total)::numeric, 2) AS total FROM facts.fact_sales",
        "compare_cols": ["total"],
    },
    {
        "category": "B - Financial Metrics",
        "name": "Total Freight/Shipping Value",
        "oltp_query": "SELECT ROUND(SUM(freight_value)::numeric, 2) AS total FROM order_items",
        "olap_query": "SELECT ROUND(SUM(shipping_value)::numeric, 2) AS total FROM facts.fact_sales",
        "compare_cols": ["total"],
    },
    {
        "category": "B - Financial Metrics",
        "name": "Average Item Price",
        "oltp_query": "SELECT ROUND(AVG(price)::numeric, 4) AS avg FROM order_items",
        "olap_query": "SELECT ROUND(AVG(unit_price)::numeric, 4) AS avg FROM facts.fact_sales",
        "compare_cols": ["avg"],
    },
    {
        "category": "B - Financial Metrics",
        "name": "Total Payment Value",
        "oltp_query": "SELECT ROUND(SUM(payment_value)::numeric, 2) AS total FROM order_payments",
        "olap_query": "SELECT ROUND(SUM(payment_value)::numeric, 2) AS total FROM facts.fact_payments",
        "compare_cols": ["total"],
    },
    {
        "category": "B - Financial Metrics",
        "name": "Payments Row Count",
        "oltp_query": "SELECT COUNT(*) AS cnt FROM order_payments",
        "olap_query": "SELECT COUNT(*) AS cnt FROM facts.fact_payments",
        "compare_cols": ["cnt"],
    },

    # =====================================================================
    # CATEGORY C: ORDER STATUS DISTRIBUTION
    # =====================================================================
    {
        "category": "C - Order Status",
        "name": "Orders by Status Distribution",
        "oltp_query": """
            SELECT o.order_status, COUNT(DISTINCT oi.order_id) AS cnt
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            GROUP BY o.order_status
            ORDER BY o.order_status
        """,
        "olap_query": """
            SELECT os.order_status, COUNT(DISTINCT s.order_id) AS cnt
            FROM facts.fact_sales s
            JOIN dimensions.dim_order_status os ON s.order_status_key = os.order_status_key
            GROUP BY os.order_status
            ORDER BY os.order_status
        """,
        "compare_cols": ["cnt"],
    },

    # =====================================================================
    # CATEGORY D: PAYMENT TYPE DISTRIBUTION
    # =====================================================================
    {
        "category": "D - Payment Types",
        "name": "Payments by Type Distribution",
        "oltp_query": """
            SELECT payment_type, COUNT(*) AS cnt
            FROM order_payments
            GROUP BY payment_type
            ORDER BY payment_type
        """,
        "olap_query": """
            SELECT pt.payment_type, COUNT(*) AS cnt
            FROM facts.fact_payments p
            JOIN dimensions.dim_payment_type pt ON p.payment_type_key = pt.payment_type_key
            GROUP BY pt.payment_type
            ORDER BY pt.payment_type
        """,
        "compare_cols": ["cnt"],
    },

    # =====================================================================
    # CATEGORY E: REVIEW SCORE DISTRIBUTION
    # =====================================================================
    {
        "category": "E - Review Scores",
        "name": "Reviews by Score Distribution",
        "oltp_query": """
            SELECT review_score, COUNT(*) AS cnt
            FROM order_reviews
            GROUP BY review_score
            ORDER BY review_score
        """,
        "olap_query": """
            SELECT review_score, COUNT(*) AS cnt
            FROM facts.fact_reviews
            GROUP BY review_score
            ORDER BY review_score
        """,
        "compare_cols": ["cnt"],
    },

    # =====================================================================
    # CATEGORY F: REVIEW METRICS
    # =====================================================================
    {
        "category": "F - Review Metrics",
        "name": "Average Review Score",
        "oltp_query": "SELECT ROUND(AVG(review_score)::numeric, 4) AS avg FROM order_reviews",
        "olap_query": "SELECT ROUND(AVG(review_score)::numeric, 4) AS avg FROM facts.fact_reviews",
        "compare_cols": ["avg"],
    },
    {
        "category": "F - Review Metrics",
        "name": "Positive Review Count (Score >= 4)",
        "oltp_query": "SELECT COUNT(*) AS cnt FROM order_reviews WHERE review_score >= 4",
        "olap_query": "SELECT COUNT(*) AS cnt FROM facts.fact_reviews WHERE is_positive = TRUE",
        "compare_cols": ["cnt"],
    },
    {
        "category": "F - Review Metrics",
        "name": "Negative Review Count (Score <= 2)",
        "oltp_query": "SELECT COUNT(*) AS cnt FROM order_reviews WHERE review_score <= 2",
        "olap_query": "SELECT COUNT(*) AS cnt FROM facts.fact_reviews WHERE is_negative = TRUE",
        "compare_cols": ["cnt"],
    },

    # =====================================================================
    # CATEGORY G: REVENUE BY CATEGORY
    # =====================================================================
    {
        "category": "G - Revenue by Category",
        "name": "Revenue by Category (All Categories)",
        "oltp_query": """
            SELECT
                COALESCE(pct.product_category_name_english, p.product_category_name) AS category,
                ROUND(SUM(oi.price)::numeric, 2) AS total_revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            LEFT JOIN product_category_name_translation pct
                ON p.product_category_name = pct.product_category_name
            GROUP BY COALESCE(pct.product_category_name_english, p.product_category_name)
            ORDER BY total_revenue DESC
        """,
        "olap_query": """
            SELECT
                p.product_category_name_english AS category,
                ROUND(SUM(s.item_total)::numeric, 2) AS total_revenue
            FROM facts.fact_sales s
            JOIN dimensions.dim_product p ON s.product_key = p.product_key
            GROUP BY p.product_category_name_english
            ORDER BY total_revenue DESC
        """,
        "compare_cols": ["total_revenue"],
    },

    # =====================================================================
    # CATEGORY H: SELLER ACQUISITION / LEADS
    # =====================================================================
    {
        "category": "H - Seller Acquisition",
        "name": "Total Qualified Leads",
        "oltp_query": "SELECT COUNT(*) AS cnt FROM leads_qualified",
        "olap_query": "SELECT COUNT(*) AS cnt FROM facts.fact_seller_acquisition",
        "compare_cols": ["cnt"],
    },
    {
        "category": "H - Seller Acquisition",
        "name": "Total Closed/Won Leads",
        "oltp_query": "SELECT COUNT(*) AS cnt FROM leads_closed",
        "olap_query": "SELECT COUNT(*) AS cnt FROM facts.fact_seller_acquisition WHERE conversion_flag = TRUE",
        "compare_cols": ["cnt"],
    },
    {
        "category": "H - Seller Acquisition",
        "name": "Leads by Source Distribution",
        "oltp_query": """
            SELECT COALESCE(lq.origin, 'unknown') AS origin, COUNT(*) AS cnt
            FROM leads_qualified lq
            GROUP BY COALESCE(lq.origin, 'unknown')
            ORDER BY COALESCE(lq.origin, 'unknown')
        """,
        "olap_query": """
            SELECT ls.origin, COUNT(*) AS cnt
            FROM facts.fact_seller_acquisition fa
            JOIN dimensions.dim_lead_source ls ON fa.lead_source_key = ls.lead_source_key
            GROUP BY ls.origin
            ORDER BY ls.origin
        """,
        "compare_cols": ["cnt"],
    },
    {
        "category": "H - Seller Acquisition",
        "name": "Leads by Business Segment",
        "oltp_query": """
            SELECT lc.business_segment, COUNT(*) AS cnt
            FROM leads_closed lc
            WHERE lc.business_segment IS NOT NULL
            GROUP BY lc.business_segment
            ORDER BY lc.business_segment
        """,
        "olap_query": """
            SELECT dl.business_segment, COUNT(*) AS cnt
            FROM facts.fact_seller_acquisition fa
            JOIN dimensions.dim_lead dl ON fa.lead_key = dl.lead_key
            WHERE dl.business_segment IS NOT NULL
            GROUP BY dl.business_segment
            ORDER BY dl.business_segment
        """,
        "compare_cols": ["cnt"],
    },

    # =====================================================================
    # CATEGORY I: ORDER EVENTS
    # =====================================================================
    {
        "category": "I - Order Events",
        "name": "Order Events: Purchased Count",
        "oltp_query": """
            SELECT COUNT(*) AS cnt FROM orders
            WHERE order_purchase_timestamp IS NOT NULL
        """,
        "olap_query": """
            SELECT COUNT(DISTINCT order_id) AS cnt
            FROM facts.fact_order_events
            WHERE event_type_key = 1
        """,
        "compare_cols": ["cnt"],
    },
    {
        "category": "I - Order Events",
        "name": "Order Events: Delivered Count",
        "oltp_query": """
            SELECT COUNT(*) AS cnt FROM orders
            WHERE order_delivered_customer_date IS NOT NULL
        """,
        "olap_query": """
            SELECT COUNT(DISTINCT order_id) AS cnt
            FROM facts.fact_order_events
            WHERE event_type_key = 4
        """,
        "compare_cols": ["cnt"],
    },
    {
        "category": "I - Order Events",
        "name": "Order Events: Canceled Count",
        "oltp_query": """
            SELECT COUNT(*) AS cnt FROM orders
            WHERE order_status = 'canceled'
        """,
        "olap_query": """
            SELECT COUNT(DISTINCT order_id) AS cnt
            FROM facts.fact_order_events
            WHERE event_type_key = 5
        """,
        "compare_cols": ["cnt"],
    },

    # =====================================================================
    # CATEGORY J: GEOGRAPHIC VALIDATION
    # =====================================================================
    {
        "category": "J - Geographic",
        "name": "Unique Cities in Customer Dimension",
        "oltp_query": """
            SELECT COUNT(DISTINCT LOWER(TRIM(customer_city))) AS cnt FROM customers
        """,
        "olap_query": """
            SELECT COUNT(DISTINCT city) AS cnt FROM dimensions.dim_customer
        """,
        "compare_cols": ["cnt"],
    },
    {
        "category": "J - Geographic",
        "name": "Unique States in Customer Dimension",
        "oltp_query": """
            SELECT COUNT(DISTINCT UPPER(TRIM(customer_state))) AS cnt FROM customers
        """,
        "olap_query": """
            SELECT COUNT(DISTINCT state) AS cnt FROM dimensions.dim_customer
        """,
        "compare_cols": ["cnt"],
    },

    # =====================================================================
    # CATEGORY K: DATE COVERAGE
    # =====================================================================
    {
        "category": "K - Date Coverage",
        "name": "Earliest Purchase Date",
        "oltp_query": """
            SELECT MIN(DATE(order_purchase_timestamp)) AS min_date FROM orders
        """,
        "olap_query": """
            SELECT MIN(d.full_date) AS min_date
            FROM facts.fact_sales s
            JOIN dimensions.dim_date d ON s.purchase_date_key = d.date_key
        """,
        "compare_cols": ["min_date"],
    },
    {
        "category": "K - Date Coverage",
        "name": "Latest Purchase Date",
        "oltp_query": """
            SELECT MAX(DATE(order_purchase_timestamp)) AS max_date FROM orders
        """,
        "olap_query": """
            SELECT MAX(d.full_date) AS max_date
            FROM facts.fact_sales s
            JOIN dimensions.dim_date d ON s.purchase_date_key = d.date_key
        """,
        "compare_cols": ["max_date"],
    },
    {
        "category": "K - Date Coverage",
        "name": "Distinct Purchase Dates Count",
        "oltp_query": """
            SELECT COUNT(DISTINCT DATE(o.order_purchase_timestamp)) AS cnt
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
        """,
        "olap_query": """
            SELECT COUNT(DISTINCT purchase_date_key) AS cnt FROM facts.fact_sales
        """,
        "compare_cols": ["cnt"],
    },

    # =====================================================================
    # CATEGORY L: PRODUCT DATA
    # =====================================================================
    {
        "category": "L - Product Data",
        "name": "Products with English Category",
        "oltp_query": """
            SELECT COUNT(DISTINCT p.product_id) AS cnt
            FROM products p
            JOIN product_category_name_translation pct
                ON p.product_category_name = pct.product_category_name
        """,
        "olap_query": """
            SELECT COUNT(DISTINCT product_key) AS cnt
            FROM dimensions.dim_product
            WHERE product_category_name_english IS NOT NULL
        """,
        "compare_cols": ["cnt"],
    },
    {
        "category": "L - Product Data",
        "name": "Average Product Weight",
        "oltp_query": """
            SELECT ROUND(AVG(COALESCE(product_weight_g, 0))::numeric, 2) AS avg FROM products
        """,
        "olap_query": """
            SELECT ROUND(AVG(product_weight_g)::numeric, 2) AS avg FROM dimensions.dim_product
        """,
        "compare_cols": ["avg"],
    },

    # =====================================================================
    # CATEGORY M: PAYMENT INSTALLMENTS
    # =====================================================================
    {
        "category": "M - Payment Installments",
        "name": "Average Payment Installments",
        "oltp_query": """
            SELECT ROUND(AVG(COALESCE(payment_installments, 0))::numeric, 2) AS avg
            FROM order_payments
        """,
        "olap_query": """
            SELECT ROUND(AVG(payment_installments)::numeric, 2) AS avg
            FROM facts.fact_payments
        """,
        "compare_cols": ["avg"],
    },
    {
        "category": "M - Payment Installments",
        "name": "Max Payment Installments",
        "oltp_query": """
            SELECT MAX(COALESCE(payment_installments, 0)) AS max FROM order_payments
        """,
        "olap_query": """
            SELECT MAX(payment_installments) AS max FROM facts.fact_payments
        """,
        "compare_cols": ["max"],
    },

        # =====================================================================
    # CATEGORY N: DELIVERY METRICS
    # =====================================================================
    {
        "category": "N - Delivery Metrics",
        "name": "Orders with Delivery Delay > 0 Days",
        "oltp_query": """
            SELECT COUNT(DISTINCT order_id) AS cnt FROM orders
            WHERE order_delivered_customer_date IS NOT NULL
              AND order_estimated_delivery_date IS NOT NULL
              AND DATE(order_delivered_customer_date) > DATE(order_estimated_delivery_date)
        """,
        "olap_query": """
            SELECT COUNT(DISTINCT order_id) AS cnt FROM facts.fact_sales
            WHERE delivery_delay_days > 0
        """,
        "compare_cols": ["cnt"],
    },
    {
        "category": "N - Delivery Metrics",
        "name": "Orders Delivered On Time or Early",
        "oltp_query": """
            SELECT COUNT(DISTINCT order_id) AS cnt FROM orders
            WHERE order_delivered_customer_date IS NOT NULL
              AND order_estimated_delivery_date IS NOT NULL
              AND DATE(order_delivered_customer_date) <= DATE(order_estimated_delivery_date)
        """,
        "olap_query": """
            SELECT COUNT(DISTINCT order_id) AS cnt FROM facts.fact_sales
            WHERE delivery_delay_days <= 0
        """,
        "compare_cols": ["cnt"],
    },
    {
        "category": "N - Delivery Metrics",
        "name": "Average Delivery Delay Days",
        "oltp_query": """
            SELECT ROUND(AVG(delay)::numeric, 2) AS avg
            FROM (
                SELECT DISTINCT order_id,
                    (DATE(order_delivered_customer_date) - DATE(order_estimated_delivery_date)) AS delay
                FROM orders
                WHERE order_delivered_customer_date IS NOT NULL
                  AND order_estimated_delivery_date IS NOT NULL
            ) sub
        """,
        "olap_query": """
            SELECT ROUND(AVG(delay)::numeric, 2) AS avg
            FROM (
                SELECT DISTINCT order_id, delivery_delay_days AS delay
                FROM facts.fact_sales
                WHERE delivery_delay_days IS NOT NULL
            ) sub
        """,
        "compare_cols": ["avg"],
    },
]