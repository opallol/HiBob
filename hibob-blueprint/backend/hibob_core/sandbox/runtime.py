"""Ephemeral sandbox runtime (Phase 7, ADR 0011).

High-risk tool types (shell/browser/mcp) execute inside an ephemeral, per-run container: no network
by default, read-only fs except a scoped workdir, destroyed after the run. v0.1 ships the runner
interface + a Noop backend (records the run, executes nothing real) so the governance path is live
and tested; the real DockerSandboxRunner is a lazy optional backend (the `sandbox` extra).
"""

from __future__ import annotations

from dataclasses import dataclass

from hibob_core.config import settings
from hibob_core.sandbox.spec import SandboxSpec


class SandboxUnavailable(Exception):
    """The configured sandbox backend isn't installed/available."""


@dataclass
class SandboxResult:
    exit_status: str          # succeeded | failed
    output: dict


class SandboxRunner:
    backend: str

    async def run(self, spec: SandboxSpec, *, payload: dict) -> SandboxResult:
        raise NotImplementedError


class NoopSandboxRunner(SandboxRunner):
    """Default backend: no container; returns a stub so flows are exercisable without Docker."""

    backend = "noop"

    async def run(self, spec: SandboxSpec, *, payload: dict) -> SandboxResult:
        return SandboxResult(
            exit_status="succeeded",
            output={"sandboxed": True, "backend": "noop", "image": spec.container_image,
                    "network_mode": spec.network_mode, "note": "noop sandbox - no real execution"},
        )


class DockerSandboxRunner(SandboxRunner):
    """Real ephemeral Docker container (lazy import; needs the `sandbox` extra)."""

    backend = "docker"

    def _client(self):
        try:
            import docker  # lazy (optional extra)
        except ImportError as e:
            raise SandboxUnavailable(
                "sandbox_backend=docker needs the 'sandbox' extra: pip install '.[sandbox]'"
            ) from e
        return docker.from_env()

    async def run(self, spec: SandboxSpec, *, payload: dict) -> SandboxResult:
        # Intentionally minimal seam: a real impl spins up `spec.container_image` with
        # network_mode/read-only fs/workdir from spec, runs payload, then removes the container.
        self._client()  # validates docker availability; full orchestration is the next increment
        raise SandboxUnavailable("DockerSandboxRunner orchestration not yet implemented (seam)")


def get_runner() -> SandboxRunner:
    backend = settings.sandbox_backend
    if backend == "docker":
        return DockerSandboxRunner()
    return NoopSandboxRunner()


def sandbox_enabled() -> bool:
    return settings.sandbox_backend != "off"
