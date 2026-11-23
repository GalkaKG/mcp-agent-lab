"""
Web interface for the local MCP AI agent.

Run:
    python app.py

Then open http://127.0.0.1:7860 in your browser.
It uses the same agent logic, MCP server and memory file as agent.py.
"""

import asyncio
import json
import os
import sys

import gradio as gr
import httpx

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent import (
    MODEL,
    OLLAMA_URL,
    SERVER_PATH,
    convert_tools,
    load_history,
    new_history,
    run_agent,
    save_history,
)


HOST = "127.0.0.1"
PORT = 7860

OLLAMA_TAGS_URL = OLLAMA_URL.replace("/api/chat", "/api/tags")


# =====================================================
# AGENT SERVICE
# Keeps one MCP session and one conversation alive
# for as long as the web app is running.
# =====================================================

class AgentService:

    def __init__(self):

        self.session = None
        self.http_client = None
        self.ollama_tools = []
        self.messages = []

        self._task = None
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._error = None

        self._lock = asyncio.Lock()

    async def _runner(self):
        """Background task that owns the MCP session and HTTP client."""

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER_PATH)],
            env=os.environ.copy()
        )

        try:

            async with stdio_client(server_params) as (read, write):

                async with ClientSession(read, write) as session:

                    await session.initialize()

                    tools_result = await session.list_tools()

                    async with httpx.AsyncClient(
                        timeout=httpx.Timeout(180.0, connect=10.0)
                    ) as http_client:

                        health = await http_client.get(OLLAMA_TAGS_URL)
                        health.raise_for_status()

                        self.session = session
                        self.http_client = http_client
                        self.ollama_tools = convert_tools(tools_result.tools)
                        self.messages = load_history()

                        self._ready.set()

                        await self._stop.wait()

        except Exception as error:

            self._error = error

        finally:

            self._ready.set()

    async def start(self):
        """Start the MCP server and connect to Ollama (once)."""

        if self._task is not None and self._task.done():
            self._task = None
            self._ready = asyncio.Event()
            self._stop = asyncio.Event()

        if self._task is None:
            self._error = None
            self._task = asyncio.create_task(self._runner())

        await self._ready.wait()

        if self._error is not None:

            error = self._error
            self._task = None

            raise RuntimeError(
                "Could not start the agent. Is Ollama running? "
                f"Details: {error}"
            )

    async def ask(self, user_message):

        async with self._lock:

            await self.start()

            backup = list(self.messages)

            try:

                result = await run_agent(
                    self.session,
                    self.http_client,
                    self.messages,
                    user_message,
                    self.ollama_tools
                )

            except Exception:

                # Remove the unfinished request from memory
                self.messages[:] = backup
                raise

            save_history(self.messages)

            return result

    async def reset(self):

        async with self._lock:

            await self.start()

            self.messages[:] = new_history()
            save_history(self.messages)

    def tool_names(self):

        return [tool["function"]["name"] for tool in self.ollama_tools]

    def restored_chat(self):
        """Turn the saved memory into messages for the chat window."""

        chat = []

        for message in self.messages:

            content = message.get("content") or ""

            if message["role"] == "user":
                chat.append({"role": "user", "content": content})

            elif message["role"] == "assistant" and content:
                chat.append({"role": "assistant", "content": content})

        return chat


service = AgentService()


# =====================================================
# UI HANDLERS
# =====================================================

def format_tool_message(tool):
    """Create a collapsible 'tool used' bubble for the chat window."""

    arguments = json.dumps(tool["arguments"], ensure_ascii=False, indent=2)

    result = json.dumps(
        tool["result"], ensure_ascii=False, indent=2, default=str
    )

    return {
        "role": "assistant",
        "content": (
            f"**Arguments**\n```json\n{arguments}\n```\n"
            f"**Result**\n```json\n{result}\n```"
        ),
        "metadata": {"title": f"🔧 Tool: {tool['name']}"}
    }


async def on_load():
    """Runs when the page opens: connect and restore the saved chat."""

    try:

        await service.start()

    except Exception as error:

        return [{"role": "assistant", "content": f"⚠️ {error}"}], \
            "Not connected"

    tools = ", ".join(f"`{name}`" for name in service.tool_names())

    return service.restored_chat(), f"**Available tools:** {tools}"


async def on_send(message, chat):

    message = (message or "").strip()

    if not message:
        yield "", chat
        return

    chat = chat + [{"role": "user", "content": message}]

    # Show the user's message immediately
    yield "", chat

    try:

        result = await service.ask(message)

    except Exception as error:

        chat.append({
            "role": "assistant",
            "content": f"⚠️ Request failed: {error}"
        })

        yield "", chat
        return

    for tool in result["tools"]:
        chat.append(format_tool_message(tool))

    chat.append({
        "role": "assistant",
        "content": result["answer"] or "(empty answer)"
    })

    yield "", chat


async def on_reset():

    try:
        await service.reset()
    except Exception as error:
        return [{"role": "assistant", "content": f"⚠️ {error}"}]

    return []


# =====================================================
# INTERFACE
# =====================================================

with gr.Blocks(title="Local MCP AI Agent") as demo:

    gr.Markdown(
        "# 🤖 Local MCP AI Agent\n"
        f"Model: `{MODEL}` · runs locally with Ollama and MCP tools"
    )

    tools_info = gr.Markdown("Connecting...")

    chatbot = gr.Chatbot(height=520, label="Conversation")

    with gr.Row():

        textbox = gr.Textbox(
            placeholder="Ask something, e.g. Calculate 125 * 48",
            show_label=False,
            scale=8,
            autofocus=True
        )

        send_button = gr.Button("Send", variant="primary", scale=1)

    reset_button = gr.Button("🗑️ New conversation (reset memory)")

    gr.Examples(
        examples=[
            "Calculate 125 multiplied by 48.",
            "Now divide it by 4.",
            "Calculate the average, median and standard deviation of 10, 20, 30, 40, 50.",
            "What is the current date and time?",
        ],
        inputs=textbox,
        label="Examples"
    )

    demo.load(on_load, outputs=[chatbot, tools_info])

    textbox.submit(on_send, [textbox, chatbot], [textbox, chatbot])
    send_button.click(on_send, [textbox, chatbot], [textbox, chatbot])
    reset_button.click(on_reset, outputs=chatbot)


if __name__ == "__main__":

    demo.queue().launch(
        server_name=HOST,
        server_port=PORT,
        theme=gr.themes.Soft()
    )