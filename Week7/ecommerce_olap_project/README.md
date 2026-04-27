# E-Commerce OLAP Data Warehouse

## 📚 Table of Contents

1. [Project Overview](#project-overview)
2. [Business Problem](#business-problem)
3. [Why OLAP?](#why-olap)
4. [Architecture](#architecture)
5. [Schema Design: Star Schema](#schema-design-star-schema)
6. [Source Database: ecommerce_oltp](#source-database-ecommerce_oltp)
7. [Target Database: ecommerce_olap](#target-database-ecommerce_olap)
8. [ETL Pipeline](#etl-pipeline)
9. [Data Mapping: OLTP → OLAP](#data-mapping-oltp--olap)
10. [Indexing Strategy](#indexing-strategy)
11. [Project Structure](#project-structure)
12. [Setup and Installation](#setup-and-installation)
13. [How to Run](#how-to-run)
14. [Output Tables](#output-tables)
15. [Design Decisions](#design-decisions)
16. [Example Queries](#example-queries)
17. [Technologies Used](#technologies-used)
18. [Future Enhancements](#future-enhancements)
19. [Summary](#summary)

---

## Project Overview

This project transforms a real-world **e-commerce OLTP database** into a fully functional **OLAP data warehouse** using a **Star Schema** design. The entire ETL pipeline is written in Python and processes data from a normalized transactional system into an analytics-optimized structure.

- **Source:** `ecommerce_oltp` — a PostgreSQL database with **10 tables** in Third Normal Form (3NF)
- **Target:** `ecommerce_olap` — a PostgreSQL data warehouse with **10 dimension tables** and **1 fact table**
- **Schema:** **Star Schema** — all dimensions connect directly to a single central fact table
- **Records processed:** 150 users · 250 products · 300 orders · 721 transaction line items
- **Execution:** Single command — `python load.py`

---

## Business Problem

An e-commerce company operates a transactional system that handles daily operations efficiently. However, the management team cannot answer critical business questions that drive strategy and growth.

### The Five Core Problems

#### Problem 1: Death by JOINs

Every analytical query requires joining 4–6 tables. To answer *"What are total sales per city?"*, an analyst must write:

```sql
SELECT b.city, SUM(oi.quantity * oi.unit_sale_price)
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN branches b ON o.branch_id = b.branch_id
WHERE o.status != 'cancelled'
GROUP BY b.city;
```

This is slow, error-prone, and unsustainable as data grows.

#### Problem 2: No Time Intelligence

The OLTP stores a single `order_date` timestamp. Business users need to analyze:

- Sales during **Ramadan** vs. other months
- **Weekend** vs. **weekday** performance
- **End-of-month** shopping surges
- **Seasonal** trends (Spring, Summer, Fall, Winter)
- **Hijri calendar** alignment for religious events
- **National holidays** (Yemen: May 22, Sep 26, Oct 14, Nov 30)

None of this exists in the source system. Analysts manually calculate dates in every query — inconsistent and error-prone.

#### Problem 3: Historical Data Destruction

When a product price changes from $100 to $120, the old price is **overwritten**. This means:

- Profit on old orders cannot be accurately calculated
- Price change impact on sales volume cannot be analyzed
- Audit trails are lost

Same issue applies to customer addresses (city changes) and payment method availability.

#### Problem 4: Inconsistent Metrics

Every analyst calculates `profit` and `profit_margin` differently:

- Some use `unit_sale_price - unit_purchase_price`
- Some forget to multiply by quantity
- Some exclude cancelled orders, others don't

There is **no single source of truth** for any metric.

#### Problem 5: Raw Status Strings

The `orders.status` column contains: `'pending'`, `'paid'`, `'shipped'`, `'delivered'`, `'cancelled'`. Analysts constantly write:

```sql
WHERE status IN ('paid', 'shipped', 'delivered')  -- "Completed"
```

If a new status like `'refunded'` is added, every report breaks.

---

## Why OLAP?

We built an OLAP data warehouse to systematically solve each problem:

| # | OLTP Problem | OLAP Solution | Implementation |
|---|-------------|---------------|----------------|
| 1 | 4–6 table JOINs | Pre-joined fact table with all foreign keys | `fct_order_transaction` connects to all dimensions via `_key` columns |
| 2 | No time intelligence | Rich calendar dimension with 25+ attributes | `dim_date`: Gregorian + Hijri + seasons + holidays + weekends |
| 3 | Historical data overwritten | Slowly Changing Dimension Type 2 | `dim_product`, `dim_user`, `dim_payment_method` track all changes |
| 4 | Inconsistent metrics | Pre-calculated measures during ETL | `sales_amount`, `profit`, `profit_margin` computed once, used by all |
| 5 | Raw status strings | Status dimension with categorization | `dim_status`: Completed / Cancelled / Pending |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    SOURCE: ecommerce_oltp                          │
│                                                                    │
│  ┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ users  │ │ orders │ │order_items│ │ products │ │ brands   │  │
│  │ (150)  │ │ (300)  │ │  (721)    │ │  (250)   │ │  (10)    │  │
│  └───┬────┘ └───┬────┘ └─────┬─────┘ └────┬─────┘ └────┬─────┘  │
│      │          │            │            │            │         │
│  ┌───┴────┐ ┌───┴────┐ ┌─────┴─────┐ ┌────┴─────┐ ┌────┴─────┐  │
│  │branches│ │currencies│ │payment_mtd│ │payments │ │categories│  │
│  │  (4)   │ │   (3)   │ │    (5)    │ │  (300)  │ │   (6)    │  │
│  └────────┘ └─────────┘ └───────────┘ └─────────┘ └──────────┘  │
│                                                                    │
│  Total: 10 tables, 3NF, optimized for writes                       │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │       PYTHON ETL PIPELINE     │
              │                               │
              │  1. extract.py                │
              │     Reads all 10 OLTP tables  │
              │                               │
              │  2. transform_dimensions.py   │
              │     Builds 10 dimension tables│
              │                               │
              │  3. transform_facts.py        │
              │     Builds 1 fact table       │
              │                               │
              │  4. load.py                   │
              │     Creates OLAP database     │
              │     Inserts all 11 tables     │
              │     Creates basic indexes     │
              └──────────────┬───────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    TARGET: ecommerce_olap                          │
│                                                                    │
│                        ⭐ STAR SCHEMA ⭐                            │
│                                                                    │
│  10 Dimension Tables               1 Fact Table                   │
│  ┌────────────────┐    ┌─────────────────────────────────────┐   │
│  │ dim_date (4018)│    │ fct_order_transaction (721)         │   │
│  │ dim_time (1440)│    │                                     │   │
│  │ dim_currency(3)│    │  transaction_key (PK)               │   │
│  │ dim_brand (10) │    │  date_key (FK) → dim_date           │   │
│  │ dim_category(6)│    │  time_key (FK) → dim_time           │   │
│  │ dim_branch (4) │    │  product_key (FK) → dim_product     │   │
│  │ dim_product(250)│   │  brand_key (FK) → dim_brand         │   │
│  │ dim_user (150) │    │  category_key (FK) → dim_category   │   │
│  │ dim_pay_mtd (5)│    │  user_key (FK) → dim_user           │   │
│  │ dim_status (5) │    │  branch_key (FK) → dim_branch       │   │
│  └────────────────┘    │  currency_key (FK) → dim_currency   │   │
│                        │  payment_method_key(FK) → dim_pay   │   │
│                        │  status_key (FK) → dim_status       │   │
│                        │  quantity | sales_amount             │   │
│                        │  profit | profit_margin              │   │
│                        └─────────────────────────────────────┘   │
│                                                                    │
│  Total: 10 dimensions + 1 fact table, optimized for reads         │
└──────────────────────────────────────────────────────────────────┘
```

---

## Schema Design: Star Schema

### Why Star Schema?

We chose the **Star Schema** architecture after careful analysis:

| Design | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Star** | Simple queries, fast JOINs, easy to understand | Some data redundancy in dimensions | ✅ **Chosen** |
| Snowflake | Less storage, normalized dimensions | Slower queries, complex JOIN chains | ❌ Rejected |
| Galaxy | Supports multiple fact tables | Over-engineered for single fact table | ❌ Deferred |

### Key Characteristics of Our Star Schema

1. **Single Fact Table:** `fct_order_transaction` at the center — one row per product per order
2. **10 Surrounding Dimensions:** Each connects directly to the fact table via surrogate keys
3. **No Inter-Dimension Links:** Dimensions are fully independent; no foreign keys between them
4. **Surrogate Keys:** Every dimension uses `_key` (surrogate) separate from `_id` (natural)
5. **Pre-calculated Measures:** `sales_amount`, `profit`, `profit_margin` stored in the fact table

### Entity Relationship Diagram

```
                         ┌──────────────────┐
                         │     dim_date     │
                         │   (4,018 rows)   │
                         └────────┬─────────┘
                                  │
                                  │ date_key
                                  │
    ┌─────────────────┐  ┌────────┴─────────┐  ┌─────────────────┐
    │   dim_product   │  │                  │  │    dim_user     │
    │   (250 rows)    │  │                  │  │   (150 rows)    │
    └───────┬─────────┘  │                  │  └────────┬────────┘
            │            │                  │           │
            │ product_key│                  │ user_key  │
            │            │                  │           │
    ┌───────┴─────────┐  │                  │  ┌────────┴────────┐
    │    dim_brand    │  │                  │  │   dim_branch    │
    │    (10 rows)    │──┤                  ├──│   (4 rows)      │
    └─────────────────┘  │                  │  └─────────────────┘
                         │                  │
    ┌─────────────────┐  │                  │  ┌─────────────────┐
    │  dim_category   │──┤  fct_order       ├──│  dim_currency   │
    │   (6 rows)      │  │  transaction     │  │   (3 rows)      │
    └─────────────────┘  │  (721 rows)      │  └─────────────────┘
                         │                  │
    ┌─────────────────┐  │                  │  ┌─────────────────┐
    │ dim_payment_mtd │──┤                  ├──│   dim_status    │
    │   (5 rows)      │  │                  │  │   (5 rows)      │
    └─────────────────┘  └────────┬─────────┘  └─────────────────┘
                                  │
                                  │ time_key
                                  │
                         ┌────────┴─────────┐
                         │     dim_time     │
                         │   (1,440 rows)   │
                         └──────────────────┘
```

---

## Source Database: ecommerce_oltp

### Tables and Relationships

The source database contains **10 tables** in Third Normal Form (3NF):

| # | Table | Rows | Purpose |
|---|-------|------|---------|
| 1 | `currencies` | 3 | SAR, USD, AED with exchange rates |
| 2 | `brands` | 10 | Product brands (Apple, Samsung, Nike, etc.) |
| 3 | `branches` | 4 | Physical store locations in Yemen |
| 4 | `categories` | 6 | Product categories (Electronics, Fashion, etc.) |
| 5 | `users` | 150 | Customer profiles with contact info |
| 6 | `products` | 250 | Products with prices and inventory |
| 7 | `payment_methods` | 5 | Credit Card, Mada, Apple Pay, Cash, STC Pay |
| 8 | `orders` | 300 | Order headers with status tracking |
| 9 | `payments` | 300 | Payment transactions linked to orders |
| 10 | `order_items` | 721 | Line items (each product within each order) |

### OLTP Entity Relationships

```
currencies ──────────────┐
                         ├──> users (preferred_currency_id)
                         └──> orders (currency_id)

brands ─────────────────────> products (brand_id)
categories ─────────────────> products (category_id)

users ──────────────────────> orders (user_id)
branches ───────────────────> orders (branch_id)

orders ─────────────────────> order_items (order_id)
orders ─────────────────────> payments (order_id)

products ───────────────────> order_items (product_id)
payment_methods ────────────> payments (method_id)
```

### OLTP Limitations

| Limitation | Business Impact |
|-----------|-----------------|
| 10 normalized tables | Every analytical query needs 4–6 JOINs |
| No calendar table | No Ramadan, Eid, weekend, or holiday flags |
| Prices overwritten on update | Cannot calculate historical profit accurately |
| Addresses overwritten | Cannot analyze sales by customer's city at time of purchase |
| Status as raw strings | No categorization; reports break on new statuses |
| Metrics calculated per query | Inconsistent profit and margin across reports |
| Timestamp-only time data | No morning/afternoon/evening classification |

---

## Target Database: ecommerce_olap

### Dimension Tables (10 tables)

#### 1. `dim_date` — Calendar Intelligence (4,018 rows, 2020–2030)

The most feature-rich dimension. Provides both Gregorian and Hijri calendar support with Yemen national holidays.

| Column | Type | Example | Purpose |
|--------|------|---------|---------|
| `date_key` | INTEGER (PK) | 20260323 | YYYYMMDD integer for fast JOINs |
| `date_actual` | DATE | 2026-03-23 | Actual date value |
| `year` | INTEGER | 2026 | Gregorian year |
| `month` | INTEGER | 3 | Month number (1–12) |
| `day` | INTEGER | 23 | Day of month |
| `quarter` | INTEGER | 1 | Quarter (1–4) |
| `day_name` | VARCHAR | Thursday | Full day name |
| `month_name` | VARCHAR | March | Full month name |
| `day_of_week` | INTEGER | 3 | 0=Monday, 6=Sunday |
| `week_of_year` | INTEGER | 13 | ISO week number |
| `is_weekend` | BOOLEAN | FALSE | Friday or Saturday |
| `is_weekday` | BOOLEAN | TRUE | Not weekend |
| `is_month_end` | BOOLEAN | FALSE | Last day of month |
| `is_month_start` | BOOLEAN | FALSE | First day of month |
| `is_year_start` | BOOLEAN | FALSE | January 1st |
| `is_year_end` | BOOLEAN | FALSE | December 31st |
| `season` | VARCHAR | Spring | Spring/Summer/Fall/Winter |
| `hijri_year` | INTEGER | 1447 | Hijri year |
| `hijri_month` | INTEGER | 9 | Hijri month (1=Muharram, 9=Ramadan) |
| `hijri_day` | INTEGER | 23 | Hijri day |
| `hijri_month_name` | VARCHAR | Ramadan | Hijri month name |
| `is_ramadan` | BOOLEAN | FALSE | True during Ramadan (Hijri month 9) |
| `is_eid_al_fitr` | BOOLEAN | FALSE | Shawwal 1–3 |
| `is_eid_al_adha` | BOOLEAN | FALSE | Dhul Hijjah 10–13 |
| `is_eid` | BOOLEAN | FALSE | Any Eid (Fitr or Adha) |
| `is_national_holiday` | BOOLEAN | FALSE | Yemen national holiday |
| `is_holiday` | BOOLEAN | FALSE | Any holiday (religious or national) |

**Yemen National Holidays:**
- **May 22** — Unity Day (National Day)
- **September 26** — September 26 Revolution
- **October 14** — October 14 Revolution
- **November 30** — Independence Day

#### 2. `dim_time` — Time of Day (1,440 rows)

Every minute of the day, classified by part of day.

| Column | Type | Example | Purpose |
|--------|------|---------|---------|
| `time_key` | INTEGER (PK) | 143500 | HHMMSS integer format |
| `time_of_day` | VARCHAR | 14:35:00 | Human-readable time |
| `hour` | INTEGER | 14 | Hour (0–23) |
| `minute` | INTEGER | 35 | Minute (0–59) |
| `daytime_name` | VARCHAR | Afternoon | Morning/Afternoon/Evening/Night |
| `day_night` | VARCHAR | Day | Day (06:00–17:59), Night (18:00–05:59) |

#### 3. `dim_currency` (3 rows)

| Column | Type | Description |
|--------|------|-------------|
| `currency_key` | SERIAL (PK) | Surrogate key |
| `currency_id` | INTEGER | Original ID from OLTP |
| `currency_code` | VARCHAR | SAR, USD, AED |
| `currency_name` | VARCHAR | Saudi Riyal, US Dollar, UAE Dirham |
| `exchange_rate_to_sar` | DECIMAL | Conversion rate to SAR |

#### 4. `dim_brand` (10 rows)

| Column | Type | Description |
|--------|------|-------------|
| `brand_key` | SERIAL (PK) | Surrogate key |
| `brand_id` | INTEGER | Original ID from OLTP |
| `brand_name` | VARCHAR | Apple, Samsung, Nike, etc. |
| `country` | VARCHAR | USA, South Korea, Germany, etc. |

#### 5. `dim_category` (6 rows)

| Column | Type | Description |
|--------|------|-------------|
| `category_key` | SERIAL (PK) | Surrogate key |
| `category_id` | INTEGER | Original ID from OLTP |
| `category_name` | VARCHAR | Electronics, Fashion, Home, etc. |

#### 6. `dim_branch` (4 rows)

| Column | Type | Description |
|--------|------|-------------|
| `branch_key` | SERIAL (PK) | Surrogate key |
| `branch_id` | INTEGER | Original ID from OLTP |
| `branch_name` | VARCHAR | Store name (Arabic) |
| `branch_city` | VARCHAR | City location |
| `branch_manager` | VARCHAR | Manager name |
| `branch_location` | TEXT | Location details |

#### 7. `dim_product` (250 rows, SCD Type 2)

Tracks product price history over time.

| Column | Type | Description |
|--------|------|-------------|
| `product_key` | SERIAL (PK) | Surrogate key |
| `product_id` | INTEGER | Original ID from OLTP |
| `product_name` | VARCHAR | Product name |
| `brand_id` | INTEGER | For reference/traceability |
| `category_id` | INTEGER | For reference/traceability |
| `purchase_price` | DECIMAL | Current purchase cost |
| `sale_price` | DECIMAL | Current sale price |
| `start_date` | DATE | When this version became effective |
| `end_date` | DATE | When this version expired (NULL = current) |
| `is_current` | BOOLEAN | TRUE for active version |

**SCD Type 2 Logic:** When a price changes:
1. Old row: `end_date = today`, `is_current = FALSE`
2. New row: `start_date = today`, `end_date = NULL`, `is_current = TRUE`

#### 8. `dim_user` (150 rows, SCD Type 2)

Tracks customer profile changes over time.

| Column | Type | Description |
|--------|------|-------------|
| `user_key` | SERIAL (PK) | Surrogate key |
| `user_id` | INTEGER | Original ID from OLTP |
| `user_name` | VARCHAR | Full name |
| `user_email` | VARCHAR | Email address |
| `user_phone` | VARCHAR | Phone number |
| `currency_key` | INTEGER (FK) | Preferred currency → `dim_currency` |
| `currency_code` | VARCHAR | Preferred currency code |
| `user_address` | VARCHAR | Customer address/city |
| `start_date` | DATE | When this version became effective |
| `end_date` | DATE | When this version expired |
| `is_current` | BOOLEAN | TRUE for active version |

#### 9. `dim_payment_method` (5 rows, SCD Type 2)

Tracks payment method availability over time.

| Column | Type | Description |
|--------|------|-------------|
| `payment_method_key` | SERIAL (PK) | Surrogate key |
| `payment_method_id` | INTEGER | Original ID from OLTP |
| `payment_method_name` | VARCHAR | Credit Card, Mada, Apple Pay, etc. |
| `is_active` | BOOLEAN | Currently available? |
| `start_date` | DATE | When active status started |
| `end_date` | DATE | When active status ended |
| `is_current` | BOOLEAN | TRUE for active version |

#### 10. `dim_status` (5 rows)

Categorizes order statuses into logical groups.

| Column | Type | Description |
|--------|------|-------------|
| `status_key` | SERIAL (PK) | Surrogate key |
| `status_id` | INTEGER | Sequential ID |
| `status_name` | VARCHAR | pending, paid, shipped, delivered, cancelled |
| `status_category` | VARCHAR | Completed / Cancelled / Pending |

**Category Mapping:**

| status_name | status_category |
|-------------|-----------------|
| `paid` | Completed |
| `shipped` | Completed |
| `delivered` | Completed |
| `cancelled` | Cancelled |
| `pending` | Pending |

---

### Fact Table

#### `fct_order_transaction` (721 rows) ⭐

**Grain (Granularity):** One row = one product sold within one order.

| Column | Type | FK Reference | Description |
|--------|------|-------------|-------------|
| `transaction_key` | SERIAL (PK) | — | Surrogate primary key |
| `date_key` | INTEGER | → `dim_date` | Order date (YYYYMMDD) |
| `time_key` | INTEGER | → `dim_time` | Order time (HHMMSS) |
| `product_key` | INTEGER | → `dim_product` | Product sold |
| `brand_key` | INTEGER | → `dim_brand` | Product brand |
| `category_key` | INTEGER | → `dim_category` | Product category |
| `user_key` | INTEGER | → `dim_user` | Customer who ordered |
| `branch_key` | INTEGER | → `dim_branch` | Store location |
| `currency_key` | INTEGER | → `dim_currency` | Order currency |
| `payment_method_key` | INTEGER | → `dim_payment_method` | Payment method used |
| `status_key` | INTEGER | → `dim_status` | Order status |
| `quantity` | INTEGER | — | Units sold |
| `unit_sale_price` | DECIMAL | — | Sale price at transaction time |
| `unit_purchase_price` | DECIMAL | — | Purchase cost at transaction time |
| `sales_amount` | DECIMAL | — | `quantity × unit_sale_price` |
| `profit` | DECIMAL | — | `sales_amount − (quantity × unit_purchase_price)` |
| `profit_margin` | DECIMAL | — | `(profit ÷ sales_amount) × 100` |

---

## ETL Pipeline

### Pipeline Files

| File | Responsibility | Input | Output |
|------|---------------|-------|--------|
| `config.py` | Database credentials & SQLAlchemy engines | None | `oltp_engine`, `olap_engine` |
| `extract.py` | Read all OLTP tables | `ecommerce_oltp` | 10 DataFrames |
| `transform_dimensions.py` | Clean, enrich, structure dimensions | Raw DataFrames | 10 dimension DataFrames |
| `transform_facts.py` | Merge, calculate, build fact table | Dimensions + Raw | 1 fact DataFrame |
| `load.py` | Create DB, tables, insert data, indexes | All 11 DataFrames | `ecommerce_olap` |
| `create_indexes.py` | All performance indexes | `olap_engine` | 23 basic indexes |

### Data Flow

```
ecommerce_db.sql ───(manual run)───> ecommerce_oltp (10 tables)
                                          │
                                     extract.py
                                          │
                                    10 DataFrames
                                          │
                        ┌─────────────────┼─────────────────┐
                        │                 │                 │
                transform_dimensions.py   │          transform_facts.py
                        │                 │                 │
                  10 Dimension            │            1 Fact
                  DataFrames              │           DataFrame
                        │                 │                 │
                        └─────────────────┼─────────────────┘
                                          │
                                      load.py
                                          │
                        ┌─────────────────┼─────────────────┐
                        │                 │                 │
                   Create tables    Insert data     create_indexes.py
                        │                 │                 │
                        └─────────────────┼─────────────────┘
                                          │
                                   ecommerce_olap
                              (10 Dims + 1 Fact table
                               + 23 basic indexes)
```

---

## Data Mapping: OLTP → OLAP

### Table-Level Mapping

| OLTP Source | OLAP Target |
|-------------|-------------|
| `users` | `dim_user` |
| `products` | `dim_product` |
| `brands` | `dim_brand` |
| `categories` | `dim_category` |
| `branches` | `dim_branch` |
| `currencies` | `dim_currency` |
| `payment_methods` | `dim_payment_method` |
| `orders.status` (distinct) | `dim_status` |
| `orders` + `order_items` | `fct_order_transaction` |

### Column-Level Mapping

| OLTP Column | OLAP Column | Transformation |
|-------------|-------------|----------------|
| `users.full_name` | `dim_user.user_name` | Direct |
| `users.address` | `dim_user.user_address` | NULL → 'Unknown' |
| `users.email` | `dim_user.user_email` | Direct |
| `users.phone` | `dim_user.user_phone` | Direct |
| `products.product_name` | `dim_product.product_name` | Direct |
| `products.purchase_price` | `dim_product.purchase_price` | Direct |
| `products.sale_price` | `dim_product.sale_price` | Direct |
| `brands.brand_name` | `dim_brand.brand_name` | Direct |
| `brands.country_of_origin` | `dim_brand.country` | Direct |
| `categories.category_name` | `dim_category.category_name` | Direct |
| `branches.branch_name` | `dim_branch.branch_name` | Direct |
| `branches.city` | `dim_branch.branch_city` | Direct |
| `branches.manager_name` | `dim_branch.branch_manager` | Direct |
| `currencies.currency_code` | `dim_currency.currency_code` | Direct |
| `currencies.currency_name` | `dim_currency.currency_name` | Direct |
| `currencies.exchange_rate_to_sar` | `dim_currency.exchange_rate_to_sar` | Direct |
| `payment_methods.method_name` | `dim_payment_method.payment_method_name` | Direct |
| `payment_methods.is_active` | `dim_payment_method.is_active` | Direct |
| `orders.status` | `dim_status.status_name` | Distinct values only |
| `order_items.quantity` | `fct_order_transaction.quantity` | Direct |
| `order_items.unit_sale_price` | `fct_order_transaction.unit_sale_price` | Direct |
| `order_items.unit_purchase_price` | `fct_order_transaction.unit_purchase_price` | Direct |

### Derived Columns

| OLAP Column | Formula |
|-------------|---------|
| `fct_order_transaction.sales_amount` | `quantity × unit_sale_price` |
| `fct_order_transaction.profit` | `sales_amount − (quantity × unit_purchase_price)` |
| `fct_order_transaction.profit_margin` | `(profit ÷ sales_amount) × 100` |
| `fct_order_transaction.date_key` | `order_date` → YYYYMMDD (integer) |
| `fct_order_transaction.time_key` | `order_date` → HHMMSS (integer) |

### Categorization Rules

| OLTP Value | OLAP Column | OLAP Value |
|------------|-------------|------------|
| `'paid'` | `dim_status.status_category` | `'Completed'` |
| `'shipped'` | `dim_status.status_category` | `'Completed'` |
| `'delivered'` | `dim_status.status_category` | `'Completed'` |
| `'cancelled'` | `dim_status.status_category` | `'Cancelled'` |
| `'pending'` | `dim_status.status_category` | `'Pending'` |

### Default Value Rules

| OLAP Column | Default | Applied When |
|-------------|---------|-------------|
| `dim_user.user_address` | `'Unknown'` | `users.address IS NULL` |
| `dim_user.currency_code` | `'SAR'` | `currencies.currency_code IS NULL` |
| `dim_user.currency_key` | `1` | `currencies.currency_key IS NULL` |

### SCD Type 2 Configuration

| Dimension | Tracks Changes On |
|-----------|-------------------|
| `dim_product` | `sale_price`, `purchase_price` |
| `dim_user` | `user_address`, `user_phone`, `currency_key` |
| `dim_payment_method` | `is_active` |

---

## Indexing Strategy

### File: `scripts/create_indexes.py`

All indexes are centralized in one file, divided into two functions:

#### `create_basic_indexes()` — Auto-Executed on Every Load

These run automatically from `load.py`. They are essential for Star Schema performance:

**Fact Table Foreign Keys (9 indexes):**
- BRIN index on `date_key` (efficient for time-series data)
- B-Tree indexes on all 8 dimension foreign keys (`product_key`, `brand_key`, `category_key`, `user_key`, `branch_key`, `currency_key`, `payment_method_key`, `status_key`)

**Fact Table Composite Indexes (2 indexes):**
- `(date_key, product_key)` — common date-product queries
- `(date_key, profit)` — common date-profit queries

**Dimension SCD Type 2 Lookups (4 indexes):**
- `dim_product`: partial index on `is_current = TRUE`, composite on `(start_date, end_date)`
- `dim_user`: partial index on `is_current = TRUE`
- `dim_payment_method`: partial index on `is_current = TRUE`

**Dimension Filter Columns (8 indexes):**
- `dim_date`: on `year`, `is_ramadan`, `is_holiday`, `is_weekend`, `is_month_end`
- `dim_time`: on `daytime_name`, `day_night`
- `dim_status`: on `status_category`

**Total basic indexes: 23**

#### `create_advanced_indexes()` — Optional, Commented Out

These are available but commented out. Users uncomment them if needed:

- Covering indexes for date-sales, product-sales, customer-sales reports
- Partial indexes for completed orders only, high-value transactions

> **⚠️ How to enable:** Open `create_indexes.py`, uncomment the desired index lines, and re-run `load.py` or call `create_advanced_indexes()` directly.

---

## Project Structure

```
ecommerce_olap_project/
│
├── data/
│   └── raw/
│       └── ecommerce_db.sql          # OLTP source file (run once manually)
│
├── scripts/
│   ├── config.py                     # Database connection settings
│   ├── extract.py                    # Extract all 10 tables from ecommerce_oltp
│   ├── transform_dimensions.py       # Build 10 dimension tables
│   ├── transform_facts.py            # Build the star schema fact table
│   ├── create_indexes.py             # All indexes (basic + advanced)
│   └── load.py                       # Create ecommerce_olap, load data, create indexes
│
├── requirements.txt                  # Python dependencies
└── README.md                         # This documentation
```

---

## Setup and Installation

### Prerequisites

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.8+ | ETL execution |
| PostgreSQL | 12+ | Source and target databases |
| pip | Latest | Package installation |

### Step 1: Install Dependencies

```bash
pip install pandas sqlalchemy psycopg2-binary hijridate
```

Or:

```bash
pip install -r requirements.txt
```

**`requirements.txt`:**
```
pandas
sqlalchemy
psycopg2-binary
hijridate
```

### Step 2: Create the OLTP Database

Run the SQL file to create and populate `ecommerce_oltp`:

```bash
psql -U postgres -f data/raw/ecommerce_db.sql
```

This creates:
- Database: `ecommerce_oltp`
- 10 tables with: 150 users · 250 products · 300 orders · 721 order items

### Step 3: Configure Connection

Edit `scripts/config.py`:

```python
DB_USER = "postgres"          # Your PostgreSQL username
DB_PASSWORD = "your_password"  # Your PostgreSQL password
DB_HOST = "localhost"
DB_PORT = "5432"
```

---

## How to Run

### Single Command

```bash
cd scripts
python load.py
```

### What Happens

1. **Database creation:** Creates `ecommerce_olap` if it doesn't exist
2. **Extraction:** Reads all 10 tables from `ecommerce_oltp`
3. **Dimension building:** Builds 10 dimension tables (4,018 + 1,440 + 3 + 10 + 6 + 4 + 150 + 5 + 250 + 5 rows)
4. **Fact table building:** Merges and calculates 721 transaction rows
5. **Loading:** Creates all 11 tables and inserts data
6. **Indexing:** Creates 23 basic indexes automatically

### Expected Output

```
Database ecommerce_olap created.
Extraction complete.
Success: dim_date built with 4018 rows.
Success: dim_time built with 1440 rows.
dim_currency built: 3 rows
dim_brand built: 10 rows
dim_category built: 6 rows
dim_branch built: 4 rows
dim_user built: 150 rows
dim_payment_method built: 5 rows
dim_product built: 250 rows
dim_status built: 5 rows
fct_order_transaction built: 721 rows
Loaded dim_date: 4018 rows.
Loaded dim_time: 1440 rows.
Loaded dim_currency: 3 rows.
Loaded dim_brand: 10 rows.
Loaded dim_category: 6 rows.
Loaded dim_branch: 4 rows.
Loaded dim_user: 150 rows.
Loaded dim_payment_method: 5 rows.
Loaded dim_product: 250 rows.
Loaded dim_status: 5 rows.
Loaded fct_order_transaction: 721 rows.
Creating basic indexes...
Basic indexes created successfully.

All tables loaded and indexed successfully!
Tip: To enable advanced indexes, edit create_indexes.py and uncomment the lines.
```

---

## Output Tables

| # | Table | Rows | Type | Key Features |
|---|-------|------|------|-------------|
| 1 | `dim_date` | 4,018 | Dimension | Gregorian + Hijri, Yemen holidays, seasons |
| 2 | `dim_time` | 1,440 | Dimension | Every minute, classified by daytime |
| 3 | `dim_currency` | 3 | Dimension | SAR, USD, AED with exchange rates |
| 4 | `dim_brand` | 10 | Dimension | Product brands with countries |
| 5 | `dim_category` | 6 | Dimension | Product categories |
| 6 | `dim_branch` | 4 | Dimension | Store locations with managers |
| 7 | `dim_product` | 250 | Dimension (SCD2) | Price history tracking |
| 8 | `dim_user` | 150 | Dimension (SCD2) | Profile history tracking |
| 9 | `dim_payment_method` | 5 | Dimension (SCD2) | Active status tracking |
| 10 | `dim_status` | 5 | Dimension | Categorized (Completed/Cancelled/Pending) |
| 11 | `fct_order_transaction` | 721 | **Fact** | Pre-calculated sales, profit, margin |

---

## Design Decisions

### 1. Star Schema Over Snowflake or Galaxy

**Why Star:** Our system has exactly one analytical focus — sales transactions. Star Schema gives the best query performance with the simplest mental model. Snowflake would add JOIN complexity for no benefit. Galaxy would be over-engineering since we don't have multiple fact tables yet.

### 2. Surrogate Keys (`_key`) Separate from Natural Keys (`_id`)

**Why:** Isolates the warehouse from OLTP ID changes. If the source system renumbers products, our `product_key` mapping absorbs the change without affecting historical data.

### 3. SCD Type 2 on Product, User, and Payment Method

**Why:** These are the only entities where history matters for analysis:
- Product prices: must calculate profit using the price *at transaction time*
- User addresses: must attribute sales to the city *at order time*
- Payment methods: must track availability *over time*

### 4. Pre-calculated Measures

**Why:** `sales_amount`, `profit`, and `profit_margin` are calculated once during ETL. Every analyst uses the exact same formula. No more "which profit number is correct?"

### 5. Yemen National Holidays

**Why:** The business operates in Yemen. The calendar dimension includes the four Yemeni national holidays: Unity Day (May 22), September 26 Revolution, October 14 Revolution, and Independence Day (Nov 30).

### 6. Hijri Calendar Integration

**Why:** Using the `hijridate` library, `dim_date` includes full Hijri calendar support. This is critical for Ramadan/Eid analysis, which drives major shopping behavior shifts.

### 7. Integer Keys for Date and Time

**Why:** `date_key = YYYYMMDD` and `time_key = HHMMSS` as integers. Integer JOINs are faster than date/time or string JOINs. They're also human-readable.

### 8. Indexing Strategy: Basic (Auto) + Advanced (Optional)

**Why:** Basic indexes are essential and lightweight. Advanced indexes trade disk space for specific query performance. By separating them, we give users control without overwhelming beginners.

---

## Example Queries

### Total Sales by City

```sql
SELECT br.branch_city, SUM(f.sales_amount) AS total_sales
FROM fct_order_transaction f
JOIN dim_branch br ON f.branch_key = br.branch_key
JOIN dim_status s ON f.status_key = s.status_key
WHERE s.status_category = 'Completed'
GROUP BY br.branch_city
ORDER BY total_sales DESC;
```

### Most Profitable Brands During Ramadan

```sql
SELECT b.brand_name, SUM(f.profit) AS total_profit
FROM fct_order_transaction f
JOIN dim_brand b ON f.brand_key = b.brand_key
JOIN dim_date d ON f.date_key = d.date_key
WHERE d.is_ramadan = TRUE
GROUP BY b.brand_name
ORDER BY total_profit DESC;
```

### Cancellation Rate by Branch

```sql
SELECT
    br.branch_name,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN s.status_category = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled,
    ROUND(100.0 * SUM(CASE WHEN s.status_category = 'Cancelled' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cancel_rate
FROM fct_order_transaction f
JOIN dim_branch br ON f.branch_key = br.branch_key
JOIN dim_status s ON f.status_key = s.status_key
GROUP BY br.branch_name
ORDER BY cancel_rate DESC;
```

### Top 10 Customers by Profit

```sql
SELECT u.user_name, SUM(f.profit) AS total_profit, ROUND(AVG(f.profit_margin), 2) AS avg_margin
FROM fct_order_transaction f
JOIN dim_user u ON f.user_key = u.user_key
WHERE u.is_current = TRUE
GROUP BY u.user_name
ORDER BY total_profit DESC
LIMIT 10;
```

### Sales by Time of Day

```sql
SELECT t.daytime_name, COUNT(*) AS orders, SUM(f.sales_amount) AS total_sales
FROM fct_order_transaction f
JOIN dim_time t ON f.time_key = t.time_key
GROUP BY t.daytime_name
ORDER BY total_sales DESC;
```

### Monthly Sales Trend (2026)

```sql
SELECT d.month_name, SUM(f.sales_amount) AS monthly_sales, SUM(f.profit) AS monthly_profit
FROM fct_order_transaction f
JOIN dim_date d ON f.date_key = d.date_key
WHERE d.year = 2026
GROUP BY d.month, d.month_name
ORDER BY d.month;
```

### Weekend vs. Weekday Performance

```sql
SELECT
    CASE WHEN d.is_weekend THEN 'Weekend' ELSE 'Weekday' END AS day_type,
    COUNT(*) AS transactions,
    SUM(f.sales_amount) AS total_sales
FROM fct_order_transaction f
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.is_weekend;
```

### National Holiday Sales Analysis

```sql
SELECT d.month_name, d.day, SUM(f.sales_amount) AS holiday_sales
FROM fct_order_transaction f
JOIN dim_date d ON f.date_key = d.date_key
WHERE d.is_national_holiday = TRUE
GROUP BY d.month, d.month_name, d.day
ORDER BY d.month, d.day;
```

---

## Technologies Used

| Technology | Purpose |
|------------|---------|
| **Python 3.8+** | ETL scripting language |
| **pandas** | Data manipulation and transformation |
| **SQLAlchemy** | Database connection and ORM |
| **psycopg2-binary** | PostgreSQL adapter |
| **hijridate** | Hijri (Islamic) calendar conversion |
| **PostgreSQL 12+** | Source (OLTP) and target (OLAP) database |

---

## Future Enhancements

| Enhancement | Benefit |
|-------------|---------|
| `dim_date` holiday population | Auto-populate actual Hijri dates for Ramadan/Eid |
| Historical exchange rates | Accurate currency conversion for old orders |
| Incremental ETL loading | Process only new/modified records instead of full rebuild |
| Additional fact table (`fct_inventory`) | Stock movement analysis using same dimensions |
| ETL logging and alerts | Track pipeline health, notify on failures |
| Data quality validation layer | Automated checks before loading |
| Power BI / Tableau dashboard templates | Ready-made reports for business users |

---

## Summary

This project transforms a normalized e-commerce database into a **Star Schema** analytics warehouse. The transformation delivers:

- ⚡ **Fast queries** — single fact table JOINs instead of 5-table chains
- 📅 **Calendar intelligence** — Gregorian + Hijri, seasons, Yemen holidays, Ramadan, Eid
- 🕐 **Time-of-day analysis** — Morning, Afternoon, Evening, Night
- 💰 **Currency dimension** — SAR, USD, AED unified
- 📈 **Pre-calculated metrics** — `sales_amount`, `profit`, `profit_margin` ready to query
- 🔄 **History tracking** — SCD Type 2 on products, users, and payment methods
- 🏷️ **Status categorization** — Completed/Cancelled/Pending
- 📊 **Mapping documentation** — Every OLTP→OLAP transformation documented
- 🚀 **Smart indexing** — 23 automatic indexes + optional advanced indexes
- 🔟 **10 dimensions + 1 fact** — Clean, simple, powerful Star Schema

**One command. Eleven tables. Unlimited insights.**

```
python load.py
```