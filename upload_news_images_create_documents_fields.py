import os
import requests
import firebase_admin
import blurhash
from firebase_admin import credentials, firestore, storage
from urllib.parse import quote
from PIL import Image, ImageEnhance # <-- ADDED ImageEnhance
from io import BytesIO

# === CONFIGURATION ===
# Unchanged.
SERVICE_ACCOUNT_PATH = "service-account.json"
BUCKET_NAME = "frontpages-fireb.firebasestorage.app"
COLLECTION_NAME = "frontpage_fixed"
RSS_JSON_FEED_URL = "https://lak7474.github.io/frontpages-app-repo/frontpages.json"

# === INITIALIZE FIREBASE ===
# Unchanged.
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred, {
        'storageBucket': BUCKET_NAME
    })

# === Firestore and Storage clients ===
# Unchanged.
db = firestore.client()
bucket = storage.bucket()

# === DELETE EXISTING DOCUMENTS ===
# Unchanged.
def delete_all_documents():
    """
    Deletes all documents in a collection in batches of 500.
    """
    collection_ref = db.collection(COLLECTION_NAME)
    docs = collection_ref.stream()
    deleted_count = 0
    batch = db.batch()
    
    for doc in docs:
        batch.delete(doc.reference)
        deleted_count += 1
        if deleted_count % 500 == 0:
            print(f"Committing batch of {deleted_count} deletes...")
            batch.commit()
            batch = db.batch()

    if deleted_count > 0:
        print(f"Committing final batch of {deleted_count} deletes...")
        batch.commit()

    if deleted_count > 0:
        print(f"🧹 All {deleted_count} documents successfully deleted from {COLLECTION_NAME}")
    else:
        print(f"🧹 Collection {COLLECTION_NAME} is already empty.")

# === FETCH JSON FEED ===
# Unchanged.
def fetch_feed():
    resp = requests.get(RSS_JSON_FEED_URL)
    resp.raise_for_status()
    return resp.json().get('items', [])

# === PROCESS EACH ITEM (REBUILT FROM YOUR WORKING SCRIPT) ===
def process_items(items):
    for item in items:
        image_src = item.get('link')
        if not image_src:
            print(" ▶️  Skipped item with no link")
            continue

        original_filename = os.path.basename(image_src)
        
        try:
            r = requests.get(image_src, stream=True)
            r.raise_for_status()
            img_data = r.content
            content_type = r.headers.get('Content-Type', 'image/jpeg')
        except Exception as e:
            print(f" ❌ Download failed for {image_src}: {e}")
            continue

        # --- LIGHT IMAGE WORKFLOW ---
        try:
            print(f"   - Processing light version for {original_filename}...")
            # Create a Pillow object ONLY for getting light image metadata
            with Image.open(BytesIO(img_data)) as img_light:
                img_light_rgb = img_light.convert('RGB')
                width, height = img_light_rgb.size
                aspect_ratio = height / width if width else None
                # This is the last thing we do with this object
                blurhash_string_light = blurhash.encode(img_light_rgb, x_components=4, y_components=3)

            # Upload the original bytes and create the Firestore doc
            light_filename = f"light-{original_filename}"
            light_doc_id = f"light-{os.path.splitext(original_filename)[0]}"
            blob_path_light = f"images/{light_filename}"
            bucket.blob(blob_path_light).upload_from_string(img_data, content_type=content_type)
            public_url_light = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{quote(blob_path_light, safe='')}?alt=media"
            db.collection(COLLECTION_NAME).document(light_doc_id).set({
                'title': item.get('title', ''), 'pubDate': item.get('pubDate', ''),
                'image': public_url_light, 'width': width, 'height': height,
                'aspect': aspect_ratio, 'blurhash': blurhash_string_light,
                'brightness': 'light', 'fetched': firestore.SERVER_TIMESTAMP
            })
            print(f" ✅ Uploaded & saved (light): {light_doc_id}")
        except Exception as e:
            print(f" ❌ Failed during LIGHT processing for {original_filename}: {e}")
            # Do not continue, still attempt the dark version
        
        # --- DARK IMAGE WORKFLOW (COMPLETELY SEPARATE) ---
        try:
            print(f"   - Processing dark version for {original_filename}...")
            # Create a SECOND, totally separate Pillow object
            with Image.open(BytesIO(img_data)) as img_dark:
                img_dark_rgb = img_dark.convert('RGB')
                
                # Rule: Do ALL Pillow manipulations FIRST
                enhancer = ImageEnhance.Brightness(img_dark_rgb)
                final_dark_img = enhancer.enhance(0.7)

                # Now get metadata from the NEWLY created dark image
                dark_width, dark_height = final_dark_img.size
                dark_aspect_ratio = dark_height / dark_width if dark_width else None
                
                # Rule: The LAST thing we do is call the destructive blurhash function
                blurhash_string_dark = blurhash.encode(final_dark_img, x_components=4, y_components=3)

                # Convert the manipulated image to bytes for upload
                buffer = BytesIO()
                final_dark_img.save(buffer, format='JPEG')
                dark_img_data_for_upload = buffer.getvalue()

            # Upload the new bytes and create the Firestore doc
            dark_filename = f"dark-{original_filename}"
            dark_doc_id = f"dark-{os.path.splitext(original_filename)[0]}"
            blob_path_dark = f"images/{dark_filename}"
            bucket.blob(blob_path_dark).upload_from_string(dark_img_data_for_upload, content_type='image/jpeg')
            public_url_dark = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{quote(blob_path_dark, safe='')}?alt=media"
            db.collection(COLLECTION_NAME).document(dark_doc_id).set({
                'title': item.get('title', ''), 'pubDate': item.get('pubDate', ''),
                'image': public_url_dark, 'width': dark_width, 'height': dark_height,
                'aspect': dark_aspect_ratio, 'blurhash': blurhash_string_dark,
                'brightness': 'dark', 'fetched': firestore.SERVER_TIMESTAMP
            })
            print(f" ✅ Uploaded & saved (dark): {dark_doc_id}")
        except Exception as e:
            print(f" ❌ Failed during DARK processing for {original_filename}: {e}")

# === MAIN ===
# Unchanged.
def main():
    print("🧹 Clearing Firestore collection…")
    delete_all_documents()
    print("\n🔄 Fetching feed…")
    items = fetch_feed()
    if not items:
        print("   → No items found in feed.")
        return
    print(f"   → {len(items)} items found. Processing…\n")
    process_items(items)
    print("\n✔️  Done.")

if __name__ == "__main__":
    main()