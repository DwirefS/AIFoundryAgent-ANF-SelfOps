# Cloud Design Patterns

## Retry with Exponential Backoff

Use for transient Azure failures (throttling, network blips):

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from azure.core.exceptions import HttpResponseError, ServiceRequestError

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((HttpResponseError, ServiceRequestError)),
)
def resilient_operation(self, ...):
    ...
```

Do NOT retry on: `ClientAuthenticationError`, `ResourceNotFoundError`, validation errors.

## Circuit Breaker

Prevent cascading failures when ANF or Foundry is down:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.timeout = recovery_timeout
        self.state = "CLOSED"  # CLOSED → OPEN → HALF_OPEN
        self.last_failure_time = None
```

## Structured Configuration (pydantic-settings)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    azure_ai_project_endpoint: str
    model_deployment_name: str = "gpt-4o"
    azure_subscription_id: str
    anf_resource_group: str
    anf_account_name: str
    anf_pool_name: str
    log_level: str = "INFO"
    log_format: str = "json"  # "json" for production, "text" for dev

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

## Graceful Shutdown

Always clean up Foundry agents on exit:

```python
import signal
import sys

def shutdown_handler(signum, frame):
    logger.info("Shutting down — cleaning up agent...")
    agent.cleanup()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
```

## Health Endpoints

For container orchestration (AKS, Container Apps):

- `/health` — liveness: process is running
- `/ready` — readiness: can serve requests (ANF reachable, Foundry reachable)
- `/metrics` — Prometheus-format metrics (optional)
