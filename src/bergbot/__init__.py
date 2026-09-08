"""Bergbot — open-source, local-first mountain-planning agent for Switzerland.

Layers (see docs/bergbot_product_spec.md §9):
- sources/      Layer 0: source adapters (contract-tested, freshness-tracked)
- core/         Layer 1: deterministic core (geometry, terrain, conditions, logistics, scoring, evidence, reporting)
- conversation/ Layer 2: intent, constraints, register, suggestions, replanning, message rendering
- adapters/     Layer 3: thin surface adapters (Telegram, CLI, channel passthrough); the Claude plugin lives in plugins/
- agent/        standalone orchestration using the Anthropic API (CLI chat, Telegram)
"""

__version__ = "0.1.0"
