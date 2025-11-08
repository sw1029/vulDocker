"""Static signature helpers for candidate pre-screening."""

from .sqli import analyze_sql_injection_signals

__all__ = ["analyze_sql_injection_signals"]
