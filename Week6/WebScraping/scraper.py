import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import os

def scrape_books():
# Create required folders
    os.makedirs("./data/raw", exist_ok=True)
    os.makedirs("./images", exist_ok=True)
    
    raw_books = []
    current_page = 1
    url = f"https://books.toscrape.com/catalogue/page-{current_page}.html"
    
    while url and current_page <= 2:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        articles = soup.find_all('article', class_="product_pod")

        print(f"Page {current_page} scraping")

        for article in articles:
            name = article.h3.a['title']
            price = article.find('p', class_="price_color").text
            rating = article.find('p', class_="star-rating")['class'][1]

            img_src = article.find('img')['src']
            img_url = urljoin(url, img_src)

            img_content = requests.get(img_url).content
            
            # Clean filename
            clean_name = name[:50].replace(':', '').replace('/', '').replace('\\', '').replace('?', '')
            
            img_path = f'images/{clean_name}.jpg'
            with open(img_path, 'wb') as f:
                f.write(img_content)

            raw_books.append({
                "Name": name,
                "Price": price,
                "Rating": rating,
                "Img_Path": img_path,
            })
            
        print(f"Page {current_page} scraped")
        next_btn = soup.find('li', class_="next")
        url = urljoin(url, next_btn.a['href']) if next_btn else None
        current_page += 1

    df = pd.DataFrame(raw_books)
    df.to_csv("./data/raw/books_raw.csv", index=False)
    print("Scraping complete - Raw data saved to data/raw/books_raw.csv")
    
    return df