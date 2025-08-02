# ===================================================================================
# === upload_news_images_create_documents_fields.py (Final with Structured OCR) ===
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
import traceback
import re
from datetime import datetime, timedelta, timezone
import json # NEW: Import the JSON library for parsing

# === CONFIGURATION (UNCHANGED) ===
SERVICE_ACCOUNT_PATH = "service-account.json"
BUCKET_NAME = "frontpages-fireb.firebasestorage.app"
COLLECTION_NAME = "frontpage_fixed"
DETAILS_COLLECTION_NAME = "newspaper_details"
RSS_JSON_FEED_URL = "https://lak7474.github.io/frontpages-app-repo/frontpages.json"

# === INITIALIZATIONS (UNCHANGED) ===
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred, {'storageBucket': BUCKET_NAME})

db = firestore.client()
bucket = storage.bucket()
SERVER_TIMESTAMP = firestore.SERVER_TIMESTAMP

try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    SEARCH_API_KEY = os.environ["GOOGLE_SEARCH_API_KEY"]
    SEARCH_ENGINE_ID = os.environ["GOOGLE_SEARCH_ENGINE_ID"]
    print("✨ All APIs configured successfully (Gemini & Google Search).")
except KeyError as e:
    print(f"❌ FATAL ERROR: A required secret is missing from the environment: {e}")
    exit(1)

# === HELPER FUNCTIONS (Analysis and Search are unchanged) ===
def google_search(query: str) -> str:
    # (This function is correct and unchanged)
    print(f"    - 🔎 Performing real-time web search for: '{query}'")
    url = "https://www.googleapis.com/customsearch/v1"
    params = {'q': query, 'key': SEARCH_API_KEY, 'cx': SEARCH_ENGINE_ID, 'num': 3}
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

def generate_ai_analysis(image_data: bytes) -> str:
    # (This function is correct and unchanged)
    try:
        print("   - 🧠 Calling Gemini 1.5 Pro for analysis...")
        model = genai.GenerativeModel(model_name='gemini-1.5-pro-latest', tools=[google_search])
        image_part = {"mime_type": "image/jpeg", "data": image_data}
        prompt = """Based on the attached newspaper front page, first identify the main, most prominent headline. Then, use the provided google_search tool to find the very latest news and context about that specific headline. Finally, write a solid analysis of the day's news, integrating the real-time information from your search. Start the entire response with "Today's insert newspaper title here front page...". Ensure the final output is a clean, narrative analysis and does not include any code, function calls, or tool outputs."""
        response = model.generate_content([prompt, image_part], request_options={"timeout": 120})
        raw_text = ""
        candidate = response.candidates[0]
        if candidate.content.parts and candidate.content.parts[0].function_call:
            function_call = candidate.content.parts[0].function_call
            print(f"   - Model wants to use tool: '{function_call.name}'")
            query = function_call.args['query']
            search_results_text = google_search(query=query)
            print("    -  Feeding search results back to the model...")
            final_response = model.generate_content([prompt, image_part, genai.protos.Part(function_response=genai.protos.FunctionResponse(name='google_search', response={'result': search_results_text}))])
            raw_text = final_response.text
            print("     - Context-aware analysis generated.")
        else:
            raw_text = response.text
            print("     - Analysis generated without web search.")
        cleanup_regex = r"```tool_outputs.*?```"
        cleaned_text = re.sub(cleanup_regex, "", raw_text, flags=re.DOTALL).strip()
        return cleaned_text
    except Exception as e:
        print(f"     - ❌ FATAL ERROR during analysis: {e}")
        traceback.print_exc()
        return "AI analysis could not be generated."

