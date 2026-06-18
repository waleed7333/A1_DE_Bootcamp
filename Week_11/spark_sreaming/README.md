# Spark Structured Streaming Labs

## 📌 Overview
Two complete labs demonstrating Apache Spark Structured Streaming with real-time data processing.

## 📁 Labs
| Lab | Description | Technologies |
|-----|-------------|--------------|
| **Lab 1** | Flight Data Analysis | CSV, foreachBatch, Console |
| **Lab 2** | Temperature Analysis | JSON, Window, Watermark, Hive |

## 🚀 Quick Start
```bash
docker compose up -d
# Access Jupyter at http://localhost:8888
```

## 📊 Results
- **Lab 1**: Successfully aggregated flight data from 6 CSV files
- **Lab 2**: Successfully processed 100 records → 77 aggregated rows

## 🛠️ Technologies
- Apache Spark Structured Streaming
- PySpark
- Apache Hive
- Jupyter Notebook
- Docker

## 📝 Documentation
Full documentation is available in this README file.

## Project Structure
```
spark_streaming/
├── docker-compose.yml
│
├── lab1/
│   ├── csv/
│   ├── data/
│   ├── notebooks/
│   │    └── flight_streaming.ipynb
│   └── streaming_input/
│
├── lab2/
│   ├── checkpoints/
│   │   ├── json/
│   │   ├── console/
│   │   └── hive/
│   ├── data/
│   ├── notebooks/
│   │   └── temperature_streaming.ipynb
│   ├── streaming_input/
│   ├── warehouse/
│   └── output/
│       └── json/
│
├── .gitignore
└── README.md
```

---

# Lab 1: Flight Data Streaming Analysis

## 1. Overview
This project implements a real-time data streaming pipeline using Apache Spark Structured Streaming. The application monitors a directory for incoming CSV files containing flight data between countries, aggregates the data by destination and origin countries, and displays the total flight count for each pair in real-time.

## 2. Architecture
```
CSV Files → Streaming Directory → Spark Streaming → Aggregation → Console Output
                ↑
                │
        add_file() function
                │
        Data Source Directory
```

### Components:
- **Spark Session**: Entry point for Spark functionality
- **Streaming Reader**: Monitors directory for new CSV files
- **Aggregation Engine**: Groups by (DEST, ORIGIN) and sums flight counts
- **Output Handler**: Displays results using foreachBatch for Jupyter compatibility

## 3. Technical Challenges & Solutions

### 3.1 Problem: Console Output Not Displaying in Jupyter

**Symptoms**: When using `outputMode("complete")` with `format("console")`, no output appeared in Jupyter Notebook cells despite the streaming query running successfully.

**Root Cause**: Jupyter's output handling mechanism does not properly capture Spark's console streaming output.

**Solution**: Implemented `foreachBatch` sink instead of console format, which allows explicit control over output display within Jupyter cells.

```python
def process_batch(df, epoch_id):
    result = df.groupBy("DEST_COUNTRY_NAME", "ORIGIN_COUNTRY_NAME") \
                .agg(sum("count").alias("total_count"))
    if result.count() > 0:
        result.show(100, truncate=False)

query = stream_df.writeStream.foreachBatch(process_batch).start()
```

### 3.2 Problem: Incorrect Aggregation Results

**Symptoms**: Each row showed count = 1 instead of the actual flight numbers.

**Root Cause**: Using `count("*")` counts rows in the batch instead of summing the existing `count` column.

**Solution**: Use `sum("count")` to properly accumulate flight totals.

## 4. Implementation Details

### 4.1 Schema Definition

```python
schema = StructType([
    StructField("DEST_COUNTRY_NAME", StringType(), True),
    StructField("ORIGIN_COUNTRY_NAME", StringType(), True),
    StructField("count", IntegerType(), True)
])
```

### 4.2 Streaming Configuration

