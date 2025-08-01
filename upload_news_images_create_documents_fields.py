# ===================================================================================
# === upload_news_images_create_documents_fields.py (Final, Linter-Friendly Version) ===
# ===================================================================================

import os
import requests
import firebase_admin
import blurhash
from firebase_admin import credentials, firestore, storage
from urllib.parse import quote
from PIL import Image, ImageEnhance
from io import BytesIO
import google.generativeai as genai

# === CONFIGURATION ===
SERVICE_ACCOUNT_PATH = "service-account.json"
BUCKET_NAME = "frontpages-fireb.firebasestorage.app"
COLLECTION_NAME = "frontpage_fixed"
RSS_JSON_FEED_URL = "https://lak7474.github.io/frontpages-app-repo/frontpages.json"

# === INITIALIZE FIREBASE ===
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred, {'storageBucket': BUCKET_NAME})

db = firestore.client()
bucket = storage.bucket()
# Correctly get the server timestamp sentinel value to avoid linter errors
SERVER_TIMESTAMP = firestore.SERVER_TIMESTAMP

# === INITIALIZE GEMINI API ===
try:
    # This will securely read the key from the GitHub Actions environment variable
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    print("✨ Gemini API configured successfully.")
except KeyError:
    print("❌ FATAL ERROR: GEMINI_API_KEY secret not found in environment.")
    exit(1)

# === HELPER FUNCTION FOR AI ANALYSIS ===
def generate_ai_analysis(image_data: bytes) -> str | None:
    """
    Generates news analysis from image bytes using the Gemini API.
    Returns the analysis text or a placeholder if it fails.
    """
    try:
        print("   - 🧠 Calling Gemini 1.5 Flash for analysis...")
        image_part = {"mime_type": "image/jpeg", "data": image_data}
        prompt = """Please give a solid analysis of the day's news, based on this newspaper front page. Go through the headlines, the stories, what is says about the current state of politics, the public mood etc. Be creative. Start with "Today's insert newspaper title here front page..." - this must be how it starts."""
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([prompt, image_part], request_options={"timeout": 100})
        print("     - Analysis generated successfully.")
        return response.text
    except Exception as e:
        print(f"     - ❌ ERROR during Gemini analysis: {e}")
        return "AI analysis could not be generated for this front page."

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

# === PROCESS EACH ITEM ===
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
        except Exception as e:
            print(f" ❌ Download failed for {original_filename}: {e}")
            continue

        # --- STAGE 1.5: GENERATE AI ANALYSIS (ONCE!) ---
        analysis_text = generate_ai_analysis(original_img_data)

        # --- STAGE 2: ALL PILLOW MANIPULATIONS ---
        try:
            print(f"   - Performing Pillow operations for {original_filename}...")
            # Light Image Data
            with Image.open(BytesIO(original_img_data)) as img:
                img_rgb = img.convert('RGB')
                enhancer = ImageEnhance.Brightness(img_rgb)
                light_img_obj = enhancer.enhance(0.9)
                light_width, light_height = light_img_obj.size
                light_aspect_ratio = light_height / light_width if light_width else None
                light_buffer = BytesIO()
                light_img_obj.save(light_buffer, format='JPEG')
                final_light_img_data = light_buffer.getvalue()

            # Dark Image Data
            with Image.open(BytesIO(original_img_data)) as img:
                img_rgb = img.convert('RGB')
                enhancer = ImageEnhance.Brightness(img_rgb)
                dark_img_obj = enhancer.enhance(0.80)
                dark_width, dark_height = dark_img_obj.size
                dark_aspect_ratio = dark_height / dark_width if dark_width else None
                dark_buffer = BytesIO()
                dark_img_obj.save(dark_buffer, format='JPEG')
                final_dark_img_data = dark_buffer.getvalue()

            print("     - Pillow operations complete.")
        except Exception as e:
            print(f" ❌ Failed during PILLOW processing for {original_filename}: {e}")
            continue
            
        # --- STAGE 3: ALL BLURHASH ENCODINGS ---
        try:
            print(f"   - Performing Blurhash operations for {original_filename}...")
            with Image.open(BytesIO(original_img_data)) as img:
                blurhash_light = blurhash.encode(img, x_components=4, y_components=3)

            with Image.open(BytesIO(final_dark_img_data)) as img:
                blurhash_dark = blurhash.encode(img, x_components=4, y_components=3)
            
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
            bucket.blob(blob_path_light).upload_from_string(final_light_img_data, content_type='image/jpeg')
            public_url_light = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{quote(blob_path_light, safe='')}?alt=media"
            db.collection(COLLECTION_NAME).document(light_doc_id).set({
                'title': item.get('title', ''), 'pubDate': item.get('pubDate', ''),
                'image': public_url_light, 'width': light_width, 'height': light_height,
                'aspect': light_aspect_ratio, 'blurhash': blurhash_light,
                'brightness': 'light', 'fetched': SERVER_TIMESTAMP,
                'analysis': analysis_text
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
                'brightness': 'dark', 'fetched': SERVER_TIMESTAMP,
                'analysis': analysis_text
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