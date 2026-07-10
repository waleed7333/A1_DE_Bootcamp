
# Operations, Validation, and Limitations

## 1. Purpose

This document provides operational procedures, validation commands, evidence expectations, troubleshooting guidance, known operational behaviors, limitations, and future enhancements.

Architecture is documented in:

```text
docs/01_PROJECT_ARCHITECTURE.md
```

Source contracts are documented in:

```text
docs/02_DATA_SOURCES_AND_CONTRACTS.md
```

Pipeline and quality design are documented in:

```text
docs/03_PIPELINES_QUALITY_AND_LAKEHOUSE.md
```

Serving and dashboard design are documented in:

```text
docs/04_SERVING_AND_DASHBOARDS.md
```

---

## 2. Local Prerequisites

The local environment requires:

* Docker.
* Docker Compose.
* Python 3.
* Sufficient Docker memory allocation.
* Power BI Desktop for dashboard development.
* GeoLite2 City database file.
* Calendarific API key when holiday enrichment is enabled.

Required local GeoIP file:

```text
data/reference/GeoLite2-City.mmdb
```

Local secrets must be stored in `.env` and must not be committed.

---

## 3. Bootstrap

Create required local environment files and folders:

```bash
python main.py bootstrap
```

Configure local development secrets:

```bash
python main.py configure-dev-secrets
```

Run preflight checks:

```bash
python main.py infra-preflight
```

---

## 4. Initialization

Initialize the platform:

```bash
python main.py init
```

Initialization is expected to perform the following actions:

* Generate local source data.
* Create or verify Kafka topics.
* Initialize MinIO and Iceberg.
* Load Product Catalog.
* Load PostgreSQL seed data.
* Register Debezium connectors.
* Execute controlled CDC changes.
* Run batch jobs.
* Validate lakehouse tables.
* Publish ClickHouse serving tables.

---

## 5. Start, Status, and Stop

Start the platform:

```bash
python main.py start
```

Check platform status:

```bash
python main.py status
```

Stop the platform safely:

```bash
python main.py stop
```

---

## 6. Reset

Dynamic runtime state can be rebuilt with:

```bash
python main.py reset --confirm
```

This command should be treated as destructive for dynamic runtime state. It is not the normal shutdown command.

---

## 7. Service Health Verification

Check Docker services:

```bash
docker compose ps -a
```

Expected core services include:

```text
postgres
zookeeper
kafka1
kafka2
kafka3
kafka-ui
debezium-connect
filebeat
spark-engine
airflow
minio
clickhouse
observability-ui
```

---

## 8. Kafka Topic Verification

Kafka topics should include:

```text
clickstream-events
webserver-logs
users-cdc
orders-cdc
order-items-cdc
debezium-connect-configs
debezium-connect-offsets
debezium-connect-status
```

Kafka UI can be used to inspect topic existence and metadata.

The internal topic `__consumer_offsets` can appear when internal topics are enabled. Its presence is normal.

---

## 9. Debezium Verification

Debezium can be verified through the Connect REST API.

List connectors:

```bash
curl http://localhost:8083/connectors
```

Check connector status:

```bash
curl http://localhost:8083/connectors/clickstream-users-cdc/status
curl http://localhost:8083/connectors/clickstream-orders-cdc/status
curl http://localhost:8083/connectors/clickstream-order-items-cdc/status
```

The expected connector and task state is:

```text
RUNNING
```

A JSON API response is sufficient operational evidence. A UI screenshot is not required.

---

## 10. MinIO and Iceberg Verification

MinIO Console can be used to verify:

* Bucket existence.
* Warehouse path.
* Iceberg metadata files.
* Processed table folders.
* Audit table folders.

Expected bucket:

```text
ecommerce-lakehouse
```

Expected warehouse path:

```text
s3://ecommerce-lakehouse/warehouse/
```

---

## 11. Spark Streaming Verification

Spark streaming status is tracked through runtime evidence files.

Common evidence path:

```text
runtime/streaming_status.json
```

The streaming status should indicate:

* Process status.
* Last micro-batch ID.
* Last micro-batch timestamp.
* Rows processed.
* Checkpoint path.
* Last error if present.

---

## 12. Analytics Refresh

The analytics refresh runs the main batch jobs:

```text
user_scd2
weather_enrichment
holiday_enrichment
validate_lakehouse
publish_serving
```

If needed, the refresh can be triggered through the project orchestration logic.

The expected successful sequence is:

```text
user_scd2: PASSED
weather_enrichment: PASSED
holiday_enrichment: PASSED
validate_lakehouse: PASSED
publish_serving: PASSED
```

---

## 13. Validation Report

Latest validation report:

```text
reports/validation_latest.json
```

Readable format:

```bash
python -m json.tool reports/validation_latest.json
```

The validation report should confirm:

* Required tables exist.
* Clean tables contain expected data.
* SCD2 constraints are valid.
* Audit tables are available.
* Quarantine counts are tracked.
* Lakehouse data is ready for serving.

---

## 14. Serving Report

Latest serving report:

```text
reports/serving_latest.json
```

Readable format:

```bash
python -m json.tool reports/serving_latest.json
```

The serving report should confirm:

* Serving build ID.
* Serving status.
* ClickHouse publish status.
* Row counts.
* Latest event timestamp.
* Serving build timestamp.

---

## 15. ClickHouse Verification

Check ClickHouse row counts:

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

Check available serving views:

```bash
docker compose exec -T clickhouse bash -lc '
clickhouse-client \
  --user "$CLICKHOUSE_USER" \
  --password "$CLICKHOUSE_PASSWORD" \
  --database personalization_olap \
  --query "
SELECT name
FROM system.tables
WHERE database = '\''personalization_olap'\''
ORDER BY name
FORMAT PrettyCompact
"
'
```

---

## 16. Power BI Verification

Power BI should connect to ClickHouse and import data from `v_*` views only.

Expected dashboard pages:

```text
Growth, Funnel Leakage & Journey Intelligence
Personalization, Context & Recommendation Intelligence
```

Power BI should not read directly from MinIO or Iceberg.

---

## 17. Operations Console

The Operations Console is a Streamlit read-only monitoring interface.

It is used for:

* Executive platform status.
* Freshness and run lineage.
* Docker and container health.
* Kafka and ingestion status.
* Source generation.
* Spark streaming reliability.
* CDC and Debezium state.
* SCD Type 2 health.
* Data quality and quarantine.
* Iceberg and MinIO checks.
* Batch jobs and external APIs.
* ClickHouse and serving status.
* Alerts and recommended actions.

The console should not expose secrets, destructive reset controls, or raw API keys.

---

## 18. Evidence Screenshot Set

Recommended final screenshot set:

```text
docs/assets/screenshots/01_docker_compose_healthy.png
docs/assets/screenshots/02_main_status_healthy.png
docs/assets/screenshots/03_kafka_topics.png
docs/assets/screenshots/04_minio_warehouse_bucket.png
docs/assets/screenshots/05_spark_streaming_status.png
docs/assets/screenshots/06_airflow_or_refresh_jobs_passed.png
docs/assets/screenshots/07_validation_latest_passed.png
docs/assets/screenshots/08_serving_latest_passed.png
docs/assets/screenshots/09_clickhouse_row_counts.png
docs/assets/screenshots/10_clickhouse_geo_weather_context.png
docs/assets/screenshots/11_quarantine_counts.png
docs/assets/screenshots/12_powerbi_dashboard_growth_funnel.png
docs/assets/screenshots/13_powerbi_dashboard_personalization.png
docs/assets/screenshots/14_powerbi_data_model.png
```

Debezium connector status can be documented through REST API commands rather than a screenshot.

Operations Console screenshots are optional and can be excluded from the final evidence set.

---

## 19. GitHub Cleanup

Before committing to GitHub, remove local secrets and runtime output.

```bash
rm -f .env

find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -name "*.pyc" -delete
rm -rf .pytest_cache

rm -rf runtime/*
rm -rf reports/*
rm -rf data/source/*
rm -rf data/minio/data/*
rm -rf data/clickhouse/*
```

Recreate placeholder files if needed:

```bash
mkdir -p runtime reports
mkdir -p data/source/clickstream data/source/web_logs data/source/postgres
mkdir -p data/minio/data data/clickhouse

touch runtime/.gitkeep
touch reports/.gitkeep
touch data/source/.gitkeep
touch data/source/clickstream/.gitkeep
touch data/source/web_logs/.gitkeep
touch data/source/postgres/.gitkeep
touch data/minio/data/.gitkeep
touch data/clickhouse/.gitkeep
```

