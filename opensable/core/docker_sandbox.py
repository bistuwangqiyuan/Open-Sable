"""
Docker Sandbox — Ephemeral container-based code execution.

Provides secure, network-isolated, resource-limited execution of
LLM-generated code inside throwaway Docker containers. Each execution
gets a fresh filesystem and is destroyed on completion.

Features:
  - Per-execution ephemeral container (auto-removed)
  - CPU, memory, and PID limits
  - Network isolation (--network none by default)
  - Read-only root filesystem with tmpfs /tmp
  - Configurable timeout with forced kill
  - Multi-language support (Python, Node.js, Bash, Ruby, Go)
  - File mounting for input/output data exchange
  - Graceful fallback to process sandbox when Docker unavailable

Usage:
    sandbox = DockerSandbox()

    result = await sandbox.execute(
        code='print("Hello from sandbox!")',
        language='python',
        timeout=30,
    )
    print(result.stdout)   # "Hello from sandbox!"
    print(result.exit_code)  # 0
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────


class Language(Enum):
    PYTHON = "python"
    NODEJS = "nodejs"
    BASH = "bash"
    RUBY = "ruby"
    GO = "go"


@dataclass
class SandboxResult:
    """Result of a sandboxed execution."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    timed_out: bool = False
    duration_ms: int = 0
    container_id: str = ""
    language: str = "python"
    error: str = ""

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> dict:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "language": self.language,
            "error": self.error,
        }


@dataclass
class SandboxConfig:
    """Configuration for the Docker sandbox."""

    # Resource limits
    memory_limit: str = "256m"      # Docker memory format
    cpu_limit: float = 1.0          # CPU cores (0.5 = half core)
    pids_limit: int = 64            # Max processes inside container
    timeout: int = 30               # Seconds before kill

    # Network
    network: str = "none"           # "none" = fully isolated

    # Filesystem
    read_only: bool = True          # Read-only root FS
    tmpfs_size: str = "64m"         # Size of writable /tmp

    # Images per language
    images: Dict[str, str] = field(default_factory=lambda: {
        "python": "python:3.12-slim",
        "nodejs": "node:20-slim",
        "bash":   "alpine:3.19",
        "ruby":   "ruby:3.3-slim",
        "go":     "golang:1.22-alpine",
    })

    # Security
    drop_capabilities: bool = True   # Drop all Linux capabilities
    no_new_privileges: bool = True   # Prevent privilege escalation
    seccomp_profile: str = ""        # Custom seccomp profile path (empty = default)


# ── Docker availability check ────────────────────────────────────────────────


def _docker_available() -> bool:
    """Check if Docker daemon is accessible."""
    return shutil.which("docker") is not None


