# System Architecture Analysis

## Overview

The E-Commerce Web Scraping & API Service follows a **layered architecture** with clear separation of concerns. This document provides a detailed analysis of each architectural component and their interactions.

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              E-COMMERCE SCRAPING PLATFORM                               │
│                                ARCHITECTURE OVERVIEW                                    │
└─────────────────────────────────────────────────────────────────────────────────────────┘

╔═══════════════╗
║    INTERNET   ║
╚═══════╤═══════╝
        │
        ▼
┌───────────────────────────────────────────────┐
│            EXTERNAL DATA SOURCE               │
│        scrapingcourse.com/ecommerce           │
│                                                │
│   • 188 Products across 12 pages              │
│   • HTML structure with product listings      │
│   • Individual product detail pages           │
└───────────────────┬───────────────────────────┘
                    │
┌───────────────────┼───────────────────┐
│                   │                    │
│   HTTP Requests   │   Image Downloads  │
│   (HTML Content)  │   (Binary Data)    │
│                   │                    │
        ▼           ▼           ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                  EXTRACTION LAYER                                       │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                    scraper.py                                    │  │
│  │                                    │                                              │  │
│  │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐                 │  │
│  │  │   fetch_page()   │───▶│ extract_products │───▶│ download_image() │               │  │
│  │  │       │          │ │        │         │ │        │          │               │  │
│  │  │ • HTTP GET        │ │ • Parse HTML     │ │ • Fetch binary    │               │  │
│  │  │ • User-Agent      │ │ • Find li.product│ │ • Save to disk    │               │  │
│  │  │ • Error handling  │ │ • Extract fields │ │ • Safe filenames  │               │  │
│  │  │ • Timeout 10s     │ │ • Follow links   │ │ • Error recovery  │               │  │
│  │  └──────────────────┘ └──────────────────┘ └──────────────────┘                 │  │
│  │                                    │                                              │  │
│  │                    ┌──────────────────┐                                          │  │
│  │                    │  save_to_csv()   │                                          │  │
│  │                    │        │         │                                          │  │
│  │                    │ • pandas to_csv  │                                          │  │
│  │                    │ • UTF-8 encoding │                                          │  │
│  │                    │ • No index       │                                          │  │
│  │                    └──────────────────┘                                          │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  OUTPUTS:                                                                               │
│  • raw_data.csv (unprocessed data)                                                     │
│  • images/*.jpg (downloaded images)                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘
        │
        │ Data Persisted
        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                  STORAGE LAYER                                          │
│                                                                                         │
│  ┌─────────────────────────────────────────┐    ┌─────────────────────────────────────┐  │
│  │             raw_data.csv                │    │            images/                 │  │
│  │                  │                      │    │                 │                   │  │
│  │   id   │ name_raw │   price_raw        │    │  1_Abominable_Hoodie.jpg           │  │
│  │   ─────┼──────────┼─────────────────   │    │  2_Adrienne_Trek_Jacket.jpg        │  │
│  │   1    │ Abominable... │ $69.00       │    │  3_Aeon_Capri.jpg                  │  │
│  │   2    │ Adrienne...   │ $57.00       │    │  ...                               │  │
│  │   ...  │ ...          │ ...           │    │  16_Artemis_Running_Short.jpg      │  │
│  │                  │                      │    │                                    │  │
│  │  Purpose: Audit trail & reprocessing   │    │  Purpose: Local image serving      │  │
│  └─────────────────────────────────────────┘    └─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
        │
        │ Read for Cleaning
        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                   CLEANING LAYER                                        │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                    cleaner.py                                    │  │
│  │                                    │                                              │  │
│  │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐                   │  │
│  │  │  clean_price()   │ │  clean_text()   │ │ validate_image()│                   │  │
│  │  │        │         │ │       │         │ │       │         │                   │  │
│  │  │ • Remove '$'     │ │ • Strip spaces  │ │ • Check exists  │                   │  │
│  │  │ • Remove letters │ │ • Remove special│ │ • Verify path   │                   │  │
│  │  │ • Convert float  │ │ • Normalize     │ │ • Return valid  │                   │  │
│  │  │ • Handle N/A     │ │ • Handle NaN    │ │ • Null if missing│                   │  │
│  │  └──────────────────┘ └──────────────────┘ └──────────────────┘                   │  │
│  │                                    │                                              │  │
│  │                    ┌──────────────────┐                                          │  │
│  │                    │ get_price_level()│                                          │  │
│  │                    │        │         │                                          │  │
│  │                    │ • < $30 → Budget │                                          │  │
│  │                    │ • $30-60 → Mid   │                                          │  │
│  │                    │ • > $60 → Premium│                                          │  │
│  │                    │ • None → Unknown │                                          │  │
│  │                    └──────────────────┘                                          │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  OUTPUT:                                                                                │
│  • cleaned_data.csv (production-ready data)                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘
        │
        │ Data Ready for API
        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 PRESENTATION LAYER                                     │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                      api.py                                    │  │
│  │                                      │                                          │  │
│  │                         FastAPI Application                                     │  │
│  │                         ═══════════════════                                     │  │
│  │                                      │                                          │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐│  │
│  │  │                              ENDPOINTS                                     ││  │
│  │  ├─────────────┬───────────────────────────────────────────────────────────────┤│  │
│  │  │    GET /   │ API information (version, endpoints, product count)           ││  │
│  │  │  GET /data │ All products as JSON array with total count                  ││  │
│  │  │GET /data/  │ Single product by ID with 404 if not found                   ││  │
│  │  │   {id}     │                                                              ││  │
│  │  │GET /image/ │ Product image file (JPEG/PNG) with proper headers            ││  │
│  │  │   {id}     │                                                              ││  │
│  │  │  GET /stats│ Statistics: min/max/avg price, categories, price levels      ││  │
│  │  └─────────────┴───────────────────────────────────────────────────────────────┘│  │
│  │                                      │                                          │  │
│  │                         Uvicorn ASGI Server                                     │  │
│  │                         ═══════════════════                                     │  │
│  │  • Host: 0.0.0.0 (all interfaces)                                               │  │
│  │  • Port: 8000                                                                   │  │
│  │  • Workers: 1 (single process)                                                  │  │
│  │  • Auto-reload: Off (production)                                                │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
        │
        │ HTTP Responses (JSON/Image)
        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CLIENT LAYER                                        │
│                                                                                         │
│  ┌─────────────────────────────┐          ┌─────────────────────────────┐             │
│  │        Web Browser          │          │        API Client           │             │
│  │              │             │          │              │              │             │
│  │  • Swagger UI (/docs)       │          │  • curl                      │             │
│  │  • Interactive testing      │          │  • Postman                   │             │
│  │  • JSON visualization       │          │  • Python requests           │             │
│  │  • Image viewing           │          │  • JavaScript fetch          │             │
│  └─────────────────────────────┘          └─────────────────────────────┘             │
│                                                                                         │
│                         Access URL: http://172.26.119.44:8000                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Extraction Layer (`scraper.py`)

**Purpose:** Fetch raw data from external source and persist without modification.

**Key Functions:**

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `fetch_page(url)` | URL string | HTML string | HTTP GET with headers and timeout |
| `extract_products(html)` | HTML string | List[Dict] | Parse HTML, find products, extract fields |
| `download_image(url, id, name)` | Image URL, ID, name | File path | Download and save image locally |
| `save_to_csv(products, path)` | List[Dict], path | None | Save to CSV using pandas |

**Design Choices:**

- **User-Agent header:** Prevents blocking by mimicking a real browser
- **Timeout (10s):** Prevents hanging on slow responses
- **Safe filenames:** Sanitizes product names for filesystem compatibility
- **Sequential requests:** Respectful to target server (0.5s delay between products)

### 2. Cleaning Layer (`cleaner.py`)

**Purpose:** Validate, normalize, and enrich raw data for production use.

**Key Functions:**

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `clean_price(price_str)` | "$69.00" | 69.0 | Parse and convert to float |
| `clean_text(text)` | "  Text  " | "Text" | Remove extra whitespace |
| `get_price_level(price)` | 69.0 | "Premium" | Categorize by price range |
| `validate_image_path(path)` | File path | Valid path or None | Check if image exists |

**Validation Rules:**

- Price: Remove currency symbols, handle "N/A", convert to float
- Text: Trim spaces, handle NaN values
- Image: Verify file existence on disk
- Categories: Handle missing values with "Uncategorized"

### 3. Presentation Layer (`api.py`)

**Purpose:** Serve cleaned data via RESTful API with documentation.

**Endpoints:**

| Endpoint | Method | Response | Status Codes |
|----------|--------|----------|--------------|
| `/` | GET | API metadata | 200 |
| `/data` | GET | All products | 200, 404 |
| `/data/{id}` | GET | Single product | 200, 404 |
| `/image/{id}` | GET | Image file | 200, 404 |
| `/stats` | GET | Statistics | 200, 404 |

**Features:**

- Automatic Swagger documentation at `/docs`
- Type validation with Pydantic
- Proper HTTP status codes
- CORS-ready (can be enabled if needed)

---

## Data Schema Comparison

### Raw vs Cleaned Data

| Aspect | Raw Data | Cleaned Data |
|--------|----------|--------------|
| **Price format** | `"$69.00"` | `69.0` (float) |
| **Text format** | May have extra spaces | Normalized |
| **Price level** | Not present | Added (Budget/Mid/Premium) |
| **Image path** | As downloaded | Validated (exists check) |
| **Missing values** | "غير متوفر", "N/A" | `None` or default |

---

## Scalability Considerations

### Current Limitations

- Single-threaded scraping (sequential requests)
- In-memory data loading (pandas DataFrame)
- No database (CSV files)

### Potential Improvements

1. **Async scraping:** Use `aiohttp` for parallel requests
2. **Database storage:** Migrate from CSV to SQLite/PostgreSQL
3. **Caching:** Add Redis for frequently accessed data
4. **Horizontal scaling:** Deploy behind load balancer with multiple instances

---

## Security Considerations

| Aspect | Implementation | Rationale |
|--------|---------------|-----------|
| **User-Agent** | Custom header | Identify as legitimate client |
| **Rate limiting** | 0.5s delay | Respect target server |
| **File paths** | Sanitized names | Prevent directory traversal |
| **API exposure** | 0.0.0.0:8000 | Configurable for internal use |
| **Firewall** | ufw allow 8000 | Explicit port opening |

---

## Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Products scraped | 16 (demo) / 188 (full) | Configurable via pagination |
| Extraction time | ~45 seconds | Includes image downloads |
| API response time | < 50ms | Cached in memory |
| Memory usage | ~60MB | pandas DataFrame in RAM |
| Startup time | ~3 seconds | Service initialization |
