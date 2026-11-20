# Configuration

The implemented format is JSON: `.git-flowkit.json` at the Git working-tree root.
The bundled [JSON Schema](../assets/config.schema.json) rejects unknown keys and wrong
types. `version: 1` is required. The Python validator supports only the schema keywords
used in this bundled schema; it is not a general-purpose JSON Schema implementation.

## Resolution

Policy values deep-merge in this order: bundled defaults < user global < repository.
Arrays replace rather than concatenate. `config` prints the effective values and layer
paths. Native release configuration remains authoritative for actual releases; FlowKit
preview settings do not silently rewrite native rules. The agent must inspect other
repository policies (including commitlint) and report differences.

Templates resolve separately: `--template` > repository `templates` pointer > native
PR/MR or commit template > global pointer > bundled template. Multiple native PR/MR
templates fail with an actionable selection error. Ordinary native Markdown is kept
as-is; an agent fills its sections rather than pretending they have `${field}` tokens.

Global config location: `GIT_FLOWKIT_CONFIG` when explicitly set; otherwise
`$XDG_CONFIG_HOME/git-flowkit/config.json`, or `~/.config/git-flowkit/config.json`.
On Windows, `%APPDATA%` is used when XDG is absent. `GIT_FLOWKIT_NO_GLOBAL=1` disables
global reads (recommended for CI). Global template pointers are relative to that
config's directory. Local and explicit pointers are repository-relative.

## Supported fields

| Field | Default / semantics |
| --- | --- |
| `branch.pattern` | `{type}/{ticket}{slug}`; exactly one type and slug; optional ticket |
| `branch.types` | feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert, hotfix, release |
| `branch.max_length` | 100 characters |
| `commit.types` | Same commit types, without hotfix/release |
| `commit.max_subject_length` | 100 characters; change to 72 for your team |
| `commit.require_scope` | false |
| `templates.commit`, `.pr`, `.merge`, `.release` | Optional relative Markdown file paths |
| `merge.required_approvals` | 1; an advisory check, never a replacement for provider policy |
| `release.engine` | auto; explicit selection required when multiple engines are found |
| `release.tag_prefix` | v |
| `release.pre1_breaking` | major; choose minor for a pre-1.0 development policy |
| `release.pre1_features` | minor; optionally patch |
| `release.rules` | feat: minor, fix: patch, perf: patch; other types: none |

A breaking marker always takes precedence over the type's rule. Before 1.0, the
breaking policy applies before the feature policy. The **perf: patch** default is our
policy, not a requirement of Conventional Commits. Branch patterns are also project
policy, not a claim of conformance to a separate Conventional Branch specification.
`{ticket}` expands to the ticket plus a trailing hyphen, or an empty string.

Only literal text and `{type}`, `{ticket}`, `{slug}` are accepted in branch patterns.
No expressions, format conversions, executable hooks, or remote template URLs exist.
Commit/PR descriptions may use Unicode; generated branch slugs are ASCII.

## Setup and customization

`init` previews a minimal config and editable templates. `init --apply` creates missing
files; existing files are always preserved. Local init does **not** automatically bind
the new templates, so it cannot override native templates unintentionally. Select one:

```json
{
  "version": 1,
  "templates": { "pr": ".git-flowkit/templates/pr.md" },
  "commit": { "require_scope": true, "max_subject_length": 72 }
}
```

`init --global --apply` creates a global config pointing to its editable templates.
For another project use `--repo PATH` before `init`. Review diffs in your editor or
Git before committing. File creation is exclusive per file, not a multi-file atomic
transaction; an interrupted setup may leave a subset. Re-running init is safe.

Do not use YAML under this filename. Do not enable remote execution through config:
this CLI has no such setting. Future schema changes require explicit migrations.
