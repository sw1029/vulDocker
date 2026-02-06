"""Static signature helpers for candidate pre-screening."""

from .registry import analyze_static_signals, register_static_analyzer
from .sqli import analyze_sql_injection_signals

# Default analyzers (can be extended by importing modules that register more).
register_static_analyzer(["cwe-89", "sqli"], analyze_sql_injection_signals)

__all__ = ["analyze_static_signals", "register_static_analyzer", "analyze_sql_injection_signals"]
