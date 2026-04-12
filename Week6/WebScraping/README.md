# Book Scraper Project

## Overview
This project scrapes book data (title, price, rating, image) from books.toscrape.com, processes and cleans the data, and organizes it by rating stars.

## Project Structure
```
WebScraping/
├── main.py              # Main orchestrator
├── scraper.py           # Scrapes data and images
├── processor.py         # Cleans raw data
├── organizer.py         # Organizes by rating
├── requirements.txt     # Dependencies
├── data/                # Raw and processed CSV files
└── images/              # Book cover images organized by rating
```

## Setup
1. Create virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run:
   ```
   python main.py
   ```

## Output
- Raw data: `data/raw/books_raw.csv`
- Clean data: `data/processed/books_clean.csv`
- Rating CSVs: `data/processed/rating_X_star.csv`
- Images: `images/rating_X/`

## Features
- Scrapes first 2 pages (20 books)
- Downloads book images
- Cleans price (removes Â£ symbol, to float), converts rating to int
- Removes duplicates/NaNs
- Organizes into rating folders (1-5 stars)

