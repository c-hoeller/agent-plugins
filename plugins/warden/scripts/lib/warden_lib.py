"""Parsing, validation, and rendering for Warden Engineering Tenets.

This module is the single source of truth for everything build.py and
validate.py do. It has no dependencies beyond PyYAML.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ID_RE = re.compile(r"^ET-(\d{4})$")
FILENAME_RE = re.compile(r"^(ET-\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")

TYPES = ("best-practice", "anti-pattern")
TIERS = (1, 2)

REQUIRED_SECTIONS: tuple[str, ...] = (
    "Rule",
    "Why",
    "Bad Example",
    "Good Example",
    "Exceptions",
)
OPTIONAL_SECTIONS: tuple[str, ...] = ("Rationalizations",)
KNOWN_SECTIONS: tuple[str, ...] = REQUIRED_SECTIONS + OPTIONAL_SECTIONS
REQUIRED_FRONTMATTER: tuple[str, ...] = (
    "id",
    "title",
    "type",
    "tier",
    "applies-to",
    "since",
    "triggers",
)

# Skill `description` + `when_to_use` text combined is capped at 1,536 chars
# in the global skill listing per Claude Code Skills docs. We keep a margin
# under that for safety and to leave room in the shared description budget
# when many tenets are active. Raise cautiously — every extra char per skill
# multiplies across the whole catalog.
SKILL_LISTING_TEXT_MAX_CHARS = 1400

# Combined budget for the descriptions of *all* unscoped tenet skills (i.e.
# tenets without `paths:`, which therefore stay in the global match pool
# regardless of the active file). Claude Code's auto-load mechanism
# considers all unscoped skill descriptions on every prompt; if their sum
# grows too large, the description budget for non-Warden skills shrinks
# and auto-load reliability drops. The budget is conservative so that the
# catalog can grow to ~25-30 unscoped tenets before the test fails — at
# which point the fix is to scope older tenets via `paths:`, not to raise
# this limit. Tier 2 tenets MUST set `paths:` and so do not count here.
UNSCOPED_DESCRIPTION_BUDGET_CHARS = 7000


class WardenError(Exception):
    """Raised by parsers; aggregated by validate()."""

    def __init__(self, path: Path | None, message: str) -> None:
        super().__init__(message)
        self.path = path
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - exercised via __repr__
        prefix = f"{self.path}: " if self.path else ""
        return f"{prefix}{self.message}"


@dataclass
class Tenet:
    path: Path
    id: str
    title: str
    type: str
    tier: int
    applies_to: Any
    since: str
    triggers: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split a markdown file into (frontmatter_yaml, body).

    Raises WardenError if the file does not start with a YAML frontmatter
    block delimited by '---' lines.
    """
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        raise WardenError(None, "missing leading '---' frontmatter delimiter")
    rest = text.split("\n", 1)[1]
    end = rest.find("\n---")
    if end == -1:
        raise WardenError(None, "missing closing '---' frontmatter delimiter")
    fm = rest[:end]
    body = rest[end + len("\n---") :].lstrip("\r\n")
    return fm, body


def parse_sections(body: str) -> dict[str, str]:
    """Parse a tenet body into a {section_name: content} dict.

    Headings are detected only outside fenced code blocks. Section content
    excludes the heading line; trailing whitespace is stripped.
    """
    lines = body.splitlines()
    in_fence = False
    fence_marker: str | None = None
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if current is not None:
            sections[current] = "\n".join(buf).strip()

    for raw in lines:
        stripped = raw.lstrip()
        if stripped.startswith("```") or stripped.startswith("````"):
            tick_count = len(stripped) - len(stripped.lstrip("`"))
            marker = "`" * tick_count
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = None
            buf.append(raw)
            continue

        if not in_fence:
            m = re.match(r"^##\s+(\S.*)\s*$", raw)
            if m:
                flush()
                current = m.group(1).strip()
                buf = []
                continue

        if current is not None:
            buf.append(raw)

    flush()
    return sections


def load_tenet(path: Path) -> Tenet:
    """Load a single tenet file. Raises WardenError on parse problems."""
    text = path.read_text(encoding="utf-8")
    try:
        fm_text, body = split_frontmatter(text)
    except WardenError as e:
        raise WardenError(path, e.message) from e

    try:
        meta = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        raise WardenError(path, f"invalid YAML frontmatter: {e}") from e

    if not isinstance(meta, dict):
        raise WardenError(path, "frontmatter must be a YAML mapping")

    sections = parse_sections(body)

    return Tenet(
        path=path,
        id=str(meta.get("id", "")),
        title=str(meta.get("title", "")),
        type=str(meta.get("type", "")),
        tier=int(meta["tier"]) if isinstance(meta.get("tier"), int) else -1,
        applies_to=meta.get("applies-to"),
        since=str(meta.get("since", "")),
        triggers=[str(t) for t in (meta.get("triggers") or [])],
        paths=[str(p) for p in (meta.get("paths") or [])],
        tags=list(meta.get("tags") or []),
        related=list(meta.get("related") or []),
        sections=sections,
    )


