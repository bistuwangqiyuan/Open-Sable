"""
Human-in-the-Loop (HITL) — Approval gates for dangerous agent actions.

Lets the agent pause execution and ask a human operator for confirmation
before running risky operations (file deletion, sending emails, executing
system commands, spending money, etc.).

Usage:
    from opensable.core.hitl import ApprovalGate, HumanApprovalRequired

    gate = ApprovalGate()

    # Register a callback that asks the user (Telegram/Discord/CLI/etc.)
    gate.set_approval_handler(my_ask_user_function)

    # In the tool execution path:
    decision = await gate.request_approval(
        action="delete_file",
        description="Delete /etc/important.conf",
        risk_level=RiskLevel.HIGH,
        context={"path": "/etc/important.conf"},
    )
    if decision.approved:
        do_the_thing()
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional
import uuid as _uuid

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk classification for actions."""
    LOW = "low"          # Informational, read-only
    MEDIUM = "medium"    # Creates/modifies local data
    HIGH = "high"        # Sends messages, deletes files, runs commands
    CRITICAL = "critical"  # System-level, irreversible, financial


class ApprovalStatus(Enum):
    """Approval decision."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"
    AUTO_APPROVED = "auto_approved"


@dataclass
class ApprovalRequest:
    """A pending approval request."""
    request_id: str
    action: str
    description: str
    risk_level: RiskLevel
    context: Dict[str, Any] = field(default_factory=dict)
    user_id: str = "default"
    created_at: datetime = field(default_factory=datetime.now)
    status: ApprovalStatus = ApprovalStatus.PENDING
    decision_by: Optional[str] = None
    decision_at: Optional[datetime] = None
    reason: str = ""


@dataclass
class ApprovalDecision:
    """The human's decision on an approval request."""
    approved: bool
    status: ApprovalStatus
    reason: str = ""
    modified_params: Optional[Dict[str, Any]] = None


class HumanApprovalRequired(Exception):
    """Raised when an action requires human approval and none is configured."""

    def __init__(self, request: ApprovalRequest):
        self.request = request
        super().__init__(f"Human approval required for: {request.action} — {request.description}")


# ── Default risk classification ─────────────────────────────

_DEFAULT_RISK_MAP: Dict[str, RiskLevel] = {
    # HIGH
    "execute_command": RiskLevel.HIGH,
    "delete_file": RiskLevel.HIGH,
    "write_file": RiskLevel.HIGH,
    "edit_file": RiskLevel.HIGH,
    "execute_code": RiskLevel.HIGH,
    "send_email": RiskLevel.HIGH,
    "send_message": RiskLevel.HIGH,
    # MEDIUM
    "browser_action": RiskLevel.MEDIUM,
    "browser_scrape": RiskLevel.MEDIUM,
    "create_skill": RiskLevel.MEDIUM,
    "move_file": RiskLevel.MEDIUM,
    # LOW
    "browser_search": RiskLevel.LOW,
    "read_file": RiskLevel.LOW,
    "list_directory": RiskLevel.LOW,
    "weather": RiskLevel.LOW,
    "calendar": RiskLevel.LOW,
    "system_info": RiskLevel.LOW,
    "vector_search": RiskLevel.LOW,
    # Trading — read operations are LOW, executions are CRITICAL
    "trading_portfolio": RiskLevel.LOW,
    "trading_price": RiskLevel.LOW,
    "trading_analyze": RiskLevel.LOW,
    "trading_signals": RiskLevel.LOW,
    "trading_history": RiskLevel.LOW,
    "trading_risk_status": RiskLevel.LOW,
    "trading_place_trade": RiskLevel.CRITICAL,
    "trading_cancel_order": RiskLevel.HIGH,
    "trading_start_scan": RiskLevel.HIGH,
    "trading_stop_scan": RiskLevel.MEDIUM,
    # Skills Marketplace — search/info are LOW, install needs user approval
    "marketplace_search": RiskLevel.LOW,
    "marketplace_info": RiskLevel.LOW,
    "marketplace_install": RiskLevel.HIGH,       # Requires human approval
    "marketplace_review": RiskLevel.MEDIUM,
    # Mobile phone tools — notifications/reminders are MEDIUM, reads are LOW
    "phone_notify": RiskLevel.MEDIUM,
    "phone_reminder": RiskLevel.MEDIUM,
    "phone_geofence": RiskLevel.MEDIUM,
    "phone_location": RiskLevel.LOW,
    "phone_device": RiskLevel.LOW,
}

