"""
ANF Foundry SelfOps — Main Entry Point.

Wires together:
  - ANFClient (azure-mgmt-netapp SDK wrapper)
  - ToolExecutor (function call dispatcher)
  - ANFSelfOpsAgent (Foundry Agent with function calling)

And starts an interactive conversation loop.

Usage:
    python -m src.main
"""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv

from .anf_client.client import ANFClient
from .tools.executor import ToolExecutor
from .agent.foundry_agent import ANFSelfOpsAgent

# ── Logging Setup ────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("anf-selfops")

# Quiet down noisy Azure SDK loggers
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)


def load_config() -> dict:
    """Load configuration from environment variables."""
    load_dotenv()

    required_vars = [
        "AZURE_AI_PROJECT_ENDPOINT",
        "MODEL_DEPLOYMENT_NAME",
        "AZURE_SUBSCRIPTION_ID",
        "ANF_RESOURCE_GROUP",
        "ANF_ACCOUNT_NAME",
        "ANF_POOL_NAME",
    ]

    config = {}
    missing = []
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing.append(var)
        config[var] = value

    if missing:
        print(f"\n❌ Missing required environment variables: {', '.join(missing)}")
        print("   Copy .env.template to .env and fill in your values.\n")
        sys.exit(1)

    return config


def run_interactive(agent: ANFSelfOpsAgent) -> None:
    """Run an interactive conversation loop with the agent."""
    print("\n" + "=" * 66)
    print("  ANF SelfOps Agent Ready")
    print("  Powered by Azure AI Foundry × Azure NetApp Files")
    print("=" * 66)
    print("\nType your request in natural language. Examples:")
    print('  • "List all volumes in the production pool"')
    print('  • "Take a snapshot of trading-data called pre-batch-jan26"')
    print('  • "Resize risk-analytics to 3 TiB"')
    print('  • "Show me the account info"')
    print('\nType "quit" or "exit" to stop.\n')

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("\nGoodbye!")
            break

        print("\nAgent: ", end="", flush=True)
        try:
            response = agent.send_message(user_input)
            print(response)
        except Exception as e:
            logger.error("Error processing message: %s", str(e), exc_info=True)
            print(f"Error: {str(e)}")
        print()


def main() -> None:
    """Main entry point."""
    config = load_config()

    # ── Initialize ANF Client ─────────────────────────────────────
    logger.info("Initializing ANF Client...")
    anf_client = ANFClient(
        subscription_id=config["AZURE_SUBSCRIPTION_ID"],
        resource_group=config["ANF_RESOURCE_GROUP"],
        account_name=config["ANF_ACCOUNT_NAME"],
        pool_name=config["ANF_POOL_NAME"],
    )

    # ── Initialize Tool Executor ──────────────────────────────────
    tool_executor = ToolExecutor(anf_client)

    # ── Initialize Foundry Agent ──────────────────────────────────
    logger.info("Initializing Foundry Agent...")
    agent = ANFSelfOpsAgent(
        project_endpoint=config["AZURE_AI_PROJECT_ENDPOINT"],
        model_deployment=config["MODEL_DEPLOYMENT_NAME"],
        tool_executor=tool_executor,
    )

    try:
        # Create the agent in Foundry
        agent.setup()
        # Start interactive loop
        run_interactive(agent)
    finally:
        # Always clean up the agent
        logger.info("Cleaning up...")
        agent.cleanup()
        logger.info("Done.")


if __name__ == "__main__":
    main()
