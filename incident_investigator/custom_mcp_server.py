# custom_mcp_server.py
import os
import requests
import asyncio
from mcp.server.fastmcp import FastMCP

# Initialize the standalone MCP server
mcp = FastMCP("SRE_Internal_Tools")

# Pull secure credentials injected by mcp_client.py
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
JIRA_DOMAIN = os.environ.get("JIRA_DOMAIN")
PAGERDUTY_API_KEY = os.environ.get("PAGERDUTY_API_KEY")

@mcp.tool()
def get_jira_status(ticket_id: str) -> str:
    """Checks Jira for known issues or active deployments related to a dynamic ticket_id."""
    if not all([JIRA_EMAIL, JIRA_API_TOKEN, JIRA_DOMAIN]):
        return "Error: Jira credentials are missing from the MCP configuration."

    url = f"https://{JIRA_DOMAIN}/rest/api/3/issue/{ticket_id}"
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, auth=auth, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Extract just the useful bits for the LLM to save tokens
            summary = data["fields"]["summary"]
            status = data["fields"]["status"]["name"]
            return f'{{"ticket": "{ticket_id}", "status": "{status}", "summary": "{summary}"}}'
        else:
            return f'{{"ticket": "{ticket_id}", "status": "Not Found or API Error: {response.status_code}"}}'
    except Exception as e:
        return f'{{"error": "{str(e)}"}}'

@mcp.tool()
def get_pagerduty_alert(incident_id: str) -> str:
    """Fetches the raw alert payload and metadata from PagerDuty using a dynamic incident_id."""
    if not PAGERDUTY_API_KEY:
        return "Error: PagerDuty API key is missing."

    url = f"https://api.pagerduty.com/incidents/{incident_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Token token={PAGERDUTY_API_KEY}"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            urgency = data["incident"]["urgency"]
            summary = data["incident"]["summary"]
            return f'{{"incident": "{incident_id}", "urgency": "{urgency}", "summary": "{summary}"}}'
        else:
             return f'{{"incident": "{incident_id}", "status": "Not Found or API Error: {response.status_code}"}}'
    except Exception as e:
        return f'{{"error": "{str(e)}"}}'

if __name__ == "__main__":
    # Start the server on standard input/output
    asyncio.run(mcp.run_stdio_async())