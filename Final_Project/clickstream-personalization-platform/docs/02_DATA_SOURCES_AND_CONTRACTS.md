# Data Sources and Contracts

## 1. Purpose

This document defines the approved data sources, source contracts, business keys, validation expectations, and downstream usage for the Clickstream Personalization Platform.

The project uses heterogeneous sources deliberately. Each source has a different ingestion style and business purpose. The contracts in this document prevent ambiguity between raw source files, Kafka topics, CDC payloads, local reference data, external APIs, clean Iceberg tables, and serving-layer outputs.

---

## 2. Source Summary

| Source | Source category | Format | Ingestion method | Target |
|---|---|---|---|---|
| Clickstream Events | Behavioral events | JSONL | Direct publisher to Kafka | `clickstream-events` |
| Web Server Logs | Infrastructure logs | Structured JSON `.log` | Filebeat to Kafka | `webserver-logs` |
| Product Catalog | Reference/master data | CSV | Static Spark batch load | `product_catalog_clean` |
| Users | Master data | PostgreSQL table | Debezium CDC to Kafka | `users-cdc`, `users_cdc_clean`, `user_profile_scd2` |
| Orders | Transactional data | PostgreSQL table | Debezium CDC to Kafka | `orders-cdc`, `orders_cdc_clean` |
| Order Items | Transactional line items | PostgreSQL table | Debezium CDC to Kafka | `order-items-cdc`, `order_items_cdc_clean` |
| GeoLite2 City | Local reference data | `.mmdb` | Local Spark lookup | Geo fields in clean clickstream and web logs |
| Open-Meteo | External context | JSON API | Scheduled Spark batch API pull | `weather_clean` |
| Calendarific | External context | JSON API | Scheduled Spark batch API pull | `holidays_clean` |

---

## 3. Global Business Keys

| Key | Used by | Purpose |
|---|---|---|
| `event_id` | Clickstream | Primary identifier for clickstream events and clickstream duplicate detection. |
| `log_id` | Web logs | Primary identifier for web server log records and web log duplicate detection. |
| `request_id` | Clickstream and web logs | Correlates user-facing behavior with server-side request performance. |
| `session_id` | Clickstream | Groups user events into journeys. |
| `visitor_id` | Clickstream | Identifies a visitor independent from account-level user identity. |
| `user_id` | Clickstream, users, orders | Connects user behavior, user profiles, and orders. |
| `checkout_id` | Clickstream and orders | Connects checkout events to order records. |
| `order_id` | Clickstream, orders, order items | Connects checkout completion, order headers, and order lines. |
| `order_item_id` | Order items | Primary identifier for order line records. |
| `product_id` | Clickstream, product catalog, order items | Connects product behavior, catalog attributes, and purchased items. |
| `ip_address` | Clickstream and web logs | Input to GeoLite2 enrichment. |
| `latitude`, `longitude`, `weather_hour` | Clickstream clean and weather | Join keys for weather context. |
| `country_code`, `holiday_date` | Clickstream clean and holidays | Join keys for holiday context. |

---

## 4. Clickstream Events Contract

### 4.1 Source purpose

Clickstream events represent client-side website behavior. They capture how users move through the website, what products they view, when they start checkout, and whether they complete purchase-related events.

### 4.2 Source format and ingestion

| Attribute | Value |
|---|---|
| Source file | `data/source/clickstream/clickstream_events.jsonl` |
| Topic | `clickstream-events` |
| Format | One JSON object per line |
| Ingestion | Direct Kafka publisher |
| Processing | Spark Structured Streaming |
| Clean target | `ecommerce.processed.clickstream_clean` |

### 4.3 Main fields

| Field | Purpose |
|---|---|
| `contract_version` | Source contract version. |
| `event_id` | Primary event identifier. |
| `event_timestamp` | Event occurrence time. |
| `session_id` | Journey/session grouping key. |
| `visitor_id` | Visitor identifier. |
| `user_id` | Authenticated user identifier when available. |
| `event_type` | Behavioral event type. |
| `page_url` | Page or endpoint path visible to the user. |
| `search_query` | Search term for search events. |
| `product_id` | Product key for product-related events. |
| `checkout_id` | Checkout key for checkout events. |
| `order_id` | Order key for checkout completion events. |
| `request_id` | Correlation key to web server logs for HTTP-backed events. |
| `ip_address` | Input for GeoIP enrichment. |
| `device_type`, `browser`, `operating_system` | Client context fields. |
| `traffic_source` | Marketing or traffic source. |
| `scroll_depth_pct` | Scroll engagement measure for scroll events. |
| `time_on_page_seconds` | Page engagement duration. |

