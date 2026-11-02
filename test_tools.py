from tools import query_customer_orders, search_knowledge_base, escalate_to_human_agent

print("--- Testing Postgres Tool ---")
print(query_customer_orders("CUST-101"))

print("\n--- Testing Vector RAG Tool ---")
print(search_knowledge_base("how to reset my hub to factory default"))

print("\n--- Testing Kafka Tool ---")
print(escalate_to_human_agent("CUST-101", "Hardware blinking red, factory reset failed", priority="HIGH"))