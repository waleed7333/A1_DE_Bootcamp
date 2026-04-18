# Deployment Architecture & Service Flow

## Overview

This document explains how the Python scripts are transformed into a deployable Debian package and how the service initializes on Ubuntu.

---

## Deployment Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        DEPLOYMENT ARCHITECTURE & SERVICE FLOW                           │
│                             From .deb Package to Running Service                        │
└─────────────────────────────────────────────────────────────────────────────────────────┘

╔══════════════════════════════╗
║         BUILD PHASE          ║
║     (Developer Machine)      ║
╚══════════════════════════════╝
            │
            ▼
┌────────────────────────────────────────────────────┐
│           BUILD DIRECTORY STRUCTURE                │
│                                                    │
│    ecommerceScraping_deb/                         │
│    ├── DEBIAN/                                    │
│    │   ├── control (Package metadata)             │
│    │   └── postinst (Post-install script)        │
│    ├── usr/                                      │
│    │   └── local/                                │
│    │       └── bin/                              │
│    │           ├── scraper.py (Extraction)       │
│    │           ├── cleaner.py (Cleaning)         │
│    │           └── api.py (API Server)           │
│    └── etc/                                      │
│        └── systemd/                              │
│            └── system/                           │
│                └── ecommerce-scraping.service    │
└────────────────────────────────────────────────────┘
            │
            │ dpkg-deb --build
            ▼
┌─────────────────────┐
│                     │
│  ecommercescraping  │
│     -1.0.0.deb      │
│                     │
│  (Debian Package)   │
└──────────┬──────────┘
           │
           │ ① dpkg -i package.deb
           ▼
╔═══════════════════════════════════════════════════════════════════════════════════════╗
║                              INSTALLATION PHASE                                       ║
║                             (Target Ubuntu Server)                                    ║
╚═══════════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              STEP 1: FILE EXTRACTION         │
│                                                                                     │
│   dpkg extracts files to system locations:                                          │
│                                                                                     │
│   Package Path → System Path                                                         │
│   ═══════════════════════════════════════════════════════════════════════════════   │
│   /usr/local/bin/scraper.py    → /usr/local/bin/scraper.py                         │
│   /usr/local/bin/cleaner.py    → /usr/local/bin/cleaner.py                         │
│   /usr/local/bin/api.py        → /usr/local/bin/api.py                             │
│   /etc/systemd/system/ecommerce-... → /etc/systemd/system/ecommerce-...            │
│                                                                                     │
│   Permissions: chmod 755 (executable) applied                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
           │
           │ ② Files extracted
           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              STEP 2: DEPENDENCY CHECK        │
│                                                                                     │
│   dpkg reads DEBIAN/control:                                                        │
│                                                                                     │
│   Depends: python3, python3-pip, python3-requests, python3-bs4, python3-pandas       │
│                                                                                     │
│   If missing → apt install -y [missing packages]                                   │
│                                                                                     │
│   ✓ python3 (already installed)                                                     │
│   ✓ python3-pip (already installed)                                                  │
│   ✓ python3-requests (installed via apt)                                            │
│   ✓ python3-bs4 (installed via apt)                                                  │
│   ✓ python3-pandas (installed via apt)                                               │
└─────────────────────────────────────────────────────────────────────────────────────┘
           │
           │ ③ Dependencies satisfied
           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          STEP 3: POST-INSTALLATION SCRIPT                           │
