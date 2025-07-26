import os
import requests
import firebase_admin
from firebase_admin import credentials, firestore, storage
from urllib.parse import quote
from PIL import Image
from io import BytesIO

# === CONFIGURATION ===
SERVICE_ACCOUNT_PATH = "service-account.json"
BUCKET_NAME = "frontpages-fireb.appspot.com"
COLLECTION_NAME = "frontpage_fixed"
RSS_JSON_FEED_URL = "https://lak7474.github.io/frontpages-app-repo/frontpages.json"

# === INITIALIZE FIREBASE ===
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred, {
        'storageBucket': BUCKET_NAME
    })

# === Firestore and Storage clients ===
db = firestore.client()
bucket = storage.bucket()

# === DELETE EXISTING DOCUMENTS ===
def delete_all_documents():
    docs = db.collection(COLLECTION_NAME).stream()
    for doc in docs:
        doc.reference.delete()
    print(f"🧹 All documents deleted from {COLLECTION_NAME}")

# === FETCH JSON FEED ===
def fetch_feed():
    resp = requests.get(RSS_JSON_FEED_URL)
    resp.raise_for_status()
    return resp.json().get('items', [])

# === PROCESS EACH ITEM ===
def process_items(items):
    for item in items:
        image_src = item.get('link')
        if not image_src:
            print(" ▶️  Skipped item with no link")
            continue

        filename = os.path.basename(image_src)
        doc_id = os.path.splitext(filename)[0]

        try:
            r = requests.get(image_src, stream=True)
            r.raise_for_status()
            img_data = r.content
        except Exception as e:
            print(f" ❌ Download failed for {image_src}: {e}")
            continue

        try:
            img = Image.open(BytesIO(img_data))
            width, height = img.size
        except Exception as e:
            print(f" ❌ Could not get image dimensions for {filename}: {e}")
            width, height = None, None

        blob_path = f"images/{filename}"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(img_data, content_type=r.headers.get('Content-Type', 'image/jpeg'))

        encoded_path = quote(blob_path, safe='')
        public_url = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{encoded_path}?alt=media"

        doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
        doc_ref.set({
            'title': item.get('title', ''),
            'pubDate': item.get('pubDate', ''),
            'image': public_url,
            'width': width,
            'height': height,
            'fetched': firestore.SERVER_TIMESTAMP
        })
        print(f" ✅ Uploaded & saved: {doc_id} ({width}x{height})")

# === MAIN ===
def main():
    print("🧹 Clearing Firestore collection…")
    delete_all_documents()

    print("🔄 Fetching feed…")
    items = fetch_feed()
    print(f"   → {len(items)} items found. Processing…")
    process_items(items)
    print("✔️  Done.")

if __name__ == "__main__":
    main()