def load_all(tenets_dir: Path) -> list[Tenet]:
    """Load every ET-*.md in tenets_dir, sorted by id."""
    files = sorted(tenets_dir.glob("ET-*.md"))
    return [load_tenet(p) for p in files]


def validate(tenets: Iterable[Tenet]) -> list[WardenError]:
    """Run all spec-defined checks. Returns a list of WardenError; empty == OK."""
    errors: list[WardenError] = []
    seen_ids: dict[str, Path] = {}
    all_ids: set[str] = set()

    tenet_list = list(tenets)
    for t in tenet_list:
        all_ids.add(t.id)

    for t in tenet_list:
        # Required frontmatter presence is implicitly checked by load_tenet's
        # use of meta.get(); empty / -1 values surface here.
        if not ID_RE.match(t.id):
            errors.append(WardenError(t.path, f"id {t.id!r} does not match ET-NNNN"))
        # Filename matches id
        m = FILENAME_RE.match(t.path.name)
        if not m:
            errors.append(
                WardenError(t.path, f"filename {t.path.name!r} does not match ET-NNNN-<slug>.md")
            )
        elif m.group(1) != t.id:
            errors.append(
                WardenError(
                    t.path,
                    f"id {t.id!r} does not match filename prefix {m.group(1)!r}",
                )
            )
        # Uniqueness
        if t.id in seen_ids:
            errors.append(
                WardenError(
                    t.path,
                    f"duplicate id {t.id!r} (first seen at {seen_ids[t.id]})",
                )
            )
        else:
            seen_ids[t.id] = t.path
        # Title
        if not t.title:
            errors.append(WardenError(t.path, "title is missing"))
        elif len(t.title) > 80:
            errors.append(WardenError(t.path, f"title length {len(t.title)} exceeds 80 chars"))
        # Type / tier
        if t.type not in TYPES:
            errors.append(WardenError(t.path, f"type {t.type!r} not in {TYPES}"))
        if t.tier not in TIERS:
            errors.append(WardenError(t.path, f"tier {t.tier!r} not in {TIERS}"))
        # applies-to is a documentation-only tag (intent label). The actual
        # auto-load gate is `paths:`. We only require the field to be present
        # and non-empty; the shape (string or mapping) is left to authors.
        if t.applies_to is None or (isinstance(t.applies_to, str) and not t.applies_to.strip()):
            errors.append(WardenError(t.path, "applies-to must be present and non-empty"))
        # since is documentation. Require non-empty; do not validate as SemVer.
        if not t.since.strip():
            errors.append(WardenError(t.path, "since must be present and non-empty"))
        # triggers — required, non-empty list of short trigger phrases. These
        # become the basis of the generated skill's `description`, which is
        # what Claude Code matches against to auto-load the tenet's skill.
        if not t.triggers:
            errors.append(
                WardenError(
                    t.path,
                    "triggers must be a non-empty list of phrases describing when "
                    "this tenet applies (used to build the auto-loaded skill description)",
                )
            )
        for trig in t.triggers:
            if not trig.strip():
                errors.append(WardenError(t.path, "triggers must not contain empty entries"))
            elif len(trig) > 200:
                errors.append(
                    WardenError(
                        t.path,
                        f"trigger entry length {len(trig)} exceeds 200 chars: {trig[:60]!r}...",
                    )
                )
        # paths — list of glob patterns scoping where the generated skill
        # auto-invokes. Required for Tier 2 (otherwise the tenet would land
        # unscoped in the global description-match pool and crowd it out at
        # scale, see UNSCOPED_DESCRIPTION_BUDGET_CHARS); optional for Tier 1
        # (universal tenets are eligible everywhere).
        if t.tier == 2 and not t.paths:
            errors.append(
                WardenError(
                    t.path,
                    "tier 2 tenets must set `paths:` to scope auto-invocation; "
                    "an unscoped tier 2 tenet competes in the global description "
                    "pool against all other skills and breaks the budget at scale",
                )
            )
        for pat in t.paths:
            if not pat.strip():
                errors.append(WardenError(t.path, "paths must not contain empty entries"))
            elif len(pat) > 200:
                errors.append(
                    WardenError(
                        t.path,
                        f"path glob length {len(pat)} exceeds 200 chars: {pat[:60]!r}...",
                    )
                )
        # related cross-refs
        for rel in t.related:
            if rel == t.id:
                errors.append(WardenError(t.path, f"related references self: {rel}"))
            elif rel not in all_ids:
                errors.append(WardenError(t.path, f"related reference {rel!r} not found"))
        # Required sections present. Section order is documented in the
        # template and obvious to any human reading the file; enforcing it
        # via validation caught nothing real and complicated edits.
        for required in REQUIRED_SECTIONS:
            if required not in t.sections:
                errors.append(WardenError(t.path, f"missing required section: ## {required}"))

    return errors


