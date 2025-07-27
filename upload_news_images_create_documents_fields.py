import os
import requests
import firebase_admin
import blurhash  # <--- ADD THIS IMPORT

from firebase_admin import credentials, firestore, storage
from urllib.parse import quote
from PIL import Image
from io import BytesIO

# === CONFIGURATION ===
# This section is unchanged from what you provided.
SERVICE_ACCOUNT_PATH = "service-account.json"
BUCKET_NAME = "frontpages-fireb.firebasestorage.app"
COLLECTION_NAME = "frontpage_fixed"
RSS_JSON_FEED_URL = "https://lak7474.github.io/frontpages-app-repo/frontpages.json"

# === INITIALIZE FIREBASE ===
# This section is unchanged from what you provided.
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred, {
        'storageBucket': BUCKET_NAME
    })

# === Firestore and Storage clients ===
# This section is unchanged from what you provided.
db = firestore.client()
bucket = storage.bucket()

# === DELETE EXISTING DOCUMENTS (EFFICIENT BATCH METHOD) ===
def delete_all_documents():
    """
    Deletes all documents in a collection in batches of 500, which is more
    efficient than deleting them one by one.
    """
    collection_ref = db.collection(COLLECTION_NAME)
    docs = collection_ref.stream()
    
    # A list to hold the documents we're about to delete.
    deleted_count = 0
    
    # Start a new batch.
    batch = db.batch()
    
    for doc in docs:
        # Add a delete operation to the batch.
        batch.delete(doc.reference)
        deleted_count += 1
        
        # Firestore batches have a limit of 500 operations.
        # Once we reach that limit, we commit the batch and start a new one.
        if deleted_count % 500 == 0:
            print(f"Committing batch of {deleted_count} deletes...")
            batch.commit()
            # Start a new batch for the next set of documents.
            batch = db.batch()

    # Commit any remaining documents in the last batch.
    if deleted_count > 0:
        print(f"Committing final batch of {deleted_count} deletes...")
        batch.commit()

    print(f"🧹 All {deleted_count} documents successfully deleted from {COLLECTION_NAME}")

# === FETCH JSON FEED ===
# This function is unchanged.
def fetch_feed():
    resp = requests.get(RSS_JSON_FEED_URL)
    resp.raise_for_status()
    return resp.json().get('items', [])

# === PROCESS EACH ITEM (THIS FUNCTION IS MODIFIED) ===
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

        # --- ADDED BLURHASH LOGIC ---
        blurhash_string = None  # <--- Initialize variable to ensure it always exists.
        try:
            img = Image.open(BytesIO(img_data))
            # Ensure image is in RGB mode, which BlurHash requires.
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            width, height = img.size
            
            # Generate the BlurHash string from the Pillow image object.
            blurhash_string = blurhash.encode(img, x_components=4, y_components=3)

        except Exception as e:
            print(f" ❌ Could not get image dimensions or blurhash for {filename}: {e}")
            width, height = None, None
        # --- END OF BLURHASH LOGIC ---

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
            'blurhash': blurhash_string,  # <--- ADDED: Save the new blurhash string to Firestore.
            'fetched': firestore.SERVER_TIMESTAMP
        })
        print(f" ✅ Uploaded & saved: {doc_id} ({width}x{height})")

# === MAIN ===
# This function is unchanged.
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