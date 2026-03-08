"""
Self-Replicator — WORLD FIRST
Autonomous self-replication and horizontal scaling.
The agent can clone itself, deploy copies, manage a fleet
of replicas, and coordinate distributed intelligence.
"""
import json
import logging
import hashlib
import shutil
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# ── Data Models ───────────────────────────────────────────────────────

@dataclass
class Replica:
    id: str
    name: str
    source_profile: str
    target_dir: str
    status: str = "created"  # created, deploying, running, stopped, failed
    created_at: str = ""
    port: int = 0
    pid: Optional[int] = None
    config_overrides: Dict[str, Any] = field(default_factory=dict)
    health_checks: int = 0
    last_heartbeat: Optional[str] = None

@dataclass
class ReplicationEvent:
    id: str
    replica_id: str
    event_type: str  # clone, deploy, start, stop, health_check, sync
    timestamp: str
    details: str = ""
    success: bool = True

# ── Core Engine ───────────────────────────────────────────────────────

class SelfReplicator:
    """
    Self-replication and horizontal scaling engine.
    Clones the agent codebase, configures replicas,
    deploys them, and manages a distributed fleet.
    """

    MAX_REPLICAS = 10
    BASE_PORT = 8800

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "self_replicator_state.json"

        self.replicas: List[Replica] = []
        self.events: List[ReplicationEvent] = []
        self.total_clones = 0
        self.total_deployments = 0
        self.total_syncs = 0

        self._load_state()

    def _get_project_root(self) -> Path:
        """Find the project root directory."""
        # Walk up from current file to find pyproject.toml
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                return parent
        return Path.cwd()

    def clone(self, name: str, profile: str = "replica",
              config_overrides: Optional[Dict[str, Any]] = None) -> Optional[Replica]:
        """Create a clone of the agent."""
        if len(self.replicas) >= self.MAX_REPLICAS:
            logger.warning(f"Max replicas ({self.MAX_REPLICAS}) reached")
            return None

        replica_id = hashlib.sha256(f"replica_{name}_{datetime.now().isoformat()}".encode()).hexdigest()[:10]
        target_dir = str(self.data_dir / "replicas" / replica_id)
        port = self.BASE_PORT + len(self.replicas)

        replica = Replica(
            id=replica_id, name=name, source_profile=profile,
            target_dir=target_dir, port=port,
            created_at=datetime.now(timezone.utc).isoformat(),
            config_overrides=config_overrides or {},
        )

        # Clone the codebase
        try:
            project_root = self._get_project_root()
            target = Path(target_dir)
            target.mkdir(parents=True, exist_ok=True)

            # Copy essential files (not the entire tree)
            essential_dirs = ["opensable", "agents", "config"]
            essential_files = ["pyproject.toml", "requirements.txt", "main.py", "sable.py"]

            for d in essential_dirs:
                src = project_root / d
                dst = target / d
                if src.exists():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
                        "__pycache__", "*.pyc", ".git", "node_modules", "venv",
                    ))

            for f in essential_files:
                src = project_root / f
                dst = target / f
                if src.exists():
                    shutil.copy2(src, dst)

            # Create data directory for replica
            (target / "data").mkdir(exist_ok=True)

            replica.status = "created"
            self.total_clones += 1
            self._record_event(replica_id, "clone", f"Cloned to {target_dir}")

        except Exception as e:
            replica.status = "failed"
            self._record_event(replica_id, "clone", f"Clone failed: {e}", success=False)
            logger.error(f"Clone failed: {e}")

        self.replicas.append(replica)
        self._save_state()
        return replica

    async def deploy(self, replica_id: str) -> bool:
        """Deploy a replica (prepare for running)."""
        replica = next((r for r in self.replicas if r.id == replica_id), None)
        if not replica:
            return False

        if replica.status == "failed":
            return False

        try:
            target = Path(replica.target_dir)
            if not target.exists():
                self._record_event(replica_id, "deploy", "Target dir missing", success=False)
                return False

            # Write replica-specific config
            config = {
                "profile": replica.source_profile,
                "port": replica.port,
                "is_replica": True,
                "parent_id": "primary",
                "replica_id": replica.id,
                **replica.config_overrides,
            }
            (target / "data" / "replica_config.json").write_text(json.dumps(config, indent=2))

            replica.status = "deploying"
            self.total_deployments += 1
            self._record_event(replica_id, "deploy", f"Deployed on port {replica.port}")
            self._save_state()
            return True

        except Exception as e:
            self._record_event(replica_id, "deploy", f"Deploy failed: {e}", success=False)
            return False

    async def start_replica(self, replica_id: str) -> bool:
        """Start a replica process."""
        replica = next((r for r in self.replicas if r.id == replica_id), None)
        if not replica or replica.status not in ("created", "deploying", "stopped"):
            return False

        try:
            import subprocess
            target = Path(replica.target_dir)
            python = sys.executable

            # Start the replica as a subprocess
            proc = subprocess.Popen(
                [python, "-m", "opensable", "--profile", replica.source_profile, "--port", str(replica.port)],
                cwd=str(target),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=True,
            )
            replica.pid = proc.pid
            replica.status = "running"
            replica.last_heartbeat = datetime.now(timezone.utc).isoformat()
            self._record_event(replica_id, "start", f"Started PID {proc.pid}")
            self._save_state()
            return True

        except Exception as e:
            self._record_event(replica_id, "start", f"Start failed: {e}", success=False)
            return False

    def stop_replica(self, replica_id: str) -> bool:
        """Stop a running replica."""
        replica = next((r for r in self.replicas if r.id == replica_id), None)
        if not replica or replica.status != "running":
            return False

        try:
            import signal
            import os
            if replica.pid:
                os.kill(replica.pid, signal.SIGTERM)
            replica.status = "stopped"
            replica.pid = None
            self._record_event(replica_id, "stop", "Stopped gracefully")
            self._save_state()
            return True
        except Exception as e:
            replica.status = "stopped"
            self._record_event(replica_id, "stop", f"Stop attempt: {e}", success=False)
            self._save_state()
            return False

    def destroy_replica(self, replica_id: str) -> bool:
        """Destroy a replica completely."""
        replica = next((r for r in self.replicas if r.id == replica_id), None)
        if not replica:
            return False

        # Stop if running
        if replica.status == "running":
            self.stop_replica(replica_id)

        # Remove files
        try:
            target = Path(replica.target_dir)
            if target.exists():
                shutil.rmtree(target)
        except Exception as e:
            logger.debug(f"Failed to remove replica files: {e}")

        self.replicas = [r for r in self.replicas if r.id != replica_id]
        self._record_event(replica_id, "destroy", "Replica destroyed")
        self._save_state()
        return True

    async def sync_state(self, replica_id: str) -> bool:
        """Sync state from primary to replica."""
        replica = next((r for r in self.replicas if r.id == replica_id), None)
        if not replica:
            return False

        try:
            project_root = self._get_project_root()
            src_data = project_root / "data"
            dst_data = Path(replica.target_dir) / "data"

            if src_data.exists():
                # Sync key state files
                for state_file in src_data.glob("*.json"):
                    dst_file = dst_data / state_file.name
                    if state_file.name != "replica_config.json":
                        shutil.copy2(state_file, dst_file)

            self.total_syncs += 1
            self._record_event(replica_id, "sync", "State synced from primary")
            self._save_state()
            return True

        except Exception as e:
            self._record_event(replica_id, "sync", f"Sync failed: {e}", success=False)
            return False

    def _record_event(self, replica_id: str, event_type: str, details: str, success: bool = True):
        eid = hashlib.sha256(f"ev_{replica_id}_{datetime.now().isoformat()}".encode()).hexdigest()[:10]
        event = ReplicationEvent(
            id=eid, replica_id=replica_id, event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=details, success=success,
        )
        self.events.append(event)
        if len(self.events) > 200:
            self.events = self.events[-200:]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_replicas": len(self.replicas),
            "running_replicas": sum(1 for r in self.replicas if r.status == "running"),
            "total_clones": self.total_clones,
            "total_deployments": self.total_deployments,
            "total_syncs": self.total_syncs,
            "max_replicas": self.MAX_REPLICAS,
            "fleet_status": {r.name: r.status for r in self.replicas},
        }

    def _save_state(self):
        try:
            state = {
                "replicas": [asdict(r) for r in self.replicas],
                "events": [asdict(e) for e in self.events[-100:]],
                "total_clones": self.total_clones,
                "total_deployments": self.total_deployments,
                "total_syncs": self.total_syncs,
            }
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.debug(f"SelfReplicator save failed: {e}")

    def _load_state(self):
        try:
            if self.state_file.exists():
                state = json.loads(self.state_file.read_text())
                self.replicas = [Replica(**r) for r in state.get("replicas", [])]
                self.events = [ReplicationEvent(**e) for e in state.get("events", [])]
                self.total_clones = state.get("total_clones", 0)
                self.total_deployments = state.get("total_deployments", 0)
                self.total_syncs = state.get("total_syncs", 0)
        except Exception as e:
            logger.debug(f"SelfReplicator load failed: {e}")
