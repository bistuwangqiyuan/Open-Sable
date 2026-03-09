"""Test the Dynamic Skill Protocol auto-wiring."""
import asyncio
import json
from types import SimpleNamespace

SAMPLE_SKILL_CODE = """
import json
from pathlib import Path

DATA_DIR = Path(globals().get("__skill_data_dir__", "."))

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "inventory_search",
            "description": "Search the inventory database for products",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "category": {"type": "string", "description": "Product category filter"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inventory_add",
            "description": "Add a new product to inventory",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Product name"},
                    "quantity": {"type": "integer", "description": "Quantity in stock"},
                },
                "required": ["name", "quantity"],
            },
        },
    },
]

TOOL_PERMISSIONS = {
    "inventory_search": "dynamic_skill",
    "inventory_add": "dynamic_skill",
}


async def initialize():
    print(f"  DATA_DIR: {DATA_DIR}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)


async def handle_inventory_search(params):
    query = params.get("query", "")
    return json.dumps({"results": [f"Widget-{query}"], "count": 1})


async def handle_inventory_add(params):
    name = params.get("name", "")
    qty = params.get("quantity", 0)
    return json.dumps({"success": True, "product": name, "quantity": qty})
"""

# Skill with NO explicit schemas — tests auto-generation from docstrings
AUTO_SCHEMA_SKILL = """
import json

async def handle_price_check(params):
    \"\"\"Check the price of a product.

    Args:
        product_name (str): Name of the product to check
        currency (str): Currency code (e.g. USD, EUR)

    Returns:
        Price information
    \"\"\"
    name = params.get("product_name", "unknown")
    currency = params.get("currency", "USD")
    return json.dumps({"product": name, "price": 42.99, "currency": currency})


async def handle_price_history(params):
    \"\"\"Get historical prices for a product.

    Args:
        product_name (str): Name of the product
        days (int): Number of days of history

    Returns:
        List of historical prices
    \"\"\"
    return json.dumps({"history": [40.0, 41.5, 42.99], "days": params.get("days", 7)})
"""


async def test_full_protocol():
    """Test skill with explicit TOOL_SCHEMAS."""
    from opensable.core.skill_creator import SkillCreator, make_dynamic_handler

    config = SimpleNamespace(data_dir="./data")
    creator = SkillCreator(config)

    result = await creator.create_skill(
        "test_inventory", "Inventory management", SAMPLE_SKILL_CODE
    )

    assert result["success"], f"Create failed: {result.get('error')}"
    print(f"✅ Skill created: success={result['success']}")

    tool_info = result["tool_info"]
    assert len(tool_info["schemas"]) == 2, f"Expected 2 schemas, got {len(tool_info['schemas'])}"
    assert "inventory_search" in tool_info["handlers"]
    assert "inventory_add" in tool_info["handlers"]
    assert tool_info["has_initialize"] is True
    print(f"  Schemas: {len(tool_info['schemas'])}")
    print(f"  Handlers: {list(tool_info['handlers'].keys())}")
    print(f"  Permissions: {tool_info['permissions']}")

    # Test handler execution via wrapper
    handler = make_dynamic_handler(tool_info["handlers"]["inventory_search"])
    result2 = await handler({"query": "cotton"})
    parsed = json.loads(result2)
    assert parsed["count"] == 1
    print(f"  Handler call: {result2}")

    # Clean up
    creator.delete_skill("test_inventory")
    print("✅ Full protocol test PASSED\n")


async def test_auto_schema():
    """Test skill WITHOUT explicit schemas — auto-generation from docstrings."""
    from opensable.core.skill_creator import SkillCreator, make_dynamic_handler

    config = SimpleNamespace(data_dir="./data")
    creator = SkillCreator(config)

    result = await creator.create_skill(
        "test_pricing", "Auto-schema pricing tool", AUTO_SCHEMA_SKILL
    )

    assert result["success"], f"Create failed: {result.get('error')}"
    print(f"✅ Auto-schema skill created")

    tool_info = result["tool_info"]
    assert len(tool_info["schemas"]) == 2, f"Expected 2 auto schemas, got {len(tool_info['schemas'])}"
    assert "price_check" in tool_info["handlers"]
    assert "price_history" in tool_info["handlers"]

    # Verify auto-generated schemas have correct parameters
    for schema in tool_info["schemas"]:
        fn = schema["function"]
        print(f"  Schema: {fn['name']} — params: {list(fn['parameters']['properties'].keys())}")

    price_schema = next(
        s for s in tool_info["schemas"] if s["function"]["name"] == "price_check"
    )
    props = price_schema["function"]["parameters"]["properties"]
    assert "product_name" in props, f"Missing product_name in auto-schema: {props}"
    assert "currency" in props, f"Missing currency in auto-schema: {props}"
    assert props["product_name"]["type"] == "string"
    print(f"  Auto-schema properties validated ✓")

    # Test handler
    handler = make_dynamic_handler(tool_info["handlers"]["price_check"])
    result2 = await handler({"product_name": "silk", "currency": "EUR"})
    parsed = json.loads(result2)
    assert parsed["price"] == 42.99
    print(f"  Handler call: {result2}")

    # Clean up
    creator.delete_skill("test_pricing")
    print("✅ Auto-schema test PASSED\n")


async def test_reload():
    """Test that skills persist and reload across sessions."""
    from opensable.core.skill_creator import SkillCreator

    config = SimpleNamespace(data_dir="./data")
    creator = SkillCreator(config)

    # Create a skill
    result = await creator.create_skill(
        "test_persist", "Persistence test", AUTO_SCHEMA_SKILL
    )
    assert result["success"]

    # Simulate restart: new SkillCreator instance
    creator2 = SkillCreator(config)
    active = creator2.load_all_active()
    assert len(active) >= 1
    found = any(s["name"] == "test_persist" for s in active)
    assert found, "Skill not found after reload"
    print(f"✅ Reload test: found {len(active)} active skill(s)")

    for s in active:
        if s["name"] == "test_persist":
            print(f"  Reloaded tools: {s['tool_info']['handler_names']}")

    # Clean up
    creator2.delete_skill("test_persist")
    print("✅ Reload test PASSED\n")


async def main():
    print("=" * 60)
    print("Dynamic Skill Auto-Wiring Tests")
    print("=" * 60 + "\n")
    await test_full_protocol()
    await test_auto_schema()
    await test_reload()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
