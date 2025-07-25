import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import json # <-- Added import for JSON handling
import re   # <-- Added import for regex

def get_tomorrows_papers_front_pages():
    """Scrape front page images from Tomorrow's Papers Today"""
    url = "https://www.tomorrowspapers.co.uk/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        
        items = []
        
        # This selector targets the specific divs containing the paper images
        paper_divs = soup.select("div.td-module-thumb")

        for div in paper_divs:
            img = div.find("img")
            if not img:
                continue

            src = img.get("src") or img.get("data-src")
            if not src:
                continue
                
            # Convert relative URLs to absolute
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = "https://www.tomorrowspapers.co.uk" + src
            
            # Use the image's alt text for the title
            alt = img.get("alt", "").strip()

            # Skip images that are clearly not front pages
            if any(skip_word in src.lower() for skip_word in ['logo', 'icon', 'avatar', 'profile', 'placeholder']):
                continue
            if not alt or any(skip_word in alt.lower() for skip_word in ['logo', 'icon', 'avatar', 'profile']):
                continue

            # Avoid duplicates
            if not any(item[1] == src for item in items):
                 items.append((alt, src))

            if len(items) >= 12: # Limit to a reasonable number
                break
        
        return items
        
    except requests.RequestException as e:
        print(f"Error fetching page: {e}")
        return []

def generate_rss(items, source_url):
    """Generate RSS feed from front page items"""
    rss_items = ""
    pub_date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    for title, img_url in items:
        # Escape XML special characters in title
        title = title.replace("&", "&").replace("<", "<").replace(">", ">")
        
        rss_items += f"""
        <item>
          <title>{title}</title>
          <link>{img_url}</link>
          <description><![CDATA[<img src="{img_url}" alt="{title}" />]]></description>
          <guid>{img_url}</guid>
          <pubDate>{pub_date_str}</pubDate>
        </item>
        """

    rss_feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>UK Newspaper Front Pages - Tomorrow's Papers Today</title>
    <link>{source_url}</link>
    <description>Daily UK newspaper front pages from Tomorrow's Papers Today</description>
    <lastBuildDate>{pub_date_str}</lastBuildDate>
    <language>en-GB</language>
    {rss_items}
  </channel>
</rss>
"""
    return rss_feed

# --- NEW FUNCTION TO GENERATE JSON ---
def generate_json(items, source_url, rss_feed_url):
    """Generate JSON feed from front page items in the specified format."""
    
    # Get the current time for the publication date
    pub_date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    # Build the main dictionary structure
    output_dict = {
        "status": "ok",
        "feed": {
            "url": rss_feed_url,
            "title": "UK Newspaper Front Pages - Tomorrow's Papers Today",
            "link": source_url,
            "author": "",
            "description": "Daily UK newspaper front pages from Tomorrow's Papers Today",
            "image": ""
        },
        "items": []
    }

    # Create a dictionary for each item and add it to the list
    for title, img_url in items:
        image_html = f'<img src="{img_url}" alt="{title}">'
        
        item_dict = {
            "title": title,
            "pubDate": pub_date_str,
            "link": img_url,
            "guid": img_url,
            "author": "",
            "thumbnail": "",
            "description": image_html,
            "content": image_html,
            "enclosure": {},
            "categories": []
        }
        output_dict["items"].append(item_dict)

    return output_dict

def main():
    """Main function to scrape and generate RSS and JSON feeds"""
    source_url = "https://www.tomorrowspapers.co.uk/"
    # The URL where your GitHub pages RSS feed is/will be hosted
    rss_feed_url = "https://lak7474.github.io/skynews-frontpages/rss.xml" 
    
    print("Scraping front pages from Tomorrow's Papers Today...")
    items = get_tomorrows_papers_front_pages()
    
    if not items:
        print("No front page images found.")
        return
    
    print(f"Found {len(items)} front page images:")
    for title, url in items:
        print(f"  - {title}")
    
    # --- Generate and save RSS feed ---
    rss_xml = generate_rss(items, source_url)
    with open("rss.xml", "w", encoding="utf-8") as f:
        f.write(rss_xml)
    print("RSS feed generated as 'rss.xml'")

    # --- Generate and save JSON feed ---
    json_data = generate_json(items, source_url, rss_feed_url)
    # Use json.dump() to write the dictionary to a file
    with open("frontpages.json", "w", encoding="utf-8") as f:
        # indent=2 makes the file human-readable
        # ensure_ascii=False allows for proper character encoding
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print("JSON feed generated as 'frontpages.json'")

if __name__ == "__main__":
    main()
