# Technical Approach — Spark RDD Employee Data Lab

##  Objective

Process a semi-structured CSV file using **low-level RDD operations** to demonstrate foundational Spark concepts before introducing higher-level APIs like DataFrames.

---

##  Architecture

```
employees.txt  →  textFile()  →  filter()  →  map()  →  reduceByKey()  →  Results
                     ↓
              Lazy Evaluation (DAG)
                     ↓
              Spark UI (port 4040)
```

---

##  Why RDD over DataFrame?

| RDD | DataFrame |
|-----|-----------|
| Low-level, full control | High-level, optimized |
| Explicit transformations | Implicit optimizations |
| Better for learning fundamentals | Better for production pipelines |

This lab intentionally uses RDDs to expose the underlying mechanics of distributed data processing.

---

##  Data Quality Strategy

### Defensive Parsing Layers

```
Layer 1: File structure   →  Remove header + empty lines
Layer 2: Field count      →  Reject records with ≠ 9 fields
Layer 3: Type validation  →  Ensure numeric fields are actually numeric
```

### Malformed Record Example

```
Raw:  "7,Robert Martinez,Legal,Legal Counsel145000,San Francisco,..."

Issue: Missing comma between "Legal Counsel" and "145000"
       → Salary field becomes "San Francisco"
       → Type validation fails at Layer 3
```

---

##  Key RDD Operations Used

| Operation | Purpose | Frequency |
|-----------|---------|-----------|
| `textFile()` | Read raw data | Once per task |
| `filter()` | Remove unwanted rows | Every task |
| `map()` | Transform elements | Every task |
| `flatMap()` | Flatten nested results | Tasks 4 & 5 |
| `reduceByKey()` | Aggregate by key | Tasks 2, 4, 5 |
| `join()` | Combine RDDs | Task 4 |
| `sortByKey()` | Order results | Tasks 2, 4, 5 |
| `countByValue()` | Frequency count | Task 5 |
| `collect()` | Materialize results | Every task |

---

##  Lazy Evaluation Benefits

All transformations are **lazy** — Spark builds a DAG and optimizes before execution:

```python
# Nothing executes yet
rdd = sc.textFile("...")
rdd = rdd.filter(...)
rdd = rdd.map(...)

# Execution triggers here
result = rdd.collect()
```

This allows Spark to:
- Combine multiple filters into one pass
- Optimize partition usage
- Minimize data shuffling

---

##  Environment Reproducibility

Docker ensures identical behavior across all machines:

- **Image:** `jupyter/pyspark-notebook:x86_64-spark-3.5.0`
- **Python:** 3.11 with PySpark pre-installed
- **Spark UI:** Available at `http://localhost:4040`

---

##  Results Summary

### Task 4: Average Salary per Department

| Department | Employees | Total Salary | Avg Salary |
|------------|:---------:|:-------------|:-----------:|
| Engineering | 3 | $365,000 | $121,667 |
| IT | 1 | $115,000 | $115,000 |
| Finance | 1 | $105,000 | $105,000 |
| Sales | 2 | $195,000 | $97,500 |
| Marketing | 1 | $92,000 | $92,000 |
| HR | 1 | $88,000 | $88,000 |

### Task 5: Employee Count per Department

| Department | Count | % of Total |
|------------|:-----:|:----------:|
| Engineering | 3 | 33% |
| Sales | 2 | 22% |
| Finance | 1 | 11% |
| IT | 1 | 11% |
| Marketing | 1 | 11% |
| HR | 1 | 11% |

### Data Quality Summary

| Category | Count |
|----------|:-----:|
| Total lines in file | 13 |
| Header row | 1 |
| Empty lines | 2 |
| Valid records | 9 |
| Malformed records | 1 |

---

##  Extensions (Beyond the Lab)

Potential improvements for production scenarios:

- Replace RDD with **DataFrame API** for automatic optimization
- Add **unit tests** for parsing functions
- Implement **logging** instead of print statements
- Use **Spark Streaming** for real-time data ingestion
- Store results in **Parquet** format for downstream queries

---

##  References

- [Apache Spark RDD Programming Guide](https://spark.apache.org/docs/latest/rdd-programming-guide.html)
- [PySpark API Documentation](https://spark.apache.org/docs/latest/api/python/)
- [Jupyter Docker Stacks](https://jupyter-docker-stacks.readthedocs.io/)

---