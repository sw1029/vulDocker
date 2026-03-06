"""Search tool adapters consumed by the Researcher agent."""

from .providers import SearchExecution, SearchProvider, SearchRequest, SearchResult
from .web_search import WebSearchTool

__all__ = [
    "SearchExecution",
    "SearchProvider",
    "SearchRequest",
    "SearchResult",
    "WebSearchTool",
]
