# Operations, Validation, Evidence, and Limitations

## 1. Purpose

This document provides the operational runbook for the Clickstream Personalization Platform. It explains how to start, stop, validate, inspect, and prepare the project for repository submission. It also documents limitations, engineering challenges, and the evidence artifacts used to prove the project behavior.

---

## 2. Environment Requirements

Recommended local environment:

| Requirement | Notes |
|---|---|
| Docker and Docker Compose | Required to run the multi-service platform. |
| Docker memory | At least 10 GB is recommended because the platform runs Kafka, Spark, Airflow, ClickHouse, PostgreSQL, MinIO, Debezium, and monitoring services. |
| Python | Required for the local CLI `main.py`. |
| `.env` file | Must be created from `.env.example`. |
| GeoLite2 City database | Required at `data/reference/GeoLite2-City.mmdb`; not committed to Git. |
| Calendarific API key | Required in `.env` for holiday enrichment. |

---

## 3. Required Local Files

The repository includes:

```text
data/reference/product_catalog.csv
```

The repository does not include licensed/local secret files such as:

```text
.env
data/reference/GeoLite2-City.mmdb
```

The `.env` file must be created locally:

```bash
cp .env.example .env
```

The GeoLite2 database must be placed manually at:

```text
data/reference/GeoLite2-City.mmdb
```

---

## 4. Main CLI Commands

The project intentionally exposes a small normal-operator CLI.

| Command | Purpose |
|---|---|
| `python main.py init` | Build the platform from a clean state. |
| `python main.py start` | Start an existing platform without deleting dynamic state. |
| `python main.py status` | Show health and evidence status. |
| `python main.py stop` | Stop containers without deleting dynamic state. |
| `python main.py reset --confirm` | Delete dynamic state and rebuild after explicit confirmation. |

Commands such as `bootstrap`, `publish-serving`, or `infra-preflight` are not part of the current user-facing CLI and should not be documented as normal commands.

---

## 5. Initial Run Flow

The normal first run is:

```bash
python main.py init
```

Conceptually, initialization performs:

1. Environment and configuration checks.
2. Source generation.
3. Docker infrastructure startup.
4. Kafka topic creation/verification.
5. MinIO bucket verification.
6. Iceberg lakehouse bootstrap.
7. Static Product Catalog clean load.
8. PostgreSQL seed loading.
9. Debezium connector creation.
10. Streaming and batch preparation.
11. Analytics refresh jobs.
12. Validation and serving publication evidence.

---

## 6. Start and Stop Flow

To start an already initialized platform:

```bash
python main.py start
```

To stop the platform without deleting data:

```bash
python main.py stop
```

To check status:

```bash
python main.py status
```

To reset dynamic state and rebuild later:

```bash
python main.py reset --confirm
```

Reset is destructive and should not be used as a normal troubleshooting shortcut.

---

## 7. Service Health Validation

Docker Compose status can be checked with:

```bash
docker compose ps
```

The expected platform includes these major services:

- PostgreSQL.
- ZooKeeper.
- Kafka broker 1.
- Kafka broker 2.
- Kafka broker 3.
- Kafka UI.
- Debezium Connect.
- MinIO.
- Filebeat.
- Spark Engine.
- Airflow.
- ClickHouse.
- Observability UI.

The screenshot `screenshots/01_docker_compose_healthy.png` is used as evidence that the platform services were running and healthy.

---

## 8. Kafka Validation

Kafka can be validated through Kafka UI or CLI. Expected business topics:

```text
clickstream-events
webserver-logs
users-cdc
orders-cdc
order-items-cdc
```

Expected Debezium internal topics:

```text
debezium-connect-configs
debezium-connect-offsets
debezium-connect-status
```

The screenshot `screenshots/03_kafka_topics.png` proves that the topics exist.

---

## 9. Debezium Validation

Debezium validates PostgreSQL CDC capture. The project creates connectors for:

```text
users
orders
order_items
```

Debezium events preserve operation type, before image, after image, source LSN, source timestamp, and Kafka metadata. The clean CDC tables store this metadata for downstream processing.

