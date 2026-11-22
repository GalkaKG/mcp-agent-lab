from mcp.server import MCPServer
from datetime import datetime
import statistics
import pandas as pd
from io import StringIO


# Initialize MCP Server
mcp = MCPServer("SmartTools")

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract the second number from the first."""
    return a - b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> str:
    """Divide the first number by the second."""
    if b == 0:
        return "Error: Cannot divide by zero."

    return str(a / b)


@mcp.tool()
def get_current_datetime() -> str:
    """Get the current local date and time."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


@mcp.tool()
def calculate_statistics(numbers: list[float]) -> dict:
    """
    Calculate descriptive statistics for a list of numbers.

    Returns count, mean, median, minimum, maximum
    and population standard deviation.
    """
    if not numbers:
        return {"error": "The list cannot be empty."}

    return {
        "count": len(numbers),
        "mean": statistics.mean(numbers),
        "median": statistics.median(numbers),
        "minimum": min(numbers),
        "maximum": max(numbers),
        "standard_deviation": statistics.pstdev(numbers)
    }


@mcp.tool()
def analyze_csv(csv_content: str) -> dict:
    """
    Analyze CSV data and return basic information.
    Use \\n to separate rows.
    """

    # Convert escaped newline characters into actual line breaks
    csv_text = csv_content.replace("\\n", "\n")

    df = pd.read_csv(StringIO(csv_text))

    if df.empty:
        return {"error": "CSV contains no data rows."}

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": df.columns.tolist()
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")
    import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# =====================================================
# CONFIGURATION
# =====================================================

MODEL = "qwen3:8b"

OLLAMA_URL = "http://localhost:11434/api/chat"

MAX_TOOL_CALLS = 10

# Conversation memory: how many recent user turns to keep
MAX_HISTORY_TURNS = 10

SYSTEM_PROMPT = (
    "You are a helpful AI data assistant. "
    "You have access to external tools through MCP. "
    "Use tools whenever they are necessary to answer "
    "the user's request. "
    "Never invent tool results. "
    "After receiving tool results, explain them clearly."
)

# Locate MCP Server independently of the working directory
BASE_DIR = Path(__file__).resolve().parent

SERVER_PATH = BASE_DIR.parent / "MCP Server" / "server.py"


# =====================================================
# CONVERT MCP TOOLS TO OLLAMA TOOLS
# =====================================================

def convert_tools(mcp_tools):

    ollama_tools = []

    for tool in mcp_tools:

        ollama_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema
            }
        })

    return ollama_tools


# =====================================================
# EXTRACT MCP TOOL RESULT
# =====================================================

def extract_tool_result(result):

    if getattr(result, "isError", False):
        return {
            "error": True,
            "message": "MCP tool execution failed."
        }

    structured = getattr(result, "structuredContent", None)

    if structured is not None:
        return structured

    content = []

    for item in result.content:

        if hasattr(item, "text"):
            content.append(item.text)

    if len(content) == 1:
        return content[0]

    return content


# =====================================================
# EXECUTE MCP TOOL
# =====================================================

async def execute_tool(session, tool_name, arguments):

    print(f"\n[TOOL CALL] {tool_name}")
    print(f"[ARGUMENTS] {arguments}")

    result = await session.call_tool(
        tool_name,
        arguments=arguments
    )

    output = extract_tool_result(result)

    print(f"[TOOL RESULT] {output}")

    return output


# =====================================================
# CONVERSATION MEMORY
# =====================================================

def new_history():
    """Create a fresh conversation containing only the system prompt."""
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def trim_history(messages):
    """
    Keep the system prompt and only the last MAX_HISTORY_TURNS user turns.
    Trimming always starts at a user message, so an assistant tool call
    is never separated from its tool result.
    """
    user_positions = [
        i for i, m in enumerate(messages) if m["role"] == "user"
    ]

    if len(user_positions) <= MAX_HISTORY_TURNS:
        return messages

    start = user_positions[-MAX_HISTORY_TURNS]

    return [messages[0]] + messages[start:]


# =====================================================
# AI AGENT LOOP
# =====================================================

async def run_agent(session, http_client, messages, user_message, ollama_tools):

    # Add the new request to the shared conversation history
    messages.append({
        "role": "user",
        "content": user_message
    })

    # Drop the oldest turns (in place, so the caller sees the change)
    messages[:] = trim_history(messages)

    for iteration in range(MAX_TOOL_CALLS):

        print("\n[LLM] Sending request to Qwen3...")

        response = await http_client.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": messages,
                "tools": ollama_tools,
                "stream": False
            }
        )

        response.raise_for_status()

        data = response.json()

        assistant_message = data["message"]

        messages.append(assistant_message)

        tool_calls = assistant_message.get("tool_calls", [])

        # No more tools required
        if not tool_calls:

            print("\n[FINAL ANSWER]\n")

            print(assistant_message.get("content", ""))

            return

        # Execute requested tools
        for tool_call in tool_calls:

            function = tool_call["function"]

            tool_name = function["name"]

            arguments = function.get("arguments", {})

            if isinstance(arguments, str):
                arguments = json.loads(arguments)

            try:

                result = await execute_tool(
                    session,
                    tool_name,
                    arguments
                )

            except Exception as error:

                result = {
                    "error": str(error)
                }

            messages.append({
                "role": "tool",
                "name": tool_name,
                "content": json.dumps(
                    result,
                    ensure_ascii=False,
                    default=str
                )
            })

    print("\nMaximum tool iterations reached.")


# =====================================================
# MAIN
# =====================================================

async def main():

    if not SERVER_PATH.exists():
        raise FileNotFoundError(
            f"MCP Server not found: {SERVER_PATH}"
        )

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        env=os.environ.copy()
    )

    print("=" * 55)
    print("LOCAL MCP AI AGENT")
    print("=" * 55)

    print(f"Model: {MODEL}")
    print(f"MCP Server: {SERVER_PATH}")

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            print("\n[MCP] Connected successfully!")

            tools_result = await session.list_tools()

            ollama_tools = convert_tools(tools_result.tools)

            print("\nAvailable tools:")

            for tool in ollama_tools:

                name = tool["function"]["name"]

                print(f" - {name}")

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(180.0, connect=10.0)
            ) as http_client:

                print("\n[OLLAMA] Connecting to Qwen3...")

                health_check = await http_client.get(
                    "http://localhost:11434/api/tags"
                )

                health_check.raise_for_status()

                print("[OLLAMA] Connected successfully!")

                print("\nType 'exit' to quit, 'reset' to clear memory.")

                # One conversation history for the whole session
                messages = new_history()

                while True:

                    user_message = input("\nYou: ").strip()

                    if user_message.lower() in ("exit", "quit"):
                        break

                    if not user_message:
                        continue

                    if user_message.lower() == "reset":
                        messages = new_history()
                        print("[MEMORY] Conversation cleared.")
                        continue

                    await run_agent(
                        session,
                        http_client,
                        messages,
                        user_message,
                        ollama_tools
                    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
    asyncio.run(main())
