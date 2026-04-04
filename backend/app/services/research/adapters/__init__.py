"""Research tool adapter implementations.

Concrete adapters for HTTP-based research tools (CourtListener, Google Scholar, stubs)
and MCP-based tools (folio-mcp).
"""

from app.services.research.adapters.clio_library import ClioLibraryAdapter
from app.services.research.adapters.courtlistener import CourtListenerAdapter
from app.services.research.adapters.descrybe import DescrybeAdapter
from app.services.research.adapters.google_scholar import GoogleScholarAdapter
from app.services.research.adapters.http_adapter import HTTPAdapter, NotConfiguredError
from app.services.research.adapters.mcp_adapter import MCPAdapter
from app.services.research.adapters.midpage import MidpageAdapter
from app.services.research.adapters.westlaw import WestlawAdapter

__all__ = [
    "ClioLibraryAdapter",
    "CourtListenerAdapter",
    "DescrybeAdapter",
    "GoogleScholarAdapter",
    "HTTPAdapter",
    "MCPAdapter",
    "MidpageAdapter",
    "NotConfiguredError",
    "WestlawAdapter",
]
