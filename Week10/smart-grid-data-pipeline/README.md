# Smart Grid Real-Time Data Pipeline

**Enterprise-grade real-time streaming data engineering platform** designed to simulate 
modern smart grid telemetry processing using Apache NiFi, Apache Kafka, and Hadoop HDFS.

The project demonstrates how scalable streaming systems are architected to ingest, validate, 
transform, distribute, and persist continuous telemetry events in near real-time.

---

## Project Overview

The Smart Grid Real-Time Data Pipeline simulates a production-style electrical grid monitoring 
environment where transformer telemetry data is continuously generated and processed through a 
distributed streaming architecture.

The platform demonstrates modern data engineering concepts including:

- Real-time streaming ingestion
- Event-driven architectures
- Distributed messaging systems
- Streaming data transformation
- Fault-tolerant processing
- Distributed storage systems
- Layered pipeline design
- Operational observability

The pipeline continuously processes smart grid telemetry measurements such as:

- Voltage readings
- Current measurements
- Transformer temperature
- Frequency stability
- Power consumption metrics
- Grid operational status events

---

## System Architecture

![Architecture Diagram](architecture-diagram/Architecture-Overview.png)

---

## High-Level Streaming Flow

```text
Python Smart Grid Generator
            ↓
Apache NiFi — Ingestion & Chunking
            ↓
Apache NiFi — Validation & Transformation
            ↓
Apache Kafka — Streaming Distribution (3 Brokers)
            ↓
Apache NiFi — Stream Consumption
            ↓
Hadoop HDFS — Distributed Persistence
```

---

## Key Enterprise Features

| Feature                          | Description                                |
| -------------------------------- | ------------------------------------------ |
| Layered Streaming Architecture   | 7 independent processing layers            |
| Kafka-Based Decoupling           | Independent producer and consumer scaling  |
| Multi-Broker Kafka Cluster       | 3 Brokers with replication factor 3        |
| DLQ Failure Isolation            | Prevents silent event loss                 |
| Record-Based Validation          | Structured schema enforcement              |
| Canonical JSON Events            | Stable downstream event contracts          |
| Time-Based HDFS Partitioning     | Optimized distributed storage organization |
| MergeRecord Optimization         | HDFS small-file mitigation                 |
| Provenance Tracking              | End-to-end FlowFile lineage visibility     |
| Back Pressure Management         | Runtime overload protection                |
| Distributed Storage Architecture | Scalable long-term persistence             |
| Failure Categorization           | 4 isolated failure directories            |

---

## Technologies Used

| Technology       | Purpose                                  |
| ---------------- | ---------------------------------------- |
| Python           | Smart grid telemetry simulation          |
| Apache NiFi      | Real-time dataflow orchestration         |
| Apache Kafka     | Distributed event streaming (3 Brokers)  |
| Apache ZooKeeper | Kafka cluster coordination               |
| Hadoop HDFS      | Distributed persistent storage           |
| Docker Compose   | Multi-container orchestration            |
| JSON             | Canonical streaming event structure      |

---

## Pipeline Layers

| # | Layer                        | Responsibility                              |
|:-:| ---------------------------- | ------------------------------------------- |
| 1 | Streaming Ingestion Layer    | Detect and ingest incoming datasets         |
| 2 | File Chunking Layer          | Split large files into 64 KB fragments      |
| 3 | Data Validation Layer        | Enforce schema and data quality             |
| 4 | Data Transformation Layer    | Build canonical JSON events                 |
| 5 | Streaming Distribution Layer | Publish events into Kafka topics            |
| 6 | Stream Consumption Layer     | Consume and prepare events for storage      |
| 7 | HDFS Persistence Layer       | Persist optimized batches into HDFS         |

---

## Project Structure

```text
smart-grid-data-pipeline/
│
├── README.md                           # Main project documentation (this file)
│
├── documentation/                       # Technical documentation
│   └── technical_documentation.md
│
├── architecture-diagram/                # Architecture diagrams
│   └── smart-grid-architecture.png
│
├── screenshots/                         # Pipeline screenshots
│
├── sample-data/                         # Sample data from each stage
│   ├── 1_generated-csv-files/
│   ├── 2_chunked-files/
│   ├── 3_cleaned-files/
│   ├── 4_transformed-json-events/
│   └── 5_hdfs-storage-samples/
│
├── nifi-flow/                           # Exported NiFi flow
│   └── smart_grid_pipeline.json
│
├── kafka-config/                        # Kafka topic configuration
│   └── create_topics.sh
│
├── python-generator/                    # Data generator source code
│   ├── requirements.txt
│   ├── config.yaml
│   └── smart_grid_generator.py
│
└── Smart-Grid-Real-Time-Pipeline-Project/      # Runtime deployment files

```

---

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Python 3.10+
- 8 GB RAM minimum

### 1. Navigate to Runtime Directory

```bash
cd Smart-Grid-Real-Time-Pipeline-Project
```

### 2. Start Infrastructure

```bash
docker compose up -d
```

### 3. Initialize Kafka Topics

```bash
docker exec -i kafka1 bash < kafka/create_topics.sh
```

### 4. Import NiFi Flow

1. Open https://localhost:8443/nifi
2. Right-click → Upload Process Group
3. Select `../nifi-flow/smart_grid_pipeline.json`

### 5. Run Smart Grid Generator

```bash
cd ../python-generator
pip install -r requirements.txt
python smart_grid_generator.py
```
---

# Screenshots

The repository includes screenshots demonstrating:

* Apache NiFi pipeline layers
* Kafka streaming operations
* HDFS distributed storage
* Queue monitoring
* Provenance tracking
* Pipeline execution lifecycle

Available inside:

```text
screenshots/
```
---

## Documentation

Comprehensive technical documentation is available in the `documentation/` directory:
`documentation.md`

Documentation covers:

- System architecture and design principles
- Streaming pipeline design
- Kafka cluster architecture
- HDFS persistence strategy
- Runtime operations and monitoring
- Failure handling and DLQ strategy
- Performance optimization
- Engineering challenges and solutions

---

## Sample Data

The repository includes sample datasets representing multiple pipeline stages:

| Stage                     | Description                    |
| ------------------------- | ------------------------------ |
| Generated CSV Files       | Raw telemetry data with errors |
| Chunked Files             | 64 KB processing fragments     |
| Transformed JSON Events   | Canonical event structure      |
| HDFS Storage Samples      | Final persisted batches        |

Available in: `sample-data/`

---

## Project Objectives

The primary goals of this project include:

- Simulating production-style streaming systems
- Demonstrating enterprise data engineering concepts
- Building scalable event-driven pipelines
- Designing modular streaming architectures
- Implementing fault-tolerant processing workflows
- Demonstrating distributed storage integration
- Showcasing operational best practices

---

## Future Enhancements

Potential future improvements include:

- Apache Spark Streaming integration for real-time analytics
- Grafana + Prometheus observability stack
- Schema Registry integration for Avro/Protobuf
- Kubernetes deployment for cloud-native orchestration
- Apache Iceberg / Delta Lake for ACID transactions on data lake
- Machine learning anomaly detection on transformer behavior
- Real-time alerting and notification system
- CI/CD pipeline for automated deployment

---

## Author

Developed as an enterprise-style real-time streaming data engineering project focused on 
smart grid telemetry processing, distributed streaming systems, and scalable data platform 
architecture.

---
