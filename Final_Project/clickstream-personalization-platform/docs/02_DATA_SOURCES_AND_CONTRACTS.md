# Data Sources and Contracts

## Purpose

This document defines the source data contracts used by **Clickstream Personalization Platform**.

The project integrates behavioral, operational, transactional, reference, geolocation, weather, and holiday data into a unified analytical platform. Each source has a defined ingestion method, ownership boundary, key structure, validation rules, and downstream analytical role.

The source contracts are designed to support:

```text
Behavior analytics
Journey analysis
Funnel analysis
Product performance
Order attribution
User profile history
Geo and context enrichment
Personalization candidate generation
Power BI reporting
```

The platform keeps source ingestion, clean lakehouse storage, serving publication, and reporting responsibilities separated.

---

## Source Inventory

| Source | Category | Format / System | Ingestion Method | Primary Role |
|---|---|---|---|---|
| Clickstream Events | Behavioral | JSONL | Local publisher to Kafka | Captures user interaction events. |
| Web Server Logs | Operational | `.log` JSON lines | Filebeat to Kafka | Captures HTTP request and response behavior. |
| Product Catalog | Reference | CSV | Spark batch load | Provides product attributes. |
| Users | Transactional | PostgreSQL | Debezium CDC to Kafka | Captures user profile changes. |
| Orders | Transactional | PostgreSQL | Debezium CDC to Kafka | Captures order-level transactions. |
| Order Items | Transactional | PostgreSQL | Debezium CDC to Kafka | Captures line-item product sales. |
| GeoIP Database | Enrichment | MaxMind GeoLite2 City `.mmdb` | Local Spark lookup | Adds location context from IP addresses. |
| Weather | External Context | Open-Meteo API | Airflow-triggered Spark batch | Adds weather context by location and hour. |
| Holidays | External Context | Calendarific API | Airflow-triggered Spark batch | Adds country-level holiday context. |

---

## Source-to-Pipeline Mapping

The sources enter the platform through two ingestion paths.

### Streaming Sources

| Source | Kafka Topic | Processing Path | Lakehouse Target |
|---|---|---|---|
| Clickstream Events | `clickstream-events` | Spark Structured Streaming | `ecommerce.processed.clickstream_clean` |
| Web Server Logs | `webserver-logs` | Spark Structured Streaming | `ecommerce.processed.webserver_logs_clean` |
| Users CDC | `users-cdc` | Spark Structured Streaming | `ecommerce.processed.users_cdc_clean` |
| Orders CDC | `orders-cdc` | Spark Structured Streaming | `ecommerce.processed.orders_cdc_clean` |
| Order Items CDC | `order-items-cdc` | Spark Structured Streaming | `ecommerce.processed.order_items_cdc_clean` |

All Kafka messages are also preserved in:

```text
ecommerce.raw.kafka_messages
```

The raw table stores Kafka topic, partition, offset, key, value, source name, and ingestion metadata.

### Batch and Reference Sources

| Source | Processing Path | Lakehouse Target |
|---|---|---|
| Product Catalog CSV | Spark batch load | `ecommerce.processed.product_catalog_clean` |
| GeoIP Database | Spark enrichment lookup | Enriched clickstream and web log tables |
| Open-Meteo Weather API | Airflow-triggered Spark batch | `ecommerce.processed.weather_clean` |
| Calendarific Holiday API | Airflow-triggered Spark batch | `ecommerce.processed.holidays_clean` |

Product catalog, GeoIP, weather, and holidays do not enter Kafka. They are handled through controlled batch and enrichment paths.

---

## Business Key Model

The project connects source systems through stable business keys.

