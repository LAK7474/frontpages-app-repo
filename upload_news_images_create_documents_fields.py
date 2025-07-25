import os
import requests
import datetime
import firebase_admin
from firebase_admin import credentials, firestore, storage
from urllib.parse import quote

# ——— CONFIGURATION ———
SERVICE_ACCOUNT_PATH = r"C:\Users\LukeA\Documents\newspaperfrontpages-firestore\frontpages-fireb-firebase-adminsdk-fbsvc-ebba7340c0.json"
BUCKET_NAME             = "frontpages-fireb.firebasestorage.app"
COLLECTION_NAME         = "frontpage_fixed"
RSS_JSON_FEED_URL       = "https://lak7474.github.io/skynews-frontpages/frontpages.json"

# ——— INITIALIZE FIREBASE ———
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred, {
        'storageBucket': BUCKET_NAME
    })

db     = firestore.client()
bucket = storage.bucket()  # uses the BUCKET_NAME from initialize_app

# ——— STEP 1: Fetch RSS JSON feed ———
def fetch_feed():
    resp = requests.get(RSS_JSON_FEED_URL)
    resp.raise_for_status()
    return resp.json().get('items', [])

# ——— STEP 2: Process each item ———
from PIL import Image
from io import BytesIO

def process_items(items):
    for item in items:
        image_src = item.get('link')
        if not image_src:
            print(" ▶️  Skipped item with no link")
            continue

        # create a safe filename & doc ID from the URL
        filename = os.path.basename(image_src)
        doc_id   = os.path.splitext(filename)[0]

        # download the image
        try:
            r = requests.get(image_src, stream=True)
            r.raise_for_status()
            img_data = r.content
        except Exception as e:
            print(f" ❌ Download failed for {image_src}: {e}")
            continue

        # Get image dimensions
        try:
            img = Image.open(BytesIO(img_data))
            width, height = img.size
        except Exception as e:
            print(f" ❌ Could not get image dimensions for {filename}: {e}")
            width, height = None, None

        # upload to Storage under images/<filename>
        blob_path = f"images/{filename}"
        blob      = bucket.blob(blob_path)
        blob.upload_from_string(img_data, content_type=r.headers.get('Content-Type', 'image/jpeg'))

        # construct the correct public URL
        encoded_path = quote(blob_path, safe='')
        public_url   = (
            f"https://firebasestorage.googleapis.com/"
            f"v0/b/{BUCKET_NAME}/o/{encoded_path}?alt=media"
        )

        # write Firestore doc
        doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
        doc_ref.set({
            'title':   item.get('title', ''),
            'pubDate': item.get('pubDate', ''),
            'image':   public_url,
            'width':   width,
            'height':  height,
            'fetched': firestore.SERVER_TIMESTAMP
        })
        print(f" ✅ Uploaded & saved: {doc_id} ({width}x{height})")

# ——— DELETE ALL DOCUMENTS IN COLLECTION ———
def delete_all_documents():
    docs = db.collection(COLLECTION_NAME).stream()
    count = 0
    for doc in docs:
        doc.reference.delete()
        count += 1
    print(f"🗑️ Deleted {count} documents from '{COLLECTION_NAME}'.")

# ——— MAIN ———
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
