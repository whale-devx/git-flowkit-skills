# Roadmap and acceptance gates

## Implemented foundation

Portable SKILL.md, standard-library CLI, schema-validated local/global JSON configuration,
custom templates, repository/template discovery, branch and commit checks, advisory
single-package SemVer, offline merge-evidence checks, and opt-in Release Please setup.
Tests exercise real temporary Git repositories and unsafe-input regressions. English and
Thai entrypoints, contribution guidelines, and a cross-platform CI matrix are included.

## Before the first public release

Require green remote CI, review the initial PR, confirm installation using the actual
Skills CLI, and run recorded sessions in the target coding agents. Configure branch
protection and review the release activation checklist. Only then enable release
creation and review the generated version/changelog. No stable-release claim before this.

## Next: native integrations with evidence

Add fixture-driven comparisons against native Release Please, semantic-release and
Changesets plans; do not translate unknown policies silently. Add a tested provider
adapter for live merge evidence only when its permissions, pagination, review semantics,
merge queues and HEAD-race handling have contract tests. Preserve offline use.

## Later, after demand is demonstrated

Extend monorepo/package selection through native engines, prerelease/maintenance-channel
integration, reproducible release artifacts, and additional translations. Registry
publishing, signing and provenance each require a separate threat model and explicit
opt-in. Avoid a dashboard, SaaS dependency, or new release engine without demonstrated need.

Measure successful setup without overwrites, repeated real-repository use, policy-detection
errors, and compatibility evidence. Stars or directory listings alone do not establish
reliability or product demand. These are future goals, not shipped capabilities.