| Key | Source Area | Purpose |
|---|---|---|
| `event_id` | Clickstream | Unique behavioral event identifier. |
| `request_id` | Clickstream, Web Logs | Links front-end behavior with web server request evidence. |
| `session_id` | Clickstream | Groups user events into a browsing session. |
| `visitor_id` | Clickstream | Tracks visitor behavior before user identification. |
| `user_id` | Clickstream, Users, Orders | Links known users, profile history, sessions, and orders. |
| `checkout_id` | Clickstream, Orders | Connects checkout events with order records. |
| `order_id` | Orders, Order Items | Links order headers with line items. |
| `product_id` | Clickstream, Order Items, Product Catalog | Connects product behavior, product reference data, and product sales. |
| `event_timestamp` | Clickstream | Orders behavioral events and supports time-based analysis. |
| `log_timestamp` | Web Logs | Orders web request records and supports web experience analysis. |
| `source_lsn` | CDC | Preserves source database change ordering. |
| `source_ts_ms` | CDC | Captures source change timestamp from Debezium. |

---

## Relationship Contract

![Business Key Relationships](../diagrams/08_business_key_relationships.png)

The analytical model is built from the following relationships:

| Relationship | Purpose |
|---|---|
| `clickstream.request_id` → `web_logs.request_id` | Correlates user behavior with HTTP request evidence. |
| `clickstream.checkout_id` → `orders.checkout_id` | Connects checkout behavior to transactional order outcomes. |
| `clickstream.order_id` → `orders.order_id` | Connects completed checkout events with confirmed orders. |
| `orders.order_id` → `order_items.order_id` | Connects order headers with product line items. |
| `order_items.product_id` → `product_catalog.product_id` | Adds product name, category, price, and inventory attributes. |
| `clickstream.product_id` → `product_catalog.product_id` | Adds product attributes to behavioral product events. |
| `clickstream.user_id` → `user_profile_scd2.user_id` | Adds user profile context to known user behavior. |
| `orders.user_id` → `user_profile_scd2.user_id` | Adds user profile context to purchases. |
| `clickstream.geo fields` → `weather_clean` | Adds location and hour weather context. |
| `clickstream.country/date` → `holidays_clean` | Adds country and date holiday context. |

---

## Clickstream Events Contract

### Purpose

Clickstream events represent user behavior on the website or commerce application. They are the primary source for session analysis, journey analysis, funnel analysis, personalization signals, and product engagement.

### Ingestion

```text
JSONL source file
  → local publisher
  → Kafka topic clickstream-events
  → Spark Structured Streaming
  → Iceberg raw and processed tables
```

### Target Tables

| Layer | Table |
|---|---|
| Raw | `ecommerce.raw.kafka_messages` |
| Processed | `ecommerce.processed.clickstream_clean` |
| Audit | `ecommerce.audit.quarantine_records`, `ecommerce.audit.quality_metrics`, `ecommerce.audit.pipeline_runs`, `ecommerce.audit.watermarks` |

### Main Fields

| Field | Description |
|---|---|
| `event_id` | Unique event identifier. |
| `event_timestamp` | Timestamp when the event occurred. |
| `event_type` | Type of behavioral event. |
| `session_id` | Session identifier. |
| `visitor_id` | Anonymous visitor identifier. |
| `user_id` | Known user identifier when available. |
| `request_id` | Request correlation key for web log joins. |
| `product_id` | Product identifier for product-scoped events. |
| `checkout_id` | Checkout identifier for checkout-scoped events. |
| `order_id` | Order identifier for completed checkout events. |
| `page_url` | Page URL or route. |
| `referrer_url` | Referring URL or page. |
| `device_type` | Device category used by the visitor. |
| `traffic_source` | Traffic source or acquisition channel. |
| `ip_address` | IP address used for GeoIP enrichment. |
| `user_agent` | Browser or client user agent. |
| `time_on_page_seconds` | Engagement duration where available. |

### Event Types

The supported behavioral event types are:

```text
page_view
product_view
search
add_to_cart
remove_from_cart
checkout_start
checkout_complete
login
logout
scroll
```

### Validation Rules