│                          (Executes DEBIAN/postinst)                                 │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │  #!/bin/bash                                                               │  │
│  │  set -e                                                                    │  │
│  │                                                                            │  │
│  │  # 3.1 Create data directories                                             │  │
│  │  mkdir -p /var/lib/ecommerceScraping/data                                  │  │
│  │  mkdir -p /var/lib/ecommerceScraping/images                                │  │
│  │  chmod -R 755 /var/lib/ecommerceScraping                                   │  │
│  │                                                                            │  │
│  │  # 3.2 Install Python packages (not in apt)                               │  │
│  │  pip3 install --break-system-packages fastapi uvicorn || true              │  │
│  │                                                                            │  │
│  │  # 3.3 Initial data extraction                                             │  │
│  │  echo "Running initial data extraction..."                                 │  │
│  │  python3 /usr/local/bin/scraper.py || true                                 │  │
│  │  echo "Cleaning data..."                                                   │  │
│  │  python3 /usr/local/bin/cleaner.py || true                                 │  │
│  │                                                                            │  │
│  │  # 3.4 Enable and start service                                           │  │
│  │  systemctl enable ecommerce-scraping.service                              │  │
│  │  systemctl start ecommerce-scraping.service                               │  │
│  │                                                                            │  │
│  │  # 3.5 Open firewall port                                                 │  │
│  │  ufw allow 8000 || true                                                   │  │
│  │                                                                            │  │
│  │  echo "Installation complete!"                                             │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
           │
           │ ④ Service registered
           ▼
╔═══════════════════════════════════════════════════════════════════════════════════════╗
║                                RUNTIME PHASE                                           ║
║                          (System Boot & Operation)                                    ║
╚═══════════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               SYSTEM BOOT SEQUENCE            │
│                                                                                     │
│  ┌─────────────┐                                                               │
│  │   Kernel    │  Linux kernel initializes                                     │
│  │    Boots    │                                                               │
│  └──────┬──────┘                                                               │
│         │                                                                      │
│         ▼                                                                      │
│  ┌─────────────┐                                                               │
│  │   systemd   │  Init system starts (PID 1)                                  │
│  │    Starts   │                                                               │
│  └──────┬──────┘                                                               │
│         │                                                                      │
│         │  Reads all service files from:                                       │
│         │  /etc/systemd/system/                                                │
│         │  /lib/systemd/system/                                                │
│         │                                                                      │
│         ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                      ecommerce-scraping.service                             │  │
│  │                                                                            │  │
│  │  [Unit]                                                                    │  │
│  │  Description=E-commerce Web Scraping API Service                          │  │
│  │  After=network.target  ← Wait for network                                 │  │
│  │                                                                            │  │
│  │  [Service]                                                                 │  │
│  │  Type=simple  ← Simple foreground process                                 │  │
│  │  User=root  ← Run with root privileges                                    │  │
│  │  WorkingDirectory=/var/lib/ecommerceScraping                              │  │
│  │  ExecStart=/usr/bin/python3 /usr/local/bin/api.py                         │  │
│  │  Restart=always  ← Auto-restart on failure                                │  │
│  │  RestartSec=5  ← Wait 5s before restart                                   │  │
│  │                                                                            │  │
│  │  [Install]                                                                 │  │
│  │  WantedBy=multi-user.target  ← Start with normal system state             │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  Because we ran:                                                                   │
│  systemctl enable ecommerce-scraping.service                                       │
│                                                                                     │
│  A symlink is created:                                                              │
│  /etc/systemd/system/multi-user.target.wants/ecommerce-scraping.service              │
│  → /etc/systemd/system/ecommerce-scraping.service                                     │
│                                                                                     │
│  This tells systemd to start the service automatically on boot.                    │
└─────────────────────────────────────────────────────────────────────────────────────┘
           │
           │ ⑤ Service started
           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               SERVICE RUNNING STATE                                  │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                          FastAPI Application                                │  │
