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
# AI AGENT LOOP
# =====================================================

async def run_agent(session, http_client, user_message, ollama_tools):

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful AI data assistant. "
                "You have access to external tools through MCP. "
                "Use tools whenever they are necessary to answer "
                "the user's request. "
                "Never invent tool results. "
                "After receiving tool results, explain them clearly."
            )
        },
        {
            "role": "user",
            "content": user_message
        }
    ]

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

                print("\nType 'exit' to quit.")

                while True:

                    user_message = input("\nYou: ").strip()

                    if user_message.lower() in ("exit", "quit"):
                        break

                    if not user_message:
                        continue

                    await run_agent(
                        session,
                        http_client,
                        user_message,
                        ollama_tools
                    )


if __name__ == "__main__":

    asyncio.run(main())