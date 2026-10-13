# CentrAlign AI — Engineering Internship Submission Document

**Candidate / Project**: Autonomous AI Task Worker  
**Project Path**: `/Users/sankalp/.gemini/antigravity/scratch/centralign-worker`  
**Google Form**: [https://forms.gle/CeaiXnsQ5oqx4dFx6](https://forms.gle/CeaiXnsQ5oqx4dFx6)

---

## 1. Project Overview & Problem Statement

The goal is to build an **Autonomous AI Task Worker** that accepts high-level natural language instructions and autonomously completes them using a computer across browsers, files, and APIs.

### Example Scenario Solved:
> *"Find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done."*

Our prototype autonomously:
1. **Understands the high-level business objective** rather than requiring step-by-step commands.
2. **Plans and executes actions** using real Chromium browser automation (Playwright), REST APIs (HTTP client), and local file systems.
3. **Observes execution outputs**, discovers and stores domain facts (e.g. invoice IDs, dates, dollar amounts) in working memory.
4. **Detects unexpected failures and retries** with alternative approaches or adjusted parameters.
5. **Enforces human supervision** when performing state-mutating actions or when stuck.
6. **Verifies completion independently** through both programmatic evidence collection and model-based verification before reporting success.

---

## 2. Architecture Explanation

The architecture is built from first principles using a custom **ReAct (Reason + Act + Observe + Adapt) loop** designed specifically for enterprise reliability:

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI / Interface                       │
│      main.py (Interactive / Single-Task / Live Demo)         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Agent Core (ReAct Loop)                 │
│                                                             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│   │ ReAct Engine │  │ Memory Store │  │ Human Approval   │  │
│   │ (Reasoning)  │  │ (Facts/Steps)│  │ (Risk-Based CLI) │  │
│   └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│          │                 │                   │            │
│          └────────┬────────┴───────────────────┘            │
│                   │                                         │
│                   ▼                                         │
│        ┌─────────────────────┐                              │
│        │ Independent Verifier│                              │
│        │ (Evidence & Audit)  │                              │
│        └──────────┬──────────┘                              │
└───────────────────┼─────────────────────────────────────────┘
                    │ Tool Invocations
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                        Tool Registry                        │
│                                                             │
│  ┌────────────────────┐ ┌────────────────┐ ┌─────────────┐  │
│  │ Browser Automation │ │ HTTP API Tool  │ │ File System │  │
│  │ (7 Playwright Tools│ │ (GET/POST/PUT/ │ │ (Read/Write/│  │
│  │  lazy Chromium)    │ │  PATCH/DELETE) │ │  List/JSON) │  │
│  └─────────┬──────────┘ └───────┬────────┘ └─────────────┘  │
└────────────┼────────────────────┼───────────────────────────┘
             │                    │
             ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│             Mock Company Portal (FastAPI Engine)            │
│                                                             │
│  • Web UI: Dashboard, Invoices, Expenses, Contacts, Tasks   │
│  • REST API: /api/invoices, /api/expenses, /api/tasks, etc. │
│  • Built with semantic HTML, CSS selectors, & seed data     │
└─────────────────────────────────────────────────────────────┘
```

### Architectural Subsystems:
1. **Agent Core (`agent/core.py`)**: Coordinates the ReAct execution lifecycle, prompt construction, OpenAI-compatible tool call handling, failure retries, and stuck-detection.
2. **Context & Memory Store (`agent/memory.py`)**: Stores chronological execution steps (`StepRecord`), discovers and extracts domain facts (`[FACT: key=value]`), logs error traces, and compresses older history to prevent context-window overflow.
3. **Independent Verifier (`agent/verifier.py`)**: Separates execution from verification. After the agent reports completion, the verifier queries database state and inspects artifacts to compute a confidence score and compile an evidence log.
4. **Human-in-the-Loop (`agent/human_loop.py`)**: Categorizes tool risks (`low`, `medium`, `high`). Mutations (`POST`, `PUT`, `DELETE`, writes) trigger interactive user confirmation panels, while stuck states (3+ consecutive errors) prompt human supervisors for direction.
5. **Browser & System Tools (`tools/`)**: 11 dedicated tools:
   - `browser_navigate`, `browser_click`, `browser_type`, `browser_extract_text`, `browser_extract_table`, `browser_get_page_info`, `browser_screenshot`.
   - `http_request` (REST APIs).
   - `read_file`, `write_file`, `list_files` (Filesystem).
6. **Realistic Company Portal (`mock_app/`)**: A dedicated FastAPI application that simulates an internal enterprise portal with both browser UI (Jinja2 + Pico CSS) and REST endpoints, populated with realistic seed data.

---

## 3. Important Technical & Design Decisions

### A. Custom ReAct Engine over Heavy Frameworks (LangChain / CrewAI)
*Decision*: Built the agent execution loop directly in Python (~500 lines) rather than wrapping LangChain or CrewAI.  
*Rationale*: 
- High auditability and debuggability. Enterprise AI workers require deterministic recovery strategies, precise prompt budgeting, and clear risk gating.
- Full transparency during live technical interviews: every decision, retry mechanism, and state mutation is understandable and customizable without third-party framework abstractions.

### B. Fine-Grained Atomic Browser Tools vs Monolithic Interpreter
*Decision*: Split browser automation into atomic tools (`browser_navigate`, `browser_click`, `browser_type`, `browser_extract_table`) backed by a shared lazy `BrowserManager` singleton.  
*Rationale*:
- Atomic tools give the model a crisp action space with explicit JSON schemas.
- Specialized tools like `browser_extract_table` parse HTML table elements directly in the DOM, returning structured lists of dicts rather than raw text blobs, drastically reducing token usage and hallucination.

### C. Fact Extraction & Context Window Management
*Decision*: Dual-channel memory tracking structured step traces and semantic domain facts via `[FACT: key=value]` markers and structured tool outputs.  
*Rationale*:
- In multi-step workflows (e.g. 15+ steps), full conversation history causes prompt degradation. The memory system condenses older steps into concise summaries while preserving all discovered facts in structured memory.

### D. Independent Two-Tier Verification
*Decision*: The agent does not declare itself successful on self-report alone. A dedicated `Verifier` runs programmatic validation (querying APIs / verifying disk artifacts) combined with structured evaluation before marking the run `PASSED`.

---

## 4. Models, APIs, Frameworks & Libraries Used

| Component | Technology | Rationale |
|---|---|---|
| **LLM Inference** | OpenAI API (`gpt-4o`) | Advanced reasoning, reliable function calling, and fast inference. |
| **Browser Engine** | Playwright (Chromium) | Robust async engine with auto-wait, screenshot capture, and resilient element locating. |
| **Mock Portal** | FastAPI + Uvicorn + Jinja2 | Fast, async-compatible enterprise portal simulation serving both HTML and JSON APIs. |
| **Styling** | Pico CSS (CDN) | Semantic, classless HTML layout ideal for browser selector automation. |
| **CLI & Diagnostics**| Rich | High-fidelity interactive panels, status spinners, and color-coded risk alerts. |
| **Data Validation** | Pydantic v2 | Strict validation of enterprise entities (Invoices, Expenses, Tasks). |
| **HTTP Engine** | httpx | High-performance asynchronous HTTP client for API tool invocations. |

---

## 5. Setup & Run Instructions

### Prerequisites
- Python 3.11+
- Git

### Installation
```bash
# Navigate to project
cd /Users/sankalp/.gemini/antigravity/scratch/centralign-worker

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### Configuration
```bash
cp .env.example .env
# Open .env and set your OPENAI_API_KEY=sk-...
```

### Running the System

```bash
# 1. Run Complete Automated Test Suite (28 unit & integration tests)
python -m unittest discover tests

# 2. Run Self-Contained End-to-End Simulation (No API key needed)
python demos/run_demo_simulated.py

# 3. Run Live Interactive Worker with OpenAI
python main.py

# 4. Run Single Task Execution
python main.py "Find the latest invoice from Acme Corp, extract the amount and due date, create a new expense entry, and verify it."
```

---

## 6. Known Limitations

1. **DOM-Centric Perception**: The agent primarily interacts via CSS selectors and DOM structure. While `browser_screenshot` captures visual snapshots, visual grounding (coordinate-based clicking via vision models) is not yet integrated.
2. **Stateless Sessions**: Discovered facts and steps persist within a single task run, but are not currently stored in a persistent database across days or sessions.
3. **Serial Execution**: Tool invocations execute serially. Independent tool actions (e.g. checking 3 invoices simultaneously) could be parallelized.
4. **Authentication Sandbox**: The mock portal does not enforce OAuth/SSO or multi-factor authentication.

---

## 7. What Would Be Built Next (Roadmap)

1. **Persistent Organizational Memory**: Integrate a vector database (e.g., Chroma or pgvector) to store company SOPs, user preferences, and historical task executions so the AI employee learns and improves over time.
2. **Multimodal Computer Use**: Integrate vision-based coordinate navigation (using GPT-4o-Vision) to interact with complex desktop applications and canvas-based web tools lacking clean DOM selectors.
3. **Workflow Macro Compilation**: When the agent successfully completes a novel task, automatically synthesize a parameterized, executable workflow script (DAG) so subsequent runs execute deterministically at 10x speed with zero LLM inference cost.
4. **Multi-Agent Specialist Teams**: Decompose complex enterprise tasks into specialized subagents (e.g. a Research Agent, a Data-Entry Agent, and an Auditor Agent) collaborating under a supervisory agent.
5. **Enterprise Audit & Compliance Vault**: Cryptographically signed action ledgers with full before/after screenshot comparisons and replay capability for SOC2/ISO compliance.

---

## 8. Assumptions Made

1. The target environment is modern web-based or API-driven enterprise software.
2. Write operations (`POST`, `PUT`, `DELETE`) require higher verification standard and human-in-the-loop oversight in production environments.
3. A narrow, genuinely working end-to-end prototype with real browser execution, realistic company data, and verified outcomes is more valuable than a wide, mock-heavy framework.
