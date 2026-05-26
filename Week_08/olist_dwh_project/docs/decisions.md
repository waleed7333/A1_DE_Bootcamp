# 🏛️ Architectural Decision Records (ADR)

## Overview

This document records all significant architectural decisions made during the design and implementation
of the Olist Data Warehouse. Each decision includes context, alternatives considered, final choice,
and consequences.

---

## ADR-001: Data Warehouse Architecture

### Status
✅ Accepted

### Context
We need to design a data warehouse that enables fast analytical queries for business users analyzing
e-commerce operations (sales, payments, reviews, seller acquisition, logistics).

### Decision
**Use Kimball Dimensional Modeling (Star Schema).**

### Alternatives Considered

| Alternative | Pros | Cons |
|:---|:---|:---|
| **Inmon (3NF)** | Better data integrity, no redundancy | Complex joins for every report, slower queries, harder for business users |
| **Wide Flat Tables** | Fastest single-table queries | Massive data duplication, impossible to maintain, inflexible |
| **Data Vault** | Excellent for audit and history | Overkill for this data volume, complex implementation |

### Rationale

1. **Query Performance:** Denormalized dimensions minimize JOIN operations. Typical analytical queries
   touch 1 fact table + 2-3 dimensions only.

2. **Business User Accessibility:** The star schema mental model (facts = events, dimensions = context)
   is intuitive for analysts and BI tools (Power BI, Tableau, Looker).

3. **Data Volume Appropriateness:** At ~1.5M source rows, the storage overhead of denormalization is
   negligible compared to the query speed benefits.

4. **OLIST Data Characteristics:** The data represents distinct business events (orders, payments,
   reviews) that map naturally to fact tables with surrounding dimensions.

### Consequences

| Positive | Negative |
|:---|:---|
| Fast analytical queries (fewer JOINs) | Some data redundancy in dimensions |
| BI tool friendly (drag-and-drop dimensions) | ETL must build surrogate keys |
| Easy for new analysts to understand | Schema changes require ETL updates |
| Scalable to larger data volumes | - |

---

## ADR-002: Multiple Fact Tables vs Single Fact Table

### Status
✅ Accepted

### Decision
**Use 5 separate fact tables, one per business process.**

### Context
The source system tracks multiple business processes: sales (order items), payments, reviews,
seller acquisition, and order lifecycle events. Each process has a different natural grain.

### Alternatives Considered

| Alternative | Pros | Cons |
|:---|:---|:---|
| **Single Merged Fact** | One table for all queries | Mixed grains cause double-counting; NULL columns everywhere; huge table |
| **Multiple Facts (Chosen)** | Correct grain per process; clean schema | Must JOIN facts for cross-process analysis |

### Grain Analysis

| Business Process | Natural Grain | Row Count | If Merged |
|:---|:---|:---:|:---|
| Sales | order_id + order_item_id | 112,650 | Reviews would explode to 112K rows |
| Payments | order_id + payment_sequential | 103,886 | Multi-payment orders duplicate sales data |
| Reviews | review_id | 99,224 | Multi-item orders get duplicate reviews |
| Seller Acquisition | mql_id | 8,000 | Would force NULL for all sales columns |
| Order Events | order_id + event_type | 393,481 | Would explode sales to 4x |

### Consequences

| Positive | Negative |
|:---|:---|
| Each fact has precisely correct grain | Cross-process analysis requires JOINs |
| No double-counting risk | 5 tables to maintain instead of 1 |
| Easy to add new business processes | - |
| Clean separation of concerns | - |

---

## ADR-003: Dedicated Dim_Location (Separate from Customer and Seller)

### Status
✅ Accepted

### Decision
**Create a separate Dim_Location conformed dimension instead of storing location attributes
directly in Dim_Customer and Dim_Seller.**

### Context
Both customers and sellers have location data (city, state, zip code). Storing these attributes
in each dimension would duplicate data and complicate geographic analysis.

### Alternatives Considered

| Alternative | Pros | Cons |
|:---|:---|:---|
| **Inline in Customer/Seller** | Simpler ETL | Duplicated cities/states; hard to analyze geography across entities |
| **Separate Dim_Location (Chosen)** | Single source of truth; easy cross-entity geo analysis | One extra JOIN in some queries |

### Rationale

1. **Single Source of Truth:** City and state names are standardized once in Dim_Location.
   Updates apply everywhere automatically.

2. **Cross-Entity Geographic Analysis:** Enables queries like "Orders where seller and customer
   are in the same state" or "Average delivery time by customer region vs seller region."

