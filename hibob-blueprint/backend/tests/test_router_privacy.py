"""Privacy routing is the non-negotiable: secret/private never reaches a cloud model."""

import pytest

from hibob_core.models.anthropic_adapter import AnthropicAdapter
from hibob_core.models.router import CloudUnavailable, ModelRouter, PrivacyViolation


def test_secret_tier_cloud_preference_is_rejected():
    with pytest.raises(PrivacyViolation):
        ModelRouter().route(privacy_tier="secret", model_preference="cloud")


def test_private_tier_cloud_preference_is_rejected():
    with pytest.raises(PrivacyViolation):
        ModelRouter().route(privacy_tier="private", model_preference="cloud")


def test_secret_tier_auto_routes_local():
    adapter = ModelRouter().route(privacy_tier="secret", model_preference="auto")
    assert adapter.is_cloud is False


def test_internal_cloud_routes_cloud():
    # Inject a configured (keyed) cloud adapter so routing can succeed.
    router = ModelRouter(anthropic=AnthropicAdapter(api_key="test-key"))
    adapter = router.route(privacy_tier="internal", model_preference="cloud")
    assert adapter.is_cloud is True


def test_auto_defaults_to_local():
    adapter = ModelRouter().route(privacy_tier="internal", model_preference="auto")
    assert adapter.is_cloud is False


def test_cloud_without_api_key_raises():
    # AnthropicAdapter with no key reports unavailable -> router rejects cloud cleanly.
    router = ModelRouter(anthropic=AnthropicAdapter(api_key=None))
    with pytest.raises(CloudUnavailable):
        router.route(privacy_tier="internal", model_preference="cloud")
