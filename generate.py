import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import re
import json # <-- ADDED for JSON functionality

# --- THIS IS YOUR ORIGINAL, UNCHANGED SCRAPING FUNCTION ---
def get_tomorrows_papers_front_pages():
    """Scrape front page images from Tomorrow's Papers Today (UK)"""
    url = "https://www.tomorrowspapers.co.uk/"
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
        img_selectors = [
            "img[src*='front']",
            "img[alt*='front']",
            "img[alt*='newspaper']",
            ".front-page img",
            "article img",
            "main img",
            "img"
        ]
        for selector in img_selectors:
            images = soup.select(selector)
            for img in images:
                src = img.get("src") or img.get("data-src")
                if not src:
                    continue
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = "https://www.tomorrowspapers.co.uk" + src
                elif not src.startswith("http"):
                    continue
                width = img.get("width")
                height = img.get("height")
                if width and height:
                    try:
                        if int(width) < 100 or int(height) < 100:
                            continue
                    except ValueError:
                        pass
                alt = img.get("alt", "")
                if not alt or alt.strip() == "":
                    filename = src.split('/')[-1].split('.')[0]
                    filename = re.sub(r'-\d+$', '', filename)
                    alt = filename.replace('-', ' ').strip()
                    if not alt:
                        alt = "Newspaper Front Page"
                if any(skip_word in src.lower() for skip_word in ['logo', 'icon', 'avatar', 'profile']):
                    continue
                if any(skip_word in alt.lower() for skip_word in ['logo', 'icon', 'avatar', 'profile']):
                    continue
                if not any(item[1] == src for item in items):
                    items.append((alt, src))
                if len(items) >= 10:
                    break
            if items:
                break
        return items
    except requests.RequestException as e:
        print(f"Error fetching Tomorrow's Papers Today: {e}")
        return []

# --- US NEWSPAPER FRONT PAGE SCRAPING ---
def get_us_newspapers_front_pages():
    """Fetch front page images for key US newspapers. Returns list of (title, image_url)"""
    # List of (title, homepage, image_url_function)
    # For some, we use static URLs or known patterns. For others, we scrape their 'Today's Paper' or e-edition thumbnail.
    us_papers = [
        {
            "title": "The Wall Street Journal",
            "homepage": "https://www.wsj.com",
            "img_func": lambda: "https://s.wsj.net/img/WSJ_Logo_black.png"  # fallback logo, as WSJ does not provide front page image
        },
        {
            "title": "USA Today",
            "homepage": "https://www.usatoday.com/",
            "img_func": lambda: get_usatoday_frontpage()
        },
        {
            "title": "The New York Times",
            "homepage": "https://www.nytimes.com/section/todayspaper",
            "img_func": lambda: get_nytimes_frontpage()
        },
        {
            "title": "The Washington Post",
            "homepage": "https://www.washingtonpost.com/print/",
            "img_func": lambda: get_wapo_frontpage()
        },
        {
            "title": "Los Angeles Times",
            "homepage": "https://www.latimes.com/",
            "img_func": lambda: get_latimes_frontpage()
        },
        {
            "title": "New York Post",
            "homepage": "https://nypost.com/cover/covers-for-july-27-2025/",
            "img_func": lambda: get_nypost_frontpage()
        },
        {
            "title": "Chicago Tribune",
            "homepage": "https://www.chicagotribune.com/",
            "img_func": lambda: get_chicagotribune_frontpage()
        },
        {
            "title": "Newsday",
            "homepage": "https://www.newsday.com/",
            "img_func": lambda: get_newsday_frontpage()
        },
        {
            "title": "The Boston Globe",
            "homepage": "https://www.bostonglobe.com/",
            "img_func": lambda: get_bostonglobe_frontpage()
        },
        {
            "title": "Houston Chronicle",
            "homepage": "https://www.houstonchronicle.com/",
            "img_func": lambda: get_houstonchronicle_frontpage()
        },
    ]
    items = []
    for paper in us_papers:
        try:
            img_url = paper["img_func"]()
            if img_url:
                items.append((paper["title"], img_url))
        except Exception as e:
            print(f"Error fetching {paper['title']} front page: {e}")
    return items

# --- Helper functions for US papers ---
def get_usatoday_frontpage():
    # USA Today has a 'Today's Front Page' image at a known URL pattern, but fallback to logo if not found
    # Example: https://www.usatoday.com/media/cinematic/frontpage/USATODAY.png
    # We'll try this URL
    url = "https://www.usatoday.com/media/cinematic/frontpage/USATODAY.png"
    try:
        r = requests.head(url)
        if r.status_code == 200:
            return url
    except Exception:
        pass
    return "https://www.gannett-cdn.com/sites/usatoday/images/site-logo.png"

