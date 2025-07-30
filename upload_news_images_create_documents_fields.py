import os # Import the os module for interacting with the operating system, like path manipulation.
import requests # Import the requests library for making HTTP requests.
import firebase_admin # Import the firebase_admin module for interacting with Firebase services.
import blurhash # Import the blurhash library for generating blurhash strings from images.
from firebase_admin import credentials, firestore, storage # Import specific modules from firebase_admin for credentials, Firestore database, and Cloud Storage.
from urllib.parse import quote # Import the quote function from urllib.parse for URL encoding.
from PIL import Image, ImageEnhance # Import Image and ImageEnhance from the Pillow (PIL) library for image processing.
from io import BytesIO # Import BytesIO from the io module to handle binary data in memory.

# === CONFIGURATION === # Section for defining configuration variables.
SERVICE_ACCOUNT_PATH = "service-account.json" # Path to the Firebase service account key file.
BUCKET_NAME = "frontpages-fireb.firebasestorage.app" # Name of the Firebase Storage bucket.
COLLECTION_NAME = "frontpage_fixed" # Name of the Firestore collection where data will be stored.
RSS_JSON_FEED_URL = "https://lak7474.github.io/frontpages-app-repo/frontpages.json" # URL of the JSON feed to fetch image data from.

# === INITIALIZE FIREBASE === # Section for initializing Firebase.
if not firebase_admin._apps: # Check if Firebase has already been initialized to prevent re-initialization errors.
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH) # Load the service account credentials from the specified path.
    firebase_admin.initialize_app(cred, { # Initialize the Firebase app with the loaded credentials and storage bucket.
        'storageBucket': BUCKET_NAME # Specify the storage bucket for the Firebase app.
    })

db = firestore.client() # Get a Firestore client instance.
bucket = storage.bucket() # Get a Cloud Storage bucket instance.

# === DELETE EXISTING DOCUMENTS === # Function to delete all documents from a specified Firestore collection.
def delete_all_documents(): # Define the function to delete all documents.
    collection_ref = db.collection(COLLECTION_NAME) # Get a reference to the Firestore collection.
    docs = collection_ref.stream() # Stream all documents from the collection.
    deleted_count = 0 # Initialize a counter for deleted documents.
    batch = db.batch() # Create a new Firestore batch for efficient deletion.
    for doc in docs: # Iterate over each document.
        batch.delete(doc.reference) # Add the document's reference to the batch for deletion.
        deleted_count += 1 # Increment the deleted count.
        if deleted_count % 500 == 0: # If 500 documents have been added to the batch.
            batch.commit() # Commit the current batch.
            batch = db.batch() # Start a new batch.
    if deleted_count % 500 > 0: # If there are any remaining documents in the last batch (less than 500).
        batch.commit() # Commit the final batch.
    if deleted_count > 0: # Check if any documents were deleted.
        print(f"🧹 All {deleted_count} documents successfully deleted from {COLLECTION_NAME}") # Print success message with count.
    else: # If no documents were found.
        print(f"🧹 Collection {COLLECTION_NAME} is already empty.") # Print message indicating the collection is empty.

# === FETCH JSON FEED === # Function to fetch the JSON feed from the specified URL.
def fetch_feed(): # Define the function to fetch the feed.
    resp = requests.get(RSS_JSON_FEED_URL) # Send an HTTP GET request to the JSON feed URL.
    resp.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx).
    return resp.json().get('items', []) # Parse the JSON response and return the 'items' array, or an empty list if not found.

