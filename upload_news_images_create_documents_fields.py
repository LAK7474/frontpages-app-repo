# ===================================================================================
# === upload_news_images_create_documents_fields.py (Definitive Final Version v2) ===
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
import traceback # Added for more detailed error logging

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
SERVER_TIMESTAMP = firestore.SERVER_TIMESTAMP

# === INITIALIZE APIS (GEMINI & SEARCH) ===
try:
    # Get all keys from the environment (set by GitHub Actions)
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    SEARCH_API_KEY = os.environ["GOOGLE_SEARCH_API_KEY"]
    SEARCH_ENGINE_ID = os.environ["GOOGLE_SEARCH_ENGINE_ID"]
    print("✨ All APIs configured successfully (Gemini & Google Search).")
except KeyError as e:
    print(f"❌ FATAL ERROR: A required secret is missing from the environment: {e}")
    exit(1)

# === NEW HELPER FUNCTION TO PERFORM A REAL WEB SEARCH ===
def google_search(query: str) -> str:
    """Performs a Google search using the Custom Search API and returns results."""
    print(f"    - 🔎 Performing real-time web search for: '{query}'")
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'q': query,
        'key': SEARCH_API_KEY,
        'cx': SEARCH_ENGINE_ID,
        'num': 3  # Get the top 3 results
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        search_results = response.json()
        snippets = [item.get('snippet', '') for item in search_results.get('items', [])]
        formatted_results = "\n".join(snippets).replace("...", "")
        return formatted_results if formatted_results else "No relevant search results found."
    except Exception as e:
        print(f"    - ❌ ERROR during web search: {e}")
        return f"Web search failed with an error: {e}"

# === REWRITTEN HELPER FUNCTION FOR ADVANCED AI ANALYSIS (DEFINITIVE BUG FIX) ===
def generate_ai_analysis(image_data: bytes) -> str:
    """Generates news analysis by letting the Gemini Pro model use a web search tool."""
    try:
        print("   - 🧠 Calling Gemini 1.5 Pro with search tool available...")
        
        model = genai.GenerativeModel(
            model_name='gemini-1.5-pro-latest',
            tools=[google_search]
        )
        
        image_part = {"mime_type": "image/jpeg", "data": image_data}
        prompt = """Based on the attached newspaper front page, first identify the main, most prominent headline. Then, use the provided google_search tool to find the very latest news and context about that specific headline. Finally, write a solid analysis of the day's news, integrating the real-time information from your search. Start the entire response with "Today's insert newspaper title here front page..." - this must be how it starts."""

        # First call to Gemini
        response = model.generate_content([prompt, image_part], request_options={"timeout": 120})
        
        # Manually check for a function call before trying to access .text
        candidate = response.candidates[0]
        function_call_part = None
        for part in candidate.content.parts:
            if part.function_call:
                function_call_part = part.function_call
                break

        # Now, use a robust if/else to handle the two distinct cases
        if function_call_part:
            # === TOOL CALLING PATH ===
            print(f"   - Model wants to use tool: '{function_call_part.name}'")
            query = function_call_part.args['query']
            
            # Execute your actual search function
            search_results_text = google_search(query=query)
            
            # Make the SECOND call, feeding the search results back to the model
            print("    -  Feeding search results back to the model for final analysis...")
            final_response = model.generate_content(
                [
                    prompt, 
                    image_part,
                    # This special object tells the model what its tool call produced
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name='google_search',
                            response={'result': search_results_text}
                        )
                    )
                ]
            )
            print("     - Context-aware analysis generated successfully.")
            return final_response.text
        else:
            # === DIRECT ANSWER PATH ===
            # We are now certain there is no function call, so calling .text is safe.
            print("     - Analysis generated without needing a web search.")
            return response.text

    except Exception as e:
        # This will now print the full error and traceback to the GitHub log
        print(f"     - ❌ FATAL ERROR during Gemini analysis: {e}")
        traceback.print_exc()
        return "AI analysis could not be generated for this front page due to a server error."

# === (The rest of your file remains exactly the same below this line) ===

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