async def _docker_running() -> bool:
    """Check if Docker daemon is running and responsive."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "info",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        code = await asyncio.wait_for(proc.wait(), timeout=5)
        return code == 0
    except Exception:
        return False


# ── Language helpers ──────────────────────────────────────────────────────────


_FILE_NAMES = {
    "python": "main.py",
    "nodejs": "main.js",
    "bash":   "main.sh",
    "ruby":   "main.rb",
    "go":     "main.go",
}

_RUN_COMMANDS = {
    "python": ["python3", "/sandbox/main.py"],
    "nodejs": ["node", "/sandbox/main.js"],
    "bash":   ["sh", "/sandbox/main.sh"],
    "ruby":   ["ruby", "/sandbox/main.rb"],
    "go":     ["sh", "-c", "cd /sandbox && go run main.go"],
}


# ── Docker Sandbox ────────────────────────────────────────────────────────────


class DockerSandbox:
    """
    Ephemeral Docker container sandbox for safe code execution.

    Each call to `execute()` creates a new container, runs the code,
    captures output, and destroys the container. No state persists
    between executions.
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._available: Optional[bool] = None

    async def is_available(self) -> bool:
        """Check if Docker sandbox can be used."""
        if self._available is None:
            if not _docker_available():
                self._available = False
            else:
                self._available = await _docker_running()
        return self._available

    async def execute(
        self,
        code: str,
        *,
        language: str = "python",
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
        input_files: Optional[Dict[str, str]] = None,
        memory_limit: Optional[str] = None,
        cpu_limit: Optional[float] = None,
        network: Optional[str] = None,
    ) -> SandboxResult:
        """
        Execute code inside an ephemeral Docker container.

        Args:
            code: Source code to execute.
            language: One of python, nodejs, bash, ruby, go.
            timeout: Override config timeout (seconds).
            env: Environment variables to pass into container.
            input_files: Dict of {filename: content} to mount alongside code.
            memory_limit: Override memory limit (e.g., "512m").
            cpu_limit: Override CPU limit (cores).
            network: Override network mode.

        Returns:
            SandboxResult with stdout, stderr, exit_code, timing, etc.
        """
        if not await self.is_available():
            return await self._fallback_execute(code, language=language, timeout=timeout)

        lang = language.lower()
        if lang not in _FILE_NAMES:
            return SandboxResult(error=f"Unsupported language: {lang}", language=lang)

        timeout = timeout or self.config.timeout
        container_name = f"sable-sandbox-{uuid.uuid4().hex[:12]}"
        image = self.config.images.get(lang, self.config.images["python"])

        # Create temp directory with code and input files
        tmpdir = Path(tempfile.mkdtemp(prefix="sable-sandbox-"))
        try:
            # Write code file
            code_file = tmpdir / _FILE_NAMES[lang]
            code_file.write_text(code, encoding="utf-8")

            # Write input files if any
            if input_files:
                for name, content in input_files.items():
                    # Sanitize filename to prevent traversal
                    safe_name = Path(name).name
                    (tmpdir / safe_name).write_text(content, encoding="utf-8")

            # Build docker run command
            cmd = self._build_docker_cmd(
                container_name=container_name,
                image=image,
                lang=lang,
                sandbox_dir=str(tmpdir),
                env=env,
                memory_limit=memory_limit or self.config.memory_limit,
                cpu_limit=cpu_limit or self.config.cpu_limit,
                network=network or self.config.network,
            )

            logger.debug(f"[DockerSandbox] Running: {' '.join(cmd)}")
            t0 = time.monotonic()

            # Execute
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
                duration_ms = int((time.monotonic() - t0) * 1000)

                return SandboxResult(
                    stdout=stdout_bytes.decode("utf-8", errors="replace").strip(),
                    stderr=stderr_bytes.decode("utf-8", errors="replace").strip(),
                    exit_code=proc.returncode or 0,
                    duration_ms=duration_ms,
                    container_id=container_name,
                    language=lang,
                )

            except asyncio.TimeoutError:
                duration_ms = int((time.monotonic() - t0) * 1000)
                # Force kill the container
                await self._kill_container(container_name)
                return SandboxResult(
                    stderr=f"Execution timed out after {timeout}s",
                    timed_out=True,
                    duration_ms=duration_ms,
                    container_id=container_name,
                    language=lang,
                )

        finally:
            # Clean up temp directory
            shutil.rmtree(tmpdir, ignore_errors=True)
            # Ensure container is removed (--rm should handle this, but be safe)
            await self._remove_container(container_name)

    def _build_docker_cmd(
        self,
        container_name: str,
        image: str,
        lang: str,
        sandbox_dir: str,
        env: Optional[Dict[str, str]],
        memory_limit: str,
        cpu_limit: float,
        network: str,
    ) -> List[str]:
        """Build the `docker run` command with all security flags."""
        cmd = [
            "docker", "run",
            "--rm",                                   # Auto-remove on exit
            "--name", container_name,                 # Named for cleanup
            "--network", network,                     # Network isolation
            "--memory", memory_limit,                 # Memory cap
            "--cpus", str(cpu_limit),                 # CPU cap
            "--pids-limit", str(self.config.pids_limit),  # PID limit
            "-v", f"{sandbox_dir}:/sandbox:ro",       # Mount code read-only
        ]

        # Read-only root filesystem with writable /tmp
        if self.config.read_only:
            cmd += ["--read-only", "--tmpfs", f"/tmp:size={self.config.tmpfs_size}"]

        # Security hardening
        if self.config.drop_capabilities:
            cmd += ["--cap-drop", "ALL"]

        if self.config.no_new_privileges:
            cmd += ["--security-opt", "no-new-privileges"]

        if self.config.seccomp_profile:
            cmd += ["--security-opt", f"seccomp={self.config.seccomp_profile}"]

        # Environment variables
        if env:
            for k, v in env.items():
                # Sanitize: no shell metacharacters
                safe_k = k.replace("=", "").replace(";", "").replace("'", "")
                safe_v = v.replace("'", "")
                cmd += ["-e", f"{safe_k}={safe_v}"]

        # Image and run command
        cmd.append(image)
        cmd += _RUN_COMMANDS.get(lang, _RUN_COMMANDS["python"])

        return cmd

    async def _kill_container(self, name: str):
        """Force kill a running container."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "kill", name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5)
        except Exception:
            pass

    async def _remove_container(self, name: str):
        """Remove a container (if it still exists)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5)
        except Exception:
            pass

    async def _fallback_execute(
        self,
        code: str,
        *,
        language: str = "python",
        timeout: Optional[int] = None,
    ) -> SandboxResult:
        """
        Fallback execution using process isolation when Docker is unavailable.
        Uses the existing sandbox_runner for Python, subprocess for others.
        """
        timeout = timeout or self.config.timeout
        lang = language.lower()
        t0 = time.monotonic()

        if lang == "python":
            try:
                from opensable.core.sandbox_runner import run_sandboxed_python, SandboxError

                output = run_sandboxed_python(code, cpu_seconds=min(timeout, 10), mem_mb=256)
                duration_ms = int((time.monotonic() - t0) * 1000)
                return SandboxResult(
                    stdout=output,
                    exit_code=0,
                    duration_ms=duration_ms,
                    language=lang,
                )
            except SandboxError as e:
                duration_ms = int((time.monotonic() - t0) * 1000)
                return SandboxResult(
                    stderr=str(e),
                    exit_code=1,
                    duration_ms=duration_ms,
                    language=lang,
                    error=str(e),
                )
        else:
            # For non-Python, use basic subprocess with timeout
            interpreters = {"nodejs": "node", "bash": "sh", "ruby": "ruby"}
            interpreter = interpreters.get(lang)
            if not interpreter or not shutil.which(interpreter):
                return SandboxResult(
                    error=f"No interpreter for {lang} and Docker unavailable",
                    language=lang,
                )

            tmpfile = Path(tempfile.mktemp(suffix=_FILE_NAMES.get(lang, ".txt")))
            try:
                tmpfile.write_text(code, encoding="utf-8")
                proc = await asyncio.create_subprocess_exec(
                    interpreter, str(tmpfile),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                duration_ms = int((time.monotonic() - t0) * 1000)
                return SandboxResult(
                    stdout=stdout_b.decode("utf-8", errors="replace").strip(),
                    stderr=stderr_b.decode("utf-8", errors="replace").strip(),
                    exit_code=proc.returncode or 0,
                    duration_ms=duration_ms,
                    language=lang,
                )
            except asyncio.TimeoutError:
                proc.kill()
                duration_ms = int((time.monotonic() - t0) * 1000)
                return SandboxResult(
                    stderr=f"Timed out after {timeout}s",
                    timed_out=True,
                    duration_ms=duration_ms,
                    language=lang,
                )
            finally:
                tmpfile.unlink(missing_ok=True)

    async def pull_images(self, languages: Optional[List[str]] = None):
        """Pre-pull Docker images for faster first execution."""
        langs = languages or list(self.config.images.keys())
        for lang in langs:
            image = self.config.images.get(lang)
            if not image:
                continue
            logger.info(f"[DockerSandbox] Pulling {image}…")
            proc = await asyncio.create_subprocess_exec(
                "docker", "pull", image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

    def status(self) -> dict:
        """Return sandbox status info."""
        return {
            "docker_available": _docker_available(),
            "config": {
                "memory_limit": self.config.memory_limit,
                "cpu_limit": self.config.cpu_limit,
                "pids_limit": self.config.pids_limit,
                "timeout": self.config.timeout,
                "network": self.config.network,
                "read_only": self.config.read_only,
            },
            "languages": list(self.config.images.keys()),
        }
