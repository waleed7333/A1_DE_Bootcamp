# Operations and Validation

## Purpose

This document describes the operational control, health visibility, validation model, and evidence outputs used by **Clickstream Personalization Platform**.

The platform is designed[object Object] with a clear operational lifecycle:

```text
Initialize
  → Start
  → Stream
  → Refresh
  → Validate
  → Publish Serving
  → Inspect Status
  → Stop or Reset
```

Operational visibility is provided through CLI commands, JSON reports, Iceberg audit tables, ClickHouse serving evidence, and a read-only Streamlit Operations Console.

The goal of the operations layer is to make the platform state observable, verifiable, and repeatable.

---

## Operational Architecture

The project uses a local Docker Compose environment controlled by the main CLI.

```text
main.py
  → platform orchestration helpers
  → Docker Compose services
  → Spark streaming and batch jobs
  → Airflow analytics refresh
  → Iceberg audit evidence
  → ClickHouse serving evidence
  → Operations Console
```

The operations model separates three concerns:

| Concern | Responsibility |
|---|---|
| Runtime control | Start, stop, initialize, reset, and inspect the local platform. |
| Validation | Confirm that ingestion, lakehouse, quality, relationships, and serving outputs are correct. |
| Evidence | Store structured operational results in reports and audit tables. |

---

## Runtime Services

The platform runs the following services.

| Service | Role |
|---|---|
| `postgres` | Transactional source system and Iceberg JDBC catalog backend. |
| `zookeeper` | Kafka coordination service. |
| `kafka1` | Kafka broker. |
| `kafka2` | Kafka broker. |
| `kafka3` | Kafka broker. |
| `kafka-ui` | Kafka topic and consumer visibility. |
| `debezium` | PostgreSQL CDC connector runtime. |
| `minio` | S3-compatible object storage for Iceberg warehouse data. |
| `filebeat` | Web server log shipper into Kafka. |
| `spark-engine` | Spark runtime for streaming and batch jobs. |
| `airflow` | Batch orchestration for analytical refresh jobs. |
| `clickhouse` | OLAP serving database for Power BI. |
| `observability-ui` | Streamlit Operations Console. |

These services are started and stopped through the project CLI and Docker Compose.

---

## CLI Control Plane

The main entry point is:

```text
main.py
```

The CLI manages the local platform lifecycle and provides a consistent way to operate the project.

### Commands

| Command | Purpose |
|---|---|
| `python main.py init` | Creates a clean first-run platform state and executes the full initialization workflow. |
| `python main.py start` | Starts the existing local platform state and resumes streaming. |
| `python main.py status` | Reports current service health, streaming state, validation status, and active serving build. |
| `python main.py stop` | Stops streaming and Docker services while preserving local state. |
| `python main.py reset --confirm` | Removes generated runtime state and prepares the project for a clean first run. |

---

## Initialization Workflow

The initialization workflow creates the complete platform state from the repository configuration and source definitions.

```bash
python main.py init
```

The initialization sequence performs:

| Step | Responsibility |
|---|---|
| Environment validation | Confirms required host tools, configuration files, credentials, and local dependencies. |
| Source generation | Creates local source files and reference data used by the ingestion workflows. |
| Infrastructure startup | Starts Docker Compose services. |
| Lakehouse bootstrap | Creates Iceberg namespaces and tables. |
| Product catalog load | Loads the static product catalog into Iceberg. |
| PostgreSQL seed | Loads users, orders, and order items into PostgreSQL. |
| Debezium connector setup | Creates CDC connectors for users, orders, and order items. |
| Streaming startup | Starts Spark Structured Streaming over Kafka topics. |
| Controlled CDC mutation | Applies deterministic source changes after the initial snapshot. |
| Refresh and validation | Runs analytical batch jobs and validates the lakehouse. |
| Serving publication | Publishes ClickHouse serving tables and stable views. |

The result is a complete local analytical platform with raw, processed, audit, serving, and dashboard-ready data layers.

---

## Start Workflow

The start command resumes an existing local project state.

```bash
python main.py start
```

The start workflow performs:

| Step | Responsibility |
|---|---|
| Start services | Starts Docker Compose services required by the platform. |
| Resume streaming | Starts Spark Structured Streaming. |
| Resume source generation | Starts the live source generator where configured. |
| Verify heartbeat | Confirms the streaming process reports initial progress. |
| Report status | Returns the current operational state. |

This command is used when the local platform state already exists and the goal is to continue operating it.

---

## Status Workflow

