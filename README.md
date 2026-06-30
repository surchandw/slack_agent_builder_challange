# Cross-Stack Incident Investigator: The Context-Aware SRE Slack Agent

**Cross-Stack Incident Investigator** is an advanced incident investigator built for the Slack Agent Builder Challenge. It eliminates the manual context-switching SREs face during an outage by instantly correlating PagerDuty alerts, Jira deployment tickets, and GitHub commits directly within a Slack channel.

What used to take 10 minutes of frantic tab-switching now takes **15 seconds.**

## Key Features
* **Zero-Latency Orchestration:** Connects to external systems using the Model Context Protocol (MCP) over zero-network-latency `stdio`.
* **Parallel Function Calling:** Gemini 3.5 Flash pulls from GitHub, Jira, and PagerDuty simultaneously, not sequentially.
* **Real-Time Asynchronous UI:** Bypasses Slack's standard 3-second timeout rule using FastAPI background tasks to render a live, terminal-style progress bar `[██████░░]`.
* **Bring-Your-Own-Model (BYOM):** Custom Python reasoning loop rather than a locked-in UI builder, ensuring total control over system prompts and temperature.

---

## Architecture

Cross-Stack Incident Investigator utilizes a **Co-located MCP Topology**. Instead of hosting MCP servers on separate cloud machines, the Python orchestrator, the custom Python FastMCP tools (Jira/PagerDuty), and the official Node.js MCP server (GitHub) all run securely inside a single Google Cloud Run container. 
Architectural diagram available under doc folder.


---

## Directory Structure

Here is the blueprint of our single-container deployment:

```text
incident_investigator/
├── .agents/
│   └── skills/
│       └── incident-triage/
│           └── SKILL.md              # SRE System Instructions & Personality for Gemini
├── config/
│   ├── mcp_config.template.json      # Secure template for MCP server initialization
│   └── mcp_config.json               # (Git-ignored) Local config with actual API keys
├── custom_mcp_server.py              # Python FastMCP server for Atlassian Jira & PagerDuty
├── .env                              # (Git-ignored) Environment file containing SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET and GCP_PROJECT_ID
├── .env_example                      # Template .env file
├── main.py                           # Core loop: FastAPI, Slack Bolt, and Unified UI State
├── mcp_client.py                     # MultiMcpOrchestrator: Bridges Python & Node.js via stdio
├── requirements.txt                  # Python dependencies (FastAPI, slack_bolt, google-genai)
├── Dockerfile                        # Atomic container deployment for Google Cloud Run
└── .gitignore                        # Security rules to prevent token leakage

Tech Stack
Language & Frameworks: Python 3, Node.js, FastAPI, Slack Bolt

AI & Reasoning: Google Gemini 3.5 Flash, Google GenAI SDK

Integration Layer: Model Context Protocol (MCP) via stdio

Infrastructure: Google Cloud Run (Serverless Container), Docker

APIs: Slack Web API, PagerDuty, Atlassian Jira, GitHub

Local Development & Setup
For security reasons, the live mcp_config.json containing our production API keys is not committed to this repository. If you wish to run this agent locally, please follow these steps:

Clone the repository:

Bash
git clone https://github.com/surchandw/slack_agent_builder_challange.git
cd incident_investigator

Set up the Configuration:
Duplicate the template file to create your local config.

Bash
cp config/mcp_config.template.json config/mcp_config.json
Open mcp_config.json and replace the placeholder <TOKEN_HERE> strings with your actual GitHub, Jira, and PagerDuty API keys.

cp .env_example .env
Open .env file and enter the values for SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET and GCP_PROJECT_ID

Install Dependencies:

Bash
pip install -r requirements.txt
npm install

Run the Server:

Bash
uvicorn main:api --port 8080 --reload

Demo & Submission:

For Demo, we have used git repo: [https://github.com/surchandw/chronos-stream-buffer.git]
We have used PagerDuty incident: 1 
and Jira ticket number : CSB-1
Slack Developer Sandbox: [https://app.slack.com/client/E0BA7AX8L4R/C0BDPESQB8S]
Video Demo: [https://youtu.be/W9L_Iu6Q6IU]

Please refer to testing_instruction.txt for testing the app.
