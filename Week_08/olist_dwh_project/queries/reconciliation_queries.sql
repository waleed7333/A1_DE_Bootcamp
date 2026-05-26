-- =============================================================================
-- OLIST DATA WAREHOUSE - RECONCILIATION QUERIES
-- =============================================================================
-- These queries compare source (olist_oltp) vs target (olist_olap) to validate
-- the ETL pipeline. Run each pair and verify results match.
-- =============================================================================

-- =============================================================================
-- CHECK 1: Total Orders Count
-- =============================================================================
-- Source (OLTP):
SELECT COUNT(*) AS total_orders FROM orders;
-- Expected: 99,441

-- Target (OLAP):
SELECT COUNT(DISTINCT order_id) AS total_orders FROM facts.fact_sales;
-- Expected: Must match source (excludes orders without items)


-- =============================================================================
-- CHECK 2: Total Order Items Count
-- =============================================================================
-- Source (OLTP):
SELECT COUNT(*) AS total_items FROM order_items;
-- Expected: 112,650

-- Target (OLAP):
SELECT COUNT(*) AS total_items FROM facts.fact_sales;
-- Expected: 112,650


-- =============================================================================
-- CHECK 3: Total Customers
-- =============================================================================
-- Source (OLTP):
SELECT COUNT(*) AS total_customers FROM customers;
-- Expected: 99,441

-- Target (OLAP):
SELECT COUNT(*) AS total_customers FROM dimensions.dim_customer;
-- Expected: 99,441


-- =============================================================================
-- CHECK 4: Total Sellers
-- =============================================================================
-- Source (OLTP):
SELECT COUNT(*) AS total_sellers FROM sellers;
-- Expected: 3,095

-- Target (OLAP):
SELECT COUNT(*) AS total_sellers FROM dimensions.dim_seller;
-- Expected: 3,095


-- =============================================================================
-- CHECK 5: Total Products
-- =============================================================================
-- Source (OLTP):
SELECT COUNT(*) AS total_products FROM products;
-- Expected: 32,951

-- Target (OLAP):
SELECT COUNT(*) AS total_products FROM dimensions.dim_product;
-- Expected: 32,951


-- =============================================================================
-- CHECK 6: Total Reviews
-- =============================================================================
-- Source (OLTP):
SELECT COUNT(*) AS total_reviews FROM order_reviews;
-- Expected: 99,224

-- Target (OLAP):
SELECT COUNT(*) AS total_reviews FROM facts.fact_reviews;
-- Expected: 99,224


-- =============================================================================
-- CHECK 7: Total Revenue
-- =============================================================================
-- Source (OLTP):
SELECT ROUND(SUM(price)::numeric, 2) AS total_revenue FROM order_items;

-- Target (OLAP):
SELECT ROUND(SUM(item_total)::numeric, 2) AS total_revenue FROM facts.fact_sales;
-- Both should return approximately 13,595,200


-- =============================================================================
-- CHECK 8: Total Shipping Value
-- =============================================================================
-- Source (OLTP):
SELECT ROUND(SUM(freight_value)::numeric, 2) AS total_shipping FROM order_items;

-- Target (OLAP):
SELECT ROUND(SUM(shipping_value)::numeric, 2) AS total_shipping FROM facts.fact_sales;
-- Both should return identical values


-- =============================================================================
-- CHECK 9: Total Payment Value
-- =============================================================================
-- Source (OLTP):
SELECT ROUND(SUM(payment_value)::numeric, 2) AS total_payments FROM order_payments;

-- Target (OLAP):
SELECT ROUND(SUM(payment_value)::numeric, 2) AS total_payments FROM facts.fact_payments;
-- Both should return identical values


-- =============================================================================
-- CHECK 10: Average Review Score
-- =============================================================================
-- Source (OLTP):
SELECT ROUND(AVG(review_score)::numeric, 4) AS avg_score FROM order_reviews;

-- Target (OLAP):
SELECT ROUND(AVG(review_score)::numeric, 4) AS avg_score FROM facts.fact_reviews;
-- Both should return identical values


-- =============================================================================
-- CHECK 11: Orders by Status
-- =============================================================================
-- Source (OLTP):
SELECT order_status, COUNT(*) AS cnt FROM orders GROUP BY order_status ORDER BY order_status;

