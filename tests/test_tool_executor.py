"""
Unit tests for the Tool Executor.

Tests the dispatch logic and serialization without requiring
actual Azure credentials or ANF resources.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.anf_client.models import CapacityPoolInfo, OperationResult, SnapshotInfo, VolumeInfo
from src.tools.executor import ToolExecutor


@pytest.fixture
def mock_anf_client():
    """Create a mock ANF client with predefined responses."""
    client = MagicMock()

    # Mock list_volumes
    client.list_volumes.return_value = [
        VolumeInfo(
            name="trading-data",
            resource_group="rg-prod",
            account_name="anf-account-01",
            pool_name="pool-premium",
            location="eastus2",
            service_level="Premium",
            quota_in_bytes=1099511627776,
            quota_in_gib=1024.0,
            protocol_types=["NFSv4.1"],
            provisioning_state="Succeeded",
            throughput_mibps=64.0,
            creation_token="trading-data",
        ),
        VolumeInfo(
            name="risk-analytics",
            resource_group="rg-prod",
            account_name="anf-account-01",
            pool_name="pool-premium",
            location="eastus2",
            service_level="Premium",
            quota_in_bytes=2199023255552,
            quota_in_gib=2048.0,
            protocol_types=["NFSv4.1"],
            provisioning_state="Succeeded",
            throughput_mibps=128.0,
            creation_token="risk-analytics",
        ),
    ]

    # Mock create_snapshot
    client.create_snapshot.return_value = OperationResult(
        success=True,
        operation="create_snapshot",
        resource_name="pre-batch-20250126",
        details="Snapshot 'pre-batch-20250126' created on volume 'trading-data'.",
    )

    # Mock list_snapshots
    client.list_snapshots.return_value = [
        SnapshotInfo(
            name="pre-batch-20250126",
            volume_name="trading-data",
            location="eastus2",
            provisioning_state="Succeeded",
        ),
    ]

    # Mock resize_volume
    client.resize_volume.return_value = OperationResult(
        success=True,
        operation="resize_volume",
        resource_name="risk-analytics",
        details="Volume 'risk-analytics' resized from 2048.0 GiB to 3072 GiB.",
    )

    # Mock list_capacity_pools
    client.list_capacity_pools.return_value = [
        CapacityPoolInfo(
            name="pool-premium",
            resource_group="rg-prod",
            location="eastus2",
            service_level="Premium",
            size_in_bytes=4398046511104,
            size_in_gib=4096.0,
            provisioning_state="Succeeded",
        )
    ]

    # Mock delete_volume
    client.delete_volume.return_value = OperationResult(
        success=True,
        operation="delete_volume",
        resource_name="trading-data",
        details="Volume 'trading-data' deleted successfully.",
    )

    # Mock revert_volume
    client.revert_volume.return_value = OperationResult(
        success=True,
        operation="revert_volume",
        resource_name="trading-data",
        details="Volume 'trading-data' reverted successfully to snapshot.",
    )

    return client


@pytest.fixture
def executor(mock_anf_client):
    """Create a ToolExecutor with the mock ANF client."""
    return ToolExecutor(mock_anf_client)


class TestToolExecutor:
    """Tests for the ToolExecutor dispatch and serialization."""

    def test_list_volumes(self, executor, mock_anf_client):
        result = executor.execute("list_volumes", {})
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "trading-data"
        assert parsed[1]["name"] == "risk-analytics"
        mock_anf_client.list_volumes.assert_called_once_with(pool_name=None)

    def test_list_volumes_with_pool(self, executor, mock_anf_client):
        executor.execute("list_volumes", {"pool_name": "pool-ultra"})
        mock_anf_client.list_volumes.assert_called_once_with(pool_name="pool-ultra")

    def test_create_snapshot(self, executor, mock_anf_client):
        result = executor.execute(
            "create_snapshot",
            {
                "volume_name": "trading-data",
                "snapshot_name": "pre-batch-20250126",
            },
        )
        parsed = json.loads(result)

        assert parsed["success"] is True
        assert parsed["operation"] == "create_snapshot"
        assert parsed["resource_name"] == "pre-batch-20250126"
        mock_anf_client.create_snapshot.assert_called_once_with(
            volume_name="trading-data",
            snapshot_name="pre-batch-20250126",
            pool_name=None,
        )

    def test_list_snapshots(self, executor, mock_anf_client):
        result = executor.execute("list_snapshots", {"volume_name": "trading-data"})
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "pre-batch-20250126"

    def test_resize_volume(self, executor, mock_anf_client):
        result = executor.execute(
            "resize_volume",
            {
                "volume_name": "risk-analytics",
                "new_size_gib": 3072,
            },
        )
        parsed = json.loads(result)

        assert parsed["success"] is True
        assert parsed["operation"] == "resize_volume"

    def test_list_capacity_pools(self, executor, mock_anf_client):
        result = executor.execute("list_capacity_pools", {})
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "pool-premium"
        mock_anf_client.list_capacity_pools.assert_called_once()

    def test_delete_volume(self, executor, mock_anf_client):
        result = executor.execute(
            "delete_volume",
            {
                "volume_name": "trading-data",
            },
        )
        parsed = json.loads(result)

        assert parsed["success"] is True
        assert parsed["operation"] == "delete_volume"
        mock_anf_client.delete_volume.assert_called_once_with(volume_name="trading-data", pool_name=None)

    def test_revert_volume(self, executor, mock_anf_client):
        result = executor.execute(
            "revert_volume",
            {
                "volume_name": "trading-data",
                "snapshot_id": "snap-1234",
            },
        )
        parsed = json.loads(result)

        assert parsed["success"] is True
        assert parsed["operation"] == "revert_volume"
        mock_anf_client.revert_volume.assert_called_once_with(
            volume_name="trading-data", snapshot_id="snap-1234", pool_name=None
        )

    def test_unknown_function(self, executor):
        result = executor.execute("nonexistent_function", {})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "Unknown function" in parsed["error"]

    def test_exception_handling(self, executor, mock_anf_client):
        mock_anf_client.list_volumes.side_effect = Exception("Connection refused")

        result = executor.execute("list_volumes", {})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "Connection refused" in parsed["error"]


class TestModels:
    """Tests for the Pydantic model serialization."""

    def test_volume_info_serialization(self):
        vol = VolumeInfo(
            name="test-vol",
            resource_group="rg",
            account_name="acct",
            pool_name="pool",
            location="eastus2",
            service_level="Premium",
            quota_in_bytes=107374182400,
            quota_in_gib=100.0,
            protocol_types=["NFSv4.1"],
            provisioning_state="Succeeded",
            creation_token="test-vol",
        )
        data = vol.model_dump(mode="json")
        assert data["name"] == "test-vol"
        assert data["quota_in_gib"] == 100.0
        assert data["service_level"] == "Premium"

    def test_operation_result_success(self):
        result = OperationResult(
            success=True,
            operation="create_snapshot",
            resource_name="snap-01",
            details="Snapshot created.",
        )
        data = result.model_dump(mode="json")
        assert data["success"] is True
        assert data["error"] is None

    def test_operation_result_failure(self):
        result = OperationResult(
            success=False,
            operation="resize_volume",
            resource_name="vol-01",
            details="",
            error="Minimum volume size is 100 GiB.",
        )
        data = result.model_dump(mode="json")
        assert data["success"] is False
        assert "100 GiB" in data["error"]
