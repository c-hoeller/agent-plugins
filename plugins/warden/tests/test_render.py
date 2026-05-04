from __future__ import annotations

import json
from pathlib import Path

from lib import warden_lib


def test_render_index_lists_each_tenet(make_tenet, tenets_dir: Path):
    make_tenet(id="ET-0001", slug="a", title="First", tags=["testing", "oop"])
    make_tenet(id="ET-0002", slug="b", title="Second", tier=2, severity="low")
    tenets = warden_lib.load_all(tenets_dir)
    out = warden_lib.render_index(tenets)
    assert "ET-0001" in out
    assert "ET-0002" in out
    assert "tags: [testing, oop]" in out
    assert "tags: []" in out  # second tenet has empty tags


def test_render_index_is_sorted_by_id(make_tenet, tenets_dir: Path):
    make_tenet(id="ET-0002", slug="b", title="Second")
    make_tenet(id="ET-0001", slug="a", title="First")
    tenets = warden_lib.load_all(tenets_dir)
    out = warden_lib.render_index(tenets)
    pos_first = out.index("ET-0001")
    pos_second = out.index("ET-0002")
    assert pos_first < pos_second


def test_render_charter_lists_tier1_tenets_only_in_tier1_section(make_tenet, tenets_dir: Path):
    make_tenet(id="ET-0001", slug="a", tier=1, title="Tier1 tenet")
    make_tenet(id="ET-0002", slug="b", tier=2, title="Tier2 tenet")
    tenets = warden_lib.load_all(tenets_dir)
    out = warden_lib.render_charter(tenets)

    tier1_section = out.split("## Tier 1")[1].split("## Tier 2")[0]
    assert "ET-0001" in tier1_section
    assert "Tier1 tenet" in tier1_section
    assert "ET-0002" not in tier1_section
    # Tier 2 is mentioned but only by count, not by individual tenets — the
    # charter delegates Tier 2 to the auto-loaded skills + lookup-tenet.
    assert "Tier 2" in out


def test_render_charter_references_full_skill_names(make_tenet, tenets_dir: Path):
    # Charter must point at the actual skill directory name so a user can
    # `cat skills/<name>/SKILL.md` directly without guessing.
    make_tenet(id="ET-0001", slug="my-tenet-here", tier=1)
    tenets = warden_lib.load_all(tenets_dir)
    out = warden_lib.render_charter(tenets)
    assert "skill `et-0001-my-tenet-here`" in out


def test_render_charter_includes_protocol_block(make_tenet, tenets_dir: Path):
    make_tenet(id="ET-0001", slug="a", tier=1)
    tenets = warden_lib.load_all(tenets_dir)
    out = warden_lib.render_charter(tenets)
    assert "## Protocol" in out
    assert "lookup-tenet" in out
    assert "cite the tenet id" in out.lower()


def test_render_charter_size_stays_small_for_25_tenets(make_tenet, tenets_dir: Path):
    # Architectural property: the always-on charter must fit comfortably
    # under Claude Code's 10_000-character SessionStart additionalContext
    # limit even with a large catalog. This test asserts the headline-only
    # design holds at scale.
    for i in range(1, 26):
        make_tenet(id=f"ET-{i:04d}", slug=f"slug-{i}", tier=1)
    tenets = warden_lib.load_all(tenets_dir)
    out = warden_lib.render_charter(tenets)
    assert len(out) < 5_000, f"charter unexpectedly large: {len(out)} chars"


def test_render_skill_for_tenet_has_minimal_frontmatter(make_tenet, tenets_dir: Path):
    make_tenet(
        id="ET-0001",
        slug="my-tenet",
        title="My tenet",
        triggers=["touching auth code", "writing a login flow"],
    )
    tenets = warden_lib.load_all(tenets_dir)
    skill_name, content = warden_lib.render_skill_for_tenet(tenets[0])

    assert skill_name == "et-0001-my-tenet"
    assert content.startswith("---\n")
    assert f"name: {skill_name}" in content
    # `description` MUST start with "Use when ..." — that is what the Claude
    # Code Skill tool keys off for auto-invocation. Don't relax this test
    # without re-validating that auto-load still works.
    assert "description: Use when touching auth code; writing a login flow." in content
    # Tenet ID and title must NOT appear in the description — they belong in
    # the skill body. Workflow/identity material in the description risks
    # Claude treating it as a shortcut and skipping the body.
    assert "Tenet ET-0001" not in content.split("---", 2)[1]
    assert "My tenet." not in content.split("---", 2)[1]


def test_render_skill_for_tenet_body_contains_all_required_sections(make_tenet, tenets_dir: Path):
    make_tenet(id="ET-0001", slug="a")
    tenets = warden_lib.load_all(tenets_dir)
    _, content = warden_lib.render_skill_for_tenet(tenets[0])
    for section in warden_lib.REQUIRED_SECTIONS:
        assert f"## {section}" in content


