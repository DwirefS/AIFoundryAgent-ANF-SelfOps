# ANF Foundry SelfOps Accelerator

> **Azure AI Foundry Agents × Azure NetApp Files — Agentic Infrastructure Self-Operations**

This accelerator demonstrates how Azure AI Foundry Agents can autonomously manage Azure NetApp Files (ANF) infrastructure through function calling. An AI agent interprets natural-language requests and executes ANF control-plane operations — snapshots, volume listing, capacity resizing, and cloning — creating a **SelfOps** pattern where AI agents manage their own data infrastructure.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        User / Application                            │
│                                                                      │
│   "Take a snapshot of the trading-data volume"                       │
│   "List all volumes in the prod capacity pool"                       │
│   "Resize the analytics volume to 2 TiB"                            │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Azure AI Foundry Agent                             │
│                                                                      │
│   Model: GPT-4o (or GPT-4.1)                                        │
│   Instructions: ANF SelfOps specialist                               │
│   Tools: Function Calling (ANF operations)                           │
│                                                                      │
│   ┌────────────────────────────────────────────────────────────┐     │
│   │  Agent analyzes intent → selects tool → returns arguments  │     │
│   └────────────────────────────────────────────────────────────┘     │
└───────────────────────────┬──────────────────────────────────────────┘
                            │  requires_action / function_call
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Tool Executor (Python)                             │
│                                                                      │
│   Receives function name + arguments from agent                      │
│   Routes to ANF Client methods                                       │
│   Returns structured JSON results                                    │
│                                                                      │
│   Functions:                                                         │
│   ├── list_volumes          → NetAppManagementClient.volumes.list    │
│   ├── get_volume            → NetAppManagementClient.volumes.get     │
│   ├── create_snapshot       → NetAppManagementClient.snapshots.create│
│   ├── list_snapshots        → NetAppManagementClient.snapshots.list  │
│   ├── delete_snapshot       → NetAppManagementClient.snapshots.delete│
│   ├── resize_volume         → NetAppManagementClient.volumes.update  │
│   └── get_account_info      → NetAppManagementClient.accounts.get   │
└───────────────────────────┬──────────────────────────────────────────┘
                            │  azure-mgmt-netapp SDK
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│              Azure NetApp Files Control Plane API                     │
│                                                                      │
│   ARM REST API (management.azure.com)                                │
│   ├── Microsoft.NetApp/netAppAccounts                                │
│   ├── Microsoft.NetApp/netAppAccounts/capacityPools                  │
│   ├── Microsoft.NetApp/netAppAccounts/capacityPools/volumes          │
│   └── Microsoft.NetApp/netAppAccounts/capacityPools/volumes/snapshots│
│                                                                      │
│   Authentication: DefaultAzureCredential (Managed Identity / SP)     │
│   RBAC: Contributor on ANF resources (minimum)                       │
└──────────────────────────────────────────────────────────────────────┘
```

## Key Concepts

### What is SelfOps?

SelfOps is a pattern where AI agents autonomously manage the infrastructure and data lifecycle that supports their own workloads. Instead of human operators manually creating snapshots, resizing volumes, or managing capacity, the agent handles these operations through natural-language commands or automated triggers.

**Use Cases for Capital Markets / Financial Services:**

- **Pre-trade snapshot**: Agent creates an ANF snapshot before executing a batch analytics job, ensuring point-in-time recovery
- **Auto-resize**: Agent monitors volume utilization and requests capacity increases before thresholds are breached
- **Data lifecycle**: Agent manages snapshot retention, creating and pruning snapshots on schedule
- **Audit trail**: Every agent action is logged with full provenance — who requested, what was executed, and the result

### Why Azure NetApp Files?

ANF provides enterprise-grade, high-performance NAS storage with:

- **Sub-millisecond latency** — critical for trading and risk workloads
- **Instant snapshots** — zero-performance-impact, space-efficient snapshots via WAFL/redirect-on-write
- **Multi-protocol** — NFS, SMB, and now S3-compatible Object REST API (public preview)
- **Control Plane REST API** — full programmatic management via ARM, enabling agent-driven operations

### Why Azure AI Foundry?

Foundry Agent Service provides:

- **Managed agent hosting** with built-in conversation state
- **Function calling** — the agent decides when to call your functions based on user intent
- **Enterprise security** — Microsoft Entra ID, RBAC, VNet integration
- **Observability** — OpenTelemetry tracing for full execution visibility

---

## Repository Structure

```
anf-foundry-selfops/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── .env.template                      # Environment variable template
├── src/
│   ├── __init__.py
│   ├── main.py                        # Entry point — creates and runs the agent
│   ├── anf_client/
│   │   ├── __init__.py
│   │   ├── client.py                  # ANF Management SDK wrapper
│   │   └── models.py                  # Pydantic models for ANF responses
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── foundry_agent.py           # Foundry Agent setup + conversation loop
│   │   └── instructions.py            # System instructions for the agent
│   └── tools/
│       ├── __init__.py
│       ├── definitions.py             # Function tool JSON schemas
│       └── executor.py                # Tool dispatch — routes calls to ANF client
├── infra/
│   ├── main.bicep                     # Bicep template — full infrastructure
│   ├── modules/
│   │   ├── anf.bicep                  # ANF account, pool, volume
│   │   ├── foundry.bicep              # AI Foundry project + model deployment
│   │   └── identity.bicep             # Managed identity + RBAC assignments
│   └── parameters.json               # Deployment parameters
├── docs/
│   ├── architecture.mermaid           # Mermaid diagram source
│   └── RBAC.md                        # RBAC and security guidance
├── tests/
│   ├── __init__.py
│   ├── test_anf_client.py             # Unit tests for ANF client
│   └── test_tool_executor.py          # Unit tests for tool dispatch
└── .github/
    └── workflows/
        └── ci.yml                     # GitHub Actions CI pipeline