# === PROCESS EACH ITEM (NEW ARCHITECTURE: PILLOW FIRST, BLURHASH LAST) === # Function to process each item from the feed.
def process_items(items): # Define the function to process items.
    for item in items: # Iterate over each item in the fetched list.
        # --- STAGE 1: DOWNLOAD --- # Stage for downloading the image.
        image_src = item.get('link') # Get the image source URL from the item.
        if not image_src: # Check if the image source URL exists.
            print(" ▶️  Skipped item with no link") # Print a message if no link is found.
            continue # Skip to the next item.

        original_filename = os.path.basename(image_src) # Extract the filename from the image source URL.
        
        try: # Start a try block to handle potential errors during download.
            r = requests.get(image_src, stream=True) # Send a GET request to download the image, with streaming enabled.
            r.raise_for_status() # Raise an HTTPError for bad responses.
            original_img_data = r.content # Get the raw content (bytes) of the downloaded image.
            content_type = r.headers.get('Content-Type', 'image/jpeg') # Get the Content-Type header, defaulting to 'image/jpeg'.
        except Exception as e: # Catch any exception that occurs during download.
            print(f" ❌ Download failed for {original_filename}: {e}") # Print an error message.
            continue # Skip to the next item.

        # --- STAGE 2: ALL PILLOW MANIPULATIONS (NO BLURHASH ALLOWED) --- # Stage for image manipulations using Pillow.
        try: # Start a try block to handle potential errors during Pillow processing.
            print(f"   - Performing Pillow operations for {original_filename}...") # Print a status message.
            # --- Light Image Data --- # Process for the "light" version of the image.
            with Image.open(BytesIO(original_img_data)) as img: # Open the image from bytes in memory using Pillow.
                img_rgb = img.convert('RGB') # Convert the image to RGB format.
                light_width, light_height = img_rgb.size # Get the width and height of the light image.
                light_aspect_ratio = light_height / light_width if light_width else None # Calculate the aspect ratio, avoiding division by zero.

            # --- Dark Image Data --- # Process for the "dark" version of the image.
            with Image.open(BytesIO(original_img_data)) as img: # Open the original image again for dark version processing.
                img_rgb = img.convert('RGB') # Convert to RGB.
                enhancer = ImageEnhance.Brightness(img_rgb) # Create a brightness enhancer.
                dark_img_obj = enhancer.enhance(0.86) # Reduce brightness by 14% (0.86 of original brightness).
                dark_width, dark_height = dark_img_obj.size # Get the width and height of the dark image.
                dark_aspect_ratio = dark_height / dark_width if dark_width else None # Calculate the aspect ratio.
                # Save the generated dark image bytes into a variable # Comment explaining the next steps.
                dark_buffer = BytesIO() # Create an in-memory binary stream to save the dark image.
                dark_img_obj.save(dark_buffer, format='JPEG') # Save the dark image object to the buffer as JPEG.
                final_dark_img_data = dark_buffer.getvalue() # Get the bytes from the buffer.

            print("     - Pillow operations complete.") # Print a completion message for Pillow operations.
        except Exception as e: # Catch any exception during Pillow processing.
            print(f" ❌ Failed during PILLOW processing for {original_filename}: {e}") # Print an error message.
            continue # Skip to the next item.

        # --- STAGE 3: ALL BLURHASH ENCODINGS (NO PILLOW ALLOWED) --- # Stage for generating Blurhash strings.
        try: # Start a try block to handle potential errors during Blurhash encoding.
            print(f"   - Performing Blurhash operations for {original_filename}...") # Print a status message.
            # Generate light blurhash from original data # Comment for light blurhash.
            with Image.open(BytesIO(original_img_data)) as img: # Open the original image data.
                blurhash_light = blurhash.encode(img.convert('RGB'), x_components=4, y_components=3) # Encode the light image to blurhash.

            # Generate dark blurhash from the NEW dark image data we saved # Comment for dark blurhash.
            with Image.open(BytesIO(final_dark_img_data)) as img: # Open the dark image data.
                blurhash_dark = blurhash.encode(img.convert('RGB'), x_components=4, y_components=3) # Encode the dark image to blurhash.
            
            print("     - Blurhash operations complete.") # Print a completion message for Blurhash operations.
        except Exception as e: # Catch any exception during Blurhash encoding.
            print(f" ❌ Failed during BLURHASH processing for {original_filename}: {e}") # Print an error message.
            continue # Skip to the next item.

        # --- STAGE 4: UPLOAD AND WRITE TO FIRESTORE --- # Stage for uploading images to Storage and writing data to Firestore.
        # Light Version # Section for the light version of the image.
        try: # Start a try block for light version processing.
            light_filename = f"light-{original_filename}" # Create a filename for the light version.
            light_doc_id = f"light-{os.path.splitext(original_filename)[0]}" # Create a document ID for the light version.
            blob_path_light = f"images/{light_filename}" # Define the path in Cloud Storage for the light image.
            bucket.blob(blob_path_light).upload_from_string(original_img_data, content_type=content_type) # Upload the original image data to Storage.
            public_url_light = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{quote(blob_path_light, safe='')}?alt=media" # Construct the public URL for the uploaded light image.
            db.collection(COLLECTION_NAME).document(light_doc_id).set({ # Set (create/overwrite) a document in Firestore.
                'title': item.get('title', ''), 'pubDate': item.get('pubDate', ''), # Add title and publication date from the item.
                'image': public_url_light, 'width': light_width, 'height': light_height, # Add image URL, width, and height.
                'aspect': light_aspect_ratio, 'blurhash': blurhash_light, # Add aspect ratio and light blurhash.
                'brightness': 'light', 'fetched': firestore.SERVER_TIMESTAMP # Add brightness type and server timestamp for 'fetched' field.
            }) # End of document data.
            print(f" ✅ Uploaded & saved (light): {light_doc_id}") # Print success message for light version.
        except Exception as e: # Catch any exception during light version processing.
            print(f" ❌ Failed to WRITE light version for {original_filename}: {e}") # Print an error message.

        # Dark Version # Section for the dark version of the image.
        try: # Start a try block for dark version processing.
            dark_filename = f"dark-{original_filename}" # Create a filename for the dark version.
            dark_doc_id = f"dark-{os.path.splitext(original_filename)[0]}" # Create a document ID for the dark version.
            blob_path_dark = f"images/{dark_filename}" # Define the path in Cloud Storage for the dark image.
            bucket.blob(blob_path_dark).upload_from_string(final_dark_img_data, content_type='image/jpeg') # Upload the dark image data to Storage.
            public_url_dark = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{quote(blob_path_dark, safe='')}?alt=media" # Construct the public URL for the uploaded dark image.
            db.collection(COLLECTION_NAME).document(dark_doc_id).set({ # Set (create/overwrite) a document in Firestore.
                'title': item.get('title', ''), 'pubDate': item.get('pubDate', ''), # Add title and publication date from the item.
                'image': public_url_dark, 'width': dark_width, 'height': dark_height, # Add image URL, width, and height.
                'aspect': dark_aspect_ratio, 'blurhash': blurhash_dark, # Add aspect ratio and dark blurhash.
                'brightness': 'dark', 'fetched': firestore.SERVER_TIMESTAMP # Add brightness type and server timestamp for 'fetched' field.
            }) # End of document data.
            print(f" ✅ Uploaded & saved (dark): {dark_doc_id}") # Print success message for dark version.
        except Exception as e: # Catch any exception during dark version processing.
            print(f" ❌ Failed to WRITE dark version for {original_filename}: {e}") # Print an error message.

# === MAIN === # Main execution block of the script.
def main(): # Define the main function.
    print("🧹 Clearing Firestore collection…") # Print a message indicating collection clearing.
    delete_all_documents() # Call the function to delete all existing documents.
    print("\n🔄 Fetching feed…") # Print a message indicating feed fetching.
    items = fetch_feed() # Call the function to fetch items from the JSON feed.
    if not items: # Check if any items were fetched.
        print("   → No items found in feed.") # Print a message if no items are found.
        return # Exit the function if no items.
    print(f"   → {len(items)} items found. Processing…\n") # Print the number of items found and start processing message.
    process_items(items) # Call the function to process each item.
    print("\n✔️  Done.") # Print a completion message.

if __name__ == "__main__": # Standard Python idiom to check if the script is being run directly.
    main() # Call the main function to start the script execution.