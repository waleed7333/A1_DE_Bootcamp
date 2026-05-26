"""
Data Cleaner Module
Responsibility: Clean raw data and validate
"""

import pandas as pd
import os
import re

# ==================== SETTINGS ====================
RAW_DATA_PATH = "/var/lib/ecommerceScraping/data/raw_data.csv"
CLEANED_DATA_PATH = "/var/lib/ecommerceScraping/data/cleaned_data.csv"

# ==================== CLEANING FUNCTIONS ====================

def clean_price(price_str):
    """Convert price string to float"""
    if pd.isna(price_str) or price_str == "N/A":
        return None
    
    # Remove currency symbols and letters
    cleaned = re.sub(r"[^\d.]", "", str(price_str))
    
    try:
        return float(cleaned)
    except:
        return None

def clean_text(text):
    """Clean text - remove extra spaces"""
    if pd.isna(text):
        return ""
    return " ".join(str(text).split())

def get_price_level(price):
    """Categorize price"""
    if price is None:
        return "Unknown"
    elif price < 30:
        return "Budget"
    elif price < 60:
        return "Mid-range"
    else:
        return "Premium"

def validate_image_path(path):
    """Check if image file exists"""
    if pd.isna(path) or path is None:
        return None
    if os.path.exists(str(path)):
        return path
    return None

# ==================== MAIN FUNCTION ====================

def main():
    print("=" * 50)
    print("DATA CLEANING STARTED")
    print("=" * 50)
    
    # 1. Check if raw data exists
    if not os.path.exists(RAW_DATA_PATH):
        print(f"ERROR: Raw data not found: {RAW_DATA_PATH}")
        print("Run scraper.py first")
        return
    
    # 2. Read raw data
    df = pd.read_csv(RAW_DATA_PATH, encoding="utf-8")
    print(f"Loaded {len(df)} products")
    
    # 3. Create clean dataframe
    clean_df = pd.DataFrame()
    
    clean_df["id"] = df["id"]
    clean_df["name"] = df["name_raw"].apply(clean_text)
    clean_df["price"] = df["price_raw"].apply(clean_price)
    clean_df["price_level"] = clean_df["price"].apply(get_price_level)
    clean_df["description"] = df["description_raw"].apply(clean_text)
    clean_df["category"] = df["category_raw"].apply(clean_text)
    clean_df["sku"] = df["sku_raw"].apply(clean_text)
    clean_df["stock"] = df["stock_raw"].apply(clean_text)
    clean_df["image_path"] = df["local_image_path"].apply(validate_image_path)
    
    # 4. Statistics
    print("\nCleaning Statistics:")
    print(f"  Products with price: {clean_df['price'].notna().sum()}")
    print(f"  Products with image: {clean_df['image_path'].notna().sum()}")
    print(f"  Price distribution:")
    for level in ["Budget", "Mid-range", "Premium", "Unknown"]:
        count = (clean_df["price_level"] == level).sum()
        print(f"    - {level}: {count}")
    
    # 5. Save clean data
    clean_df.to_csv(CLEANED_DATA_PATH, index=False, encoding="utf-8")
    
    print("=" * 50)
    print(f"COMPLETED! Clean data saved to: {CLEANED_DATA_PATH}")
    print("=" * 50)
    
    # 6. Show sample
    print("\nSample data:")
    print(clean_df[["id", "name", "price", "price_level"]].head(10).to_string(index=False))

if __name__ == "__main__":
    main()
