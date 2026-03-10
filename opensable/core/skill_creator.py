"""
Dynamic Skill Creation System,  Enhanced with Auto-Wiring

Allows Sable to create its own skills on-the-fly by generating Python code.
Created skills are automatically wired into the live tool registry with:
  - OpenAI-format tool schemas  (LLM can immediately call the new tools)
  - Dispatch routing            (schema name → handler function)
  - RBAC permissions            (role-based access control per tool)
  - Startup re-loading          (skills persist across restarts)

─── Dynamic Skill Protocol ───────────────────────────────────────────────

A skill module **may** define any combination of:

  TOOL_SCHEMAS       list[dict]  ,  OpenAI function-calling schema dicts
  TOOL_PERMISSIONS   dict        ,  tool_name → permission string
  handle_<name>()    async func  ,  handler for each tool (params dict → str)
  initialize()       async func  ,  one-time setup (DB tables, etc.)

If TOOL_SCHEMAS is omitted, minimal schemas are auto-generated from the
handler functions' docstrings.  If TOOL_PERMISSIONS is omitted, all tools
default to the 'dynamic_skill' permission.

Persistent storage is available via the module-level variable
``__skill_data_dir__`` which is injected before the module executes.
"""

import asyncio
import logging
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json
import ast
import re

from opensable.core.paths import opensable_home

logger = logging.getLogger(__name__)

# ── Security ──────────────────────────────────────────────────────────────

# Patterns that are always forbidden in dynamic skill code
FORBIDDEN_PATTERNS = [
    r"os\.system\s*\(",
    r"subprocess\.(?:run|call|Popen|check_output|check_call)\s*\([^)]*shell\s*=\s*True",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"__import__\s*\(",
    r"open\s*\(\s*['\"]\/etc\/",
    r"open\s*\(\s*['\"]\/root\/",
    r"shutil\.rmtree\s*\(\s*['\"]\/",
    r"os\.remove\s*\(\s*['\"]\/",
]


