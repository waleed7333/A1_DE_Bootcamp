"""
FastAPI Application
Responsibility: Serve cleaned data via REST API
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import pandas as pd
import os

# ==================== SETTINGS ====================
app = FastAPI(title="Web Scraping API", version="1.0.0")

CLEANED_DATA_PATH = "/var/lib/ecommerceScraping/data/cleaned_data.csv"
IMAGES_DIR = "/var/lib/ecommerceScraping/images"
# ==================== LOAD DATA ====================

def load_data():
    """Load data from CSV file"""
    if not os.path.exists(CLEANED_DATA_PATH):
        print(f"Warning: Data file not found: {CLEANED_DATA_PATH}")
        return pd.DataFrame()
    
    df = pd.read_csv(CLEANED_DATA_PATH, encoding="utf-8")
    print(f"Loaded {len(df)} products")
    return df

products_df = load_data()

# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    """Home page - API info"""
    return {
        "message": "Web Scraping API",
        "version": "1.0.0",
        "endpoints": {
            "/data": "Get all products",
            "/data/{product_id}": "Get single product",
            "/image/{product_id}": "Get product image",
            "/stats": "Get statistics"
        },
        "total_products": len(products_df)
    }

@app.get("/data")
async def get_all_products():
    """Return all products"""
    if products_df.empty:
        raise HTTPException(status_code=404, detail="No data available")
    
    return {
        "total": len(products_df),
        "products": products_df.to_dict(orient="records")
    }

@app.get("/data/{product_id}")
async def get_product(product_id: int):
    """Return single product by ID"""
    if products_df.empty:
        raise HTTPException(status_code=404, detail="No data available")
    
    product = products_df[products_df["id"] == product_id]
    
    if product.empty:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    return product.iloc[0].to_dict()

@app.get("/image/{product_id}")
async def get_image(product_id: int):
    """Return product image"""
    if products_df.empty:
        raise HTTPException(status_code=404, detail="No data available")
    
    product = products_df[products_df["id"] == product_id]
    
    if product.empty:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    img_path = product.iloc[0]["image_path"]
    
    if pd.isna(img_path) or not os.path.exists(str(img_path)):
        raise HTTPException(status_code=404, detail="Image not available")
    
    return FileResponse(str(img_path))

@app.get("/stats")
async def get_stats():
    """Return data statistics"""
    if products_df.empty:
        raise HTTPException(status_code=404, detail="No data available")
    
    return {
        "total_products": len(products_df),
        "categories": products_df["category"].unique().tolist(),
        "price_levels": products_df["price_level"].value_counts().to_dict(),
        "price_range": {
            "min": float(products_df["price"].min()) if products_df["price"].notna().any() else None,
            "max": float(products_df["price"].max()) if products_df["price"].notna().any() else None,
            "average": float(products_df["price"].mean()) if products_df["price"].notna().any() else None
        }
    }

# ==================== RUN ====================

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("STARTING FASTAPI SERVER")
    print("=" * 50)
    print(f"Products loaded: {len(products_df)}")
    print("Server: http://127.0.0.1:8000")
    print("Docs: http://127.0.0.1:8000/docs")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