| Rule | Requirement |
|---|---|
| Event identity | `event_id` is required. |
| Session identity | `session_id` is required. |
| Event type | `event_type` is required and must be supported. |
| Timestamp | `event_timestamp` is required and must be parseable. |
| Visitor identity | `visitor_id` is required. `user_id` is present when the visitor is known. |
| Product events | `product_id` is required for `product_view`, `add_to_cart`, and `remove_from_cart`. |
| Checkout events | `checkout_id` is required for `checkout_start` and checkout-related events. |
| Completed checkout | `order_id` is required for `checkout_complete`. |
| Deduplication | Duplicate `event_id` records are tracked and routed through quality evidence. |
| Quarantine | Invalid records are written to quarantine with reason codes. |

### Analytical Usage

Clickstream data supports:

- Session counting.
- Active user behavior.
- Returning user behavior.
- Product view analysis.
- Cart and checkout funnel analysis.
- Search behavior.
- Journey sequencing.
- Personalization candidate generation.
- Geo and context enrichment.
- Web log correlation through `request_id`.

---

## Web Server Logs Contract

### Purpose

Web server logs provide request-level operational evidence for website experience analysis. They complement clickstream events by capturing HTTP response behavior, latency, status codes, endpoints, user agents, and request correlation.

### Ingestion

```text
.log JSON lines
  → Filebeat
  → Kafka topic webserver-logs
  → Spark Structured Streaming
  → Iceberg raw and processed tables
```

### Target Tables

| Layer | Table |
|---|---|
| Raw | `ecommerce.raw.kafka_messages` |
| Processed | `ecommerce.processed.webserver_logs_clean` |
| Audit | `ecommerce.audit.quarantine_records`, `ecommerce.audit.quality_metrics`, `ecommerce.audit.pipeline_runs`, `ecommerce.audit.watermarks` |

### Main Fields

| Field | Description |
|---|---|
| `log_id` | Unique web log record identifier. |
| `request_id` | Request correlation key used to join web logs with clickstream events. |
| `log_timestamp` | Timestamp when the request was logged. |
| `ip_address` | Request IP address used for GeoIP enrichment. |
| `http_method` | HTTP method. |
| `endpoint` | Request endpoint or route. |
| `status_code` | HTTP response status code. |
| `response_time_ms` | Request latency in milliseconds. |
| `user_agent` | Request user agent. |
| `bytes_sent` | Response size in bytes. |
| `geo_country_code` | Enriched country code. |
| `geo_country_name` | Enriched country name where available. |
| `geo_city` | Enriched city. |
| `geo_latitude` | Enriched latitude. |
| `geo_longitude` | Enriched longitude. |
| `geo_timezone` | Enriched timezone. |

### Validation Rules

| Rule | Requirement |
|---|---|
| Log identity | `log_id` is required. |
| Request identity | `request_id` is required. |
| Timestamp | `log_timestamp` is required and must be parseable. |
| HTTP method | `http_method` is required. |
| Endpoint | `endpoint` is required. |
| Status code | `status_code` is required and must be numeric. |
| Response time | `response_time_ms` must be numeric when present. |
| Deduplication | Duplicate `log_id` records are tracked through quality evidence. |
| Quarantine | Invalid records are written to quarantine with reason codes. |

### Analytical Usage

Web server logs support:

- Web experience monitoring.
- Response latency analysis.
- HTTP status distribution.
- Endpoint performance analysis.
- Clickstream-to-request correlation through `request_id`.
- Country and city web traffic context.

---

## Product Catalog Contract

### Purpose

The product catalog is the static product reference source for the platform. It provides the descriptive and commercial attributes needed for product performance, funnel analysis, personalization, and Power BI reporting.

### Ingestion

```text
CSV reference file
  → Spark batch load
  → Iceberg processed table
```

### Target Table

```text
ecommerce.processed.product_catalog_clean
```

### Main Fields

