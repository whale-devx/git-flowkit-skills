# Templates and CLI

Run `python <skill-directory>/scripts/flowkit.py --repo <target> COMMAND`.
Place the global `--repo` option before the command. No `git-flowkit` npm executable
is published or required. Python 3.11+ and Git are the helper runtime dependencies.

| Command | Effect |
| --- | --- |
| `doctor`, `config`, `validate` | Read-only repository inspection and validation |
| `init [--global] [--apply]` | Preview; optionally create missing config/templates |
| `branch TYPE DESCRIPTION [--ticket ID]` | Print a name, do not create a branch |
| `check-branch NAME` | Validate the configured pattern and Git ref syntax |
| `check-commit --message TEXT` or `--file PATH` | Validate a real commit message |
| `render KIND --data PATH [--template RELATIVE_PATH]` | Render commit/pr/merge/release text to stdout |
| `release-preview --current X.Y.Z --since REF` | Read real history after an explicit release boundary |
| `release-preview --current X.Y.Z --commits PATH` | Analyze a JSON array without guessing history |
| `release-setup [--branch main] [--initial-version 0.0.0] [--apply]` | Scaffold opt-in Release Please |
| `merge-check --evidence PATH` | Advisory offline check; never merges |

Exit codes: 0 success, 1 merge blocked, 2 invalid input/configuration or another handled
error. JSON errors go to stderr. Branch and rendered template text go to stdout;
other command results use JSON. Full help is available with `--help`.

## Template data

Templates replace only literal `${field_name}` placeholders, in one pass. No evaluation,
shell execution, recursion, or automatic downloads occur. Missing fields are errors;
unused data fields are allowed. Data is a flat JSON object of strings.

| Template | Required fields in the bundled default |
| --- | --- |
| commit | type, scope, breaking, summary, body, footers |
| pr | summary, motivation, changes, validation, risks, release_impact, issues |
| merge | title, summary, breaking_changes, references |
| release | version, summary, changes, breaking_changes, validation |

For commit rendering, `scope` includes parentheses (or is empty); `breaking` is `!`
(or empty). Use empty strings for optional body/footer fields. Rendered commit and
merge text is validated against the configured commit profile. A merge title is the
Conventional Commit subject, not a provider-generated `Merge pull request ...` string.

A PR must distinguish executed tests from planned or skipped checks. Preserve complete
breaking-change footers when squashing. The CLI does not configure the provider's
squash-message settings, and cannot ensure a maintainer keeps the proposed text.

Templates can be written in any language. Keep machine tokens (`feat`, `fix`,
`BREAKING CHANGE`, version numbers and paths) intact; translate explanatory prose.
