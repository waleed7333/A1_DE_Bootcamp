
# Data Sources and Contracts

## 1. Purpose

This document defines the approved project data sources, source formats, ingestion paths, keys, event types, CDC contracts, and validation rules.

Pipeline implementation details are documented in:

```text
docs/03_PIPELINES_QUALITY_AND_LAKEHOUSE.md
```

---

## 2. Approved Data Sources

| # | Source             | Format                            | Ingestion Mode             | Target                     |
| - | ------------------ | --------------------------------- | -------------------------- | -------------------------- |
| 1 | Clickstream Events | JSONL                             | Streaming through Kafka    | `clickstream-events`       |
| 2 | Web Server Logs    | Structured `.log` NDJSON          | Filebeat to Kafka          | `webserver-logs`           |
| 3 | Product Catalog    | CSV                               | Static initial batch load  | `product_catalog_clean`    |
| 4 | Users              | PostgreSQL table                  | Debezium CDC               | `users-cdc`                |
| 5 | Orders             | PostgreSQL table                  | Debezium CDC               | `orders-cdc`               |
| 6 | Order Items        | PostgreSQL table                  | Debezium CDC               | `order-items-cdc`          |
| 7 | GeoIP              | MaxMind GeoLite2 City `.mmdb`     | Local enrichment reference | Geo fields in clean tables |
| 8 | Weather            | Open-Meteo Historical Weather API | Scheduled batch enrichment | `weather_clean`            |
| 9 | Holidays           | Calendarific API                  | Scheduled batch enrichment | `holidays_clean`           |

---

## 3. Kafka Topics

### 3.1 Business topics

```text
clickstream-events
webserver-logs
users-cdc
orders-cdc
order-items-cdc
```

### 3.2 Debezium internal topics

```text
debezium-connect-configs
debezium-connect-offsets
debezium-connect-status
```

---

## 4. Clickstream Events Contract

### 4.1 Source

```text
data/source/clickstream/clickstream_events.jsonl
```

### 4.2 Kafka topic

```text
clickstream-events
```

### 4.3 Key fields

| Field             | Purpose                                      |
| ----------------- | -------------------------------------------- |
| `event_id`        | Unique event identifier                      |
| `session_id`      | Website session identifier                   |
| `visitor_id`      | Anonymous visitor identifier                 |
| `user_id`         | Authenticated user identifier when available |
| `request_id`      | Correlation key with web server logs         |
| `product_id`      | Product behavior key                         |
| `checkout_id`     | Checkout journey key                         |
| `order_id`        | Completed checkout to order key              |
| `event_timestamp` | Source event time                            |
| `ip_address`      | GeoIP enrichment input                       |

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

### 4.5 Main source fields

```text
contract_version
event_id
event_timestamp
session_id
visitor_id
user_id
event_type
page_url
search_query
product_id
checkout_id
order_id
request_id
ip_address
device_type
browser
operating_system
traffic_source
scroll_depth_pct
time_on_page_seconds
```

### 4.6 Validation rules

| Rule                     | Description                                                                |
| ------------------------ | -------------------------------------------------------------------------- |
| Required identifiers     | `event_id`, `session_id`, and `event_type` must exist                      |
| User or visitor identity | At least one of `user_id` or `visitor_id` must be present                  |
| Event type contract      | `event_type` must be one of the supported event types                      |
| Product events           | Product-related events require `product_id`                                |
| Checkout start           | Checkout start events require `checkout_id`                                |
| Checkout complete        | Checkout complete events require `checkout_id` and `order_id`              |
| Timestamp                | `event_timestamp` must be parseable                                        |
| Duplicate handling       | Duplicate `event_id` records are excluded from clean analytics and tracked |

---

## 5. Web Server Logs Contract

### 5.1 Source

```text
data/source/web_logs/webserver_access.log
```

### 5.2 Kafka topic

```text
webserver-logs
```

### 5.3 Main source fields

```text
contract_version
log_id
request_id
timestamp
ip_address
http_method
endpoint
status_code
response_time_ms
user_agent
bytes_sent
```

### 5.4 Key fields

| Field              | Purpose                                 |
| ------------------ | --------------------------------------- |
| `log_id`           | Unique log identifier                   |
| `request_id`       | Correlation key with clickstream events |
| `timestamp`        | Source log time                         |
| `ip_address`       | GeoIP enrichment input                  |
| `endpoint`         | Requested server endpoint               |
| `status_code`      | HTTP response status                    |
| `response_time_ms` | Technical performance metric            |

### 5.5 Validation rules

| Rule                 | Description                                                              |
| -------------------- | ------------------------------------------------------------------------ |
| Required identifiers | `log_id` and `request_id` must exist                                     |
| Timestamp            | `timestamp` must be parseable                                            |
| HTTP status          | `status_code` must be valid                                              |
| Response time        | `response_time_ms` must be numeric                                       |
| Duplicate handling   | Duplicate `log_id` records are excluded from clean analytics and tracked |

---

## 6. Product Catalog Contract

### 6.1 Source

```text
data/source/product_catalog.csv
```

### 6.2 Processing mode

Product Catalog is a static initial CSV load.

It is not a streaming source and not a CDC source.

### 6.3 Main fields

