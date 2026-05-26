# 📖 Data Dictionary - Olist Data Warehouse

## Overview

This document provides a complete column-level description of every table in the Gold Layer
(`olist_olap.dimensions` and `olist_olap.facts` schemas).

### Column Type Conventions

| Type | Description |
|:---|:---|
| `PK` | Primary Key - Unique identifier for each row |
| `FK` | Foreign Key - References a primary key in another table |
| `DD` | Degenerate Dimension - Identifier without its own dimension table |
| `Measure` | Fact - Numeric value that can be aggregated (SUM, AVG, COUNT) |
| `Derived` | Calculated during ETL from other columns |

---

## Dimensions (11 Tables)

---

### dim_date

**Description:** Calendar dimension containing all dates from 2016-01-01 to 2018-12-31.
Enables time-based analysis at any granularity (day, month, quarter, year).

**Source:** Generated programmatically (not from source data).

**Row Count:** 1,096

| # | Column | Type | Example | Description |
|:--:|:---|:---|:---|:---|
| 1 | `date_key` | INT (PK) | 20171002 | Surrogate key in YYYYMMDD format |
| 2 | `full_date` | DATE | 2017-10-02 | Complete calendar date |
| 3 | `year` | INT | 2017 | Year number |
| 4 | `month` | INT | 10 | Month number (1-12) |
| 5 | `month_name` | VARCHAR | October | Full month name in English |
| 6 | `quarter` | INT | 4 | Quarter number (1-4) |
| 7 | `day_of_week` | INT | 1 | ISO day (1=Monday, 7=Sunday) |
| 8 | `day_name` | VARCHAR | Monday | Full day name in English |
| 9 | `is_weekend` | BOOLEAN | false | TRUE for Saturday and Sunday |

**Used By:**
- `fact_sales` (5 role-playing roles: purchase, approved, delivered_carrier, delivered_customer, estimated)
- `fact_payments` (payment_date_key)
- `fact_reviews` (review_creation_date_key, review_answer_date_key)
- `fact_seller_acquisition` (first_contact_date_key, won_date_key)
- `fact_order_events` (event_date_key)

---

### dim_time

**Description:** Time-of-day dimension with all 1,440 minutes in a day. Enables intraday
analysis of purchasing patterns.

**Source:** Generated programmatically.

**Row Count:** 1,440

| # | Column | Type | Example | Description |
|:--:|:---|:---|:---|:---|
| 1 | `time_key` | INT (PK) | 896 | Minutes since midnight (0-1439) |
| 2 | `hour` | INT | 14 | Hour in 24-hour format (0-23) |
| 3 | `minute` | INT | 56 | Minute of hour (0-59) |
| 4 | `hour_12` | INT | 2 | Hour in 12-hour format (1-12) |
| 5 | `am_pm` | VARCHAR | PM | AM or PM indicator |
| 6 | `part_of_day` | VARCHAR | Afternoon | Morning, Afternoon, Evening, Night |
| 7 | `is_business_hours` | BOOLEAN | true | TRUE if 9:00 AM to 5:00 PM |

**Part of Day Mapping:**
| Time Range | part_of_day |
|:---|:---|
| 06:00 - 11:59 | Morning |
| 12:00 - 17:59 | Afternoon |
| 18:00 - 21:59 | Evening |
| 22:00 - 05:59 | Night |

**Used By:**
- `fact_sales` (purchase_time_key)

---

### dim_customer

**Description:** Customer profiles including geographic information.

**Source:** `silver.customers`

**SCD Strategy:** Type 1 (Overwrite)

**Row Count:** 99,441

| # | Column | Type | Example | Description |
|:--:|:---|:---|:---|:---|
| 1 | `customer_key` | INT (PK) | 4291 | Surrogate key |
| 2 | `customer_id` | VARCHAR | 06b8999e2... | Original ID from source system |
| 3 | `customer_unique_id` | VARCHAR | 861eff4711... | Unique customer identifier across all orders |
| 4 | `city` | VARCHAR | franca | Customer city (lowercase, standardized) |
| 5 | `state` | VARCHAR(2) | SP | State abbreviation (uppercase) |
| 6 | `zip_code_prefix` | INT | 14409 | 5-digit Brazilian zip code prefix |