# Type alias for the callback that asks a human
ApprovalHandler = Callable[[ApprovalRequest], Awaitable[ApprovalDecision]]


class ApprovalGate:
    """
    Central approval gate that intercepts risky tool calls.

    Modes:
    - auto_approve_below: auto-approve anything below this risk level
    - approval_handler: async callback that presents the request to a human
    - timeout_seconds: how long to wait for a decision before timing out
    """

    def __init__(
        self,
        *,
        auto_approve_below: RiskLevel = RiskLevel.HIGH,
        timeout_seconds: float = 300.0,
        risk_map: Optional[Dict[str, RiskLevel]] = None,
    ):
        self.auto_approve_below = auto_approve_below
        self.timeout_seconds = timeout_seconds
        self.risk_map = {**_DEFAULT_RISK_MAP, **(risk_map or {})}
        self._handler: Optional[ApprovalHandler] = None
        self._history: List[ApprovalRequest] = []

    def set_approval_handler(self, handler: ApprovalHandler) -> None:
        """Set the callback that asks a human for approval."""
        self._handler = handler

    def get_risk_level(self, action: str) -> RiskLevel:
        """Look up the risk level for a given action/tool name."""
        return self.risk_map.get(action, RiskLevel.MEDIUM)

    def _risk_order(self, level: RiskLevel) -> int:
        return {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}[level]

    async def request_approval(
        self,
        action: str,
        description: str,
        *,
        risk_level: Optional[RiskLevel] = None,
        context: Optional[Dict[str, Any]] = None,
        user_id: str = "default",
    ) -> ApprovalDecision:
        """
        Check if an action needs approval.

        Returns ApprovalDecision.approved=True if auto-approved or human approved.
        """
        level = risk_level or self.get_risk_level(action)
        request = ApprovalRequest(
            request_id=str(_uuid.uuid4())[:8],
            action=action,
            description=description,
            risk_level=level,
            context=context or {},
            user_id=user_id,
        )

        # Auto-approve low-risk actions
        if self._risk_order(level) < self._risk_order(self.auto_approve_below):
            request.status = ApprovalStatus.AUTO_APPROVED
            request.decision_at = datetime.now()
            self._history.append(request)
            logger.debug(f"Auto-approved {action} (risk={level.value})")
            return ApprovalDecision(approved=True, status=ApprovalStatus.AUTO_APPROVED)

        # No handler configured → raise
        if not self._handler:
            self._history.append(request)
            raise HumanApprovalRequired(request)

        # Ask human
        logger.info(f"⏳ Requesting human approval for: {action} (risk={level.value})")
        try:
            decision = await asyncio.wait_for(
                self._handler(request),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            request.status = ApprovalStatus.TIMEOUT
            request.decision_at = datetime.now()
            self._history.append(request)
            logger.warning(f"Approval request timed out for: {action}")
            return ApprovalDecision(
                approved=False,
                status=ApprovalStatus.TIMEOUT,
                reason="Approval timed out",
            )

        request.status = decision.status
        request.decision_at = datetime.now()
        request.reason = decision.reason
        self._history.append(request)

        if decision.approved:
            logger.info(f"✅ Approved: {action}")
        else:
            logger.info(f"❌ Denied: {action} — {decision.reason}")

        return decision

    @property
    def history(self) -> List[ApprovalRequest]:
        """Return the audit trail of all approval requests."""
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()
