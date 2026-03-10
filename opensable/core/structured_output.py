"""
Structured Output,  Force LLM responses into typed Pydantic models.

Guarantees that agent output conforms to a user-defined schema, enabling
reliable downstream processing (JSON APIs, database inserts, UI rendering).

Usage:
    from pydantic import BaseModel
    from opensable.core.structured_output import StructuredOutputParser

    class FlightResult(BaseModel):
        airline: str
        price: float
        departure: str

    parser = StructuredOutputParser(FlightResult)

    # Inject schema instruction into prompt
    system_prompt = parser.get_format_instructions()

    # Parse LLM text into model
    result: FlightResult = await parser.parse(llm_text)
"""

from __future__ import annotations

import json as _json
import logging
import re
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ParseError(Exception):
    """Raised when LLM output cannot be parsed into the target schema."""

    def __init__(self, message: str, raw_output: str, errors: Optional[List[Dict]] = None):
        super().__init__(message)
        self.raw_output = raw_output
        self.errors = errors or []


class StructuredOutputParser(Generic[T]):
    """
    Parses free-form LLM text into a typed Pydantic model.

    Strategy:
    1. Try direct JSON parse
    2. Extract JSON from markdown code fences
    3. Regex-extract JSON objects
    4. Raise ParseError (caller can retry)
    """

    def __init__(self, schema: Type[T], *, strict: bool = True):
        self.schema = schema
        self.strict = strict

    # ── Format instructions (inject into system prompt) ───────

    def get_format_instructions(self) -> str:
        """Return a string telling the LLM how to format its response."""
        schema_json = _json.dumps(self.schema.model_json_schema(), indent=2)
        return (
            "You MUST respond with a valid JSON object that conforms to the "
            "following schema.  Do NOT include any text outside the JSON.\n\n"
            f"```json\n{schema_json}\n```"
        )

    def get_system_prompt_addon(self) -> str:
        """Shorter version suitable for appending to an existing system prompt."""
        fields = []
        for name, info in self.schema.model_fields.items():
            annotation = info.annotation.__name__ if hasattr(info.annotation, "__name__") else str(info.annotation)
            desc = info.description or ""
            fields.append(f'  "{name}": {annotation}  // {desc}' if desc else f'  "{name}": {annotation}')
        body = ",\n".join(fields)
        return (
            "\n\nRespond with ONLY a JSON object in this format:\n"
            "```json\n{\n" + body + "\n}\n```"
        )

    # ── Parsing ───────────────────────────────────────────────

    def parse(self, text: str) -> T:
        """Parse LLM output text into the target Pydantic model."""
        return self._parse_sync(text)

    def _parse_sync(self, text: str) -> T:
        text = text.strip()

        # Strategy 1: direct JSON
        obj = self._try_json(text)
        if obj is not None:
            return self._validate(obj, text)

        # Strategy 2: extract from code fences
        fenced = re.findall(r"```(?:json)?\s*\n?([\s\S]*?)```", text)
        for block in fenced:
            obj = self._try_json(block.strip())
            if obj is not None:
                return self._validate(obj, text)

        # Strategy 3: regex for JSON objects
        for match in re.finditer(r"\{[\s\S]*\}", text):
            obj = self._try_json(match.group())
            if obj is not None:
                return self._validate(obj, text)

        raise ParseError(
            f"Could not extract JSON from LLM output for {self.schema.__name__}",
            raw_output=text,
        )

    def _try_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            data = _json.loads(text)
            if isinstance(data, dict):
                return data
        except _json.JSONDecodeError:
            pass
        return None

    def _validate(self, data: Dict[str, Any], raw: str) -> T:
        try:
            return self.schema.model_validate(data, strict=self.strict)
        except ValidationError as exc:
            if not self.strict:
                # Lenient mode: try with coercion
                try:
                    return self.schema.model_validate(data, strict=False)
                except ValidationError:
                    pass
            raise ParseError(
                f"JSON found but doesn't match {self.schema.__name__}: {exc}",
                raw_output=raw,
                errors=exc.errors(),
            ) from exc

    # ── List parsing ──────────────────────────────────────────

    def parse_list(self, text: str) -> List[T]:
        """Parse a JSON array of objects into a list of models."""
        text = text.strip()

        # Try direct
        try:
            data = _json.loads(text)
            if isinstance(data, list):
                return [self.schema.model_validate(item) for item in data]
        except Exception:
            pass

        # Try from code fences
        fenced = re.findall(r"```(?:json)?\s*\n?([\s\S]*?)```", text)
        for block in fenced:
            try:
                data = _json.loads(block.strip())
                if isinstance(data, list):
                    return [self.schema.model_validate(item) for item in data]
            except Exception:
                continue

        raise ParseError(
            f"Could not parse list of {self.schema.__name__} from output",
            raw_output=text,
        )
