# Smart Grid Real-Time Pipeline — Runtime Infrastructure & Deployment Manual

This directory contains the complete runtime infrastructure required to deploy, execute, 
monitor, and operate the Smart Grid Real-Time Streaming Pipeline.

The environment simulates a production-oriented streaming data engineering platform using 
distributed event streaming, real-time orchestration, fault-tolerant messaging, and scalable 
storage systems.

---

## Runtime Infrastructure Overview

The runtime platform integrates multiple distributed services operating together inside a 
containerized environment.

| Service              | Responsibility                                              |
| -------------------- | ----------------------------------------------------------- |
| Apache NiFi          | Streaming ingestion, orchestration, transformation, routing |
| Apache Kafka Cluster | Distributed event streaming backbone (3 Brokers)            |
| Apache ZooKeeper     | Kafka cluster coordination                                  |
| Hadoop HDFS          | Distributed persistent storage (NameNode + DataNode)        |
| Kafka UI             | Kafka monitoring and inspection                             |
| Python Generator     | Real-time smart grid telemetry simulation                   |
| Docker Compose       | Multi-container orchestration                               |

---

## Container Architecture Layout

```text
Docker Host
│
├── Apache NiFi Container
│       ├── File Ingestion
│       ├── Chunking
│       ├── Validation
│       ├── JSON Transformation
│       ├── Kafka Publishing
│       └── HDFS Persistence
│
├── Kafka Cluster
│       ├── kafka1 (Broker ID: 1)
│       ├── kafka2 (Broker ID: 2)
│       └── kafka3 (Broker ID: 3)
│
├── ZooKeeper Container
│
├── Hadoop NameNode Container
│
├── Hadoop DataNode Container
│
├── Kafka UI Container
│
└── Python Generator Runtime
```

---

## Full Runtime Project Structure

```text
Smart-Grid-Real-Time-Pipeline-Project/
│
├── docker-compose.yml
├── hadoop.env
├── requirements.txt
├── .gitignore
├── README.md                           # (this file)
│
├── data_ingestion/
│   ├── output/
│   ├── config.yaml
│   └── smart_grid_generator.py
│
├── kafka/
│   └── create_topics.sh
│
├── hadoop/
│   └── config/
│       ├── core-site.xml
│       └── hdfs-site.xml
│
├── nifi/
│   ├── conf/
│   ├── drivers/
│   ├── extensions/
│   ├── database_repo/
│   ├── flowfile_repo/
│   ├── content_repo/
│   └── provenance_repo/
│
└── nifi_data/
    ├── incoming/
    ├── archive/
    └── failed/
        ├── corrupted/
        ├── hdfs/
        ├── invalid_schema/
        └── kafka/
```

---

## Runtime Directory Responsibilities

| Directory          | Responsibility                    |
| ------------------ | --------------------------------- |
| data_ingestion/    | Smart grid telemetry generation   |
| kafka/             | Kafka topic initialization        |
| hadoop/config/     | Shared Hadoop configuration       |
| nifi/conf/         | NiFi runtime configuration        |
| nifi/drivers/      | External JDBC and runtime drivers |
| nifi/extensions/   | Additional NiFi extensions        |
| nifi_data/         | Runtime operational storage       |
| nifi_data/archive/ | Successfully processed files      |
| nifi_data/failed/  | Failure isolation storage         |

---

## Infrastructure Requirements

Before deploying the environment, ensure the host machine satisfies the following requirements.

| Resource       | Recommended       |
| -------------- | ----------------- |
| RAM            | 8 GB or higher    |
| CPU            | 4 Cores or higher |
| Storage        | SSD Recommended   |
| Docker         | Latest Stable     |
| Docker Compose | Latest Stable     |
| Python         | Python 3.10+      |

---

## Container Networking

All runtime services communicate through a dedicated Docker bridge network:

```text
data_network
```

This isolated network enables:

- Internal broker communication
- Service discovery
- Container-to-container connectivity
- Secure runtime isolation

---

## Runtime Ports