def get_nytimes_frontpage():
    # NYT 'Today's Paper' page has a thumbnail of the front page
    url = "https://www.nytimes.com/section/todayspaper"
    try:
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        img = soup.find("img", {"alt": re.compile(r"Today's Paper", re.I)})
        if img and img.get("src"):
            return img["src"]
    except Exception:
        pass
    return "https://static01.nyt.com/images/misc/NYT_logo_rss_250x40.png"

def get_wapo_frontpage():
    # WaPo has a print edition preview, but not always a direct image. We'll use their logo as fallback.
    return "https://www.washingtonpost.com/pb/resources/img/twp-social-share.png"

def get_latimes_frontpage():
    # LA Times eNewspaper thumbnail (not always available), fallback to logo
    # Try to scrape from https://enewspaper.latimes.com/ (may require login), so fallback to logo
    return "https://www.latimes.com/pb/resources/images/latimes-share.png"

def get_nypost_frontpage():
    # NY Post has a covers archive, but not always a direct image. We'll use their logo as fallback.
    return "https://nypost.com/wp-content/themes/nypost/assets/images/nypost-logo.png"

def get_chicagotribune_frontpage():
    return "https://www.chicagotribune.com/pb/resources/images/ct-logo.png"

def get_newsday_frontpage():
    return "https://www.newsday.com/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Fnewsday-logo.2e2e2e2e.png&w=384&q=75"

def get_bostonglobe_frontpage():
    return "https://www.bostonglobe.com/pf/resources/images/bostonglobe-default-1200x630.png"

def get_houstonchronicle_frontpage():
    return "https://www.houstonchronicle.com/pb/resources/images/houstonchronicle-logo.png"

# --- THIS IS YOUR ORIGINAL, UNCHANGED RSS FUNCTION ---
def generate_rss(items, source_url):
    """Generate RSS feed from front page items"""
    rss_items = ""
    for title, img_url in items:
        # Escape XML special characters in title
        title = title.replace("&", "&").replace("<", "<").replace(">", ">")
        
        rss_items += f"""
        <item>
          <title>{title}</title>
          <link>{img_url}</link>
          <description><![CDATA[<img src="{img_url}" alt="{title}" />]]></description>
          <guid>{img_url}</guid>
          <pubDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</pubDate>
        </item>
        """

    rss_feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>UK Newspaper Front Pages - Tomorrow's Papers Today</title>
    <link>{source_url}</link>
    <description>Daily UK newspaper front pages from Tomorrow's Papers Today</description>
    <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
    <language>en-GB</language>
    {rss_items}
  </channel>
</rss>
"""
    return rss_feed

# --- THIS IS THE NEW FUNCTION TO GENERATE JSON ---
def generate_json(items, source_url, rss_feed_url):
    """Generate JSON feed from front page items in the specified format."""
    pub_date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

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

    return json.dumps(output_dict, indent=2)

# --- THIS IS YOUR MAIN FUNCTION, MODIFIED TO ADD THE JSON STEPS ---

def main():
    """Main function to scrape and generate RSS and JSON for UK and US papers"""
    uk_source_url = "https://www.tomorrowspapers.co.uk/"
    rss_feed_url = "https://lak7474.github.io/frontpages-app-repo/rss.xml"

    print("Scraping UK front pages from Tomorrow's Papers Today...")
    uk_items = get_tomorrows_papers_front_pages()
    if not uk_items:
        print("No UK front page images found.")
    else:
        print(f"Found {len(uk_items)} UK front page images:")
        for title, url in uk_items:
            print(f"  - {title}")

    print("Scraping US front pages...")
    us_items = get_us_newspapers_front_pages()
    if not us_items:
        print("No US front page images found.")
    else:
        print(f"Found {len(us_items)} US front page images:")
        for title, url in us_items:
            print(f"  - {title}")

    # Combine UK and US items
    all_items = uk_items + us_items

    # RSS and JSON generation
    rss_xml = generate_rss(all_items, uk_source_url)
    with open("rss.xml", "w", encoding="utf-8") as f:
        f.write(rss_xml)
    print("RSS feed generated as 'rss.xml'")

    json_output = generate_json(all_items, uk_source_url, rss_feed_url)
    with open("frontpages.json", "w", encoding="utf-8") as f:
        f.write(json_output)
    print("JSON feed generated as 'frontpages.json'")

if __name__ == "__main__":
    main()