---

## 20. Files Not Intended for GitHub

The following should not be committed:

```text
.env
runtime/*
reports/*
data/source/*
data/minio/data/*
data/clickhouse/*
__pycache__/
*.pyc
.pytest_cache/
GeoLite2-City.mmdb
```

Generated screenshots can be committed only if they are intentionally part of the project evidence documentation.

---

## 21. Known Operational Behaviors

### 21.1 ClickHouse freshness

ClickHouse does not automatically reflect every new Iceberg write.

Expected flow:

```text
Spark Streaming writes Iceberg
    → validate_lakehouse
    → publish_serving
    → ClickHouse updated
    → Power BI refresh
```

If ClickHouse appears stale, compare:

```text
Latest Iceberg event time
Latest ClickHouse event time
```

Then run the analytics refresh if needed.

### 21.2 Weather current-day coverage

Weather enrichment uses Open-Meteo Historical Weather API.

Current-day weather can be unavailable by design depending on archive availability. Historical weather records are the expected stable enrichment source.

### 21.3 Product Catalog behavior

Product Catalog is static and loaded as an initial CSV snapshot. It does not generate CDC events.

### 21.4 SCD2 boundary

SCD Type 2 applies only to User Profile.

Orders and Order Items are used as CDC-derived transactional facts.

### 21.5 Debezium JSON output

Debezium Connect status endpoints return JSON. This is normal and sufficient for operational verification.

---

## 22. Troubleshooting Guide

| Symptom                                        | Likely Cause                                                   | Suggested Action                                       |
| ---------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------ |
| Kafka topic missing                            | Kafka initialization did not complete                          | Re-run initialization or inspect Kafka broker logs     |
| Debezium connector not running                 | Connector registration or PostgreSQL logical replication issue | Check Debezium status endpoint and PostgreSQL settings |
| Spark streaming not processing                 | Kafka input stopped, checkpoint issue, or Spark error          | Check `runtime/streaming_status.json` and Spark logs   |
| ClickHouse row counts unchanged                | `publish_serving` has not run after new Iceberg writes         | Run analytics refresh and refresh Power BI             |
| Power BI shows old data                        | Import model has not been refreshed                            | Refresh Power BI after successful serving publish      |
| Weather values are unavailable for current day | Historical archive behavior                                    | Verify historical records and coverage status          |
| Quarantine rate high                           | Invalid generated or source records                            | Check top rejection reasons and source contract rules  |
| Duplicate current SCD2 users                   | SCD2 logic or CDC ordering issue                               | Inspect `user_profile_scd2` validation results         |

---

## 23. Limitations

The current implementation is designed for a local educational capstone environment.

Known limitations:

* The platform runs locally through Docker Compose, not a managed cloud deployment.
* Power BI uses Import mode, not DirectQuery.
* External API availability can affect weather and holiday enrichment.
* Weather enrichment is based on historical weather coverage.
* The Operations Console is read-only and does not provide advanced alert delivery.
* Scaling is limited by local machine CPU, memory, and Docker resources.
* The generated data is synthetic and designed for demonstration and validation.
* The project does not include a trained machine learning recommendation model.

---

## 24. Future Enhancements

Potential enhancements:

* Add machine learning recommendation models.
* Add automated alert notifications.
* Add cloud deployment option.
* Add incremental ClickHouse publish optimization.
* Add historical trend comparison across larger time windows.
* Add CI checks for documentation and project contract validation.
* Add dashboard deployment automation.
* Add deeper Kafka lag and consumer group metrics.
* Add lineage visualization for serving builds.
* Add data contract tests for each source.

---

## 25. Final Validation Checklist

Before considering the project ready:

```text
Docker services are healthy
Kafka topics exist
Debezium connectors are RUNNING
Spark streaming status is available
Iceberg tables exist
Product Catalog loaded
CDC clean tables populated
User SCD2 validation passed
Weather enrichment completed or coverage explained
Holiday enrichment completed
Lakehouse validation passed
ClickHouse serving publish passed
Power BI dashboards refresh successfully
Local secrets are removed before GitHub commit
Runtime outputs are excluded from GitHub
Documentation does not contain personal presentation notes
```
