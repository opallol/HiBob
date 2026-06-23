"""Tool Gateway (ADR 0004/0005) - STUB. Lands in Phase 4 with the Policy Engine + Sandbox.

Phase 1 has no tools. When tools arrive, this package owns the registry, the gateway
(validate -> provenance check -> policy decision -> approval -> execute -> audit), and
adapters. A registered Hermes agent-backend (Phase 5) is one tool_type here, never an
import of Core.
"""
