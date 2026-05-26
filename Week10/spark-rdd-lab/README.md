# Spark RDD Lab — Employee Data Processing

A hands-on lab for processing and analyzing employee data using **Apache Spark RDDs** with **PySpark**.

---

##  Overview

This project demonstrates core RDD operations through five practical tasks:

| # | Task | Key Operations |
|---|------|----------------|
| 1 | Parse text data into structured format | `textFile`, `filter`, `map` |
| 2 | Count occurrences of each name | `map`, `reduceByKey` |
| 3 | Filter invalid records safely | `filter`, custom validation |
| 4 | Average salary per department | `reduceByKey`, `join` |
| 5 | Employee count per department | `map`, `reduceByKey`, `countByValue` |

---

##  Tech Stack

| Technology | Version |
|------------|---------|
| PySpark | 3.5.0 |
| Python | 3.11 |
| Docker & Docker Compose | Latest |
| JupyterLab | 4.x |

---

##  Quick Start

```bash
# Clone and enter project
cd spark-rdd-lab

# Start the environment
docker-compose up -d

# Open JupyterLab
# http://localhost:8888
```

No authentication token required (local development mode).

---

##  Project Structure

```
spark-rdd-lab/
├── docker-compose.yml
├── README.md
├── data/
│   └── raw/
│       └── employees.txt          # Raw input data
├── notebooks/
│   ├── 01_data_exploration.ipynb  # Task 1
│   ├── 02_name_count.ipynb        # Task 2
│   ├── 03_data_cleaning.ipynb     # Task 3
│   ├── 04_avg_salary.ipynb        # Task 4
│   └── 05_emp_by_dept.ipynb       # Task 5
└── docs/
    └── approach.md                # Technical documentation
```

---

##  Dataset

**employees.txt** — 10 employee records with intentional data quality issues:

- Header row
- Empty lines
- Malformed record (missing comma)

These imperfections simulate real-world data challenges.

---

##  Key Learnings

- RDD transformations (`map`, `filter`, `flatMap`)
- Key-value pair operations (`reduceByKey`, `join`, `sortByKey`)
- Lazy evaluation and Spark job execution
- Defensive data parsing with multi-layer validation
- Environment reproducibility with Docker

---

##  Documentation

See [docs/approach.md](docs/approach.md) for detailed methodology and architectural decisions.

---

##  Author

[Waleed Alabbasi]



---
