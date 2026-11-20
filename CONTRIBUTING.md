# Contributing

Keep Git FlowKit portable, inspectable, and non-destructive. A new feature should solve
a reproducible workflow problem, not simply add another prompt or engine abstraction.

Use Python 3.11+ and Git. The helpers and tests use the standard library only:

```bash
python -m unittest discover -s tests -v
python tools/validate_repo.py
```

Create a focused branch, use Conventional Commits, and open a PR with actual validation
results. Use a conventional PR title for squash merges. Add a regression test for a bug
and update the English/Thai entrypoints when changing user-facing behavior. Never publish
or change repository protections as part of an ordinary contribution.

Config additions must update defaults, schema, validation tests and the configuration
reference together. Template edits must preserve machine-readable breaking markers.
Release changes require tests for pre-1.0 behavior, tag collisions, native engine ownership,
and non-destructive setup. Do not replace a native engine or silently add credentials.

Useful contributions: agent/version-specific installation evidence, safe engine fixtures,
translations, Windows edge cases, and failures where existing policy was misunderstood.
Record actual outcomes; do not label a provider supported merely because its name appears
in installer documentation. Keep external actions SHA-pinned and review dependency changes.

Security issues follow [SECURITY.md](SECURITY.md), not public reproduction details.
Contributions are under the existing MIT license; retain attribution when reusing code.
