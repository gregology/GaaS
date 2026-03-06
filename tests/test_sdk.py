"""Tests for gaas_sdk package imports and runtime registration."""

import pytest

from gaas_sdk.models import (
    YoloAction,
    AutomationConfig,
)
from gaas_sdk.manifest import (
    ServiceManifest,
)
from gaas_sdk.actions import is_service_action
from gaas_sdk import runtime


class TestSDKImports:
    """Verify all public API is importable from gaas_sdk."""

    def test_top_level_imports(self):
        import gaas_sdk
        assert hasattr(gaas_sdk, "YoloAction")
        assert hasattr(gaas_sdk, "AutomationConfig")
        assert hasattr(gaas_sdk, "NoteStore")
        assert hasattr(gaas_sdk, "MISSING")
        assert hasattr(gaas_sdk, "build_schema")
        assert hasattr(gaas_sdk, "IntegrationManifest")
        assert hasattr(gaas_sdk, "ServiceManifest")
        assert hasattr(gaas_sdk, "is_service_action")
        assert hasattr(gaas_sdk, "runtime")

    def test_models_are_same_as_app(self):
        from app.config import YoloAction as AppYoloAction
        assert YoloAction is AppYoloAction

        from app.config import AutomationConfig as AppAutomationConfig
        assert AutomationConfig is AppAutomationConfig


class TestServiceManifest:
    def test_defaults(self):
        svc = ServiceManifest(
            name="Test",
            description="A test service",
            handler=".services.test.handle",
        )
        assert svc.reversible is False
        assert svc.input_schema == {}

    def test_reversible(self):
        svc = ServiceManifest(
            name="Search",
            description="Web search",
            handler=".services.search.handle",
            reversible=True,
        )
        assert svc.reversible is True


class TestIsServiceAction:
    def test_service_dict(self):
        assert is_service_action({"service": {"call": "gemini.default.web_research"}}) is True

    def test_script_dict(self):
        assert is_service_action({"script": {"name": "test"}}) is False

    def test_string_action(self):
        assert is_service_action("archive") is False

    def test_none(self):
        assert is_service_action(None) is False


class TestRuntimeRegistration:
    def test_runtime_is_registered(self):
        """After conftest registers runtime, functions should work."""
        assert runtime._enqueue is not None
        assert runtime._get_integration is not None

    def test_runtime_not_registered_error(self):
        """Calling before register raises RuntimeNotRegistered."""
        import gaas_sdk.runtime as rt
        old = rt._enqueue
        try:
            rt._enqueue = None
            with pytest.raises(runtime.RuntimeNotRegistered):
                rt.enqueue({"type": "test"})
        finally:
            rt._enqueue = old
