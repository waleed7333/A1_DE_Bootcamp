
# Running the ETL Pipeline

## Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- Olist SQLite database file

## Setup

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

Copy the example file and edit with your PostgreSQL credentials:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password_here
```

### Step 3: Place the Source Database

Download the Olist SQLite database from Kaggle:
https://www.kaggle.com/datasets/terencicp/e-commerce-dataset-by-olist-as-an-sqlite-database

Place it at: `../data/olist.sqlite`

Or update `SQLITE_PATH` in `.env` to point to your file location.

### Step 4: Create the Data Directory

```bash
mkdir -p ../data
```

## Run the Pipeline

From the `code/` directory:

```bash
python main.py
```

Or from the project root:

```bash
python code/main.py
```

## What Happens

The pipeline executes **8 phases** sequentially:

| Phase | Description | Expected Output |
|:-----:|:---|:---|
| 1 | Extract: SQLite → olist_oltp | 11 tables, ~1.5M rows |
| 2 | Bronze: Raw copy → olist_olap.bronze | 11 tables with _loaded_at |
| 3 | Silver: Clean → olist_olap.silver | 9 cleaned tables |
| 4 | Gold: Build 11 dimensions | 165,666 rows |
| 5 | Gold: Build 5 facts | 717,241 rows |
| 6 | Load: Write + indexes | 20 indexes created |
| 7 | Validate: Structural checks | 29 checks |
| 8 | Reconciliation: Source vs Target | 37 checks |

## Expected Final Output

```
============================================================
  VALIDATION REPORT
============================================================
  TOTAL: 29 checks | 29 passed | 0 failed
  STATUS: ✓ ALL CHECKS PASSED
============================================================

============================================================
  RECONCILIATION SUMMARY
============================================================
  Total checks: 37
  Passed:       37
  Failed:       0
  Status:       ✓ SOURCE AND TARGET ARE IDENTICAL
============================================================

██████████████████████████████████████████████████████████████
█                                                            █
█               PIPELINE COMPLETED SUCCESSFULLY              █
█                                                            █
██████████████████████████████████████████████████████████████
```

## Troubleshooting

| Issue | Solution |
|:---|:---|
| `Could not connect to PostgreSQL` | Check DB_HOST, DB_PORT, DB_USER, DB_PASSWORD in `.env` |
| `Database already exists` | Normal on second run - pipeline is idempotent |
| `SQLite file not found` | Verify `SQLITE_PATH` in `.env` or place file at `../data/olist.sqlite` |
| `Permission denied` | Ensure PostgreSQL user has CREATE DATABASE privileges |

## Project Structure

```
code/
├── main.py                            # Master orchestrator
├── requirements.txt                   # Python dependencies
├── .env.example                       # Template for credentials
├── .gitignore
└── src/
    ├── config.py                      # Configuration & DB connections
    ├── extract/
    │   └── migrate.py                 # Phase 1: Extract
    ├── transform/
    │   ├── bronze/
    │   │   └── build_bronze.py        # Phase 2: Bronze
    │   ├── silver/
    │   │   └── build_silver.py        # Phase 3: Silver
    │   └── gold/
    │       ├── build_dimensions.py    # Phase 4: Dimensions
    │       └── build_facts.py         # Phase 5: Facts
    ├── load/
    │   └── load_to_gold.py            # Phase 6: Load
    ├── reconciliation/
    │   ├── reconciliation_queries.py  # Query definitions
    │   └── run_reconciliation.py     # Phase 8: Reconciliation
    └── validate.py                    # Phase 7: Validation
