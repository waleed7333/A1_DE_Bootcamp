import os
import sys

def main():
    print("=" * 50)
    print("WEB SCRAPING PROJECT")
    print("=" * 50)
    
    try:
# Import modules
        from scraper import scrape_books
        from processor import process_data
        from organizer import organize_data
        
# Step 1: Scrape data
        print("\n📚 STEP 1: Scraping books data...")
        print("-" * 30)
        scrape_books()
        
# Step 2: Process and clean data
        print("\n🧹 STEP 2: Processing and cleaning data...")
        print("-" * 30)
        process_data()
        
# Step 3: Organize data by rating
        print("\n📁 STEP 3: Organizing data by rating...")
        print("-" * 30)
        organize_data()
        
        print("\n" + "=" * 50)
        print("✅ ALL OPERATIONS COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        
# Display summary of generated files
        print("\n📊 Generated Files:")
        print("-" * 30)
        print("Raw data: data/raw/books_raw.csv")
        print("Clean data: data/processed/books_clean.csv")
        print("Rating files: data/processed/rating_1_star.csv ~ rating_5_star.csv")
        print("Images: images/rating_1/ ~ images/rating_5/")
        
    except Exception as e:
        print(f"\n❌ Error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()