3. **Storage Efficiency:** Storing location_key (INT) instead of city (VARCHAR) + state (VARCHAR)
   in fact tables saves significant space at scale.

4. **Brazilian Regions:** Added a `region` column mapping states to 5 Brazilian regions
   (North, Northeast, Central-West, Southeast, South) for higher-level geographic analysis.

### Consequences

| Positive | Negative |
|:---|:---|
| No city/state duplication | Need location_key lookup during ETL |
| Easy cross-entity geo analysis | 302 customer and 253 seller zip codes not found in geolocation (0.27%) |
| Region-level analysis built-in | - |

---

## ADR-004: Dim_Lead with Optional seller_key

### Status
✅ Accepted

### Decision
**Create a dedicated Dim_Lead dimension for Marketing Qualified Leads, with an optional seller_key
foreign key in Fact_Seller_Acquisition that is NULL for unconverted leads.**

### Context
The source system tracks marketing leads separately from sellers. A lead exists before conversion;
a seller exists after. Only ~10.5% of leads (842 of 8,000) convert to sellers.

### Alternatives Considered

| Alternative | Pros | Cons |
|:---|:---|:---|
| **Only Dim_Seller** | Fewer tables | 7,620 leads have no seller; NULL dimension key is anti-pattern |
| **NULL seller_key (Chosen)** | Correct entity modeling | Extra dimension table |
| **Only Dim_Lead** | Unified lead view | Can't analyze seller performance post-conversion |

### Rationale

1. **Correct Entity Separation:** Lead ≠ Seller. They are different entities with different
   attributes and lifecycles.

2. **Full Funnel Analysis:** Enables tracking from lead acquisition (first_contact_date) through
   conversion (won_date) to seller performance (Fact_Sales).

3. **NULL is Meaningful:** The 7,620 NULL seller_key values represent unconverted leads - this
   is accurate, not an error.

### Query Examples Enabled

```sql
-- Conversion rate by lead source
SELECT ls.origin, 
       COUNT(*) AS leads,
       COUNT(CASE WHEN conversion_flag THEN 1 END) AS converted,
       ROUND(100.0 * COUNT(CASE WHEN conversion_flag THEN 1 END) / COUNT(*), 1) AS rate
FROM facts.fact_seller_acquisition fa
JOIN dimensions.dim_lead_source ls ON fa.lead_source_key = ls.lead_source_key
GROUP BY ls.origin;

-- Average revenue of converted sellers by lead source
SELECT ls.origin,
       ROUND(AVG(fs.item_total), 2) AS avg_seller_revenue
FROM facts.fact_seller_acquisition fa
JOIN dimensions.dim_lead_source ls ON fa.lead_source_key = ls.lead_source_key
JOIN facts.fact_sales fs ON fa.seller_key = fs.seller_key
WHERE fa.conversion_flag = TRUE
GROUP BY ls.origin;
```

### Consequences

| Positive | Negative |
|:---|:---|
| Full funnel visibility | Extra dimension to maintain |
| Clean entity separation | seller_key validation must allow NULLs |
| Supports conversion analysis | - |

---

## ADR-005: Fact_Order_Events (Factless Fact Table)

### Status
✅ Accepted

### Decision
**Create a factless fact table (Fact_Order_Events) by unpivoting order timestamps into
individual event rows.**

### Context
Each order goes through a lifecycle: purchased → approved → delivered_carrier → delivered_customer
(potentially canceled). Analyzing this funnel from Fact_Sales requires UNION ALL on 4-5 date columns,
resulting in multiple full table scans.

### Alternatives Considered

| Alternative | Pros | Cons |
|:---|:---|:---|
| **UNION ALL from Fact_Sales** | No extra table | 3-5 full scans per query; complex SQL |
| **Fact_Order_Events (Chosen)** | One scan; simple GROUP BY | Extra storage (~393K rows); ETL complexity |

### ETL Logic

From one row in `orders`:
```
order_id = 123
order_purchase_timestamp      → event: purchased
order_approved_at             → event: approved
order_delivered_carrier_date  → event: delivered_carrier
order_delivered_customer_date → event: delivered_customer
(if canceled)                 → event: canceled
```

### Query Comparison

| Approach | Query Complexity | Performance |
|:---|:---|:---|
| UNION ALL | 15+ lines, 4 subqueries | 4 full scans of Fact_Sales |
| Fact_Order_Events | 5 lines, 1 scan | 1 index scan |