# === REWRITTEN HELPER FUNCTION FOR STRUCTURED OCR === ### MODIFIED ###
def generate_ocr_text(image_data: bytes) -> dict: # Return type is now dict
    """Performs structured OCR on an image and returns a JSON object (as a dict)."""
    try:
        print("   - 📄 Calling Gemini 1.5 Flash for Structured OCR...")
        model = genai.GenerativeModel(model_name='gemini-1.5-flash-latest')
        image_part = {"mime_type": "image/jpeg", "data": image_data}
        
        # A much more advanced prompt instructing the AI to act as a document parser
        prompt = """Analyze the attached newspaper front page. Identify all text elements and classify them. Your output MUST be a single, valid JSON object and nothing else. Do not use markdown.

The JSON object should have a key "articles" which is an array of text elements. Each element in the array should be an object with two keys: "type" and "text".

The "type" can be one of the following strings: "headline", "subheading", "body_text", or "caption".

Example Output:
{
  "articles": [
    { "type": "headline", "text": "BIG NEWS SHAKES THE NATION" },
    { "type": "subheading", "text": "Markets react to the shocking announcement from yesterday." },
    { "type": "body_text", "text": "The full story begins here, with multiple paragraphs of text extracted from the main column of the newspaper..." },
    { "type": "caption", "text": "A picture showing the event." }
  ]
}
"""
        response = model.generate_content([prompt, image_part], request_options={"timeout": 100})
        
        # Parse the JSON string from the AI into a Python dictionary
        try:
            # The .text property might be wrapped in markdown backticks, so we clean it first
            cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
            json_output = json.loads(cleaned_response)
            print("     - Structured OCR JSON parsed successfully.")
            return json_output
        except json.JSONDecodeError as e:
            print(f"     - ❌ ERROR parsing JSON from AI: {e}")
            return {"error": "Failed to parse structured text from AI.", "raw_response": response.text}

    except Exception as e:
        print(f"     - ❌ FATAL ERROR during OCR: {e}")
        traceback.print_exc()
        return {"error": "Text could not be extracted from this image."}


# === Other functions are unchanged except for where they save the data ===

def calculate_paper_date(pub_date_str: str) -> str | None:
    # (This function is correct and unchanged)
    if not pub_date_str: return None
    try:
        parsed_date = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
        parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        if parsed_date.hour >= 20: paper_date = parsed_date + timedelta(days=1)
        else: paper_date = parsed_date
        return paper_date.strftime("%A %d %B %Y")
    except (ValueError, TypeError):
        print(f"   - ⚠️ Could not parse date: {pub_date_str}"); return None

def get_newspaper_details(title: str) -> dict:
    # (This function is correct and unchanged)
    lower_title = title.lower()
    title_map = {"sun": "sun", "mail": "mail", "metro": "metro", "mirror": "mirror", "times": "times", "telegraph": "telegraph", "express": "express", "star": "star", "i": "i", "guardian": "guardian", "observer": "observer", "financial": "financial", "ft": "financial", "independent": "independent"}
    doc_id = None
    for keyword, id in title_map.items():
        if keyword in lower_title: doc_id = id; break
    if not doc_id: print(f"   - ⚠️ No newspaper details found for title: {title}"); return {}
    try:
        doc_ref = db.collection("newspaper_details").document(doc_id)
        doc = doc_ref.get()
        if doc.exists: print(f"   - 📖 Found details for '{doc_id}' in Firestore."); return doc.to_dict()
        else: print(f"   - ⚠️ Document '{doc_id}' not found."); return {}
    except Exception as e: print(f"   - ❌ ERROR fetching details for '{doc_id}': {e}"); return {}

def delete_all_documents():
    # (This function is correct and unchanged)
    collection_ref = db.collection(COLLECTION_NAME)
    docs = collection_ref.stream()
    deleted_count = 0
    batch = db.batch()
    for doc in docs:
        batch.delete(doc.reference)
        deleted_count += 1
        if deleted_count % 500 == 0: batch.commit(); batch = db.batch()
    if deleted_count % 500 > 0: batch.commit()
    if deleted_count > 0: print(f"🧹 All {deleted_count} documents successfully deleted from {COLLECTION_NAME}")
    else: print(f"🧹 Collection {COLLECTION_NAME} is already empty.")

def fetch_feed():
    # (This function is correct and unchanged)
    resp = requests.get(RSS_JSON_FEED_URL)
    resp.raise_for_status()
    return resp.json().get('items', [])

