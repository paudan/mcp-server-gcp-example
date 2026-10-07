import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate_toolspec as gen  # noqa: E402


def test_toolspec_is_under_budget():
    assert len(gen.build().encode()) <= gen.LIMIT


def test_prose_is_stripped_but_property_named_title_survives():
    schema = {"title": "X", "description": "d", "$defs": {"A": {}},
              "properties": {"title": {"type": "string", "description": "the title"},
                             "entry": {"$ref": "#/$defs/A"}}}
    assert gen.without_prose(schema) == {
        "properties": {"title": {"type": "string"}, "entry": {"type": "object"}}}


def test_annotations_survive():
    tools = json.loads(gen.build())["tools"]
    assert all("annotations" in t for t in tools)


def test_over_budget_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(gen, "LIMIT", 10)
    assert gen.main(str(tmp_path / "t.json")) == 1