```text
product_id
product_name
category
price
inventory
created_at
updated_at
```

### 6.4 Validation rules

| Rule         | Description                                  |
| ------------ | -------------------------------------------- |
| Product key  | `product_id` must be present and unique      |
| Product name | `product_name` must be present               |
| Category     | `category` must be present                   |
| Price        | `price` must be numeric and non-negative     |
| Inventory    | `inventory` must be numeric and non-negative |

---

## 7. PostgreSQL CDC Contracts

PostgreSQL is used as the source system for:

```text
public.users
public.orders
public.order_items
```

Changes are captured by Debezium and published to Kafka.

### 7.1 CDC operation values

| Operation | Meaning       |
| --------- | ------------- |
| `r`       | Snapshot read |
| `c`       | Create        |
| `u`       | Update        |
| `d`       | Delete        |

### 7.2 CDC metadata preserved

```text
operation
before_json
after_json
source_lsn
source_ts_ms
kafka_topic
kafka_partition
kafka_offset
source_record_id
processed_at
```

---

## 8. Users Contract

### 8.1 Source table

```text
public.users
```

### 8.2 Kafka topic

```text
users-cdc
```

### 8.3 Main fields

```text
user_id
email
first_name
last_name
membership_type
account_status
country_code
city
created_at
updated_at
```

### 8.4 Target tables

```text
processed.users_cdc_clean
processed.user_profile_scd2
```

### 8.5 SCD Type 2 behavior

User Profile changes are converted into SCD Type 2 records by a scheduled Spark batch job.

SCD2 applies only to Users.

---

## 9. Orders Contract

### 9.1 Source table

```text
public.orders
```

### 9.2 Kafka topic

```text
orders-cdc
```

### 9.3 Main fields

```text
order_id
user_id
checkout_id
order_timestamp
order_status
payment_status
currency
subtotal_amount
discount_amount
tax_amount
shipping_amount
total_amount
created_at
updated_at
```

### 9.4 Target table

```text
processed.orders_cdc_clean
```

Orders are used for serving facts and marts. They are not modeled as SCD Type 2.

---

## 10. Order Items Contract

### 10.1 Source table

```text
public.order_items
```

### 10.2 Kafka topic

```text
order-items-cdc
```

### 10.3 Main fields

```text
order_item_id
order_id
product_id
quantity
unit_price
line_total
created_at
updated_at
```

### 10.4 Target table

```text
processed.order_items_cdc_clean
```

Order Items are used for transaction line analysis and product revenue analysis. They are not modeled as SCD Type 2.

---

## 11. GeoIP Contract

### 11.1 Source

```text
data/reference/GeoLite2-City.mmdb
```

### 11.2 Enrichment input

```text
ip_address
```

### 11.3 Enrichment output fields

```text
geo_country_code
geo_country_name
geo_city
geo_latitude
geo_longitude
geo_timezone
```

GeoIP enrichment is applied to clickstream events and web server logs.

---

## 12. Weather Contract

### 12.1 Source

```text
Open-Meteo Historical Weather API
```

### 12.2 Key construction

Weather enrichment is based on:

```text
rounded geo_latitude
rounded geo_longitude
event hour
```

### 12.3 Target table

```text
processed.weather_clean
```

### 12.4 Main target fields

```text
weather_key
latitude
longitude
weather_hour
temperature_c
precipitation_mm
weather_code
weather_condition
coverage_status
fetched_at
```

### 12.5 Operational behavior

Current-day weather can be unavailable by design when using a historical weather archive. This is treated as an expected coverage behavior, not as a pipeline failure.

---

## 13. Holiday Contract

### 13.1 Source

```text
Calendarific API
```

### 13.2 Key construction

Holiday enrichment is based on:

```text
country_code
year
```

### 13.3 Target table

```text
processed.holidays_clean
```

### 13.4 Main target fields

```text
holiday_key
country_code
holiday_date
holiday_name
holiday_type
year
coverage_status
fetched_at
```

---

## 14. Business Key Relationships

| Relationship                                            | Purpose                                                  |
| ------------------------------------------------------- | -------------------------------------------------------- |
| `clickstream.request_id` ↔ `web_logs.request_id`        | Correlates user behavior with server request performance |
| `clickstream.user_id` ↔ `users.user_id`                 | Adds user profile and segment context                    |
| `orders.user_id` ↔ `users.user_id`                      | Connects users to transactions                           |
| `clickstream.checkout_id` ↔ `orders.checkout_id`        | Connects checkout journey to order                       |
| `clickstream.order_id` ↔ `orders.order_id`              | Connects completed checkout event to order               |
| `orders.order_id` ↔ `order_items.order_id`              | Connects order header to line items                      |
| `clickstream.product_id` ↔ `product_catalog.product_id` | Connects behavior to product attributes                  |
| `order_items.product_id` ↔ `product_catalog.product_id` | Connects revenue to product attributes                   |
| `ip_address` → GeoLite2                                 | Adds country, city, coordinates, and timezone            |
| Geo coordinates + event hour ↔ Weather                  | Adds weather context                                     |
| Country + local event date ↔ Holidays                   | Adds holiday context                                     |

Recommended diagram:

```text
diagrams/08_business_key_relationships.png
```

---