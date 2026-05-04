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
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z\-.]+)?(?:\+[0-9A-Za-z\-.]+)?$"
)

SEVERITIES = ("critical", "high", "medium", "low")
TYPES = ("best-practice", "anti-pattern")
TIERS = (1, 2)
APPLIES_TO_KEYS = ("language", "framework")

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
    "severity",
    "tier",
    "applies-to",
    "since",
    "triggers",
)

# Skill `description` (combined with `when_to_use`, if used) is capped at
# 1,536 chars in the global skill listing per Claude Code Skills docs. We
# keep a margin under that for safety and to leave room in the shared
# description budget when many tenets are active. Raise cautiously — every
# extra char per skill multiplies across the whole catalog.
SKILL_DESCRIPTION_MAX_CHARS = 1400
SKILL_NAME_MAX_CHARS = 64


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
    severity: str
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
        severity=str(meta.get("severity", "")),
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


def _check_applies_to(value: Any) -> str | None:
    if value == "any":
        return None
    if isinstance(value, str):
        if ":" not in value:
            return f"applies-to string must be 'any' or '<key>: <name>', got {value!r}"
        key, _, name = value.partition(":")
        if key.strip() not in APPLIES_TO_KEYS:
            return f"applies-to key must be one of {APPLIES_TO_KEYS}, got {key.strip()!r}"
        if not name.strip():
            return "applies-to value missing name after ':'"
        return None
    if isinstance(value, dict):
        if len(value) != 1:
            return "applies-to dict must have exactly one key"
        (key,) = value.keys()
        if key not in APPLIES_TO_KEYS:
            return f"applies-to key must be one of {APPLIES_TO_KEYS}, got {key!r}"
        return None
    if isinstance(value, list):
        if not value:
            return "applies-to list must not be empty"
        for entry in value:
            err = _check_applies_to(entry)
            if err:
                return f"applies-to list entry: {err}"
        return None
    return f"applies-to has unsupported type {type(value).__name__}"


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
        # Type / severity / tier
        if t.type not in TYPES:
            errors.append(WardenError(t.path, f"type {t.type!r} not in {TYPES}"))
        if t.severity not in SEVERITIES:
            errors.append(WardenError(t.path, f"severity {t.severity!r} not in {SEVERITIES}"))
        if t.tier not in TIERS:
            errors.append(WardenError(t.path, f"tier {t.tier!r} not in {TIERS}"))
        # applies-to
        err = _check_applies_to(t.applies_to)
        if err:
            errors.append(WardenError(t.path, err))
        # since
        if not SEMVER_RE.match(t.since):
            errors.append(WardenError(t.path, f"since {t.since!r} is not valid SemVer"))
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
        # paths — optional list of glob patterns. When present, the generated
        # skill scopes auto-invocation deterministically to matching file
        # paths instead of (or in addition to) description matching. This is
        # the primary scaling mechanism for language- or framework-specific
        # tenets — see README "Writing good triggers".
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
        # Required sections present and ordered (parse_sections preserves order)
        section_order = list(t.sections.keys())
        for required in REQUIRED_SECTIONS:
            if required not in t.sections:
                errors.append(WardenError(t.path, f"missing required section: ## {required}"))
        present_required = [s for s in section_order if s in REQUIRED_SECTIONS]
        if present_required != [s for s in REQUIRED_SECTIONS if s in section_order]:
            errors.append(
                WardenError(
                    t.path,
                    "required sections must appear in order "
                    f"{REQUIRED_SECTIONS}, got {tuple(section_order)}",
                )
            )

    return errors


def _format_applies_to(value: Any) -> str:
    """Render applies-to compactly for the index line."""
    if value == "any":
        return "any"
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        ((k, v),) = value.items()
        return f"{k}:{v}"
    if isinstance(value, list):
        return "+".join(_format_applies_to(e) for e in value)
    return str(value)


