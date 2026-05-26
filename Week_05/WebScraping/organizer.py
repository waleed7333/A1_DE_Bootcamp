import pandas as pd
import os
import shutil

def organize_data():
    print("Starting data organization...")
    
# Read clean data
    df = pd.read_csv("./data/processed/books_clean.csv")
    
# Get all unique ratings
    ratings = sorted(df['Rating'].unique())
    
# Create folders for each rating
    for rating in ratings:
# Image folders
        os.makedirs(f"./images/rating_{rating}", exist_ok=True)
        
# Data folders
        os.makedirs(f"./data/processed", exist_ok=True)
    
# Classify data and images by rating
    for rating in ratings:
# Filter data by rating
        rating_df = df[df['Rating'] == rating]
        
# Save rating-specific CSV file
        rating_df.to_csv(f"./data/processed/rating_{rating}_star.csv", index=False)
        print(f"Created rating_{rating}_star.csv with {len(rating_df)} books")
        
# Move images to appropriate folder
        for _, row in rating_df.iterrows():
            img_source = row['Img_Path']
            if os.path.exists(img_source):
# Extract filename from path
                img_filename = os.path.basename(img_source)
                img_dest = f"./images/rating_{rating}/{img_filename}"
                
# Copy image to new folder
                shutil.move(img_source, img_dest)
        
        print(f"Organized {len(rating_df)} images for rating {rating}")
    
    print("Organization complete!")
    print("\nSummary:")
    for rating in ratings:
        count = len(df[df['Rating'] == rating])
        print(f"Rating {rating} star(s): {count} books")

if __name__ == "__main__":
    organize_data()