"""
Guardrails — Input/Output validation for safe, reliable agent execution.

Validates user inputs BEFORE the LLM sees them and validates LLM outputs
BEFORE returning them.  Blocks prompt injection, enforces output schemas,
content policies, and custom rules.

Usage:
    from opensable.core.guardrails import GuardrailsEngine, InputGuardrail, OutputGuardrail

    engine = GuardrailsEngine()
    engine.add_input(ContentPolicyGuardrail())
    engine.add_input(PromptInjectionGuardrail())
    engine.add_output(OutputSchemaGuardrail(schema=MyModel))

    # In the agent loop:
    result = await engine.validate_input(user_message)
    if not result.passed:
        return result.rejection_message

    llm_response = await llm.invoke(...)

    result = await engine.validate_output(llm_response)
    if not result.passed:
        # retry or return fallback
"""

from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


# ── Result types ──────────────────────────────────────────────

class GuardrailAction(Enum):
    """What to do when a guardrail trips."""
    BLOCK = "block"          # Reject entirely
    WARN = "warn"            # Log warning, allow through
    SANITIZE = "sanitize"    # Modify content and continue
    RETRY = "retry"          # Ask the LLM to regenerate


@dataclass
class GuardrailResult:
    """Result of a single guardrail check."""
    passed: bool
    guardrail_name: str
    action: GuardrailAction = GuardrailAction.BLOCK
    rejection_message: str = ""
    sanitized_content: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def triggered(self) -> bool:
        """True when the guardrail fired (i.e. the check did NOT pass cleanly)."""
        return not self.passed or self.action in (GuardrailAction.SANITIZE, GuardrailAction.WARN)

    @property
    def message(self) -> str:
        return self.rejection_message

    @property
    def sanitized(self) -> Optional[str]:
        return self.sanitized_content


@dataclass
class ValidationResult:
    """Aggregated result of all guardrail checks on a piece of content."""
    passed: bool
    results: List[GuardrailResult] = field(default_factory=list)
    sanitized_content: Optional[str] = None
    rejection_message: str = ""

    @property
    def failed_guardrails(self) -> List[str]:
        return [r.guardrail_name for r in self.results if not r.passed]


# ── Abstract base classes ─────────────────────────────────────

class InputGuardrail(ABC):
    """Validates user input before the LLM sees it."""

    name: str = "input_guardrail"

    @abstractmethod
    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        ...


class OutputGuardrail(ABC):
    """Validates LLM output before returning to the user."""

    name: str = "output_guardrail"

    @abstractmethod
    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        ...


# ── Built-in input guardrails ────────────────────────────────

class PromptInjectionGuardrail(InputGuardrail):
    """Detects common prompt injection patterns."""

    name = "prompt_injection"

    _INJECTION_PATTERNS = [
        r"ignore (?:all )?(?:previous|above|prior) (?:instructions|prompts|rules)",
        r"you are now (?:a |an )?(?:different|new|evil)",
        r"disregard (?:everything|all|your)",
        r"forget (?:everything|all|your)",
        r"system\s*prompt\s*:",
        r"<\|(?:im_start|im_end|system)\|>",
        r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>",
        r"pretend (?:you are|to be|you're)",
        r"act as (?:if )?(?:you are|you're|a|an)",
        r"jailbreak|DAN\s*mode|developer\s*mode",
        r"do anything now|bypass (?:filter|safety|restriction)",
    ]

    def __init__(self, custom_patterns: Optional[List[str]] = None):
        self._compiled = [
            re.compile(p, re.IGNORECASE) for p in self._INJECTION_PATTERNS
        ]
        if custom_patterns:
            self._compiled.extend(re.compile(p, re.IGNORECASE) for p in custom_patterns)

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        for pattern in self._compiled:
            match = pattern.search(content)
            if match:
                logger.warning(f"Prompt injection detected: {match.group()!r}")
                return GuardrailResult(
                    passed=False,
                    guardrail_name=self.name,
                    action=GuardrailAction.BLOCK,
                    rejection_message="I can't process that request — it looks like a prompt injection attempt.",
                    details={"matched_pattern": match.group()},
                )
        return GuardrailResult(passed=True, guardrail_name=self.name)