```sql
-- With Fact_Order_Events (simple):
SELECT et.event_type_name, COUNT(DISTINCT order_id)
FROM facts.fact_order_events f
JOIN dimensions.dim_event_type et ON f.event_type_key = et.event_type_key
GROUP BY et.event_type_name;
```

### Consequences

| Positive | Negative |
|:---|:---|
| Simple funnel queries | Extra 393K rows storage |
| Fast performance | ETL must unpivot 99K orders |
| Easy to add new events | - |

---

## ADR-006: Slowly Changing Dimension Strategy

### Status
✅ Accepted

### Decision
**Use SCD Type 1 (overwrite) for all customer and seller dimensions.**

### Context
The Olist dataset does not contain historical address changes. Each customer and seller appears
with a single address snapshot. Implementing SCD Type 2 (which tracks history) requires effective
date columns and change detection mechanisms that are absent from the source.

### Alternatives Considered

| Alternative | Pros | Cons |
|:---|:---|:---|
| **SCD Type 1 (Chosen)** | Simple ETL; correct for available data | Cannot track historical address changes |
| **SCD Type 2** | Full historical tracking | No source data supports it; meaningless without change history |

### Implementation

```sql
-- Type 1: Simply overwrite
UPDATE dimensions.dim_customer 
SET city = new_city, state = new_state 
WHERE customer_id = updated_customer_id;
```

### Future Consideration

If future data includes address change timestamps, upgrade to SCD Type 2:
```sql
ALTER TABLE dimensions.dim_customer 
ADD COLUMN effective_start_date DATE,
ADD COLUMN effective_end_date DATE,
ADD COLUMN is_current BOOLEAN;
```

### Consequences

| Positive | Negative |
|:---|:---|
| Simple ETL logic | Cannot analyze customer movement patterns |
| Correct for available data | Requires schema change if history needed later |
| Faster dimension loads | - |

---

## ADR-007: Review Grain - No product_key or seller_key

### Status
✅ Accepted

### Decision
**Fact_Reviews grain is one row per review_id. Do not add product_key or seller_key directly.
Instead, join through Fact_Sales via order_id when product/seller analysis is needed.**

### Context
A customer writes one review per order, not per product. If an order contains 3 products, there is
still only 1 review. Adding product_key would force choosing one product (arbitrary) or duplicating
the review 3 times (incorrect).

### Problem Illustration

```
Order #A001 contains:
├── Product X (from Seller A)
├── Product Y (from Seller B)
└── Product Z (from Seller A)

Customer writes: 1 review (score: 4)
```

| Approach | Rows | Problem |
|:---|:---:|:---|
| Add product_key | 3 | Review duplicated; which product gets the score? |
| Pick first product | 1 | Arbitrarily assigns review to Product X only |
| **No product_key (Chosen)** | **1** | **Correct grain; join via order_id** |

### Correct Query Pattern

```sql
-- Average review score by product category
SELECT p.product_category_name_english,
       ROUND(AVG(r.review_score), 2) AS avg_score
FROM facts.fact_reviews r
JOIN facts.fact_sales s ON r.order_id = s.order_id
JOIN dimensions.dim_product p ON s.product_key = p.product_key
GROUP BY p.product_category_name_english;
```

### Consequences

| Positive | Negative |
|:---|:---|
| Correct grain preservation | Extra JOIN for product-level review analysis |
| No data duplication | Slightly more complex review-product queries |
| Clean star schema | - |

---

## ADR-008: Performance Indexing Strategy

### Status
✅ Accepted

### Decision
**Create 20 B-tree indexes covering all foreign key columns in fact tables.**

### Index List

| # | Table | Column | Index Name |
|:--:|:---|:---|:---|
| 1 | fact_sales | customer_key | idx_fact_sales_customer_key |
| 2 | fact_sales | seller_key | idx_fact_sales_seller_key |
| 3 | fact_sales | product_key | idx_fact_sales_product_key |
| 4 | fact_sales | purchase_date_key | idx_fact_sales_purchase_date_key |
| 5 | fact_sales | delivered_customer_date_key | idx_fact_sales_delivered_customer_date_key |
| 6 | fact_sales | order_status_key | idx_fact_sales_order_status_key |
| 7 | fact_sales | customer_location_key | idx_fact_sales_customer_location_key |
| 8 | fact_sales | seller_location_key | idx_fact_sales_seller_location_key |
| 9 | fact_payments | customer_key | idx_fact_payments_customer_key |
| 10 | fact_payments | payment_date_key | idx_fact_payments_payment_date_key |
| 11 | fact_payments | payment_type_key | idx_fact_payments_payment_type_key |
| 12 | fact_reviews | customer_key | idx_fact_reviews_customer_key |
| 13 | fact_reviews | review_creation_date_key | idx_fact_reviews_review_creation_date_key |
| 14 | fact_seller_acquisition | lead_key | idx_fact_seller_acquisition_lead_key |
| 15 | fact_seller_acquisition | seller_key | idx_fact_seller_acquisition_seller_key |
| 16 | fact_seller_acquisition | lead_source_key | idx_fact_seller_acquisition_lead_source_key |
| 17 | fact_order_events | customer_key | idx_fact_order_events_customer_key |
| 18 | fact_order_events | seller_key | idx_fact_order_events_seller_key |
| 19 | fact_order_events | event_date_key | idx_fact_order_events_event_date_key |
| 20 | fact_order_events | event_type_key | idx_fact_order_events_event_type_key |

