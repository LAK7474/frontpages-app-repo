# ===================================================================================
# === upload_newspaper_details.py                                                 ===
# === A one-time script to populate the newspaper_details collection              ===
# === WITH THE USER'S ORIGINAL, CURATED DATA RESTORED                             ===
# ===================================================================================

import firebase_admin
from firebase_admin import credentials, firestore
import os

# --- Configuration ---
# Get the directory where THIS script is located.
script_dir = os.path.dirname(os.path.abspath(__file__))
# Join that directory path with the filename to get a full, absolute path.
SERVICE_ACCOUNT_PATH = os.path.join(script_dir, "service-account.json")
DETAILS_COLLECTION_NAME = "newspaper_details" 

# --- The Data to Upload (RESTORED TO YOUR ORIGINAL TEXT) ---
NEWSPAPER_DATA = {
    "sun": {
        "ownedBy1": "News UK", "ownedBy2": "News Corp", "ownedBy3": "Murdoch Family",
        "format": "Tabloid", "style": "Tabloid", "leaning": "Right-wing populist, pro-Conservative, strongly pro-Brexit",
        "readershipDemographics": "Predominantly working-class, older males, lower educational attainment, strong in Midlands and North, high Leave vote areas, traditionally Labour but socially conservative"
    },
    "mail": {
        "ownedBy1": "DMG Media", "ownedBy2": "Daily Mail and General Trust (DMGT)", "ownedBy3": "Harmsworth Family",
        "format": "Tabloid", "style": "Tabloid", "leaning": "Traditionalist right-wing, anti-woke, socially conservative, pro-Tory",
        "readershipDemographics": "Middle-class to upper-middle-class, older readers (50+), suburban and rural England, strong female readership, southern bias, Conservative voters"
    },
    "metro": {
        "ownedBy1": "DMG Media", "ownedBy2": "DMGT", "ownedBy3": "Harmsworth Family",
        "format": "Tabloid", "style": "Tabloid", "leaning": "Politically neutral-lite, apolitical tone, low editorialising",
        "readershipDemographics": "Young urban commuters (18–40), students and early-career workers, multicultural cities, London-heavy, politically mixed"
    },
    "mirror": {
        "ownedBy1": "Reach Plc", "ownedBy2": None, "ownedBy3": None,
        "format": "Tabloid", "style": "Tabloid", "leaning": "Centre-left, Labour-supporting, socially liberal, working-class focus",
        "readershipDemographics": "Working-class, older Labour voters, Northern and Midlands stronghold, traditionally unionist, mixed education levels"
    },
    "times": {
        "ownedBy1": "News UK", "ownedBy2": "News Corp", "ownedBy3": "Murdoch Family",
        "format": "Compact (Tabloid-sized)", "style": "Broadsheet", "leaning": "Centre-right, establishment conservative, fiscally right-leaning, socially moderate",
        "readershipDemographics": "Upper-middle-class professionals, high educational attainment, London and Home Counties, older (40+), policy-focused Conservative/Lib Dem voters"
    },
    "telegraph": {
        "ownedBy1": "Telegraph Media Group (TMG)", "ownedBy2": "Press Holdings", "ownedBy3": "Barclay Family",
        "format": "Broadsheet", "style": "Tabloid-broadsheet hybrid", "leaning": "Right-wing, pro-Conservative, free-market, anti-EU, culture war emphasis",
        "readershipDemographics": "Wealthy, older (50+), business-owning and retired professionals, Home Counties, rural South, pro-Brexit Conservative voters"
    },
    "express": {
        "ownedBy1": "Reach Plc", "ownedBy2": None, "ownedBy3": None,
        "format": "Tabloid", "style": "Tabloid", "leaning": "Populist right-wing, pro-Brexit, anti-immigration, nationalist tone",
        "readershipDemographics": "Older readers (60+), C2DE classes, Midlands, South-West, strongly pro-Brexit, nostalgic patriotic tone"
    },
    "star": {
        "ownedBy1": "Reach Plc", "ownedBy2": None, "ownedBy3": None,
        "format": "Tabloid", "style": "Tabloid", "leaning": "Apolitical in tone, entertainment-heavy, occasionally anti-elitist",
        "readershipDemographics": "Younger working-class readers, male-skewed, interested in sport/celebrity, low political engagement, North and Midlands"
    },
    "i": {
        "ownedBy1": "DMG Media", "ownedBy2": "DMGT", "ownedBy3": "Harmsworth Family",
        "format": "Compact (Tabloid-sized)", "style": "Broadsheet", "leaning": "Centrist to centre-left, balanced reporting, policy-focused",
        "readershipDemographics": "Educated, urban, middle-class professionals, politically engaged centrists, high digital uptake, London and university cities"
    },
    "guardian": {
        "ownedBy1": "Guardian News & Media", "ownedBy2": "Scott Trust", "ownedBy3": None,
        "format": "Tabloid", "style": "Broadsheet", "leaning": "Progressive left, pro-Labour/Green, socially liberal, pro-migrant, critical of capitalism",
        "readershipDemographics": "Highly educated, younger (25–45), middle-class, urban/metropolitan, public sector, arts, and academia-heavy, Remain voters"
    },
    "observer": { # Sunday edition of The Guardian
        "ownedBy1": "Guardian News & Media", "ownedBy2": "Scott Trust", "ownedBy3": None,
        "format": "Tabloid", "style": "Broadsheet", "leaning": "Centre-left to left-liberal, pro-Labour, strongly socially liberal",
        "readershipDemographics": "Liberal professionals, Guardian-adjacent readers, Sunday political readers, older than weekday Guardian, middle-class"
    },
    "financial": {
        "ownedBy1": "The Financial Times Ltd", "ownedBy2": "Nikkei Inc.", "ownedBy3": None,
        "format": "Broadsheet", "style": "Broadsheet", "leaning": "Economic centre-right, pro-business, socially liberal, pro-EU/globalist",
        "readershipDemographics": "Senior professionals, business and finance elite, City of London, high income, international readership, Oxbridge/LSE educated"
    },
    "ft": { # Weekend edition of the Financial Times
        "ownedBy1": "The Financial Times Ltd", "ownedBy2": "Nikkei Inc.", "ownedBy3": None,
        "format": "Broadsheet", "style": "Broadsheet", "leaning": "Economic centre-right, pro-business, socially liberal, pro-EU/globalist",
        "readershipDemographics": "Senior professionals, business and finance elite, City of London, high income, international readership, Oxbridge/LSE educated"
    },
    "independent": {
        "ownedBy1": "Independent Digital News & Media Ltd", "ownedBy2": "Lebedev Family", "ownedBy3": None,
        "format": "Digital-only", "style": "Broadsheet", "leaning": "Centre-left liberal, pro-EU, socially progressive, metropolitan outlook",
        "readershipDemographics": "Young professionals, digital-native readers (20s–40s), educated, urban, socially progressive, Remain voters"
    }
}


def upload_details():
    """Connects to Firebase and uploads the newspaper data."""
    try:
        # --- Initialize Firebase ---
        if not firebase_admin._apps:
            cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        collection_ref = db.collection(DETAILS_COLLECTION_NAME)
        
        print(f"Starting upload to '{DETAILS_COLLECTION_NAME}' collection...")

        for doc_id, data in NEWSPAPER_DATA.items():
            doc_ref = collection_ref.document(doc_id)
            doc_ref.set(data)
            print(f"  ✅ Successfully uploaded details for: {doc_id}")
            
        print("\n✔️ Upload complete. Your original wording has been restored in Firestore.")

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        print("Please ensure your 'service-account.json' file is in the correct directory and has the right permissions.")


# --- Main execution block ---
if __name__ == "__main__":
    upload_details()