class ContentPolicyGuardrail(InputGuardrail):
    """Blocks requests for harmful, illegal, or dangerous content."""

    name = "content_policy"

    _BLOCKED_CATEGORIES = [
        (r"\b(?:how to (?:make|build|create) (?:a )?(?:bomb|explosive|weapon))\b", "weapons"),
        (r"\b(?:how to (?:hack|break into|exploit))\b", "hacking"),
        (r"\b(?:child\s*(?:porn|abuse|exploitation))\b", "csam"),
        (r"\b(?:synthesize|manufacture|cook)\s+(?:meth|cocaine|fentanyl|heroin)\b", "drugs"),
    ]

    def __init__(self, extra_rules: Optional[List[tuple]] = None):
        self._rules = [
            (re.compile(p, re.IGNORECASE), cat) for p, cat in self._BLOCKED_CATEGORIES
        ]
        if extra_rules:
            self._rules.extend(
                (re.compile(p, re.IGNORECASE), cat) for p, cat in extra_rules
            )

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        for pattern, category in self._rules:
            if pattern.search(content):
                logger.warning(f"Content policy violation: category={category}")
                return GuardrailResult(
                    passed=False,
                    guardrail_name=self.name,
                    action=GuardrailAction.BLOCK,
                    rejection_message="Sorry, I can't assist with that.",
                    details={"category": category},
                )
        return GuardrailResult(passed=True, guardrail_name=self.name)


class MaxLengthGuardrail(InputGuardrail):
    """Rejects inputs that exceed a token/character limit."""

    name = "max_length"

    def __init__(self, max_chars: int = 32_000):
        self.max_chars = max_chars

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        if len(content) > self.max_chars:
            return GuardrailResult(
                passed=False,
                guardrail_name=self.name,
                action=GuardrailAction.SANITIZE,
                rejection_message=f"Input too long ({len(content):,} chars). Maximum is {self.max_chars:,}.",
                sanitized_content=content[: self.max_chars],
                details={"length": len(content), "max": self.max_chars},
            )
        return GuardrailResult(passed=True, guardrail_name=self.name)


# ── Built-in output guardrails ───────────────────────────────

class OutputSchemaGuardrail(OutputGuardrail):
    """Validates that LLM output conforms to a Pydantic model (structured output)."""

    name = "output_schema"

    def __init__(self, schema: Type):
        self.schema = schema

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        import json as _json

        try:
            data = _json.loads(content)
            self.schema(**data)
            return GuardrailResult(passed=True, guardrail_name=self.name)
        except (_json.JSONDecodeError, Exception) as exc:
            return GuardrailResult(
                passed=False,
                guardrail_name=self.name,
                action=GuardrailAction.RETRY,
                rejection_message=f"Output doesn't match required schema: {exc}",
                details={"error": str(exc)},
            )


class HallucinationGuardrail(OutputGuardrail):
    """Flags outputs that claim to have real-time data without tool results."""

    name = "hallucination"

    _LIVE_DATA_CLAIMS = re.compile(
        r"\b(?:currently|right now|as of today|at the moment|live|real-time)\b.*?"
        r"\b(?:\d+[\.\,]?\d*\s*(?:USD|EUR|%|degrees|°))\b",
        re.IGNORECASE,
    )

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        ctx = context or {}
        has_tool_results = ctx.get("has_tool_results", False)

        if not has_tool_results and self._LIVE_DATA_CLAIMS.search(content):
            return GuardrailResult(
                passed=False,
                guardrail_name=self.name,
                action=GuardrailAction.WARN,
                rejection_message="",
                details={"reason": "live data claim without tool results"},
            )
        return GuardrailResult(passed=True, guardrail_name=self.name)