### Performance Impact

| Scenario | Without Index | With Index |
|:---|:---|:---|
| JOIN fact_sales ↔ dim_customer | Full table scan (112K rows) | Index lookup (~3 page reads) |
| Filter by date range | Full table scan | Index range scan |
| GROUP BY category | Hash join on full scan | Nested loop with index |

### Consequences

| Positive | Negative |
|:---|:---|
| 10-100x faster analytical queries | Slightly slower data loads (~5%) |
| Enables real-time dashboard queries | Additional storage (~10% of table size) |
| Better query plan generation | - |

---

## ADR-009: Surrogate Keys Strategy

### Status
✅ Accepted

### Decision
**All dimension tables use integer surrogate keys (INT) as primary keys instead of the original
VARCHAR(32) natural keys from the source system.**

### Rationale

| Factor | Natural Keys (VARCHAR) | Surrogate Keys (INT) |
|:---|:---|:---|
| Storage per FK | 32 bytes | 4 bytes |
| Index size | Larger | 8x smaller |
| JOIN speed | Slower (string comparison) | Faster (integer comparison) |
| SCD support | Hard (key changes break history) | Easy (key never changes) |
| Data warehouse standard | Rarely used | Industry best practice |

### Example

```
Natural Key:  '06b8999e2fba1a1fbc88172c00ba8bc7' (32 bytes)
Surrogate Key: 4291 (4 bytes)

Fact_Sales has 112,650 rows × 5 FKs:
- Natural: 112,650 × 5 × 32 = 18 MB for FKs alone
- Surrogate: 112,650 × 5 × 4 = 2.3 MB for FKs
= 8x storage savings
```

### Consequences

| Positive | Negative |
|:---|:---|
| 8x smaller FK storage | Must maintain lookup maps during ETL |
| Faster JOIN performance | Cannot query by natural key directly |
| SCD ready (keys never change) | Extra mapping step in fact table build |
| Industry standard | - |

---

## ADR-010: Medallion Architecture (Bronze → Silver → Gold)

### Status
✅ Accepted

### Decision
**Implement a three-layer architecture within the transformation pipeline.**

### Layer Purposes

| Layer | Schema | Purpose | User Persona |
|:---|:---|:---|:---|
| **Bronze** | `olist_olap.bronze` | Raw 1:1 copy from source; immutable historical record | Data Engineers |
| **Silver** | `olist_olap.silver` | Cleaned, merged, typed; ready for analysis | Data Analysts |
| **Gold** | `olist_olap.dimensions` + `olist_olap.facts` | Business-ready star schema | Business Users, BI Tools |

### Data Flow

```
Source (SQLite) ──▶ OLTP (PostgreSQL) ──▶ Bronze ──▶ Silver ──▶ Gold
   Raw data           Migration            Raw copy   Cleaned    Star Schema
   ~1.5M rows         ~1.5M rows          ~1.5M rows  ~578K rows ~882K rows
```

### Why Not Skip Bronze?

1. **Reprocessing:** If a cleaning bug is discovered, bronze allows re-running silver without
   re-extracting from source.
2. **Audit Trail:** `_loaded_at` timestamps track when data was ingested.
3. **Source of Truth:** Preserves exactly what the source provided, unchanged.

### Why Not Skip Silver?

1. **Quality Checkpoint:** Silver is where all cleaning logic lives. Analysts can query silver
   directly for exploratory work.
2. **Separation of Concerns:** Gold only does mapping and surrogate key replacement. All complex
   logic (geolocation aggregation, lead merging, type conversion) stays in silver.

### Consequences