**Used By:**
- `fact_sales` (customer_key)
- `fact_payments` (customer_key)
- `fact_reviews` (customer_key)
- `fact_order_events` (customer_key)

---

### dim_seller

**Description:** Seller profiles including geographic information.

**Source:** `silver.sellers`

**SCD Strategy:** Type 1 (Overwrite)

**Row Count:** 3,095

| # | Column | Type | Example | Description |
|:--:|:---|:---|:---|:---|
| 1 | `seller_key` | INT (PK) | 1429 | Surrogate key |
| 2 | `seller_id` | VARCHAR | 48436dade... | Original ID from source system |
| 3 | `city` | VARCHAR | campinas | Seller city (lowercase, standardized) |
| 4 | `state` | VARCHAR(2) | SP | State abbreviation (uppercase) |
| 5 | `zip_code_prefix` | INT | 13023 | 5-digit Brazilian zip code prefix |

**Used By:**
- `fact_sales` (seller_key)
- `fact_seller_acquisition` (seller_key - NULL for unconverted leads)
- `fact_order_events` (seller_key)

---

### dim_product

**Description:** Product catalog with physical dimensions and category classification
in both Portuguese and English.

**Source:** `silver.products` (joined with `product_category_name_translation`)

**SCD Strategy:** Type 1 (Overwrite)

**Row Count:** 32,951

| # | Column | Type | Example | Description |
|:--:|:---|:---|:---|:---|
| 1 | `product_key` | INT (PK) | 8742 | Surrogate key |
| 2 | `product_id` | VARCHAR | 4244733e0... | Original ID from source system |
| 3 | `product_category_name` | VARCHAR | beleza_saude | Category name in Portuguese |
| 4 | `product_category_name_english` | VARCHAR | health_beauty | Category name in English |
| 5 | `product_name_length` | INT | 40 | Character count of product name |
| 6 | `product_description_length` | INT | 287 | Character count of product description |
| 7 | `product_photos_qty` | INT | 1 | Number of product photos |
| 8 | `product_weight_g` | INT | 225 | Product weight in grams |
| 9 | `product_length_cm` | INT | 16 | Product length in centimeters |
| 10 | `product_height_cm` | INT | 10 | Product height in centimeters |
| 11 | `product_width_cm` | INT | 14 | Product width in centimeters |

**Used By:**
- `fact_sales` (product_key)

---

### dim_location

**Description:** Geographic dimension with zip code, city, state, and Brazilian region.
Built from aggregated geolocation data (1M rows → 19,615 unique zip codes).

**Source:** `silver.geolocation` (aggregated) + region mapping

**SCD Strategy:** Type 1 (Overwrite)

**Row Count:** 19,615

| # | Column | Type | Example | Description |
|:--:|:---|:---|:---|:---|
| 1 | `location_key` | INT (PK) | 8234 | Surrogate key |
| 2 | `zip_code_prefix` | INT | 14409 | 5-digit Brazilian zip code prefix |
| 3 | `city` | VARCHAR | franca | City name (lowercase, standardized) |
| 4 | `state` | VARCHAR(2) | SP | State abbreviation (uppercase) |
| 5 | `region` | VARCHAR | Southeast | Brazilian region |

**Region Mapping:**
| Region | States |
|:---|:---|
| North | AM, PA, RO, RR, AP, TO, AC |
| Northeast | BA, PE, CE, MA, PB, RN, AL, SE, PI |
| Central-West | DF, GO, MT, MS |
| Southeast | SP, RJ, MG, ES |
| South | PR, SC, RS |

**Used By:**
- `fact_sales` (customer_location_key, seller_location_key)

---

### dim_lead

**Description:** Marketing Qualified Leads - descriptive attributes of each lead captured
through marketing channels.

**Source:** `silver.leads` (merged from `leads_qualified` + `leads_closed`)

**SCD Strategy:** Type 1 (Overwrite)

**Row Count:** 8,000