The status command reports the current platform state.

```bash
python main.py status
```

The status output includes:

| Area | Evidence |
|---|---|
| Service state | Docker service health and running status. |
| HTTP probes | Health checks for MinIO, Debezium, Airflow, and ClickHouse. |
| Spark streaming | Streaming process state and completed batch evidence. |
| Validation | Latest lakehouse validation status. |
| Serving | Active ClickHouse serving build. |
| Overall platform status | Consolidated health result. |

A healthy status indicates that services are running, streaming is active, validation has passed, and an active serving build is available.

---

## Stop Workflow

The stop command shuts down the platform while preserving local state.

```bash
python main.py stop
```

The stop workflow performs:

| Step | Responsibility |
|---|---|
| Stop source generation | Stops the live source generator process. |
| Stop streaming | Stops the Spark streaming process. |
| Stop services | Stops Docker Compose containers. |
| Preserve state | Keeps local data, reports, checkpoints, and generated files. |

This keeps the project ready for later startup without rebuilding the platform from zero.

---

## Reset Workflow

The reset command removes generated runtime state and returns the project to a clean first-run state.

```bash
python main.py reset --confirm
```

The reset workflow is used when the platform should be rebuilt from the beginning.

It removes dynamic local state such as:

```text
runtime/
reports generated from previous runs
generated source outputs
container-backed runtime data
local checkpoints
```

It preserves source code, configuration files, documentation, reference definitions, Docker files, and project assets.

---

## Operations Console

The project includes a Streamlit-based Operations Console.

```text
observability_ui/
```

The console provides read-only operational visibility into the project.

### Console Sections

| Section | Purpose |
|---|---|
| Overview | Summarizes platform health, validation status, serving status, and key operational indicators. |
| Infrastructure | Displays Docker service state and endpoint health checks. |
| Kafka & CDC | Shows Kafka topic readiness and Debezium connector status. |
| Spark Streaming | Shows streaming activity, batch progress, and stream state evidence. |
| Lakehouse Storage | Shows Iceberg table availability and storage-layer evidence. |
| Data Quality | Shows accepted, rejected, duplicate, and quarantine evidence. |
| SCD Type 2 | Shows user profile current-state and historical profile evidence. |
| Batch & APIs | Shows Airflow refresh jobs and external enrichment status. |
| Serving & Power BI | Shows ClickHouse serving build state and Power BI view readiness. |

The console is intentionally read-only. It presents evidence from the platform without modifying data or changing runtime behavior.

---

## Operational Evidence Files

The platform writes structured evidence files during operation.

| File | Purpose |
|---|---|
| `runtime/observability/latest.json` | Latest consolidated health snapshot. |
| `runtime/observability/history.jsonl` | Historical health snapshots. |
| `reports/validation_latest.json` | Latest lakehouse validation report. |
| `reports/serving_latest.json` | Latest ClickHouse serving publication report. |
| `reports/streaming_start_report.json` | Streaming startup evidence. |
| Runtime logs | Process-level execution details for Spark and supporting workflows. |

These files allow the platform state to be inspected through CLI commands, the Operations Console, and direct report review.

---

## Audit Tables

Operational evidence is also stored inside Iceberg audit tables.

| Table | Purpose |
|---|---|
| `ecommerce.audit.pipeline_runs` | Pipeline run status and execution metadata. |
| `ecommerce.audit.quality_metrics` | Source-level quality metrics and reconciliation counts. |
| `ecommerce.audit.quarantine_records` | Invalid and duplicate records with reason codes. |
| `ecommerce.audit.external_api_failures` | Weather and holiday enrichment request failures. |
| `ecommerce.audit.watermarks` | Streaming and batch progress markers. |
| `ecommerce.audit.validation_runs` | Lakehouse validation result history. |
| `ecommerce.audit.serving_builds` | Serving build activation and publication evidence. |

The audit tables make the pipeline state queryable and durable inside the lakehouse.

---

## Validation Model

Validation is part of the normal analytical refresh workflow.

```text
Iceberg tables
  → validate_lakehouse
  → validation_runs
  → reports/validation_latest.json
  → Operations Console
```

The validation layer checks whether the lakehouse is ready for serving publication.

### Validation Areas