def process_items(items):
    for item in items:
        # --- STAGE 1 ---
        image_src = item.get('link')
        pub_date_str = item.get('pubDate')
        title = item.get('title', '')
        if not image_src or not title: print(" ▶️  Skipped item with no link or title"); continue
        details = get_newspaper_details(title)
        paper_date_str_formatted = calculate_paper_date(pub_date_str)
        original_filename = os.path.basename(image_src)
        try:
            r = requests.get(image_src, stream=True); r.raise_for_status(); original_img_data = r.content
        except Exception as e: print(f" ❌ Download failed for {original_filename}: {e}"); continue
        # --- STAGE 1.5 ---
        analysis_text = generate_ai_analysis(original_img_data)
        ocr_data = generate_ocr_text(original_img_data) # Variable name changed to reflect it holds a dictionary
        # --- STAGE 2 & 3 ---
        try:
            print(f"   - Performing Pillow operations for {original_filename}...")
            with Image.open(BytesIO(original_img_data)) as img:
                img_rgb = img.convert('RGB'); enhancer = ImageEnhance.Brightness(img_rgb); light_img_obj = enhancer.enhance(0.9)
                light_width, light_height = light_img_obj.size; light_aspect_ratio = light_height / light_width if light_width else None
                light_buffer = BytesIO(); light_img_obj.save(light_buffer, format='JPEG'); final_light_img_data = light_buffer.getvalue()
            with Image.open(BytesIO(original_img_data)) as img:
                img_rgb = img.convert('RGB'); enhancer = ImageEnhance.Brightness(img_rgb); dark_img_obj = enhancer.enhance(0.80)
                dark_width, dark_height = dark_img_obj.size; dark_aspect_ratio = dark_height / dark_width if dark_width else None
                dark_buffer = BytesIO(); dark_img_obj.save(dark_buffer, format='JPEG'); final_dark_img_data = dark_buffer.getvalue()
            print("     - Pillow operations complete.")
        except Exception as e: print(f" ❌ Failed during PILLOW processing for {original_filename}: {e}"); continue
        try:
            print(f"   - Performing Blurhash operations for {original_filename}...")
            with Image.open(BytesIO(original_img_data)) as img: blurhash_light = blurhash.encode(img, x_components=4, y_components=3)
            with Image.open(BytesIO(final_dark_img_data)) as img: blurhash_dark = blurhash.encode(img, x_components=4, y_components=3)
            print("     - Blurhash operations complete.")
        except Exception as e: print(f" ❌ Failed during BLURHASH processing for {original_filename}: {e}"); continue
        # --- STAGE 4 --- ### MODIFIED ###
        base_doc_data = {
            'title': title, 'pubDate': pub_date_str, 'dateOfPaper': paper_date_str_formatted,
            'analysis': analysis_text, 'ocr_text': ocr_data, # This now saves the entire JSON object
            'fetched': SERVER_TIMESTAMP, 'ownedBy1': details.get('ownedBy1'), 'ownedBy2': details.get('ownedBy2'), 'ownedBy3': details.get('ownedBy3'),
            'format': details.get('format'), 'style': details.get('style'), 'leaning': details.get('leaning'),
            'readershipDemographics': details.get('readershipDemographics'),
        }
        # Light Version
        try:
            light_filename = f"light-{original_filename}"; light_doc_id = f"light-{os.path.splitext(original_filename)[0]}"
            blob_path_light = f"images/{light_filename}"; bucket.blob(blob_path_light).upload_from_string(final_light_img_data, content_type='image/jpeg')
            public_url_light = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{quote(blob_path_light, safe='')}?alt=media"
            light_doc = base_doc_data.copy()
            light_doc.update({'image': public_url_light, 'width': light_width, 'height': light_height, 'aspect': light_aspect_ratio, 'blurhash': blurhash_light, 'brightness': 'light'})
            db.collection(COLLECTION_NAME).document(light_doc_id).set(light_doc)
            print(f" ✅ Uploaded & saved (light): {light_doc_id}")
        except Exception as e: print(f" ❌ Failed to WRITE light version for {original_filename}: {e}")
        # Dark Version
        try:
            dark_filename = f"dark-{original_filename}"; dark_doc_id = f"dark-{os.path.splitext(original_filename)[0]}"
            blob_path_dark = f"images/{dark_filename}"; bucket.blob(blob_path_dark).upload_from_string(final_dark_img_data, content_type='image/jpeg')
            public_url_dark = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{quote(blob_path_dark, safe='')}?alt=media"
            dark_doc = base_doc_data.copy()
            dark_doc.update({'image': public_url_dark, 'width': dark_width, 'height': dark_height, 'aspect': dark_aspect_ratio, 'blurhash': blurhash_dark, 'brightness': 'dark'})
            db.collection(COLLECTION_NAME).document(dark_doc_id).set(dark_doc)
            print(f" ✅ Uploaded & saved (dark): {dark_doc_id}")
        except Exception as e: print(f" ❌ Failed to WRITE dark version for {original_filename}: {e}")

def main():
    print("🧹 Clearing Firestore collection…"); delete_all_documents()
    print("\n🔄 Fetching feed…"); items = fetch_feed()
    if not items: print("   → No items found in feed."); return
    print(f"   → {len(items)} items found. Processing…\n"); process_items(items)
    print("\n✔️  Done.")

if __name__ == "__main__":
    main()