| # | Column | Type | Example | Description |
|:--:|:---|:---|:---|:---|
| 1 | `lead_key` | INT (PK) | 542 | Surrogate key |
| 2 | `mql_id` | VARCHAR | 5420aad7f... | Marketing Qualified Lead identifier |
| 3 | `lead_type` | VARCHAR | online_medium | Type of lead (industry, online_big, online_medium, online_small, offline, online_top) |
| 4 | `lead_behaviour_profile` | VARCHAR | cat | Behavior profile (cat, eagle, wolf, NULL) |
| 5 | `business_segment` | VARCHAR | pet | Target business segment |
| 6 | `business_type` | VARCHAR | reseller | Business type (reseller, manufacturer) |

**Used By:**
- `fact_seller_acquisition` (lead_key)

---

### dim_payment_type

**Description:** Payment method lookup table.

**Source:** Distinct values from `silver.order_payments`

**Row Count:** 5

| # | Column | Type | Example | Description |
|:--:|:---|:---|:---|:---|
| 1 | `payment_type_key` | INT (PK) | 1 | Surrogate key |
| 2 | `payment_type` | VARCHAR | credit_card | Payment method name |

**Values:** credit_card, boleto, voucher, debit_card, not_defined

**Used By:**
- `fact_payments` (payment_type_key)

---

### dim_order_status

**Description:** Order lifecycle status lookup table.

**Source:** Distinct values from `silver.orders`

**Row Count:** 8

| # | Column | Type | Example | Description |
|:--:|:---|:---|:---|:---|
| 1 | `order_status_key` | INT (PK) | 1 | Surrogate key |
| 2 | `order_status` | VARCHAR | delivered | Order status name |

**Values:** approved, canceled, created, delivered, invoiced, processing, shipped, unavailable

**Used By:**
- `fact_sales` (order_status_key)

---

### dim_event_type

**Description:** Order lifecycle event types for Fact_Order_Events.

**Source:** Static/hardcoded values

**Row Count:** 5

| # | Column | Type | Example | Description |
|:--:|:---|:---|:---|:---|
| 1 | `event_type_key` | INT (PK) | 1 | Surrogate key |
| 2 | `event_type_name` | VARCHAR | purchased | Event type name |

**Values:**
| event_type_key | event_type_name |
|:---:|:---|
| 1 | purchased |
| 2 | approved |
| 3 | delivered_carrier |
| 4 | delivered_customer |
| 5 | canceled |

**Used By:**
- `fact_order_events` (event_type_key)

---

### dim_lead_source

**Description:** Marketing channel/origin lookup table.

**Source:** Distinct values from `silver.leads.origin`

**Row Count:** 10

| # | Column | Type | Example | Description |
|:--:|:---|:---|:---|:---|
| 1 | `lead_source_key` | INT (PK) | 4 | Surrogate key |
| 2 | `origin` | VARCHAR | organic_search | Marketing channel name |

**Values:** organic_search, paid_search, social, email, referral, direct_traffic, unknown, others...

**Used By:**
- `fact_seller_acquisition` (lead_source_key)

---

## Facts (5 Tables)

---

### fact_sales

**Description:** Core sales fact table tracking every item sold in every order. Contains pricing,
shipping, delivery performance, and all dimensional references.

**Source:** `silver.order_items` JOIN `silver.orders`

**Grain:** One row per `order_id` + `order_item_id`

**Row Count:** 112,650

