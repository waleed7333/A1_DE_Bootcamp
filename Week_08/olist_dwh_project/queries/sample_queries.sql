-- =============================================================================
-- OLIST DATA WAREHOUSE - SAMPLE ANALYTICAL QUERIES
-- =============================================================================
-- These queries demonstrate the analytical capabilities of the star schema.
-- Each query answers a specific business question.
-- =============================================================================

-- =============================================================================
-- Q1: How are sales trending over time?
-- =============================================================================
-- Monthly revenue trend with year-over-year comparison
SELECT 
    d.year,
    d.month,
    d.month_name,
    COUNT(DISTINCT s.order_id) AS total_orders,
    ROUND(SUM(s.item_total)::numeric, 2) AS total_revenue,
    ROUND(AVG(s.item_total)::numeric, 2) AS avg_order_value,
    COUNT(DISTINCT s.customer_key) AS unique_customers
FROM facts.fact_sales s
JOIN dimensions.dim_date d ON s.purchase_date_key = d.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;


-- =============================================================================
-- Q2: Who are the most valuable customers?
-- =============================================================================
-- Top 10 customers by lifetime value with order frequency
SELECT 
    c.customer_unique_id,
    COUNT(DISTINCT s.order_id) AS total_orders,
    ROUND(SUM(s.item_total)::numeric, 2) AS lifetime_value,
    ROUND(AVG(s.item_total)::numeric, 2) AS avg_order_value,
    MIN(d.full_date) AS first_purchase,
    MAX(d.full_date) AS last_purchase
FROM facts.fact_sales s
JOIN dimensions.dim_customer c ON s.customer_key = c.customer_key
JOIN dimensions.dim_date d ON s.purchase_date_key = d.date_key
GROUP BY c.customer_unique_id
ORDER BY lifetime_value DESC
LIMIT 10;


-- =============================================================================
-- Q3: What affects delivery performance?
-- =============================================================================
-- Delivery delay by customer state and region
SELECT 
    loc.region,
    loc.state,
    COUNT(DISTINCT s.order_id) AS total_deliveries,
    ROUND(AVG(s.delivery_delay_days)::numeric, 1) AS avg_delay_days,
    ROUND(100.0 * COUNT(CASE WHEN s.delivery_delay_days > 0 THEN 1 END) / COUNT(*), 1) AS late_delivery_pct,
    ROUND(MAX(s.delivery_delay_days)::numeric, 0) AS max_delay_days
FROM facts.fact_sales s
JOIN dimensions.dim_location loc ON s.customer_location_key = loc.location_key
WHERE s.delivered_customer_date_key IS NOT NULL
  AND s.estimated_delivery_date_key IS NOT NULL
GROUP BY loc.region, loc.state
ORDER BY avg_delay_days DESC;


-- =============================================================================
-- Q4: Which products/categories drive revenue?
-- =============================================================================
-- Top 10 product categories by revenue with review scores
SELECT 
    p.product_category_name_english AS category,
    COUNT(DISTINCT s.product_key) AS unique_products,
    COUNT(DISTINCT s.order_id) AS total_orders,
    ROUND(SUM(s.item_total)::numeric, 2) AS total_revenue,
    ROUND(AVG(s.unit_price)::numeric, 2) AS avg_unit_price,
    ROUND(AVG(r.review_score)::numeric, 2) AS avg_review_score
FROM facts.fact_sales s
JOIN dimensions.dim_product p ON s.product_key = p.product_key
LEFT JOIN facts.fact_reviews r ON s.order_id = r.order_id
GROUP BY p.product_category_name_english
ORDER BY total_revenue DESC
LIMIT 10;


-- =============================================================================
-- Q5: Payment behavior analysis
-- =============================================================================
-- How payment method and installments affect order value
SELECT 
    pt.payment_type,
    CASE 
        WHEN p.payment_installments = 1 THEN 'Single Payment'
        WHEN p.payment_installments BETWEEN 2 AND 4 THEN '2-4 Installments'
        WHEN p.payment_installments BETWEEN 5 AND 8 THEN '5-8 Installments'
        ELSE '9+ Installments'
    END AS installment_group,
    COUNT(DISTINCT p.order_id) AS order_count,
    ROUND(AVG(p.payment_value)::numeric, 2) AS avg_payment_value,
    ROUND(SUM(p.payment_value)::numeric, 2) AS total_paid
FROM facts.fact_payments p
JOIN dimensions.dim_payment_type pt ON p.payment_type_key = pt.payment_type_key
GROUP BY pt.payment_type, installment_group
ORDER BY pt.payment_type, MIN(p.payment_installments);


-- =============================================================================
-- Q6: Order lifecycle funnel analysis
-- =============================================================================
-- Conversion rates through each stage of the order lifecycle
SELECT 
    et.event_type_name,
    COUNT(DISTINCT f.order_id) AS order_count,
    ROUND(
        100.0 * COUNT(DISTINCT f.order_id) / 
        FIRST_VALUE(COUNT(DISTINCT f.order_id)) OVER (ORDER BY et.event_type_key),
        1
    ) AS conversion_rate_pct
FROM facts.fact_order_events f
JOIN dimensions.dim_event_type et ON f.event_type_key = et.event_type_key
GROUP BY et.event_type_key, et.event_type_name
ORDER BY et.event_type_key;