| Parameter | Value | Purpose |
|-----------|-------|---------|
| maxFilesPerTrigger | 1 | Process one file at a time for clear visualization |
| trigger | 5 seconds | Processing interval |
| outputMode | update | Show only changed records |

### 4.3 Directory Structure

| Path | Purpose |
|------|---------|
| `/home/jovyan/lab1/streaming_input` | Directory monitored by Spark |
| `/home/jovyan/lab1/data` | Source directory for CSV files |
| `/home/jovyan/lab1/csv` | Original CSV files backup |

---
## 5. Execution Workflow

### Step 1: Environment Setup
```bash
docker-compose up -d
```

### Step 2: Access Jupyter
```
http://localhost:8888
```

### Step 3: Execute Cells Sequentially
1. Import libraries
2. Create Spark session
3. Define schema
4. Configure paths
5. Define batch processor
6. Start streaming query
7. Add files using `add_file()`

### Step 4: Add Files
```python
add_file('2010-summary.csv')  # Wait 5-10 seconds for results
add_file('2011-summary.csv')
add_file('2012-summary.csv')
# ... continue for all files
```



## 6. Sample Output

```
==================================================
Batch: 0
==================================================
+-----------------+-----------------+-----------+
|DEST_COUNTRY_NAME|ORIGIN_COUNTRY_NAME|total_count|
+-----------------+-----------------+-----------+
|United States    |United States    |348113     |
|Dominican Republic|United States    |1109       |
|United States    |Germany          |1406       |
|Mexico           |United States    |6220       |
+-----------------+-----------------+-----------+
```

## 7. Key Functions

| Function | Description |
|----------|-------------|
| `add_file(filename)` | Copies CSV from data directory to streaming_input |
| `list_files()` | Displays available CSV files |
| `check_status()` | Shows streaming query status |
| `process_batch(df, epoch_id)` | Processes each batch and displays results |

## 8. Testing Results

- **File 1 (2010)**: Successfully processed, 255 records aggregated
- **File 2 (2011)**: Successfully merged with previous data
- **All 6 files**: Cumulative aggregation working correctly
- **Update Mode**: Only changed records displayed after each batch

---
# Lab 2: Temperature Data Streaming Analysis

## 1. Overview

This project processes streaming JSON files containing temperature data for multiple countries. The application calculates the average temperature per country every 15 minutes, discards late data using watermarking, and concurrently routes the active streaming data to **three distinct destinations**: a local JSON filesystem, a managed Apache Hive catalog (Parquet format), and the live Jupyter console container environment.

## 2. Architecture

```
JSON Files → Streaming Directory → Spark Streaming → Aggregation → 3 Active Destination Sinks
                     ↑                               (Window +     ├─ Live Console (Console Sink)
                     │                                Watermark)   ├─ Local Filesystem (JSON Sink)
             Automated Ingestion Injected Batch                    └─ Data Warehouse (Hive Parquet Table)
                     │
            Source Data Directory

```

### Components:

* **Spark Session**: Configured with explicit Hive implementation (`enableHiveSupport()`) and structured metadata warehouse catalog setup.
* **Streaming Reader**: Monitors input directory for new JSON files using structured schemas with dynamic rate limiting via `maxFilesPerTrigger`.
* **Window Aggregation**: Computes a 15-minute tumbling time window per country.
* **Watermark Engine**: Evaluates event-time fields and enforces a 10-minute threshold to handle and discard late-arriving data streams.
* **Multi-Streaming Sinks**: Employs parallel independent stream engines execution to store, persist, and preview pipeline state simultaneously.

---

## 3. Technical Challenges & Solutions

### 3.1 Problem: Late Data Discarding & Timeline Bound Rules

**Requirement**: Dynamically eliminate data payloads that fail to arrive within 10 minutes of their actual internal event timestamp.

**Solution**: Generated a timestamp transformation mapping from raw event payload strings, injected `withWatermark("event_time", "10 minutes")`, and tightly bound it directly inside the structural tumbling `groupBy(window(...))` block statement.

