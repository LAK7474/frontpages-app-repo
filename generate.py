import requests
from bs4 import BeautifulSoup
from datetime import datetime

url = "https://news.sky.com/the-front-pages"
html = requests.get(url).text
soup = BeautifulSoup(html, "html.parser")

items = []

# Find images with data-src attribute containing 'skynews-'
for img in soup.select("img[data-src*='skynews-']"):
    src = img.get("data-src")
    alt = img.get("alt", "Newspaper")
    if not src.startswith("http"):
        src = "https:" + src
    items.append((alt, src))
    if len(items) >= 6:
        break

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
    <link>{url}</link>
    <description>Daily UK newspaper front pages</description>
    <lastBuildDate>{datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
    {rss_items}
  </channel>
</rss>
"""

with open("rss.xml", "w", encoding="utf-8") as f:
    f.write(rss_feed)