| Area | Validation Purpose |
|---|---|
| Table availability | Confirms required Iceberg tables exist and can be queried. |
| Raw and clean data | Confirms ingestion produced expected raw and processed outputs. |
| Reconciliation | Validates source record accounting across accepted, rejected, and duplicate records. |
| Quarantine | Confirms invalid and duplicate records are visible as evidence. |
| CDC outputs | Confirms users, orders, and order items CDC tables are available. |
| SCD Type 2 | Confirms current user profile state and SCD2 output availability. |
| Relationship coverage | Checks important analytical joins across request, session, user, product, checkout, and order keys. |
| Context enrichment | Confirms weather and holiday context tables are available. |
| Serving readiness | Confirms the platform has the data required for serving publication. |

---

## Data Quality Validation

The data quality model follows the reconciliation rule:

```text
Input records = Accepted records + Rejected records + Duplicate records
```

This rule is tracked through:

```text
ecommerce.audit.quality_metrics
```

### Quality Validation Outputs

| Output | Purpose |
|---|---|
| `input_records` | Number of records read from the source. |
| `accepted_records` | Number of records accepted into clean tables. |
| `rejected_records` | Number of invalid records routed to quarantine. |
| `duplicate_records` | Number of duplicate records detected. |
| `source_name` | Source being validated. |
| `pipeline_run_id` | Pipeline run associated with the metric. |

This creates a measurable and auditable quality trail for streaming and batch operations.

---

## Quarantine Validation

Invalid and duplicate records are preserved in:

```text
ecommerce.audit.quarantine_records
```

The quarantine model validates that records failing source contracts are traceable.

### Quarantine Evidence

| Evidence | Description |
|---|---|
| Source | Identifies the source or topic that produced the record. |
| Record key | Preserves the source-level record identifier where available. |
| Reason code | Explains the quarantine reason. |
| Raw payload | Preserves the rejected record payload or representative content. |
| Timestamp | Records when the quarantine event occurred. |
| Pipeline run | Links the quarantine event to a pipeline execution. |

Quarantine records protect clean analytical tables while preserving inspection evidence.

---

## CDC Validation

CDC validation focuses on the PostgreSQL-to-Debezium-to-Kafka-to-Iceberg path.

### CDC Sources

| Source Table | Kafka Topic | Clean Table |
|---|---|---|
| `users` | `users-cdc` | `users_cdc_clean` |
| `orders` | `orders-cdc` | `orders_cdc_clean` |
| `order_items` | `order-items-cdc` | `order_items_cdc_clean` |

### CDC Evidence

| Field | Purpose |
|---|---|
| `op` | CDC operation type. |
| `source_lsn` | Source database ordering metadata. |
| `source_ts_ms` | Source change timestamp. |
| Kafka metadata | Topic, partition, offset, and ingestion traceability. |

CDC validation confirms that transactional changes are captured, cleaned, and available for analytical processing.

---

## SCD Type 2 Validation

The user SCD Type 2 table is validated as part of the analytical refresh.

```text
ecommerce.processed.user_profile_scd2
```

Validation focuses on:

| Check | Purpose |
|---|---|
| Current profile rows | Confirms active current rows exist for user reporting. |
| User key consistency | Confirms user records maintain stable identifiers. |
| Effective timestamps | Confirms profile versions include effective date fields. |
| Current flag | Confirms current records are identified through `is_current`. |
| CDC lineage | Confirms source ordering metadata is preserved where required. |

The SCD2 table supports current user dimensions and historical profile analysis.

---

## External Enrichment Validation

The project validates external context enrichment outputs.

### Weather

```text
ecommerce.processed.weather_clean
```

Weather validation confirms that observed location-hour combinations can be enriched and stored with normalized weather fields.

### Holidays

```text
ecommerce.processed.holidays_clean
```

Holiday validation confirms that country-year context is available for holiday-aware analysis.

### API Failure Evidence

```text
ecommerce.audit.external_api_failures
```

External API failure evidence keeps context enrichment observable and traceable.

---

## Serving Validation

Serving validation confirms that the ClickHouse reporting contract is ready for Power BI.

The serving publication writes:

```text
reports/serving_latest.json
ecommerce.audit.serving_builds
```

### Serving Checks

| Check | Purpose |
|---|---|
| Physical table publication | Confirms serving tables are written to ClickHouse. |
| Active build registration | Confirms the latest successful serving build is active. |
| Stable view availability | Confirms all expected `v_*` views are queryable. |
| View contract count | Confirms the final twelve Power BI views are present. |
| Row count evidence | Records serving output counts by table. |
| Audit evidence | Records the serving build in Iceberg audit storage. |

The final Power BI view contract contains twelve stable views.

---

## Final Power BI View Contract

