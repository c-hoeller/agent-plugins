from __future__ import annotations

from pathlib import Path

import pytest
from lib import warden_lib


def test_split_frontmatter_extracts_yaml_and_body():
    text = "---\nid: ET-0001\n---\n\n## Rule\n\nDo it.\n"
    fm, body = warden_lib.split_frontmatter(text)
    assert fm.strip() == "id: ET-0001"
    assert body.lstrip().startswith("## Rule")


def test_split_frontmatter_missing_opener_raises():
    with pytest.raises(warden_lib.WardenError):
        warden_lib.split_frontmatter("no frontmatter here")


def test_split_frontmatter_missing_closer_raises():
    with pytest.raises(warden_lib.WardenError):
        warden_lib.split_frontmatter("---\nid: x\nstill no closer\n")


def test_parse_sections_handles_required_sections():
    body = (
        "## Rule\n\nText A.\n\n"
        "## Why\n\nText B.\n\n"
        "## Bad Example\n\n```ts\nbad\n```\n\n"
        "## Good Example\n\n```ts\ngood\n```\n\n"
        "## Exceptions\n\n- one\n- two\n"
    )
    sections = warden_lib.parse_sections(body)
    assert set(sections) == {"Rule", "Why", "Bad Example", "Good Example", "Exceptions"}
    assert sections["Rule"] == "Text A."
    assert "bad" in sections["Bad Example"]
    assert "- one" in sections["Exceptions"]


def test_parse_sections_ignores_headings_inside_code_fences():
    body = "## Rule\n\n```md\n## Not A Heading\n```\n## Why\n\nReal heading.\n"
    sections = warden_lib.parse_sections(body)
    assert "Not A Heading" not in sections
    assert sections["Why"] == "Real heading."


def test_load_tenet_reads_full_record(valid_tenet: Path):
    t = warden_lib.load_tenet(valid_tenet)
    assert t.id == "ET-0001"
    assert t.title == "Example tenet"
    assert t.type == "best-practice"
    assert t.severity == "high"
    assert t.tier == 1
    assert t.applies_to == "any"
    assert t.since == "0.1.0"
    assert "Rule" in t.sections
    assert "Exceptions" in t.sections


def test_load_all_returns_sorted_list(make_tenet, tenets_dir: Path):
    make_tenet(id="ET-0002", slug="b")
    make_tenet(id="ET-0001", slug="a")
    tenets = warden_lib.load_all(tenets_dir)
    assert [t.id for t in tenets] == ["ET-0001", "ET-0002"]