| Service                   | Internal Port | External Port | Access Type   |
| ------------------------- | ------------- | ------------- | ------------- |
| Apache NiFi HTTPS UI      | 8443          | 8443          | External      |
| Kafka Broker 1 (EXTERNAL) | 9092          | 9092          | External      |
| Kafka Broker 2 (EXTERNAL) | 9093          | 9093          | External      |
| Kafka Broker 3 (EXTERNAL) | 9094          | 9094          | External      |
| Kafka Broker 1 (HOST)     | 29092         | 29092         | Localhost     |
| Kafka Broker 2 (HOST)     | 29093         | 29093         | Localhost     |
| Kafka Broker 3 (HOST)     | 29094         | 29094         | Localhost     |
| Kafka Broker 1 (INTERNAL) | 19092         | Internal Only | Inter-Broker  |
| Kafka Broker 2 (INTERNAL) | 19093         | Internal Only | Inter-Broker  |
| Kafka Broker 3 (INTERNAL) | 19094         | Internal Only | Inter-Broker  |
| ZooKeeper                 | 2181          | 2181          | External      |
| Hadoop NameNode UI        | 9870          | 9870          | External      |
| Hadoop NameNode RPC       | 9000          | 9000          | External      |
| Kafka UI                  | 8080          | 8080          | External      |

---

## Service Access URLs

| Service            | URL                           |
| ------------------ | ----------------------------- |
| Apache NiFi        | https://localhost:8443/nifi   |
| Hadoop NameNode UI | http://localhost:9870         |
| Kafka UI           | http://localhost:8080         |
| Kafka Broker 1     | localhost:9092                |
| Kafka Broker 2     | localhost:9093                |
| Kafka Broker 3     | localhost:9094                |

---

## Kafka Cluster Architecture

The runtime environment deploys a multi-broker Kafka cluster with 3 brokers.

```text
Kafka Cluster
│
├── kafka1 (Broker ID: 1)
├── kafka2 (Broker ID: 2)
└── kafka3 (Broker ID: 3)
```

The cluster was designed to simulate enterprise-style streaming infrastructure with:

- Distributed partitions across multiple brokers
- Topic replication for data durability
- Broker fault tolerance
- High availability concepts
- Multi-listener communication (INTERNAL, EXTERNAL, HOST)

---

## Kafka Listener Design

The Kafka cluster uses multiple listener types for different communication paths.

| Listener | Purpose                                                | Example                     |
| -------- | ------------------------------------------------------ | --------------------------- |
| INTERNAL | Inter-broker communication and internal Docker traffic | `INTERNAL://kafka1:19092`   |
| EXTERNAL | Docker network access for containers                   | `EXTERNAL://kafka1:9092`    |
| HOST     | Localhost access from the host machine                 | `HOST://localhost:29092`    |

This architecture separates internal cluster traffic from external client access, 
following Kafka best practices for multi-listener configurations.

---

## Kafka Replication Strategy

The Kafka cluster uses replication settings designed to emulate fault-tolerant streaming systems.

| Configuration                    | Value | Purpose                              |
| -------------------------------- | ----- | ------------------------------------ |
| replication.factor               | 3     | Data replicated on all 3 brokers     |
| min.insync.replicas              | 2     | At least 2 replicas before ACK       |
| offsets.topic.replication.factor | 3     | Consumer offset durability           |

These settings improve:

- Data durability
- Broker fault tolerance
- Message availability
- Cluster resilience

---

## Persistent Runtime Storage

The runtime environment uses persistent Docker volume mappings to preserve operational state 
across container restarts.

---

### NiFi Persistent Repositories

| Repository            | Purpose                       |
| --------------------- | ----------------------------- |
| database_repository   | NiFi internal metadata        |
| flowfile_repository   | FlowFile state tracking       |
| content_repository    | Actual FlowFile content       |
| provenance_repository | Data lineage tracking         |

These repositories remain persistent even if containers are recreated.

---

### Docker Volume Mapping Strategy

Example volume mappings from `docker-compose.yml`:

```yaml
volumes:
  - ./nifi/conf:/opt/nifi/nifi-current/conf
  - ./nifi/drivers:/opt/nifi/nifi-current/drivers
  - ./nifi/extensions:/opt/nifi/nifi-current/nar_extensions
  - ./nifi/database_repo:/opt/nifi/nifi-current/database_repository
  - ./nifi/flowfile_repo:/opt/nifi/nifi-current/flowfile_repository
  - ./nifi/content_repo:/opt/nifi/nifi-current/content_repository
  - ./nifi/provenance_repo:/opt/nifi/nifi-current/provenance_repository
```