| Category | Views |
|---|---|
| Dimensions | `v_dim_date`, `v_dim_product`, `v_dim_user_current` |
| Facts | `v_fact_clickstream_event`, `v_fact_order`, `v_fact_order_item` |
| Journey Marts | `v_mart_journey_session`, `v_mart_navigation_paths` |
| Product and Experience Marts | `v_mart_product_performance_daily`, `v_mart_web_experience_daily` |
| Context and Personalization Marts | `v_mart_context_impact_daily`, `v_mart_personalization_candidates` |

Power BI reads these views only. Dashboard-specific measures and calculations are handled inside Power BI.

---

## Validation Reports

### `reports/validation_latest.json`

This report stores the latest lakehouse validation result.

It includes:

| Field | Purpose |
|---|---|
| `status` | Validation status. |
| `validation_id` | Validation run identifier. |
| `checks` | Validation checks and results. |
| `created_at` | Validation timestamp. |

### `reports/serving_latest.json`

This report stores the latest ClickHouse serving publication result.

It includes:

| Field | Purpose |
|---|---|
| `status` | Serving publication status. |
| `serving_build_id` | Active serving build identifier. |
| `validation_id` | Related validation run identifier. |
| `counts` | Row count summary by serving table. |
| `table_validation` | Serving table validation result. |
| `view_validation` | Stable view validation result. |
| `activated_at_utc` | Build activation timestamp. |

---

## Health Evidence Model

The status workflow consolidates service health, streaming activity, validation evidence, and serving readiness into a single operational summary.

A ready platform state is represented by running services, active streaming evidence, passed validation, and an available serving build for the Power BI view contract.

---

## Runtime Health Checks

The status workflow checks:

| Component | Evidence |
|---|---|
| PostgreSQL | Container state. |
| ZooKeeper | Container state. |
| Kafka brokers | Container state and health. |
| Kafka UI | Container state. |
| Debezium | Container state and HTTP health. |
| MinIO | Container state and HTTP health. |
| Filebeat | Container state. |
| Spark | Container state and streaming evidence. |
| Airflow | Container state and HTTP health. |
| ClickHouse | Container state and HTTP health. |
| Operations Console | Container state. |
| Latest validation | Latest validation report status. |
| Active serving build | Latest active serving build identifier. |

The health model combines service-level and data-platform-level evidence.

---

## Operational Commands

### Check platform status

```bash
python main.py status
```

### Run analytical refresh

```bash
python - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "src"))

from platform_core.orchestration import run_analytics_refresh

results, ok, run_id = run_analytics_refresh(root, timeout_seconds=1800)

print()
print("ANALYTICS REFRESH")
print("=" * 80)
print("Run ID:", run_id)
print("Status:", "PASSED" if ok else "FAILED")
for item in results:
    print(f"{item.status:5} {item.job:25} {item.detail}")
print("=" * 80)

raise SystemExit(0 if ok else 2)
PY
```

### Inspect latest serving evidence

```bash
python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("reports/serving_latest.json").read_text(encoding="utf-8"))

print()
print("SERVING VALIDATION SUMMARY")
print("=" * 80)
print("Status:", payload.get("status"))
print("Build:", payload.get("serving_build_id"))
print("Table validation:", payload.get("table_validation", {}).get("status"))
print("View validation:", payload.get("view_validation", {}).get("status"))
print("Expected views:", payload.get("view_validation", {}).get("expected_view_count"))
print("Observed views:", payload.get("view_validation", {}).get("observed_view_count"))
print("Failures:", payload.get("view_validation", {}).get("failures"))
print("=" * 80)
print()
PY
```

### Check ClickHouse serving views

