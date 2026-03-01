# Testing Strategy

## Test Pyramid

```
         ╱ E2E (manual — run agent interactively) ╲
        ╱ Integration (requires Azure credentials)  ╲
       ╱ Unit tests (mocked — no credentials needed)  ╲
```

## Unit Tests (default — `pytest tests/ -m "not integration"`)

Mock the Azure SDK clients. Test:
- Tool executor dispatch logic
- Pydantic model serialization
- Argument validation
- Error handling paths

```python
@pytest.fixture
def mock_anf_client():
    client = MagicMock()
    client.list_volumes.return_value = [VolumeInfo(...)]
    return client
```

## Integration Tests (`pytest tests/ -m integration`)

Require real Azure credentials and ANF resources. Mark with `@pytest.mark.integration`:

```python
@pytest.mark.integration
def test_list_volumes_real():
    client = ANFClient(...)
    volumes = client.list_volumes()
    assert isinstance(volumes, list)
```

## Running Tests

```bash
# Unit only (CI, no creds)
pytest tests/ -v -m "not integration" --tb=short

# Integration (needs .env with real values)
pytest tests/ -v -m integration

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Single test file
pytest tests/test_tool_executor.py -v
```

## Test File Naming

- `tests/test_<module>.py` mirrors `src/<module>.py`
- Test classes: `class Test<ClassName>:`
- Test methods: `def test_<behavior_being_tested>():`
