"""
Azure AI Foundry Agent — ANF SelfOps.

Sets up a Foundry Agent with function calling tools that manage ANF resources.
Uses the stable GA SDK (azure-ai-projects 1.0.0 / azure-ai-agents 1.x) with
the threads + runs + create_and_process_run pattern.

SDK Reference:
  - azure-ai-agents: https://learn.microsoft.com/python/api/overview/azure/ai-agents-readme
  - Function calling: https://learn.microsoft.com/azure/ai-foundry/agents/how-to/tools-classic/function-calling

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
from typing import Optional

from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import (
    FunctionTool,
    MessageRole,
    RequiredFunctionToolCall,
    RunStatus,
    SubmitToolOutputsAction,
    ToolOutput,
)
from azure.identity import DefaultAzureCredential

from .instructions import AGENT_INSTRUCTIONS, AGENT_NAME
from ..tools.definitions import ALL_TOOLS
from ..tools.executor import ToolExecutor

logger = logging.getLogger(__name__)


class ANFSelfOpsAgent:
    """
    Foundry Agent for ANF SelfOps — manages ANF infrastructure via function calling.

    Lifecycle:
        1. __init__: Connect to Foundry project
        2. setup: Create the agent with function tools
        3. run_conversation: Interactive loop (create thread → send message → process → respond)
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
        self._project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=self._credential,
        )
        self._model = model_deployment
        self._tool_executor = tool_executor
        self._agent = None
        self._thread = None

        logger.info("ANFSelfOpsAgent initialized (endpoint=%s, model=%s)", project_endpoint, model_deployment)

    def setup(self) -> None:
        """Create the Foundry agent with ANF function tools."""
        logger.info("Creating Foundry agent: %s", AGENT_NAME)

        # Build function tool definitions
        tools = [{"type": "function", "function": self._tool_to_dict(t)} for t in ALL_TOOLS]

        self._agent = self._project_client.agents.create_agent(
            model=self._model,
            name=AGENT_NAME,
            instructions=AGENT_INSTRUCTIONS,
            tools=tools,
        )
        logger.info("Agent created: id=%s, name=%s", self._agent.id, self._agent.name)

    def create_thread(self) -> str:
        """Create a new conversation thread. Returns thread ID."""
        self._thread = self._project_client.agents.create_thread()
        logger.info("Thread created: %s", self._thread.id)
        return self._thread.id

    def send_message(self, user_message: str) -> str:
        """
        Send a user message to the agent and return the assistant's response.

        This handles the full function-calling loop:
          1. Create message in thread
          2. Create a run
          3. Poll until complete or requires_action
          4. If requires_action → execute tools → submit outputs → repeat
          5. Return final assistant message

        Args:
            user_message: The user's natural-language request.

        Returns:
            The agent's response text.
        """
        if not self._thread:
            self.create_thread()

        # Add user message to thread
        self._project_client.agents.create_message(
            thread_id=self._thread.id,
            role=MessageRole.USER,
            content=user_message,
        )
        logger.info("User message sent: %s", user_message[:100])

        # Create and process the run (handles polling internally)
        run = self._project_client.agents.create_run(
            thread_id=self._thread.id,
            agent_id=self._agent.id,
        )

        # Poll and handle function calls
        while True:
            run = self._project_client.agents.get_run(
                thread_id=self._thread.id,
                run_id=run.id,
            )

            if run.status == RunStatus.COMPLETED:
                break
            elif run.status == RunStatus.FAILED:
                logger.error("Run failed: %s", run.last_error)
                return f"Error: The agent encountered an issue — {run.last_error}"
            elif run.status == RunStatus.REQUIRES_ACTION:
                run = self._handle_requires_action(run)
            elif run.status in (RunStatus.CANCELLED, RunStatus.EXPIRED):
                return f"Run {run.status}. Please try again."
            else:
                # Still in progress — will poll again
                import time
                time.sleep(0.5)

        # Retrieve the assistant's response
        messages = self._project_client.agents.list_messages(thread_id=self._thread.id)
        # Get the latest assistant message
        for msg in messages.data:
            if msg.role == MessageRole.AGENT:
                # Extract text content
                for content in msg.content:
                    if hasattr(content, "text"):
                        return content.text.value
                break

        return "The agent completed processing but did not return a text response."

    def _handle_requires_action(self, run) -> object:
        """
        Handle a run that requires function tool execution.

        Extracts the function calls from the run, executes them via
        the ToolExecutor, and submits the outputs back to the agent.
        """
        if not isinstance(run.required_action, SubmitToolOutputsAction):
            logger.warning("Unexpected required_action type: %s", type(run.required_action))
            return run

        tool_outputs = []

        for tool_call in run.required_action.submit_tool_outputs.tool_calls:
            if isinstance(tool_call, RequiredFunctionToolCall):
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)

                logger.info("Agent requested tool: %s(%s)", function_name, arguments)

                # Execute the function via the ToolExecutor
                result_json = self._tool_executor.execute(function_name, arguments)

                logger.info("Tool result: %s", result_json[:200])

                tool_outputs.append(
                    ToolOutput(
                        tool_call_id=tool_call.id,
                        output=result_json,
                    )
                )

        # Submit tool outputs back to the run
        if tool_outputs:
            run = self._project_client.agents.submit_tool_outputs_to_run(
                thread_id=self._thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs,
            )
            logger.info("Submitted %d tool outputs", len(tool_outputs))

        return run

    def cleanup(self) -> None:
        """Delete the agent and clean up resources."""
        if self._agent:
            self._project_client.agents.delete_agent(self._agent.id)
            logger.info("Agent deleted: %s", self._agent.id)

    @staticmethod
    def _tool_to_dict(tool: FunctionTool) -> dict:
        """Convert a FunctionTool to the dict format expected by create_agent."""
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