| Field | Description |
|---|---|
| `product_id` | Product identifier. |
| `product_name` | Product display name. |
| `category` | Product category. |
| `price` | Product price. |
| `inventory` | Available inventory count. |
| `created_at` | Source creation timestamp. |
| `updated_at` | Source update timestamp. |
| `catalog_checksum` | Catalog row checksum used for reference integrity. |
| `loaded_at` | Timestamp when the catalog row was loaded into the lakehouse. |

### Validation Rules

| Rule | Requirement |
|---|---|
| Product identity | `product_id` is required and unique. |
| Product name | `product_name` is required. |
| Category | `category` is required. |
| Price | `price` must be non-negative. |
| Inventory | `inventory` must be non-negative. |
| Static reference | Product catalog is loaded as reference data and is not modeled as CDC. |

### Analytical Usage

Product catalog data supports:

- Product dimension creation.
- Product category analysis.
- Product performance marts.
- Revenue and units sold analysis.
- Personalization candidate enrichment.
- Power BI product slicers and dimensions.

---

## PostgreSQL Users CDC Contract

### Purpose

The users table represents user profile and account attributes. Changes are captured through Debezium CDC and used to build a clean CDC event table and an SCD Type 2 user profile dimension.

### Ingestion

```text
PostgreSQL users table
  → Debezium connector
  → Kafka topic users-cdc
  → Spark Structured Streaming
  → users_cdc_clean
  → Spark Batch SCD2
  → user_profile_scd2
```

### Target Tables

| Layer | Table |
|---|---|
| Processed CDC | `ecommerce.processed.users_cdc_clean` |
| Processed Dimension | `ecommerce.processed.user_profile_scd2` |
| Serving Dimension | `personalization_olap.v_dim_user_current` |

### Main Fields

| Field | Description |
|---|---|
| `user_id` | User identifier. |
| `email` | User email address. |
| `full_name` | User display name. |
| `membership_type` | User membership tier or segment. |
| `account_status` | User account state. |
| `country_code` | User country code. |
| `city` | User city. |
| `op` | Debezium operation code. |
| `source_lsn` | Source database log sequence number. |
| `source_ts_ms` | Source change timestamp. |
| `processed_at` | Processing timestamp. |

### CDC Operations

| Operation | Meaning |
|---|---|
| `r` | Initial Debezium snapshot record. |
| `c` | Insert. |
| `u` | Update. |
| `d` | Delete. |

### SCD Type 2 Contract

The SCD2 user profile table maintains user history through:

| Field | Description |
|---|---|
| `effective_from` | Start timestamp for the profile version. |
| `effective_to` | End timestamp for the profile version. |
| `is_current` | Indicates the active current profile row. |
| `source_lsn` | CDC ordering and lineage reference. |
| `source_ts_ms` | Source change timestamp. |

### Analytical Usage

Users CDC and SCD2 support:

- Current user dimension.
- Historical user profile tracking.
- Membership analysis.
- User segmentation.
- Order and behavior enrichment.
- Accurate user context for serving views.

---

## PostgreSQL Orders CDC Contract

### Purpose

The orders table represents order-level transactions and purchase outcomes. It is captured through Debezium CDC and used for revenue, checkout completion, conversion, and order attribution analysis.

### Ingestion

```text
PostgreSQL orders table
  → Debezium connector
  → Kafka topic orders-cdc
  → Spark Structured Streaming
  → orders_cdc_clean
```

### Target Tables

| Layer | Table |
|---|---|
| Processed CDC | `ecommerce.processed.orders_cdc_clean` |
| Serving Fact | `personalization_olap.v_fact_order` |

### Main Fields

| Field | Description |
|---|---|
| `order_id` | Order identifier. |
| `checkout_id` | Checkout identifier linking order outcome to clickstream activity. |
| `user_id` | User who placed the order. |
| `order_timestamp` | Order timestamp. |
| `order_status` | Order status. |
| `total_amount` | Order-level amount. |
| `confirmed_purchase` | Purchase confirmation flag. |
| `recognized_revenue` | Revenue recognized for confirmed orders. |
| `country_code` | Order country context. |
| `city` | Order city context. |
| `membership_type_at_order` | User membership state at order time. |
| `op` | Debezium operation code. |
| `source_lsn` | Source database ordering metadata. |
| `source_ts_ms` | Source change timestamp. |

