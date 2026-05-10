# Smart Traffic Data Pipeline

## Intelligent Traffic Monitoring and Analysis System for Smart Cities

### Apache NiFi | PostgreSQL | Hadoop HDFS | Docker | Python

---

## Table of Contents

1. [Real-World Scenario](#1-real-world-scenario)
2. [The Data Problem](#2-the-data-problem)
3. [Data Sources - Complete Field Specifications](#3-data-sources---complete-field-specifications)
4. [System Architecture](#4-system-architecture)
5. [NiFi Pipeline Design](#5-nifi-pipeline-design)
6. [Data Cleaning Strategy](#6-data-cleaning-strategy)
7. [Best Practices Implementation](#7-best-practices-implementation)
8. [Challenges and Solutions](#8-challenges-and-solutions)
9. [Operations Guide](#9-operations-guide)
10. [Performance Monitoring](#10-performance-monitoring)
11. [Future Expansion Plan](#11-future-expansion-plan)
12. [Appendices](#12-appendices)

---

## 1. Real-World Scenario

### A Smart City Monitoring Traffic Flow

In a major metropolitan city such as Riyadh or Dubai, thousands of sensors and cameras are deployed across key intersections. These sensors transmit data **every second** about road conditions. The objective extends beyond simple monitoring to **predicting congestion before it occurs**, automatically detecting accidents, and dynamically adjusting traffic light timing.

Simultaneously, a **centralized system** (relational database) maintains a registry of all intersections: their names, districts, signal types, last maintenance dates, and more. This registry changes slowly: a new intersection is added as the city expands, a signal undergoes maintenance, timing is adjusted, or firmware is updated.

**The Engineering Challenge:** How do we bring these two sources together—one fast and streaming (thousands of readings per second), the other slowly changing (daily or weekly updates)—clean them, merge them, and store them for downstream analytics?

**Stakeholders Benefiting From This System:**
- **Traffic Control Room:** Real-time congestion and accident monitoring
- **Urban Planning Department:** Traffic pattern analysis for new road planning
- **Maintenance Department:** Identifying signals requiring maintenance based on performance
- **Civil Defense:** Accident detection and emergency response routing

---

## 2. The Data Problem

### Why Is the Data "Dirty"?

In real-world systems, data is never perfect. We intentionally designed our data generators to produce **realistic flaws** that mirror actual field conditions. The goal: build a robust pipeline capable of handling real-world data chaos.

### Defect Classification

We classified defects into **5 main categories**:

| Category | Description | Severity |
|----------|-------------|----------|
| **Missing Values** | Null or empty values | Medium |
| **Invalid Formats** | Text instead of numbers, malformed dates | High |
| **Logical Errors** | Negative values, internal contradictions | High |
| **Duplicates** | Repeated records | Low |
| **Outliers** | Unreasonable extreme values | Medium |

---

## 3. Data Sources - Complete Field Specifications

### Source 1: Traffic Sensor Simulator

**File:** `generate_transactions.py`
**Format:** NDJSON (Newline Delimited JSON)
**Generation Rate:** New file every 2-5 seconds
**File Content:** 3-8 records per file
**Naming Convention:** `Transaction_YYYYMMDD_HHMMSS_microseconds.json`

#### Complete Field Specifications for Source 1:

| # | Field Name | Type | Description | Value Source | Intentional Flaws |
|---|-----------|-------|-------------|--------------|-------------------|
| 1 | `event_id` | UUID | Unique traffic event identifier | `uuid.uuid4()` | 12% duplicates (DUPLICATE_EVENT) |
| 2 | `intersection_id` | VARCHAR(8) | Intersection ID (INT-0001 to INT-0030) | Random selection from list | Clean |
| 3 | `vehicle_type` | ENUM | Type of vehicle | car, truck, bus, motorcycle, emergency | car appears more frequently (realistic) |
| 4 | `vehicle_count` | INTEGER | Vehicles counted in last 5 seconds | 0-30 normal range | null, -1, "unknown" |
| 5 | `avg_speed_kmh` | FLOAT | Average speed (km/h) | 0-80 normal range | null, -10.0, 150.0 |
| 6 | `congestion_level` | ENUM | Traffic congestion level | smooth, moderate, heavy, gridlock | null, "", contradictory value (20%) |
| 7 | `district` | VARCHAR(50) | City district | Downtown, Industrial Zone, etc. | null, "", "downtown" (wrong case) |
| 8 | `lane_id` | INTEGER | Lane number | 1-4 | null |
| 9 | `temperature_c` | FLOAT | Road surface temperature (°C) | 20-70 normal range | null, -99.9 (error code), 95.0 |
| 10 | `visibility_m` | FLOAT | Visibility range (meters) | 50-5000 normal range | null, 0.0, -1.0 |
| 11 | `accident_flag` | BOOLEAN | Accident detected? | Logic: speed<5 + gridlock = true | null, true with high speed (error) |
| 12 | `signal_status` | ENUM | Traffic light status | green, yellow, red, flashing | null |
| 13 | `event_timestamp` | TIMESTAMP | Event timestamp | ISO 8601 | Always valid |

#### Flaw Generation Logic (Example):

```python
# Example: generating vehicle_count with flaws
def generate_vehicle_count():
    return random.choice([
        random.randint(0, 30),    # 80% - valid value
        None,                      # 10% - sensor offline
        -1,                        # 5% - error code
        "unknown"                  # 5% - format error
    ])
```

---

### Source 2: Intersection Reference Database

**File:** `generate_db.py`
**Database:** PostgreSQL 13
**Table:** `intersections`
**Update Rate:** Every 10-15 seconds (30% insert, 70% update)

#### Complete Table Schema:

| # | Column Name | Type | Constraints | Description | Intentional Flaws |
|---|------------|------|-------------|-------------|-------------------|
| 1 | `intersection_id` | VARCHAR(10) | PRIMARY KEY | Intersection identifier (INT-XXXX) | None (primary key) |
| 2 | `intersection_name` | VARCHAR(100) | NOT NULL | Names of intersecting streets | None |
| 3 | `district` | VARCHAR(50) | - | City district | null, "", "unknown" |
| 4 | `total_lanes` | INTEGER | - | Number of lanes (2-4) | null |
| 5 | `has_camera` | BOOLEAN | - | Has surveillance camera? | None |
| 6 | `has_sensor` | BOOLEAN | - | Has ground sensor? | None |
| 7 | `signal_type` | VARCHAR(20) | - | Type of traffic light | smart, fixed, adaptive, manual |
| 8 | `signal_timing_sec` | INTEGER | - | Green light duration (seconds) | null, 0, -1, "N/A" |
| 9 | `last_maintenance` | DATE | - | Last maintenance date | None (may be old) |
| 10 | `status` | VARCHAR(20) | - | Intersection status | active, maintenance, offline, null |
| 11 | `firmware_version` | VARCHAR(10) | - | Traffic light firmware version | null |
| 12 | `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update (used for incremental extraction) | None |

#### Simulation Logic:

```python
# 30% chance: add new intersection (city expansion)
if random.random() < 0.30:
    add_new_intersection()

# 70% chance: update existing intersection (maintenance, timing change)
else:
    update_existing_intersection()
```

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DOCKER ENVIRONMENT                            │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ python-     │  │ python-     │  │          │  │              │  │
│  │ simulator   │  │ simulator   │  │ postgres │  │   hadoop     │  │
│  │ (Traffic)   │  │ (DB Gen)    │  │  :5432   │  │ :9870 :9000  │  │
│  └──────┬──────┘  └──────┬──────┘  └────┬─────┘  └──────┬───────┘  │
│         │                │              │               │          │
│         ▼                ▼              ▼               ▼          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      APACHE NIFI                             │   │
│  │                     :8443 (Web UI)                           │   │
│  │                                                              │   │
│  │  ListFile → FetchFile → SplitRecord → EvaluateJsonPath      │   │
│  │                                           (Traffic Fields)   │   │
│  │                                                              │   │
│  │  QueryDatabaseTable ───────────────→ EvaluateJsonPath        │   │
│  │  (Incremental)                        (DB Fields)            │   │
│  │                                           │                  │   │
│  │                              Funnel (Merge)                  │   │
│  │                                    │                         │   │
│  │                           QueryRecord (Dedup)                │   │
│  │                                    │                         │   │
│  │                           UpdateRecord (Clean)               │   │
│  │                                    │                         │   │
│  │                           PutFile → ExecuteStreamCommand     │   │
│  │                                         │                    │   │
│  └─────────────────────────────────────────┼────────────────────┘   │
│                                             │                       │
│                                    ┌────────▼───────┐               │
│                                    │   HDFS Storage  │               │
│                                    │  /traffic-data  │               │
│                                    └────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

### Docker Components

| Container | Image | Ports | Purpose |
|-----------|-------|-------|---------|
| nifi | apache/nifi:latest | 8443 | Data flow engine |
| postgres | postgres:13 | 5432 | Operational database |
| python-simulator | python-simulator:custom | - | Data generators |
| hadoop | itversity/itvdelab:latest | 9870, 9000 | Distributed file system |

### Shared Volumes

| Volume | Used By | Purpose |
|--------|---------|---------|
| `./data/incoming` | python-simulator (write), nifi (read) | Incoming JSON files |
| `./data/scripts` | python-simulator | Python simulation scripts |
| `./hdfs-staging` | nifi (write), hadoop (read) | Staging area for HDFS |
| `./nifi-extensions` | nifi | JDBC drivers & Hadoop config |

---

## 5. NiFi Pipeline Design

### Flow Overview

```
[Sources] → [Ingestion] → [Split] → [Extract] → [Merge] → [Clean] → [Store]
```

### Stage 1: File Ingestion

| # | Processor | Type | Function | Key Settings |
|---|-----------|------|----------|--------------|
| 1 | **Sensors-Incoming-Data** | ListFile | Watch `/data/incoming` directory | File Filter: `[^\.].*\.json`<br/>Min File Age: 5 sec<br/>Max Dir Listing Time: 10 sec |
| 2 | **Fetch-Sensor-Files** | FetchFile | Read file contents | Completion Strategy: Move File<br/>Move Destination: `/data/processed` |

**Why ListFile + FetchFile Instead of GetFile?**
- **Separation of Concerns:** Watching is decoupled from fetching
- **Better Error Handling:** Fetch failure doesn't affect watching
- **Flexibility:** Processors can be inserted between them (filtering, prioritization)
- **Performance:** ListFile is lightweight; FetchFile operates only when needed

**Critical Settings:**
- `Minimum File Age: 5 sec` — Prevents reading incomplete files
- `Completion Strategy: Move File` — Prevents duplicate reads

---

### Stage 2: Split & Extract

| # | Processor | Type | Function |
|---|-----------|------|----------|
| 3 | **Split-JSON-Records** | SplitRecord | Split each NDJSON file into individual records |
| 4 | **Extract-JSON-Fields** | EvaluateJsonPath | Extract 13 traffic fields as FlowFile Attributes |

**Records Per Split: 1** — Each JSON record becomes an independent FlowFile.

---

### Stage 3: Database Extraction

| # | Processor | Type | Function |
|---|-----------|------|----------|
| 5 | **Fetch-Intersections-From-DB** | QueryDatabaseTable | Incremental extraction from PostgreSQL |
| 6 | **Extract-DB-Fields** | EvaluateJsonPath | Extract 12 intersection fields as FlowFile Attributes |

**Incremental Extraction:**
- `Maximum-value Columns: updated_at` — Pulls only records updated since last extraction
- `Run Schedule: 10 sec` — Checks for changes every 10 seconds

---

### Stage 4: Merge & Clean

| # | Processor | Type | Function | Configuration |
|---|-----------|------|----------|---------------|
| 7 | **Traffic-Data-Merge** | Funnel | Merge both data paths (traffic + intersections) | - |
| 8 | **Remove-Duplicates** | QueryRecord | Remove duplicate records | `SELECT DISTINCT * FROM FLOWFILE` |
| 9 | **Clean-Traffic-Data** | UpdateRecord | Clean invalid and missing values | 7 cleaning rules |

---

### Stage 5: Storage

| # | Processor | Type | Function |
|---|-----------|------|----------|
| 10 | **Store-to-HDFS-Staging** | PutFile | Save files to `/hdfs-staging` |
| 11 | **Move-to-HDFS** | ExecuteStreamCommand | Auto-transfer to HDFS via WebHDFS |

---

## 6. Data Cleaning Strategy

### Rationale for Merging Before Cleaning

| Comparison | Clean Each Source Separately | Merge Then Clean (Chosen) |
|------------|------------------------------|---------------------------|
| Number of Cleaning Rules | Duplicated (×2) | Single set |
| Contradiction Detection | Difficult | Easy |
| Maintainability | Harder | Easier |
| Scalability | New source = new rules | Rules remain unchanged |

### Detailed Cleaning Rules

| # | Field | Condition | Replacement Value | Logic |
|---|-------|-----------|-------------------|-------|
| 1 | `vehicle_count` | null, negative, textual | `0` | Strip non-numeric, replace invalid |
| 2 | `avg_speed_kmh` | Negative | `0.0` | Negative speed = sensor fault |
| 3 | `temperature_c` | > 75 or < -50 | `25.0` | Moderate default temperature |
| 4 | `visibility_m` | ≤ 0 | `1000.0` | Zero visibility is impossible |
| 5 | `congestion_level` | Empty or null | `"unknown"` | Unknown classification |
| 6 | `signal_status` | Empty or null | `"unknown"` | Unknown status |
| 7 | `district` | Empty or null | `"Unassigned"` | Unspecified district |

---

## 7. Best Practices Implementation

### Back Pressure

| Location | Object Threshold | Size Threshold |
|----------|-----------------|----------------|
| Queue between FetchFile and SplitRecord | 10 | 10 MB |

**Behavior:** When FlowFile count in the queue reaches 10, FetchFile automatically pauses until SplitRecord processes some files.

### Yield Duration

| Location | Value | Rationale |
|----------|-------|-----------|
| Fetch-Intersections-From-DB | 10 sec | Give PostgreSQL time to recover if temporarily unavailable |

### Penalty Duration

| Location | Value | Rationale |
|----------|-------|-----------|
| Remove-Duplicates | 10 sec | Delay failed records before retrying |

### Prioritizer

| Location | Type | Rationale |
|----------|------|-----------|
| Queue between ListFile and FetchFile | FirstInFirstOut | Ensure chronological processing order |

### Relationship Management

All unused relationships (`failure`, `unmatched`, `original`, `not.found`, `permission.denied`) are set to **auto-terminate** to prevent validation warnings and clarify design intent.

---

## 8. Challenges and Solutions

| # | Challenge | Symptom | Root Cause Analysis | Solution |
|---|-----------|---------|---------------------|----------|
| 1 | SplitJSON Not Working | Out=0 despite inputs | SplitJSON requires JSON Array; our data is NDJSON | SplitRecord with JsonTreeReader |
| 2 | PutHDFS Missing | Processor not listed | Removed to external NAR extension in NiFi 2.9.0 | Downloaded NAR + PutFile/WebHDFS hybrid |
| 3 | psycopg2 Disappears | ModuleNotFoundError after restart | Container doesn't persist pip installations | Custom Docker image (python-simulator:custom) |
| 4 | JSON Evaluation for Two Sources | Field collision | Sources have completely different fields | Separate EvaluateJsonPath per source |
| 5 | DetectDuplicate Too Complex | Requires DistributedMapCacheServer | Not available in NiFi 2.9.0 | QueryRecord with SELECT DISTINCT |
| 6 | ConvertRecord Not Converting | Data remained as JSON | Possible version compatibility | Accepted JSON as valid final format |
| 7 | FetchFile Too Slow | 10-minute delay before output | Scheduling and timeout settings | Reduced Max Dir Listing Time to 10s |
| 8 | JDBC Files Lost | PostgreSQL-Pool fails after restart | Restart clears temporary container files | Persistent Docker Volume (`nifi-extensions`) |

---

## 9. Operations Guide

### Prerequisites
- Docker and Docker Compose
- WSL2 or Linux
- Minimum 8GB RAM recommended

### Startup

```bash
# 1. Navigate to project directory
cd ~/nifi-project

# 2. Start all services
docker compose up -d --build

# 3. Wait for all services to initialize (approximately 2 minutes)
docker ps
# Should see 4 containers: nifi, postgres, python-simulator, hadoop

# 4. Launch data generators (in two separate terminals)
docker exec -it python-simulator python3 /scripts/generate_transactions.py
docker exec -it python-simulator python3 /scripts/generate_db.py

# 5. Create HDFS directory
docker exec -it hadoop /opt/hadoop-3.3.0/bin/hdfs dfs -mkdir -p /traffic-data

# 6. Start all NiFi processors from the NiFi UI
# Open https://localhost:8443/nifi
# Username: admin / Password: adminadminadmin
# Press Ctrl+A, then click Start

# 7. Transfer files to HDFS
docker exec -it hadoop /opt/hadoop-3.3.0/bin/hdfs dfs -put /hdfs-staging/* /traffic-data/

# 8. Verify results
docker exec -it hadoop /opt/hadoop-3.3.0/bin/hdfs dfs -ls /traffic-data/ | tail -5
docker exec -it postgres psql -U nifi_user -d nifi_db -c "SELECT COUNT(*) FROM intersections;"
```

### Access URLs

| Service | URL | Description |
|---------|-----|-------------|
| NiFi | https://localhost:8443/nifi | Flow management UI |
| HDFS | http://localhost:9870 | File system monitoring |
| Adminer | http://localhost:8080 | Database management |

---

## 10. Performance Monitoring

### NiFi Bulletin Board

Monitor via the alert icon in the upper-right corner of the NiFi UI. Expected errors:

| Error | Meaning | Action |
|-------|---------|--------|
| `not.found` in FetchFile | File was deleted before reading | Normal, ignored |
| `did not have valid JSON` | Dirty data arrived | Normal, proves system works |
| `Connection refused` temporarily | PostgreSQL recovering | Yield Duration handles it |

### HDFS Metrics

```bash
# Number of stored files
docker exec -it hadoop /opt/hadoop-3.3.0/bin/hdfs dfs -count /traffic-data/

# Data size
docker exec -it hadoop /opt/hadoop-3.3.0/bin/hdfs dfs -du -h /traffic-data/
```

### PostgreSQL Metrics

```sql
-- Intersection count
SELECT COUNT(*) FROM intersections;

-- Latest update
SELECT MAX(updated_at) FROM intersections;

-- Intersections by status
SELECT status, COUNT(*) FROM intersections GROUP BY status;
```

---

## 11. Future Expansion Plan

### Proposed Enhancements

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| **Apache Kafka** | Add Kafka as buffer layer between sensors and NiFi for better resilience | High |
| **Parquet Format** | Convert to Parquet for better compression and query performance | Medium |
| **Hive Integration** | Create external Hive tables for SQL querying | Medium |
| **Apache Spark** | Advanced analytics and ML for congestion prediction | Low |
| **Grafana Dashboard** | Real-time traffic monitoring dashboard | Low |
| **Alerting** | Automated alerts on accident detection or severe congestion | Low |

---

## 12. Appendices

### Appendix A: Complete Processor Inventory

| # | Processor Name | Type | Function | Input | Output |
|---|---------------|------|----------|-------|--------|
| 1 | Sensors-Incoming-Data | ListFile | Watch for new files | - | success |
| 2 | Fetch-Sensor-Files | FetchFile | Read file contents | success | success |
| 3 | Split-JSON-Records | SplitRecord | Split files into records | success | splits |
| 4 | Extract-JSON-Fields | EvaluateJsonPath | Extract traffic fields | splits | matched |
| 5 | Fetch-Intersections-From-DB | QueryDatabaseTable | Incremental extraction from PostgreSQL | - | success |
| 6 | Extract-DB-Fields | EvaluateJsonPath | Extract intersection fields | success | matched |
| 7 | Traffic-Data-Merge | Funnel | Merge both sources | matched ×2 | - |
| 8 | Remove-Duplicates | QueryRecord | Remove duplicate records | - | SQL Query |
| 9 | Clean-Traffic-Data | UpdateRecord | Clean invalid values | SQL Query | success |
| 10 | Store-to-HDFS-Staging | PutFile | Temporary save | success | success |
| 11 | Move-to-HDFS | ExecuteStreamCommand | Transfer to HDFS | success | original |

### Appendix B: Sample Data Before and After Cleaning

#### Before Cleaning:
```json
{
  "event_id": "DUPLICATE_EVENT",
  "intersection_id": "INT-0016",
  "vehicle_type": "motorcycle",
  "vehicle_count": "unknown",
  "avg_speed_kmh": -10.0,
  "congestion_level": null,
  "district": "",
  "lane_id": 2,
  "temperature_c": null,
  "visibility_m": -1.0,
  "accident_flag": null,
  "signal_status": null,
  "event_timestamp": "2026-05-07T23:59:37"
}
```

#### After Cleaning:
```json
{
  "event_id": "DUPLICATE_EVENT",
  "intersection_id": "INT-0016",
  "vehicle_type": "motorcycle",
  "vehicle_count": 0,
  "avg_speed_kmh": 0.0,
  "congestion_level": "unknown",
  "district": "Unassigned",
  "lane_id": 2,
  "temperature_c": 25.0,
  "visibility_m": 1000.0,
  "accident_flag": false,
  "signal_status": "unknown",
  "event_timestamp": "2026-05-07T23:59:37"
}
```

### Appendix C: Project Directory Structure

```
nifi-project/
├── docker-compose.yml              # Docker configuration
├── Dockerfile                      # Custom Python image build
├── README.md                       # This documentation
├── data/
│   ├── incoming/                   # Incoming JSON files
│   ├── processed/                  # Files after reading
│   └── scripts/
│       ├── generate_transactions.py  # Traffic sensor simulator
│       └── generate_db.py           # Database simulator
├── hdfs-staging/                   # Staging area for HDFS
└── nifi-extensions/
    ├── postgresql-42.7.3.jar      # JDBC Driver
    └── hadoop-conf/               # Hadoop configuration
        ├── core-site.xml
        └── hdfs-site.xml
```

---