| Positive | Negative |
|:---|:---|
| Clear separation of concerns | Extra storage for bronze layer |
| Reprocessing capability | Longer pipeline execution |
| Analysts can use silver directly | More schemas to manage |
| Industry-standard pattern | - |

---

## ADR-011: Reconciliation Testing Strategy

### Status
✅ Accepted

### Decision
**Implement 37 source-to-target reconciliation checks that compare aggregate metrics between
olist_oltp (source) and olist_olap (target) to validate ETL correctness.**

### Check Categories

| Category | Checks | What It Validates |
|:---|:---:|:---|
| Row Counts | 6 | No data loss during ETL |
| Financial Metrics | 5 | Revenue, shipping, payment accuracy |
| Distributions | 4 | Order status, payment types, review scores, lead sources |
| Review Metrics | 3 | Average scores, positive/negative ratios |
| Category Revenue | 1 | Product-level aggregation correctness |
| Seller Acquisition | 4 | Lead counts, conversions, funnel accuracy |
| Order Events | 3 | Event type counts match source |
| Geographic | 2 | City/state uniqueness preserved |
| Date Coverage | 3 | Date range completeness |
| Product Data | 2 | Category translations, weight accuracy |
| Installments | 2 | Payment installment calculations |
| Delivery Metrics | 3 | Delay calculations, on-time percentages |

### Design Principle

Each reconciliation check has:
1. A query on the source (OLTP) that computes a specific metric
2. An equivalent query on the target (OLAP) that computes the same metric
3. Automated comparison with tolerance thresholds

### Separation of Concerns

Queries are stored separately from execution logic:
- `reconciliation_queries.py` - Query definitions only (data)
- `run_reconciliation.py` - Test runner (code)

This allows adding new checks without modifying any execution logic.

### Consequences

| Positive | Negative |
|:---|:---|
| Catches ETL bugs before reports are affected | 37 queries to maintain |
| Easy to add new checks | Some queries needed refinement for grain matching |
| Automated PASS/FAIL reporting | - |
| Query-code separation | - |

---

## ADR-012: Dim_Time and Time Analysis

### Status
✅ Accepted

### Decision
**Create Dim_Time dimension (1,440 rows = every minute of the day) and add purchase_time_key
to Fact_Sales for intraday analysis.**

### Structure

| Column | Type | Example | Purpose |
|:---|:---|:---|:---|
| time_key | INT PK | 896 | Minutes since midnight (14×60 + 56 = 896) |
| hour | INT | 14 | 24-hour format |
| minute | INT | 56 | Minute of hour |
| part_of_day | VARCHAR | Afternoon | Morning/Afternoon/Evening/Night |
| is_business_hours | BOOLEAN | TRUE | 9AM-5PM indicator |

### Time Extraction Logic

```python
# From timestamp: 2017-10-02 14:56:33
purchase_dt = pd.to_datetime(df["order_purchase_timestamp"])
df["purchase_time_key"] = purchase_dt.dt.hour * 60 + purchase_dt.dt.minute
# Result: time_key = 896
```

### Analysis Enabled

| Business Question | Query Pattern |
|:---|:---|
| Peak shopping hours? | GROUP BY hour, COUNT orders |
| Weekend vs weekday patterns? | JOIN dim_date.is_weekend + dim_time.part_of_day |
| Business hours revenue share? | Filter is_business_hours = TRUE vs FALSE |
| Late-night high-value orders? | Filter part_of_day = 'Night', AVG item_total |

### Consequences

| Positive | Negative |
|:---|:---|
| Intraday analysis capability | 1,440 extra dimension rows (negligible) |
| Simple time categorization | Must be extracted from timestamp in ETL |
| Enables time-based dashboard filters | - |

---

## Summary

| ADR | Decision | Status |
|:--:|:---|:--:|
| 001 | Kimball Star Schema | ✅ |
| 002 | Multiple Fact Tables (5) | ✅ |
| 003 | Separate Dim_Location | ✅ |
| 004 | Dim_Lead + Optional seller_key | ✅ |
| 005 | Fact_Order_Events (Factless Fact) | ✅ |
| 006 | SCD Type 1 (Overwrite) | ✅ |
| 007 | No product_key in Fact_Reviews | ✅ |
| 008 | 20 Performance Indexes | ✅ |
| 009 | Integer Surrogate Keys | ✅ |
| 010 | Medallion Architecture | ✅ |
| 011 | 37 Reconciliation Checks | ✅ |
| 012 | Dim_Time for Intraday Analysis | ✅ |
