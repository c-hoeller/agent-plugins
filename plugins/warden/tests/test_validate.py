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


def test_invalid_severity_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(severity="huge")
    errors = _validate(tenets_dir)
    assert any("severity" in e.message for e in errors)


def test_invalid_type_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(type="rule")
    errors = _validate(tenets_dir)
    assert any("type" in e.message for e in errors)


def test_invalid_tier_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(tier=3)
    errors = _validate(tenets_dir)
    assert any("tier" in e.message for e in errors)


def test_invalid_semver_in_since_is_flagged(make_tenet, tenets_dir: Path):
    make_tenet(since="oneish")
    errors = _validate(tenets_dir)
    assert any("SemVer" in e.message for e in errors)


def test_applies_to_mapping_form_valid(make_tenet, tenets_dir: Path):
    make_tenet(applies_to={"language": "TypeScript"})
    assert _validate(tenets_dir) == []


def test_applies_to_string_other_than_any_is_flagged(make_tenet, tenets_dir: Path):
    # Only "any" is a valid string form; "language: TS" colon-strings used to
    # be accepted but were dropped — mapping form is the canonical alternative.
    make_tenet(applies_to="language: typescript")
    errors = _validate(tenets_dir)
    assert any("applies-to" in e.message for e in errors)


def test_applies_to_invalid_key(make_tenet, tenets_dir: Path):
    make_tenet(applies_to={"weird": "ts"})
    errors = _validate(tenets_dir)
    assert any("applies-to" in e.message for e in errors)


def test_applies_to_list_form_is_flagged(make_tenet, tenets_dir: Path):
    # List form is intentionally no longer supported — multi-language tenets
    # should scope via `paths:` globs instead.
    make_tenet(applies_to=[{"language": "TypeScript"}, {"language": "JavaScript"}])
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
