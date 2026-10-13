# CentrAlign AI — Autonomous Task Worker

An AI-powered autonomous task worker that takes natural language instructions and executes them using browser automation, API calls, and file operations — with built-in planning, error recovery, verification, and human-in-the-loop approval.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🎯 What It Does

Give it a task in plain English:

> "Find the latest invoice from Acme Corp, extract the amount and due date, enter it into our expense tracker, and tell me once it's done."

The agent will:
1. **Understand** the end goal (not just follow literal steps)
2. **Plan** a sequence of actions
3. **Execute** using browser automation and APIs
4. **Observe** results and adapt
5. **Recover** from failures with retries and alternatives
6. **Verify** the outcome was actually achieved
7. **Report** a summary with evidence

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py (CLI)                         │
│                 Interactive / Single-task / Demo              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Agent Core (ReAct Loop)                   │
│                                                               │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│   │ Planner  │  │ Executor │  │ Verifier │  │ Human     │  │
│   │ (LLM)    │  │          │  │          │  │ Approval  │  │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│        │              │              │               │        │
│        └──────┬───────┘              │               │        │
│               │                      │               │        │
│        ┌──────▼──────┐               │               │        │
│        │   Memory    │◄──────────────┘               │        │
│        │  (Context)  │                               │        │
│        └─────────────┘                               │        │
└──────────┬───────────────────────────────────────────┘        │
           │                                                     │
           ▼                                                     │
┌─────────────────────────────────────────────────────────────┐ │
│                       Tool Registry                          │ │
│                                                               │ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │ │
│  │  Browser    │  │ File System │  │  HTTP/API Client    │ │ │
│  │  (Playwright│  │  (Read/     │  │  (GET/POST/PATCH)   │ │ │
│  │   7 tools)  │  │   Write)    │  │                     │ │ │
│  └──────┬──────┘  └─────────────┘  └─────────────────────┘ │ │
└─────────┼───────────────────────────────────────────────────┘ │
          │                                                      │
          ▼                                                      │
┌─────────────────────────────────────────────────────────────┐  │
│              Mock Company Portal (FastAPI)                    │  │
│                                                               │  │
│  Web UI: Dashboard, Invoices, Expenses, Contacts, Tasks      │  │
│  REST API: /api/invoices, /api/expenses, /api/contacts, ...  │  │
└─────────────────────────────────────────────────────────────┘  │
```

### Core Design: ReAct (Reason + Act) Loop

The agent uses a **ReAct loop** — an established pattern for LLM-based agents that alternates between:

1. **Reason**: The LLM thinks about what to do next based on the task, current context, and previous observations
2. **Act**: It selects and invokes a tool (browser action, API call, file operation)
3. **Observe**: The result is fed back to the LLM as context for the next iteration

This continues until the task is complete, the agent gets stuck, or the maximum step limit is reached.

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| **Agent Core** | `agent/core.py` | ReAct loop, conversation management, step execution |
| **Memory** | `agent/memory.py` | Tracks steps, facts, errors; provides context to LLM |
| **Verifier** | `agent/verifier.py` | Post-task verification using LLM + programmatic checks |
| **Human Loop** | `agent/human_loop.py` | CLI-based approval and clarification system |
| **Browser Tools** | `tools/browser_tool.py` | 7 Playwright-based browser automation tools |
| **File Tools** | `tools/filesystem_tool.py` | Read, write, list files |
| **API Tools** | `tools/api_tool.py` | Generic HTTP client for REST APIs |
| **Mock App** | `mock_app/` | FastAPI company portal with web UI and REST API |
| **Config** | `config.py` | Environment-based configuration |

## 🚀 Setup & Run

### Prerequisites

- Python 3.11+
- An OpenAI API key (GPT-4o recommended)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd centralign-worker

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Run

```bash
# Interactive mode — enter tasks at the prompt
python main.py

# Single task mode
python main.py "Find the latest invoice from Acme Corp and extract the amount"

# Demo mode — runs a pre-built scenario end-to-end
python main.py --demo

