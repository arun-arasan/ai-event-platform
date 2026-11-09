"""AI customer support agent for enterprise product support workflows.

This module orchestrates a support interaction by combining:
- relational customer-order lookups via PostgreSQL,
- semantic technical troubleshooting via a MongoDB vector database,
- human escalation via Kafka when the issue requires intervention.

The agent uses Gemini's function-calling behavior to decide which tool to invoke based on the
user's request, while keeping the actual logic in separate utility functions for clarity and
reusability.
"""

import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Import the support tools that provide the agent's data and action capabilities.
import tools

# Load environment variables for API configuration before creating the Gemini client.
load_dotenv()

# System instruction that defines the operating policy for the support agent. These rules tell
# the model which tool to call depending on the user request, and they emphasize grounding the
# response in retrieved tool output rather than inventing unsupported details.
SYSTEM_INSTRUCTION = """
You are an Enterprise AI Customer Support Agent with direct access to database records, 
a vector knowledge base of technical manuals, and an event-driven Kafka escalation broker.

Operating Rules:
1. When a user asks about order status, tracking, or delivery, call 'query_customer_orders'.
2. When a user asks technical questions, troubleshooting steps, or device setup instructions, call 'search_knowledge_base'.
3. If an issue cannot be resolved using the knowledge base, or if the user asks for a refund/human representative, call 'escalate_to_human_agent'.
4. Ground your answers strictly in the tool outputs. Do not invent order numbers or manual instructions.
"""


def run_agent_interaction(user_prompt: str, customer_id: str = "CUST-101"):
    """Run a full support-agent interaction for a single user prompt.

    The function does three main things:
    1. builds a Gemini client configured with the support tools,
    2. sends the user's request with customer context included,
    3. prints and returns the final response.
    """
    # Create a Gemini client using the API key from the environment. This client is responsible
    # for the model call, tool invocation, and chat state.
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Supply native Python functions directly as callable tools. Gemini's automatic function
    # calling can invoke these functions during the chat turn and pass back their outputs.
    tool_declarations = [
        tools.query_customer_orders,
        tools.search_knowledge_base,
        tools.escalate_to_human_agent,
    ]

    # Attach the current customer context to the prompt so the agent can answer with the correct
    # account identity while still following the general operating rules.
    full_prompt = f"[Context: Logged-in Customer ID is {customer_id}]\nUser: {user_prompt}"
    print(f"\nUser Query: {user_prompt}")
    print("-" * 60)

    # Create a chat session with the support rules embedded in the system instruction and the
    # tools available for function calling. This allows the model to reason over a user request
    # and decide when to query the database or search the knowledge base.
    chat = client.chats.create(
        model="gemini-3.8-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.1,
            tools=tool_declarations,
        ),
    )

    # Send the full prompt to the model, which may invoke tool calls before producing a final
    # textual answer. We then print the result and return it to the caller.
    response = chat.send_message(full_prompt)

    print("-" * 60)
    print(f"Agent Final Response:\n{response.text}\n")
    return response.text


if __name__ == "__main__":
    # Test Scenario 1: Multi-tool reasoning (Postgres Order check + RAG Manual Search)
    # This scenario demonstrates the agent combining order lookup and technical troubleshooting
    # information in a single user request.
    run_agent_interaction(
        user_prompt="I ordered a Smart Home Hub Pro. What's its delivery status, and how do I do a factory reset once it arrives?",
        customer_id="CUST-101"
    )

    # Test Scenario 2: Event-driven escalation to Kafka
    # This scenario shows the agent escalating a serious support issue to a human support flow.
    run_agent_interaction(
        user_prompt="I tried resetting my device twice and it started smoking. I want to talk to a manager immediately!",
        customer_id="CUST-101"
    )
