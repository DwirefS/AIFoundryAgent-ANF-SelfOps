# Deployment, Testing, and Validation Guide

This guide explores the exact paths for deploying the **AI Foundry Agent for ANF**, alongside the methodologies used for validating and testing the infrastructure and deterministic agent operations.

---

## 🚀 Deployment Guide

We offer three distinct approaches to deploying the full stack, depending on your target environment.

### 1. Fully Automated IaC with Bicep

The most robust and repeatable mechanism is using the provided Bicep templates located in `infra/`. This creates all Azure resources from scratch.

* **What it deploys:**
  * An Azure Virtual Network (VNet) with a delegated `Microsoft.NetApp/volumes` subnet.
  * An Azure NetApp Files Account, Capacity Pool, and initial Volume.
  * An Azure AI Foundry Hub/Project with a GPT-4o model deployment.
  * A comprehensive system-assigned **Managed Identity** mapped out with specific RBAC rules (e.g. `Contributor` on the ANF Resource Group, `Azure AI User` on the AI Hub).

* **How to run:**

  ```bash
  az deployment group create \
    --resource-group <resource-group-name> \
    --template-file infra/main.bicep \
    --parameters infra/parameters.json
  ```

### 2. Containerized / App Hosting (Docker)

The entire agent runtime has been packaged securely using a multi-stage `Dockerfile`.

* **The builder stage:** Pulls down native dependencies securely.
* **The runtime stage:** A minimalist image copying solely the compiled artifacts, dramatically dropping the attack surface.

* **How to run locally:**

  ```bash
  docker build -t anf-foundry-selfops .
  docker run -it --env-file .env anf-foundry-selfops
  ```

* **Production Recommendation:** For production workloads, we explicitly advise deploying the built container image to **Azure Container Apps**. It is serverless, scales to zero (since the Agent only processes data intermittently on-demand), and natively mounts the required Managed Identity.

### 3. CI/CD Pipeline (GitHub Actions)

Continuous execution and verification are codified out-of-the-box. Any changes to the main branch automatically invoke:

1. `ruff` Linting.
2. `mypy` Static type checking over every function.
3. Automated unit-tests validating Python logic.
4. (Optionally) the deployment pipeline itself.

---

## 🧪 Testing and Validation Scenarios

This repository adopts a strict **"Testing Pyramid"** approach, keeping development fast while ensuring production-grade safety when connecting agent logic to the physical storage plane.

### 1. Isolated Unit Tests (Offline Validation)

These define the core logic of the Python codebase. **They do not require Azure credentials.** Instead, they mock the raw Azure Python Management SDK to validate how the orchestrator functions react.

* **What we validate:**
  * **Input constraints:** If the Agent tells the Python executor to resize an ANF volume down to 50 GiB instead of 100+ GiB, do the constraint validators correctly fail and return a parsed error to the GPT-prompt?
  * **Tool Dispatch:** Validate routing logic between the Agent Tool commands and the `ANFClient` SDK wrappers.
  
* **How to run:**

  ```bash
  pytest tests/ -v -m "not integration"
  ```

### 2. Live Integration Tests

These tests operate on **actual Azure Subscriptions**. They require the AI Agent application to have valid Entra ID credentials (or Managed Identity logic).

* **What we validate:**
  * Real round-trip execution over the Azure Resource Manager API (ARM).
  * Network peering validity, Managed Identity permission assertion, and physical capacity.

* **How to run:**

  ```bash
  # Ensure your .env is loaded first with a valid Sub ID!
  pytest tests/ -v -m integration
  ```

### 3. End-to-End Validation / Smoke Testing Scripts

The codebase explicitly ships with several BASH scripts designed to aggressively test all operational scenarios for a QA environment.

#### Scenario: `scripts/smoke-test.sh`

This script executes *every single Function Tool* asynchronously. It sequentially provisions volume test-snapshots, queries sizes, resizes volumes by 1 GiB, retrieves the list of Active Directories on the NetApp Account, and eventually deletes the snapshots.

#### Scenario: `scripts/validate.sh`

A passive validation script. Before moving to Production, running `bash scripts/validate.sh` systematically probes the local or container environment for:

1. Valid Python bindings and package imports.
2. An active cached Azure CLI token (`az account show`).
3. Appropriate reachability directly to the Azure AI Foundry endpoints.

---

### Understanding the Loop

If you combine both Bicep (`infra/main.bicep`) and the validation scripts (`scripts/validate.sh`), you ensure absolute security and deterministic performance prior to allowing an LLM to take control.