---

## 10. Spark Streaming Validation

Spark Structured Streaming should be validated by checking streaming status evidence and clean table counts.

The screenshot:

```text
screenshots/05_spark_streaming_status.png
```

shows streaming status evidence.

The clean count screenshot:

```text
screenshots/09_clean_processed_table_counts.png
```

shows that streaming and batch outputs exist in processed Iceberg tables.

---

## 11. Audit and Quarantine Validation

The project includes an inspection job for audit evidence:

```text
spark_jobs/inspect_audit_counts.py
```

Run the full audit inspection:

```bash
docker compose exec -T spark-engine bash -lc '
cd /opt/project
PYTHONPATH=/opt/project/spark_jobs \
spark-submit --master local[2] \
  --conf spark.ui.enabled=false \
  /opt/project/spark_jobs/inspect_audit_counts.py \
  2>/tmp/audit_spark_noise.log
'
```

The redirection hides long Spark startup logs and makes terminal output easier to capture.

### 11.1 Print only clean processed table counts

```bash
docker compose exec -T spark-engine bash -lc '
cd /opt/project
PYTHONPATH=/opt/project/spark_jobs \
spark-submit --master local[2] \
  --conf spark.ui.enabled=false \
  /opt/project/spark_jobs/inspect_audit_counts.py \
  2>/tmp/audit_spark_noise.log \
| awk "
index(\$0, \"1. CLEAN PROCESSED TABLE ROW COUNTS\") {flag=1}
index(\$0, \"2. QUARANTINE COUNTS BY SOURCE AND REASON\") {flag=0}
flag
"
'
```

### 11.2 Print only quarantine counts

```bash
docker compose exec -T spark-engine bash -lc '
cd /opt/project
PYTHONPATH=/opt/project/spark_jobs \
spark-submit --master local[2] \
  --conf spark.ui.enabled=false \
  /opt/project/spark_jobs/inspect_audit_counts.py \
  2>/tmp/audit_spark_noise.log \
| awk "
index(\$0, \"2. QUARANTINE COUNTS BY SOURCE AND REASON\") {flag=1}
index(\$0, \"3. DUPLICATE RECORD SAMPLES\") {flag=0}
flag
"
'
```

### 11.3 Print only duplicate samples

```bash
docker compose exec -T spark-engine bash -lc '
cd /opt/project
PYTHONPATH=/opt/project/spark_jobs \
spark-submit --master local[2] \
  --conf spark.ui.enabled=false \
  /opt/project/spark_jobs/inspect_audit_counts.py \
  2>/tmp/audit_spark_noise.log \
| awk "
index(\$0, \"3. DUPLICATE RECORD SAMPLES\") {flag=1}
index(\$0, \"4. INVALID RECORD SAMPLES\") {flag=0}
flag
"
'
```

### 11.4 Print only invalid samples

```bash
docker compose exec -T spark-engine bash -lc '
cd /opt/project
PYTHONPATH=/opt/project/spark_jobs \
spark-submit --master local[2] \
  --conf spark.ui.enabled=false \
  /opt/project/spark_jobs/inspect_audit_counts.py \
  2>/tmp/audit_spark_noise.log \
| awk "
index(\$0, \"4. INVALID RECORD SAMPLES\") {flag=1}
index(\$0, \"5. QUALITY METRICS SUMMARY\") {flag=0}
flag
"
'
```

### 11.5 Print only quality metrics

```bash
docker compose exec -T spark-engine bash -lc '
cd /opt/project
PYTHONPATH=/opt/project/spark_jobs \
spark-submit --master local[2] \
  --conf spark.ui.enabled=false \
  /opt/project/spark_jobs/inspect_audit_counts.py \
  2>/tmp/audit_spark_noise.log \
| awk "
index(\$0, \"5. QUALITY METRICS SUMMARY\") {flag=1}
index(\$0, \"6. PIPELINE, VALIDATION, AND SERVING EVIDENCE\") {flag=0}
flag
"
'
```

---

## 12. Lakehouse Validation