def test_render_skill_emits_generated_marker(make_tenet, tenets_dir: Path):
    # The marker must point at the source path so a human inspecting the
    # generated skill can find the file to edit, and must mention the
    # build command so they know how to regenerate after editing.
    make_tenet(id="ET-0001", slug="my-tenet")
    tenets = warden_lib.load_all(tenets_dir)
    _, content = warden_lib.render_skill_for_tenet(tenets[0])
    body = content.split("---", 2)[2]
    first_body_line = next(line for line in body.splitlines() if line.strip())
    assert first_body_line.startswith("<!--")
    assert "generated from tenets/ET-0001-my-tenet.md" in first_body_line
    assert "uv run poe build" in first_body_line
    assert "do not edit by hand" in first_body_line


def test_render_skill_description_truncates_at_hard_cap(make_tenet, tenets_dir: Path):
    long_trigger = "x" * 195  # under per-trigger 200 cap, but enough to bust the total
    make_tenet(triggers=[long_trigger] * 10)
    tenets = warden_lib.load_all(tenets_dir)
    _, content = warden_lib.render_skill_for_tenet(tenets[0])
    description_line = next(
        line for line in content.splitlines() if line.startswith("description: ")
    )
    description = description_line[len("description: ") :]
    assert len(description) <= warden_lib.SKILL_DESCRIPTION_MAX_CHARS


def test_unscoped_description_usage_excludes_paths_scoped_tenets(make_tenet, tenets_dir: Path):
    # `paths:`-scoped tenets are gated by file-glob and don't compete in the
    # global description-match pool, so they must not count toward the
    # unscoped budget.
    make_tenet(id="ET-0001", slug="unscoped", triggers=["doing the unscoped thing"])
    make_tenet(
        id="ET-0002",
        slug="scoped",
        triggers=["doing the scoped thing in TS"],
        applies_to={"language": "TypeScript"},
    )
    # The make_tenet fixture doesn't expose `paths` directly; inject it.
    scoped_path = tenets_dir / "ET-0002-scoped.md"
    scoped_path.write_text(
        scoped_path.read_text(encoding="utf-8").replace(
            "triggers:", 'paths:\n  - "**/*.ts"\ntriggers:', 1
        ),
        encoding="utf-8",
    )
    tenets = warden_lib.load_all(tenets_dir)
    total, breakdown = warden_lib.unscoped_description_usage(tenets)
    ids = [tid for tid, _ in breakdown]
    assert ids == ["ET-0001"], f"only ET-0001 should be unscoped, got {ids}"
    assert total == len(warden_lib._build_skill_description(tenets[0]))


def test_real_catalog_unscoped_description_usage_under_budget():
    """Drift detector for the live catalog.

    Sums the descriptions of every committed tenet without `paths:` and
    fails if their total exceeds the budget. Failure mode: a future tenet
    addition (or a trigger-list expansion) silently eats into the global
    description-match budget; this test surfaces it before the next push.

    Fix when this fails: scope the largest contributors via `paths:`, or
    shorten their trigger lists. Do NOT raise the budget — the cap exists
    so non-Warden skills keep room in the shared pool.
    """
    plugin_root = Path(__file__).resolve().parent.parent
    tenets = warden_lib.load_all(plugin_root / "tenets")
    total, breakdown = warden_lib.unscoped_description_usage(tenets)
    if total > warden_lib.UNSCOPED_DESCRIPTION_BUDGET_CHARS:
        top = "\n".join(f"    {tid}: {chars} chars" for tid, chars in breakdown[:5])
        raise AssertionError(
            f"unscoped tenet description total {total} chars exceeds budget "
            f"{warden_lib.UNSCOPED_DESCRIPTION_BUDGET_CHARS}.\n"
            f"  top contributors:\n{top}\n"
            f"  fix: scope these via `paths:` or shorten their triggers."
        )


def test_hook_payload_is_valid_session_start_json(make_tenet, tenets_dir: Path):
    make_tenet(id="ET-0001", slug="a", tier=1, title="Tier1 tenet")
    tenets = warden_lib.load_all(tenets_dir)
    rendered = warden_lib.render_charter(tenets)
    payload = warden_lib.render_tier1_hook_payload(rendered)

    parsed = json.loads(payload)
    assert parsed["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert parsed["hookSpecificOutput"]["additionalContext"] == rendered
    assert "Tier1 tenet" in parsed["hookSpecificOutput"]["additionalContext"]


def test_hook_payload_escapes_special_characters(make_tenet, tenets_dir: Path):
    # Quotes, backslashes and newlines in tenet content must survive a JSON
    # round-trip — this is exactly the case the shell hook cannot handle, and
    # the reason the payload is pre-built at build time. We exercise the
    # round-trip via an arbitrary string rather than a tenet field, since the
    # charter no longer embeds tenet body prose.
    raw = 'Use "double quotes" and a \\backslash and\nnewlines.'
    payload = warden_lib.render_tier1_hook_payload(raw)
    parsed = json.loads(payload)
    assert parsed["hookSpecificOutput"]["additionalContext"] == raw
