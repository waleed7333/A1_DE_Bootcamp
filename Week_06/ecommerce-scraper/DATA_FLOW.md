# Data Flow Diagram (DFD Level 1)

## Overview

This document provides a detailed **Data Flow Diagram (DFD)** showing how data moves through the system from external source to end user.

---

## Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW DIAGRAM (DFD Level 1)                            │
│                          E-Commerce Web Scraping & API Service                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                               EXTERNAL ENTITY
                          ┌─────────────────┐
                          │   E-commerce    │
                          │     Website     │
                          │   (Data Source) │
                          └────────┬────────┘
                                   │
                                   │ ① HTML Content (HTTP Response)
                                   │ • Product listings
                                   │ • Detail page HTML
                                   │ • Image URLs
                                   ▼
┌────────────────────────────────────────────────────────┐
│                                                        │
│                PROCESS 1.0: EXTRACT DATA              │
│                ════════════════════════════            │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │                    scraper.py                    │ │
│  │                      │                           │ │
│  │                 Input:                         │ │
│  │                 • Main page URL                 │ │
│  │                 • Product detail URLs           │ │
│  │                      │                           │ │
│  │              Processing:                       │ │
│  │              1. Fetch HTML with requests       │ │
│  │              2. Parse with BeautifulSoup       │ │
│  │              3. Extract product links          │ │
│  │              4. Visit each product page        │ │
│  │              5. Extract fields (name, price)   │ │
│  │              6. Download images                │ │
│  │                      │                           │ │
│  │               Output:                          │ │
│  │               • List of product dictionaries   │ │
│  │               • Downloaded image files         │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
└────────────┬──────────────────────┬────────────────────┘
             │                      │
             │ ② Raw CSV Data       │ ③ Image Binary Data
             │   (Unprocessed)      │   (JPEG/PNG files)
             ▼                      ▼
┌─────────────────────────┐    ┌─────────────────────────┐
│      DATA STORE D1       │    │      DATA STORE D2      │
│            │             │    │            │             │
│      raw_data.csv        │    │     images/              │
│            │             │    │            │             │
│  ┌───────────────────┐   │    │  ┌───────────────────┐   │
│  │     Fields:       │   │    │  │     Files:        │   │
│  │     • id          │   │    │  │  • 1_Abominable...│   │
│  │     • name_raw    │   │    │  │  • 2_Adrienne...  │   │
│  │     • price_raw   │   │    │  │  • 3_Aeon_Capri...│   │
│  │     • description_│   │    │  │  • ...           │   │
│  │     • category_raw│   │    │  │                  │   │
│  │     • sku_raw     │   │    │  │   Format: Binary │   │
│  │     • stock_raw   │   │    │  │   Location:      │   │
│  │     • image_url   │   │    │  │   /var/lib/      │   │
│  │     • local_image_│   │    │  │   ecommerceScrap…│   │
│  └───────────────────┘   │    │  └───────────────────┘   │
│            │             │    │            │             │
│   Purpose:              │    │   Purpose:             │
│   Audit trail &         │    │   Local image serving │
│   reprocessing          │    │                        │
└────────────┬────────────┘    └───────────┬─────────────┘
             │                              │
             │ ④ Read Raw Data              │ ⑤ Validate Path
             │   (CSV → DataFrame)          │   (Check exists)
             │                              │
             └───────────┬───────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│                                                        │
│                PROCESS 2.0: CLEAN DATA                 │
│                ════════════════════════                │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │                    cleaner.py                     │ │
│  │                      │                           │ │
│  │                 Input:                           │ │
│  │                 • raw_data.csv (DataFrame)       │ │
│  │                 • Image directory path           │ │
│  │                      │                           │ │
│  │              Processing:                          │ │
│  │              1. Parse price strings to float     │ │
│  │              2. Normalize text (trim spaces)     │ │
│  │              3. Categorize by price level        │ │
│  │              4. Validate image file existence   │ │
│  │              5. Handle missing values           │ │
│  │                      │                           │ │
│  │           Transformations:                       │ │
│  │           • "$69.00" → 69.0                    │ │
│  │           • "  Text  " → "Text"                 │ │
│  │           • price → price_level (Budget/Mid/Premium) │
│  │           • path → validated_path (if exists)   │ │
│  │                      │                           │ │
│  │               Output:                           │ │
│  │               • Cleaned DataFrame               │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
└────────────────────────┬───────────────────────────────┘
                         │
                         │ ⑥ Cleaned CSV Data
                         │   (Production Ready)
                         ▼
