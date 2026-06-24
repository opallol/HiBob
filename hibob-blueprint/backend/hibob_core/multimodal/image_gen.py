"""Image generation (Phase 9, ADR 0015). Policy-gated, never auto-published.

Runs as the `image_generate` tool through the Tool Gateway, so it inherits policy/approval/audit.
Privacy containment: private/secret generation must stay local (never a cloud provider). The real
local model is a lazy seam; absent, a draft stub artifact is returned so the governed flow works.
"""

from __future__ import annotations

import hashlib

from hibob_core.config import settings


class OutputError(Exception):
    pass


class OutputUnavailable(Exception):
    """The local generation provider isn't installed (lazy seam)."""


def _local_provider():
    # Seam: a real impl loads settings.image_model. Kept optional so the gateway flow is testable.
    raise OutputUnavailable("local image-gen provider not installed (seam)")


def generate(prompt: str, *, privacy_tier: str = "internal", model_preference: str = "local") -> dict:
    """Return a draft image artifact. Never auto-published (ADR 0015)."""
    wants_cloud = model_preference == "cloud"
    if privacy_tier in ("private", "secret") and wants_cloud:
        raise OutputError(
            f"privacy_tier='{privacy_tier}' image generation cannot use a cloud provider (ADR 0015)"
        )
    if wants_cloud and not settings.allow_cloud_image_gen:
        raise OutputError("cloud image generation is disabled (allow_cloud_image_gen=false)")

    ref = "img-" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    try:
        _local_provider()  # real generation would happen here
    except OutputUnavailable:
        # Draft stub: the governed path (tool -> policy -> approval -> audit) still holds.
        return {"type": "image", "media_type": "image/png", "ref": ref, "published": False,
                "provider": "stub", "prompt": prompt}
    return {"type": "image", "media_type": "image/png", "ref": ref, "published": False,
            "provider": "local"}
