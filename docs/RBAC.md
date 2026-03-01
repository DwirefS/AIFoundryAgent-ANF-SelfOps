# RBAC & Security Guide — ANF Foundry SelfOps

## Overview

This accelerator requires two sets of permissions:

1. **Foundry Agent permissions** — to create and run agents in Azure AI Foundry
2. **ANF Management permissions** — to execute control-plane operations on ANF resources

Both should follow **least-privilege principles**: grant only what's needed, scoped as narrowly as possible.

---

## Required RBAC Role Assignments

### For the Agent's Identity (Managed Identity / Service Principal)

| Resource | Role | Scope | Purpose |
|----------|------|-------|---------|
| AI Foundry Project | `Azure AI User` | Project resource | Create/run agents, manage threads |
| ANF Account | `Contributor` | ANF account resource | Manage volumes, snapshots, pools |

### For the Developer (Interactive Use)

| Resource | Role | Scope | Purpose |
|----------|------|-------|---------|
| AI Foundry Project | `Azure AI User` | Project resource | Run the agent interactively |
| ANF Account | `Reader` | ANF account resource | View resources (agent handles writes) |

---

## Authentication Flow

```
Developer Workstation          Azure Resources
─────────────────────          ───────────────
                               
  az login                     
    │                          
    ▼                          
  DefaultAzureCredential       
    │                          
    ├──► AI Foundry Project ──► Agent Service (create agent, run threads)
    │                          
    └──► ARM REST API ────────► ANF Control Plane (snapshots, resize, list)
```

In production, replace `az login` with **Managed Identity** (Azure VM, AKS, Container Apps):

```
Azure VM / AKS Pod            Azure Resources
─────────────────────          ───────────────
                               
  System-Assigned MI           
    │                          
    ▼                          
  DefaultAzureCredential       
  (auto-detects MI)            
    │                          
    ├──► AI Foundry Project
    └──► ANF Control Plane
```

---

## Setting Up RBAC

### Option 1: Azure CLI

```bash
# Variables
IDENTITY_PRINCIPAL_ID="<managed-identity-or-sp-object-id>"
ANF_ACCOUNT_RESOURCE_ID="/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.NetApp/netAppAccounts/<account>"
FOUNDRY_PROJECT_RESOURCE_ID="/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.MachineLearningServices/workspaces/<project>"

# ANF Contributor (scoped to ANF account only — not the entire resource group)
az role assignment create \
  --assignee "$IDENTITY_PRINCIPAL_ID" \
  --role "Contributor" \
  --scope "$ANF_ACCOUNT_RESOURCE_ID"

# AI Foundry User
az role assignment create \
  --assignee "$IDENTITY_PRINCIPAL_ID" \
  --role "Azure AI User" \
  --scope "$FOUNDRY_PROJECT_RESOURCE_ID"
```

### Option 2: Bicep (see infra/modules/identity.bicep)

The included Bicep templates create a User-Assigned Managed Identity and assign both roles.

---

## Security Best Practices

1. **Never store credentials in code.** `DefaultAzureCredential` handles the authentication chain automatically.

2. **Scope RBAC narrowly.** Assign `Contributor` to the ANF **account** resource, not the resource group or subscription.

3. **Use Managed Identity in production.** Service principal secrets expire and can leak. Managed Identity is passwordless.

4. **Enable Azure Activity Log monitoring.** Every ANF management operation (snapshot create, volume resize) generates an Activity Log entry with the caller's identity.

5. **Enable Foundry tracing.** Connect Application Insights to your Foundry project for full observability of agent decisions and tool calls.

6. **Implement confirmation for destructive ops.** The agent instructions require user confirmation before delete operations. This is enforced in the agent's system prompt, not in code — consider adding code-level guardrails for production.

7. **Network isolation.** ANF volumes exist in a customer VNet. The agent's compute (VM, AKS) should be in the same VNet or have appropriate peering. The Foundry agent endpoint is a public service, but ANF management goes through ARM (management.azure.com).

---

## Audit Trail

Every operation the agent performs is traceable through three channels:

| Channel | What's logged | Retention |
|---------|---------------|-----------|
| Azure Activity Log | All ARM operations (snapshot create, volume resize) with caller identity | 90 days (default) |
| Foundry Agent Tracing | Agent reasoning, tool calls, function arguments, results | Configurable via Application Insights |
| Application Logs | Python logging from this accelerator (src/agent, src/anf_client) | Your log infrastructure |

For capital markets compliance, consider exporting Activity Logs to a Log Analytics workspace or SIEM for long-term retention.