### 4.4 Supported event types

```text
page_view
product_view
search
scroll
add_to_cart
remove_from_cart
checkout_start
checkout_complete
login
logout
```

### 4.5 Validation rules

The streaming pipeline validates clickstream records before writing clean data.

| Rule | Reason |
|---|---|
| `event_id` is required | Needed for identity and deduplication. |
| `session_id` is required | Needed for journey analysis. |
| `event_type` is required and must be supported | Prevents unknown behavior categories from entering clean analytics. |
| Product-related events require `product_id` | Required for product analysis and product dimension joins. |
| Checkout events require `checkout_id` | Required for funnel and order correlation. |
| `checkout_complete` requires `order_id` | Required for purchase completion correlation. |
| Source contract version must be supported | Prevents incompatible schema versions from being accepted silently. |
| Duplicate `event_id` is rejected | Preserves one accepted event per event identifier. |

### 4.6 Downstream usage

Clean clickstream events support:

- Funnel metrics.
- Session journeys.
- Navigation paths.
- Product engagement.
- User behavior analysis.
- Geo/context enrichment.
- Personalization candidate logic.
- Request correlation with web logs through `request_id`.
- Order correlation through `checkout_id` and `order_id`.

---

## 5. Web Server Logs Contract

### 5.1 Source purpose

Web server logs represent server-side request evidence. They provide operational context such as HTTP method, endpoint, status code, response time, user agent, and bytes sent.

### 5.2 Source format and ingestion

| Attribute | Value |
|---|---|
| Source file | `data/source/web_logs/webserver_access.log` |
| Topic | `webserver-logs` |
| Format | Structured JSON records stored as `.log` lines |
| Ingestion | Filebeat tails the `.log` file and publishes to Kafka |
| Processing | Spark Structured Streaming |
| Clean target | `ecommerce.processed.webserver_logs_clean` |

### 5.3 Main fields

| Field | Purpose |
|---|---|
| `contract_version` | Source contract version. |
| `log_id` | Primary log record identifier. |
| `request_id` | Correlation key to clickstream events. |
| `timestamp` | Server request time. |
| `ip_address` | Input to GeoIP enrichment. |
| `http_method` | Request method. |
| `endpoint` | Requested endpoint. |
| `status_code` | HTTP status code. |
| `response_time_ms` | Server response duration. |
| `user_agent` | Client user agent string. |
| `bytes_sent` | Response payload size. |

### 5.4 Validation rules

| Rule | Reason |
|---|---|
| `log_id` is required | Needed for identity and duplicate detection. |
| `request_id` is required | Needed for clickstream correlation. |
| `status_code` must be valid | Prevents impossible HTTP status values. |
| Contract version must be supported | Prevents incompatible log schemas. |
| Duplicate `log_id` is rejected | Prevents duplicate server-side request evidence. |

### 5.5 Downstream usage

Web logs are joined or aligned with clickstream behavior to analyze:

- Endpoint performance.
- HTTP error context.
- Response time impact.
- Request correlation coverage.
- Web experience metrics by date, endpoint, status code, and context.

---

## 6. Product Catalog Contract

### 6.1 Source purpose

Product Catalog is static reference data for product attributes. It is used to classify product behavior, product revenue, product engagement, and product performance.

### 6.2 Source format and ingestion

| Attribute | Value |
|---|---|
| Source file | `data/reference/product_catalog.csv` |
| Format | CSV with header |
| Mode | Static initial clean load only |
| Processing | Spark batch during lakehouse bootstrap |
| Clean target | `ecommerce.processed.product_catalog_clean` |

### 6.3 Main fields

| Field | Purpose |
|---|---|
| `product_id` | Product primary key. |
| `product_name` | Display name. |
| `category` | Product category. |
| `price` | Product reference price. |
| `inventory` | Available inventory snapshot. |
| `created_at`, `updated_at` | Reference timestamps. |

The clean Iceberg table also stores `catalog_checksum` and `loaded_at` so the static file can be verified against the generation manifest.

### 6.4 Validation rules

| Rule | Reason |
|---|---|
| Product ID is required | Needed for joins. |
| Product ID must be unique | Prevents ambiguous product dimension rows. |
| Product name and category are required | Needed for reporting. |
| Price must not be negative | Prevents invalid revenue calculations. |
| Inventory must not be negative | Prevents invalid stock interpretation. |
| Checksum must match manifest | Confirms the static reference file was not changed unexpectedly. |

### 6.5 Downstream usage

