import os
import json
import psycopg2
import numpy as np
from pymongo import MongoClient
from kafka import KafkaProducer
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Gemini client for embedding user search queries
genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 1. PostgreSQL Tool
def query_customer_orders(customer_id: str) -> str:
    """Queries Postgres to retrieve all recent orders and shipment statuses for a customer ID."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "enterprise_db"),
            user=os.getenv("POSTGRES_USER", "devuser"),
            password=os.getenv("POSTGRES_PASSWORD", "devpassword")
        )
        cur = conn.cursor()
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

        if not rows:
            return json.dumps({"status": "not_found", "message": f"No orders found for customer {customer_id}"})

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
        return json.dumps({"error": f"PostgreSQL query failed: {str(e)}"})

# 2. Vector Search (RAG) Tool using MongoDB + NumPy
def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def search_knowledge_base(query: str, product_filter: str = None) -> str:
    """Embeds user search query and performs cosine similarity search over MongoDB manual embeddings."""
    try:
        # Generate query embedding
        emb_res = genai_client.models.embed_content(
            model="gemini-embedding-001",
            contents=query
        )
        query_vector = emb_res.embeddings[0].values

        # Connect to MongoDB
        mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://devuser:devpassword@localhost:27017/"))
        db = mongo_client["enterprise_knowledge"]
        collection = db["product_docs"]

        mongo_filter = {}
        if product_filter:
            mongo_filter["product_name"] = product_filter

        docs = list(collection.find(mongo_filter))
        if not docs:
            return json.dumps({"status": "no_results", "message": "No documentation matching criteria."})

        # Score documents via Cosine Similarity
        scored_docs = []
        for doc in docs:
            score = cosine_similarity(query_vector, doc["embedding"])
            scored_docs.append({
                "product": doc["product_name"],
                "section": doc["section"],
                "text": doc["text"],
                "similarity_score": float(score)
            })

        # Sort descending by score and pick top match
        scored_docs.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_match = scored_docs[0]

        return json.dumps({
            "status": "success",
            "top_match": top_match
        })
    except Exception as e:
        return json.dumps({"error": f"Vector search failed: {str(e)}"})

# 3. Kafka Producer Tool
def escalate_to_human_agent(customer_id: str, issue_description: str, priority: str = "NORMAL") -> str:
    """Emits an escalation event to the Kafka 'support-tickets' topic."""
    try:
        producer = KafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )
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
        return json.dumps({"error": f"Kafka publish failed: {str(e)}"})