| # | Column | Type | FK Reference | Description |
|:--:|:---|:---|:---|:---|
| 1 | `sales_key` | BIGINT (PK) | - | Surrogate key |
| 2 | `order_id` | VARCHAR (DD) | - | Order identifier (degenerate dimension) |
| 3 | `order_item_id` | INT | - | Item sequence number within order (1, 2, 3...) |
| 4 | `customer_key` | INT (FK) | dim_customer | Customer who placed the order |
| 5 | `seller_key` | INT (FK) | dim_seller | Seller who fulfilled the item |
| 6 | `product_key` | INT (FK) | dim_product | Product sold |
| 7 | `customer_location_key` | INT (FK) | dim_location | Customer's geographic location |
| 8 | `seller_location_key` | INT (FK) | dim_location | Seller's geographic location |
| 9 | `purchase_date_key` | INT (FK) | dim_date | Date order was placed |
| 10 | `approved_date_key` | INT (FK) | dim_date | Date payment was approved |
| 11 | `delivered_carrier_date_key` | INT (FK) | dim_date | Date handed to shipping carrier |
| 12 | `delivered_customer_date_key` | INT (FK) | dim_date | Date delivered to customer |
| 13 | `estimated_delivery_date_key` | INT (FK) | dim_date | Originally promised delivery date |
| 14 | `order_status_key` | INT (FK) | dim_order_status | Current order status |
| 15 | `unit_price` | DECIMAL (Measure) | - | Price per unit in Brazilian Real (R$) |
| 16 | `quantity` | INT (Measure) | - | Number of units (default 1) |
| 17 | `item_total` | DECIMAL (Measure) | - | unit_price × quantity |
| 18 | `shipping_value` | DECIMAL (Measure) | - | Freight cost charged to customer |
| 19 | `delivery_delay_days` | INT (Measure) | - | Actual delivery days - estimated (positive = late) |

**Calculated Fields:**
- `item_total = unit_price × quantity`
- `delivery_delay_days = delivered_customer_date - estimated_delivery_date`

---

### fact_payments

**Description:** Payment transactions fact table. An order can have multiple payments
(different methods, installments, split payments).

**Source:** `silver.order_payments` JOIN `silver.orders`

**Grain:** One row per `order_id` + `payment_sequential`

**Row Count:** 103,886

| # | Column | Type | FK Reference | Description |
|:--:|:---|:---|:---|:---|
| 1 | `payment_key` | INT (PK) | - | Surrogate key |
| 2 | `order_id` | VARCHAR (DD) | - | Order identifier (degenerate dimension) |
| 3 | `payment_sequential` | INT | - | Payment sequence within order (1, 2, 3...) |
| 4 | `customer_key` | INT (FK) | dim_customer | Customer who made the payment |
| 5 | `payment_date_key` | INT (FK) | dim_date | Date of payment (approximated to purchase date) |
| 6 | `payment_type_key` | INT (FK) | dim_payment_type | Payment method used |
| 7 | `payment_value` | DECIMAL (Measure) | - | Amount paid in Brazilian Real (R$) |
| 8 | `payment_installments` | INT | - | Number of installments |

**Note:** `payment_date_key` is approximated to `order_purchase_timestamp` because the source
`order_payments` table does not contain an explicit payment date.

---

### fact_reviews

**Description:** Customer review fact table. Contains satisfaction scores and derived sentiment flags.

**Source:** `silver.order_reviews` JOIN `silver.orders`

**Grain:** One row per `review_id`

**Row Count:** 99,224

| # | Column | Type | FK Reference | Description |
|:--:|:---|:---|:---|:---|
| 1 | `review_key` | INT (PK) | - | Surrogate key |
| 2 | `review_id` | VARCHAR | - | Unique review identifier |
| 3 | `order_id` | VARCHAR (DD) | - | Order identifier (degenerate dimension) |
| 4 | `customer_key` | INT (FK) | dim_customer | Customer who wrote the review |
| 5 | `review_creation_date_key` | INT (FK) | dim_date | Date review was submitted |
| 6 | `review_answer_date_key` | INT (FK) | dim_date | Date seller responded to review |
| 7 | `review_score` | INT (Measure) | - | Rating score (1-5) |
| 8 | `is_positive` | BOOLEAN (Derived) | - | TRUE if review_score >= 4 |
| 9 | `is_negative` | BOOLEAN (Derived) | - | TRUE if review_score <= 2 |

**Note:** This fact does not include `product_key` or `seller_key` because a review applies to
an entire order, not individual items. For product-level review analysis, join through
`fact_sales` via `order_id`.

---

### fact_seller_acquisition

**Description:** Marketing funnel fact table tracking leads from first contact through
conversion to seller.

**Source:** `silver.leads`

**Grain:** One row per `mql_id`

**Row Count:** 8,000