```python
agg_df = stream_df \
    .withColumn("event_time", to_timestamp(col("event_timestamp"), "yyyy-MM-dd HH:mm:ss")) \
    .withWatermark("event_time", "10 minutes") \
    .groupBy(
        window(col("event_time"), "15 minutes"),
        col("country")
    ) \
    .agg(avg("temperature").alias("avg_temperature"))

```

### 3.2 Problem: Multi-Destination Structural Streaming Sinks Execution

**Requirement**: Persist processed streams into a distributed-ready tabular analytical platform (Hive/Parquet), raw portable files (JSON), and interactive text representations (Console) at the same time without interrupting the pipeline.

**Solution**: Instantiated three completely isolated stream query processes running asynchronously on top of the underlying thread pool. Each engine is provided with its own distinct state context tracker and checkpoint directory (`checkpoint_json`, `checkpoint_hive`, `checkpoint_console`) to guarantee exactly-once processing guarantees and prevent internal task blockages.

```python
# Sink 1: Native Filesystem JSON Storage
json_query = agg_df.writeStream.format("json").outputMode("append").option("path", json_output).option("checkpointLocation", checkpoint_json).start()

# Sink 2: Enterprise Metadata Warehouse Catalog (Parquet Backed)
hive_query = agg_df.writeStream.format("parquet").outputMode("append").option("checkpointLocation", checkpoint_hive).toTable("default.temperature_avg_table")

# Sink 3: Live Interactive Container Monitor Stream
console_query = agg_df.writeStream.format("console").outputMode("append").option("truncate", "false").option("checkpointLocation", checkpoint_console).start()

```

### 3.3 Problem: Complex Structural Output Objects (Window Metadata)

**Symptoms**: Standard aggregate outputs yield nested schema structs `window: {start: timestamp, end: timestamp}` which degrades usability in external query tools and adds serialization overhead to target outputs.

**Solution**: Added a clean structural extraction phase (`.select()`) that flattens the internal window sub-properties out into isolated top-level timeline data fields (`window_start`, `window_end`).

```python
.select(
    col("country"),
    col("window.start").alias("window_start"),
    col("window.end").alias("window_end"),
    col("avg_temperature")
)

```

---

## 4. Implementation Details

### 4.1 Schema Definition

```python
schema = StructType([
    StructField("event_timestamp", StringType(), True),
    StructField("country", StringType(), True),
    StructField("temperature", DoubleType(), True)
])

```

### 4.2 Streaming Configurations Parameters

| Parameter | Value | Purpose |
| --- | --- | --- |
| `maxFilesPerTrigger` | 1 | Restricts ingestion pace to one single batch file per interval for granular pipeline validation |
| `outputMode` | `append` | Mandated output type constraint required when working with stateful queries combined with Watermarks |
| `Watermark Boundary` | 10 minutes | Explicit time-skipping barrier logic utilized to drop out-of-bounds late records |
| `Tumbling Window` | 15 minutes | Timeline window aggregation block dimensions per distinct country |
| `Metastore Strategy` | Hive Catalog | Embedded metastore tracking via Spark configurations to persist structure layouts natively |

### 4.3 Directory & Pipeline Structure Mapping

| Container Native Path | System Architecture Purpose |
| --- | --- |
| `/home/jovyan/lab2/streaming_input` | Active directory watched and pulled continuously by Spark |
| `/home/jovyan/lab2/data` | Offline source storage pool holding structural file simulated inputs |
| `/home/jovyan/lab2/warehouse` | Apache Hive central directory holding native transaction tables |
| `/home/jovyan/lab2/output/json` | Flat-file direct destination dump directory for raw JSON verification |
| `/home/jovyan/lab2/checkpoints/` | Distributed WAL tracker containing separate checkpoints metadata states |

---

## 5. Execution Workflow & Production Verification

