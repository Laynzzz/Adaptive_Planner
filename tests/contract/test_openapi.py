"""The committed client contract cannot silently lag the application routes."""

import json
from pathlib import Path

from planner.app import create_app


def test_committed_openapi_matches_application():
    path = Path(__file__).resolve().parents[2] / "apps/web/src/api/openapi.json"
    assert json.loads(path.read_text(encoding="utf-8")) == create_app().openapi()
