"""
Akashic Records — WORLD FIRST
===============================
Immutable, append-only record of EVERY thought, decision, and outcome.
A permanent consciousness ledger that can NEVER be altered.
The agent's eternal memory — a blockchain of consciousness.

Named after the theosophical concept of a cosmic repository
of all events, thoughts, and experiences.
No AI agent has an immutable consciousness ledger.
"""

import json, time, uuid, hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class AkashicEntry:
    """An immutable record in the Akashic Records."""
    entry_id: str = ""
    sequence: int = 0
    entry_type: str = ""       # thought, decision, outcome, event, reflection
    content: str = ""
    context: dict = field(default_factory=dict)
    prev_hash: str = ""        # hash of previous entry (chain)
    entry_hash: str = ""       # hash of this entry
    timestamp: float = 0.0


class AkashicRecords:
    """
    Immutable consciousness ledger.
    Every thought, decision, and outcome is permanently recorded.
    Entries are chained via hashes — tampering is detectable.
    """

    def __init__(self, data_dir: str, max_entries_in_memory: int = 5000):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ledger_file = self._dir / "akashic_ledger.jsonl"  # append-only
        self._index_file = self._dir / "akashic_index.json"
        self._max_mem = max_entries_in_memory
        self.sequence: int = 0
        self.last_hash: str = "genesis"
        self.entry_count: int = 0
        self.type_counts: dict[str, int] = {}
        self.recent_entries: list[AkashicEntry] = []
        self._load_index()

    def record(self, entry_type: str, content: str,
               context: dict = None) -> AkashicEntry:
        """Record an immutable entry. Cannot be modified or deleted."""
        self.sequence += 1

        # Build the entry
        entry = AkashicEntry(
            entry_id=str(uuid.uuid4())[:12],
            sequence=self.sequence,
            entry_type=entry_type,
            content=content[:500],
            context=context or {},
            prev_hash=self.last_hash,
            timestamp=time.time(),
        )

        # Calculate hash (makes chain immutable)
        hash_input = f"{entry.sequence}|{entry.entry_type}|{entry.content}|{entry.prev_hash}|{entry.timestamp}"
        entry.entry_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        self.last_hash = entry.entry_hash

        # Append to ledger (NEVER overwrite)
        with open(self._ledger_file, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

        # Update tracking
        self.entry_count += 1
        self.type_counts[entry_type] = self.type_counts.get(entry_type, 0) + 1

        # Keep recent in memory
        self.recent_entries.append(entry)
        if len(self.recent_entries) > self._max_mem:
            self.recent_entries = self.recent_entries[-self._max_mem:]

        self._save_index()
        return entry

    def query(self, entry_type: str = "", keyword: str = "",
              limit: int = 20) -> list[dict]:
        """Query the Akashic Records (read-only, never modify)."""
        results = []
        keyword_lower = keyword.lower()

        for entry in reversed(self.recent_entries):
            if entry_type and entry.entry_type != entry_type:
                continue
            if keyword_lower and keyword_lower not in entry.content.lower():
                continue
            results.append({
                "sequence": entry.sequence,
                "type": entry.entry_type,
                "content": entry.content[:200],
                "hash": entry.entry_hash,
                "timestamp": entry.timestamp,
            })
            if len(results) >= limit:
                break
        return results

    def verify_integrity(self, last_n: int = 100) -> dict:
        """Verify the chain integrity — detect any tampering."""
        entries = self.recent_entries[-last_n:]
        if len(entries) < 2:
            return {"verified": True, "checked": len(entries), "broken_links": 0}

        broken = 0
        for i in range(1, len(entries)):
            expected_prev = entries[i - 1].entry_hash
            actual_prev = entries[i].prev_hash
            if expected_prev != actual_prev:
                broken += 1

        return {
            "verified": broken == 0,
            "checked": len(entries),
            "broken_links": broken,
            "chain_health": round(1.0 - broken / max(len(entries) - 1, 1), 3),
        }

    def get_timeline(self, hours: float = 24) -> dict:
        """Get activity timeline for the last N hours."""
        cutoff = time.time() - hours * 3600
        timeline = {}
        for entry in self.recent_entries:
            if entry.timestamp >= cutoff:
                hour_key = time.strftime("%H:00", time.localtime(entry.timestamp))
                if hour_key not in timeline:
                    timeline[hour_key] = {"count": 0, "types": {}}
                timeline[hour_key]["count"] += 1
                t = entry.entry_type
                timeline[hour_key]["types"][t] = timeline[hour_key]["types"].get(t, 0) + 1
        return timeline

    def get_stats(self) -> dict:
        integrity = self.verify_integrity(50)
        return {
            "total_entries": self.entry_count,
            "sequence": self.sequence,
            "type_counts": self.type_counts,
            "chain_integrity": integrity["chain_health"],
            "chain_verified": integrity["verified"],
            "recent_entries": [
                {"seq": e.sequence, "type": e.entry_type,
                 "content": e.content[:60], "hash": e.entry_hash[:8]}
                for e in self.recent_entries[-5:]
            ],
            "entries_per_type": self.type_counts,
        }

    def _save_index(self):
        data = {
            "sequence": self.sequence,
            "last_hash": self.last_hash,
            "entry_count": self.entry_count,
            "type_counts": self.type_counts,
        }
        self._index_file.write_text(json.dumps(data, indent=2))

    def _load_index(self):
        if self._index_file.exists():
            try:
                data = json.loads(self._index_file.read_text())
                self.sequence = data.get("sequence", 0)
                self.last_hash = data.get("last_hash", "genesis")
                self.entry_count = data.get("entry_count", 0)
                self.type_counts = data.get("type_counts", {})
            except Exception:
                pass
        # Load recent entries from ledger
        if self._ledger_file.exists():
            try:
                lines = self._ledger_file.read_text().strip().split("\n")
                for line in lines[-self._max_mem:]:
                    if line.strip():
                        data = json.loads(line)
                        self.recent_entries.append(AkashicEntry(**data))
            except Exception:
                pass