### Validation Rules

| Rule | Requirement |
|---|---|
| Order identity | `order_id` is required. |
| Checkout identity | `checkout_id` is required when order is connected to checkout behavior. |
| User identity | `user_id` is required for user-level order analysis. |
| Amount | Monetary values must be non-negative. |
| Purchase flag | Confirmed purchase values must be normalized for analytical use. |
| CDC metadata | `source_lsn` and `source_ts_ms` are preserved for lineage and ordering. |

### Analytical Usage

Orders CDC supports:

- Purchase completion analysis.
- Revenue reporting.
- Checkout attribution.
- Order-level facts.
- User and membership revenue analysis.
- Joining checkout events to transactional outcomes.

---

## PostgreSQL Order Items CDC Contract

### Purpose

The order items table represents product-level details for orders. It is captured through Debezium CDC and supports product revenue, units sold, category performance, and product-level attribution.

### Ingestion

```text
PostgreSQL order_items table
  → Debezium connector
  → Kafka topic order-items-cdc
  → Spark Structured Streaming
  → order_items_cdc_clean
```

### Target Tables

| Layer | Table |
|---|---|
| Processed CDC | `ecommerce.processed.order_items_cdc_clean` |
| Serving Fact | `personalization_olap.v_fact_order_item` |

### Main Fields

| Field | Description |
|---|---|
| `order_item_id` | Order item identifier. |
| `order_id` | Parent order identifier. |
| `product_id` | Purchased product identifier. |
| `quantity` | Quantity purchased. |
| `unit_price` | Unit price at purchase time. |
| `line_total` | Quantity multiplied by unit price. |
| `op` | Debezium operation code. |
| `source_lsn` | Source database ordering metadata. |
| `source_ts_ms` | Source change timestamp. |

### Validation Rules

| Rule | Requirement |
|---|---|
| Order item identity | `order_item_id` is required. |
| Order relationship | `order_id` is required. |
| Product relationship | `product_id` is required. |
| Quantity | `quantity` must be positive. |
| Price | `unit_price` must be non-negative. |
| Line total | `line_total` must be non-negative. |
| CDC metadata | CDC ordering and timestamp metadata are preserved. |

### Analytical Usage

Order items CDC supports:

- Product-level sales analysis.
- Units sold.
- Revenue by product and category.
- Product performance marts.
- Joining transactions with product catalog attributes.

---

## GeoIP Enrichment Contract

### Purpose

GeoIP enrichment converts IP addresses into geographical context for behavioral and web experience analysis.

### Source

```text
MaxMind GeoLite2 City database
```

### Enrichment Outputs

| Field | Description |
|---|---|
| `geo_country_code` | Country code derived from IP address. |
| `geo_country_name` | Country name where available. |
| `geo_city` | City derived from IP address. |
| `geo_latitude` | Latitude coordinate. |
| `geo_longitude` | Longitude coordinate. |
| `geo_timezone` | Timezone where available. |

### Usage

GeoIP enrichment is applied to:

```text
clickstream_clean
webserver_logs_clean
```

### Analytical Usage

GeoIP enrichment supports:

- Country-level traffic analysis.
- City-level engagement analysis.
- Weather enrichment location matching.
- Holiday context by country.
- Geographic dashboard slicers and visuals.

---

## Weather Context Contract

### Purpose

Weather context adds environmental signals to user behavior and session analysis. Weather enrichment is performed as a scheduled batch job using distinct location and hour combinations observed in clean clickstream data.

### Source

```text
Open-Meteo historical weather API
```

### Target Table

```text
ecommerce.processed.weather_clean
```

