# mcp_client.py
import json
import os
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MultiMcpOrchestrator:
    def __init__(self, config_path="config/mcp_config.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        self.sessions = {}

    # NEW: We now accept the exit_stack explicitly from FastAPI
    async def connect_to_servers(self, exit_stack):
        """Spins up all registered MCP servers as separate processes."""
        
        for server_name, cfg in self.config["mcpServers"].items():
            
            merged_env = os.environ.copy()
            merged_env.update(cfg.get("env", {}))
            
            server_params = StdioServerParameters(
                command=cfg["command"],
                args=cfg["args"],
                env=merged_env 
            )
            
            transport = await exit_stack.enter_async_context(stdio_client(server_params))
            read_stream, write_stream = transport
            
            session = await exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
            
            await session.initialize()
            self.sessions[server_name] = session
            print(f"Successfully connected to standalone MCP Server: {server_name}")

    async def get_all_combined_tools(self) -> list:
        """Queries active servers and translates their tools for Gemini's strict SDK."""
       
        function_declarations = []
        
        # --- NEW: Schema Sanitizer ---
        def clean_schema(schema: dict) -> dict:
            """Recursively strips ONLY the $schema key that crashes Gemini."""
            if not isinstance(schema, dict):
                return schema
            cleaned = {}
            for k, v in schema.items():
                # Only strip $schema. Leave 'title' alone so GitHub PR parameters work!
                if k == "$schema": 
                    continue
                if isinstance(v, dict):
                    cleaned[k] = clean_schema(v)
                elif isinstance(v, list):
                    cleaned[k] = [clean_schema(i) for i in v]
                else:
                    cleaned[k] = v
            return cleaned
        
        for server_name, session in self.sessions.items():
            tools_response = await session.list_tools()
            for tool in tools_response.tools:
                
                # 1. Sanitize the raw MCP schema
                safe_parameters = clean_schema(tool.inputSchema)
                
                # 2. Wrap it cleanly in Gemini's expected Pydantic class
                func_decl = types.FunctionDeclaration(
                    name=f"{server_name}__{tool.name}",
                    description=tool.description or "No description provided.",
                    parameters=safe_parameters
                )
                function_declarations.append(func_decl)
        
        if not function_declarations:
            return []
            
        return [types.Tool(function_declarations=function_declarations)]

    
    async def execute_mcp_tool(self, namespaced_tool_name: str, arguments: dict):
        
        # --- NEW: Strip Vertex AI's internal OpenAPI prefix ---
        clean_name = namespaced_tool_name
        if clean_name.startswith("default_api:"):
            clean_name = clean_name.split(":", 1)[-1]
            
        server_name, original_tool_name = clean_name.split("__", 1)
        
        session = self.sessions.get(server_name)
        if not session:
            raise ValueError(f"No active MCP session found for server: {server_name}")
            
        # Call the tool
        result = await session.call_tool(original_tool_name, arguments)
        
        # Extract the raw text from the content array
        extracted_text = ""
        for item in result.content:
            if item.type == "text":
                extracted_text += item.text
                
        # If the tool failed, explicitly tell Gemini so it stops trying!
        if result.isError:
            return f"Error executing {original_tool_name}: {extracted_text}"
            
        return extracted_text