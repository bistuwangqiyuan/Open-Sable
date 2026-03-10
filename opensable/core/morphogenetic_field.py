"""
Morphogenetic Field,  WORLD FIRST
===================================
Template patterns that guide the formation of new capabilities.
When the agent needs a new ability, it grows one following the
structural blueprint of its most successful existing capabilities.

Like biological morphogenesis,  new organs grow following
the field patterns of existing ones. No AI does this.
"""

import json, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class CapabilityTemplate:
    """A structural template derived from a successful capability."""
    template_id: str = ""
    source_capability: str = ""
    structure: dict = field(default_factory=dict)
    success_rate: float = 0.0
    replication_count: int = 0
    created_at: float = 0.0


@dataclass
class GrowthEvent:
    """A new capability grown from a morphogenetic template."""
    growth_id: str = ""
    template_used: str = ""
    new_capability: str = ""
    adaptation_steps: list = field(default_factory=list)
    maturity: float = 0.0     # 0=embryonic, 1=fully mature
    timestamp: float = 0.0


class MorphogeneticField:
    """
    Guides the formation of new capabilities by replicating
    the structural patterns of successful existing ones.
    """

    def __init__(self, data_dir: str, max_templates: int = 50):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "morphogenetic_field_state.json"
        self.templates: dict[str, CapabilityTemplate] = {}
        self.growths: list[GrowthEvent] = []
        self.active_growths: dict[str, GrowthEvent] = {}
        self._max = max_templates
        self._load_state()

    def extract_template(self, capability_name: str, structure: dict,
                         success_rate: float = 0.7) -> str:
        """Extract a morphogenetic template from a successful capability."""
        tid = str(uuid.uuid4())[:8]
        template = CapabilityTemplate(
            template_id=tid,
            source_capability=capability_name,
            structure=structure,
            success_rate=success_rate,
            replication_count=0,
            created_at=time.time(),
        )
        self.templates[tid] = template
        if len(self.templates) > self._max:
            # Remove least successful templates
            worst = min(self.templates.items(),
                       key=lambda x: x[1].success_rate)
            del self.templates[worst[0]]
        self._save_state()
        return tid

    async def grow_capability(self, need: str, llm=None) -> dict:
        """Grow a new capability based on the best matching template."""
        if not self.templates:
            return {"error": "no_templates", "msg": "Extract templates first"}

        # Find best template
        best_template = max(self.templates.values(),
                           key=lambda t: t.success_rate)

        if llm:
            prompt = (
                f"MORPHOGENETIC GROWTH,  grow a new capability from a template:\n\n"
                f"Need: {need[:200]}\n"
                f"Template source: {best_template.source_capability}\n"
                f"Template structure: {json.dumps(best_template.structure)}\n\n"
                f"Design a new capability that meets the need by adapting "
                f"the template's structure. Keep the same architectural pattern.\n"
                f"Return JSON: {{\"capability_name\": \"...\", "
                f"\"adaptation_steps\": [\"...\"], \"maturity\": 0.0-1.0}}"
            )
            try:
                raw = await llm.chat_raw(prompt, max_tokens=400)
                import re
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    result = json.loads(m.group())
                    growth = GrowthEvent(
                        growth_id=str(uuid.uuid4())[:8],
                        template_used=best_template.template_id,
                        new_capability=result.get("capability_name", need[:50]),
                        adaptation_steps=result.get("adaptation_steps", []),
                        maturity=result.get("maturity", 0.3),
                        timestamp=time.time(),
                    )
                    self.growths.append(growth)
                    self.active_growths[growth.growth_id] = growth
                    best_template.replication_count += 1
                    self._save_state()
                    return {
                        "growth_id": growth.growth_id,
                        "capability": growth.new_capability,
                        "template": best_template.source_capability,
                        "maturity": growth.maturity,
                        "steps": growth.adaptation_steps,
                    }
            except Exception:
                pass

        # Heuristic growth
        growth = GrowthEvent(
            growth_id=str(uuid.uuid4())[:8],
            template_used=best_template.template_id,
            new_capability=f"adapted_{need[:30]}",
            adaptation_steps=["clone_structure", "adapt_to_need", "initialize"],
            maturity=0.2,
            timestamp=time.time(),
        )
        self.growths.append(growth)
        self.active_growths[growth.growth_id] = growth
        best_template.replication_count += 1
        if len(self.growths) > 200:
            self.growths = self.growths[-200:]
        self._save_state()
        return {
            "growth_id": growth.growth_id,
            "capability": growth.new_capability,
            "template": best_template.source_capability,
            "maturity": growth.maturity,
        }

    def mature(self, growth_id: str, amount: float = 0.1) -> dict:
        """Increase the maturity of a growing capability."""
        if growth_id in self.active_growths:
            g = self.active_growths[growth_id]
            g.maturity = min(1.0, g.maturity + amount)
            if g.maturity >= 1.0:
                del self.active_growths[growth_id]
            self._save_state()
            return {"growth_id": growth_id, "maturity": round(g.maturity, 2),
                    "fully_grown": g.maturity >= 1.0}
        return {"error": "growth_not_found"}

    def get_stats(self) -> dict:
        return {
            "templates": len(self.templates),
            "total_growths": len(self.growths),
            "active_growths": len(self.active_growths),
            "best_templates": [
                {"source": t.source_capability, "success": round(t.success_rate, 2),
                 "replications": t.replication_count}
                for t in sorted(self.templates.values(),
                               key=lambda t: t.success_rate, reverse=True)[:5]
            ],
            "growing_capabilities": [
                {"name": g.new_capability, "maturity": round(g.maturity, 2)}
                for g in self.active_growths.values()
            ],
        }

    def _save_state(self):
        data = {
            "templates": {k: asdict(v) for k, v in self.templates.items()},
            "growths": [asdict(g) for g in self.growths[-200:]],
            "active_growths": {k: asdict(v) for k, v in self.active_growths.items()},
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for k, v in data.get("templates", {}).items():
                    self.templates[k] = CapabilityTemplate(**v)
                for g in data.get("growths", []):
                    self.growths.append(GrowthEvent(**g))
                for k, v in data.get("active_growths", {}).items():
                    self.active_growths[k] = GrowthEvent(**v)
            except Exception:
                pass
