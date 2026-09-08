"""Conditions: weather sampled along the route by hour, wind on exposed segments, fire danger, SLF presence."""

from bergbot.core.conditions.weather import assess_conditions

__all__ = ["assess_conditions"]
