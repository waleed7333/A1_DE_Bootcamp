# Serving Layer and Dashboards

## 1. Purpose

This document explains the ClickHouse serving layer, the relationship between physical tables and `v_*` views, the Power BI model, dashboard scenarios, and the business interpretation of the final analytical outputs.

The serving layer exists so that Power BI reads optimized analytical structures instead of raw Kafka, PostgreSQL, or Iceberg processing tables.

---

## 2. Serving Layer Objective

The serving layer transforms validated lakehouse data into dashboard-ready structures:

- Dimensions.
- Facts.
- Marts.
- Latest-active views.

This provides fast queries, simpler dashboard modeling, and a clean boundary between data engineering pipelines and business intelligence reporting.

---

## 3. Why ClickHouse Was Used

ClickHouse is used because it is well suited for analytical queries over event, fact, and mart tables. It supports fast aggregations, efficient columnar storage, and simple SQL access for dashboard tools.

In this project, ClickHouse provides:

- A dedicated OLAP serving database.
- Physical tables for dimensions, facts, and marts.
- A serving control mechanism for active builds.
- Regular `v_*` views for Power BI.
- Separation between lakehouse processing and dashboard consumption.

ClickHouse is not used as the raw data lake and is not the source-of-truth for CDC history. Iceberg remains the governed lakehouse store.

---

## 4. ClickHouse Database

Database name:

```text
personalization_olap
```

Power BI connects to this database and selects views prefixed with `v_`.

---

## 5. Physical Tables vs `v_*` Views

The serving job writes physical ClickHouse tables with a `serving_build_id`. Each serving publication creates a new build and writes rows for that build.

The `v_*` views expose only the latest active serving build. This design allows multiple builds to exist in physical tables while Power BI always reads the active version.

Important rule:

```text
v_* means latest ACTIVE serving build.
```

It does not mean that the table is automatically the current user table. For example, `v_dim_user_current` is current-user data because its underlying dimension is built from current SCD2 rows, while the `v_` prefix itself means latest active serving build.

---

## 6. Serving Control

The serving publication process records active builds in a serving control table. The views filter physical tables by the latest active build.

Conceptual logic:

```text
physical_table rows
  ↓ filter by active serving_build_id
v_* view
  ↓
Power BI
```

This prevents Power BI from reading stale or mixed-build data.

---

## 7. Dimensions

| View | Purpose |
|---|---|
| `v_dim_date` | Date dimension used for time filtering and date-based reporting. |
| `v_dim_product` | Product dimension from the static product catalog. |
| `v_dim_user_current` | Current user dimension for the latest active serving build. |

`v_dim_user_current` does not replace the full SCD2 history. The full historical user profile table remains in Iceberg as `ecommerce.processed.user_profile_scd2`.

---

## 8. Facts

| View | Purpose |
|---|---|
| `v_fact_clickstream_event` | Event-level behavioral fact table. |
| `v_fact_order` | Order header fact table. |
| `v_fact_order_item` | Order item fact table. |

Facts support event counts, revenue metrics, product analysis, journey analysis, and relationship joins between behavior and transactions.

---

## 9. Marts

| View | Purpose |
|---|---|
| `v_mart_journey_session` | Session-level journey and funnel outcomes. |
| `v_mart_navigation_paths` | Navigation transitions and user path analysis. |
| `v_mart_product_performance_daily` | Daily product engagement and conversion metrics. |
| `v_mart_web_experience_daily` | Endpoint performance and web experience metrics. |
| `v_mart_context_impact_daily` | Country, city, weather, and holiday context metrics. |
| `v_mart_personalization_candidates` | Product and segment candidates for personalization. |

Marts reduce dashboard complexity by pre-aggregating analytical patterns that would be expensive or difficult to build directly in Power BI.

---

## 10. Power BI Connection Rule

Power BI must select only ClickHouse views with the `v_` prefix.

Approved views:

```text
v_dim_date
v_dim_product
v_dim_user_current
v_fact_clickstream_event
v_fact_order
v_fact_order_item
v_mart_journey_session
v_mart_navigation_paths
v_mart_product_performance_daily
v_mart_web_experience_daily
v_mart_context_impact_daily
v_mart_personalization_candidates
```

Power BI should not import physical non-view serving tables, raw Iceberg data, audit tables, Kafka topics, or PostgreSQL source tables.

