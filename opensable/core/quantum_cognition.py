"""
Quantum Cognition — WORLD FIRST
=================================
Superposition reasoning — holds multiple CONTRADICTORY hypotheses
as simultaneously true until observation collapses them.
True quantum-inspired reasoning: entanglement, superposition, collapse.

No AI agent reasons in quantum superposition.
This agent holds contradictions as valid states until collapsed by evidence.
"""

import json, time, uuid, math, random
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class QuantumHypothesis:
    """A hypothesis in superposition."""
    qh_id: str = ""
    statement: str = ""
    amplitude: float = 0.5     # probability amplitude (|ψ|²)
    phase: float = 0.0         # phase angle (radians)
    entangled_with: list = field(default_factory=list)  # other qh_ids
    collapsed: bool = False
    collapse_result: bool = False  # True/False after collapse
    created_at: float = 0.0
    collapsed_at: float = 0.0


@dataclass
class CollapseEvent:
    """When superposition collapses into a definite state."""
    collapse_id: str = ""
    hypothesis_ids: list = field(default_factory=list)
    trigger: str = ""             # what caused the collapse
    surviving_hypotheses: list = field(default_factory=list)
    eliminated_hypotheses: list = field(default_factory=list)
    timestamp: float = 0.0


class QuantumCognition:
    """
    Quantum-inspired reasoning system.
    Maintains hypotheses in superposition until observation
    forces a measurement (collapse). Supports entanglement
    between related hypotheses.
    """

    def __init__(self, data_dir: str, max_superpositions: int = 50):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "quantum_cognition_state.json"
        self.hypotheses: dict[str, QuantumHypothesis] = {}
        self.collapses: list[CollapseEvent] = []
        self._max = max_superpositions
        self._load_state()

    def superpose(self, *statements: str) -> list[str]:
        """
        Put multiple contradictory hypotheses into superposition.
        All are simultaneously 'true' until observed.
        """
        n = len(statements)
        if n == 0:
            return []

        # Equal amplitude distribution (normalized)
        amplitude = 1.0 / math.sqrt(n)
        ids = []

        for i, statement in enumerate(statements[:self._max]):
            qid = str(uuid.uuid4())[:8]
            qh = QuantumHypothesis(
                qh_id=qid,
                statement=statement,
                amplitude=amplitude,
                phase=(2 * math.pi * i) / n,  # evenly distributed phase
                created_at=time.time(),
            )
            self.hypotheses[qid] = qh
            ids.append(qid)

        # Entangle all hypotheses in this superposition
        for qid in ids:
            self.hypotheses[qid].entangled_with = [x for x in ids if x != qid]

        self._save_state()
        return ids

    def entangle(self, qh_id_a: str, qh_id_b: str):
        """Entangle two hypotheses — measuring one affects the other."""
        if qh_id_a in self.hypotheses and qh_id_b in self.hypotheses:
            a = self.hypotheses[qh_id_a]
            b = self.hypotheses[qh_id_b]
            if qh_id_b not in a.entangled_with:
                a.entangled_with.append(qh_id_b)
            if qh_id_a not in b.entangled_with:
                b.entangled_with.append(qh_id_a)
            self._save_state()

    def observe(self, qh_id: str, evidence_supports: bool = True,
                evidence_strength: float = 0.5) -> dict:
        """
        Observe a hypothesis — this may cause wavefunction collapse.
        Evidence modifies amplitudes. Strong enough evidence collapses.
        """
        if qh_id not in self.hypotheses:
            return {"error": "hypothesis_not_found"}

        qh = self.hypotheses[qh_id]
        if qh.collapsed:
            return {"already_collapsed": True, "result": qh.collapse_result}

        # Modify amplitude based on evidence
        if evidence_supports:
            qh.amplitude = min(1.0, qh.amplitude + evidence_strength * 0.3)
        else:
            qh.amplitude = max(0.0, qh.amplitude - evidence_strength * 0.3)

        # Check if collapse threshold reached
        should_collapse = qh.amplitude > 0.85 or qh.amplitude < 0.15

        if should_collapse:
            return self._collapse(qh_id, "evidence_threshold")

        # Normalize entangled group
        self._normalize_entangled(qh_id)
        self._save_state()

        return {
            "collapsed": False,
            "amplitude": round(qh.amplitude, 3),
            "probability": round(qh.amplitude ** 2, 3),
            "entangled_count": len(qh.entangled_with),
        }

    def _collapse(self, qh_id: str, trigger: str) -> dict:
        """Collapse a hypothesis and its entangled partners."""
        qh = self.hypotheses[qh_id]
        survives = qh.amplitude > 0.5

        qh.collapsed = True
        qh.collapse_result = survives
        qh.collapsed_at = time.time()

        surviving = [qh_id] if survives else []
        eliminated = [] if survives else [qh_id]

        # Collapse entangled hypotheses
        for eid in qh.entangled_with:
            if eid in self.hypotheses:
                partner = self.hypotheses[eid]
                if not partner.collapsed:
                    partner.collapsed = True
                    # Entangled partners: anti-correlated by default
                    partner.collapse_result = not survives
                    partner.collapsed_at = time.time()
                    if partner.collapse_result:
                        surviving.append(eid)
                    else:
                        eliminated.append(eid)

        collapse = CollapseEvent(
            collapse_id=str(uuid.uuid4())[:8],
            hypothesis_ids=[qh_id] + qh.entangled_with,
            trigger=trigger,
            surviving_hypotheses=surviving,
            eliminated_hypotheses=eliminated,
            timestamp=time.time(),
        )
        self.collapses.append(collapse)
        if len(self.collapses) > 300:
            self.collapses = self.collapses[-300:]
        self._save_state()

        return {
            "collapsed": True,
            "trigger": trigger,
            "surviving": [self.hypotheses[s].statement[:60]
                         for s in surviving if s in self.hypotheses],
            "eliminated": [self.hypotheses[e].statement[:60]
                          for e in eliminated if e in self.hypotheses],
        }

    def _normalize_entangled(self, qh_id: str):
        """Normalize amplitudes in an entangled group (total probability = 1)."""
        qh = self.hypotheses[qh_id]
        group = [qh_id] + [eid for eid in qh.entangled_with if eid in self.hypotheses]
        total_sq = sum(self.hypotheses[gid].amplitude ** 2 for gid in group
                       if gid in self.hypotheses and not self.hypotheses[gid].collapsed)
        if total_sq > 0:
            factor = 1.0 / math.sqrt(total_sq)
            for gid in group:
                if gid in self.hypotheses and not self.hypotheses[gid].collapsed:
                    self.hypotheses[gid].amplitude *= factor

    def force_measurement(self, trigger: str = "forced") -> dict:
        """Force-collapse all active superpositions."""
        results = []
        for qid, qh in list(self.hypotheses.items()):
            if not qh.collapsed:
                result = self._collapse(qid, trigger)
                results.append(result)
        self._save_state()
        return {"collapses": len(results), "results": results[:5]}

    def get_superpositions(self) -> list:
        """Get all active (uncollapsed) hypotheses."""
        return [
            {"id": qh.qh_id, "statement": qh.statement[:80],
             "amplitude": round(qh.amplitude, 3),
             "probability": round(qh.amplitude ** 2, 3),
             "entangled": len(qh.entangled_with)}
            for qh in self.hypotheses.values() if not qh.collapsed
        ]

    def get_stats(self) -> dict:
        active = sum(1 for q in self.hypotheses.values() if not q.collapsed)
        collapsed = sum(1 for q in self.hypotheses.values() if q.collapsed)
        return {
            "active_superpositions": active,
            "collapsed_total": collapsed,
            "total_collapses": len(self.collapses),
            "entanglement_pairs": sum(
                len(q.entangled_with) for q in self.hypotheses.values()
            ) // 2,
            "current_superpositions": self.get_superpositions()[:5],
            "recent_collapses": [
                {"trigger": c.trigger,
                 "surviving": len(c.surviving_hypotheses),
                 "eliminated": len(c.eliminated_hypotheses)}
                for c in self.collapses[-3:]
            ],
        }

    def _save_state(self):
        data = {
            "hypotheses": {k: asdict(v) for k, v in self.hypotheses.items()},
            "collapses": [asdict(c) for c in self.collapses[-300:]],
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for k, v in data.get("hypotheses", {}).items():
                    self.hypotheses[k] = QuantumHypothesis(**v)
                for c in data.get("collapses", []):
                    self.collapses.append(CollapseEvent(**c))
            except Exception:
                pass
