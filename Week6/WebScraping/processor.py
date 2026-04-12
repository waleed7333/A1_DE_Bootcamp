import pandas as pd
import os

def process_data():
    print("Starting data processing...")
    
# Read raw data
    raw_df = pd.read_csv("./data/raw/books_raw.csv")
    
# Create copy for cleaning
    df = raw_df.copy()
    
# Clean price - remove pound symbol and convert to float
    df['Price'] = df['Price'].str.replace('Â£', '').astype(float)
    
# Convert rating from text to numbers
    rating_map = {
        'One': 1,
        'Two': 2,
        'Three': 3,
        'Four': 4,
        'Five': 5
    }
    df['Rating'] = df['Rating'].map(rating_map)
    
# Remove duplicate rows
    df = df.drop_duplicates()
    
# Remove rows with missing values
    df = df.dropna()
    
# Create processed folder if not exists
    os.makedirs("./data/processed", exist_ok=True)
    
# Save clean data
    df.to_csv("./data/processed/books_clean.csv", index=False)
    print("Processing complete - Clean data saved to data/processed/books_clean.csv")
    
    return df