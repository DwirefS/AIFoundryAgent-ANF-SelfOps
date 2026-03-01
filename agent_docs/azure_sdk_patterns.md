# Azure SDK Patterns

## Authentication

Always use `DefaultAzureCredential`. It tries, in order:
1. Environment variables (AZURE_CLIENT_ID/SECRET/TENANT_ID)
2. Managed Identity (on Azure VMs, AKS, Container Apps)
3. Azure CLI (`az login`)
4. Azure PowerShell
5. Interactive browser

```python
from azure.identity import DefaultAzureCredential
credential = DefaultAzureCredential()
# Pass to any Azure SDK client — never store or pass secrets
```

## Long-Running Operations (LRO)

ANF management operations (snapshot create, volume resize) are LROs:

```python
# begin_* returns a poller, NOT the result
poller = client.snapshots.begin_create(rg, account, pool, volume, name, body)

# .result() blocks until complete (can take 10-60 seconds)
snapshot = poller.result()

# For async code:
snapshot = await poller.result()
```

## Error Handling

```python
from azure.core.exceptions import (
    HttpResponseError,      # 4xx/5xx from Azure
    ResourceNotFoundError,  # 404
    ClientAuthenticationError,  # Auth failures
    ServiceRequestError,    # Network/transport errors
)

try:
    result = client.volumes.get(rg, account, pool, volume)
except ResourceNotFoundError:
    logger.warning("Volume %s not found", volume)
except HttpResponseError as e:
    logger.error("Azure error %d: %s", e.status_code, e.message)
except ServiceRequestError as e:
    logger.error("Network error: %s", str(e))
```

## Pagination

SDK list methods return iterables that handle pagination automatically:

```python
# This handles all pages transparently
for volume in client.volumes.list(rg, account, pool):
    process(volume)
```

## Resource Name Extraction

SDK returns fully qualified names like `account/pool/volume`. Extract the short name:

```python
short_name = volume.name.split("/")[-1] if "/" in volume.name else volume.name
```