│  │                                                                            │  │
│  │  Process: python3 /usr/local/bin/api.py                                   │  │
│  │  PID: 39726                                                               │  │
│  │  User: root                                                               │  │
│  │                                                                            │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐   │  │
│  │  │                        Uvicorn ASGI Server                         │   │  │
│  │  │                        ═══════════════════                          │   │  │
│  │  │  • Listening: 0.0.0.0:8000                                          │   │  │
│  │  │  • Workers: 1                                                        │   │  │
│  │  │  • Loaded products: 16                                              │   │  │
│  │  │  • Memory: ~60MB                                                    │   │  │
│  │  └─────────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                            │  │
│  │  Endpoints Available:                                                      │  │
│  │  • GET /           → API information                                      │  │
│  │  • GET /data       → All products                                        │  │
│  │  • GET /data/{id}  → Single product                                      │  │
│  │  • GET /image/{id} → Product image                                      │  │
│  │  • GET /stats      → Statistics                                          │  │
│  │  • GET /docs       → Swagger UI                                          │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                         Firewall Configuration                             │  │
│  │                                                                            │  │
│  │  Command: ufw allow 8000                                                   │  │
│  │                                                                            │  │
│  │  Status:                                                                   │  │
│  │  ┌──────────────────────────────────────────────────────────────────────┐ │  │
│  │  │  To      Action  From                                                 │ │  │
│  │  │  --      ------  ----                                                 │ │  │
│  │  │  8000    ALLOW   Anywhere                                            │ │  │
│  │  │  8000    ALLOW   Anywhere (v6)                                       │ │  │
│  │  └──────────────────────────────────────────────────────────────────────┘ │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                          Auto-Restart Behavior                              │  │
│  │                                                                            │  │
│  │  If the service crashes or is killed:                                     │  │
│  │                                                                            │  │
│  │  1. systemd detects process exit (code != 0)                              │  │
│  │  2. Waits 5 seconds (RestartSec=5)                                        │  │
│  │  3. Executes /usr/bin/python3 /usr/local/bin/api.py again                │  │
│  │  4. Increments restart counter                                            │  │
│  │                                                                            │  │
│  │  This ensures HIGH AVAILABILITY of the API service.                       │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
           │
           │ ⑥ HTTP Request received
           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                 CLIENT ACCESS                                        │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                            Access Methods                                   │  │
│  │                                                                            │  │
│  │  From same machine:                                                        │  │
│  │  $ curl http://localhost:8000/data                                         │  │
│  │  $ curl http://127.0.0.1:8000/stats                                        │  │
│  │                                                                            │  │
│  │  From local network:                                                       │  │
│  │  http://172.26.119.44:8000/docs                                            │  │
│  │  http://192.168.1.100:8000/data                                           │  │
│  │                                                                            │  │
│  │  From browser (Swagger UI):                                                │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │               E-commerce Web Scraping API                          │  │  │
│  │  │               ══════════════════════════════                      │  │  │
│  │  │                     │                                              │  │  │
│  │  │      GET /data      →  Get all products                            │  │  │
│  │  │      GET /data/{id} →  Get single product                          │  │  │
│  │  │      GET /image/{id} → Get product image                           │  │  │
│  │  │      GET /stats     →  Get statistics                               │  │  │
│  │  │                     │                                              │  │  │
│  │  │         [ Try it out ]  [ Execute ]                                  │  │  │
│  │  └─────────────────────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Service Management Commands

| Command | Purpose |
|---------|---------|
| `sudo systemctl status ecommerce-scraping` | Check service health |
| `sudo systemctl start ecommerce-scraping` | Start service |
| `sudo systemctl stop ecommerce-scraping` | Stop service |
| `sudo systemctl restart ecommerce-scraping` | Restart service |
| `sudo systemctl enable ecommerce-scraping` | Enable auto-start on boot |
| `sudo systemctl disable ecommerce-scraping` | Disable auto-start |
| `sudo journalctl -u ecommerce-scraping -f` | View live logs |

---

## Uninstallation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        UNINSTALLATION                           │
│                                                                  │
│  1. sudo systemctl stop ecommerce-scraping                      │
│     → Stops the running service                                  │
│                                                                  │
│  2. sudo systemctl disable ecommerce-scraping                   │
│     → Removes auto-start symlink                                 │
│                                                                  │
│  3. sudo dpkg -r ecommercescraping                              │
│     → Removes package files                                     │
│                                                                  │
│  4. sudo rm -rf /var/lib/ecommerceScraping (optional)            │
│     → Removes scraped data                                       │
│                                                                  │
│  5. sudo ufw delete allow 8000 (optional)                       │
│     → Closes firewall port                                      │
└─────────────────────────────────────────────────────────────────┘
```