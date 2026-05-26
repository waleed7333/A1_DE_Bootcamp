# E-Commerce Web Scraping & API Service

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136.0-green.svg)
![Ubuntu](https://img.shields.io/badge/Ubuntu-20.04+-orange.svg)
![License](https://img.shields.io/badge/License-Educational-purple.svg)

A **production-ready web scraping microservice** that transforms a simple Python script into a fully deployable Debian package with automatic service management on Ubuntu.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
- [Installation](#installation)
- [Service Management](#service-management)
- [Project Structure](#project-structure)
- [Design Decisions](#design-decisions)
- [Data Schema](#data-schema)
- [Requirements](#requirements)
- [Author](#author)

---

## Overview

This project demonstrates a complete **ETL (Extract, Transform, Load) pipeline** combined with a **RESTful API layer**, packaged as a Debian package for seamless deployment on any Ubuntu server.

### What It Does

1. **Extracts** product data from an e-commerce demo website
2. **Downloads** product images locally
3. **Cleans** and validates the raw data
4. **Serves** the data via a FastAPI REST API
5. **Runs automatically** as a systemd service on boot

### From Script to System

```
Python Script → REST API → systemd Service → Debian Package → Production Deployment
```

---

## Features

### Data Pipeline

- **Raw Data Preservation:** Original data saved before cleaning for audit/debugging
- **Intelligent Cleaning:** Price parsing, text normalization, image validation
- **Price Categorization:** Automatic Budget/Mid-range/Premium classification
- **Parallel Image Download:** Efficient batch image fetching

### API Layer

- **RESTful Endpoints:** Full CRUD-like operations via HTTP
- **Interactive Documentation:** Auto-generated Swagger UI at `/docs`
- **Image Serving:** Direct image delivery via `/image/{id}`
- **Statistics Endpoint:** Min/max/average price analysis

### Deployment

- **Single-Command Installation:** `sudo dpkg -i package.deb`
- **Automatic Service Registration:** systemd integration
- **Boot-Time Startup:** Service starts automatically on system boot
- **Auto-Restart:** Failed services restart automatically
- **Firewall Configuration:** Automatic port 8000 opening

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SYSTEM ARCHITECTURE                               │
└─────────────────────────────────────────────────────────────────────────────┘

INTERNET
 │
 ▼
┌───────────────────┐
│  E-commerce Site  │  (scrapingcourse.com/ecommerce)
└─────────┬─────────┘
          │ HTTP GET
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            EXTRACTION LAYER                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         scraper.py                                   │   │
│  │  • Fetches HTML from product pages                                   │   │
│  │  • Parses with BeautifulSoup                                        │   │
│  │  • Downloads product images                                          │   │
│  │  • Saves raw data to CSV                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌───────────────────┐          ┌───────────────────┐
│    raw_data.csv   │          │      images/      │
│   (Unprocessed)   │          │   (Downloaded)    │
└─────────┬─────────┘          └─────────┬─────────┘
          │                              │
          └──────────────┬──────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             CLEANING LAYER                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         cleaner.py                                   │   │
│  │  • Parses price strings to float ($69.00 → 69.0)                    │   │
│  │  • Removes extra whitespace                                          │   │
│  │  • Categorizes products (Budget/Mid-range/Premium)                  │   │
│  │  • Validates image file existence                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌───────────────────┐
│  cleaned_data.csv  │
│   (Production)    │
└─────────┬─────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                            api.py                                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │   │
│  │  │  GET /data  │  │ GET /data/  │  │ GET /image/ │                │   │
│  │  │             │  │    {id}     │  │    {id}     │                │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │   │
│  │                                                                     │   │
│  │              FastAPI + Uvicorn ASGI Server                          │   │
│  │                    Listening: 0.0.0.0:8000                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌───────────────────┐
│   API Consumer    │
│ (Browser/Client)  │
└───────────────────┘
```

---

## Quick Start

### Prerequisites

- Ubuntu 20.04 or newer
- Python 3.7+
- Internet connection (for initial data fetch)

### One-Command Installation

```bash
# Download and install the Debian package
sudo dpkg -i ecommercescraping-1.0.0.deb

# Fix any missing dependencies (if needed)
sudo apt --fix-broken install -y
```

### Verify Installation

```bash
# Check service status
sudo systemctl status ecommerce-scraping

# Test the API
curl http://localhost:8000/
```

### Access the API

Open your browser and navigate to:

| Resource | URL |
|----------|-----|
| API Documentation | `http://YOUR_SERVER_IP:8000/docs` |
| All Products | `http://YOUR_SERVER_IP:8000/data` |
| Statistics | `http://YOUR_SERVER_IP:8000/stats` |

---

## API Documentation

### Base URL

```
http://your-server-ip:8000
```

### Endpoints

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| GET | `/` | API information | JSON with version and available endpoints |
| GET | `/data` | Get all products | JSON array of all products |
| GET | `/data/{id}` | Get product by ID | JSON object of single product |
| GET | `/image/{id}` | Get product image | Image file (JPEG/PNG) |
| GET | `/stats` | Get statistics | JSON with min/max/avg prices, categories |

### Example Response (`/data/1`)

```json
{
  "id": 1,
  "name": "Abominable Hoodie",
  "price": 69.0,
  "price_level": "Premium",
  "description": "A warm and comfortable hoodie...",
  "category": "Hoodies & Sweatshirts",
  "sku": "MH09",
  "stock": "Out of stock",
  "image_path": "/var/lib/ecommerceScraping/images/1_Abominable_Hoodie.jpg"
}
```

### Interactive Documentation

Visit `/docs` for the auto-generated Swagger UI where you can test all endpoints directly from your browser.

---

## Installation

### Building from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/ecommerce-scraper.git
cd ecommerce-scraper

# Build the Debian package
dpkg-deb --build ecommerceScraping_deb
mv ecommerceScraping_deb.deb ecommercescraping-1.0.0.deb

# Install
sudo dpkg -i ecommercescraping-1.0.0.deb
```

### Uninstallation

```bash
# Stop and disable the service
sudo systemctl stop ecommerce-scraping
sudo systemctl disable ecommerce-scraping

# Remove the package
sudo dpkg -r ecommercescraping

# Clean up data (optional)
sudo rm -rf /var/lib/ecommerceScraping
```

---

## Service Management

### Basic Commands

```bash
# Check service status
sudo systemctl status ecommerce-scraping

# Start the service
sudo systemctl start ecommerce-scraping

# Stop the service
sudo systemctl stop ecommerce-scraping

# Restart the service
sudo systemctl restart ecommerce-scraping

# View logs
sudo journalctl -u ecommerce-scraping -f

# Enable auto-start on boot
sudo systemctl enable ecommerce-scraping

# Disable auto-start on boot
sudo systemctl disable ecommerce-scraping
```

### Service Configuration

The service is defined in `/etc/systemd/system/ecommerce-scraping.service`:

```ini
[Unit]
Description=E-commerce Web Scraping API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/lib/ecommerceScraping
ExecStart=/usr/bin/python3 /usr/local/bin/api.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Project Structure

### Development Structure (GitHub)

```
ecommerce-scraper/
│
├── README.md                              # Project overview, quick start, API docs
│
├── ARCHITECTURE.md                        # System architecture diagrams and component analysis
│
├── DATA_FLOW.md                           # Data flow diagrams (DFD) with numbered flows
│
├── DEPLOYMENT.md                          # Deployment flow from .deb to running service
│
├── DESIGN_JUSTIFICATION.md                # Why each design decision was made (SRP, FHS, etc.)
│
├── MODULE_DEPENDENCIES.md                 # Module relationships and dependency graphs
│
├── SYSTEMD_SERVICE_EXPLAINED.md           # Line-by-line explanation of systemd service file
│
├── requirements.txt                       # Python dependencies list
│
├── ecommercescraping-1.0.0.deb            # Built Debian package (ready to install)
│
└── ecommerceScraping_deb/                 # Debian package build directory
    │
    ├── DEBIAN/                            # Package control files
    │   ├── control                        # Package metadata (name, version, dependencies)
    │   └── postinst                       # Post-installation script (runs after dpkg extracts files)
    │
    ├── etc/                               # System configuration files
    │   └── systemd/
    │       └── system/
    │           └── ecommerce-scraping.service    # systemd service definition (auto-start on boot)
    │
    ├── usr/                               # User system resources (Unix System Resources)
    │   └── local/                         # Locally installed software (not from apt)
    │       └── bin/                       # Executable binaries and scripts
    │           ├── scraper.py             # EXTRACTION: Fetches HTML, parses products, downloads images
    │           ├── cleaner.py             # CLEANING: Validates data, converts prices, categorizes
    │           └── api.py                 # PRESENTATION: FastAPI server, REST endpoints, Swagger docs
    │
    └── var/                               # Variable data (changes during runtime)
        └── lib/                           # Application-specific variable data (FHS standard)
            └── ecommerceScraping/         # Our application's data directory
                ├── data/                  # CSV storage directory (created by postinst)
                │   ├── raw_data.csv       # Unprocessed data from website (created by scraper.py)
                │   └── cleaned_data.csv   # Validated/cleaned data (created by cleaner.py)
                └── images/                # Downloaded product images directory (created by postinst)
                    └── *.jpg              # Product images (downloaded by scraper.py)
```

### Installed Structure (Ubuntu)

```
/
├── usr/
│   └── local/
│       └── bin/
│           ├── scraper.py              # Extraction script
│           ├── cleaner.py              # Cleaning script
│           └── api.py                  # API server
│
├── var/
│   └── lib/
│       └── ecommerceScraping/
│           ├── data/
│           │   ├── raw_data.csv        # Raw extracted data
│           │   └── cleaned_data.csv    # Cleaned data
│           └── images/                 # Downloaded product images
│
└── etc/
    └── systemd/
        └── system/
            └── ecommerce-scraping.service
```

---

## Design Decisions

### Why Separate Extraction, Cleaning, and Presentation?

| Module | Responsibility | Why Separated? |
|--------|----------------|----------------|
| scraper.py | Data extraction | Isolates website structure changes |
| cleaner.py | Data validation | Business logic independent of source |
| api.py | Data presentation | Swappable API layer |

> **Benefit:** If the website changes, only scraper.py needs modification.

### Why Preserve Raw Data?

- **Audit Trail:** Track what was originally extracted
- **Reprocessing:** Re-clean with new rules without re-scraping
- **Debugging:** Identify issues in cleaning logic
- **Respect for Source:** Minimize requests to target website

### Why /var/lib/ Instead of /home/?

Following the Linux FHS (Filesystem Hierarchy Standard):

| Path | Purpose |
|------|---------|
| `/var/lib/` | Variable data for applications |
| `/home/` | Human user directories |
| `/usr/local/bin/` | Locally installed executables |
| `/etc/systemd/system/` | System service definitions |

### Why FastAPI Over Flask?

| Feature | FastAPI | Flask |
|---------|---------|-------|
| Automatic Swagger Docs | ✅ Built-in | ❌ Requires extensions |
| Async Support | ✅ Native | ❌ Limited |
| Data Validation | ✅ Pydantic | ❌ Manual |
| Performance | ✅ High (ASGI) | 🟡 Medium (WSGI) |
| Type Hints | ✅ First-class | ❌ Not prioritized |

### Why host="0.0.0.0"?

Allows connections from:

- `localhost` (127.0.0.1)
- Local network (192.168.x.x, 172.x.x.x)
- External networks (with proper port forwarding)

This is the standard for services that need to be accessible beyond the local machine.

### Why Restart=always in systemd?

Ensures high availability:

- Service crashes → Automatic restart
- Server reboots → Service starts on boot
- Network issues → Recovers when network returns

---

## Data Schema

### Raw Data (raw_data.csv)

| Column | Type | Example | Description |
|--------|------|---------|-------------|
| id | int | 1 | Sequential product ID |
| name_raw | string | "Abominable Hoodie" | Original product name |
| price_raw | string | "$69.00" | Original price string |
| description_raw | string | "A warm..." | Original description |
| category_raw | string | "Hoodies" | Original category |
| sku_raw | string | "MH09" | Original SKU |
| stock_raw | string | "Out of stock" | Original stock status |
| image_url | string | "https://..." | Remote image URL |
| local_image_path | string | "/var/..." | Local image path |

### Cleaned Data (cleaned_data.csv)

| Column | Type | Example | Description |
|--------|------|---------|-------------|
| id | int | 1 | Sequential product ID |
| name | string | "Abominable Hoodie" | Cleaned name |
| price | float | 69.0 | Numeric price |
| price_level | string | "Premium" | Budget/Mid-range/Premium |
| description | string | "A warm..." | Cleaned description |
| category | string | "Hoodies" | Cleaned category |
| sku | string | "MH09" | Cleaned SKU |
| stock | string | "Out of stock" | Cleaned stock status |
| image_path | string | "/var/..." | Validated image path |

### Price Level Classification

| Level | Range | Examples |
|-------|-------|----------|
| Budget | < $30 | Water bottle ($7), Gym short ($20) |
| Mid-range | $30 - $60 | Running short ($40), Watch ($45) |
| Premium | > $60 | Hoodie ($69), Gym pant ($74) |

---

## Handwritten Analysis

The following documentation files provide in-depth analysis with ASCII diagrams:

- **ARCHITECTURE.md** - System architecture overview with component diagrams
- **DATA_FLOW.md** - Detailed data flow diagrams (DFD Level 1)
- **DEPLOYMENT.md** - Deployment and service initialization flow
- **MODULE_DEPENDENCIES.md** - Module relationship and dependency diagrams
- **DESIGN_JUSTIFICATION.md** - Design decisions and rationale

These files contain the same analysis that would be submitted as handwritten notes, formatted for GitHub rendering.

---

## Requirements

### Development

- Python 3.7+
- pip3
- Virtual environment (recommended)

### Production (Ubuntu)

- Ubuntu 20.04 or newer
- systemd
- ufw (optional, for firewall)

### Python Dependencies

```
requests>=2.31.0
beautifulsoup4>=4.12.3
pandas>=2.2.0
fastapi>=0.109.0
uvicorn>=0.27.0
```

---

## Author

**Waleed**

University Project - System Integration Course

Date: 2026

---

## License

This project is created for educational purposes as part of a university assignment demonstrating:

- Web scraping techniques
- Data pipeline architecture
- Linux service management
- Debian packaging

---

## Acknowledgments

- **ScrapingCourse.com** - Demo e-commerce site for testing
- **FastAPI** - Modern web framework
- **BeautifulSoup** - HTML parsing library

---

⭐ If you found this project useful, please give it a star on GitHub! ⭐
