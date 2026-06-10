"""Unit tests for API HTTP service layer.

Tests real service business logic with mocked dependencies:
- persistence_mgr (database operations)
- model_mgr (runtime model management)
- platform_mgr (platform management)
- plugin_connector (plugin runtime)
- adjacent services (cross-service calls)

Does NOT:
- Start real Quart server
- Access real database
- Call real provider/platform/network

Uses tests.factories.FakeApp as base mock application.
"""