---

### Why Persistent Volumes Matter

Persistent storage enables:

- Durable FlowFile tracking
- Provenance retention across restarts
- Easier debugging with historical context
- Runtime reproducibility
- Stable local development
- Safer container recreation

Without persistence:

- Runtime state may be lost
- Provenance history disappears
- Failed FlowFiles become unrecoverable
- Operational troubleshooting becomes difficult

---

## Hadoop Shared Configuration

The runtime environment mounts Hadoop configuration files into dependent containers using 
read-only mappings.

Example from `docker-compose.yml`:

```yaml
- ./hadoop/config:/opt/hadoop/config:ro
```

This strategy provides:

- Centralized configuration management
- Shared Hadoop access across containers
- Runtime consistency
- Protection against accidental modification

---

## Infrastructure Deployment

The entire runtime platform is deployed using Docker Compose.

---

### Starting the Environment

From the root runtime directory:

```bash
cd "Smart Grid Real-Time Pipeline project"
docker compose up -d
```

This command initializes:

- Apache NiFi
- Kafka Cluster (3 Brokers)
- ZooKeeper
- Hadoop NameNode
- Hadoop DataNode
- Kafka UI

---

### Verifying Running Containers

Verify container health using:

```bash
docker ps
```

Expected containers:

```text
nifi
kafka1
kafka2
kafka3
zookeeper
hdfs_namenode
hdfs_datanode
kafka-ui
```

---

## Kafka Topic Initialization

Kafka topics are initialized using the automation script located inside:

```text
kafka/create_topics.sh
```

Run the script:

```bash
docker exec -i kafka1 bash < kafka/create_topics.sh
```

---

## Streaming Topics

| Topic           | Partitions | Replication Factor | Purpose                          |
| --------------- | :--------: | :----------------: | -------------------------------- |
| smartgrid-clean |     3      |         3          | Valid streaming telemetry events |
| smartgrid-dlq   |     1      |         3          | Failed event isolation           |

---

## Python Smart Grid Generator

The Python generator continuously simulates electrical grid telemetry from 10 transformers 
across 5 cities.

Generated telemetry includes:

- Voltage readings (220-240V)
- Current measurements (100-500A)
- Transformer temperature (30-65°C)
- Frequency stability (59.8-60.2Hz)
- Power consumption metrics
- Grid event states (NORMAL, OUTAGE, OVERLOAD, FREQ_DRIFT, OVERHEAT)

---

### Generator Setup

Navigate to the generator directory:

```bash
cd data_ingestion
```

Install Python dependencies:

```bash
pip install -r ../requirements.txt
```

Run the generator:

```bash
python smart_grid_generator.py
```

Generated CSV files are automatically written into:

```text
data_ingestion/output/
```

These files are shared with Apache NiFi through mounted runtime volumes 
(`./data_ingestion/output:/data/incoming`).

---

## Apache NiFi Flow Import

The exported NiFi flow is located inside:

```text
../nifi-flow/smart_grid_pipeline.json
```

---

### Importing the Flow

