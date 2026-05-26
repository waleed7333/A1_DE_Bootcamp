
# Olist E-Commerce Data Warehouse

## Executive Summary

| Field | Value |
|:---|:---|
| **Project** | Data Engineering Assignment - Olist Data Warehouse |
| **Dataset** | Olist E-Commerce (Kaggle) |
| **Architecture** | Kimball Star Schema + Medallion Pattern (Bronze → Silver → Gold) |
| **Dimensions** | 11 tables |
| **Facts** | 5 tables (multi-fact model) |
| **ETL** | Python + Pandas + SQLAlchemy (8 phases, fully automated) |
| **Validation** | 29 structural checks + 37 reconciliation checks |
| **Status** | ✅ ALL CHECKS PASSED - PIPELINE COMPLETED SUCCESSFULLY |

---

## Pipeline Results (One Command)

```bash
python code/main.py
```

| Phase | Description | Result |
|:-----:|:---|:---|
| 1 | Extract: SQLite → olist_oltp | ✅ 1,559,764 rows migrated |
| 2 | Bronze: Raw copy → olist_olap.bronze | ✅ 11 tables with _loaded_at |
| 3 | Silver: Clean → olist_olap.silver | ✅ 578,303 rows (9 tables) |
| 4 | Gold Dimensions: Build 11 dimensions | ✅ 165,666 rows |
| 5 | Gold Facts: Build 5 facts | ✅ 717,241 rows |
| 6 | Load: Write + 20 indexes | ✅ 882,907 total rows |
| 7 | Validate: Structural checks | ✅ 29/29 passed |
| 8 | Reconcile: Source vs Target | ✅ 37/37 matches |

---

## Key Design Decisions

| # | Decision | Rationale |
|:--:|:---|:---|
| 1 | **Kimball Star Schema** | Fast queries, business-user friendly, optimal for BI tools |
| 2 | **Multiple Fact Tables (5)** | Preserves correct grain per business process, prevents double-counting |
| 3 | **Separate Dim_Location** | Single source of truth for geography, enables cross-entity location analysis |
| 4 | **Dim_Lead + Optional seller_key** | Separates Lead entity from Seller entity, supports full funnel analysis |
| 5 | **Fact_Order_Events (Factless Fact)** | Enables simple order lifecycle funnel queries, avoids multiple full scans |
| 6 | **SCD Type 1** | Correct for available data (source lacks change history) |
| 7 | **No product_key in Fact_Reviews** | Respects review grain (one review per order, not per product) |
| 8 | **20 Performance Indexes** | Optimizes JOIN performance for all foreign key relationships |
| 9 | **37 Reconciliation Checks** | Source-to-target validation catches ETL discrepancies |
| 10 | **Integer Surrogate Keys** | 8x smaller FK storage, faster JOINs than VARCHAR keys |

---

## Business Questions Answered

| Business Question | Analysis | Status |
|:---|:---|:--:|
| How are sales trending over time? | Monthly revenue with YoY comparison | ✅ |
| Who are the most valuable customers? | Top 10 by lifetime value | ✅ |
| What affects delivery performance? | Delay analysis by state and region | ✅ |
| Which products drive revenue? | Category revenue with review scores | ✅ |
| Payment behavior analysis | Installments impact on order value | ✅ |
| Order lifecycle funnel | Conversion rates through stages | ✅ |
| Seller acquisition funnel | Marketing channel conversion rates | ✅ |
| Customer retention | Repeat purchase rate by month | ✅ |

---

## Architecture Overview

### Data Flow

```
Source (SQLite) ──▶ Extract (olist_oltp) ──▶ Bronze ──▶ Silver ──▶ Gold ──▶ Reports
  11 Tables           ~1.5M Rows            Raw Copy    Cleaned    Star Schema
  Phase 1             Phase 1                Phase 2     Phase 3    Phases 4-5-6
```

### Star Schema

| Type | Count | Tables |
|:---|:---:|:---|
| **Dimensions** | 11 | dim_date, dim_time, dim_customer, dim_seller, dim_product, dim_location, dim_lead, dim_payment_type, dim_order_status, dim_event_type, dim_lead_source |
| **Facts** | 5 | fact_sales, fact_payments, fact_reviews, fact_seller_acquisition, fact_order_events |

### Fact Table Grains

