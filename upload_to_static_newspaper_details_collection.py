# ===================================================================
# === upload_newspaper_details.py                             ===
# === A one-time script to populate the newspaper_details collection ===
# ===================================================================

import firebase_admin
from firebase_admin import credentials, firestore

# --- Configuration ---
# Ensure this matches your main script and your service account file name.
SERVICE_ACCOUNT_PATH = "service-account.json"
DETAILS_COLLECTION_NAME = "newspaper_details" 

# --- The Data to Upload ---
# This is the master list of all newspaper meta-data.
NEWSPAPER_DATA = {
    "sun": {
        "ownedBy1": "News UK", "ownedBy2": "News Corp", "ownedBy3": "Murdoch Family",
        "format": "Tabloid", "style": "Tabloid", "leaning": "Right-wing populist",
        "readershipDemographics": "Predominantly working-class, older males, lower educational attainment."
    },
    "mail": {
        "ownedBy1": "DMG Media", "ownedBy2": "Daily Mail and General Trust (DMGT)", "ownedBy3": "Harmsworth Family",
        "format": "Tabloid", "style": "Tabloid", "leaning": "Traditionalist right-wing",
        "readershipDemographics": "Middle-class to upper-middle-class, older readers (50+), strong female readership."
    },
    "metro": {
        "ownedBy1": "DMG Media", "ownedBy2": "DMGT", "ownedBy3": "Harmsworth Family",
        "format": "Tabloid", "style": "Tabloid", "leaning": "Politically neutral-lite",
        "readershipDemographics": "Young urban commuters (18–40), students and early-career workers."
    },
    "mirror": {
        "ownedBy1": "Reach Plc", "ownedBy2": None, "ownedBy3": None,
        "format": "Tabloid", "style": "Tabloid", "leaning": "Centre-left",
        "readershipDemographics": "Working-class, older Labour voters, Northern and Midlands stronghold."
    },
    "times": {
        "ownedBy1": "News UK", "ownedBy2": "News Corp", "ownedBy3": "Murdoch Family",
        "format": "Compact", "style": "Broadsheet", "leaning": "Centre-right",
        "readershipDemographics": "Upper-middle-class professionals, high educational attainment, policy-focused voters."
    },
    "telegraph": {
        "ownedBy1": "Telegraph Media Group (TMG)", "ownedBy2": "Press Holdings", "ownedBy3": "Barclay Family",
        "format": "Broadsheet", "style": "Hybrid", "leaning": "Right-wing",
        "readershipDemographics": "Wealthy, older (50+), business-owning and retired professionals."
    },
    "express": {
        "ownedBy1": "Reach Plc", "ownedBy2": None, "ownedBy3": None,
        "format": "Tabloid", "style": "Tabloid", "leaning": "Populist right-wing",
        "readershipDemographics": "Older readers (60+), C2DE classes, strongly pro-Brexit."
    },
    "star": {
        "ownedBy1": "Reach Plc", "ownedBy2": None, "ownedBy3": None,
        "format": "Tabloid", "style": "Tabloid", "leaning": "Apolitical",
        "readershipDemographics": "Younger working-class readers, male-skewed, interested in sport/celebrity."
    },
    "i": {
        "ownedBy1": "DMG Media", "ownedBy2": "DMGT", "ownedBy3": "Harmsworth Family",
        "format": "Compact", "style": "Broadsheet", "leaning": "Centrist",
        "readershipDemographics": "Educated, urban, middle-class professionals, politically engaged centrists."
    },
    "guardian": {
        "ownedBy1": "Guardian News & Media", "ownedBy2": "Scott Trust", "ownedBy3": None,
        "format": "Tabloid", "style": "Broadsheet", "leaning": "Progressive left",
        "readershipDemographics": "Highly educated, younger (25–45), middle-class, urban/metropolitan."
    },
    "observer": { # Sunday edition of The Guardian
        "ownedBy1": "Guardian News & Media", "ownedBy2": "Scott Trust", "ownedBy3": None,
        "format": "Tabloid", "style": "Broadsheet", "leaning": "Centre-left",
        "readershipDemographics": "Liberal professionals, Guardian-adjacent readers, Sunday political readers."
    },
    "financial": {
        "ownedBy1": "The Financial Times Ltd", "ownedBy2": "Nikkei Inc.", "ownedBy3": None,
        "format": "Broadsheet", "style": "Broadsheet", "leaning": "Economic centre-right",
        "readershipDemographics": "Senior professionals, business and finance elite, high income, international."
    },
    "ft": { # Weekend edition of the Financial Times
        "ownedBy1": "The Financial Times Ltd", "ownedBy2": "Nikkei Inc.", "ownedBy3": None,
        "format": "Broadsheet", "style": "Broadsheet", "leaning": "Economic centre-right",
        "readershipDemographics": "Senior professionals, business and finance elite, high income, international."
    },
    "independent": {
        "ownedBy1": "Independent Digital News & Media Ltd", "ownedBy2": "Lebedev Family", "ownedBy3": None,
        "format": "Digital-only", "style": "Broadsheet", "leaning": "Centre-left liberal",
        "readershipDemographics": "Young professionals, digital-native readers (20s–40s)."
    }
}


### PASTE THIS MODIFIED FUNCTION INTO YOUR SCRIPT ###

def upload_details():
    """Connects to Firebase and uploads the newspaper data."""
    try:
        # --- Initialize Firebase ---
        if not firebase_admin._apps:
            # CHECKPOINT 1: We should see this immediately.
            print("Attempting to load credentials from service-account.json...")
            cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
            
            # CHECKPOINT 2: This is where it's likely getting stuck.
            print("Credentials loaded. Attempting to initialize Firebase app (this is the network call)...")
            firebase_admin.initialize_app(cred)
            
            # CHECKPOINT 3: If you see this, the problem is elsewhere (unlikely).
            print("Firebase app initialized successfully!")
        
        db = firestore.client()
        collection_ref = db.collection(DETAILS_COLLECTION_NAME)
        
        print(f"Starting upload to '{DETAILS_COLLECTION_NAME}' collection...")

        for doc_id, data in NEWSPAPER_DATA.items():
            doc_ref = collection_ref.document(doc_id)
            doc_ref.set(data)
            print(f"  ✅ Successfully uploaded details for: {doc_id}")
            
        print("\n✔️ Upload complete.")

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        print("Please ensure your 'service-account.json' file is in the correct directory and has the right permissions.")


# --- Main execution block ---
if __name__ == "__main__":
    upload_details()