Inside Apache NiFi (https://localhost:8443/nifi):

1. Right-click on the canvas
2. Select **Upload Process Group**
3. Browse and select `smart_grid_pipeline.json`
4. Click **Upload**

---

## Runtime Data Lifecycle

The streaming pipeline processes telemetry data through multiple execution layers.

```text
Python Generator
        ↓
File Ingestion Layer (ListFile → FetchFile)
        ↓
Chunking Layer (SplitText → 64 KB fragments)
        ↓
Validation Layer (ConvertRecord → ValidateRecord → QueryRecord)
        ↓
JSON Transformation Layer (ConvertRecord → SplitJson → JoltTransformJSON)
        ↓
Kafka Streaming Layer (PublishKafka)
        ↓
Kafka Consumer Layer (ConsumeKafka → EvaluateJsonPath → RouteOnAttribute)
        ↓
HDFS Persistence Layer (MergeRecord → UpdateAttribute → PutHDFS)
```

---

## Runtime Operational Storage

| Directory          | Purpose                      |
| ------------------ | ---------------------------- |
| nifi_data/incoming | Incoming datasets (mounted)  |
| nifi_data/archive  | Successfully processed files |
| nifi_data/failed   | Failed FlowFiles             |

---

## Failure Isolation Structure

```text
nifi_data/failed/
│
├── corrupted/          # Corrupted or unreadable files
├── hdfs/               # HDFS persistence failures
├── invalid_schema/     # Schema validation failures
└── kafka/              # Kafka publishing failures
```

---

## Failure Categories

| Failure Directory | Description                   | Recovery Strategy           |
| ----------------- | ----------------------------- | --------------------------- |
| corrupted/        | Corrupted or unreadable files | Manual inspection           |
| invalid_schema/   | Validation failures           | Schema review               |
| kafka/            | Kafka publishing failures     | Retry or manual publish     |
| hdfs/             | HDFS persistence failures     | Retry after HDFS recovery   |

This separation simplifies:

- Runtime debugging
- Operational recovery
- Failure tracing
- Data quality analysis

---

## HDFS Storage Layout

Processed batches are persisted using time-based partitioning.

Example structure:

```text
/smartgrid/year=2026/month=05/day=20/hour=02
```

---

## Partitioning Benefits

Time-based partitioning improves:

- Historical analytics performance
- Query efficiency (Partition Pruning)
- Scalable data organization
- Time-series retrieval
- Integration with Hive/Spark partitioned tables

---

## Recommended Startup Sequence

For stable runtime execution, follow the startup order below.

| Step | Action                                 |
| :--: | -------------------------------------- |
|  1   | Start Docker containers                |
|  2   | Verify Kafka cluster health            |
|  3   | Create Kafka topics                    |
|  4   | Import NiFi flow                       |
|  5   | Enable all NiFi Controller Services    |
|  6   | Start all NiFi Process Groups          |
|  7   | Run Python generator                   |

---

## Operational Validation Checklist

Before running the generator, verify:

- [ ] All containers are healthy (`docker ps`)
- [ ] Kafka brokers are reachable
- [ ] Kafka topics exist (`smartgrid-clean`, `smartgrid-dlq`)
- [ ] NiFi Controller Services are enabled
- [ ] HDFS NameNode UI is accessible
- [ ] No major NiFi queues are blocked

---

## Runtime Monitoring Recommendations

During execution, continuously monitor:

| Area                 | Purpose                      | Tool                |
| -------------------- | ---------------------------- | ------------------- |
| NiFi Queues          | Detect congestion            | NiFi Summary Page   |
| Provenance Events    | Trace FlowFile lifecycle     | NiFi Provenance     |
| Bulletin Board       | Detect runtime errors        | NiFi Bulletin Board |
| Kafka Topics         | Verify streaming activity    | Kafka UI            |
| Processor Throughput | Monitor pipeline performance | NiFi Summary Page   |
| HDFS Directories     | Verify persistence           | HDFS NameNode UI    |

---

## Common Operational Issues

| Issue                     | Possible Cause                     | Recommended Action                |
| ------------------------- | ---------------------------------- | --------------------------------- |
| Kafka connection failures | Brokers not fully initialized      | Wait 10-15 seconds after startup  |
| NiFi queue growth         | Downstream bottlenecks             | Check processor status            |
| Empty HDFS partitions     | Missing partition attributes       | Verify UpdateAttribute after Merge|
| Failed FlowFiles          | Invalid schemas or corrupted files | Check nifi_data/failed/           |
| No generated files        | Generator not running              | Check Python process              |

---

## Shutdown Procedure

To stop all services:

```bash
docker compose down
```

To stop and remove all volumes (clean state):

```bash
docker compose down -v
```

---

## Runtime Scope

This runtime directory focuses on:

- Infrastructure deployment
- Container orchestration
- Runtime execution
- Streaming operations
- Persistent storage
- Failure isolation
- Operational monitoring

Detailed architectural explanations, engineering decisions, streaming concepts, and 
processor-level implementation details are documented separately inside the main repository 
documentation directory.