def render_charter(tenets: Iterable[Tenet], preamble: str) -> str:
    """Generate build/charter.md — the always-on Warden constitution.

    `preamble` is the static charter intro (Protocol + Rationalizations),
    typically read from templates/charter-preamble.md so authors can edit it
    as plain markdown without touching Python. This function appends the
    Tier 1 listing and a Tier 2 count footer, both derived from the live
    tenet catalog.

    Tier 1 tenets that carry `paths:` are visually annotated with `· scoped`
    so a reader on a non-matching codebase understands why the skill may
    never auto-load even though the charter lists the tenet as binding.
    """
    tenet_list = sorted(tenets, key=lambda t: t.id)
    tier1 = [t for t in tenet_list if t.tier == 1]
    tier2 = [t for t in tenet_list if t.tier == 2]

    lines: list[str] = [preamble.rstrip(), ""]

    if tier1:
        lines.append("## Tier 1 — universal, always-relevant")
        lines.append("")
        for t in tier1:
            entry = f"- `{t.id}` — {t.title} → skill `{_skill_name_for(t)}`"
            if t.paths:
                entry += " · scoped"
            lines.append(entry)
        lines.append("")

    if tier2:
        lines.append(
            "## Tier 2 — context-specific (auto-load via triggers, "
            f"or browse via `lookup-tenet`; {len(tier2)} total)"
        )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _skill_name_for(tenet: Tenet) -> str:
    """Generate the skill directory name for a tenet (e.g. et-0001-no-lower-...)."""
    # Filename format is enforced as ET-NNNN-<slug>.md by validation, so the
    # third split chunk is always the slug.
    slug = tenet.path.stem.split("-", 2)[-1]
    return f"et-{tenet.id[3:].lower()}-{slug}"


def _build_skill_description(tenet: Tenet) -> str:
    """Compose a Claude-Code skill `description` from a tenet's title.

    The description names *what* the skill is — the tenet's imperative rule —
    so Claude can recognise the skill's purpose at a glance. The triggering
    situations live in `when_to_use` (see `_build_skill_when_to_use`); keeping
    them separate matches the docs' guidance ("description is what the skill
    does, when_to_use is when to invoke it") and lets Claude weight the two
    fields differently when matching.
    """
    return tenet.title.rstrip(".") + "."


def _build_skill_when_to_use(tenet: Tenet) -> str:
    """Compose a Claude-Code skill `when_to_use` field from a tenet's triggers.

    Format: 'Use when <trigger 1>; <trigger 2>; ....'

    Front-loaded triggers matter because the `description` + `when_to_use`
    text combined is capped at 1,536 chars in the global skill listing; when
    the shared description budget tightens, the first trigger is what
    survives truncation. The hard cap below keeps combined length under
    SKILL_LISTING_TEXT_MAX_CHARS as a safety net.
    """
    triggers = "; ".join(t.strip().rstrip(".") for t in tenet.triggers if t.strip())
    when_to_use = f"Use when {triggers}."
    description_overhead = len(_build_skill_description(tenet)) + len(" ")
    cap = SKILL_LISTING_TEXT_MAX_CHARS - description_overhead
    if len(when_to_use) > cap:
        # Validation also limits each trigger to 200 chars, so reaching this
        # should be rare. The ellipsis signals truncation in the listing.
        when_to_use = when_to_use[: cap - 1].rstrip() + "…"
    return when_to_use


def _skill_listing_text(tenet: Tenet) -> str:
    """Return the combined description + when_to_use text Claude Code lists.

    Mirrors how the skill-listing budget is computed: the two fields are
    concatenated with a separator. Used by `unscoped_description_usage` to
    measure each tenet's contribution to the shared budget.
    """
    return f"{_build_skill_description(tenet)} {_build_skill_when_to_use(tenet)}"


def unscoped_description_usage(tenets: Iterable[Tenet]) -> tuple[int, list[tuple[str, int]]]:
    """Return (total_chars, per_tenet_breakdown) for tenets without `paths:`.

    Only unscoped tenets compete in the global description-match pool on every
    prompt; tenets with `paths:` are gated by file-glob and don't count here.
    Each tenet's contribution is the combined description + when_to_use text,
    matching the cap Claude Code applies in the listing. The breakdown is
    sorted descending so the largest contributors surface first when a budget
    violation is reported.
    """
    breakdown = [(t.id, len(_skill_listing_text(t))) for t in tenets if not t.paths]
    breakdown.sort(key=lambda pair: pair[1], reverse=True)
    return sum(chars for _, chars in breakdown), breakdown


