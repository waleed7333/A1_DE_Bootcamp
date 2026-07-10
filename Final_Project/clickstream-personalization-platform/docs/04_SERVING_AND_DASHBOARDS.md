
# Serving Layer and Dashboards

## 1. Purpose

This document describes the ClickHouse serving layer, Power BI model, dashboard pages, and refresh behavior.

Pipeline and lakehouse processing are documented in:

```text
docs/03_PIPELINES_QUALITY_AND_LAKEHOUSE.md
```

Operational validation is documented in:

```text
docs/05_OPERATIONS_VALIDATION_AND_LIMITATIONS.md
```

---

## 2. Serving Architecture

The serving flow is:

```text
Validated Iceberg Tables
    → Spark Batch publish_serving
    → ClickHouse personalization_olap
    → ClickHouse v_* Views
    → Power BI Import Mode
```

Power BI does not read directly from Iceberg or MinIO.

---

## 3. ClickHouse Database

Database:

```text
personalization_olap
```

ClickHouse contains dashboard-ready structures grouped into:

* Dimensions.
* Facts.
* Analytical marts.
* Power BI-facing views.

Recommended diagram:

```text
diagrams/05_olap_model.png
```

---

## 4. Power BI Consumption Rule

Power BI reads only ClickHouse views using the `v_*` naming convention.

This keeps Power BI isolated from raw processing details and allows ClickHouse to act as the governed serving boundary.

---

## 5. Main Dimensions

| View                 | Purpose                                   |
| -------------------- | ----------------------------------------- |
| `v_dim_date`         | Date attributes for dashboard filtering   |
| `v_dim_product`      | Product attributes and category context   |
| `v_dim_user_current` | Current user profile attributes from SCD2 |

---

## 6. Main Facts

| View                       | Purpose                       |
| -------------------------- | ----------------------------- |
| `v_fact_clickstream_event` | Event-level user behavior     |
| `v_fact_order`             | Order-level transaction facts |
| `v_fact_order_item`        | Order item transaction facts  |

---

## 7. Analytical Marts

| View                                | Purpose                                            |
| ----------------------------------- | -------------------------------------------------- |
| `v_mart_journey_session`            | Session-level journey and engagement analysis      |
| `v_mart_navigation_paths`           | Page transition and navigation path analysis       |
| `v_mart_product_performance_daily`  | Daily product behavior and conversion analysis     |
| `v_mart_web_experience_daily`       | Technical experience metrics by day                |
| `v_mart_context_impact_daily`       | Weather and holiday contextual analysis            |
| `v_mart_personalization_candidates` | Product and segment candidates for personalization |

---

## 8. Key Serving Relationships

| Relationship                                      | Purpose                               |
| ------------------------------------------------- | ------------------------------------- |
| Date dimension to facts and marts                 | Time filtering and trend analysis     |
| Product dimension to clickstream and order items  | Product behavior and revenue analysis |
| Current user dimension to clickstream and orders  | Segment and membership analysis       |
| Orders to order items                             | Transaction detail analysis           |
| Clickstream to orders through checkout/order keys | Funnel and conversion analysis        |
| Context marts to weather and holiday tables       | Contextual business analysis          |

---

## 9. Dashboard Page 1

### Name

```text
Growth, Funnel Leakage & Journey Intelligence
```

### Purpose

This page focuses on revenue, conversion, funnel leakage, navigation, and high-intent user behavior.

### Main analysis areas

* Total revenue.
* Paid orders.
* Conversion rate.
* Sessions and engagement.
* Cart abandonment.
* Revenue at risk.
* Funnel stages.
* Drop-off points.
* Top navigation paths.
* High-intent cities and segments.

### Typical business questions

* Where do users abandon the journey?
* Which funnel stages lose the most potential revenue?
* Which cities or segments show high intent?
* Which paths are common before conversion or abandonment?

---

## 10. Dashboard Page 2

### Name

```text
Personalization, Context & Recommendation Intelligence
```

### Purpose

This page focuses on personalization candidates, product interest, segment behavior, and contextual enrichment.

### Main analysis areas

* Candidate products for personalization.
* High-view low-conversion products.
* Membership segment behavior.
* Weather-associated behavior.
* Holiday-associated behavior.
* Product recommendation opportunities.
* Contextual revenue patterns.

### Typical business questions

* Which products receive attention but do not convert?
* Which segments should receive personalized recommendations?
* Are weather or holiday contexts associated with behavior changes?
* Which products are strong candidates for recommendation logic?

---

## 11. Operations Console Boundary

The Operations Console is not a Power BI dashboard page.

It is a separate Streamlit monitoring interface for:

* Platform health.
* Streaming status.
* CDC status.
* SCD2 health.
* Data quality.
* Lakehouse validation.
* ClickHouse serving state.
* Alerts and recommendations.

---

## 12. Serving Refresh Behavior

ClickHouse does not update automatically after every Iceberg write.

The serving layer is updated by:

```text
publish_serving
```

Expected sequence:

```text
Streaming writes Iceberg
    → Batch enrichment and validation
    → publish_serving
    → ClickHouse updated
    → Power BI refresh
```

---

## 13. Freshness Tracking

The serving layer should be evaluated using:

```text
Latest Iceberg event time
Latest ClickHouse event time
Freshness gap in minutes
Latest serving build ID
Latest Power BI refresh time
```

This distinction is important because streaming data may exist in Iceberg before it is published to ClickHouse.

---

## 14. Serving Build Evidence

The latest serving report is written to:

```text
reports/serving_latest.json
```

It should include evidence such as:

* Serving build ID.
* Build timestamp.
* Status.
* Published tables or views.
* Row counts.
* Validation dependency.
* Errors if publish failed.

---

## 15. Power BI Screenshots

Recommended final screenshot paths:

```text
docs/assets/screenshots/12_powerbi_dashboard_growth_funnel.png
docs/assets/screenshots/13_powerbi_dashboard_personalization.png
docs/assets/screenshots/14_powerbi_data_model.png
```

Dashboard screenshots should be exported at high resolution, preferably:


KPI labels should be readable and not truncated.

---


## 16. Serving Validation Queries

Example ClickHouse row count validation:

```bash
docker compose exec -T clickhouse bash -lc '
clickhouse-client \
  --user "$CLICKHOUSE_USER" \
  --password "$CLICKHOUSE_PASSWORD" \
  --database personalization_olap \
  --query "
SELECT
    count() AS clickstream_rows,
    max(event_timestamp) AS latest_event
FROM v_fact_clickstream_event
FORMAT PrettyCompact
"
'
```

Example view count validation:

```bash
docker compose exec -T clickhouse bash -lc '
clickhouse-client \
  --user "$CLICKHOUSE_USER" \
  --password "$CLICKHOUSE_PASSWORD" \
  --database personalization_olap \
  --query "
SELECT
    name
FROM system.tables
WHERE database = '\''personalization_olap'\''
ORDER BY name
FORMAT PrettyCompact
"
'
```

---