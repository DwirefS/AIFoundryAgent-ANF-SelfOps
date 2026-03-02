# AI Storage Ops — Comprehensive Lab Guide

Welcome to the **AI Storage Ops** accelerator lab. In this guide, you will deploy a production-ready Azure AI Foundry Agent capable of autonomously provisioning, protecting, resizing, and deleting Azure NetApp Files infrastructure using natural language.

---

## Prerequisites

Before starting this lab, ensure you have:

1. An active **Azure Subscription** where you have at least `Contributor` rights.
2. The **Azure CLI** installed and authenticated (`az login`).
3. Python 3.11+ installed.
4. Git cloned to your local environment.

---

## Phase 1: Automated Infrastructure Deployment

This project ships with a unified `deploy.sh` script that provisions BOTH your underlying storage network (via Bicep IaC) AND your Agentic AI (via Azure CLI).

### Step 1: Run the Deployment Script

Open your terminal and execute:

```bash
bash scripts/deploy.sh <your-subscription-id> anf-ai-storage-rg eastus2
```

**What happens in the background?**

1. **Azure Resource Manager (Bicep):** Provisions a Virtual Network, delegates a subnet to `Microsoft.NetApp/volumes`, and creates the base Azure NetApp Files Account and Capacity Pool. It also creates a system-assigned Managed Identity with `Contributor` rights specifically over this resource group.
2. **Azure AI Foundry (CLI):** Provisions an Azure OpenAI resource, deploys a `gpt-4o` model, then creates your AI Foundry Hub and Project, linking the model connections natively.

### Step 2: Configure Your Environment Variables

Once the script completes, it will automatically generate an `.env.generated` file in your root directory containing all the endpoints and names.

Rename it to `.env`:

```bash
mv .env.generated .env
```

*Note: A `.gitignore` has been provided to ensure this file is never leaked into version control.*

---

## Phase 2: Interacting with the AI Storage Ops Agent

With your infrastructure alive, you are ready to talk to your Azure NetApp Files plane.

### Step 1: Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Step 2: Boot the AI Orchestrator

```bash
python -m src.main
```

You will be greeted by a terminal interface. The Foundry Agent will now read its systemic persona and initialize the 10 Function Tools it has been given to manage your storage.

### Step 3: Run the Test Scenarios

Copy and paste the following scenarios exactly as written. Watch the terminal as the Agent reasons about the request, realizes it needs more context, maps variables to JSON endpoints, and executes actions against the underlying Azure Control Plane faster than you ever could.

**Scenario A: Discovery**
> "Can you give me a summary of my Azure NetApp Files capacity pools?"

**Scenario B: Rapid Provisioning**
> "Take a snapshot of the trading-data volume and call it 'pre-batch-test'."

**Scenario C: Resizing**
> "Wait, the batch job requires more space. Resize 'trading-data' to 2048 GiB."

**Scenario D: Disaster Recovery (The Revert Tool)**
> "Oh no, the data was corrupted. Let's roll back. Revert the trading-data volume to the 'pre-batch-test' snapshot we just created!"

---

## Phase 3: Extending the Capabilities

*(Optional Homework)*

Now that you have deployed the full stack, explore the code to see how the connection works!

1. Open `src/tools/definitions.py` to see the JSON Schemas we provide the GPT engine.
2. Open `src/tools/executor.py` to see how those JSON callbacks route directly into the standard `azure-mgmt-netapp` SDK.
3. Try adding a brand new tool (e.g., `list_volume_backups` or `pause_snapshot_policy`).

---

## Conclusion & Teardown

To avoid incurring continuous cloud costs for your lab environment, when you are entirely finished testing:

```bash
bash scripts/teardown.sh anf-ai-storage-rg
```