### Main Fields

| Field | Description |
|---|---|
| `weather_key` | Stable key for location and weather hour. |
| `latitude` | Latitude used for API lookup. |
| `longitude` | Longitude used for API lookup. |
| `weather_hour` | Hourly weather timestamp. |
| `temperature_c` | Temperature in Celsius. |
| `precipitation_mm` | Precipitation in millimeters. |
| `weather_code` | Weather condition code. |
| `weather_condition` | Weather condition label. |
| `coverage_status` | Coverage status for the weather lookup. |
| `fetched_at` | Timestamp when the enrichment was fetched. |

### Analytical Usage

Weather context supports:

- Weather impact analysis.
- Context-aware engagement analysis.
- Weather and product behavior comparison.
- Contextual dashboard visuals.

---

## Holiday Context Contract

### Purpose

Holiday context adds country-level calendar signals to user behavior and revenue analysis. Holiday enrichment is performed through scheduled batch processing based on countries and years observed in clean analytical data.

### Source

```text
Calendarific API
```

### Target Table

```text
ecommerce.processed.holidays_clean
```

### Main Fields

| Field | Description |
|---|---|
| `holiday_key` | Stable key for country and holiday date. |
| `country_code` | Country code. |
| `holiday_date` | Holiday date. |
| `holiday_name` | Holiday name. |
| `holiday_type` | Holiday category or type. |
| `year` | Holiday year. |
| `coverage_status` | Coverage status for the holiday enrichment record. |
| `fetched_at` | Timestamp when the enrichment was fetched. |

### Analytical Usage

Holiday context supports:

- Holiday impact analysis.
- Country-level context analysis.
- Revenue and engagement comparison by holiday period.
- Context-aware Power BI reporting.

---

## Kafka Topic Contract

The platform separates business data topics from Kafka Connect internal topics.

### Business Topics

| Topic | Source |
|---|---|
| `clickstream-events` | Clickstream event publisher. |
| `webserver-logs` | Filebeat web log shipper. |
| `users-cdc` | Debezium users connector. |
| `orders-cdc` | Debezium orders connector. |
| `order-items-cdc` | Debezium order items connector. |

### Kafka Connect Internal Topics

| Topic | Purpose |
|---|---|
| `debezium-connect-configs` | Kafka Connect connector configuration state. |
| `debezium-connect-offsets` | Kafka Connect source offset tracking. |
| `debezium-connect-status` | Kafka Connect connector and task status. |

Business topics are consumed by Spark Structured Streaming. Kafka Connect internal topics are managed by Debezium Connect and are not part of the analytical model.

---

## Clean Table Contract

The processed lakehouse tables represent the clean analytical contract.

| Clean Table | Built From | Main Purpose |
|---|---|---|
| `product_catalog_clean` | Product Catalog CSV | Product reference dimension. |
| `clickstream_clean` | Clickstream Kafka topic | Behavioral event analytics. |
| `webserver_logs_clean` | Web log Kafka topic | Web experience analytics. |
| `users_cdc_clean` | Users CDC topic | User CDC event history. |
| `orders_cdc_clean` | Orders CDC topic | Order CDC event history. |
| `order_items_cdc_clean` | Order Items CDC topic | Order item CDC event history. |
| `user_profile_scd2` | Users CDC clean table | Historical and current user profile dimension. |
| `weather_clean` | Open-Meteo API | Weather context. |
| `holidays_clean` | Calendarific API | Holiday context. |

---

## Quarantine Contract

Invalid and duplicate records are not silently discarded. They are written to audit evidence.

Target table:

```text
ecommerce.audit.quarantine_records
```

### Quarantine Fields

| Field | Description |
|---|---|
| `source_name` | Source or topic that produced the record. |
| `record_key` | Source-level record identifier where available. |
| `reason_code` | Structured reason for quarantine. |
| `raw_payload` | Raw record payload or representative payload. |
| `quarantined_at` | Timestamp when the record was quarantined. |
| `pipeline_run_id` | Pipeline run associated with the quarantine record. |