def render_skill_for_tenet(tenet: Tenet) -> tuple[str, str]:
    """Generate (skill_dir_name, SKILL.md content) for one tenet.

    The body mirrors the source tenet (Rule, Why, Bad/Good Examples,
    Exceptions) so the skill, once auto-loaded, contains everything
    Claude needs to apply or invoke an Exception. Frontmatter is the
    minimal Claude Code skill schema: `name` + `description`.
    """
    skill_name = _skill_name_for(tenet)
    description = _build_skill_description(tenet)
    when_to_use = _build_skill_when_to_use(tenet)

    # `user-invocable: false` keeps generated tenet skills out of the `/` menu.
    # They are background knowledge that auto-loads via triggers / paths; no
    # user types `/warden:et-0001-…` directly. Hides them from autocomplete
    # without affecting Claude's ability to invoke them.
    fm: list[str] = [
        "---",
        f"name: {skill_name}",
        f"description: {description}",
        f"when_to_use: {when_to_use}",
        "user-invocable: false",
    ]
    if tenet.paths:
        # Emitted as a YAML flow sequence so a one-line addition to the
        # frontmatter doesn't visually overwhelm the file. Patterns are
        # validated to be ASCII-safe and short, so JSON-style quoting is
        # always sufficient.
        quoted = ", ".join(json.dumps(p) for p in tenet.paths)
        fm.append(f"paths: [{quoted}]")
    fm.extend(["---", ""])
    body: list[str] = []
    # Generated-file marker. Discoverable by anyone reading the skill from
    # disk (via `find`, IDE search, etc.) without needing to know the
    # repo's CLAUDE.md "Hard rules" section that documents the contract.
    body.append(
        f"<!-- generated from {tenet.path.parent.name}/{tenet.path.name} "
        f"by `uv run poe build` — do not edit by hand. -->"
    )
    body.append("")
    body.append(f"# {tenet.id} — {tenet.title}")
    body.append("")
    body.append(f"_Type: {tenet.type} · Tier: {tenet.tier}_")
    body.append("")
    for section in REQUIRED_SECTIONS:
        content = tenet.sections.get(section, "").strip()
        body.append(f"## {section}")
        body.append("")
        body.append(content if content else "_(none)_")
        body.append("")
    # Optional sections — only emitted when present in the source. Keeps the
    # generated skill body lean for tenets that don't need them.
    for section in OPTIONAL_SECTIONS:
        content = tenet.sections.get(section, "").strip()
        if not content:
            continue
        body.append(f"## {section}")
        body.append("")
        body.append(content)
        body.append("")

    return skill_name, "\n".join(fm) + "\n".join(body).rstrip() + "\n"


def render_tier1_hook_payload(rendered_bundle: str) -> str:
    """Wrap a rendered Tier 1 bundle as a SessionStart hook JSON payload.

    The hook script writes this verbatim to stdout. Claude Code reads it as
    {"hookSpecificOutput": {"hookEventName": "SessionStart",
    "additionalContext": "..."}} and injects additionalContext into session
    context.
    """
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": rendered_bundle,
        }
    }
    return json.dumps(payload, ensure_ascii=False)


def render_index_json(tenets: Iterable[Tenet]) -> str:
    """Generate build/index.json — structured tenet metadata for `lookup-tenet`.

    Schema is intentionally flat — one object per tenet, every queryable
    field at the top level, no nesting beyond `applies_to`. Schema version
    is embedded so consumers can detect breaking changes.
    """
    sorted_tenets = sorted(tenets, key=lambda t: t.id)
    payload = {
        "schema_version": 1,
        "tenets": [
            {
                "id": t.id,
                "title": t.title,
                "type": t.type,
                "tier": t.tier,
                "applies_to": t.applies_to,
                "paths": t.paths,
                "tags": t.tags,
                "related": t.related,
                "since": t.since,
                "skill": _skill_name_for(t),
            }
            for t in sorted_tenets
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def read_charter_preamble(plugin_root: Path) -> str:
    """Read templates/charter-preamble.md from the plugin root.

    The preamble is the static charter intro (Protocol + Rationalizations).
    Keeping it as a markdown file rather than a Python literal lets authors
    edit the always-on session contract without touching build code.
    """
    path = plugin_root / "templates" / "charter-preamble.md"
    return path.read_text(encoding="utf-8")
