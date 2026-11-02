import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Import the underlying tools
import tools

load_dotenv()

# Map tool names to actual functions for dynamic dispatch
TOOL_REGISTRY = {
    "query_customer_orders": tools.query_customer_orders,
    "search_knowledge_base": tools.search_knowledge_base,
    "escalate_to_human_agent": tools.escalate_to_human_agent,
}

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
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Register the tools with Gemini
    tool_declarations = [
        tools.query_customer_orders,
        tools.search_knowledge_base,
        tools.escalate_to_human_agent,
    ]

    # Initialize a multi-turn chat session with tools enabled
    chat = client.chats.create(
        model="gemini-3.8-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2,
            tools=tool_declarations,
        ),
    )

    full_prompt = f"[Context: Logged-in Customer ID is {customer_id}]\nUser: {user_prompt}"
    print(f"\nUser Query: {user_prompt}")
    print("-" * 60)

    # First turn: Send user input to Gemini
    response = chat.send_message(full_prompt)

    # Agent Loop: Handle multi-step tool calls
    while response.function_calls:
        for function_call in response.function_calls:
            func_name = function_call.name
            func_args = function_call.args
            
            print(f"[Agent Decision] -> Calling tool: {func_name} with args: {dict(func_args)}")

            # Execute the matching tool from our registry
            tool_fn = TOOL_REGISTRY.get(func_name)
            if tool_fn:
                tool_output_str = tool_fn(**func_args)
                try:
                    tool_output_dict = json.loads(tool_output_str)
                except Exception:
                    tool_output_dict = {"raw_output": tool_output_str}
            else:
                tool_output_dict = {"error": f"Function {func_name} not found"}

            print(f"[Tool Execution] -> Returned: {str(tool_output_dict)[:120]}...")

            # Send tool output back to Gemini
            response = chat.send_message(
                types.Part.from_function_response(
                    name=func_name,
                    response=tool_output_dict
                )
            )

    print("-" * 60)
    print(f"Agent Response:\n{response.text}\n")
    return response.text

if __name__ == "__main__":
    # Test Scenario 1: Multi-tool reasoning (Postgres Order check + RAG Manual Search)
    run_agent_interaction(
        user_prompt="I ordered a Smart Home Hub Pro. What's its delivery status, and how do I do a factory reset once it arrives?",
        customer_id="CUST-101"
    )

    # Test Scenario 2: Event-driven escalation to Kafka
    run_agent_interaction(
        user_prompt="I tried resetting my device twice and it started smoking. I want to talk to a manager immediately!",
        customer_id="CUST-101"
    )