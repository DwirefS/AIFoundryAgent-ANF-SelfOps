# Deployment Guide

## Docker

```bash
docker build -t anf-foundry-selfops .
docker run --env-file .env anf-foundry-selfops
```

Multi-stage build: builder stage installs deps, runtime stage copies only what's needed.

## CI/CD (GitHub Actions)

Pipeline stages: lint → type-check → unit-test → bicep-validate → (on main) docker-build → push

## Infrastructure (Bicep)

```bash
az deployment group create \
  --resource-group <rg> \
  --template-file infra/main.bicep \
  --parameters infra/parameters.json
```

Deploys: VNet, ANF account/pool/volume, Managed Identity, RBAC assignments.

## Container Deployment Options

- **Azure Container Apps**: Serverless, scale-to-zero, simplest for this workload
- **AKS**: Full Kubernetes, if part of larger platform
- **Azure VM**: Direct deployment for dev/test
