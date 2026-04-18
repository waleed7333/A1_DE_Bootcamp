# Module Dependency Diagram

## Overview

This document illustrates the relationships between all modules in the system, including both custom Python modules and external dependencies.

---

## Complete Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                             MODULE DEPENDENCY DIAGRAM                                  │
│                        (UML-inspired Component Relationship)                           │
└─────────────────────────────────────────────────────────────────────────────────────────┘

╔════════════════════════════════╗
║      EXTERNAL PACKAGES         ║
║     (PyPI / Python Ecosystem)  ║
╚════════════════════════════════╝
           │
           │
┌──────────┴──────────┬───────────────────────────────┬───────────────────────────────┐
│                      │                               │                               │
▼                      ▼                               ▼                               ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│    requests     │  │  BeautifulSoup  │  │     pandas      │  │     FastAPI     │
│     (HTTP)      │  │    (Parsing)   │  │   (DataFrame)   │  │(Web Framework)  │
│                  │  │                 │  │                 │  │                  │
│  • get()        │  │  • find()       │  │  • read_csv()  │  │  • @app.get()   │
│  • Response     │  │  • find_all()   │  │  • to_csv()    │  │  • HTTPException │
│  • headers      │  │  • text         │  │  • to_dict()   │  │  • FileResponse │
│  • timeout      │  │  • get()        │  │  • notna()     │  │  • JSONResponse │
│                 │  │                 │  │  • value_counts │  │                  │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                     │                     │                     │
         │                     │                     │                     │
         ▼                     ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              CUSTOM MODULES                                              │
