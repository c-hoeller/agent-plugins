from __future__ import annotations

from pathlib import Path

from lib import warden_lib


def _validate(tenets_dir: Path) -> list[warden_lib.WardenError]:
    return warden_lib.validate(warden_lib.load_all(tenets_dir))


def test_valid_tenet_has_no_errors(valid_tenet: Path, tenets_dir: Path):
    assert _validate(tenets_dir) == []


def test_id_must_match_filename(make_tenet, tenets_dir: Path):
    p = make_tenet(id="ET-0001", slug="alpha")
    # Mutate the frontmatter id so it no longer matches the filename prefix.
    p.write_text(p.read_text().replace("id: ET-0001", "id: ET-0099"), encoding="utf-8")
    errors = _validate(tenets_dir)
    assert any("filename prefix" in e.message for e in errors)


def test_duplicate_ids_are_flagged(make_tenet, tenets_dir: Path):
    make_tenet(id="ET-0001", slug="first")
    make_tenet(id="ET-0001", slug="second")
    errors = _validate(tenets_dir)
    assert any("duplicate id" in e.message for e in errors)


def test_invalid_type_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(type="rule")
    errors = _validate(tenets_dir)
    assert any("type" in e.message for e in errors)


def test_invalid_tier_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(tier=3)
    errors = _validate(tenets_dir)
    assert any("tier" in e.message for e in errors)


def test_since_must_be_non_empty(make_tenet, tenets_dir: Path):
    make_tenet(since="")
    errors = _validate(tenets_dir)
    assert any("since" in e.message for e in errors)


def test_since_must_be_semver(make_tenet, tenets_dir: Path):
    # `since` is enforced as MAJOR.MINOR.PATCH so it stays comparable with the
    # plugin's pyproject.toml version. Reject pre-release suffixes, two-segment
    # forms, and free text.
    for bad in ("0.1", "0.1.0-beta", "1.0.0+meta", "v0.1.0", "next"):
        make_tenet(id="ET-9999", slug="bad-since", since=bad)
        errors = _validate(tenets_dir)
        assert any("MAJOR.MINOR.PATCH" in e.message for e in errors), (
            f"expected SemVer error for since={bad!r}, got {[e.message for e in errors]}"
        )
        # Reset so the next iteration's tenet write replaces this one.
        (tenets_dir / "ET-9999-bad-since.md").unlink()


def test_since_accepts_valid_semver(make_tenet, tenets_dir: Path):
    for good in ("0.1.0", "1.0.0", "10.20.30"):
        make_tenet(id="ET-9999", slug="good-since", since=good)
        assert _validate(tenets_dir) == [], f"unexpected errors for since={good!r}"
        (tenets_dir / "ET-9999-good-since.md").unlink()


def test_applies_to_mapping_form_is_accepted(make_tenet, tenets_dir: Path):
    make_tenet(applies_to={"language": "TypeScript"})
    assert _validate(tenets_dir) == []


def test_applies_to_arbitrary_string_is_accepted(make_tenet, tenets_dir: Path):
    # applies-to is documentation; the actual auto-load gate is `paths:`.
    # Authors are free to pick any concise label.
    make_tenet(applies_to="language: typescript")
    assert _validate(tenets_dir) == []


def test_applies_to_empty_string_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(applies_to="")
    errors = _validate(tenets_dir)
    assert any("applies-to" in e.message for e in errors)


def test_related_unresolved_id_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(id="ET-0001", related=["ET-0099"])
    errors = _validate(tenets_dir)
    assert any("related reference" in e.message for e in errors)


def test_related_self_reference_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(id="ET-0001", related=["ET-0001"])
    errors = _validate(tenets_dir)
    assert any("references self" in e.message for e in errors)


def test_missing_triggers_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(triggers=[])
    errors = _validate(tenets_dir)
    assert any("triggers" in e.message for e in errors)


def test_empty_trigger_entry_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(triggers=["valid trigger", "   "])
    errors = _validate(tenets_dir)
    assert any("empty entries" in e.message for e in errors)


def test_overly_long_trigger_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(triggers=["x" * 250])
    errors = _validate(tenets_dir)
    assert any("trigger entry length" in e.message for e in errors)


def test_tier2_without_paths_is_flagged(make_tenet, tenets_dir: Path):
    # Tier 2 = language-/framework-specific. Without `paths:` the skill lands
    # in the global description-match pool, which doesn't scale.
    p = make_tenet(tier=2, applies_to={"language": "TypeScript"})
    errors = _validate(tenets_dir)
    assert any("tier 2 tenets must set `paths:`" in e.message for e in errors), (
        f"expected tier-2-without-paths error for {p.name}, got {[e.message for e in errors]}"
    )


def test_tier2_with_paths_is_valid(make_tenet, tenets_dir: Path):
    p = make_tenet(tier=2, applies_to={"language": "TypeScript"})
    p.write_text(
        p.read_text(encoding="utf-8").replace("tier: 2", 'tier: 2\npaths:\n  - "**/*.ts"', 1),
        encoding="utf-8",
    )
    assert _validate(tenets_dir) == []


def test_tier1_without_paths_is_valid(make_tenet, tenets_dir: Path):
    # Tier 1 = universal. Language-agnostic tenets stay eligible everywhere.
    make_tenet(tier=1)
    assert _validate(tenets_dir) == []


def test_missing_section_is_flagged(make_tenet, tenets_dir: Path):
    p = make_tenet()
    text = p.read_text()
    text = text.replace("## Exceptions\n\nNone.\n", "")
    p.write_text(text, encoding="utf-8")
    errors = _validate(tenets_dir)
    assert any("missing required section" in e.message for e in errors)