```bash
docker compose exec -T clickhouse bash -lc '
clickhouse-client \
  --user "$CLICKHOUSE_USER" \
  --password "$CLICKHOUSE_PASSWORD" \
  --query "
SELECT '\''v_dim_date'\'' AS view_name, count() AS row_count FROM personalization_olap.v_dim_date
UNION ALL SELECT '\''v_dim_product'\'', count() FROM personalization_olap.v_dim_product
UNION ALL SELECT '\''v_dim_user_current'\'', count() FROM personalization_olap.v_dim_user_current
UNION ALL SELECT '\''v_fact_clickstream_event'\'', count() FROM personalization_olap.v_fact_clickstream_event
UNION ALL SELECT '\''v_fact_order'\'', count() FROM personalization_olap.v_fact_order
UNION ALL SELECT '\''v_fact_order_item'\'', count() FROM personalization_olap.v_fact_order_item
UNION ALL SELECT '\''v_mart_journey_session'\'', count() FROM personalization_olap.v_mart_journey_session
UNION ALL SELECT '\''v_mart_navigation_paths'\'', count() FROM personalization_olap.v_mart_navigation_paths
UNION ALL SELECT '\''v_mart_product_performance_daily'\'', count() FROM personalization_olap.v_mart_product_performance_daily
UNION ALL SELECT '\''v_mart_web_experience_daily'\'', count() FROM personalization_olap.v_mart_web_experience_daily
UNION ALL SELECT '\''v_mart_context_impact_daily'\'', count() FROM personalization_olap.v_mart_context_impact_daily
UNION ALL SELECT '\''v_mart_personalization_candidates'\'', count() FROM personalization_olap.v_mart_personalization_candidates
ORDER BY view_name
FORMAT PrettyCompact
"
'
```

---

## Development Quality Checks

The project includes formatting, linting, and tests.

```bash
black .
ruff check .
pytest -q
```

Targeted syntax checks can be executed with:

```bash
python -m py_compile \
  main.py \
  airflow/dags/analytics_refresh.py \
  observability_ui/app.py \
  observability_ui/services/probes.py \
  spark_jobs/bootstrap_lakehouse.py \
  spark_jobs/streaming_ingestion.py \
  spark_jobs/weather_enrichment.py \
  spark_jobs/holiday_enrichment.py \
  spark_jobs/user_scd2_incremental.py \
  spark_jobs/validate_lakehouse.py \
  spark_jobs/publish_clickhouse.py
```

The test suite includes contract checks for the final serving model, observability structure, project configuration, and documentation alignment.

---

## Operations Console Evidence

The Operations Console presents evidence from several layers.

| Evidence Source | Used For |
|---|---|
| Docker service state | Infrastructure status. |
| HTTP probes | Endpoint availability. |
| Runtime observability JSON | Latest health snapshot and historical status. |
| Spark streaming evidence | Streaming batch progress and state. |
| Iceberg table checks | Lakehouse table visibility. |
| Quality metrics | Accepted, rejected, and duplicate record evidence. |
| Quarantine records | Invalid and duplicate record inspection. |
| Validation reports | Latest lakehouse validation state. |
| Serving reports | Active serving build and view readiness. |
| ClickHouse queries | Power BI serving view availability. |

The console provides a compact operational view of the full data platform.

---

## Evidence Screenshots

Operational screenshots are stored in:

```text
screenshots/
```

Representative evidence includes:

| Area | Screenshot |
|---|---|
| Docker health | `01_docker_compose_healthy.png` |
| Platform health | `02_main_status_healthy_1.png`, `02_main_status_healthy_2.png` |
| Kafka topics | `03_kafka_topics.png` |
| MinIO warehouse | `04_minio_warehouse_bucket_1.png`, `04_minio_warehouse_bucket_2.png`, `04_minio_warehouse_bucket_3.png` |
| Spark streaming | `05_spark_streaming_status.png` |
| Airflow refresh | `06_airflow_or_refresh_jobs_passed_1.png`, `06_airflow_or_refresh_jobs_passed_2.png` |
| Validation | `07_validation_latest_passed_1.png`, `07_validation_latest_passed_2.png` |
| Serving publication | `08_serving_latest_passed.png` |
| ClickHouse row counts | `14_clickhouse_row_counts.png` |
| Context analytics | `15_clickhouse_geo_weather_context_1.png`, `15_clickhouse_geo_weather_context_2.png` |
| Operations Console | Operations screenshots where included in the repository. |
| Power BI | `16_powerbi_dashboard_Executive_Overview.png`, `17_powerbi_dashboard_Growth&Revenue.png`, `18_powerbi_dashboard_Funnel&Journey.png`, `19_powerbi_dashboard_Personalization&Context.png`, `20_powerbi_data_model.png` |

---

## Final Operational Contract

The final operational contract is:

```text
CLI commands manage the platform lifecycle.
Docker Compose runs the service topology.
Spark Structured Streaming processes Kafka topics.
Airflow triggers scheduled analytical refresh jobs.
Iceberg stores raw, processed, and audit evidence.
ClickHouse publishes twelve stable Power BI views.
Power BI consumes curated serving views only.
Operations Console surfaces health, quality, validation, and serving evidence.
```

The platform state is verifiable through CLI output, JSON reports, audit tables, ClickHouse checks, screenshots, and the Operations Console.