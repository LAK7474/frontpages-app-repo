import requests
from bs4 import BeautifulSoup
from datetime import datetime

def get_latest_front_pages_url():
    homepage_url = "https://news.sky.com/uk"
    html = requests.get(homepage_url).text
    soup = BeautifulSoup(html, "html.parser")

    # Search for anchor tags with "front pages" in text or href
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True).lower()
        if 'front pages' in text or 'front-pages' in href:
            # Build full URL
            if href.startswith("/"):
                href = "https://news.sky.com" + href
            return href
    return None

def scrape_front_page_images(article_url):
    html = requests.get(article_url).text
    soup = BeautifulSoup(html, "html.parser")

    items = []
    # Pull first 30 images from the article page
    for img in soup.select("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
        if not src.startswith("http"):
            src = "https:" + src
        alt = img.get("alt", "Newspaper Front Page")
        items.append((alt, src))
        if len(items) >= 30:  # change limit to 30
            break
    return items

def generate_rss(items, source_url):
    rss_items = ""
    for title, img_url in items:
        rss_items += f"""
        <item>
          <title>{title}</title>
          <link>{img_url}</link>
          <description><![CDATA[<img src="{img_url}" />]]></description>
        </item>
        """

    rss_feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sky News Front Pages</title>
    <link>{source_url}</link>
    <description>Daily UK newspaper front pages</description>
    <lastBuildDate>{datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
    {rss_items}
  </channel>
</rss>
"""
    return rss_feed

def main():
    front_pages_url = get_latest_front_pages_url()
    if not front_pages_url:
        print("No front pages article found on homepage.")
        return

    items = scrape_front_page_images(front_pages_url)
    if not items:
        print("No front page images found on article.")
        return

    rss_xml = generate_rss(items, front_pages_url)
    with open("rss.xml", "w", encoding="utf-8") as f:
        f.write(rss_xml)
    print("RSS feed generated.")

if __name__ == "__main__":
    main()