Lakehouse validation records evidence in:

```text
ecommerce.audit.validation_runs
reports/validation_latest.json
```

Validation checks include:

- Raw/clean/quarantine reconciliation.
- Quality status.
- Relationship status.
- SCD2 status.
- Coverage status.
- Orphan checks.
- Request correlation coverage.

Screenshots:

```text
screenshots/07_validation_latest_passed_1.png
screenshots/07_validation_latest_passed_2.png
```

show validation evidence.

---

## 13. Serving Validation

Serving publication records evidence in:

```text
ecommerce.audit.serving_builds
reports/serving_latest.json
```

The serving output should be verified in ClickHouse through row counts and dashboard views.

Screenshots:

```text
screenshots/08_serving_latest_passed.png
screenshots/14_clickhouse_row_counts.png
screenshots/15_clickhouse_geo_weather_context_1.png
screenshots/15_clickhouse_geo_weather_context_2.png
```

support serving validation.

---

## 14. Power BI Validation

Power BI validation requires checking:

- The report opens successfully.
- The model uses ClickHouse `v_*` views.
- The dashboard pages are populated.
- Funnel measures do not use incorrect denominator logic.
- Date display is interpreted consistently.
- The model view shows the expected dimensions, facts, and marts.

Screenshots:

```text
screenshots/16_powerbi_dashboard_growth_funnel.png
screenshots/17_powerbi_dashboard_personalization.png
screenshots/18_powerbi_data_model.png
```

provide final reporting evidence.

---

## 15. Evidence Screenshot Set

The README contains the detailed description of every screenshot. The final evidence set should include service health, Kafka topics, MinIO warehouse, Spark streaming status, Airflow/batch status, validation status, serving status, processed counts, quarantine counts, duplicate samples, invalid samples, quality metrics, ClickHouse counts, context evidence, Power BI dashboards, and the Power BI data model.

---

## 16. Engineering Challenges and Resolutions

### 16.1 GeoIP enrichment produced incorrect or incomplete geography

| Item | Detail |
|---|---|
| Problem | Source records originally risked mixing generated geography with GeoIP-derived geography. |
| Root cause | Country/city should be produced by the GeoLite2 lookup, not trusted from generated source fields. |
| Impact | Geo and context analysis would be unreliable if the source already contained final geography. |
| Resolution | Source records contain `ip_address`; Spark enriches country, city, latitude, longitude, and timezone using GeoLite2. |
| Validation evidence | Clean clickstream/web log rows contain GeoIP fields; ClickHouse context screenshots show geo/context data. |

### 16.2 Weather enrichment could become inefficient

| Item | Detail |
|---|---|
| Problem | Calling Open-Meteo per event would create too many requests. |
| Root cause | Many events share the same location and date/hour range. |
| Impact | Slow batch jobs and unnecessary API pressure. |
| Resolution | Weather enrichment groups by location/date range and writes hourly weather context. |
| Validation evidence | `weather_clean` row counts and context screenshots. |

### 16.3 Current-day weather appears as skipped

| Item | Detail |
|---|---|
| Problem | Current/future UTC timestamps do not produce historical archive weather rows. |
| Root cause | Open-Meteo Historical Weather Archive is not intended for current/future timestamps. |
| Impact | Some current-day weather keys show skipped status. |
| Resolution | The job records these cases in `external_api_failures` with status `SKIPPED`. |
| Validation evidence | Audit output shows Open-Meteo skipped records with explanatory messages. |

### 16.4 Docker memory pressure

| Item | Detail |
|---|---|
| Problem | The full local platform is resource intensive. |
| Root cause | Kafka, Spark, Airflow, ClickHouse, Debezium, MinIO, and PostgreSQL all run locally. |
| Impact | Low-memory machines may experience slow startup or unstable services. |
| Resolution | Low-memory service limits, one Spark container, Airflow parallelism of one, and recommended Docker memory documented. |
| Validation evidence | Docker Compose healthy screenshot. |

### 16.5 Kafka and ZooKeeper startup readiness