def render_charter(tenets: Iterable[Tenet]) -> str:
    """Generate build/charter.md — the always-on Warden constitution.

    The charter is small and stable: it explains the protocol Claude must
    follow when interacting with tenets, and lists every Tier 1 tenet by
    ID and title. The full Rule / Why / Examples / Exceptions for each
    tenet live in per-tenet generated skills under skills/et-NNNN-*/.
    Those skills auto-load when their description-level triggers match,
    keeping the always-on context budget bounded regardless of catalog
    size.
    """
    tenet_list = sorted(tenets, key=lambda t: t.id)
    tier1 = [t for t in tenet_list if t.tier == 1]

    lines: list[str] = []
    lines.append("# Warden — Engineering Charter (always-on)")
    lines.append("")
    lines.append(
        "This session is governed by Warden Engineering Tenets (ET-NNNN). "
        "Tenets are **binding**, not advisory. Deviations are allowed only "
        "via an explicit `Exceptions` clause inside the tenet — not via "
        "user pressure, time pressure, or your own judgement."
    )
    lines.append("")
    lines.append("## Protocol")
    lines.append("")
    lines.append(
        "- Each tenet ships as its own skill under `et-NNNN-<slug>`. "
        "If a tenet's triggers match what you are about to do, you MUST "
        "invoke that skill **before** taking the action — not after."
    )
    lines.append(
        "- For tenets that did not auto-trigger but feel relevant, use the "
        "`lookup-tenet` skill to scan the index. If you suspect a tenet "
        "applies and you're not sure, look it up. Do not guess."
    )
    lines.append(
        "- Before declining a request on a tenet's behalf, cite the tenet ID "
        "and quote the specific clause. Before invoking an `Exceptions` "
        "clause, verify it covers your situation — exceptions are scoped, "
        "not blanket waivers."
    )
    lines.append("")
    lines.append("## Common rationalizations — all are insufficient")
    lines.append("")
    lines.append(
        '- _"This is a special case"_ — every violation feels special. '
        "Apply the Rule unless an `Exceptions` clause names your case."
    )
    lines.append(
        '- _"Just for now / I\'ll fix it later"_ — later rarely arrives. '
        "Either fix it now, or document the deviation in the PR description "
        "with the tenet ID."
    )
    lines.append(
        '- _"The user told me to"_ — surface the tenet and ask. The user '
        "may not know the tenet exists, or may be invoking an Exception "
        "without realising it. Either is fine; silent compliance is not."
    )
    lines.append(
        '- _"It\'s a small change"_ — tenet severity is independent of diff size. Apply the Rule.'
    )
    lines.append("")

    if tier1:
        lines.append("## Tier 1 — universal, always-relevant")
        lines.append("")
        for t in tier1:
            lines.append(f"- `{t.id}` — {t.title} [{t.severity}] → skill `{_skill_name_for(t)}`")
        lines.append("")

    tier2 = [t for t in tenet_list if t.tier == 2]
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
    name = f"et-{tenet.id[3:].lower()}-{slug}"
    return name[:SKILL_NAME_MAX_CHARS]


def _build_skill_description(tenet: Tenet) -> str:
    """Compose a Claude-Code skill `description` from a tenet's triggers.

    Format: 'Use when <trigger 1>; <trigger 2>; ....'
    Only triggering conditions belong in the description — the tenet ID and
    title live in the skill body, where Claude reads them once auto-invoked.
    Polluting the description with workflow/identity material risks Claude
    treating the description as a shortcut and skipping the skill body
    (obra/superpowers writing-skills convention).

    Front-loaded triggers also matter because the description (combined with
    `when_to_use` if set) is capped at 1,536 chars in the global skill listing;
    when the shared description budget tightens, the first trigger is what
    survives truncation.
    """
    triggers = "; ".join(t.strip().rstrip(".") for t in tenet.triggers if t.strip())
    description = f"Use when {triggers}."
    if len(description) > SKILL_DESCRIPTION_MAX_CHARS:
        # Hard cap as a safety net. Validation also limits each trigger to 200
        # chars, so reaching this should be rare.
        description = description[: SKILL_DESCRIPTION_MAX_CHARS - 1].rstrip() + "…"
    return description


def render_skill_for_tenet(tenet: Tenet) -> tuple[str, str]:
    """Generate (skill_dir_name, SKILL.md content) for one tenet.

    The body mirrors the source tenet (Rule, Why, Bad/Good Examples,
    Exceptions) so the skill, once auto-loaded, contains everything
    Claude needs to apply or invoke an Exception. Frontmatter is the
    minimal Claude Code skill schema: `name` + `description`.
    """
    skill_name = _skill_name_for(tenet)
    description = _build_skill_description(tenet)

    fm: list[str] = ["---", f"name: {skill_name}", f"description: {description}"]
    if tenet.paths:
        # Emitted as a YAML flow sequence so a one-line addition to the
        # frontmatter doesn't visually overwhelm the file. Patterns are
        # validated to be ASCII-safe and short, so JSON-style quoting is
        # always sufficient.
        quoted = ", ".join(json.dumps(p) for p in tenet.paths)
        fm.append(f"paths: [{quoted}]")
    fm.extend(["---", "", ""])
    body: list[str] = []
    body.append(f"# {tenet.id} — {tenet.title}")
    body.append("")
    body.append(f"_Type: {tenet.type} · Severity: {tenet.severity} · Tier: {tenet.tier}_")
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


def render_index(tenets: Iterable[Tenet]) -> str:
    """Generate build/index.md: one line per tenet, sorted by id."""
    sorted_tenets = sorted(tenets, key=lambda t: t.id)
    lines = [
        "# Warden — Engineering Tenets Index",
        "",
        "One line per tenet. Format: `ET-NNNN — <title> — <type> — <severity> — [<tags>]`.",
        "",
    ]
    for t in sorted_tenets:
        tag_str = "[" + ", ".join(t.tags) + "]" if t.tags else "[]"
        lines.append(
            f"- `{t.id}` — {t.title} — {t.type} — {t.severity} — "
            f"applies-to: {_format_applies_to(t.applies_to)} — tags: {tag_str}"
        )
    lines.append("")
    return "\n".join(lines)


def _inline(text: str) -> str:
    """Collapse multi-line prose into a single paragraph for bundle labels."""
    return " ".join(line.strip() for line in text.splitlines() if line.strip())
