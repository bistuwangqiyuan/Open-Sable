"""
@function_tool — Auto-generate OpenAI-format tool schemas from Python functions.

Inspects type hints, docstrings, and default values to produce the JSON schema
that LLMs need for function/tool calling.  No more hand-writing 20-line dicts.

Usage:
    from opensable.core.function_tool import function_tool

    @function_tool
    async def get_weather(city: str, units: str = "celsius") -> str:
        '''Get the current weather for a city.

        Args:
            city: Name of the city (e.g. "Tokyo")
            units: Temperature units — "celsius" or "fahrenheit"
        '''
        return f"Weather in {city}: 22°{units[0].upper()}"

    # The decorator exposes:
    schema = get_weather.schema   # OpenAI function calling JSON
    result = await get_weather("Tokyo")

    # Or register many at once on an agent:
    agent = SableAgent(config, tools=[get_weather, search_web, run_code])
"""

from __future__ import annotations

import inspect
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, get_type_hints

logger = logging.getLogger(__name__)

# Python type → JSON Schema type mapping
_TYPE_MAP: Dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}


def _python_type_to_json(annotation: Any) -> Dict[str, Any]:
    """Convert a Python type annotation to a JSON Schema fragment."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {"type": "string"}

    # Handle Optional[X] → {"type": "X"} (we mark it optional via required)
    origin = getattr(annotation, "__origin__", None)
    if origin is list or origin is List:
        args = getattr(annotation, "__args__", (Any,))
        item_type = _python_type_to_json(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item_type}
    if origin is dict or origin is Dict:
        return {"type": "object"}

    # Direct type
    json_type = _TYPE_MAP.get(annotation, "string")
    return {"type": json_type}


def _parse_docstring_args(docstring: str) -> Dict[str, str]:
    """
    Parse Google-style or numpy-style docstring to extract per-parameter descriptions.

    Supports:
        Args:
            city: Name of the city
            units: Temperature units
    """
    descriptions: Dict[str, str] = {}
    if not docstring:
        return descriptions

    # Google-style: "    param_name: description"
    in_args = False
    for line in docstring.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith(("args:", "arguments:", "parameters:", "params:")):
            in_args = True
            continue
        if in_args:
            if not stripped or stripped.lower().startswith(("returns:", "raises:", "yields:", "example", "note")):
                in_args = False
                continue
            # Match "param_name: description" or "param_name (type): description"
            m = re.match(r"(\w+)\s*(?:\([^)]*\))?\s*:\s*(.+)", stripped)
            if m:
                descriptions[m.group(1)] = m.group(2).strip()

    return descriptions


def _build_schema(fn: Callable) -> Dict[str, Any]:
    """Build an OpenAI function-calling schema from a Python function."""
    sig = inspect.signature(fn)
    hints = get_type_hints(fn) if hasattr(fn, "__annotations__") else {}
    docstring = inspect.getdoc(fn) or ""
    param_docs = _parse_docstring_args(docstring)

    # Function-level description = first line of docstring
    description = docstring.split("\n")[0].strip() if docstring else fn.__name__.replace("_", " ").title()

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue

        prop = _python_type_to_json(hints.get(name, param.annotation))
        if name in param_docs:
            prop["description"] = param_docs[name]

        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            required.append(name)

        properties[name] = prop

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


class FunctionTool:
    """
    Wraps a Python function with its auto-generated OpenAI tool schema.

    Calling the wrapper delegates to the original function.
    """

    def __init__(self, fn: Callable, *, name: str | None = None, description: str | None = None):
        self._fn = fn
        self._schema = _build_schema(fn)

        # Allow overrides
        if name:
            self._schema["function"]["name"] = name
        if description:
            self._schema["function"]["description"] = description

        # Copy function metadata
        self.__name__ = self._schema["function"]["name"]
        self.__doc__ = fn.__doc__
        self.__wrapped__ = fn

    @property
    def schema(self) -> Dict[str, Any]:
        """Return the OpenAI function-calling JSON schema."""
        return self._schema

    @property
    def name(self) -> str:
        return self._schema["function"]["name"]

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the underlying function (supports both sync and async)."""
        result = self._fn(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def execute(self, arguments: Dict[str, Any]) -> str:
        """Execute with a dict of arguments (as the LLM would provide)."""
        try:
            result = await self(**arguments)
            return str(result)
        except Exception as e:
            return f"❌ {self.name} failed: {e}"

    def __repr__(self) -> str:
        params = list(self._schema["function"]["parameters"]["properties"].keys())
        return f"<FunctionTool {self.name}({', '.join(params)})>"


def function_tool(
    fn: Callable | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> FunctionTool | Callable[[Callable], FunctionTool]:
    """
    Decorator that turns a Python function into a tool with auto-generated schema.

    Can be used with or without arguments:

        @function_tool
        async def search(query: str) -> str: ...

        @function_tool(name="web_search", description="Search the internet")
        async def search(query: str) -> str: ...
    """
    if fn is not None:
        # @function_tool  (no parentheses)
        return FunctionTool(fn)

    # @function_tool(name=..., description=...)
    def decorator(f: Callable) -> FunctionTool:
        return FunctionTool(f, name=name, description=description)
    return decorator


def collect_schemas(tools: List[FunctionTool]) -> List[Dict[str, Any]]:
    """Collect OpenAI-format schemas from a list of FunctionTool instances."""
    return [t.schema for t in tools]


def build_tool_executor(tools: List[FunctionTool]) -> Dict[str, FunctionTool]:
    """Build a name→tool map for quick dispatch."""
    return {t.name: t for t in tools}
