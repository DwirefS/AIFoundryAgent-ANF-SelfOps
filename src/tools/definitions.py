"""
Function tool definitions for the ANF SelfOps Foundry Agent.

Each definition describes a function the agent can call, including:
  - name: unique function identifier
  - description: what the function does (helps the model decide when to call it)
  - parameters: JSON Schema for the function's arguments

Reference:
  https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools-classic/function-calling
"""

from azure.ai.agents.models import FunctionTool, ToolSet

# ── Individual Tool Definitions ──────────────────────────────────────

list_volumes_tool = FunctionTool(
    name="list_volumes",
    description=(
        "List all Azure NetApp Files volumes in a capacity pool. "
        "Returns volume names, sizes, service levels, throughput, and protocols. "
        "Use this when the user asks to see volumes, check capacity, or get an overview."
    ),
    parameters={
        "type": "object",
        "properties": {
            "pool_name": {
                "type": "string",
                "description": (
                    "Name of the ANF capacity pool. "
                    "If not specified, the default pool is used."
                ),
            },
        },
        "required": [],
        "additionalProperties": False,
    },
)

get_volume_tool = FunctionTool(
    name="get_volume",
    description=(
        "Get detailed information about a specific Azure NetApp Files volume, "
        "including its size, service level, throughput, protocols, and subnet. "
        "Use this when the user asks about a specific volume."
    ),
    parameters={
        "type": "object",
        "properties": {
            "volume_name": {
                "type": "string",
                "description": "Name of the ANF volume to retrieve.",
            },
            "pool_name": {
                "type": "string",
                "description": "Capacity pool name. Uses default if not specified.",
            },
        },
        "required": ["volume_name"],
        "additionalProperties": False,
    },
)

create_snapshot_tool = FunctionTool(
    name="create_snapshot",
    description=(
        "Create a point-in-time snapshot of an Azure NetApp Files volume. "
        "ANF snapshots are instant, space-efficient (redirect-on-write), "
        "and have zero performance impact. Use this when the user asks to "
        "take a snapshot, create a backup point, or preserve data before operations."
    ),
    parameters={
        "type": "object",
        "properties": {
            "volume_name": {
                "type": "string",
                "description": "Name of the ANF volume to snapshot.",
            },
            "snapshot_name": {
                "type": "string",
                "description": (
                    "Name for the new snapshot. Should be descriptive, e.g., "
                    "'pre-batch-20250126' or 'daily-backup-Mon'."
                ),
            },
            "pool_name": {
                "type": "string",
                "description": "Capacity pool name. Uses default if not specified.",
            },
        },
        "required": ["volume_name", "snapshot_name"],
        "additionalProperties": False,
    },
)

list_snapshots_tool = FunctionTool(
    name="list_snapshots",
    description=(
        "List all snapshots for an Azure NetApp Files volume. "
        "Returns snapshot names, creation times, and provisioning states. "
        "Use this when the user asks to see existing snapshots or check backup status."
    ),
    parameters={
        "type": "object",
        "properties": {
            "volume_name": {
                "type": "string",
                "description": "Name of the ANF volume whose snapshots to list.",
            },
            "pool_name": {
                "type": "string",
                "description": "Capacity pool name. Uses default if not specified.",
            },
        },
        "required": ["volume_name"],
        "additionalProperties": False,
    },
)

delete_snapshot_tool = FunctionTool(
    name="delete_snapshot",
    description=(
        "Delete a snapshot from an Azure NetApp Files volume. "
        "This is a destructive operation — the snapshot cannot be recovered. "
        "Use this when the user explicitly asks to remove or clean up a snapshot."
    ),
    parameters={
        "type": "object",
        "properties": {
            "volume_name": {
                "type": "string",
                "description": "Name of the ANF volume containing the snapshot.",
            },
            "snapshot_name": {
                "type": "string",
                "description": "Name of the snapshot to delete.",
            },
            "pool_name": {
                "type": "string",
                "description": "Capacity pool name. Uses default if not specified.",
            },
        },
        "required": ["volume_name", "snapshot_name"],
        "additionalProperties": False,
    },
)

resize_volume_tool = FunctionTool(
    name="resize_volume",
    description=(
        "Resize an Azure NetApp Files volume. ANF supports online resize — "
        "no downtime or performance impact. Minimum size is 100 GiB. "
        "Use this when the user asks to change volume capacity, grow a volume, "
        "or adjust storage size."
    ),
    parameters={
        "type": "object",
        "properties": {
            "volume_name": {
                "type": "string",
                "description": "Name of the ANF volume to resize.",
            },
            "new_size_gib": {
                "type": "integer",
                "description": (
                    "New volume size in GiB. Must be >= 100. "
                    "For TiB, multiply by 1024 (e.g., 2 TiB = 2048 GiB)."
                ),
            },
            "pool_name": {
                "type": "string",
                "description": "Capacity pool name. Uses default if not specified.",
            },
        },
        "required": ["volume_name", "new_size_gib"],
        "additionalProperties": False,
    },
)

get_account_info_tool = FunctionTool(
    name="get_account_info",
    description=(
        "Get information about the Azure NetApp Files account, including "
        "its location, provisioning state, and Active Directory connections. "
        "Use this when the user asks about the ANF account or wants general info."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
)


# ── Aggregated ToolSet ───────────────────────────────────────────────

ALL_TOOLS = [
    list_volumes_tool,
    get_volume_tool,
    create_snapshot_tool,
    list_snapshots_tool,
    delete_snapshot_tool,
    resize_volume_tool,
    get_account_info_tool,
]


def create_toolset() -> ToolSet:
    """
    Create a ToolSet containing all ANF SelfOps function tools.

    Returns:
        ToolSet configured with all function tool definitions.
    """
    toolset = ToolSet()
    for tool in ALL_TOOLS:
        toolset.add(tool)
    return toolset
