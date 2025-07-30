import os
import requests
import firebase_admin
import blurhash
from firebase_admin import credentials, firestore, storage
from urllib.parse import quote
from PIL import Image, ImageEnhance
from io import BytesIO

# === CONFIGURATION ===
SERVICE_ACCOUNT_PATH = "service-account.json"
BUCKET_NAME = "frontpages-fireb.firebasestorage.app"
COLLECTION_NAME = "frontpage_fixed"
RSS_JSON_FEED_URL = "https://lak7474.github.io/frontpages-app-repo/frontpages.json"

# === INITIALIZE FIREBASE ===
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred, {
        'storageBucket': BUCKET_NAME
    })

db = firestore.client()
bucket = storage.bucket()

# === DELETE EXISTING DOCUMENTS ===
def delete_all_documents():
    collection_ref = db.collection(COLLECTION_NAME)
    docs = collection_ref.stream()
    deleted_count = 0
    batch = db.batch()
    for doc in docs:
        batch.delete(doc.reference)
        deleted_count += 1
        if deleted_count % 500 == 0:
            batch.commit()
            batch = db.batch()
    if deleted_count % 500 > 0:
        batch.commit()
    if deleted_count > 0:
        print(f"🧹 All {deleted_count} documents successfully deleted from {COLLECTION_NAME}")
    else:
        print(f"🧹 Collection {COLLECTION_NAME} is already empty.")

# === FETCH JSON FEED ===
def fetch_feed():
    resp = requests.get(RSS_JSON_FEED_URL)
    resp.raise_for_status()
    return resp.json().get('items', [])

# === PROCESS EACH ITEM (NEW ARCHITECTURE: PILLOW FIRST, BLURHASH LAST) ===
def process_items(items):
    for item in items:
        # --- STAGE 1: DOWNLOAD ---
        image_src = item.get('link')
        if not image_src:
            print(" ▶️  Skipped item with no link")
            continue

        original_filename = os.path.basename(image_src)
        
        try:
            r = requests.get(image_src, stream=True)
            r.raise_for_status()
            original_img_data = r.content
            content_type = r.headers.get('Content-Type', 'image/jpeg')
        except Exception as e:
            print(f" ❌ Download failed for {original_filename}: {e}")
            continue

        # --- STAGE 2: ALL PILLOW MANIPULATIONS (NO BLURHASH ALLOWED) ---
        try:
            print(f"   - Performing Pillow operations for {original_filename}...")
            # --- Light Image Data ---
            with Image.open(BytesIO(original_img_data)) as img:
                img_rgb = img.convert('RGB')
                light_width, light_height = img_rgb.size
                light_aspect_ratio = light_height / light_width if light_width else None

            # --- Dark Image Data ---
            with Image.open(BytesIO(original_img_data)) as img:
                img_rgb = img.convert('RGB')
                enhancer = ImageEnhance.Brightness(img_rgb)
                dark_img_obj = enhancer.enhance(0.7)
                dark_width, dark_height = dark_img_obj.size
                dark_aspect_ratio = dark_height / dark_width if dark_width else None
                # Save the generated dark image bytes into a variable
                dark_buffer = BytesIO()
                dark_img_obj.save(dark_buffer, format='JPEG')
                final_dark_img_data = dark_buffer.getvalue()

            print("     - Pillow operations complete.")
        except Exception as e:
            print(f" ❌ Failed during PILLOW processing for {original_filename}: {e}")
            continue

        # --- STAGE 3: ALL BLURHASH ENCODINGS (NO PILLOW ALLOWED) ---
        try:
            print(f"   - Performing Blurhash operations for {original_filename}...")
            # Generate light blurhash from original data
            with Image.open(BytesIO(original_img_data)) as img:
                blurhash_light = blurhash.encode(img.convert('RGB'), x_components=4, y_components=3)

            # Generate dark blurhash from the NEW dark image data we saved
            with Image.open(BytesIO(final_dark_img_data)) as img:
                blurhash_dark = blurhash.encode(img.convert('RGB'), x_components=4, y_components=3)
            
            print("     - Blurhash operations complete.")
        except Exception as e:
            print(f" ❌ Failed during BLURHASH processing for {original_filename}: {e}")
            continue

        # --- STAGE 4: UPLOAD AND WRITE TO FIRESTORE ---
        # Light Version
        try:
            light_filename = f"light-{original_filename}"
            light_doc_id = f"light-{os.path.splitext(original_filename)[0]}"
            blob_path_light = f"images/{light_filename}"
            bucket.blob(blob_path_light).upload_from_string(original_img_data, content_type=content_type)
            public_url_light = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{quote(blob_path_light, safe='')}?alt=media"
            db.collection(COLLECTION_NAME).document(light_doc_id).set({
                'title': item.get('title', ''), 'pubDate': item.get('pubDate', ''),
                'image': public_url_light, 'width': light_width, 'height': light_height,
                'aspect': light_aspect_ratio, 'blurhash': blurhash_light,
                'brightness': 'light', 'fetched': firestore.SERVER_TIMESTAMP
            })
            print(f" ✅ Uploaded & saved (light): {light_doc_id}")
        except Exception as e:
            print(f" ❌ Failed to WRITE light version for {original_filename}: {e}")

        # Dark Version
        try:
            dark_filename = f"dark-{original_filename}"
            dark_doc_id = f"dark-{os.path.splitext(original_filename)[0]}"
            blob_path_dark = f"images/{dark_filename}"
            bucket.blob(blob_path_dark).upload_from_string(final_dark_img_data, content_type='image/jpeg')
            public_url_dark = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{quote(blob_path_dark, safe='')}?alt=media"
            db.collection(COLLECTION_NAME).document(dark_doc_id).set({
                'title': item.get('title', ''), 'pubDate': item.get('pubDate', ''),
                'image': public_url_dark, 'width': dark_width, 'height': dark_height,
                'aspect': dark_aspect_ratio, 'blurhash': blurhash_dark,
                'brightness': 'dark', 'fetched': firestore.SERVER_TIMESTAMP
            })
            print(f" ✅ Uploaded & saved (dark): {dark_doc_id}")
        except Exception as e:
            print(f" ❌ Failed to WRITE dark version for {original_filename}: {e}")

# === MAIN ===
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