### Quarantine Categories

| Category | Meaning |
|---|---|
| Invalid records | Records that fail required field, type, timestamp, or source-specific validation. |
| Duplicate records | Records identified as duplicates by source-level identifiers. |
| Parse failures | Records that cannot be parsed into the expected structure. |
| Contract violations | Records that violate event-specific or CDC-specific expectations. |

---

## Data Quality Contract

The data quality model uses explicit reconciliation:

```text
Input records = Accepted records + Rejected records + Duplicate records
```

Quality metrics are recorded in:

```text
ecommerce.audit.quality_metrics
```

### Quality Metric Fields

| Field | Description |
|---|---|
| `pipeline_run_id` | Pipeline run identifier. |
| `source_name` | Source being measured. |
| `input_records` | Number of records read from the source. |
| `accepted_records` | Number of records written to clean tables. |
| `rejected_records` | Number of invalid records routed to quarantine. |
| `duplicate_records` | Number of duplicate records detected. |
| `recorded_at` | Metric timestamp. |

The quality contract makes ingestion behavior measurable, auditable, and suitable for operational evidence.

---

## Serving Source Contract

ClickHouse serving outputs are built from clean Iceberg data and published by the `publish_serving` Spark job.

Power BI consumes only stable ClickHouse `v_*` views.

### Final Serving Views

| View | Analytical Role |
|---|---|
| `v_dim_date` | Date dimension. |
| `v_dim_product` | Product dimension. |
| `v_dim_user_current` | Current user profile dimension. |
| `v_fact_clickstream_event` | Clickstream event fact. |
| `v_fact_order` | Order fact. |
| `v_fact_order_item` | Order item fact. |
| `v_mart_journey_session` | Session-level journey mart. |
| `v_mart_navigation_paths` | Navigation path mart. |
| `v_mart_product_performance_daily` | Daily product performance mart. |
| `v_mart_web_experience_daily` | Daily web experience mart. |
| `v_mart_context_impact_daily` | Daily context impact mart. |
| `v_mart_personalization_candidates` | Personalization candidate mart. |

The serving view contract keeps the BI model stable and prevents Power BI from depending on raw, internal, or audit storage layers.

---

## Source Ownership Boundaries

The platform maintains clear ownership boundaries between source data, processing outputs, and serving views.

| Layer | Owns | Does Not Own |
|---|---|---|
| Source systems | Original events, logs, relational records, reference files, and context APIs. | Clean analytics tables or dashboard logic. |
| Kafka | Transport of streaming source records. | Final analytical storage or BI semantics. |
| Spark Streaming | Continuous parsing, validation, enrichment, deduplication, and clean table writes. | Dashboard calculations. |
| Spark Batch | SCD2, external context enrichment, validation, and serving publication. | User-facing dashboard layout. |
| Iceberg | Raw, processed, quarantine, and audit table storage. | Power BI presentation model. |
| ClickHouse | Curated serving tables and stable `v_*` reporting views. | Raw ingestion storage. |
| Power BI | Semantic measures, ratios, slicers, visuals, and dashboard pages. | Raw pipeline processing. |

---

## Contract Summary

The source contract can be summarized as:

```text
Behavioral data      → Clickstream Kafka topic
Operational logs     → Filebeat Kafka topic
Transactional data   → Debezium CDC Kafka topics
Reference data       → Spark batch load
Geo context          → Local GeoIP enrichment
Weather context      → Scheduled API enrichment
Holiday context      → Scheduled API enrichment
        ↓
Spark processing
        ↓
Iceberg raw, processed, quarantine, and audit tables
        ↓
ClickHouse serving views
        ↓
Power BI dashboard
```

The project uses source-specific validation rules, stable business keys, CDC metadata, and audit evidence to keep the analytical model consistent from ingestion through reporting.
