from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import get_settings
from app.services.source_fusion_service import SourceFusionService


def test_the_odds_api_is_not_registered_runtime_source() -> None:
    registry = SourceFusionService(get_settings()).registry()
    keys = {source.key for source in registry}
    assert "the_odds_api" not in keys