class SkillCreator:
    """
    Creates and manages dynamically generated skills with full tool-registry
    auto-wiring.
    """

    def __init__(self, config):
        self.config = config
        self.skills_dir = opensable_home() / "dynamic_skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        # Per-skill persistent data lives under dynamic_skills/data/<name>/
        self.data_dir = self.skills_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Registry tracks every created skill and its tool names
        self.registry_file = self.skills_dir / "registry.json"
        self.registry: Dict[str, Dict] = self._load_registry()

        # Loaded module references (for runtime access)
        self._loaded_modules: Dict[str, Any] = {}

    # ── Registry persistence ──────────────────────────────────────────────

    def _load_registry(self) -> Dict[str, Dict]:
        if not self.registry_file.exists():
            return {}
        try:
            return json.loads(self.registry_file.read_text())
        except Exception:
            return {}

    def _save_registry(self):
        self.registry_file.write_text(
            json.dumps(self.registry, indent=2, default=str)
        )

    # ── Module loading ────────────────────────────────────────────────────

    def _load_module(self, name: str, skill_file: Path):
        """Load a Python module from a .py file and inject helpers."""
        module_name = f"dynamic_skill_{name}"

        # Remove previous version if it was loaded before (hot-reload)
        if module_name in sys.modules:
            del sys.modules[module_name]

        spec = importlib.util.spec_from_file_location(module_name, skill_file)
        if not spec or not spec.loader:
            raise RuntimeError(f"Cannot create module spec for {skill_file}")

        module = importlib.util.module_from_spec(spec)

        # Inject a persistent data directory the module code can use
        skill_data = str(self.data_dir / name)
        Path(skill_data).mkdir(parents=True, exist_ok=True)
        module.__skill_data_dir__ = skill_data

        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    # ── Tool-info extraction ──────────────────────────────────────────────

    def _extract_tool_info(self, module, skill_name: str) -> Dict[str, Any]:
        """
        Inspect a loaded skill module and return everything needed to wire
        its tools into the live ToolRegistry.

        Returns dict with keys:
            schemas        – list of OpenAI tool schema dicts
            permissions    – dict  tool_name → permission string
            handlers       – dict  tool_name → callable
            handler_names  – list  of tool name strings
            has_initialize – bool
        """
        schemas: List[Dict] = list(getattr(module, "TOOL_SCHEMAS", []))
        permissions: Dict[str, str] = dict(getattr(module, "TOOL_PERMISSIONS", {}))
        has_initialize = hasattr(module, "initialize") and callable(module.initialize)

        # Discover handle_<tool_name> functions
        handlers: Dict[str, Any] = {}
        for attr_name in dir(module):
            if attr_name.startswith("handle_"):
                fn = getattr(module, attr_name)
                if callable(fn):
                    tool_name = attr_name[7:]  # strip "handle_"
                    handlers[tool_name] = fn

        # Auto-generate schemas for handlers that lack an explicit entry
        schema_names = {s.get("function", {}).get("name") for s in schemas}
        for tool_name, fn in handlers.items():
            if tool_name not in schema_names:
                schemas.append(
                    self._auto_generate_schema(tool_name, fn, skill_name)
                )

        # Default RBAC permission for handlers without an explicit mapping
        for tool_name in handlers:
            if tool_name not in permissions:
                permissions[tool_name] = "dynamic_skill"

        return {
            "schemas": schemas,
            "permissions": permissions,
            "handlers": handlers,
            "handler_names": list(handlers.keys()),
            "has_initialize": has_initialize,
        }

    def _auto_generate_schema(
        self, tool_name: str, handler_fn, skill_name: str
    ) -> Dict:
        """
        Auto-generate an OpenAI function-calling schema from a handler's
        docstring.  Falls back to a minimal schema if parsing fails.

        Docstring convention::

            First line is the description.

            Args:
                param_name (type): Description of the parameter
        """
        doc = (
            inspect.getdoc(handler_fn)
            or f"Dynamic tool '{tool_name}' from skill '{skill_name}'"
        )
        lines = doc.split("\n")
        description = lines[0].strip() if lines else f"Tool: {tool_name}"

        properties: Dict[str, Any] = {}
        required: List[str] = []

        # Parse an Args/Parameters/Params section
        in_args = False
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.lower().startswith(("args:", "parameters:", "params:")):
                in_args = True
                continue
            if in_args:
                if (
                    not stripped
                    or stripped.lower().startswith(
                        ("returns:", "return:", "raises:", "note:")
                    )
                ):
                    in_args = False
                    continue
                m = re.match(
                    r"[-*]?\s*(\w+)\s*(?:\((\w+)\))?\s*[:\-–]\s*(.*)", stripped
                )
                if m:
                    pname, ptype, pdesc = m.groups()
                    _type_map = {
                        "str": "string",
                        "string": "string",
                        "int": "integer",
                        "integer": "integer",
                        "float": "number",
                        "number": "number",
                        "bool": "boolean",
                        "boolean": "boolean",
                        "list": "array",
                        "array": "array",
                        "dict": "object",
                        "object": "object",
                    }
                    json_type = _type_map.get((ptype or "").lower(), "string")
                    prop: Dict[str, Any] = {
                        "type": json_type,
                        "description": (pdesc.strip() or pname),
                    }
                    if json_type == "array":
                        prop["items"] = {"type": "string"}
                    properties[pname] = prop
                    required.append(pname)

        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    # ── Validation & security ─────────────────────────────────────────────

    def _validate_syntax(self, code: str) -> Dict[str, Any]:
        try:
            ast.parse(code)
            return {"valid": True}
        except SyntaxError as e:
            return {"valid": False, "error": f"Line {e.lineno}: {e.msg}"}

    def _check_security(self, code: str) -> Dict[str, Any]:
        """
        Security check,  blocks dangerous patterns while allowing
        legitimate imports (sqlite3, json, pathlib, etc.).
        """
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, code):
                return {
                    "safe": False,
                    "reason": f"Forbidden pattern detected: {pattern}",
                }
        return {"safe": True}

    # ── Skill CRUD ────────────────────────────────────────────────────────

    async def create_skill(
        self,
        name: str,
        description: str,
        code: str,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Create a new dynamic skill from generated Python code.

        The module is loaded, its tool info extracted, and returned so the
        ToolRegistry can wire schemas, dispatch, and RBAC at runtime.

        Returns:
            Dict with keys: success, skill, path, module, tool_info, message
        """
        logger.info(f"🧬 Creating dynamic skill: {name}")

        # Validate name
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", name):
            return {
                "success": False,
                "error": (
                    "Skill name must start with a letter and contain only "
                    "letters, digits, or underscores"
                ),
            }

        # Validate syntax
        syntax = self._validate_syntax(code)
        if not syntax["valid"]:
            return {"success": False, "error": f"Syntax error: {syntax['error']}"}

        # Security check
        security = self._check_security(code)
        if not security["safe"]:
            return {
                "success": False,
                "error": f"Security violation: {security['reason']}",
            }

        # Write skill file
        skill_file = self.skills_dir / f"{name}.py"
        skill_file.write_text(code)

        # Load module
        try:
            module = self._load_module(name, skill_file)
            self._loaded_modules[name] = module
        except Exception as e:
            logger.error(f"Failed to load skill '{name}': {e}")
            skill_file.unlink(missing_ok=True)
            return {"success": False, "error": f"Failed to load module: {e}"}

        # Extract tool info
        tool_info = self._extract_tool_info(module, name)

        # Persist to registry
        self.registry[name] = {
            "name": name,
            "description": description,
            "file": str(skill_file),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "active": True,
            "tool_names": tool_info["handler_names"],
        }
        self._save_registry()

        n_tools = len(tool_info["handlers"])
        logger.info(
            f"✅ Skill '{name}' created,  "
            f"{n_tools} tool(s), "
            f"{len(tool_info['schemas'])} schema(s)"
        )

        return {
            "success": True,
            "skill": name,
            "path": str(skill_file),
            "module": module,
            "tool_info": tool_info,
            "message": (
                f"Skill '{name}' created with "
                f"{n_tools} auto-wired tool(s)"
            ),
        }

    def load_all_active(self) -> List[Dict[str, Any]]:
        """
        Load every active skill from disk and return module + tool_info
        for each.  Called once during ``ToolRegistry.initialize()`` so
        dynamic skills survive restarts.
        """
        results = []
        for name, entry in list(self.registry.items()):
            if not entry.get("active", True):
                continue
            skill_file = Path(entry["file"])
            if not skill_file.exists():
                logger.warning(
                    f"Dynamic skill '{name}' file missing,  skipping"
                )
                continue
            try:
                module = self._load_module(name, skill_file)
                self._loaded_modules[name] = module
                tool_info = self._extract_tool_info(module, name)
                results.append(
                    {"name": name, "module": module, "tool_info": tool_info}
                )
                logger.info(
                    f"✅ Reloaded dynamic skill '{name}',  "
                    f"{len(tool_info['handlers'])} tool(s)"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to reload dynamic skill '{name}': {e}"
                )
        return results

    async def list_skills(self) -> List[Dict]:
        """Return metadata for every registered skill."""
        return [
            {
                "name": e["name"],
                "description": e["description"],
                "active": e.get("active", True),
                "tool_names": e.get("tool_names", []),
                "metadata": e.get("metadata", {}),
                "created_at": e.get("created_at", "unknown"),
            }
            for e in self.registry.values()
        ]

    def disable_skill(self, name: str) -> bool:
        if name in self.registry:
            self.registry[name]["active"] = False
            self._save_registry()
            logger.info(f"Disabled skill: {name}")
            return True
        return False

    def enable_skill(self, name: str) -> bool:
        if name in self.registry:
            self.registry[name]["active"] = True
            self._save_registry()
            logger.info(f"Enabled skill: {name}")
            return True
        return False

    def delete_skill(self, name: str) -> Dict[str, Any]:
        """Delete a skill and return its tool names for unregistration."""
        if name not in self.registry:
            return {"success": False, "error": f"Skill '{name}' not found"}

        entry = self.registry[name]
        tool_names = entry.get("tool_names", [])

        # Remove file
        skill_file = Path(entry["file"])
        if skill_file.exists():
            skill_file.unlink()

        # Remove from registry
        del self.registry[name]
        self._save_registry()

        # Unload from Python
        module_name = f"dynamic_skill_{name}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        self._loaded_modules.pop(name, None)

        logger.info(f"Deleted skill '{name}' (tools: {tool_names})")
        return {"success": True, "tool_names": tool_names}


# ── Helper: create async wrapper for a dynamic handler ───────────────────

def make_dynamic_handler(handler_fn):
    """
    Wrap a dynamic skill's handler function so it conforms to the
    ToolRegistry convention:  ``async fn(params: dict) -> str``

    Handles both sync and async handlers, and JSON-serialises dict results.
    """
    if asyncio.iscoroutinefunction(handler_fn):

        async def _wrapper(params):
            try:
                result = await handler_fn(params)
                if isinstance(result, (dict, list)):
                    return json.dumps(result, indent=2, default=str)
                return str(result)
            except Exception as e:
                return json.dumps({"error": str(e)})

    else:

        async def _wrapper(params):
            try:
                result = handler_fn(params)
                if isinstance(result, (dict, list)):
                    return json.dumps(result, indent=2, default=str)
                return str(result)
            except Exception as e:
                return json.dumps({"error": str(e)})

    return _wrapper


# ── Skill Template (shown to the LLM when it creates skills) ─────────────

SKILL_PROTOCOL_GUIDE = '''\
# ── Dynamic Skill Protocol ─────────────────────────────────────────────
#
# A dynamic skill module should define:
#
#   TOOL_SCHEMAS      ,  list of OpenAI function-calling schema dicts
#   TOOL_PERMISSIONS  ,  dict of tool_name → permission string
#   handle_<name>()   ,  async handler for each tool  (params dict → str)
#   initialize()      ,  optional async setup (DB tables, etc.)
#
# The module-level variable  __skill_data_dir__  is injected automatically
# and points to a persistent directory for this skill's data files / DBs.
#
# Example:
#
#   import json, sqlite3
#   from pathlib import Path
#
#   DATA_DIR = Path(globals().get("__skill_data_dir__", "."))
#
#   TOOL_SCHEMAS = [{
#       "type": "function",
#       "function": {
#           "name": "my_tool",
#           "description": "Does something useful",
#           "parameters": {
#               "type": "object",
#               "properties": {
#                   "query": {"type": "string", "description": "Input query"}
#               },
#               "required": ["query"]
#           }
#       }
#   }]
#
#   TOOL_PERMISSIONS = {"my_tool": "dynamic_skill"}
#
#   async def initialize():
#       db = sqlite3.connect(str(DATA_DIR / "store.db"))
#       db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT)")
#       db.commit(); db.close()
#
#   async def handle_my_tool(params: dict) -> str:
#       query = params.get("query", "")
#       return json.dumps({"success": True, "result": f"Processed: {query}"})
'''
