"""Source adapter package for the World Cup prediction platform.

These adapters are the new modular ingestion/health-check boundary. They are not wired
into the legacy FixtureIngestionService yet; integration should be done after tests pass.
"""

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult

__all__ = [
    "BaseSourceAdapter",
    "SourceAdapterResult",
]
