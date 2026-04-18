"""
Web Scraper - Extraction Module
Responsibility: Fetch raw data from website and save as-is
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from urllib.parse import urljoin
import time

# ==================== SETTINGS ====================
BASE_URL = "https://www.scrapingcourse.com/ecommerce/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
IMAGES_DIR = "/var/lib/ecommerceScraping/images"
RAW_DATA_PATH = "/var/lib/ecommerceScraping/data/raw_data.csv"

# ==================== HELPER FUNCTIONS ====================

def create_directories():
    """Create necessary folders if they don't exist"""
    os.makedirs("data", exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    print("✓ Directories created: data/, images/")

def fetch_page(url):
    """Fetch HTML page from internet"""
    try:
        print(f"Fetching: {url}")
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching page: {e}")
        return None

def get_product_links(html):
    """Extract all product links from main page"""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    
    # Find all product items
    products = soup.find_all("li", class_="product")
    
    for product in products:
        link_elem = product.find("a", href=True)
        if link_elem:
            full_url = urljoin(BASE_URL, link_elem["href"])
            links.append(full_url)
    
    print(f"Found {len(links)} product links")
    return links

def extract_product_details(product_url, product_id):
    """Visit product page and extract all details"""
    html = fetch_page(product_url)
    if not html:
        return None
    
    soup = BeautifulSoup(html, "html.parser")
    
    try:
        # Product name
        name_elem = soup.find("h1", class_="product_title")
        name = name_elem.text.strip() if name_elem else "Unknown"
        
        # Price
        price_elem = soup.find("p", class_="price")
        if price_elem:
            amount = price_elem.find("span", class_="woocommerce-Price-amount")
            price = amount.text.strip() if amount else "N/A"
        else:
            price = "N/A"
        
        # Description
        desc_elem = soup.find("div", class_="woocommerce-product-details__short-description")
        description = desc_elem.text.strip() if desc_elem else ""
        
        # Category
        category_elem = soup.find("span", class_="posted_in")
        if category_elem:
            cat_links = category_elem.find_all("a")
            category = ", ".join([c.text.strip() for c in cat_links])
        else:
            category = "Uncategorized"
        
        # Image URL
        img_elem = soup.find("div", class_="woocommerce-product-gallery__image")
        if img_elem:
            img_tag = img_elem.find("img")
            img_url = img_tag.get("src") if img_tag else None
        else:
            img_url = None
        
        # Download image
        local_img_path = None
        if img_url:
            local_img_path = download_image(img_url, product_id, name)
        
        # SKU
        sku_elem = soup.find("span", class_="sku")
        sku = sku_elem.text.strip() if sku_elem else "N/A"
        
        # Stock status
        stock_elem = soup.find("p", class_="stock")
        stock = stock_elem.text.strip() if stock_elem else "In stock"
        
        product = {
            "id": product_id,
            "name_raw": name,
            "price_raw": price,
            "description_raw": description,
            "category_raw": category,
            "sku_raw": sku,
            "stock_raw": stock,
            "image_url": img_url,
            "local_image_path": local_img_path
        }
        
        return product
        
    except Exception as e:
        print(f"  Error extracting product {product_id}: {e}")
        return None

def download_image(img_url, product_id, product_name):
    """Download and save image locally"""
    try:
        # Get file extension
        ext = img_url.split(".")[-1].split("?")[0]
        if ext not in ["jpg", "jpeg", "png", "webp", "gif"]:
            ext = "jpg"
        
        # Create safe filename
        safe_name = "".join(c for c in product_name[:30] if c.isalnum() or c in (" ", "-", "_")).rstrip()
        safe_name = safe_name.replace(" ", "_")
        filename = f"{product_id}_{safe_name}.{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)
        
        # Download
        response = requests.get(img_url, headers=HEADERS, timeout=10)
        with open(filepath, "wb") as f:
            f.write(response.content)
        
        return filepath
        
    except Exception as e:
        print(f"    Image download failed: {e}")
        return None

def save_to_csv(products, filepath):
    """Save data to CSV file"""
    df = pd.DataFrame(products)
    df.to_csv(filepath, index=False, encoding="utf-8")
    print(f"✓ Saved {len(products)} products to: {filepath}")

# ==================== MAIN FUNCTION ====================

def main():
    print("=" * 50)
    print("WEB SCRAPING STARTED")
    print("=" * 50)
    
    # 1. Create directories
    create_directories()
    
    # 2. Fetch main page
    html = fetch_page(BASE_URL)
    if not html:
        print("Failed to fetch main page")
        return
    
    # 3. Get all product links
    product_links = get_product_links(html)
    
    # 4. Extract details from each product
    all_products = []
    for idx, link in enumerate(product_links, 1):
        print(f"\nProduct {idx}/{len(product_links)}")
        product = extract_product_details(link, idx)
        if product:
            all_products.append(product)
            print(f"  ✓ {product['name_raw'][:40]}... - {product['price_raw']}")
        
        # Be polite - small delay
        time.sleep(0.5)
    
    # 5. Save data
    save_to_csv(all_products, RAW_DATA_PATH)
    
    print("=" * 50)
    print(f"COMPLETED! {len(all_products)} products extracted")
    print(f"Raw data: {RAW_DATA_PATH}")
    print(f"Images: {IMAGES_DIR}/")
    print("=" * 50)

if __name__ == "__main__":
    main()
