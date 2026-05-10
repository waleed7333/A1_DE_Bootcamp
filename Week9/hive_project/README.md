
# 🐝 Apache Hive SCD Type 2 Project

## 📋 Project Overview

This project demonstrates the implementation of **Slowly Changing Dimension Type 2 (SCD2)** using **Apache Hive** on a Dockerized Hadoop environment. The project covers the full lifecycle of managing customer data with historical change tracking, without using transactional tables or UPDATE/DELETE operations.

---

## 🏠 Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Docker Container                   │
│  ┌─────────────────────────────────────────────────┐ │
│  │              itversity/itvdelab                  │ │
│  │  ┌─────────┐  ┌─────────┐                       │ │
│  │  │  Hadoop │  │  Hive   │                       │ │
│  │  │  3.3.0  │  │  3.1.2  │                       │ │
│  │  └─────────┘  └─────────┘                       │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
hive_project/
│   docker-compose.yml          # Docker Compose configuration
│   README.md                   # Project documentation (this file)
│
├─── data/                      # Input CSV files
│       customer_scd2_mixed.csv # Initial customer data (218 records)
│       customer_updated.csv    # Updated customer data (4372 records)
│
└─── screenshots/               # Project screenshots
        hive_01.png ~ hive_11.png
```

---

## 🎯 Learning Objectives

| # | Objective | Status |
|---|-----------|--------|
| 1 | Create Internal (Managed) and External tables | ✅ |
| 2 | Load data into both table types | ✅ |
| 3 | Observe the difference when dropping Internal vs External tables | ✅ |
| 4 | Handle delimiter issues inside address column | ✅ |
| 5 | Create customer dimension as SCD Type 2 | ✅ |
| 6 | Insert new records and update changed records without UPDATE/DELETE | ✅ |
| 7 | Work around Hive's limitation on transactional operations | ✅ |

---

## 🚀 Getting Started

### Prerequisites

- **Docker** and **Docker Compose** installed
- **WSL** (Windows Subsystem for Linux) or native Linux environment
- At least **8 GB** of free RAM

### Step 1: Clone and Prepare

```bash
mkdir -p ~/hive_project/data
mkdir -p ~/hive_project/screenshots
cd ~/hive_project
```

Place the data files (`customer_scd2_mixed.csv`, `customer_updated.csv`) inside the `data/` folder.

### Step 2: Create docker-compose.yml

```yaml
version: '3.8'

services:
  hive:
    image: itversity/itvdelab:latest
    container_name: hive_project
    ports:
      - "10000:10000"
      - "9083:9083"
      - "50070:50070"
      - "8088:8088"
      - "8888:8888"
    volumes:
      - ./data:/data
    stdin_open: true
    tty: true
    command: /bin/bash
```

### Step 3: Start the Container

```bash
docker compose up -d
docker exec -it hive_project bash
```

### Step 4: Initialize Services

```bash
/deploy.sh
```

Open a **new terminal**, then:

```bash
docker exec -it hive_project bash
hive
```

---

## 📊 Implementation Steps

### 1. Create Database

```sql
CREATE DATABASE IF NOT EXISTS customer_scd;
USE customer_scd;
```

### 2. Create Tables

```sql
-- Internal (Managed) Table
CREATE TABLE customers_internal (
  CustomerID INT, Name STRING, Email STRING,
  Phone_Number STRING, Address STRING, JOIN_Date STRING,
  Start_Date STRING, End_Date STRING, Is_Current INT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
TBLPROPERTIES ("skip.header.line.count"="1");

-- External Table
CREATE EXTERNAL TABLE customers_external (
  CustomerID INT, Name STRING, Email STRING,
  Phone_Number STRING, Address STRING, JOIN_Date STRING,
  Start_Date STRING, End_Date STRING, Is_Current INT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/user/hive/warehouse/customer_scd.db/customers_external'
TBLPROPERTIES ("skip.header.line.count"="1");
```

### 3. Load Data

```sql
-- Internal
LOAD DATA LOCAL INPATH '/data/customer_scd2_mixed.csv' INTO TABLE customers_internal;

-- External
!hdfs dfs -put /data/customer_scd2_mixed.csv /user/hive/warehouse/customer_scd.db/customers_external/;
```

### 4. Drop Tables & Observe

```sql
DROP TABLE customers_internal;
SELECT * FROM customers_internal LIMIT 1;  -- Error: Table not found

DROP TABLE customers_external;
!hdfs dfs -ls /user/hive/warehouse/customer_scd.db/customers_external;
-- File still exists! ✅
```

### 5. Create SCD2 Final Table

```sql
CREATE EXTERNAL TABLE customer_scd2_final (
  CustomerID INT, Name STRING, Email STRING,
  Phone_Number STRING, Address STRING, JOIN_Date STRING,
  Start_Date STRING, End_Date STRING, Is_Current INT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/user/hive/warehouse/customer_scd.db/customer_scd2_final'
TBLPROPERTIES ("skip.header.line.count"="1");
```

### 6. Load Updates

```sql
CREATE TEMPORARY TABLE updates_stage (
  CustomerID INT, Name STRING, Email STRING,
  Phone_Number STRING, Address STRING, JOIN_Date STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
TBLPROPERTIES ("skip.header.line.count"="1");

LOAD DATA LOCAL INPATH '/data/customer_updated.csv' INTO TABLE updates_stage;
```

### 7. Apply SCD Type 2

```sql
INSERT OVERWRITE TABLE customer_scd2_final
SELECT ... FROM (
  -- Close old records that have updates
  SELECT ...
  FROM customer_scd2_final existing
  LEFT JOIN updates_stage updates ON existing.CustomerID = updates.CustomerID

  UNION ALL

  -- Insert new records from updates
  SELECT ...
  FROM updates_stage updates
) combined;
```

### 8. Fix NULL Values

```sql
INSERT OVERWRITE TABLE customer_scd2_final
SELECT ..., CASE WHEN Is_Current IS NULL THEN 1 ELSE Is_Current END AS Is_Current
FROM customer_scd2_final;
```

---

## 📈 Results

```
Final Table Count:    4586 total
Historical Records:   130 (Is_Current = 0)
Current Records:      4456 (Is_Current = 1)
```

---

## 🔑 Key Takeaways

1. **Internal tables** store data in Hive's warehouse directory; dropping the table **deletes the data**.
2. **External tables** reference data in a user-defined HDFS location; dropping the table **preserves the data**.
3. **SCD Type 2** tracks history by adding new rows for each change, using `Start_Date`, `End_Date`, and `Is_Current` flags.
4. **Hive does not support UPDATE/DELETE** on non-transactional tables, so `INSERT OVERWRITE` with `LEFT JOIN` is used to simulate SCD2.
5. The address column contained commas inside quoted strings, which Hive handles correctly with the default CSV SerDe.

---

## 🛠 Technologies Used

| Technology | Version | Purpose |
|------------|---------|---------|
| Docker | Latest | Containerization |
| Apache Hadoop | 3.3.0 | Distributed Storage (HDFS) |
| Apache Hive | 3.1.2 | Data Warehousing & SQL Interface |
| Derby | Embedded | Hive Metastore Database |

---

## 📝 Author

- **Name**: Waleed Alabbasi
- **Project Date**: May 2026
- **Course**: Big Data Engineering with Apache Hive

---

## 📜 License

This project is created for educational purposes as part of a Big Data coursework assignment.
