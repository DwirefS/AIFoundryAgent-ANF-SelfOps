# Security Guide

## Authentication: DefaultAzureCredential Only

Never hardcode credentials. Never use connection strings with embedded keys.

## RBAC: Least Privilege

| Identity | Resource | Role | Why |
|----------|----------|------|-----|
| Agent MI | ANF Account | Contributor | Manage volumes/snapshots |
| Agent MI | Foundry Project | Azure AI User | Create/run agents |
| Developer | ANF Account | Reader | View-only for debugging |

Scope to the **resource**, not the resource group or subscription.

## Secret Management

- No secrets in code, env files committed to git, or Bicep parameters
- Use Azure Key Vault for any secrets beyond DefaultAzureCredential
- .env is gitignored — never commit

## Agent Prompt Security

- System instructions require confirmation for destructive ops
- Consider code-level guardrails (not just prompt-level) for production
- Log all tool executions for audit

## Network

- ANF volumes exist in customer VNet
- Agent compute must be in same VNet or peered
- Foundry endpoint is public (management.azure.com)
- Consider Private Endpoints for production
