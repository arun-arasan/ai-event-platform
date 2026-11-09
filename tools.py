"""Utility tools for a support/operations assistant.

This module provides a small set of tool functions that the application can call to:
- fetch customer order information from PostgreSQL,
- perform semantic product-document lookup using MongoDB + embeddings,
- publish a support escalation event to Kafka.

The functions return JSON-encoded strings so they can be used easily by an agent or LLM
workflow that expects tool calls to return structured, machine-readable content.
"""

import os
import json
import psycopg2
import numpy as np
from pymongo import MongoClient
from kafka import KafkaProducer
from google import genai
from dotenv import load_dotenv

# Load environment variables from the local .env file so the tool functions can access
# database connection settings, API keys, and service endpoints without hardcoding them.
load_dotenv()

# Gemini client for embedding user search queries. This is reused by the vector search tool so
# we don't need to recreate a client every time we run a search.
genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# 1. PostgreSQL Tool
# This tool is responsible for customer support operations that require relational data.
# It fetches a customer's order history and shipping state from the PostgreSQL database.
def query_customer_orders(customer_id: str) -> str:
    """Query all orders and shipment statuses for a given customer ID.

    Returns a JSON string containing either:
    - a success payload with order details, or
    - a not_found message, or
    - an error payload if the database query fails.
    """
    try:
        # Connect to PostgreSQL using environment-configured values. This keeps the app
        # portable across local, staging, and production environments.
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "enterprise_db"),
            user=os.getenv("POSTGRES_USER", "devuser"),
            password=os.getenv("POSTGRES_PASSWORD", "devpassword")
        )

        # The cursor executes SQL statements and retrieves rows from the database.
        cur = conn.cursor()

        # Join the customers and orders tables to gather the customer's identity and records in
        # a single query. The %s placeholder is used to safely parameterize the customer ID.
        query = """
            SELECT c.name, c.email, c.tier, o.order_id, o.product_name, o.status, o.delivery_date
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            WHERE c.customer_id = %s;
        """
        cur.execute(query, (customer_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # If no rows match the customer, return a friendly "not found" result rather than an
        # empty or error response.
        if not rows:
            return json.dumps({"status": "not_found", "message": f"No orders found for customer {customer_id}"})

        # Normalize each database row into a clean, JSON-friendly dictionary for downstream use.
        orders = []
        for r in rows:
            orders.append({
                "customer_name": r[0],
                "customer_email": r[1],
                "tier": r[2],
                "order_id": r[3],
                "product_name": r[4],
                "order_status": r[5],
                "delivery_date": str(r[6])
            })
        return json.dumps({"status": "success", "orders": orders})
    except Exception as e:
        # Wrap database failures in JSON so the calling agent can understand the issue and react
        # without receiving a raw Python exception.
        return json.dumps({"error": f"PostgreSQL query failed: {str(e)}"})


# 2. Vector Search (RAG) Tool using MongoDB + NumPy
# This tool embeds the user's natural-language query, compares it to stored embeddings, and
# returns the most relevant product documentation text. This supports "search by meaning"
# instead of only exact keyword matching.
def cosine_similarity(a, b):
    """Compute cosine similarity between two numeric vectors."""
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def search_knowledge_base(query: str, product_filter: str = None) -> str:
    """Embed a query and rank document matches in MongoDB by semantic similarity.

    The function takes a search phrase and optionally narrows results to a product family,
    then returns the best matching document chunk with its similarity score.
    """
    try:
        # Generate a vector embedding for the incoming search query using the same Gemini model
        # that was used to create the product document embeddings in the MongoDB collection.
        emb_res = genai_client.models.embed_content(
            model="gemini-embedding-001",
            contents=query
        )
        query_vector = emb_res.embeddings[0].values

        # Connect to MongoDB to inspect the product knowledge base.
        mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
        db = mongo_client["enterprise_knowledge"]
        collection = db["product_docs"]

        # Build a filter when the caller specifies a product, allowing context-limited searches.
        mongo_filter = {}
        if product_filter:
            mongo_filter["product_name"] = product_filter

        # Pull all candidate documents for the given filter. These are the text chunks that may
        # match the user's question semantically.
        docs = list(collection.find(mongo_filter))
        if not docs:
            return json.dumps({"status": "no_results", "message": "No documentation matching criteria."})

        # Score documents via cosine similarity. The closer the query vector is to a document
        # vector, the more semantically relevant the text block is likely to be.
        scored_docs = []
        for doc in docs:
            score = cosine_similarity(query_vector, doc["embedding"])
            scored_docs.append({
                "product": doc["product_name"],
                "section": doc["section"],
                "text": doc["text"],
                "similarity_score": float(score)
            })

        # Sort descending by score and select the best match to return to the caller.
        scored_docs.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_match = scored_docs[0]

        return json.dumps({
            "status": "success",
            "top_match": top_match
        })
    except Exception as e:
        # Return any failure as structured JSON instead of throwing raw exceptions to the agent.
        return json.dumps({"error": f"Vector search failed: {str(e)}"})


# 3. Kafka Producer Tool
# This tool is used when a support issue requires human intervention. It emits a structured
# event to Kafka so downstream operational systems can create or assign a ticket.
def escalate_to_human_agent(customer_id: str, issue_description: str, priority: str = "NORMAL") -> str:
    """Publish a human-escalation event to Kafka for a customer support issue."""
    try:
        # Kafka producer sends event data as JSON bytes to the support-tickets topic.
        producer = KafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )

        # The payload contains the core incident metadata a support team would need to triage.
        event_payload = {
            "event_type": "SUPPORT_TICKET_ESCALATED",
            "customer_id": customer_id,
            "issue": issue_description,
            "priority": priority
        }
        producer.send("support-tickets", value=event_payload)
        producer.flush()
        producer.close()

        return json.dumps({
            "status": "escalated",
            "topic": "support-tickets",
            "event": event_payload
        })
    except Exception as e:
        # If Kafka is unavailable or misconfigured, return a structured error so callers can
        # decide whether to retry later or handle the escalation another way.
        return json.dumps({"error": f"Kafka publish failed: {str(e)}"})