---

## 11. Power BI Import Mode

The report uses Import mode. This is appropriate for the project because:

- The dataset is project-sized.
- ClickHouse already publishes serving-ready tables.
- Import mode makes dashboard interaction fast.
- The report can be refreshed after a serving build is published.

The tradeoff is that Power BI must be refreshed to reflect a newly published ClickHouse serving build.

---

## 12. Dashboard Scenario 1: Growth and Funnel Intelligence

The first dashboard page focuses on growth, revenue, journey, and funnel leakage.

### 12.1 Business question

How do users move from browsing to product interest, cart action, checkout start, and purchase completion, and where does the journey lose users?

### 12.2 Key analysis areas

- Total sessions.
- Clickstream event volume.
- Checkout starts.
- Checkout completions.
- Cart-to-checkout rate.
- Checkout-to-purchase rate.
- Revenue and order metrics.
- Product and category performance.
- Session outcomes.
- Navigation path behavior.

### 12.3 Why this page matters

This page connects behavioral events to transactional outcomes. It supports decisions about funnel optimization, product-page improvements, checkout experience, and revenue leakage.

---

## 13. Dashboard Scenario 2: Personalization and Context Intelligence

The second dashboard page focuses on personalization candidates and context-aware segmentation.

### 13.1 Business question

Which products, users, segments, countries, devices, traffic sources, weather contexts, or holiday contexts show behavior patterns that can support personalization?

### 13.2 Key analysis areas

- Products with high interest and lower conversion.
- Product candidate ranking.
- User and traffic segments.
- Country and city behavior.
- Device/browser differences.
- Weather and holiday context.
- Web experience by endpoint or response condition.

### 13.3 Why this page matters

Personalization requires more than purchase records. It needs product interest, journey behavior, context, and friction indicators. This page turns the lakehouse and serving model into business-facing personalization intelligence.

---

## 14. Funnel Measures

The dashboard funnel should be interpreted carefully. A correct funnel measure must use the correct denominator.

| Measure | Meaning |
|---|---|
| Add to Cart | Count of `add_to_cart` events. |
| Checkout Starts | Count of `checkout_start` events or sessions that reached checkout start, depending on visual context. |
| Checkout Completes | Count of `checkout_complete` events or completed checkout sessions. |
| Cart to Checkout Rate | Checkout starts divided by add-to-cart events/sessions in the same grain. |
| Checkout to Purchase Rate | Checkout completes divided by checkout starts in the same grain. |

Rates should not be forced to 100% by using mismatched numerator and denominator filters. If a visual shows 100% everywhere, the filter context and denominator definition should be checked.

---

## 15. Relationship Model

The analytical model depends on these relationships:

| Relationship | Key |
|---|---|
| Date dimension to facts/marts | Date key or date field. |
| Product dimension to clickstream facts | `product_id`. |
| Product dimension to order item facts | `product_id`. |
| User dimension to clickstream facts | `user_id`. |
| User dimension to order facts | `user_id`. |
| Order fact to order item fact | `order_id`. |
| Clickstream checkout events to orders | `checkout_id`, `order_id`. |

These relationships allow the report to combine behavior, revenue, products, users, and context.

---

## 16. Serving Evidence

Serving publication writes evidence to:

```text
reports/serving_latest.json
ecommerce.audit.serving_builds
```

The evidence records:

- Serving build ID.
- Validation ID used by the build.
- Build status.
- Row count summary.
- Activation timestamp.
- Error message if publication failed.

This evidence is important because it proves that ClickHouse data was published from a validated lakehouse state.

---

## 17. Dashboard Screenshots

The dashboard screenshots are stored in:

```text
screenshots/16_powerbi_dashboard_growth_funnel.png
screenshots/17_powerbi_dashboard_personalization.png
screenshots/18_powerbi_data_model.png
```

The README explains what each screenshot shows and what it proves.

---

## 18. Serving Limitations

- ClickHouse is a serving store, not the governed lakehouse source of truth.
- Power BI uses Import mode and must be refreshed after serving publication.
- The dashboard reflects the latest active serving build exposed by `v_*` views.
- User SCD2 history is kept in Iceberg; Power BI uses current user dimension rows for the active serving build.
- The personalization candidate mart is analytical ranking logic, not a trained machine learning recommendation model.
