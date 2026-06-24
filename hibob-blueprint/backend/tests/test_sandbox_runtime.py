"""Ephemeral sandbox runtime (ADR 0011). Noop backend + lazy docker."""

import builtins

import pytest

from hibob_core.config import settings
from hibob_core.sandbox import runtime
from hibob_core.sandbox.spec import SandboxSpec, spec_for_tool


async def test_noop_runner_returns_sandboxed_stub():
    res = await runtime.NoopSandboxRunner().run(SandboxSpec(container_image="img"), payload={})
    assert res.exit_status == "succeeded"
    assert res.output["sandboxed"] is True
    assert res.output["network_mode"] == "none"


def test_get_runner_and_enabled(monkeypatch):
    monkeypatch.setattr(settings, "sandbox_backend", "noop")
    assert runtime.get_runner().backend == "noop"
    assert runtime.sandbox_enabled() is True
    monkeypatch.setattr(settings, "sandbox_backend", "docker")
    assert runtime.get_runner().backend == "docker"
    monkeypatch.setattr(settings, "sandbox_backend", "off")
    assert runtime.sandbox_enabled() is False


def test_spec_locked_down_by_default():
    spec = spec_for_tool({"input_schema_json": {}})
    assert spec.network_mode == "none" and spec.filesystem_mode == "read_only"
    spec2 = spec_for_tool({"input_schema_json": {"constraints": {"allow_hosts": ["localhost"]}}})
    assert spec2.network_mode == "bridge" and spec2.allow_hosts == ["localhost"]


async def test_docker_runner_unavailable_without_extra(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "docker":
            raise ImportError("no docker")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(runtime.SandboxUnavailable):
        await runtime.DockerSandboxRunner().run(SandboxSpec(container_image="x"), payload={})