# Verbose mode (debug logging)
python main.py --demo --verbose
```

## 🎮 Demo Scenario

The built-in demo (`python main.py --demo`) executes this task:

> "Find the latest invoice from Acme Corp in our internal portal, extract the amount and due date, create a new expense entry with those details, and confirm it was saved."

The agent will:
1. Navigate to the mock company portal
2. Go to the invoices section
3. Find the Acme Corp invoice
4. Extract the amount and due date
5. Navigate to the expense form
6. Fill in the form with extracted data
7. Submit the form
8. Verify the expense was created
9. Report results with evidence

## 🔧 Technical / Design Decisions

### Why a custom ReAct loop instead of LangChain/CrewAI?

I built the agent loop from scratch to demonstrate deep understanding of how agentic systems work. Using a framework would hide the core logic and make it harder to explain, debug, or modify during a technical discussion. The custom implementation is ~300 lines and handles planning, execution, error recovery, and verification — all visible and modifiable.

### Why OpenAI function calling?

OpenAI's function calling API provides structured, reliable tool invocation. The LLM returns JSON with the tool name and arguments, which is much more reliable than parsing free-text tool calls. This also makes the agent's decisions auditable — every tool invocation is explicit.

### Why Playwright for browser automation?

Playwright offers the most robust browser automation with built-in waits, network interception, and screenshot capabilities. It's async-native (perfect for our event loop) and handles modern web apps well. The agent uses CSS selectors to interact with elements, which maps naturally to how the LLM reasons about web pages.

### Why a mock app instead of real websites?

A mock environment lets us demonstrate genuine end-to-end autonomy without depending on external services, credentials, or network access. The mock app has realistic data and a proper web UI that the browser automation actually interacts with — this is real browser automation, not API mocking.

### Why separate browser tools instead of one monolithic tool?

Each browser action (navigate, click, type, extract) is a separate tool. This gives the LLM fine-grained control over browser interactions and makes each action's intent clear. A monolithic "browser" tool with sub-commands would be harder for the LLM to reason about.

### Memory system design

The memory system stores three types of information:
1. **Step records** — what was done, what happened (full execution trace)
2. **Discovered facts** — key-value pairs extracted during execution (e.g., invoice_amount = $5,230)
3. **Errors** — what went wrong and when

This gives the LLM rich context for decision-making and enables the verifier to check what was accomplished.

### Verification approach

Post-task verification uses a two-pronged approach:
1. **LLM-based analysis** — the LLM reviews the execution trace and determines if the goal was achieved
2. **Programmatic checks** — where possible, the verifier tries to read back created records to confirm they exist

## ⚠️ Known Limitations

1. **Scope**: The prototype is designed to work with the included mock company portal. It can interact with other websites but is optimized for this controlled environment.

2. **Visual understanding**: The agent uses text extraction and DOM analysis rather than vision/screenshots for decision-making. Screenshot capability exists for debugging but isn't used by the LLM for reasoning.

3. **Complex multi-page workflows**: While the agent handles multi-step tasks well, very long workflows (20+ steps) may lose context as the conversation grows.

4. **Concurrent actions**: The agent executes one action at a time. Parallel tool execution could speed up independent tasks.

5. **Authentication**: The mock app has no authentication. Real-world deployment would need credential management and session handling.

6. **Cost**: Each task requires multiple LLM calls (planning + per-step reasoning + verification). A production system would need cost optimization.

## 🔮 What I Would Build Next

Given additional time, I would prioritize:

1. **Persistent memory across tasks** — Store learned procedures, company-specific knowledge, and past task outcomes in a vector database so the agent gets better over time.

2. **Vision-based browser interaction** — Feed screenshots to a multimodal LLM (GPT-4o Vision) so the agent can understand visual layouts, not just DOM text.

3. **Parallel tool execution** — Execute independent tool calls concurrently to speed up multi-step tasks.

4. **Task templates** — Allow users to save successful task executions as reusable templates that can be parameterized and replayed.

5. **Streaming execution UI** — A web-based dashboard showing real-time agent progress, browser screenshots, decision traces, and approval requests.

6. **Multi-agent orchestration** — Break complex tasks into subtasks handled by specialized sub-agents (browser agent, data extraction agent, form-filling agent).

7. **Sandbox security** — Run browser automation in isolated containers with network policies to prevent unauthorized access.

8. **Evaluation framework** — Automated test suite with diverse task scenarios, success criteria, and regression detection.

## 🧱 Assumptions

- The user has a valid OpenAI API key with access to GPT-4o
- Python 3.11+ is available
- The system has enough resources to run Chromium (Playwright)
- Tasks are scoped to web-based workflows within the mock company portal
- The mock portal's simple HTML structure is representative of real internal tools

## 🛠️ Models, APIs, Frameworks & Tools Used

| Component | Technology | Purpose |
|-----------|-----------|---------|
| LLM | OpenAI GPT-4o | Reasoning, planning, tool selection |
| Browser automation | Playwright | Web interaction, screenshots |
| Web framework | FastAPI + Jinja2 | Mock company portal |
| HTTP client | httpx | API tool implementation |
| CLI | Rich | Terminal UI and formatting |
| Configuration | python-dotenv | Environment management |
| Data models | Pydantic | Structured data validation |
| CSS framework | Pico CSS (CDN) | Mock app styling |

## 📄 License

MIT

---

*Built for CentrAlign AI Engineering Internship application.*