Product Catalog joins to clickstream product events and order items through `product_id`. It supports product dimensions, category analysis, product performance marts, and personalization candidate outputs.

---

## 7. PostgreSQL Users CDC Contract

### 7.1 Source purpose

The Users source provides customer profile state and profile changes. It is seeded into PostgreSQL and then captured through Debezium CDC.

### 7.2 Source format and ingestion

| Attribute | Value |
|---|---|
| Source table | `public.users` |
| Seed file | `data/source/postgres/users_seed.csv` |
| CDC topic | `users-cdc` |
| CDC tool | Debezium Connect |
| Clean CDC target | `ecommerce.processed.users_cdc_clean` |
| SCD2 target | `ecommerce.processed.user_profile_scd2` |

### 7.3 Main user fields

| Field | Purpose |
|---|---|
| `user_id` | User primary key. |
| `email` | User email. |
| `first_name`, `last_name` | Name attributes. |
| `membership_type` | User segment. |
| `account_status` | Active/inactive status. |
| `country_code`, `city` | Profile location attributes. |
| `created_at`, `updated_at` | Source timestamps. |

### 7.4 CDC metadata fields preserved

| Field | Purpose |
|---|---|
| `operation` | Debezium operation code such as snapshot/read, create, update, delete. |
| `before_json` | Previous row state. |
| `after_json` | New row state. |
| `source_lsn` | PostgreSQL log sequence position. |
| `source_ts_ms` | Source event timestamp in milliseconds. |
| `kafka_topic`, `kafka_partition`, `kafka_offset` | Kafka traceability metadata. |
| `source_record_id` | Source-level record identifier. |

### 7.5 SCD Type 2 behavior

Only Users are modeled as SCD Type 2. The SCD2 job reads `users_cdc_clean`, orders changes by CDC metadata, and writes versioned profile rows to `user_profile_scd2`.

The SCD2 table includes:

- `effective_from`.
- `effective_to`.
- `is_current`.
- `version_sequence`.
- `is_deleted`.
- `source_lsn`.

This preserves historical user profile changes while still allowing ClickHouse to publish a current-user dimension for dashboard use.

---

## 8. PostgreSQL Orders CDC Contract

### 8.1 Source purpose

Orders represent transaction headers. They provide order-level status, payment state, currency, totals, checkout linkage, and revenue information.

### 8.2 Source format and ingestion

| Attribute | Value |
|---|---|
| Source table | `public.orders` |
| Seed file | `data/source/postgres/orders_seed.csv` |
| CDC topic | `orders-cdc` |
| CDC tool | Debezium Connect |
| Clean target | `ecommerce.processed.orders_cdc_clean` |

### 8.3 Main fields

| Field | Purpose |
|---|---|
| `order_id` | Order primary key. |
| `user_id` | User who owns the order. |
| `checkout_id` | Checkout correlation key. |
| `order_timestamp` | Order time. |
| `order_status` | Business order state. |
| `payment_status` | Payment outcome. |
| `currency` | Currency code. |
| `subtotal_amount`, `discount_amount`, `tax_amount`, `shipping_amount`, `total_amount` | Financial measures. |
| `created_at`, `updated_at` | Source timestamps. |

### 8.4 Downstream usage

Orders are used to build the ClickHouse order fact, revenue metrics, checkout completion analysis, and session/order correlation through `checkout_id` and `order_id`.

Orders are not modeled as SCD2 in this project. CDC changes are preserved in the clean CDC table and later transformed into serving facts.

---

## 9. PostgreSQL Order Items CDC Contract

### 9.1 Source purpose

Order Items represent line-level purchase detail. They connect orders to products and quantify purchased items.

### 9.2 Source format and ingestion

| Attribute | Value |
|---|---|
| Source table | `public.order_items` |
| Seed file | `data/source/postgres/order_items_seed.csv` |
| CDC topic | `order-items-cdc` |
| CDC tool | Debezium Connect |
| Clean target | `ecommerce.processed.order_items_cdc_clean` |

### 9.3 Main fields

| Field | Purpose |
|---|---|
| `order_item_id` | Order item primary key. |
| `order_id` | Parent order key. |
| `product_id` | Purchased product key. |
| `quantity` | Purchased quantity. |
| `unit_price` | Unit price at order time. |
| `line_total` | Line-level revenue. |
| `created_at`, `updated_at` | Source timestamps. |

### 9.4 Downstream usage

Order Items support product revenue, product conversion, order composition, and joins between order facts and product dimensions.

---

## 10. GeoLite2 City Contract

### 10.1 Source purpose

GeoLite2 City is a local reference database used to convert `ip_address` values into geographic context.