┌─────────────────────────────────┐
│         DATA STORE D3           │
│                                 │
│       cleaned_data.csv          │
│                                 │
│  ┌───────────────────────────┐  │
│  │        Fields:            │  │
│  │        • id               │  │
│  │        • name (cleaned)   │  │
│  │        • price (float)    │  │
│  │        • price_level      │  │
│  │        • description      │  │
│  │        • category (cleaned│  │
│  │        • sku (cleaned)    │  │
│  │        • stock (cleaned)  │  │
│  │        • image_path       │  │
│  └───────────────────────────┘  │
│                                 │
│         Purpose:                │
│     Production data for API     │
└──────────────┬──────────────────┘
               │
               │ ⑦ Pandas Read
               │   (CSV → DataFrame)
               ▼
┌────────────────────────────────────────────────────────┐
│                                                        │
│                 PROCESS 3.0: SERVE API                │
│                 ═══════════════════════                │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │                      api.py                       │ │
│  │                      │                           │ │
│  │                 Input:                           │ │
│  │                 • cleaned_data.csv (on startup)  │ │
│  │                 • HTTP requests                  │ │
│  │                      │                           │ │
│  │              Processing:                          │ │
│  │              1. Load data into memory (pandas)   │ │
│  │              2. Route requests to handlers      │ │
│  │              3. Filter/transform for response    │ │
│  │              4. Serve images via FileResponse    │ │
│  │              5. Calculate statistics            │ │
│  │                      │                           │ │
│  │              Endpoints:                         │ │
│  │              • GET / → API info                 │ │
│  │              • GET /data → All products (JSON)  │ │
│  │              • GET /data/{id}→ Single product    │ │
│  │              • GET /image/{id}→ Image file      │ │
│  │              • GET /stats → Statistics (JSON)  │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
└────────────────────────┬───────────────────────────────┘
                         │
                         │ ⑧ HTTP Response
                         │   • JSON (application/json)
                         │   • Image (image/jpeg)
                         ▼
┌─────────────────────────────────┐
│         EXTERNAL ENTITY         │
│                                 │
│         API Consumer            │
│                                 │
│   • Web Browser                │
│   • curl / Postman             │
│   • Mobile App                 │
│   • Other Services             │
│                                 │
│   Access:                      │
│   http://IP:8000/{endpoint}    │
└─────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════════════════
                                    DATA FLOW LEGEND
═══════════════════════════════════════════════════════════════════════════════════════════

① HTML Content   : HTTP GET response containing product data
② Raw CSV Data   : Unprocessed data persisted for audit
③ Image Binary   : Downloaded image files (JPEG/PNG)
④ Read Raw Data  : pandas read_csv operation
⑤ Validate Path  : os.path.exists check
⑥ Cleaned CSV    : Processed data ready for production
⑦ Pandas Read    : Loading cleaned data into memory
⑧ HTTP Response  : JSON or binary image response to client
```

---

## Data Transformation Steps

### Step 1: Raw Extraction

```
Website HTML → BeautifulSoup → Dict → pandas → raw_data.csv
```

### Step 2: Data Cleaning

```
raw_data.csv → pandas DataFrame → Clean Functions → cleaned_data.csv
```

**Price Transformation:**

```
"$69.00" → 69.0 → "Premium"
```

**Text Transformation:**

```
"  Abominable Hoodie  " → "Abominable Hoodie"
```

### Step 3: API Serving

```
cleaned_data.csv → pandas DataFrame (memory) → JSON Response
```

**Single Product Flow:**

```
GET /data/1 → Filter DataFrame by id=1 → Convert to dict → JSON
```

---

## Data Volume Estimates

| Stage | Records | Size | Format |
|-------|---------|------|--------|
| Raw HTML (per page) | N/A | ~500KB | HTML |
| Raw CSV (16 products) | 16 rows | ~4.5KB | CSV |
| Raw CSV (188 products) | 188 rows | ~52KB | CSV |
| Images (per product) | 1 file | ~50KB | JPEG |
| Images (16 products) | 16 files | ~800KB | JPEG |
| Cleaned CSV (16 products) | 16 rows | ~3KB | CSV |
| JSON Response (/data) | 16 objects | ~12KB | JSON |