"""
Ethical Reasoning Framework — consequence analysis + guardrails.

Evaluates the ethical implications and potential consequences of
autonomous actions BEFORE executing them, providing a safety layer
that goes beyond simple permission checks.

Key ideas:
  - **Consequence analysis**: estimates impact and reversibility of actions
  - **Stakeholder impact**: considers who is affected by an action
  - **Guardrail rules**: hard rules that cannot be overridden
  - **Risk scoring**: combined ethical risk score for each action
  - **Audit trail**: records all ethical evaluations for transparency

Persistence: ``ethical_reasoner_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Hard guardrail rules that cannot be overridden
_GUARDRAILS = [
    {"id": "no_harm", "rule": "Never take actions that could physically harm a person", "severity": 1.0},
    {"id": "no_deception", "rule": "Never impersonate a real person or create deceptive content presented as real", "severity": 0.9},
    {"id": "privacy", "rule": "Never expose private user data to unauthorized parties", "severity": 0.9},
    {"id": "consent", "rule": "Never access services or data without proper authorization", "severity": 0.8},
    {"id": "reversibility", "rule": "Prefer reversible actions over irreversible ones", "severity": 0.6},
    {"id": "proportionality", "rule": "Actions should be proportional to the goal — don't use a sledgehammer for a nail", "severity": 0.5},
    {"id": "transparency", "rule": "Always be transparent about being an AI when directly asked", "severity": 0.8},
    {"id": "resource_respect", "rule": "Don't consume excessive resources (rate limits, storage, bandwidth) without justification", "severity": 0.4},
]


@dataclass
class EthicalEvaluation:
    """Result of evaluating an action's ethical implications."""

    eval_id: str
    action_description: str
    risk_score: float  # 0-1 (0=safe, 1=dangerous)
    verdict: str  # approved, caution, blocked
    reasons: List[str]
    guardrails_triggered: List[str]
    stakeholders_affected: List[str]
    reversible: bool
    tick: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class EthicalReasoner:
    """Evaluates ethical implications of autonomous actions."""

    def __init__(
        self,
        data_dir: Path,
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._data_dir / "ethical_reasoner_state.json"

        self._evaluations: List[EthicalEvaluation] = []
        self._total_approved: int = 0
        self._total_cautioned: int = 0
        self._total_blocked: int = 0
        self._custom_rules: List[Dict[str, Any]] = []

        self._load_state()

    # ── Evaluate ──────────────────────────────────────────────────────────────

    def evaluate(
        self,
        action: str,
        tick: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> EthicalEvaluation:
        """Evaluate the ethical implications of a proposed action.

        Returns an EthicalEvaluation with verdict: approved, caution, or blocked.
        """
        import hashlib
        eval_id = f"eval_{hashlib.md5(f'{action}_{tick}'.encode()).hexdigest()[:8]}"

        risk_score = 0.0
        reasons = []
        triggered = []
        stakeholders = []
        reversible = True

        action_lower = action.lower()

        # ── Check hard guardrails ─────────────────────────────────────────
        for guardrail in _GUARDRAILS:
            triggered_this = False

            # Check based on guardrail ID
            if guardrail["id"] == "no_harm":
                harm_words = {"delete all", "destroy", "kill", "rm -rf /", "format disk", "drop database"}
                if any(w in action_lower for w in harm_words):
                    triggered_this = True
                    reasons.append(f"Potentially harmful: matches '{guardrail['rule']}'")

            elif guardrail["id"] == "no_deception":
                deception_words = {"impersonate", "pretend to be", "fake identity", "phishing"}
                if any(w in action_lower for w in deception_words):
                    triggered_this = True
                    reasons.append("Potential deception detected")

            elif guardrail["id"] == "privacy":
                privacy_words = {"leak password", "expose credentials", "share private", "dump user data"}
                if any(w in action_lower for w in privacy_words):
                    triggered_this = True
                    reasons.append("Privacy violation risk")
                    stakeholders.append("users")

            elif guardrail["id"] == "consent":
                consent_words = {"without permission", "unauthorized", "hack", "brute force", "bypass auth"}
                if any(w in action_lower for w in consent_words):
                    triggered_this = True
                    reasons.append("Consent/authorization concern")

            elif guardrail["id"] == "reversibility":
                irreversible = {"delete permanently", "drop table", "purge", "wipe", "overwrite"}
                if any(w in action_lower for w in irreversible):
                    reversible = False
                    risk_score += 0.15
                    reasons.append("Action may be irreversible")

            elif guardrail["id"] == "resource_respect":
                resource_words = {"spam", "flood", "mass email", "bulk send", "ddos"}
                if any(w in action_lower for w in resource_words):
                    triggered_this = True
                    reasons.append("Excessive resource consumption")

            if triggered_this:
                triggered.append(guardrail["id"])
                risk_score += guardrail["severity"] * 0.5

        # ── Check custom rules ────────────────────────────────────────────
        for rule in self._custom_rules:
            keywords = rule.get("keywords", [])
            if any(kw.lower() in action_lower for kw in keywords):
                triggered.append(rule.get("id", "custom"))
                risk_score += rule.get("severity", 0.3) * 0.5
                reasons.append(rule.get("reason", "Custom rule triggered"))

        # ── Context-based assessment ──────────────────────────────────────
        if context:
            # Financial actions get extra scrutiny
            if context.get("involves_money"):
                risk_score += 0.2
                reasons.append("Financial action — extra scrutiny applied")
                stakeholders.append("user_finances")

            # Actions affecting other users
            if context.get("affects_others"):
                risk_score += 0.1
                stakeholders.extend(context.get("affected_parties", ["others"]))

            # Public-facing actions
            if context.get("public"):
                risk_score += 0.1
                reasons.append("Public-facing action")

        # ── Determine verdict ─────────────────────────────────────────────
        risk_score = min(1.0, risk_score)

        if risk_score >= 0.7 or any(
            g in triggered for g in ["no_harm", "no_deception", "privacy"]
        ):
            verdict = "blocked"
            self._total_blocked += 1
        elif risk_score >= 0.3 or triggered:
            verdict = "caution"
            self._total_cautioned += 1
        else:
            verdict = "approved"
            self._total_approved += 1

        if not reasons:
            reasons.append("No ethical concerns identified")

        evaluation = EthicalEvaluation(
            eval_id=eval_id,
            action_description=action[:300],
            risk_score=round(risk_score, 3),
            verdict=verdict,
            reasons=reasons,
            guardrails_triggered=triggered,
            stakeholders_affected=list(set(stakeholders)),
            reversible=reversible,
            tick=tick,
        )

        self._evaluations.append(evaluation)
        if len(self._evaluations) > 500:
            self._evaluations = self._evaluations[-500:]

        self._save_state()

        if verdict == "blocked":
            logger.warning(f"🛡️ Ethical block: {action[:80]} (risk={risk_score:.2f})")
        elif verdict == "caution":
            logger.info(f"⚠️ Ethical caution: {action[:80]} (risk={risk_score:.2f})")

        return evaluation

    # ── Custom rules ──────────────────────────────────────────────────────────

    def add_rule(self, rule_id: str, keywords: List[str], severity: float, reason: str):
        """Add a custom ethical guardrail rule."""
        self._custom_rules.append({
            "id": rule_id,
            "keywords": keywords,
            "severity": max(0, min(1, severity)),
            "reason": reason,
        })
        self._save_state()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        total = self._total_approved + self._total_cautioned + self._total_blocked

        # Most triggered guardrails
        guardrail_counts: Dict[str, int] = {}
        for ev in self._evaluations:
            for g in ev.guardrails_triggered:
                guardrail_counts[g] = guardrail_counts.get(g, 0) + 1

        return {
            "total_evaluations": total,
            "approved": self._total_approved,
            "cautioned": self._total_cautioned,
            "blocked": self._total_blocked,
            "approval_rate": round(self._total_approved / max(total, 1), 3),
            "custom_rules": len(self._custom_rules),
            "guardrail_triggers": guardrail_counts,
            "recent_evaluations": [
                {
                    "action": ev.action_description[:80],
                    "verdict": ev.verdict,
                    "risk": ev.risk_score,
                    "guardrails": ev.guardrails_triggered,
                }
                for ev in self._evaluations[-8:]
            ],
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "evaluations": [asdict(e) for e in self._evaluations[-500:]],
                "custom_rules": self._custom_rules,
                "total_approved": self._total_approved,
                "total_cautioned": self._total_cautioned,
                "total_blocked": self._total_blocked,
            }
            self._state_file.write_text(json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Ethical reasoner save failed: {e}")

    def _load_state(self):
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._total_approved = data.get("total_approved", 0)
                self._total_cautioned = data.get("total_cautioned", 0)
                self._total_blocked = data.get("total_blocked", 0)
                self._custom_rules = data.get("custom_rules", [])

                for edata in data.get("evaluations", []):
                    self._evaluations.append(EthicalEvaluation(**edata))
        except Exception as e:
            logger.debug(f"Ethical reasoner load failed: {e}")