| Item | Detail |
|---|---|
| Problem | Kafka readiness can lag behind container startup. |
| Root cause | Kafka brokers require ZooKeeper coordination and topic metadata readiness. |
| Impact | Downstream services can fail if started before Kafka is ready. |
| Resolution | Health checks and service dependencies are used in Docker Compose. |
| Validation evidence | Kafka topic screenshot and Docker Compose health screenshot. |

### 16.6 Power BI funnel rates can appear incorrect if filter context is wrong

| Item | Detail |
|---|---|
| Problem | Some rates can show 100% when numerator and denominator are not defined at the same grain. |
| Root cause | DAX/filter context mismatch. |
| Impact | Funnel interpretation becomes misleading. |
| Resolution | Measures should use consistent numerator/denominator definitions for cart-to-checkout and checkout-to-purchase. |
| Validation evidence | Final dashboard screenshots and model view. |

### 16.7 Quarantine file count was confused with quarantine record count

| Item | Detail |
|---|---|
| Problem | Counting files under an Iceberg table path can show a number unrelated to rejected record count. |
| Root cause | Iceberg stores data files, metadata files, manifests, and snapshots. |
| Impact | A screenshot could incorrectly report quarantine evidence. |
| Resolution | Use Spark SQL against `ecommerce.audit.quarantine_records` to count records by source and reason. |
| Validation evidence | `screenshots/10_quarantine_counts.png`, `screenshots/11_duplicate_record_samples.png`, and `screenshots/12_invalid_record_samples.png`. |

### 16.8 Documentation drift

| Item | Detail |
|---|---|
| Problem | Earlier documentation can become stale as architecture decisions change. |
| Root cause | Project scope evolved through implementation and validation. |
| Impact | README or docs can mention old filenames, old tools, or unsupported commands. |
| Resolution | Documentation is aligned to `config/settings.yaml`, `docker-compose.yml`, `main.py`, `spark_jobs`, screenshots, and diagrams. |
| Validation evidence | Final documentation references actual files and actual supported commands. |

---

## 17. Known Limitations

| Limitation | Explanation |
|---|---|
| Local deployment | The platform runs locally through Docker Compose, not on managed cloud infrastructure. |
| Project-sized dataset | Source generation creates deterministic project data, not production-scale traffic. |
| Current-day weather handling | Historical weather API skips current/future timestamps by design. |
| Power BI Import mode | Report refresh is required after new serving publication. |
| Product Catalog static | Product Catalog is intentionally static; product CDC is outside scope. |
| SCD2 only for users | Orders and order items are CDC-cleaned but not modeled as SCD2. |
| Operations Console is read-only | It is intended for visibility, not service control. |
| No ML recommender model | Personalization candidates are analytical outputs, not trained recommendation models. |

---

## 18. GitHub Cleanup Checklist

Before committing or publishing the repository, remove dynamic and local files.

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
mkdir -p runtime reports
mkdir -p data/source/clickstream data/source/web_logs data/source/postgres
mkdir -p data/minio/data data/clickhouse
touch runtime/.gitkeep reports/.gitkeep
touch data/source/.gitkeep data/source/clickstream/.gitkeep data/source/web_logs/.gitkeep data/source/postgres/.gitkeep
touch data/minio/data/.gitkeep data/clickhouse/.gitkeep
```

Do not commit:

```text
.env
GeoLite2-City.mmdb
runtime outputs
reports generated during local runs
data/source generated files
data/minio/data lakehouse objects
data/clickhouse local database files
__pycache__
.pytest_cache
*.pyc
```

---

## 19. Final Validation Before Submission

A final project check should confirm:

- README links match actual files.
- Documentation uses only real commands supported by `main.py`.
- Diagrams exist under `diagrams/` with clean names.
- Screenshots exist under `screenshots/` with documented purpose.
- `.env` is absent from the repository.
- GeoLite2 `.mmdb` file is not committed.
- Runtime and data storage folders contain only `.gitkeep` placeholders after cleanup.
- Power BI file is present under `powerBI/`.
- Tests do not require generated runtime data unless the docs say to generate it first.