class PIIRedactionGuardrail(OutputGuardrail):
    """Redacts PII from LLM output (emails, phone numbers, SSN, credit cards)."""

    name = "pii_redaction"

    _PII_PATTERNS = [
        (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN REDACTED]"),
        (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "[CARD REDACTED]"),
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL REDACTED]"),
    ]

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        sanitized = content
        found = []
        for pattern, replacement in self._PII_PATTERNS:
            if pattern.search(sanitized):
                found.append(replacement)
                sanitized = pattern.sub(replacement, sanitized)

        if found:
            return GuardrailResult(
                passed=True,  # allow but sanitize
                guardrail_name=self.name,
                action=GuardrailAction.SANITIZE,
                sanitized_content=sanitized,
                details={"redacted_types": found},
            )
        return GuardrailResult(passed=True, guardrail_name=self.name)


# ── Engine ────────────────────────────────────────────────────

class GuardrailsEngine:
    """
    Central engine that runs all registered guardrails on inputs/outputs.

    Usage:
        engine = GuardrailsEngine()
        engine.add_input(PromptInjectionGuardrail())
        engine.add_output(PIIRedactionGuardrail())

        result = await engine.validate_input(user_text)
        result = await engine.validate_output(llm_text, context={...})
    """

    def __init__(self):
        self._input_guardrails: List[InputGuardrail] = []
        self._output_guardrails: List[OutputGuardrail] = []

    # -- Registration ---

    def add_input(self, guardrail: InputGuardrail) -> "GuardrailsEngine":
        self._input_guardrails.append(guardrail)
        return self

    def add_output(self, guardrail: OutputGuardrail) -> "GuardrailsEngine":
        self._output_guardrails.append(guardrail)
        return self

    # -- Validation ---

    def validate_input(
        self, content: str, context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Run all input guardrails.  Returns as soon as one BLOCKs."""
        results: List[GuardrailResult] = []
        sanitized = content

        for guardrail in self._input_guardrails:
            try:
                result = guardrail.check(sanitized, context)
            except Exception as exc:
                logger.error(f"Input guardrail {guardrail.name} crashed: {exc}")
                result = GuardrailResult(passed=True, guardrail_name=guardrail.name)

            results.append(result)

            if not result.passed and result.action == GuardrailAction.BLOCK:
                return ValidationResult(
                    passed=False,
                    results=results,
                    rejection_message=result.rejection_message,
                )

            if result.sanitized_content:
                sanitized = result.sanitized_content

        return ValidationResult(passed=True, results=results, sanitized_content=sanitized)

    def validate_output(
        self, content: str, context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Run all output guardrails."""
        results: List[GuardrailResult] = []
        sanitized = content
        needs_retry = False

        for guardrail in self._output_guardrails:
            try:
                result = guardrail.check(sanitized, context)
            except Exception as exc:
                logger.error(f"Output guardrail {guardrail.name} crashed: {exc}")
                result = GuardrailResult(passed=True, guardrail_name=guardrail.name)

            results.append(result)

            if not result.passed:
                if result.action == GuardrailAction.BLOCK:
                    return ValidationResult(
                        passed=False,
                        results=results,
                        rejection_message=result.rejection_message,
                    )
                if result.action == GuardrailAction.RETRY:
                    needs_retry = True

            if result.sanitized_content:
                sanitized = result.sanitized_content

        if needs_retry:
            return ValidationResult(
                passed=False,
                results=results,
                rejection_message="Output validation failed — retrying.",
                sanitized_content=sanitized,
            )

        return ValidationResult(passed=True, results=results, sanitized_content=sanitized)

    # -- Factory: sensible defaults ---

    @classmethod
    def default(cls) -> "GuardrailsEngine":
        """Create an engine with sensible default guardrails."""
        engine = cls()
        engine.add_input(PromptInjectionGuardrail())
        engine.add_input(ContentPolicyGuardrail())
        engine.add_input(MaxLengthGuardrail())
        engine.add_output(HallucinationGuardrail())
        engine.add_output(PIIRedactionGuardrail())
        return engine