-- Target (OLAP):
SELECT os.order_status, COUNT(DISTINCT s.order_id) AS cnt
FROM facts.fact_sales s
JOIN dimensions.dim_order_status os ON s.order_status_key = os.order_status_key
GROUP BY os.order_status ORDER BY os.order_status;
-- Distributions should match


-- =============================================================================
-- CHECK 12: Payments by Type
-- =============================================================================
-- Source (OLTP):
SELECT payment_type, COUNT(*) AS cnt FROM order_payments GROUP BY payment_type ORDER BY payment_type;

-- Target (OLAP):
SELECT pt.payment_type, COUNT(*) AS cnt
FROM facts.fact_payments p
JOIN dimensions.dim_payment_type pt ON p.payment_type_key = pt.payment_type_key
GROUP BY pt.payment_type ORDER BY pt.payment_type;
-- Distributions should match


-- =============================================================================
-- CHECK 13: Total Qualified Leads
-- =============================================================================
-- Source (OLTP):
SELECT COUNT(*) AS total_leads FROM leads_qualified;
-- Expected: 8,000

-- Target (OLAP):
SELECT COUNT(*) AS total_leads FROM facts.fact_seller_acquisition;
-- Expected: 8,000


-- =============================================================================
-- CHECK 14: Total Closed/Won Leads
-- =============================================================================
-- Source (OLTP):
SELECT COUNT(*) AS converted_leads FROM leads_closed;
-- Expected: ~842

-- Target (OLAP):
SELECT COUNT(*) AS converted_leads FROM facts.fact_seller_acquisition WHERE conversion_flag = TRUE;
-- Expected: ~842


-- =============================================================================
-- CHECK 15: Order Events - Purchased
-- =============================================================================
-- Source (OLTP):
SELECT COUNT(*) AS purchased FROM orders WHERE order_purchase_timestamp IS NOT NULL;
-- Expected: 99,441

-- Target (OLAP):
SELECT COUNT(DISTINCT order_id) AS purchased FROM facts.fact_order_events WHERE event_type_key = 1;
-- Expected: 99,441


-- =============================================================================
-- CHECK 16: Order Events - Delivered
-- =============================================================================
-- Source (OLTP):
SELECT COUNT(*) AS delivered FROM orders WHERE order_delivered_customer_date IS NOT NULL;
-- Expected: ~96,476

-- Target (OLAP):
SELECT COUNT(DISTINCT order_id) AS delivered FROM facts.fact_order_events WHERE event_type_key = 4;
-- Expected: ~96,476


-- =============================================================================
-- CHECK 17: Earliest and Latest Purchase Dates
-- =============================================================================
-- Source (OLTP):
SELECT MIN(DATE(order_purchase_timestamp)) AS min_date, MAX(DATE(order_purchase_timestamp)) AS max_date FROM orders;

-- Target (OLAP):
SELECT MIN(d.full_date) AS min_date, MAX(d.full_date) AS max_date
FROM facts.fact_sales s
JOIN dimensions.dim_date d ON s.purchase_date_key = d.date_key;
-- Both should return identical date ranges


-- =============================================================================
-- CHECK 18: Delivery Delay Summary
-- =============================================================================
-- Source (OLTP):
SELECT 
    COUNT(*) AS total_delivered,
    COUNT(CASE WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 1 END) AS late_orders,
    COUNT(CASE WHEN order_delivered_customer_date <= order_estimated_delivery_date THEN 1 END) AS on_time_orders
FROM orders
WHERE order_delivered_customer_date IS NOT NULL AND order_estimated_delivery_date IS NOT NULL;

-- Target (OLAP):
SELECT 
    COUNT(*) AS total_delivered,
    COUNT(CASE WHEN delivery_delay_days > 0 THEN 1 END) AS late_orders,
    COUNT(CASE WHEN delivery_delay_days <= 0 THEN 1 END) AS on_time_orders
FROM facts.fact_sales
WHERE delivery_delay_days IS NOT NULL;
-- Counts should match (with grain consideration: use COUNT DISTINCT order_id for OLAP)