| Fact Table | Grain | Row Count | Business Process |
|:---|:---|:---:|:---|
| fact_sales | order_id + order_item_id | 112,650 | Sales transactions |
| fact_payments | order_id + payment_sequential | 103,886 | Payment processing |
| fact_reviews | review_id | 99,224 | Customer satisfaction |
| fact_seller_acquisition | mql_id | 8,000 | Marketing funnel |
| fact_order_events | order_id + event_type_key | 393,481 | Order lifecycle |

---

## Project Structure

```
Olist_DWH_Project/
│
├── README.md                              # This file
│
├── code/                                  # All source code
│   ├── README.md                          # Setup & run instructions
│   ├── main.py                            # Master orchestrator
│   ├── requirements.txt                   # Python dependencies
│   ├── .env.example                       # Credentials template
│   ├── .gitignore
│   └── src/
│       ├── config.py                      # Configuration & DB connections
│       ├── extract/migrate.py             # Phase 1: SQLite → olist_oltp
│       ├── transform/
│       │   ├── bronze/build_bronze.py     # Phase 2: Raw copy
│       │   ├── silver/build_silver.py     # Phase 3: Clean & standardize
│       │   └── gold/
│       │       ├── build_dimensions.py    # Phase 4: 11 dimensions
│       │       └── build_facts.py         # Phase 5: 5 facts
│       ├── load/load_to_gold.py           # Phase 6: Write + indexes
│       ├── reconciliation/
│       │   ├── reconciliation_queries.py  # 37 query pairs
│       │   └── run_reconciliation.py     # Phase 8: Source vs target
│       └── validate.py                    # Phase 7: Structural checks
│
├── docs/                                  # Detailed documentation
│   ├── architecture_diagram.md            # Mermaid source
│   ├── star_schema_diagram.md             # Mermaid source
│   ├── medallion_layers.md                # Mermaid source
│   ├── data_dictionary.md                 # Column-level docs
│   └── decisions.md                       # 12 ADR records
│
├── images/                                # Exported diagrams
│   ├── star_schema_diagram.png            # Full star schema ER diagram
│   ├── architecture_diagram.png           # Pipeline data flow
│   └── medallion_layers.png               # Bronze → Silver → Gold
│
├── queries/                               # Ready-to-use SQL
│   ├── sample_queries.sql                 # 12 analytical queries
│   └── reconciliation_queries.sql         # 18 validation queries
│
└── pipeline_output.txt                    # Successful execution log
```

---

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 12+

### Setup

```bash
# 1. Install dependencies
pip install -r code/requirements.txt

# 2. Configure credentials
cp code/.env.example code/.env
# Edit code/.env with your PostgreSQL details

# 3. Run the pipeline
python code/main.py
```

Detailed setup instructions in [`code/README.md`](code/README.md).

---

## Validation & Quality Assurance

### Structural Validation (29 checks)

| Category | Count | What It Checks |
|:---|:---:|:---|
| Row Counts | 5 | Fact tables match silver source counts |
| NULL Foreign Keys | 16 | Critical FKs are populated |
| Referential Integrity | 8 | All FKs have matching dimension PKs |

### Reconciliation Testing (37 checks)

| Category | Checks | Coverage |
|:---|:---:|:---|
| A - Row Counts | 6 | Orders, items, customers, sellers, products, reviews |
| B - Financial Metrics | 5 | Revenue, shipping, avg price, payments |
| C-G - Distributions | 7 | Status, payment types, scores, categories, leads |
| H-N - Advanced | 19 | Events, geography, dates, products, installments, delivery |

---

## Documentation Index

| Document | Content |
|:---|:---|
| `docs/decisions.md` | 12 Architectural Decision Records (ADR) with trade-off analysis |
| `docs/data_dictionary.md` | Complete column-level documentation for all 16 tables |
| `docs/architecture_diagram.md` | Mermaid source for pipeline architecture |
| `docs/star_schema_diagram.md` | Mermaid source for star schema ER diagram |
| `docs/medallion_layers.md` | Mermaid source for three-layer architecture |
| `code/README.md` | Setup, run, and troubleshooting instructions |

---

## License

This project is created for educational purposes using the publicly available Olist E-commerce dataset from Kaggle.

**Dataset Source:** [Olist E-Commerce Dataset on Kaggle](https://www.kaggle.com/datasets/terencicp/e-commerce-dataset-by-olist-as-an-sqlite-database)