│                          (Our Python Scripts - Internal)                                │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                           1. SCRAPER MODULE (scraper.py)                                │
│                           ═══════════════════════════════                              │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                  DEPENDENCIES                                      │  │
│  │                                                                                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │  │
│  │  │  requests   │  │ BeautifulSoup│  │   pandas   │  │     os     │            │  │
│  │  │             │  │             │  │             │  │  (built-in) │            │  │
│  │  │  • get()    │  │  • HTML     │  │  • DataFrame│  │  • makedirs│            │  │
│  │  │  • headers  │  │   parsing   │  │  • to_csv() │  │  • path.join│           │  │
│  │  │  • timeout  │  │  • find()   │  │             │  │  • exists   │            │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │  │
│  │                                                                                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                             │  │
│  │  │    time     │  │   urllib    │  │     re      │                             │  │
│  │  │  (built-in) │  │  (built-in) │  │  (built-in) │                             │  │
│  │  │             │  │             │  │             │                             │  │
│  │  │  • sleep()  │  │ • urljoin() │  │   • sub()   │                             │  │
│  │  │  for rate   │  │ for full    │  │  filename   │                             │  │
│  │  │  limiting   │  │   URLs      │  │  sanitize   │                             │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                             │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                  FUNCTIONS                                        │  │
│  │                                                                                   │  │
│  │  create_directories()                                                             │  │
│  │  ├── Called by: main()                                                           │  │
│  │  ├── Uses: os.makedirs()                                                         │  │
│  │  └── Creates: data/, images/                                                     │  │
│  │                                                                                   │  │
│  │  fetch_page(url)                                                                  │  │
│  │  ├── Called by: main(), extract_product_details()                                 │  │
│  │  ├── Uses: requests.get()                                                        │  │
│  │  └── Returns: HTML string                                                        │  │
│  │                                                                                   │  │
│  │  get_product_links(html)                                                          │  │
│  │  ├── Called by: main()                                                           │  │
│  │  ├── Uses: BeautifulSoup.find_all('li', class_='product')                        │  │
│  │  └── Returns: List of product URLs                                               │  │
│  │                                                                                   │  │
│  │  extract_product_details(url, product_id)                                        │  │
│  │  ├── Called by: main() (loop)                                                    │  │
│  │  ├── Uses: fetch_page(), BeautifulSoup.find()                                    │  │
│  │  ├── Calls: download_image()                                                      │  │
│  │  └── Returns: Dict with product data                                             │  │
│  │                                                                                   │  │
│  │  download_image(img_url, product_id, product_name)                               │  │
│  │  ├── Called by: extract_product_details()                                         │  │
│  │  ├── Uses: requests.get(), open(wb), re.sub()                                    │  │
│  │  └── Returns: Local file path or None                                            │  │
│  │                                                                                   │  │
│  │  save_to_csv(products, filepath)                                                 │  │
│  │  ├── Called by: main()                                                           │  │
│  │  ├── Uses: pandas.DataFrame.to_csv()                                             │  │
│  │  └── Returns: None                                                               │  │
│  │                                                                                   │  │
│  │  main()                                                                          │  │
│  │  ├── Entry point                                                                  │  │
│  │  ├── Calls: create_dirs → fetch_page → get_product_links →                        │  │
│  │  │           extract_product_details (loop) → save_to_csv                         │  │
│  │  └── Returns: None                                                               │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                    OUTPUTS                                       │  │
│  │                                                                                   │  │
│  │  • /var/lib/ecommerceScraping/data/raw_data.csv                                 │  │
│  │  • /var/lib/ecommerceScraping/images/*.jpg                                       │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
           │
           │ Reads raw_data.csv
           ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                           2. CLEANER MODULE (cleaner.py)                                │
│                           ═══════════════════════════════                              │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                  DEPENDENCIES                                      │  │
│  │                                                                                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │  │
│  │  │   pandas    │  │     os      │  │     re      │  │   (none)    │            │  │
│  │  │             │  │  (built-in) │  │  (built-in) │  │             │            │  │
│  │  │ • read_csv()│  │  • path     │  │   • sub()   │  │             │            │  │
│  │  │ • to_csv()  │  │   .exists() │  │  for text   │  │             │            │  │
│  │  │ • DataFrame  │  │             │  │  cleaning   │  │             │            │  │
│  │  │  operations  │  │             │  │             │  │             │            │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                  FUNCTIONS                                        │  │
│  │                                                                                   │  │
│  │  clean_price(price_str)                                                          │  │
│  │  ├── Called by: main() (via apply)                                                │  │
│  │  ├── Uses: re.sub(r'[^\d.]', '', str)                                            │  │
│  │  ├── Input: "$69.00"                                                              │  │
│  │  └── Returns: 69.0 (float) or None                                               │  │
│  │                                                                                   │  │
│  │  clean_text(text)                                                                │  │
│  │  ├── Called by: main() (via apply)                                                │  │
│  │  ├── Uses: str.split() + ' '.join()                                              │  │
│  │  ├── Input: "  Text with spaces  "                                               │  │
│  │  └── Returns: "Text with spaces"                                                 │  │
│  │                                                                                   │  │
│  │  clean_category(category_str)                                                     │  │
│  │  ├── Called by: main() (via apply)                                                │  │
│  │  ├── Uses: clean_text()                                                          │  │
│  │  └── Returns: Cleaned category string                                            │  │
│  │                                                                                   │  │
│  │  get_price_level(price)                                                           │  │
│  │  ├── Called by: main() (via apply)                                                │  │
│  │  ├── Logic:                                                                      │  │
│  │  │   • price < 30 → "Budget"                                                     │  │
│  │  │   • price < 60 → "Mid-range"                                                  │  │
│  │  │   • price >= 60 → "Premium"                                                   │  │
│  │  │   • price None → "Unknown"                                                    │  │
│  │  └── Returns: Category string                                                    │  │
│  │                                                                                   │  │
│  │  validate_image_path(path)                                                       │  │
│  │  ├── Called by: main() (via apply)                                                │  │
│  │  ├── Uses: os.path.exists()                                                      │  │
│  │  ├── Input: "/var/lib/ecommerceScraping/images/1_Abom.jpg"                        │  │
│  │  └── Returns: Path if exists, else None                                          │  │
│  │                                                                                   │  │
│  │  main()                                                                          │  │
│  │  ├── Entry point                                                                  │  │
│  │  ├── Calls: pd.read_csv() → apply cleaning functions → pd.to_csv()              │  │
│  │  └── Returns: None                                                               │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                     OUTPUT                                      │  │
│  │                                                                                   │  │
│  │  • /var/lib/ecommerceScraping/data/cleaned_data.csv                              │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
           │
           │ Reads cleaned_data.csv
           ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                              3. API MODULE (api.py)                                    │
│                              ═══════════════════════════                               │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                  DEPENDENCIES                                      │  │
│  │                                                                                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │  │
│  │  │   FastAPI   │  │   pandas    │  │   uvicorn   │  │     os      │            │  │
│  │  │             │  │             │  │             │  │  (built-in) │            │  │
│  │  │  • FastAPI()│  │ • read_csv()│  │   • run()   │  │  • path     │            │  │
│  │  │ • @app.get()│  │ • to_dict() │  │    ASGI     │  │   .exists() │            │  │
│  │  │ • HTTPExc-  │  │ • notna()   │  │   server    │  │  • getcwd() │            │  │
│  │  │   eption    │  │ • min/max/  │  │             │  │             │            │  │
│  │  │ • FileResp- │  │   mean()    │  │             │  │             │            │  │
│  │  │   onse      │  │             │  │             │  │             │            │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                             FUNCTIONS & ENDPOINTS                                 │  │
│  │                                                                                   │  │
│  │  load_data()                                                                       │  │
│  │  ├── Called by: Module level (on import)                                          │  │
│  │  ├── Uses: pd.read_csv(CLEANED_DATA_PATH)                                        │  │
│  │  └── Returns: pandas DataFrame                                                   │  │
│  │                                                                                   │  │
│  │  @app.get("/")                                                                    │  │
│  │  async def root()                                                                │  │
│  │  ├── Returns: API information (version, endpoints, product count)                │  │
│  │  └── HTTP Status: 200                                                            │  │
│  │                                                                                   │  │
│  │  @app.get("/data")                                                                │  │
│  │  async def get_all_products()                                                    │  │
│  │  ├── Returns: {"total": N, "products": [...]}                                    │  │
│  │  └── HTTP Status: 200, 404 (if no data)                                          │  │
│  │                                                                                   │  │
│  │  @app.get("/data/{product_id}")                                                  │  │
│  │  async def get_product(product_id: int)                                          │  │
│  │  ├── Filters: products_df[products_df["id"] == product_id]                       │  │
│  │  └── HTTP Status: 200, 404 (if not found)                                        │  │
│  │                                                                                   │  │
│  │  @app.get("/image/{product_id}")                                                 │  │
│  │  async def get_product_image(product_id: int)                                   │  │
│  │  ├── Uses: FileResponse(image_path)                                              │  │
│  │  └── HTTP Status: 200, 404 (if no image)                                         │  │
│  │                                                                                   │  │
│  │  @app.get("/stats")                                                               │  │
│  │  async def get_statistics()                                                       │  │
│  │  ├── Returns: {                                                                  │  │
│  │  │   "total_products": N,                                                        │  │
│  │  │   "categories": [...],                                                        │  │
│  │  │   "price_levels": {...},                                                      │  │
│  │  │   "price_range": {"min": X, "max": Y, "average": Z}                          │  │
│  │  │ }                                                                            │  │
│  │  └── HTTP Status: 200, 404 (if no data)                                          │  │
│  │                                                                                   │  │
│  │  main block                                                                       │  │
│  │  ├── Entry point when run directly                                                │  │
│  │  ├── Uses: uvicorn.run(app, host="0.0.0.0", port=8000)                          │  │
│  │  └── Prints startup messages                                                     │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                    EXPOSES                                        │  │
│  │                                                                                   │  │
│  │  • http://0.0.0.0:8000 (REST API)                                                 │  │
│  │  • http://0.0.0.0:8000/docs (Swagger Documentation)                              │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Interaction Sequence Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              SEQUENCE DIAGRAM                                          │
│                          (Data Extraction & API Serving Flow)                           │
└─────────────────────────────────────────────────────────────────────────────────────────┘

  User/Client    api.py    cleaner.py   scraper.py    Website
      │            │           │            │            │
      │            │           │            │            │
      │            │      (On package installation - postinst script)
      │            │           │            │            │
      │            │           ├──HTTP GET──────▶│
      │            │           │◀───HTML────────┤
      │            │           │            │            │
      │            │           ├──Parse HTML───┤
      │            │           │            │            │
      │            │           ├──HTTP GET──────▶│ (each product)
      │            │           │◀───HTML────────┤
      │            │           │            │            │
      │            │           ├──HTTP GET──────▶│ (images)
      │            │           │◀───Binary──────┤
      │            │           │            │            │
      │            │           ├──Save CSV───┐ │            │
      │            │           │            │ │            │
      │            │◀──Read raw CSV──────────┤ │            │
      │            │           │            │ │            │
      │            │      Clean data────────┐ │ │            │
      │            │           │            │ │ │            │
      │            │      Save cleaned──────┘ │ │            │
      │            │           │            │ │            │
      │◀──Read cleaned──────────┤ │ │            │
      │            │           │            │            │
      │      (Service starts - systemd)       │            │
      │            │           │            │            │
      │──HTTP GET──────▶│            │            │
      │      /data      │            │            │
      │◀──JSON──────────┤            │            │
      │            │           │            │            │
      │──HTTP GET──────▶│            │            │
      │    /data/1      │            │            │
      │◀──JSON──────────┤            │            │
      │            │           │            │            │
      │──HTTP GET──────▶│            │            │
      │   /image/1      │            │            │
      │◀──JPEG Image────┤            │            │
      │            │           │            │            │
```

---

## Dependency Version Matrix

| Package | Version | Purpose | Installation Method |
|---------|---------|---------|---------------------|
| Python | 3.12+ | Runtime | apt |
| requests | 2.31.0 | HTTP client | apt (python3-requests) |
| beautifulsoup4 | 4.12.3 | HTML parsing | apt (python3-bs4) |
| pandas | 2.2.0 | Data manipulation | apt (python3-pandas) |
| fastapi | 0.136.0 | Web framework | pip (--break-system-packages) |
| uvicorn | 0.44.0 | ASGI server | pip (--break-system-packages) |
| pydantic | 2.13.2 | Data validation | pip (fastapi dependency) |
| starlette | 1.0.0 | Web toolkit | pip (fastapi dependency) |