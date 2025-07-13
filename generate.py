import requests
from bs4 import BeautifulSoup
from datetime import datetime

def get_tomorrows_papers_front_pages():
    """Scrape front page images from Tomorrow's Papers Today"""
    url = "https://www.tomorrowspapers.co.uk/"
    
    # Headers to avoid 403 blocking
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        
        items = []
        
        # Look for images in the front pages section
        # Try different selectors that might contain the front page images
        img_selectors = [
            "img[src*='front']",  # Images with 'front' in src
            "img[alt*='front']",  # Images with 'front' in alt text
            "img[alt*='newspaper']",  # Images with 'newspaper' in alt
            ".front-page img",  # Images in elements with front-page class
            "article img",  # Images in article elements
            "main img",  # Images in main content
            "img"  # Fallback to all images
        ]
        
        for selector in img_selectors:
            images = soup.select(selector)
            for img in images:
                src = img.get("src") or img.get("data-src")
                if not src:
                    continue
                    
                # Convert relative URLs to absolute
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = "https://www.tomorrowspapers.co.uk" + src
                elif not src.startswith("http"):
                    continue
                
                # Skip very small images (likely logos/icons)
                width = img.get("width")
                height = img.get("height")
                if width and height:
                    try:
                        if int(width) < 100 or int(height) < 100:
                            continue
                    except ValueError:
                        pass
                
                alt = img.get("alt", "Newspaper Front Page")
                
                # Skip images that are clearly not front pages
                if any(skip_word in src.lower() for skip_word in ['logo', 'icon', 'avatar', 'profile']):
                    continue
                if any(skip_word in alt.lower() for skip_word in ['logo', 'icon', 'avatar', 'profile']):
                    continue
                
                items.append((alt, src))
                
                if len(items) >= 10:  # Get up to 10 images
                    break
            
            if items:  # If we found images with this selector, stop trying others
                break
        
        return items
        
    except requests.RequestException as e:
        print(f"Error fetching Newsworks page: {e}")
        return []

def generate_rss(items, source_url):
    """Generate RSS feed from front page items"""
    rss_items = ""
    for title, img_url in items:
        # Escape XML special characters in title
        title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        rss_items += f"""
        <item>
          <title>{title}</title>
          <link>{img_url}</link>
          <description><![CDATA[<img src="{img_url}" alt="{title}" />]]></description>
          <guid>{img_url}</guid>
          <pubDate>{datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")}</pubDate>
        </item>
        """

    rss_feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>UK Newspaper Front Pages - Tomorrow's Papers Today</title>
    <link>{source_url}</link>
    <description>Daily UK newspaper front pages from Tomorrow's Papers Today</description>
    <lastBuildDate>{datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
    <language>en-GB</language>
    {rss_items}
  </channel>
</rss>
"""
    return rss_feed

def main():
    """Main function to scrape and generate RSS"""
    source_url = "https://www.tomorrowspapers.co.uk/"
    
    print("Scraping front pages from Tomorrow's Papers Today...")
    items = get_tomorrows_papers_front_pages()
    
    if not items:
        print("No front page images found.")
        return
    
    print(f"Found {len(items)} front page images:")
    for title, url in items:
        print(f"  - {title}")
    
    rss_xml = generate_rss(items, source_url)
    
    with open("tomorrows_papers_front_pages.xml", "w", encoding="utf-8") as f:
        f.write(rss_xml)
    
    print("RSS feed generated as 'tomorrows_papers_front_pages.xml'")

if __name__ == "__main__":
    main()
