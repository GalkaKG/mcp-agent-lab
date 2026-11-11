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
MCP Server/
│
├── MCP Agent/
│   └── agent.py
│
├── MCP Server/
│   ├── server.py
│   └── requirements.txt

```

### File Responsibilities

- `agent.py` – Connects to Ollama, initializes the MCP client, discovers available tools, and manages the AI tool-calling loop.
- `server.py` – Implements the MCP server and exposes Python functions as tools.
- `requirements.txt` – Contains the MCP server dependencies.
- `test.py` and `test.ipynb` – Development and experimentation files.

## Getting Started

### Prerequisites

Make sure you have installed:

- Python 3.10+
- Ollama
- Git (optional)

### 1. Install Ollama

Download and install Ollama from:

https://ollama.com/

### 2. Download the Qwen3 Model

In Windows Open PowerShell and run:

```powershell
ollama pull qwen3:8b
```

Verify the installation:

```powershell
ollama list
```

### 3. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd "MCP Server"
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

Install the MCP server dependencies:

```bash
pip install -r ".\MCP Server\requirements.txt"
```

Install HTTPX:

```bash
pip install httpx
```

### 6. Start the AI Agent

Navigate to the agent directory:

```bash
cd ".\MCP Agent"
```

Run:

```bash
python agent.py
```

The agent will:
1. Start the MCP server as a separate process.
2. Establish an MCP client session.
3. Discover available tools.
4. Connect to the local Ollama API.
5. Initialize the interactive AI agent.

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

### Example 3: Current Date and Time

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
```

You can change the model by updating the `MODEL` variable to another locally available Ollama model.

---

## Current Limitations

- Conversation history is not persisted between user requests.
- Tool execution is currently limited by a configurable iteration count.
- CSV analysis currently accepts CSV content as input rather than directly exploring arbitrary local files.
- Tool access and file permissions require additional security controls before production use.

---

## Roadmap

Planned improvements:
- [ ] Add conversation memory.
- [ ] Implement advanced CSV file analysis using Pandas.
- [ ] Add automatic data profiling and missing-value detection.
- [ ] Enable more complex multi-step tool execution.
- [ ] Improve error handling and input validation.
- [ ] Add support for additional MCP servers.
- [ ] Implement logging and execution tracing.
- [ ] Add a user-friendly interface.

---

