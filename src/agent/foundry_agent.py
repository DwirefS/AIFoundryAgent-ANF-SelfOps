"""
Azure AI Foundry Agent — ANF SelfOps.

Sets up a Foundry Agent with function calling tools that manage ANF resources.
Uses the stable GA SDK (azure-ai-projects 1.0.0 / azure-ai-agents >=1.1.0) with
the create_thread_and_process_run + enable_auto_function_calls pattern.

SDK Reference:
  - azure-ai-agents: https://learn.microsoft.com/python/api/overview/azure/ai-agents-readme
  - Function calling: https://learn.microsoft.com/azure/ai-foundry/agents/how-to/tools-classic/function-calling

Architecture Note (azure-ai-agents 1.1.0):
  The GA SDK consolidated the thread/message/run workflow:
    - create_thread_and_process_run: Creates thread, runs agent, polls to completion
    - enable_auto_function_calls: SDK handles function call dispatch automatically
    - send_request: Low-level REST for operations not exposed as methods (e.g., list_messages)
  The older pattern (create_thread → create_message → create_run → poll → submit_tool_outputs)
  is no longer available on AgentsClient. Those operations are now internal to the SDK.

Migration Note (Foundry 2.x / Responses API):
  Microsoft is transitioning to azure-ai-projects >= 2.0.0b1 which uses:
    - PromptAgentDefinition + create_version (instead of create_agent)
    - openai_client.responses.create (instead of threads + runs)
    - previous_response_id for conversation continuity
  When the 2.x SDK reaches GA, this module can be migrated. See:
  https://learn.microsoft.com/azure/ai-foundry/agents/how-to/tools/function-calling
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import (
    AgentThreadCreationOptions,
    FunctionDefinition,
    ThreadMessageOptions,
)
from azure.core.rest import HttpRequest
from azure.identity import DefaultAzureCredential

from .instructions import AGENT_INSTRUCTIONS, AGENT_NAME
from ..tools.definitions import ALL_TOOLS
from ..tools.executor import ToolExecutor

logger = logging.getLogger(__name__)


class ANFSelfOpsAgent:
    """
    Foundry Agent for ANF SelfOps — manages ANF infrastructure via function calling.

    Uses the azure-ai-agents 1.1.0 GA pattern:
      - create_agent: Register the agent with function tool definitions
      - enable_auto_function_calls: SDK auto-dispatches function calls to Python callables
      - create_thread_and_process_run: One-shot thread + run + polling per user message
      - send_request: Low-level REST to retrieve assistant messages

    Lifecycle:
        1. __init__: Connect to Foundry project
        2. setup: Create the agent with function tools + register auto-callable functions
        3. send_message: Per-message loop (create_thread_and_process_run → retrieve response)
        4. cleanup: Delete the agent
    """

    def __init__(
        self,
        project_endpoint: str,
        model_deployment: str,
        tool_executor: ToolExecutor,
        credential: Optional[DefaultAzureCredential] = None,
    ):
        self._credential = credential or DefaultAzureCredential()

        # For hub-based AI Foundry projects, the endpoint is a connection string
        # (region;subscription;resourceGroup;projectName) and requires the legacy
        # environment variable to activate the correct auth scopes and API version.
        # See: AgentsClient.__init__ in azure.ai.agents._patch (legacy endpoint handling)
        if ";" in project_endpoint:
            os.environ["AZURE_AI_AGENTS_TESTS_IS_TEST_RUN"] = "True"
            logger.info("Legacy hub-based project detected — enabled connection string mode")

        self._project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=self._credential,
        )
        self._agents_client = self._project_client.agents
        self._model = model_deployment
        self._tool_executor = tool_executor
        self._agent = None

        logger.info(
            "ANFSelfOpsAgent initialized (endpoint=%s, model=%s)",
            project_endpoint[:50] + "..." if len(project_endpoint) > 50 else project_endpoint,
            model_deployment,
        )

    def setup(self) -> None:
        """Create the Foundry agent with ANF function tools and register auto-callables."""
        logger.info("Creating Foundry agent: %s", AGENT_NAME)

        # Build function tool definitions for the agent
        tools = [{"type": "function", "function": self._tool_to_dict(t)} for t in ALL_TOOLS]

        self._agent = self._agents_client.create_agent(
            model=self._model,
            name=AGENT_NAME,
            instructions=AGENT_INSTRUCTIONS,
            tools=tools,
        )
        logger.info("Agent created: id=%s, name=%s", self._agent.id, self._agent.name)

        # Register auto-callable functions so the SDK handles function dispatch
        # during create_thread_and_process_run. Each callable's __name__ must match
        # the corresponding FunctionDefinition name.
        callables = self._build_auto_callables()
        self._agents_client.enable_auto_function_calls(tools=callables)
        logger.info("Registered %d auto-callable functions", len(callables))

    def send_message(self, user_message: str) -> str:
        """
        Send a user message to the agent and return the assistant's response.

        Creates a new thread per message with the auto-function-calling pattern:
          1. Build thread with user message
          2. create_thread_and_process_run (SDK handles polling + function calls)
          3. Retrieve the assistant's response via REST

        Args:
            user_message: The user's natural-language request.

        Returns:
            The agent's response text.
        """
        if not self._agent:
            raise RuntimeError("Agent not initialized. Call setup() first.")

        logger.info("User message: %s", user_message[:100])

        # Build thread options with the user message
        thread = AgentThreadCreationOptions(
            messages=[
                ThreadMessageOptions(
                    role="user",
                    content=user_message,
                )
            ]
        )

        # Create thread and process run — SDK handles:
        #   - Thread creation
        #   - Run creation
        #   - Polling until completion
        #   - Auto function call dispatch (via enable_auto_function_calls)
        try:
            run = self._agents_client.create_thread_and_process_run(
                agent_id=self._agent.id,
                thread=thread,
            )
        except Exception as e:
            logger.error("create_thread_and_process_run failed: %s", str(e))
            return f"Error: The agent encountered an issue — {str(e)}"

        logger.info("Run completed: id=%s, status=%s, thread=%s", run.id, run.status, run.thread_id)

        if run.status != "completed":
            error_detail = getattr(run, "last_error", None) or run.status
            return f"Run {run.status}: {error_detail}. Please try again."

        # Retrieve the assistant's response from the thread
        return self._get_last_assistant_message(run.thread_id)

    def _get_last_assistant_message(self, thread_id: str) -> str:
        """
        Retrieve the last assistant message from a thread via REST.

        The AgentsClient in azure-ai-agents 1.1.0 does not expose a list_messages
        method. We use send_request to make a raw GET /threads/{id}/messages call.
        """
        try:
            request = HttpRequest(
                method="GET",
                url=f"/threads/{thread_id}/messages",
                params={"limit": "10", "api-version": "2025-05-15-preview"},
            )
            response = self._agents_client.send_request(request)
            response.raise_for_status()

            data = response.json()

            # Messages are returned newest-first. Find the first assistant message.
            for msg in data.get("data", []):
                if msg.get("role") == "assistant":
                    # Extract text content from the message
                    for content_block in msg.get("content", []):
                        if content_block.get("type") == "text":
                            return content_block["text"].get("value", "")

            return "The agent completed processing but did not return a text response."

        except Exception as e:
            logger.error("Failed to retrieve messages from thread %s: %s", thread_id, str(e))
            return f"Error retrieving response: {str(e)}"

    def _build_auto_callables(self) -> set:
        """
        Build a set of Python callables for enable_auto_function_calls.

        Each callable's __name__ must match the FunctionDefinition name so the SDK
        can route function calls from the agent to the correct Python function.
        The callables accept **kwargs and delegate to the ToolExecutor.
        """
        callables = set()

        for tool_def in ALL_TOOLS:
            # Create a closure that captures the tool name
            def make_callable(name: str):
                def tool_func(**kwargs: Any) -> str:
                    return self._tool_executor.execute(name, kwargs)

                # The SDK matches by function __name__
                tool_func.__name__ = name
                # Add a docstring for the SDK (optional but good practice)
                tool_func.__doc__ = f"Execute the {name} ANF operation."
                return tool_func

            callables.add(make_callable(tool_def.name))

        return callables

    def cleanup(self) -> None:
        """Delete the agent and clean up resources."""
        if self._agent:
            try:
                self._agents_client.delete_agent(self._agent.id)
                logger.info("Agent deleted: %s", self._agent.id)
            except Exception as e:
                logger.warning("Failed to delete agent %s: %s", self._agent.id, str(e))

    @staticmethod
    def _tool_to_dict(tool: FunctionDefinition) -> dict:
        """Convert a FunctionDefinition to the dict format expected by create_agent."""
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
