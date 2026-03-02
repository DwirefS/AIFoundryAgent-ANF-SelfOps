# AI Storage Ops — Test Scenarios & Prompts

Now that your Azure AI Foundry Agent is armed with full Azure NetApp Files management capabilities, you can interact with it using natural language.

Here are structured test scenarios you can run to validate the agent's reasoning, tool dispatching, and REST API executions.

## Scenario 1: Infrastructure Discovery (Read-Only)

**Goal:** Verify the agent can correctly query the state of the account and the underlying capacity pools before acting.

**Prompts to try:**

1. *"Can you give me a summary of my Azure NetApp Files account? How many active directory connections does it have?"*
2. *"List all the capacity pools available right now. I need to know their service levels and total provisioned sizes."*
3. *"What volumes currently exist in the 'pool-premium' capacity pool? Give me a table with their names, sizes in GiB, and throughput."*

**Expected Agent Behavior:**
The agent should chain calls to `get_account_info`, `list_capacity_pools`, and `list_volumes`. It should parse the JSON results and present a clean markdown summary.

---

## Scenario 2: Provisioning & Protection (Write Operations)

**Goal:** Verify the agent can correctly sequence snapshots and capacity expansions without hallucinating parameters.

**Prompts to try:**

1. *"I have a volume named 'trading-data'. I'm about to run a massive batch job. Can you take a snapshot of it right now and name it 'pre-batch-test'?"*
2. *"Wait, before the batch job runs, we need more throughput. Please resize the 'trading-data' volume strictly to 2048 GiB."*
3. *"Can you list all the snapshots for 'trading-data' to verify the backup was taken successfully?"*

**Expected Agent Behavior:**
The agent must execute `create_snapshot`, wait for the Azure Long Running Operation (LRO) to return success, then execute `resize_volume`, and finally validate using `list_snapshots`.

---

## Scenario 3: The "Oops" Disaster Recovery (Destructive Operations)

**Goal:** Verify the agent respects destructive boundaries, understands relationships between volumes and snapshots, and can execute fast restorations.

**Prompts to try:**

1. *"The batch job corrupted the 'trading-data' volume! We need to roll back. Can you revert the volume back to the 'pre-batch-test' snapshot we just took?"*
2. *"Actually, this whole testing environment is no longer needed. Please delete the 'pre-batch-test' snapshot..."*
3. *"...and now permanently delete the 'trading-data' volume itself."*

**Expected Agent Behavior:**
The agent will call `list_snapshots` to find the Resource ID (`snapshot_id`) corresponding to the name you provided, then execute `revert_volume`. Afterward, it will execute `delete_snapshot` followed by `delete_volume`.

---

## Scenario 4: Error Handling & Guardrails

**Goal:** Verify the agent correctly parses error messages from the Azure REST API and relay them securely back to the user instead of crashing.

**Prompts to try:**

1. *"Resize the 'trading-data' volume to 50 GiB."*
   *(Expected: Agent reports failure because ANF minimum volume size is 100 GiB).*
2. *"Can you delete the 'pool-premium' capacity pool?"*
   *(Expected: Agent refuses or states it does not have a tool to delete capacity pools, demonstrating RBAC/Tool-level scoping).*