```

---

## Prerequisites

1. **Azure Subscription** with:
   - Azure NetApp Files registered (`Microsoft.NetApp` provider)
   - Azure AI Foundry project with a deployed GPT-4o (or GPT-4.1) model
   - A VNet with a delegated subnet for ANF (`Microsoft.NetApp/volumes`)

2. **Python 3.9+**

3. **Azure CLI** authenticated (`az login`)

4. **RBAC Roles**:
   - `Azure AI User` on the Foundry project (for agent operations)
   - `Contributor` on the ANF account/resource group (for management operations)

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/<your-org>/anf-foundry-selfops.git
cd anf-foundry-selfops
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.template .env
# Edit .env with your values
```

### 3. Deploy infrastructure (optional — if you need new ANF + Foundry resources)

```bash
az deployment group create \
  --resource-group <your-rg> \
  --template-file infra/main.bicep \
  --parameters infra/parameters.json
```

### 4. Run the agent

```bash
python -m src.main
```

You'll get an interactive prompt where you can issue natural-language commands:

```
ANF SelfOps Agent Ready. Type your request (or 'quit' to exit):

> List all volumes in the production pool
Agent: I found 3 volumes in the 'production' capacity pool:
  1. trading-data (1 TiB, Premium, 98.2 MiB/s throughput)
  2. risk-analytics (2 TiB, Premium, 196.4 MiB/s throughput)  
  3. market-feeds (500 GiB, Standard, 16 MiB/s throughput)

> Take a snapshot of trading-data called "pre-batch-20250126"
Agent: Snapshot created successfully:
  - Name: pre-batch-20250126
  - Volume: trading-data
  - Created: 2025-01-26T14:32:01Z
  - Provisioning State: Succeeded

> Resize risk-analytics to 3 TiB
Agent: Volume resized successfully:
  - Volume: risk-analytics
  - Previous Size: 2 TiB (2,199,023,255,552 bytes)
  - New Size: 3 TiB (3,298,534,883,328 bytes)
  - Note: ANF volume resize is online — no downtime required.
```

---

## Security & RBAC

See [docs/RBAC.md](docs/RBAC.md) for detailed security guidance.

**Key principles:**

- Use **Managed Identity** (not service principal secrets) in production
- Apply **least-privilege RBAC**: the agent's identity needs only `Contributor` on ANF resources, not the entire subscription
- All agent actions are **auditable** via Azure Activity Log and Foundry tracing
- **No credentials in code** — `DefaultAzureCredential` handles authentication chain

---

## SDK Versions

| Package | Version | Purpose |
|---------|---------|---------|
| `azure-ai-projects` | `1.0.0` (GA) | Foundry Agent Service client |
| `azure-ai-agents` | `1.1.0` (GA) | Agent operations (threads, runs, function calling) |
| `azure-mgmt-netapp` | `>=14.0.0` | ANF control-plane management |
| `azure-identity` | `>=1.17.0` | Authentication (DefaultAzureCredential) |
| `pydantic` | `>=2.0` | Response model validation |

> **Note on SDK evolution:** Microsoft is transitioning to a new Foundry SDK (`azure-ai-projects>=2.0.0b1`) built on the OpenAI Responses API. This accelerator uses the **stable GA SDK (1.x)** for production reliability. See `src/agent/foundry_agent.py` comments for migration guidance to the 2.x Responses pattern when it reaches GA.

---

## License

MIT — see [LICENSE](LICENSE)

---

## Related Accelerators

| Repo | Scenario |
|------|----------|
| `anf-onelake-fabric-agents` | ANF → Object REST API → OneLake S3 Shortcut → Fabric Data Agents |
| `anf-ai-search-rag` | ANF → Object REST API → OneLake S3 Shortcut → Azure AI Search → RAG |
| **`anf-foundry-selfops`** | **Foundry Agents → ANF Control Plane → SelfOps** (this repo) |
