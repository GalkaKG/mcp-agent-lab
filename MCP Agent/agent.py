import asyncio
import json
import os
import re
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

# Persistent memory: conversation is saved here after every request
MEMORY_FILE = BASE_DIR / "memory.json"


# =====================================================
# HELPERS
# =====================================================

def strip_thinking(text):
    """Remove the <think>...</think> reasoning block that Qwen3 may add."""
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()


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


def save_history(messages):
    """
    Save the conversation to MEMORY_FILE.
    Writes to a temporary file first, so a crash during saving
    cannot corrupt the existing memory.
    """
    temp_file = MEMORY_FILE.with_suffix(".tmp")

    try:
        temp_file.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8"
        )
        temp_file.replace(MEMORY_FILE)

    except OSError as error:
        print(f"[MEMORY] Could not save memory: {error}")


def load_history():
    """
    Load the saved conversation, or start a new one if there is none.
    A damaged memory file is renamed to memory.json.bak, not deleted.
    """
    if not MEMORY_FILE.exists():
        return new_history()

    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))

        if not isinstance(data, list) or not all(
            isinstance(m, dict) and "role" in m for m in data
        ):
            raise ValueError("unexpected memory file format")

    except (OSError, ValueError) as error:
        backup = MEMORY_FILE.with_suffix(".json.bak")
        print(f"[MEMORY] Memory file is damaged ({error}).")

        try:
            MEMORY_FILE.replace(backup)
            print(f"[MEMORY] Saved a copy as {backup.name}. Starting fresh.")
        except OSError:
            print("[MEMORY] Starting fresh.")

        return new_history()

    # Always use the current system prompt, drop any old one
    history = [m for m in data if m["role"] != "system"]

    return trim_history(new_history() + history)


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
    """
    Process one user request.

    Prints the progress to the console and returns a dictionary:
        {"answer": str, "tools": [{"name", "arguments", "result"}, ...]}
    so other interfaces (for example the web UI) can display it.
    """

    tool_log = []

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

        # Keep the reasoning block out of the answer and the memory
        assistant_message["content"] = strip_thinking(
            assistant_message.get("content", "")
        )

        messages.append(assistant_message)

        tool_calls = assistant_message.get("tool_calls", [])

        # No more tools required
        if not tool_calls:

            print("\n[FINAL ANSWER]\n")

            print(assistant_message.get("content", ""))

            return {
                "answer": assistant_message.get("content", ""),
                "tools": tool_log
            }

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

            tool_log.append({
                "name": tool_name,
                "arguments": arguments,
                "result": result
            })

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

    return {
        "answer": "Maximum tool iterations reached.",
        "tools": tool_log
    }


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

                # Conversation history, restored from the previous session
                messages = load_history()

                saved_turns = sum(
                    1 for m in messages if m["role"] == "user"
                )

                if saved_turns:
                    print(
                        f"[MEMORY] Restored {saved_turns} previous "
                        f"message(s) from {MEMORY_FILE.name}."
                    )

                while True:

                    user_message = input("\nYou: ").strip()

                    if user_message.lower() in ("exit", "quit"):
                        break

                    if not user_message:
                        continue

                    if user_message.lower() == "reset":
                        messages = new_history()
                        save_history(messages)
                        print("[MEMORY] Conversation cleared.")
                        continue

                    backup = list(messages)

                    try:

                        await run_agent(
                            session,
                            http_client,
                            messages,
                            user_message,
                            ollama_tools
                        )

                    except Exception as error:

                        # Remove the unfinished request from memory
                        messages[:] = backup
                        print(f"\n[ERROR] Request failed: {error}")

                    save_history(messages)


if __name__ == "__main__":

    asyncio.run(main())