### 10.2 Source format and usage

| Attribute | Value |
|---|---|
| File path | `data/reference/GeoLite2-City.mmdb` |
| Format | MaxMind `.mmdb` |
| Mode | Local reference lookup |
| Used by | Spark Structured Streaming |
| Output fields | country code, country name, city, latitude, longitude, timezone |

### 10.3 Important contract rule

Source records contain `ip_address` only. Country and city are not trusted from generated source files. Geo fields are produced by Spark lookup using the local GeoLite2 database.

### 10.4 Downstream usage

Geo fields support:

- Country and city segmentation.
- Weather enrichment keys through latitude and longitude.
- Holiday enrichment keys through country code and local date logic.
- Context impact analysis in ClickHouse marts.

---

## 11. Open-Meteo Weather Contract

### 11.1 Source purpose

Open-Meteo provides historical weather context for observed clickstream locations and event hours.

### 11.2 Source format and usage

| Attribute | Value |
|---|---|
| API | Open-Meteo Historical Weather API |
| API key | Not required |
| Mode | Scheduled Spark batch pull |
| Input keys | latitude, longitude, weather hour/date range |
| Clean target | `ecommerce.processed.weather_clean` |

### 11.3 Output fields

| Field | Purpose |
|---|---|
| `weather_key` | Unique weather record key. |
| `latitude`, `longitude` | Weather location keys. |
| `weather_hour` | Hourly weather timestamp. |
| `temperature_c` | Temperature in Celsius. |
| `precipitation_mm` | Precipitation amount. |
| `weather_code` | Weather code from provider. |
| `weather_condition` | Interpreted weather condition. |
| `coverage_status` | Indicates API coverage status. |
| `fetched_at` | Batch fetch timestamp. |

### 11.4 Current-day behavior

The project uses a historical weather archive. Current or future UTC timestamps are intentionally skipped and recorded as external API evidence with status `SKIPPED`. This is expected behavior, not a platform failure.

---

## 12. Calendarific Holiday Contract

### 12.1 Source purpose

Calendarific provides public holiday context by country and year. This allows behavior to be analyzed alongside holiday calendars.

### 12.2 Source format and usage

| Attribute | Value |
|---|---|
| API | Calendarific |
| API key | Required in `.env` as `CALENDARIFIC_API_KEY` |
| Mode | Scheduled Spark batch pull |
| Input keys | country code and year |
| Clean target | `ecommerce.processed.holidays_clean` |

### 12.3 Output fields

| Field | Purpose |
|---|---|
| `holiday_key` | Unique holiday record key. |
| `country_code` | Country code. |
| `holiday_date` | Holiday date. |
| `holiday_name` | Holiday name. |
| `holiday_type` | Holiday type/category. |
| `year` | Calendar year. |
| `coverage_status` | API coverage status. |
| `fetched_at` | Batch fetch timestamp. |

---

## 13. Source Generation Counts

The deterministic source generation settings are defined in `config/settings.yaml`.

| Setting | Value |
|---|---:|
| Product catalog count | 72 |
| User count | 96 |
| Order count | 48 |
| Order item count | 96 |
| Abandoned session count | 24 |
| Browsing session count | 24 |
| Invalid clickstream records | 5 |
| Duplicate clickstream records | 2 |
| Invalid web log records | 4 |
| Duplicate web log records | 2 |
| Late event count | 2 |

The source files intentionally include valid, invalid, duplicate, and late-arrival examples. This is required for proving quality controls and quarantine behavior.

---

## 14. Downstream Relationship Map

| Relationship | Key |
|---|---|
| Clickstream to web logs | `request_id` |
| Clickstream to users | `user_id` |
| Clickstream to orders | `checkout_id`, `order_id` |
| Orders to order items | `order_id` |
| Order items to product catalog | `product_id` |
| Clickstream product events to product catalog | `product_id` |
| Clickstream and web logs to GeoIP | `ip_address` |
| Clickstream clean to weather | rounded latitude, rounded longitude, event hour |
| Clickstream clean to holidays | country code and local event date/year |

---

## 15. Contract Boundaries

The following boundaries are important:

- Raw source files are not final analytical tables.
- Kafka topics are transport contracts, not dashboard models.
- CDC clean tables preserve change events, not only current state.
- `user_profile_scd2` is the historical user profile table.
- ClickHouse `dim_user_current` is the current user dimension for a serving build, not the full SCD2 table.
- `v_*` ClickHouse views expose the latest active serving build.
- Power BI must not connect directly to raw Kafka, PostgreSQL source tables, or Iceberg raw/audit tables.
