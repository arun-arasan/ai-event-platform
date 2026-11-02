import os
from dotenv import load_dotenv
from google import genai
from pymongo import MongoClient

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing in .env file.")

client = genai.Client(api_key=api_key)

PRODUCT_MANUALS = [
    {
        "product_name": "Smart Home Hub Pro",
        "section": "Reset Instructions",
        "text": "To perform a factory reset on the Smart Home Hub Pro, press and hold the pinhole reset button located at the bottom of the device for 10 seconds. The LED ring will cycle amber three times before turning solid blue, indicating reset completion."
    },
    {
        "product_name": "Smart Home Hub Pro",
        "section": "Wi-Fi Connectivity Troubleshooting",
        "text": "If the Smart Home Hub Pro loses Wi-Fi connection, verify that the 2.4GHz network band is active on your router. The hub does not operate on 5GHz-only networks. Power cycle the hub by disconnecting power for 15 seconds."
    },
    {
        "product_name": "Ultra HD Security Cam",
        "section": "MicroSD Storage Setup",
        "text": "The Ultra HD Security Cam supports UHS-I Class 10 MicroSD cards up to 256GB. Format the card in FAT32 or exFAT format before inserting. Turn off the camera before inserting or removing the card to prevent file corruption."
    },
    {
        "product_name": "Wireless Mesh Node",
        "section": "Pairing Secondary Nodes",
        "text": "To link an additional Wireless Mesh Node to an existing network, position the node within 10 feet of the main router. Press the sync button on the rear for 3 seconds until the front LED pulses green, then initiate discovery in the companion app."
    }
]

def seed_mongo():
    mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://devuser:devpassword@localhost:27017/"))
    db = mongo_client["enterprise_knowledge"]
    collection = db["product_docs"]

    collection.delete_many({})
    print("Cleared existing documents from MongoDB collection 'product_docs'.")

    # Target the current embedding model
    embedding_model = "gemini-embedding-001"
    print(f"Generating embeddings using model: {embedding_model}...")

    records_to_insert = []
    for doc in PRODUCT_MANUALS:
        response = client.models.embed_content(
            model=embedding_model,
            contents=doc["text"]
        )
        
        embedding_vector = response.embeddings[0].values
        
        doc_record = {
            "product_name": doc["product_name"],
            "section": doc["section"],
            "text": doc["text"],
            "embedding": embedding_vector
        }
        records_to_insert.append(doc_record)

    collection.insert_many(records_to_insert)
    print(f"Successfully stored {len(records_to_insert)} documents with vector embeddings in MongoDB.")

if __name__ == "__main__":
    seed_mongo()