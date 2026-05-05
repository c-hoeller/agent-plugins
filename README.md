# hoeller-agent-plugins

Claude Code plugin marketplace.

## Available plugins

| Name                                | What it does                                                                                |
|-------------------------------------|---------------------------------------------------------------------------------------------|
| [warden](plugins/warden/README.md)  | Senior coding standards as Engineering Tenets, auto-loaded into every Claude Code session.  |

## Installation

In a Claude Code session:

```text
/plugin marketplace add <git-url-of-this-repo>
/plugin install warden@hoeller-agent-plugins
```

The marketplace exposes each plugin as a separate installable. Install
only what you want; plugins are independent.

## Repository layout

```text
.
├── .claude-plugin/
│   └── marketplace.json     # marketplace manifest, lists all plugins
├── plugins/
│   └── warden/              # one plugin per subdirectory
└── README.md
```

Each `plugins/<name>/` directory is a self-contained Claude Code
plugin with its own `.claude-plugin/plugin.json`, `hooks/`, `skills/`,
and content.

## License

MIT
