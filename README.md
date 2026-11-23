# Local MCP AI Agent

A locally running AI agent powered by **Qwen3**, **Ollama**, and the **Model Context Protocol (MCP)**.

This project demonstrates how to build an AI agent that can interact with external tools through MCP, execute Python functions, process data, and generate natural language responses based on actual tool outputs.

The application runs locally using Ollama, without requiring paid LLM APIs or cloud-based AI services.

## Overview

Traditional chatbots primarily generate responses based on information learned during model training or provided in the conversation.

An AI agent can go further by interacting with external tools, retrieving information, performing calculations, and executing specific operations.

This project combines a locally hosted LLM with an MCP server to demonstrate this approach.

The LLM determines which tools are relevant to a user's request, while the Python agent orchestrates tool execution through the MCP client.

## Architecture

```text
                    USER
                      |
                      v
              PYTHON AI AGENT
                      |
              +-------+-------+
              |               |
              v               v
          OLLAMA API       MCP CLIENT
              |               |
              v               v
           QWEN3:8B        MCP SERVER
                              |
                  +-----------+-----------+
                  |           |           |
                  v           v           v
               MATH       STATISTICS    DATA
               TOOLS        TOOLS      ANALYSIS
                  |           |           |
                  +-----------+-----------+
                              |
                              v
                        TOOL RESULTS
                              |
                              v
                         QWEN3:8B
                              |
                              v
                       FINAL RESPONSE
```

| Component | Responsibility |
|---|---|
| Qwen3:8B | Local Large Language Model |
| Ollama | Runs and exposes the local LLM through an API |
| Python AI Agent | Orchestrates communication between the LLM and MCP |
| MCP Client | Discovers available tools and invokes them |
| MCP Server | Exposes Python functions as MCP tools |
| Pandas | Provides data processing and analysis capabilities |
| HTTPX | Handles asynchronous HTTP communication with Ollama |
| AsyncIO | Supports asynchronous execution of the agent |


## Features

### Local LLM Integration

- Runs Qwen3:8B locally using Ollama.
- Communicates with the model through the Ollama HTTP API.
- Uses asynchronous HTTP requests with HTTPX.
- Does not require external LLM API subscriptions.

### MCP Tool Integration

The MCP server currently exposes seven tools:

| Tool | Description |
|---|---|
| `add` | Adds two numbers. |
| `subtract` | Subtracts one number from another. |
| `multiply` | Multiplies two numbers. |
| `divide` | Divides two numbers with zero-division handling. |
| `get_current_datetime` | Returns the current local date and time. |
| `calculate_statistics` | Calculates descriptive statistics for numerical data. |
| `analyze_csv` | Analyzes CSV content and returns basic structural information. |

### AI Agent Capabilities

The Python agent implements a tool-calling loop:

1. Receives a natural language request.
2. Sends the request and available tool definitions to Qwen3.
3. Processes the model's tool selection.
4. Invokes the selected MCP tool.
5. Returns the execution result to the LLM.
6. Generates a final natural language response.

The agent supports multiple tool calls within a single request, subject to a configurable iteration limit.

### Web Interface

A browser-based chat interface built with Gradio (`app.py`).

- Chat window with your conversation history.
- Every tool call is shown in a collapsible block with its arguments and result.
- Clickable example questions.
- "New conversation" button that clears the memory.
- Uses the same agent logic, MCP server and `memory.json` as the console version, so the conversation continues in either interface.

### Conversation Memory

The agent keeps the conversation history, so follow-up questions work naturally, even after the program is restarted.

- The conversation is saved to `MCP Agent/memory.json` after every request and restored on the next start.
- The file is written safely (temporary file first), so a crash cannot corrupt the existing memory.
- If a request fails, the unfinished turn is removed from memory.
- A damaged memory file is renamed to `memory.json.bak` and the agent starts a new conversation.
- `memory.json` is listed in `.gitignore`, because it contains your conversations.

- The full history (user messages, tool calls, tool results and answers) is sent to the model with every request.
- Only the last `MAX_HISTORY_TURNS` user turns are kept, so the context does not grow indefinitely.
- Old turns are trimmed at user-message boundaries, so a tool call is never separated from its result.
- Type `reset` to clear the memory and start a new conversation (this also clears the saved file).

### Statistical Analysis

The `calculate_statistics` tool provides:

- Count
- Mean
- Median
- Minimum
- Maximum
- Population standard deviation

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application and agent orchestration |
| Qwen3:8B | Local language model |
| Ollama | Local model runtime |
| Model Context Protocol (MCP) | Standardized tool communication |
| HTTPX | Asynchronous HTTP communication |
| Pandas | Data processing |
| AsyncIO | Asynchronous execution |

## Project Structure

```text
mcp-agent-lab/
│
├── MCP Agent/
│   ├── agent.py           (console interface)
│   ├── app.py             (web interface)
│   └── memory.json        (created automatically)
│
├── MCP Server/
│   └── server.py
│
├── requirements.txt
├── .gitignore
└── README.md
```

### File Responsibilities

