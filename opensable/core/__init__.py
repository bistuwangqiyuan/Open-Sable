"""Core package for Open-Sable — all public symbols."""

from .agent import SableAgent
from .config import load_config, OpenSableConfig

# SDK essentials
from .function_tool import FunctionTool, function_tool, collect_schemas, build_tool_executor
from .runner import Agent, Runner, RunResult, StreamEvent
from .mcp import MCPClient, MCPTool, MCPResource, connect_mcp_tools

# Production primitives
from .guardrails import (
    GuardrailsEngine,
    GuardrailAction,
    GuardrailResult,
    InputGuardrail,
    OutputGuardrail,
    PromptInjectionGuardrail,
    ContentPolicyGuardrail,
    MaxLengthGuardrail,
    OutputSchemaGuardrail,
    HallucinationGuardrail,
    PIIRedactionGuardrail,
    ValidationResult,
)
from .structured_output import StructuredOutputParser, ParseError
from .hitl import (
    ApprovalGate,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    RiskLevel,
    HumanApprovalRequired,
)
from .checkpointing import Checkpoint, CheckpointStore, StepRecord
from .handoffs import (
    Handoff,
    HandoffRouter,
    HandoffResult,
    HandoffStatus,
    default_handoffs,
)
from .flows import Flow, FlowBuilder, FlowEvent, StepResult, start, listen, router

__all__ = [
    # Agent
    "SableAgent",
    "load_config",
    "OpenSableConfig",
    # SDK essentials
    "Agent",
    "Runner",
    "RunResult",
    "StreamEvent",
    "FunctionTool",
    "function_tool",
    "collect_schemas",
    "build_tool_executor",
    # MCP
    "MCPClient",
    "MCPTool",
    "MCPResource",
    "connect_mcp_tools",
    # Guardrails
    "GuardrailsEngine",
    "GuardrailAction",
    "GuardrailResult",
    "InputGuardrail",
    "OutputGuardrail",
    "PromptInjectionGuardrail",
    "ContentPolicyGuardrail",
    "MaxLengthGuardrail",
    "OutputSchemaGuardrail",
    "HallucinationGuardrail",
    "PIIRedactionGuardrail",
    "ValidationResult",
    # Structured output
    "StructuredOutputParser",
    "ParseError",
    # HITL
    "ApprovalGate",
    "ApprovalDecision",
    "ApprovalRequest",
    "ApprovalStatus",
    "RiskLevel",
    "HumanApprovalRequired",
    # Checkpointing
    "Checkpoint",
    "CheckpointStore",
    "StepRecord",
    # Handoffs
    "Handoff",
    "HandoffRouter",
    "HandoffResult",
    "HandoffStatus",
    "default_handoffs",
    # Flows
    "Flow",
    "FlowBuilder",
    "FlowEvent",
    "StepResult",
    "start",
    "listen",
    "router",
]