| # | Column | Type | FK Reference | Description |
|:--:|:---|:---|:---|:---|
| 1 | `acquisition_key` | INT (PK) | - | Surrogate key |
| 2 | `lead_key` | INT (FK) | dim_lead | Lead profile (always populated) |
| 3 | `seller_key` | INT (FK) | dim_seller | Seller profile (NULL if not converted) |
| 4 | `lead_source_key` | INT (FK) | dim_lead_source | Marketing channel that generated the lead |
| 5 | `first_contact_date_key` | INT (FK) | dim_date | Date lead first entered the funnel |
| 6 | `won_date_key` | INT (FK) | dim_date | Date lead converted to seller (NULL if not) |
| 7 | `declared_monthly_revenue` | DECIMAL (Measure) | - | Self-declared monthly revenue in R$ |
| 8 | `declared_product_catalog_size` | DECIMAL (Measure) | - | Self-declared number of products |
| 9 | `has_company` | BOOLEAN (Measure) | - | Whether lead has registered company |
| 10 | `has_gtin` | BOOLEAN (Measure) | - | Whether products have GTIN barcodes |
| 11 | `conversion_flag` | BOOLEAN (Derived) | - | TRUE if won_date is not NULL |
| 12 | `conversion_days` | INT (Measure) | - | Days between first_contact and won_date |

**Conversion Statistics:** 380 of 8,000 leads converted (4.75%). 7,620 leads remain unconverted
(seller_key IS NULL).

---

### fact_order_events

**Description:** Factless fact table tracking each order's lifecycle events.
Each order generates 3-5 rows (one per lifecycle stage reached).

**Source:** `silver.orders` (unpivoted timestamps)

**Grain:** One row per `order_id` + `event_type_key`

**Row Count:** 393,481

| # | Column | Type | FK Reference | Description |
|:--:|:---|:---|:---|:---|
| 1 | `event_key` | BIGINT (PK) | - | Surrogate key |
| 2 | `order_id` | VARCHAR (DD) | - | Order identifier (degenerate dimension) |
| 3 | `customer_key` | INT (FK) | dim_customer | Customer associated with order |
| 4 | `seller_key` | INT (FK) | dim_seller | Seller associated with order |
| 5 | `event_date_key` | INT (FK) | dim_date | Date the event occurred |
| 6 | `event_type_key` | INT (FK) | dim_event_type | Type of event |

**Event Distribution (approximate):**
| event_type_name | Order Count | % |
|:---|---:|---:|
| purchased | 99,441 | 100% |
| approved | ~99,200 | ~99.8% |
| delivered_carrier | ~98,500 | ~99.1% |
| delivered_customer | 96,476 | 97.0% |
| canceled | ~300 | ~0.3% |

---

## Role-Playing Dimensions

`dim_date` serves as a role-playing dimension in `fact_sales`, used 5 times with different meanings:

| Role | FK Column | Meaning |
|:---|:---|:---|
| Purchase Date | purchase_date_key | When customer placed the order |
| Approval Date | approved_date_key | When payment was approved |
| Carrier Date | delivered_carrier_date_key | When order was handed to shipping company |
| Delivery Date | delivered_customer_date_key | When order reached customer |
| Estimated Date | estimated_delivery_date_key | When delivery was originally promised |

`dim_location` serves as a role-playing dimension in `fact_sales`, used 2 times:

| Role | FK Column | Meaning |
|:---|:---|:---|
| Customer Location | customer_location_key | Where the customer is located |
| Seller Location | seller_location_key | Where the seller is located |

---

## Cross-Reference Matrix

| Dimension | fact_sales | fact_payments | fact_reviews | fact_seller_acquisition | fact_order_events |
|:---|:--:|:--:|:--:|:--:|:--:|
| dim_date | ✅ (x5) | ✅ | ✅ (x2) | ✅ (x2) | ✅ |
| dim_time | ✅ | - | - | - | - |
| dim_customer | ✅ | ✅ | ✅ | - | ✅ |
| dim_seller | ✅ | - | - | ✅ (nullable) | ✅ |
| dim_product | ✅ | - | - | - | - |
| dim_location | ✅ (x2) | - | - | - | - |
| dim_lead | - | - | - | ✅ | - |
| dim_payment_type | - | ✅ | - | - | - |
| dim_order_status | ✅ | - | - | - | - |
| dim_event_type | - | - | - | - | ✅ |
| dim_lead_source | - | - | - | ✅ | - |