- `app.py` – Web interface (Gradio). Reuses the agent logic from `agent.py`.
- `memory.json` – Created automatically; stores the saved conversation (not committed to git).
- `agent.py` – Connects to Ollama, initializes the MCP client, discovers available tools, and manages the AI tool-calling loop.
- `server.py` – Implements the MCP server and exposes Python functions as tools.
- `requirements.txt` – Contains the project dependencies (MCP SDK, HTTPX, Pandas). Located in the repository root and must be saved as UTF-8.


## Getting Started

### Prerequisites

Make sure you have installed:

- Python 3.10+
- MCP Python SDK 2.x (installed through `requirements.txt`)
- Ollama
- Git (optional)

### 1. Install Ollama

Download and install Ollama from:

https://ollama.com/

### 2. Download the Qwen3 Model

In Windows, open PowerShell and run:

```powershell
ollama pull qwen3:8b
```

Verify the installation:

```powershell
ollama list
```

### 3. Clone the Repository

```bash
git clone git@github.com:GalkaKG/mcp-agent-lab.git
cd mcp-agent-lab
```

### 4. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

### 5. Install Dependencies

From the repository root, install the dependencies:

```bash
pip install -r requirements.txt
```

The file contains:

```text
mcp[cli]>=2.0
httpx
pandas
gradio>=5
```

### 6. Start the AI Agent

You can use the agent from the console or from the browser. Both share the same memory.

#### Option A: Web interface

```powershell
cd ".\MCP Agent"
python app.py
```

Then open http://127.0.0.1:7860 in your browser. The page starts the MCP server and connects to Ollama automatically. Stop it with `Ctrl+C`.

#### Option B: Console

Navigate to the agent directory:

```powershell
cd ".\MCP Agent"
```

Run:

```bash
python agent.py
```

The console agent will:
1. Start the MCP server as a separate process.
2. Establish an MCP client session.
3. Discover available tools.
4. Connect to the local Ollama API.
5. Initialize the interactive AI agent with conversation memory.

Make sure the Ollama service is running before you start the agent (`ollama list` should work).

---

## Usage Examples

Once the agent is running, you can interact with it using natural language.

### Example 1: Mathematical Operations

**Input:**
```text
Calculate 125 multiplied by 48.
```

**Agent execution:**
```text
[TOOL CALL] multiply
[ARGUMENTS] {'a': 125, 'b': 48}
[TOOL RESULT] 6000.0
```

**Response:**
> The result of multiplying 125 by 48 is 6000.

---

### Example 2: Statistical Analysis

**Input:**
```text
Calculate the average, median and standard deviation
of these numbers: 10, 20, 30, 40, 50.
```

**Agent execution:**
```text
[TOOL CALL] calculate_statistics

[ARGUMENTS]
{
    "numbers": [10, 20, 30, 40, 50]
}
```

**Response:**
```text
Count: 5
Mean: 30.0
Median: 30.0
Minimum: 10.0
Maximum: 50.0
Standard Deviation: 14.14
```

---

### Example 3: Conversation Memory

**Input:**
```text
You: Calculate 125 multiplied by 48.
You: Now divide it by 4.
```

The agent remembers the previous result (6000) and calls `divide` with `a = 6000` and `b = 4`, without the number being repeated.

The memory is saved to disk, so after you type `exit` and start the agent again, it still remembers the conversation:

```text
[MEMORY] Restored 2 previous message(s) from memory.json.
You: What was the last result?
```

To start a new conversation, type `reset`.

---

### Example 4: Current Date and Time

**Input:**
```text
What is the current date and time?
```

The agent automatically selects `get_current_datetime` and returns the result.

---

## Configuration

The main configuration parameters are defined in `agent.py`:

```python
MODEL = "qwen3:8b"
OLLAMA_URL = "http://localhost:11434/api/chat"
MAX_TOOL_CALLS = 10
MAX_HISTORY_TURNS = 10
MEMORY_FILE = BASE_DIR / "memory.json"
```

- `MODEL` – the local Ollama model. You can change it to another locally available model.
- `MAX_TOOL_CALLS` – maximum number of tool-calling iterations per request.
- `MAX_HISTORY_TURNS` – number of recent user turns kept in the conversation memory.
- `MEMORY_FILE` – file where the conversation is saved between sessions.

---

## Current Limitations

- Only one conversation is stored. Use `reset` to start a new one; older conversations are not archived.
- The memory file is stored as plain, unencrypted JSON.
- Memory is limited by the number of turns, not by tokens, so very large inputs can still exceed the model context.
- Tool execution is currently limited by a configurable iteration count.
- CSV analysis currently accepts CSV content as input rather than directly exploring arbitrary local files.
- Tool access and file permissions require additional security controls before production use.

---

## Roadmap

Planned improvements:
- [ ] Implement advanced CSV file analysis using Pandas.
- [ ] Add automatic data profiling and missing-value detection.
- [ ] Enable more complex multi-step tool execution.
- [ ] Improve error handling and input validation.
- [ ] Add support for additional MCP servers.
- [ ] Implement logging and execution tracing.