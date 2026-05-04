from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))


BODY_TEMPLATE = """\
## Rule

{rule}

## Why

{why}

## Bad Example

```ts
// bad
```

## Good Example

```ts
// good
```

## Exceptions

{exceptions}
"""


def make_tenet_file(
    tenets_dir: Path,
    *,
    id: str = "ET-0001",
    slug: str = "example-tenet",
    title: str = "Example tenet",
    type: str = "best-practice",
    tier: int = 1,
    applies_to: Any = "any",
    triggers: list[str] | None = None,
    tags: list[str] | None = None,
    related: list[str] | None = None,
    since: str = "0.1.0",
    rule: str = "Do the right thing.",
    why: str = "Because it's right.",
    exceptions: str = "None.",
) -> Path:
    frontmatter: dict[str, Any] = {
        "id": id,
        "title": title,
        "type": type,
        "tier": tier,
        "applies-to": applies_to,
        "triggers": triggers if triggers is not None else ["the rule applies to this change"],
        "tags": tags if tags is not None else [],
        "related": related if related is not None else [],
        "since": since,
    }
    fm_yaml = yaml.safe_dump(frontmatter, sort_keys=False).rstrip()
    body = BODY_TEMPLATE.format(rule=rule, why=why, exceptions=exceptions)
    content = f"---\n{fm_yaml}\n---\n\n{body}"
    path = tenets_dir / f"{id}-{slug}.md"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def tenets_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tenets"
    d.mkdir()
    return d


@pytest.fixture
def valid_tenet(tenets_dir: Path) -> Path:
    return make_tenet_file(tenets_dir)


@pytest.fixture
def make_tenet(tenets_dir: Path):
    def _factory(**overrides):
        return make_tenet_file(tenets_dir, **overrides)

    return _factory