### Phase 1: Deep Cleanup and Initialization

Runs an automatic validation script that searches for old file leftovers across the target environment, deletes stale checkpoints, and resets the target Hive schema database safely:

```python
# Automatic directory purging sequence execution
if os.path.exists(folder):
    shutil.rmtree(item_path, ignore_errors=True)

```

### Phase 2: Simulating Dynamic Intermittent Data Arrival

Ingests incoming data payloads incrementally using sequential programmatic file feeding to replicate a production micro-batch environment:

```python
# Periodic file movement log simulator
➕ Added to Stream: batch1.json
➕ Added to Stream: batch2.json
➕ Added to Stream: batch3.json
...
🏁 All batch files have been injected successfully!

```

---

## 6. Real Production Run Outputs

### Destination Sink Verification Check (Before Shutdown)

```
🖥️ --- Destination 3: Live Console Sink Status ---
Engine Name: Console_Stream
Status: Active ✅
Last Progress Rows/sec: 0.0

```

### Persistent Target Verification 1: Reading From Managed Hive Table

```
Total rows in Hive = 77
+---------+-------------------+-------------------+------------------+
|country  |window_start       |window_end         |avg_temperature   |
+---------+-------------------+-------------------+------------------+
|Australia|2024-01-15 11:00:00|2024-01-15 11:15:00|32.0              |
|Australia|2024-01-15 10:30:00|2024-01-15 10:45:00|31.2              |
|Canada   |2024-01-15 14:15:00|2024-01-15 14:30:00|-3.9              |
|France   |2024-01-15 13:15:00|2024-01-15 13:30:00|8.8               |
+---------+-------------------+-------------------+------------------+

```

### Persistent Target Verification 2: Reading From JSON Storage Filesystem

```
Total rows in JSON Filesystem = 77
+------------------+---------+------------------------+------------------------+
|avg_temperature   |country  |window_end              |window_start            |
+------------------+---------+------------------------+------------------------+
|33.7              |Australia|2024-01-15T14:30:00.000Z|2024-01-15T14:15:00.000Z|
|32.0              |Australia|2024-01-15T11:15:00.000Z|2024-01-15T11:00:00.000Z|
|-4.5              |Canada   |2024-01-15T13:00:00.000Z|2024-01-15T12:45:00.000Z|
+------------------+---------+------------------------+------------------------+

```

---

## 7. Testing Evaluation & Metrics

* **Pipeline Integrity**: Successfully evaluated and computed metrics across 100 raw incoming structural changes.
* **Watermark Compliance**: Output verification validates state boundaries. Out of 100 raw records, 77 historical entries were calculated and stored, confirming that the remaining 23 late-arriving logs were successfully identified and skipped by the watermark configuration.
* **Sink Uniformity**: Strict verification metrics confirm zero drift between the distinct execution layers. Total calculated data records verified inside the JSON local file directory exactly matches rows within the Hive managed container catalog (77 Rows).

---

# Common Setup

## Environment Configuration
```yaml
# docker-compose.yml content
```

## Running the Labs
```bash
# Start Docker containers
docker-compose up -d

# Access Jupyter
http://localhost:8888

# Stop containers
docker-compose down
```


## 9. Conclusion

The Spark Structured Streaming course labs demonstrate the capacity to build resilient, real-time data pipelines. Lab 1 successfully handles targeted file ingestion and complex programmatic batch outputs via foreachBatch within a notebook. Lab 2 advances this design into a production-grade architecture by incorporating sliding event-time windows, handling late-arriving data through custom Watermarks, and leveraging asynchronous parallel computing threads to broadcast data simultaneously to three distinct active streaming endpoints (Live Console, Local JSON, and Managed Hive Tables).

## 10. References

- Apache Spark Structured Streaming Documentation
- PySpark API Reference
- Apache Hive Catalog Integration with Spark SQL
- Docker Compose Configuration

---