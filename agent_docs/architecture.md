# Architecture — ANF Foundry SelfOps

## System Overview

```
User (natural language) → Foundry Agent → Function Calling → Tool Executor → ANF Client → ARM API → ANF Resources
```

## Component Responsibilities

### src/config/settings.py
Central configuration via pydantic-settings. All env vars validated at startup. Single source of truth for connection strings, resource names, feature flags.

### src/anf_client/
**Pure infrastructure layer.** No AI logic. Wraps azure-mgmt-netapp SDK. Every method:
- Accepts typed Python args (not raw JSON)
- Returns a Pydantic model (VolumeInfo, SnapshotInfo, OperationResult)
- Handles Azure SDK exceptions internally
- Logs operations with structured context

### src/tools/definitions.py
**Contract between agent and code.** Each FunctionTool defines:
- `name`: exact function identifier the model calls
- `description`: helps the model decide WHEN to call (be specific and descriptive)
- `parameters`: JSON Schema the model fills with arguments

### src/tools/executor.py
**Dispatch layer.** Pure routing — no business logic. Maps function_name → ANFClient method. Serializes Pydantic results to JSON strings for the agent.

### src/agent/foundry_agent.py
**Agent lifecycle manager.** Handles:
1. Agent creation with tools
2. Thread management (one thread per conversation)
3. The run loop: create_run → poll → handle requires_action → submit outputs
4. Message extraction from completed runs
5. Cleanup (agent deletion)

### src/main.py
**Wiring and CLI.** Creates instances, injects dependencies, runs the interactive loop. No business logic here — just composition.

## Data Flow (Create Snapshot Example)

```
1. User types: "Take a snapshot of trading-data called pre-batch"
2. main.py → agent.send_message("Take a snapshot...")
3. foundry_agent.py → create_message → create_run
4. Foundry service: GPT-4o analyzes intent → selects create_snapshot tool
5. Run enters REQUIRES_ACTION state with:
   {"name": "create_snapshot", "arguments": '{"volume_name":"trading-data","snapshot_name":"pre-batch"}'}
6. foundry_agent.py._handle_requires_action → extracts tool calls
7. executor.execute("create_snapshot", {"volume_name":"trading-data","snapshot_name":"pre-batch"})
8. executor._dispatch → anf_client.create_snapshot(volume_name="trading-data", snapshot_name="pre-batch")
9. ANFClient → client.snapshots.begin_create(...) → poller.result()
10. Returns OperationResult(success=True, ...)
11. executor._serialize → JSON string
12. foundry_agent.py → submit_tool_outputs_to_run(tool_outputs=[ToolOutput(...)])
13. Run resumes → GPT-4o generates natural language response
14. Run enters COMPLETED state
15. foundry_agent.py → list_messages → extract assistant text
16. Returns: "Snapshot 'pre-batch' created on volume 'trading-data'. ..."
```

## Adding a New Tool (Checklist)

1. `src/anf_client/client.py` — add method
2. `src/anf_client/models.py` — add response model if needed
3. `src/tools/definitions.py` — add FunctionTool + append to ALL_TOOLS
4. `src/tools/executor.py` — add to FUNCTION_REGISTRY + _dispatch
5. `tests/test_tool_executor.py` — add mock + test
6. `src/agent/instructions.py` — mention new tool in agent instructions
