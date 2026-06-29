import os
import asyncio
from fastapi import FastAPI, Request
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from google import genai
from google.genai import types

# Import context manager libraries
from contextlib import asynccontextmanager, AsyncExitStack
from mcp_client import MultiMcpOrchestrator

# --- 🟢 NEW: UNIFIED SLACK UI BUILDER ---
def build_slack_ui(user_id: str, state: dict) -> str:
    """Generates a highly polished terminal-style UI for Slack based on the current agent state."""
    base = f"<@{user_id}> 🔍 *Investigating cross-stack context (Jira/GitHub/PagerDuty)...*\n"
    
    if state["phase"] == "thinking":
        return base + f"`[LLM Reasoning{state['thinking_dots']}]` ⏳"
        
    elif state["phase"] == "executing":
        clean_name = state["tool_name"].split(":")[-1].replace("_", " ").title()
        bar_length = 10
        
        # Calculate progress bar fill
        progress = state["current_step"] / state["total_steps"] if state["total_steps"] > 0 else 0
        filled_length = int(round(bar_length * progress))
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        percentage = int(progress * 100)
        
        return (
            base +
            f"```\n"
            f"🛠️ [Step {state['current_step']}/{state['total_steps']}]: {clean_name}\n"
            f"↳ 📊 {bar} {percentage}%\n"
            f"```"
        )
# ----------------------------------------

# 1. Initialize Gemini and the MCP Orchestrator
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
LOCATION = os.environ.get("GCP_LOCATION", "global")

gemini_client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
orchestrator = MultiMcpOrchestrator(config_path="config/mcp_config.json")

# Load SKILL.md instructions
with open(".agents/skills/incident-triage/SKILL.md", "r") as f:
    SRE_SYSTEM_INSTRUCTION = f.read()

# LIFECYCLE ROUTING
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        print("Starting background MCP Servers...")
        await orchestrator.connect_to_servers(stack)
        yield 
        print("Cloud Run is shutting down. Closing MCP connections.")

api = FastAPI(lifespan=app_lifespan)

slack_app = AsyncApp(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)
slack_handler = AsyncSlackRequestHandler(slack_app)

@api.post("/slack/events")
async def slack_events_endpoint(request: Request):
    if "x-slack-retry-num" in request.headers:
        return {"status": "ok"}
    return await slack_handler.handle(request)

@slack_app.event("app_mention")
async def handle_mention(event, say, client, logger):
    user_id = event.get("user")
    user_text = event.get("text")
    clean_prompt = user_text.split(">")[-1].strip()

    try:
        # 1. Initialize shared UI State
        ui_state = {
            "phase": "thinking",
            "tool_name": "",
            "current_step": 0,
            "total_steps": 1,
            "thinking_dots": ""
        }

        # 2. Send the initial message and capture its Timestamp (ts)
        loading_message = await say(text=build_slack_ui(user_id, ui_state))
        channel_id = loading_message["channel"]
        message_ts = loading_message["ts"]

        # 3. Define the background UI Updater
        stop_event = asyncio.Event()
        
        async def background_ui_updater():
            while not stop_event.is_set():
                await asyncio.sleep(2) # Pulse every 2 seconds
                if stop_event.is_set():
                    break
                
                # Only pulse dots if LLM is actively thinking
                if ui_state["phase"] == "thinking":
                    if len(ui_state["thinking_dots"]) >= 9:
                        ui_state["thinking_dots"] = ""
                    else:
                        ui_state["thinking_dots"] += "..."
                
                try:
                    await client.chat_update(
                        channel=channel_id,
                        ts=message_ts,
                        text=build_slack_ui(user_id, ui_state)
                    )
                except Exception:
                    pass

        # Fire the background task
        progress_task = asyncio.create_task(background_ui_updater())

        # --- AI EXECUTION LOOP ---
        mcp_tools = await orchestrator.get_all_combined_tools()
        history = [types.Content(role="user", parts=[types.Part.from_text(text=clean_prompt)])]
        ai_reply = None
        
        for step in range(15):
            response = gemini_client.models.generate_content(
                model="gemini-3.5-flash",
                contents=history,
                config=types.GenerateContentConfig(
                    system_instruction=SRE_SYSTEM_INSTRUCTION,
                    tools=mcp_tools
                )
            )

            history.append(response.candidates[0].content)
            function_calls = [p.function_call for p in response.candidates[0].content.parts if p.function_call]

            if function_calls:
                response_parts = []
                
                # 🟢 Switch UI to Execution Mode
                ui_state["phase"] = "executing"
                ui_state["total_steps"] = len(function_calls)

                for index, fc in enumerate(function_calls, start=1):
                    # Update UI state for the specific tool
                    ui_state["current_step"] = index
                    ui_state["tool_name"] = fc.name
                    
                    # Force an immediate Slack update before execution
                    try:
                        await client.chat_update(
                            channel=channel_id,
                            ts=message_ts,
                            text=build_slack_ui(user_id, ui_state)
                        )
                    except Exception:
                        pass
                    
                    # Execute MCP Tool
                    tool_args = fc.args
                    mcp_result = await orchestrator.execute_mcp_tool(fc.name, tool_args)
                    response_parts.append(types.Part.from_function_response(name=fc.name, response={"result": mcp_result}))
                
                history.append(types.Content(role="user", parts=response_parts))
                
                # 🟢 Switch UI back to Thinking Mode for the next LLM turn
                ui_state["phase"] = "thinking"
                ui_state["thinking_dots"] = ""

            else:
                ai_reply = response.text
                break
        
        if not ai_reply:
            ai_reply = "⚠️ Agent reached maximum execution limits without finding a conclusion."

        # 4. Stop the progress bar once the LLM is done
        stop_event.set()
        await progress_task 

    except Exception as e:
        if 'stop_event' in locals():
            stop_event.set() 
        logger.error(f"Agent Error: {e}")
        ai_reply = f"⚠️ **SRE Agent Error:** Failed to process incident.\n```\n{str(e)}\n```"
    
    # 5. Post the final root-cause summary
    await say(text=f"<@{user_id}>\n{ai_reply}")

@slack_app.event("message")
async def handle_message_events(body, logger):
    """Silently acknowledge standard channel messages to stop Slack from throwing 404s."""
    pass