-- =============================================================================
-- Q7: Seller acquisition funnel by marketing channel
-- =============================================================================
-- Which marketing channels bring the best-converting sellers?
SELECT 
    ls.origin AS marketing_channel,
    COUNT(*) AS total_leads,
    COUNT(CASE WHEN fa.conversion_flag THEN 1 END) AS converted_leads,
    ROUND(100.0 * COUNT(CASE WHEN fa.conversion_flag THEN 1 END) / COUNT(*), 1) AS conversion_rate_pct,
    ROUND(AVG(fa.conversion_days)::numeric, 1) AS avg_days_to_convert,
    ROUND(AVG(COALESCE(fa.declared_monthly_revenue, 0))::numeric, 2) AS avg_declared_revenue
FROM facts.fact_seller_acquisition fa
JOIN dimensions.dim_lead_source ls ON fa.lead_source_key = ls.lead_source_key
GROUP BY ls.origin
ORDER BY conversion_rate_pct DESC;


-- =============================================================================
-- Q8: Daily sales with weekend vs weekday comparison
-- =============================================================================
SELECT 
    d.day_name,
    d.is_weekend,
    COUNT(DISTINCT s.order_id) AS total_orders,
    ROUND(AVG(s.item_total)::numeric, 2) AS avg_order_value,
    ROUND(SUM(s.item_total)::numeric, 2) AS total_revenue
FROM facts.fact_sales s
JOIN dimensions.dim_date d ON s.purchase_date_key = d.date_key
GROUP BY d.day_of_week, d.day_name, d.is_weekend
ORDER BY d.day_of_week;


-- =============================================================================
-- Q9: Customer satisfaction by delivery performance
-- =============================================================================
-- How delivery delay impacts review scores
SELECT 
    CASE 
        WHEN s.delivery_delay_days <= -3 THEN '3+ days early'
        WHEN s.delivery_delay_days < 0 THEN '1-2 days early'
        WHEN s.delivery_delay_days = 0 THEN 'On time'
        WHEN s.delivery_delay_days BETWEEN 1 AND 5 THEN '1-5 days late'
        WHEN s.delivery_delay_days BETWEEN 6 AND 10 THEN '6-10 days late'
        ELSE '10+ days late'
    END AS delivery_performance,
    COUNT(DISTINCT s.order_id) AS order_count,
    ROUND(AVG(r.review_score)::numeric, 2) AS avg_review_score,
    ROUND(100.0 * COUNT(CASE WHEN r.is_negative THEN 1 END) / COUNT(r.review_key), 1) AS negative_review_pct
FROM facts.fact_sales s
JOIN facts.fact_reviews r ON s.order_id = r.order_id
WHERE s.delivered_customer_date_key IS NOT NULL
GROUP BY delivery_performance
ORDER BY MIN(s.delivery_delay_days);


-- =============================================================================
-- Q10: Top performing sellers
-- =============================================================================
-- Sellers with highest revenue and best ratings
SELECT 
    sel.seller_id,
    loc.city AS seller_city,
    loc.state AS seller_state,
    COUNT(DISTINCT s.order_id) AS total_orders,
    ROUND(SUM(s.item_total)::numeric, 2) AS total_revenue,
    ROUND(AVG(r.review_score)::numeric, 2) AS avg_rating,
    ROUND(AVG(s.delivery_delay_days)::numeric, 1) AS avg_delivery_delay,
    COUNT(DISTINCT s.product_key) AS unique_products_sold
FROM facts.fact_sales s
JOIN dimensions.dim_seller sel ON s.seller_key = sel.seller_key
JOIN dimensions.dim_location loc ON s.seller_location_key = loc.location_key
LEFT JOIN facts.fact_reviews r ON s.order_id = r.order_id
GROUP BY sel.seller_id, loc.city, loc.state
HAVING COUNT(DISTINCT s.order_id) >= 10
ORDER BY total_revenue DESC
LIMIT 20;


-- =============================================================================
-- Q11: Revenue by Brazilian region
-- =============================================================================
SELECT 
    loc.region,
    COUNT(DISTINCT s.order_id) AS total_orders,
    ROUND(SUM(s.item_total)::numeric, 2) AS total_revenue,
    COUNT(DISTINCT s.customer_key) AS unique_customers,
    COUNT(DISTINCT s.seller_key) AS active_sellers,
    ROUND(AVG(s.item_total)::numeric, 2) AS avg_order_value
FROM facts.fact_sales s
JOIN dimensions.dim_location loc ON s.customer_location_key = loc.location_key
GROUP BY loc.region
ORDER BY total_revenue DESC;


-- =============================================================================
-- Q12: Monthly customer retention (repeat purchase rate)
-- =============================================================================
WITH customer_first_purchase AS (
    SELECT 
        customer_key,
        MIN(purchase_date_key) AS first_purchase_date_key
    FROM facts.fact_sales
    GROUP BY customer_key
)
SELECT 
    d.year,
    d.month,
    d.month_name,
    COUNT(DISTINCT s.customer_key) AS total_customers,
    COUNT(DISTINCT CASE 
        WHEN s.purchase_date_key > cfp.first_purchase_date_key 
        THEN s.customer_key 
    END) AS repeat_customers,
    ROUND(100.0 * COUNT(DISTINCT CASE 
        WHEN s.purchase_date_key > cfp.first_purchase_date_key 
        THEN s.customer_key 
    END) / COUNT(DISTINCT s.customer_key), 1) AS repeat_rate_pct
FROM facts.fact_sales s
JOIN customer_first_purchase cfp ON s.customer_key = cfp.customer_key
JOIN dimensions.dim_date d ON s.purchase_date_key = d.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;