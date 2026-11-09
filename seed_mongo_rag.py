"""Seed MongoDB with product documentation and vector embeddings.

This script loads a small set of product manuals into a MongoDB collection that is
optimized for semantic retrieval. Each text block is converted into a vector embedding
using Google's Gemini embedding model so the documents can later be searched by
meaning rather than exact keyword matches.

The script is designed to be run as a one-time data initialization step. It clears any
existing records in the target collection before repopulating it with fresh embeddings.

This file acts as the knowledge-base bootstrap for a retrieval-augmented generation (RAG)
workflow. In production, the source documents would usually come from a CMS, product
portal, or an upstream ingestion pipeline, but this script keeps it simple by storing a small
curated set of product documentation in memory and turning it into searchable vectors.
"""

import os
from dotenv import load_dotenv
from google import genai
from pymongo import MongoClient

# Load environment variables from a local .env file so API keys and connection strings can
# be managed outside of source control and adjusted per environment without code changes.
load_dotenv()

# Validate that the Gemini API key is configured before creating the client. This fails fast
# and gives a clear error message if the environment has not been set up correctly.
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing in .env file.")

# Create the Gemini client used for embedding generation. The client handles the API
# authentication and request creation details for us so the rest of the script can focus on
# the knowledge-base logic instead of HTTP details.
client = genai.Client(api_key=api_key)

# This list represents the product knowledge base to be vectorized. Each item contains a
# product name, a section heading, and the text content that should be searchable later.
# In a real production system, this list could be loaded from a database, JSON file, or
# user-provided product documentation set.
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
    """Populate the MongoDB collection with embedded product documentation.

    The workflow is:
    1. Open the MongoDB connection and select the target database/collection.
    2. Clear any stale records so the collection reflects the latest data set.
    3. Generate embeddings for each product text block using the Gemini embedding API.
    4. Store the original metadata and the vector embedding together in a single document.

    This function is meant to be run as a one-time data-loading script, not during normal app
    runtime. That makes it easy to refresh the local knowledge base when documentation changes.
    """
    # Connect to MongoDB using either a configured MONGO_URI value or the local default.
    # This script assumes a MongoDB instance is running on localhost and using the default
    # port, which is typical for local development of a vector-search prototype.
    mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))

    # Use a dedicated database and collection for product knowledge so the data is isolated
    # from unrelated application data and remains easy to query during retrieval experiments.
    db = mongo_client["enterprise_knowledge"]
    collection = db["product_docs"]

    # Remove any previous seed data before loading the new corpus. This ensures the vector
    # search index stays in sync with the current product documentation set and avoids stale
    # search results from earlier runs.
    collection.delete_many({})
    print("Cleared existing documents from MongoDB collection 'product_docs'.")

    # The embedding model must be one that Gemini supports for vector generation. Using a
    # consistent model name keeps the stored embeddings compatible with downstream retrieval
    # calls and allows for predictable performance characteristics.
    embedding_model = "gemini-embedding-001"
    print(f"Generating embeddings using model: {embedding_model}...")

    # Accumulate the records in memory before the bulk insert so we can perform one database
    # write instead of many small writes. This is simple and efficient for small seed sets.
    records_to_insert = []

    # Convert each manual entry into a MongoDB document that includes both the source text
    # and the generated vector. This allows us to retrieve the original context when a search
    # result is returned by the RAG system.
    for doc in PRODUCT_MANUALS:
        # Ask the Gemini API to generate an embedding for the text content only. The vector
        # representation captures the semantic meaning of the content, not just literal words.
        response = client.models.embed_content(
            model=embedding_model,
            contents=doc["text"]
        )

        # The embedding API returns a structured response whose first element contains the
        # vector values. These numeric values are stored in MongoDB so they can be used for
        # similarity search later.
        embedding_vector = response.embeddings[0].values

        # Each MongoDB record stores the metadata (product name and section) alongside the
        # original source text and the generated embedding. This makes the document useful
        # both for display and for vector search/retrieval workflows.
        doc_record = {
            "product_name": doc["product_name"],
            "section": doc["section"],
            "text": doc["text"],
            "embedding": embedding_vector
        }
        records_to_insert.append(doc_record)

    # Insert the batch as a single operation for efficiency. This is ideal for a seed script
    # that initializes a small set of knowledge base documents.
    collection.insert_many(records_to_insert)
    print(f"Successfully stored {len(records_to_insert)} documents with vector embeddings in MongoDB.")


if __name__ == "__main__":
    # Run the seeding process when this script is executed directly.
    seed_mongo()
